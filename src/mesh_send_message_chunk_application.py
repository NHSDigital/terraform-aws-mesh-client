from collections.abc import Generator
from dataclasses import asdict
from http import HTTPStatus
from io import BytesIO
from typing import Any

from mypy_boto3_s3.service_resource import Object
from shared.application import MESHLambdaApplication
from shared.send_parameters import SendParameters, get_send_parameters


class MaxByteExceededException(Exception):
    """Raised when a file has more chunks, but no more bytes"""

    def __init__(self, msg=None):
        super().__init__()
        self.msg = msg


class MeshSendMessageChunkApplication(MESHLambdaApplication):
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

        self.environment = self.config.environment
        self.input = {}
        self.body = None
        self.from_event_bridge = False

        self.current_byte = 0
        self.current_chunk = 1

        self.s3_object: Object = None  # type: ignore[assignment]
        self.send_params: SendParameters = None  # type: ignore[assignment]

    def initialise(self):
        """Setup class variables"""
        super().initialise()
        self.s3_object = None  # type: ignore[assignment]
        self.from_event_bridge = self.event.get("source") == "aws.s3"
        self.input = {} if self.from_event_bridge else self.event.get("body", {})
        self.current_byte = self.input.get("current_byte_position", 0)
        self.current_chunk = self.input.get("chunk_number", 1)
        self.send_params = self._get_send_params()
        self.response: dict[str, Any] = (
            {
                "statusCode": int(HTTPStatus.INTERNAL_SERVER_ERROR),
                "headers": {"Content-Type": "application/json"},
                "body": {
                    "internal_id": self.log_object.internal_id,
                },
            }
            if self.from_event_bridge
            else self.event.raw_event
        )

        self.response["body"]["send_params"] = asdict(self.send_params)

        # Execution ID can come from the Step Function context or we use the internalID (e.g. direct invocation)
        self.execution_id = (
            self.input.get("execution_id") or self.log_object.internal_id
        )
        # Again, might not be from the Step Function context if directly invoked via EventBridge.
        self.lock_name = (
            self.input.get("lock_name") or self.send_params.send_lock_name()
        )

    def _get_send_params(self) -> SendParameters:
        # invoked from most recent check send params or from another send message chunk
        from_input = self.input.get("send_params")
        if from_input:
            return SendParameters(**from_input)

        # invoked directly from event bridge trigger or from a previous function version
        detail = self.event.get("detail", {})
        bucket = self.input.get(
            "bucket", detail.get("requestParameters", {}).get("bucketName")
        )
        key = self.input.get("key", detail.get("requestParameters", {}).get("key"))
        self.s3_object = self.s3.Object(bucket, key)

        return get_send_parameters(self.s3_object, self.config, self.ssm)

    def _get_chunk_from_s3(self) -> Generator[bytes, None, None]:
        """Get a file or chunk of a file from S3"""
        start_byte = self.current_byte
        end_byte = start_byte + self.config.chunk_size
        if end_byte > self.s3_object.content_length:
            end_byte = self.s3_object.content_length
        while self.current_byte < end_byte:
            bytes_to_end = end_byte - self.current_byte
            if bytes_to_end > self.config.crumb_size:
                range_spec = f"bytes={self.current_byte}-{self.current_byte + self.config.crumb_size - 1}"
                self.current_byte = self.current_byte + self.config.crumb_size
            else:
                range_spec = f"bytes={self.current_byte}-{end_byte-1}"
                self.current_byte = end_byte

            response = self.s3_object.get(Range=range_spec)

            body = response.get("Body")
            assert body

            file_content = body.read()

            self.log_object.write_log(
                "MESHSEND0006",
                None,
                {
                    "file": self.s3_object.key,
                    "bucket": self.s3_object.bucket_name,
                    "num_bytes": len(file_content),
                    "byte_range": range_spec,
                },
            )
            yield file_content

    def start(self):
        """Main body of lambda"""

        complete = self.input.get("complete", False)
        if complete:
            self.response.update({"statusCode": int(HTTPStatus.INTERNAL_SERVER_ERROR)})
            raise SystemError("Already completed upload to MESH")

        send_params = self.send_params

        self.log_object.write_log(
            "MESHSEND0004a",
            None,
            {
                "src_mailbox": send_params.sender,
                "dest_mailbox": send_params.recipient,
                "workflow_id": send_params.workflow_id,
            },
        )

        self._acquire_lock(self.lock_name, self.execution_id)

        if not self.s3_object:
            self.s3_object = self.s3.Object(send_params.s3_bucket, send_params.s3_key)

        _ = self.s3_object.content_length  # trigger a 'head-object' request

        message_id = self.input.get("message_id", "")
        total_chunks = send_params.total_chunks

        self.log_object.write_log(
            "MESHSEND0005",
            None,
            {
                "file": send_params.s3_key,
                "bucket": send_params.s3_bucket,
                "chunk_num": self.current_chunk,
                "max_chunk": send_params.total_chunks,
            },
        )

        self.mailbox_id = send_params.sender

        if send_params.file_size < 1:
            self.response.update({"statusCode": int(HTTPStatus.NOT_FOUND)})
            raise FileNotFoundError

        with self:
            mailbox_response = self.send_chunk(
                message_id=message_id,
                content=self._get_chunk_from_s3(),
                send_params=send_params,
                chunk_num=self.current_chunk,
            )

            if self.current_chunk == 1:
                message_id = mailbox_response.json()["message_id"]

        self.response.update({"statusCode": int(HTTPStatus.OK)})

        complete = bool(
            self.current_chunk >= total_chunks if send_params.chunked else True
        )

        if self.current_byte >= send_params.file_size and not complete:
            raise MaxByteExceededException

        if send_params.chunked and not complete:
            self.current_chunk += 1

        if complete:
            # check mailbox for any reports
            self.log_object.write_log(
                "MESHSEND0008",
                None,
                {
                    "file": send_params.s3_key,
                    "bucket": send_params.s3_bucket,
                    "chunk_num": self.current_chunk,
                    "max_chunk": total_chunks,
                },
            )

        self.response["body"].update(
            {
                "complete": complete,
                "message_id": message_id,
                "chunk_number": self.current_chunk,
                "current_byte_position": self.current_byte,
            }
        )

    def send_chunk(
        self,
        message_id: str,
        content: Generator[bytes, None, None],
        send_params: SendParameters,
        chunk_num: int = 1,
    ):
        """Send a chunk from a stream"""

        kwargs = send_params.to_client_kwargs()
        if chunk_num > 1:
            kwargs["message_id"] = message_id

        chunk = BytesIO(b"".join(chunk for chunk in content))

        response = self.mesh_client.send_chunk(
            chunk=chunk,
            chunk_num=chunk_num,
            **kwargs,
        )
        response.raw.decode_content = True

        if chunk_num == 1:
            message_id = response.json()["message_id"]

        self.log_object.write_log(
            "MESHSEND0007",
            None,
            {
                "file": send_params.filename,
                "http_status": response.status_code,
                "message_id": message_id,
                "chunk_num": chunk_num,
                "max_chunk": send_params.total_chunks,
            },
        )
        return response


# create instance of class in global space
# this ensures initial setup of logging/config is only done on cold start
app = MeshSendMessageChunkApplication()


def lambda_handler(event, context):
    """Standard lambda_handler"""
    return app.main(event, context)
