import json
import os
import tempfile
from http import HTTPStatus
from io import BytesIO
from typing import cast

from botocore.exceptions import ClientError
from nhs_aws_helpers import s3_client
from requests import Response
from requests.structures import CaseInsensitiveDict
from shared.common import nullsafe_quote
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


MB = 1024 * 1024
DEFAULT_CRUMB_SIZE = 10 * MB
MIN_MULTIPART_SIZE = 5 * MB


class MeshFetchMessageChunkApplication(LambdaApplication):
    """
    MESH API Lambda for sending a message
    """

    def __init__(self, additional_log_config=None, load_ssm_params=False):
        """
        Init variables
        """
        super().__init__(additional_log_config, load_ssm_params)
        self.input = {}
        self.environment = os.environ.get("Environment", "default")
        self.crumb_size = int(os.environ.get("CRUMB_SIZE", DEFAULT_CRUMB_SIZE))
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

            self._retrieve_chunk(mailbox)
            self.chunked = (
                self.http_response.status_code == HTTPStatus.PARTIAL_CONTENT.value
            )
            self._get_aws_bucket_and_key(mailbox)
            is_report = self.http_response.headers.get("Mex-MessageType") == "REPORT"
            if is_report or self.number_of_chunks < 2:
                self._handle_un_chunked_message(mailbox, is_report)
                return

            self._handle_multiple_chunk_message(mailbox)

    def _retrieve_chunk(self, mailbox: MeshMailbox):
        self._http_response = mailbox.get_chunk(
            self.message_id, chunk_num=self.current_chunk
        )
        self.number_of_chunks = int(
            self._http_response.headers.get("Mex-Total-Chunks", "0")
        )

        if self.number_of_chunks < 2:
            self.log_object.write_log(
                "MESHFETCH0001a",
                None,
                {
                    "content_length": self._http_response.headers.get(
                        "content-length", 0
                    ),
                    "message_id": self.message_id,
                },
            )
            return
        self.log_object.write_log(
            "MESHFETCH0001b",
            None,
            {
                "content_length": self._http_response.headers.get("content-length", 0),
                "message_id": self.message_id,
                "chunk_num": self.current_chunk,
                "max_chunk": self.number_of_chunks,
            },
        )

    def _handle_multiple_chunk_message(self, mailbox: MeshMailbox):
        self.log_object.write_log(
            "MESHFETCH0013", None, {"message_id": self.message_id}
        )
        if self.current_chunk == 1:
            self._create_multipart_upload()

        while self.current_chunk <= self.number_of_chunks:
            with tempfile.NamedTemporaryFile() as buffer:
                response = self.http_response
                # we never want to create more chunks than total_chunks ( as that is limited to 10k )
                for crumb in response.iter_content(chunk_size=self.crumb_size):
                    buffer.write(crumb)
                buffer.flush()
                length = buffer.tell()
                if (
                    self.current_chunk == self.number_of_chunks
                    or length > MIN_MULTIPART_SIZE
                ):
                    buffer.seek(0)
                    self._upload_part_to_s3(cast(BytesIO, buffer), length)
                    # break here so next chunk will be handed by a separate lambda invocation to avoid timeout
                    break

                self.current_chunk += 1
                self._retrieve_chunk(mailbox)

        if self.current_chunk == self.number_of_chunks:
            self._finish_multipart_upload()
            mailbox.acknowledge_message(self.message_id)
            self.log_object.write_log(
                "MESHFETCH0004", None, {"message_id": self.message_id}
            )
            self._update_response(complete=True)
            # fully complete
            return

        # move to next chunk and return
        self.current_chunk += 1
        self.log_object.write_log(
            "MESHFETCH0003",
            None,
            {"chunk": self.current_chunk, "message_id": self.message_id},
        )
        self._update_response(complete=False)

    def _handle_un_chunked_message(self, mailbox: MeshMailbox, is_report: bool):
        self.log_object.write_log(
            "MESHFETCH0010" if is_report else "MESHFETCH0011",
            None,
            {"message_id": self.message_id},
        )

        chunk_data = (
            json.dumps(dict(self.http_response.headers)).encode("utf-8")
            if is_report
            else self.http_response.raw.read(decode_content=True)
        )
        content_type = (
            "application/json" if is_report else get_content_type(self.http_response)
        )

        self._upload_to_s3(
            chunk_data,
            s3_key=self.s3_key,
            content_type=content_type,
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

    def _upload_part_to_s3(self, buffer: BytesIO, content_length: int):
        try:
            response = self.s3_client.upload_part(
                Body=buffer,
                Bucket=self.s3_bucket,
                Key=self.s3_key,
                PartNumber=self.aws_current_part_id,
                ContentLength=content_length,
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
                    "content_length": content_length,
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
                "aws_part_size": content_length,
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
                "s3_bucket": self.s3_bucket,
                "s3_key": self.s3_key,
            }
        )


# create instance of class in global space
# this ensures initial setup of logging/config is only done on cold start
app = MeshFetchMessageChunkApplication()


def lambda_handler(event, context):
    """Standard lambda_handler"""
    return app.main(event, context)
