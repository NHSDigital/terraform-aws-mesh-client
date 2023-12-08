"""
Module for MESH API functionality for step functions
"""
import os
from collections.abc import Generator
from http import HTTPStatus

from nhs_aws_helpers import s3_client
from spine_aws_common import LambdaApplication

from mesh_client_aws_serverless.mesh_common import MeshCommon
from mesh_client_aws_serverless.mesh_mailbox import MeshMailbox, MeshMessage


class MaxByteExceededException(Exception):
    """Raised when a file has more chunks, but no more bytes"""

    def __init__(self, msg=None):
        super().__init__()
        self.msg = msg


class MeshSendMessageChunkApplication(LambdaApplication):
    """
    MESH API Lambda for sending a message / message chunk
    """

    MEBIBYTE = 1024 * 1024
    DEFAULT_BUFFER_SIZE = 20 * MEBIBYTE

    def __init__(self, additional_log_config=None, load_ssm_params=False):
        """
        Init variables
        """
        super().__init__(additional_log_config, load_ssm_params)
        self.input = {}
        self.body = None
        self.environment = os.environ.get("Environment", "default")
        self.chunked = False
        self.current_byte = 0
        self.current_chunk = 1
        self.chunk_size = MeshCommon.DEFAULT_CHUNK_SIZE
        self.compression_ratio = 1
        self.will_compress = False
        self.s3_client = s3_client()
        self.bucket = ""
        self.key = ""
        self.buffer_size = self.DEFAULT_BUFFER_SIZE
        self.file_size = 0

    def initialise(self):
        """Setup class variables"""
        self.input = self.event.get("body")
        self.response = self.event.raw_event
        self.current_byte = self.input.get("current_byte_position", 0)
        self.current_chunk = self.input.get("chunk_number", 1)
        self.chunk_size = self.input.get("chunk_size", MeshCommon.DEFAULT_CHUNK_SIZE)
        self.chunked = self.input.get("chunked", False)
        self.compression_ratio = self.input.get("compress_ratio", 1)
        self.will_compress = self.input.get("will_compress", False)
        if self.chunked:
            self.will_compress = True
        self.bucket = self.input["bucket"]
        self.key = self.input["key"]
        return super().initialise()

    def _get_file_from_s3(self) -> Generator[bytes, None, None]:
        """Get a file or chunk of a file from S3"""
        start_byte = self.current_byte
        end_byte = start_byte + (self.chunk_size * self.compression_ratio)
        if end_byte > self.file_size:
            end_byte = self.file_size
        while self.current_byte < end_byte:
            bytes_to_end = end_byte - self.current_byte
            if bytes_to_end > self.buffer_size:
                range_spec = f"bytes={self.current_byte}-{self.current_byte + self.buffer_size - 1}"
                self.current_byte = self.current_byte + self.buffer_size
            else:
                range_spec = f"bytes={self.current_byte}-{end_byte-1}"
                self.current_byte = end_byte

            response = self.s3_client.get_object(
                Bucket=self.bucket, Key=self.key, Range=range_spec
            )

            body = response.get("Body")
            assert body

            file_content = body.read()

            self.log_object.write_log(
                "MESHSEND0006",
                None,
                {
                    "file": self.key,
                    "bucket": self.bucket,
                    "num_bytes": len(file_content),
                    "byte_range": range_spec,
                },
            )
            yield file_content

    def start(self):
        """Main body of lambda"""

        is_finished = self.input.get("complete", False)
        if is_finished:
            self.response.update({"statusCode": HTTPStatus.INTERNAL_SERVER_ERROR.value})
            raise SystemError("Already completed upload to MESH")

        total_chunks = self.input.get("total_chunks", 1)
        message_id = self.input.get("message_id", None)

        file_response = self.s3_client.head_object(Bucket=self.bucket, Key=self.key)
        metadata = file_response.get("Metadata", {})

        dest_mailbox = self.input.get("dest_mailbox") or metadata.get("mex-to")
        assert dest_mailbox
        workflow_id = self.input.get("workflow_id") or metadata.get(
            "mex-workflowid", ""
        )

        self.file_size = file_response["ContentLength"]
        self.log_object.write_log(
            "MESHSEND0005",
            None,
            {
                "file": self.key,
                "bucket": self.bucket,
                "chunk_num": self.current_chunk,
                "max_chunk": total_chunks,
            },
        )

        with MeshMailbox(
            self.log_object, self.input["src_mailbox"], self.environment
        ) as mailbox:
            message_object = MeshMessage(
                content=self._get_file_from_s3(),
                file_name=os.path.basename(self.key),
                metadata=metadata,
                message_id=message_id,
                dest_mailbox=dest_mailbox,
                src_mailbox=mailbox.mailbox,
                workflow_id=workflow_id,
                will_compress=self.will_compress,
            )

            if self.file_size > 0:
                mailbox_response = mailbox.send_chunk(
                    mesh_message_object=message_object,
                    number_of_chunks=total_chunks,
                    chunk_num=self.current_chunk,
                )
                status_code = mailbox_response.status_code
                if self.current_chunk == 1:
                    message_id = mailbox_response.json()["message_id"]
                status_code = HTTPStatus.OK.value
            else:
                status_code = HTTPStatus.NOT_FOUND.value
                self.response.update({"statusCode": status_code})
                raise FileNotFoundError

            is_finished = self.current_chunk >= total_chunks if self.chunked else True
            if self.current_byte >= self.file_size and not is_finished:
                raise MaxByteExceededException
            if self.chunked and not is_finished:
                self.current_chunk += 1

            if is_finished:
                # check mailbox for any reports
                self.log_object.write_log(
                    "MESHSEND0008",
                    None,
                    {
                        "file": self.key,
                        "bucket": self.bucket,
                        "chunk_num": self.current_chunk,
                        "max_chunk": total_chunks,
                    },
                )
        # update input event to send as response
        self.response.update({"statusCode": status_code})
        self.response["body"].update(
            {
                "complete": is_finished,
                "message_id": message_id,
                "chunk_number": self.current_chunk,
                "current_byte_position": self.current_byte,
                "will_compress": self.will_compress,
            }
        )


# create instance of class in global space
# this ensures initial setup of logging/config is only done on cold start
app = MeshSendMessageChunkApplication()


def lambda_handler(event, context):
    """Standard lambda_handler"""
    return app.main(event, context)
