import json
import os
from http import HTTPStatus

from botocore.exceptions import ClientError
from nhs_aws_helpers import s3_client
from requests import Response
from requests.structures import CaseInsensitiveDict
from shared.common import MeshCommon, nullsafe_quote
from shared.mailbox import MeshMailbox
from spine_aws_common import LambdaApplication

_METADATA_HEADERS = {
    "mex-to",
    "mex-from",
    "mex-workflowid",
    "mex-filename",
    "mex-subject",
    "mex-localid",
    "mex-partnerid",
    "mex-messagetype",
    "mex-statuscode",
    "mex-statusdescription",
    "mex-statussuccess",
}


def metadata_from_headers(headers: CaseInsensitiveDict) -> dict[str, str]:
    return {
        mex: nullsafe_quote(headers.get(mex))
        for mex in _METADATA_HEADERS
        if mex in headers
    }


def get_content_type(response: Response) -> str:
    return response.headers.get("Content-Type") or "application/octet-stream"


class MeshFetchMessageChunkApplication(LambdaApplication):
    """
    MESH API Lambda for sending a message
    """

    MEBIBYTE = 1024 * 1024
    DEFAULT_BUFFER_SIZE = 5 * MEBIBYTE

    def __init__(self, additional_log_config=None, load_ssm_params=False):
        """
        Init variables
        """
        super().__init__(additional_log_config, load_ssm_params)
        self.input = {}
        self.environment = os.environ.get("Environment", "default")
        self.chunk_size = os.environ.get("CHUNK_SIZE", MeshCommon.DEFAULT_CHUNK_SIZE)
        self._http_response: Response | None = None
        self.response = {}
        self.internal_id = None
        self.aws_upload_id: str = ""
        self.aws_current_part_id = 0
        self.aws_part_etags = []
        self.chunked = False
        self.number_of_chunks = 0
        self.current_chunk = 0
        self.message_id = None
        self.s3_client = s3_client()
        self.s3_bucket = ""
        self.http_headers_bytes_read = 0
        self.s3_key = ""
        self.s3_tempfile_key = None

    def initialise(self):
        """decode input event"""
        self.input = self.event.get("body")
        self.internal_id = self.input.get("internal_id", "Not Provided")
        self.aws_upload_id = self.input.get("aws_upload_id", "Not Provided")
        self.aws_current_part_id = self.input.get("aws_current_part_id", 1)
        self.aws_part_etags = self.input.get("aws_part_etags", [])
        self.chunked = bool(self.input.get("chunked", False))
        self.current_chunk = self.input.get("chunk_num", 1)
        self.message_id = self.input["message_id"]
        self.response = self.event.raw_event
        self.log_object.internal_id = self.internal_id

    @property
    def http_response(self) -> Response:
        assert (
            self._http_response is not None
        ), "http_response not initialised, call start"
        return self._http_response

    def start(self):
        self.log_object.write_log(
            "MESHFETCH0001",
            None,
            {
                "message_id": self.message_id,
            },
        )
        with MeshMailbox(
            self.log_object, self.input["dest_mailbox"], self.environment
        ) as mailbox:
            # get stream for this chunk
            self._http_response = mailbox.get_chunk(
                self.message_id, chunk_num=self.current_chunk
            )
            self.number_of_chunks = self._get_number_of_chunks()
            self.http_response.raise_for_status()
            self.chunked = (
                self.http_response.status_code == HTTPStatus.PARTIAL_CONTENT.value
            )
            self._get_aws_bucket_and_key(mailbox)

            if self.http_response.headers.get("Mex-Messagetype") == "REPORT":
                self._handle_report_message(mailbox)
            elif self.number_of_chunks == 1:
                self._handle_single_chunk_message(mailbox)
            else:
                self._handle_multiple_chunk_message(mailbox)

    def _handle_multiple_chunk_message(self, mailbox: MeshMailbox):
        self.log_object.write_log(
            "MESHFETCH0013", None, {"message_id": self.message_id}
        )
        if self.current_chunk == 1:
            self._create_multipart_upload()
        self._read_bytes_into_buffer()
        self.log_object.write_log(
            "MESHFETCH0001a",
            None,
            {
                "length": self.http_headers_bytes_read,
                "message_id": self.message_id,
            },
        )
        last_chunk = self._is_last_chunk(self.current_chunk)
        if last_chunk:
            self._finish_multipart_upload()
            mailbox.acknowledge_message(self.message_id)
            self.log_object.write_log(
                "MESHFETCH0004", None, {"message_id": self.message_id}
            )
        else:
            self.current_chunk += 1
            self.log_object.write_log(
                "MESHFETCH0003",
                None,
                {"chunk": self.current_chunk, "message_id": self.message_id},
            )
        self._update_response(complete=last_chunk)

    def _handle_single_chunk_message(self, mailbox: MeshMailbox):
        self.log_object.write_log(
            "MESHFETCH0011", None, {"message_id": self.message_id}
        )
        chunk_data = self.http_response.raw.read(decode_content=True)
        self._upload_to_s3(
            chunk_data,
            s3_key=self.s3_key,
            content_type=get_content_type(self.http_response),
            metadata=metadata_from_headers(self.http_response.headers),
        )
        mailbox.acknowledge_message(self.message_id)
        self._update_response(complete=True)
        self.log_object.write_log(
            "MESHFETCH0012", None, {"message_id": self.message_id}
        )

    def _handle_report_message(self, mailbox: MeshMailbox):
        self.log_object.write_log(
            "MESHFETCH0010",
            None,
            {
                "message_id": self.message_id,
                "s3_bucket": self.s3_bucket,
                "s3_key": self.s3_key,
            },
        )
        buffer = json.dumps(dict(self.http_response.headers)).encode("utf-8")
        self.http_headers_bytes_read = len(buffer)
        self._upload_to_s3(
            buffer,
            s3_key=self.s3_key,
            content_type="application/json",
            metadata=metadata_from_headers(self.http_response.headers),
        )
        mailbox.acknowledge_message(self.message_id)
        self._update_response(complete=True)
        self.log_object.write_log(
            "MESHFETCH0012", None, {"message_id": self.message_id}
        )

    def _get_filename(self):
        file_name = (self.http_response.headers.get("Mex-Filename", "") or "").strip()
        if file_name:
            return file_name
        assert self.message_id
        if (
            self.http_response.headers.get("Mex-Messagetype", "") or ""
        ).upper() == "REPORT":
            return f"{self.message_id}.ctl"

        return f"{self.message_id}.dat"

    def _get_aws_bucket_and_key(self, mailbox: MeshMailbox):
        self.s3_bucket = mailbox.params["INBOUND_BUCKET"]
        s3_folder = (mailbox.params.get("INBOUND_FOLDER", "") or "").strip().rstrip("/")
        if len(s3_folder) > 0:
            s3_folder += "/"
        file_name = self._get_filename()
        self.s3_key = f"{s3_folder}{file_name}"
        self.log_object.write_log(
            "MESHFETCH0001c",
            None,
            {
                "message_id": self.message_id,
                "chunk_num": self.current_chunk,
                "s3_key": self.s3_key,
                "s3_bucket": self.s3_bucket,
                "s3_folder": s3_folder,
            },
        )

    def _is_last_chunk(self, chunk_num: int) -> bool:
        chunk_range = self.http_response.headers.get("Mex-Chunk-Range", "1:1")
        self.number_of_chunks = int(chunk_range.split(":")[1])
        return chunk_num == self.number_of_chunks

    def _get_number_of_chunks(self) -> int:
        chunk_range = self.http_response.headers.get("Mex-Chunk-Range", "1:1")
        number_of_chunks = int(chunk_range.split(":")[1])
        return number_of_chunks

    def _upload_part_to_s3(self, buffer):
        """Upload a part to S3 and check response"""
        overflow_filename = f"part_overflow_{self.message_id}.tmp"
        self.s3_tempfile_key = os.path.basename(self.s3_key) + overflow_filename

        # check if part_overflow_{message_id}.tmp exists and pre-pend to buffer
        try:
            s3_response = self.s3_client.get_object(
                Bucket=self.s3_bucket, Key=self.s3_tempfile_key
            )
            if s3_response["ResponseMetadata"]["HTTPStatusCode"] == HTTPStatus.OK.value:
                pre_buffer = s3_response["Body"].read()
                buffer = pre_buffer + buffer

                self.log_object.write_log(
                    "MESHFETCH0002b",
                    None,
                    {
                        "number_of_chunks": self.number_of_chunks,
                        "aws_part_size": len(pre_buffer),
                        "aws_upload_id": self.aws_upload_id,
                    },
                )

            self.s3_client.delete_object(
                Bucket=self.s3_bucket,
                Key=self.s3_tempfile_key,
            )
        except ClientError as e:
            self.log_object.write_log(
                "MESHFETCH0002c",
                None,
                {
                    "client_error": e,
                    "number_of_chunks": self.number_of_chunks,
                    "aws_upload_id": self.aws_upload_id,
                },
            )

        try:
            response = self.s3_client.upload_part(
                Body=buffer,
                Bucket=self.s3_bucket,
                Key=self.s3_key,
                PartNumber=self.aws_current_part_id,
                ContentLength=len(buffer),
                UploadId=self.aws_upload_id,
            )
        except ClientError as e:
            self.response.update({"statusCode": HTTPStatus.INTERNAL_SERVER_ERROR.value})
            self.log_object.write_log(
                "MESHFETCH0006",
                None,
                {
                    "key": self.s3_key,
                    "bucket": self.s3_bucket,
                    "content_length": len(buffer),
                    "aws_upload_id": self.aws_upload_id,
                    "error": e,
                },
            )
            raise e

        etag = response["ETag"]
        self.aws_part_etags.append(
            {
                "ETag": etag,
                "PartNumber": self.aws_current_part_id,
            }
        )
        self.aws_current_part_id += 1
        self.log_object.write_log(
            "MESHFETCH0002",
            None,
            {
                "number_of_chunks": self.number_of_chunks,
                "aws_part_id": self.aws_current_part_id,
                "aws_part_size": len(buffer),
                "aws_upload_id": self.aws_upload_id,
                "etag": etag,
            },
        )
        return etag

    def _upload_to_s3(
        self,
        buffer,
        s3_key,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ):
        metadata = metadata or {}
        content_type = content_type or "application/octet-stream"
        self.s3_client.put_object(
            Bucket=self.s3_bucket,
            Key=s3_key,
            Body=buffer,
            ContentType=content_type,
            Metadata=metadata,
        )
        self.log_object.write_log(
            "MESHFETCH0002a",
            None,
            {
                "HEADERS": self.http_response.headers,
                "RESPONSE": self.http_response,
                "aws_part_size": len(buffer),
                "aws_upload_id": self.aws_upload_id,
            },
        )

    def _create_multipart_upload(self):
        """Create an S3 multipart upload"""
        try:
            self.log_object.write_log(
                "MESHFETCH0009",
                None,
                {
                    "CHUNKS": self.number_of_chunks,
                    "key": self.s3_key,
                    "bucket": self.s3_bucket,
                },
            )
            multipart_upload = self.s3_client.create_multipart_upload(
                Bucket=self.s3_bucket,
                Key=self.s3_key,
                Metadata=metadata_from_headers(self.http_response.headers),
                ContentType=get_content_type(self.http_response),
            )
            self.aws_upload_id = multipart_upload["UploadId"]
            self.log_object.write_log(
                "MESHFETCH0005a",
                None,
                {
                    "key": self.s3_key,
                    "bucket": self.s3_bucket,
                },
            )
        except ClientError as e:
            self.response.update({"statusCode": HTTPStatus.INTERNAL_SERVER_ERROR.value})
            self.log_object.write_log(
                "MESHFETCH0005b",
                None,
                {
                    "key": self.s3_key,
                    "bucket": self.s3_bucket,
                    "error": e,
                },
            )
            raise e

    def _finish_multipart_upload(self):
        """Complete the s3 multipart upload"""
        try:
            self.log_object.write_log(
                "MESHFETCH0008",
                None,
                {
                    "mesh_msg_id": self.message_id,
                    "key": self.s3_key,
                    "bucket": self.s3_bucket,
                    "aws_upload_id": self.aws_upload_id,
                    "PARTS": {"Parts": self.aws_part_etags},
                },
            )
            self.s3_client.complete_multipart_upload(
                Bucket=self.s3_bucket,
                Key=self.s3_key,
                UploadId=self.aws_upload_id,
                MultipartUpload={"Parts": self.aws_part_etags},
            )

        except ClientError as e:
            self.response.update({"statusCode": HTTPStatus.INTERNAL_SERVER_ERROR.value})
            self.log_object.write_log(
                "MESHFETCH0007",
                None,
                {
                    "number_of_chunks": self.number_of_chunks,
                    "mesh_msg_id": self.message_id,
                    "key": self.s3_key,
                    "bucket": self.s3_bucket,
                    "aws_upload_id": self.aws_upload_id,
                    "error": e,
                },
            )
            raise e

    def _update_response(self, complete: bool):
        self.response.update({"statusCode": self.http_response.status_code})
        self.response["body"].update(
            {
                "complete": complete,
                "chunk_num": self.current_chunk,
                "aws_upload_id": self.aws_upload_id,
                "aws_current_part_id": self.aws_current_part_id,
                "aws_part_etags": self.aws_part_etags,
                "internal_id": self.internal_id,
                "file_name": self._get_filename(),
            }
        )

    def _read_bytes_into_buffer(self):
        part_buffer = b""
        for buffer in self.http_response.iter_content(
            chunk_size=self.DEFAULT_BUFFER_SIZE
        ):
            self.log_object.write_log(
                "MESHFETCH0003a", None, {"buffer_len": len(buffer)}
            )
            # Condition here to account for odd sized chunks
            if len(buffer) < 5 * self.MEBIBYTE:
                self._upload_to_s3(buffer, self.s3_tempfile_key)
            else:
                self._upload_part_to_s3(part_buffer + buffer)
                self.http_headers_bytes_read += len(buffer)


# create instance of class in global space
# this ensures initial setup of logging/config is only done on cold start
app = MeshFetchMessageChunkApplication()


def lambda_handler(event, context):
    """Standard lambda_handler"""
    return app.main(event, context)
