import json
import os
import tempfile
from http import HTTPStatus
from io import BytesIO
from typing import cast

from botocore.exceptions import ClientError
from requests import Response
from requests.structures import CaseInsensitiveDict
from shared.application import INBOUND_BUCKET, INBOUND_FOLDER, MESHLambdaApplication
from shared.common import nullsafe_quote
from shared.config import MiB

_METADATA_HEADERS = {
    "mex-messageid",
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
    "mex-content-checksum",
    "mex-content-compressed",
    "mex-content-encrypted",
}


def metadata_from_headers(headers: CaseInsensitiveDict) -> dict[str, str]:
    return {
        mex: nullsafe_quote(headers.get(mex))
        for mex in _METADATA_HEADERS
        if mex in headers
    }


def get_content_type(response: Response) -> str:
    return response.headers.get("Content-Type") or "application/octet-stream"


AWS_MIN_MULTIPART_SIZE = 5 * MiB


class MeshFetchMessageChunkApplication(MESHLambdaApplication):
    """
    MESH API Lambda for sending a message
    """

    def __init__(self, additional_log_config=None, load_ssm_params=False):
        """
        Init variables
        """
        super().__init__(additional_log_config, load_ssm_params)
        self.input = {}

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

        self.s3_bucket = ""
        self.s3_key = ""

    def initialise(self):
        """decode input event"""
        self._http_response = None
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
        self.s3_bucket = self.input.get("s3_bucket", "")  # will be empty on first chunk
        self.s3_key = self.input.get("s3_key", "")  # will be empty on first chunk

        self.lock_name = self.input.get("lock_name") or None
        self.execution_id = self.input.get("execution_id") or None
        self.should_release_lock = self.input.get("release_lock", False) or False

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

        self.mailbox_id = self.input["dest_mailbox"]

        self._acquire_lock(self.lock_name, self.execution_id)

        with self:
            # get stream for this chunk

            self._retrieve_current_chunk()
            self.chunked = self.http_response.status_code == int(
                HTTPStatus.PARTIAL_CONTENT
            )
            is_report = self.http_response.headers.get("Mex-MessageType") == "REPORT"
            self._ensure_s3_bucket_and_key(is_report)
            if is_report or self.number_of_chunks < 2:
                self._handle_un_chunked_message(is_report)
            else:
                self._handle_multiple_chunk_message()

            if not self.should_release_lock:
                return

    def _retrieve_current_chunk(self):
        self._http_response = self.get_chunk(
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

    def _handle_multiple_chunk_message(self):
        self.log_object.write_log(
            "MESHFETCH0013", None, {"message_id": self.message_id}
        )
        if self.current_chunk == 1:
            self._create_multipart_upload()

        while self.current_chunk <= self.number_of_chunks:
            with tempfile.NamedTemporaryFile() as buffer:
                response = self.http_response
                # we never want to create more chunks than total_chunks ( as that is limited to 10k )
                for crumb in response.iter_content(chunk_size=self.config.crumb_size):
                    buffer.write(crumb)
                buffer.flush()
                length = buffer.tell()
                if (
                    self.current_chunk == self.number_of_chunks
                    or length > AWS_MIN_MULTIPART_SIZE
                ):
                    buffer.seek(0)
                    self._upload_part_to_s3(cast(BytesIO, buffer), length)
                    # break here so next chunk will be handed by a separate lambda invocation to avoid timeout
                    break

                self.current_chunk += 1
                self._retrieve_current_chunk()

        if self.current_chunk == self.number_of_chunks:
            self._finish_multipart_upload()
            self.acknowledge_message(self.message_id)
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

    def _handle_un_chunked_message(self, is_report: bool):
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
            content_type=content_type,
            metadata=metadata_from_headers(self.http_response.headers),
        )

        self.acknowledge_message(self.message_id)
        self._update_response(complete=True)
        self.log_object.write_log(
            "MESHFETCH0012", None, {"message_id": self.message_id}
        )

    def _get_filename(self, is_report: bool):
        extension = "ctl" if is_report else "dat"
        default_filename = f"{self.message_id}.{extension}"
        if not self.config.use_sender_filename:
            return default_filename

        file_name_header = (
            self.http_response.headers.get("Mex-FileName", "") or ""
        ).strip()
        if file_name_header:
            return file_name_header
        return default_filename

    def _ensure_s3_bucket_and_key(self, is_report: bool):
        # must be called after ensure_params
        if self.current_chunk > 1:
            # should not change once selected on first chunk
            assert self.s3_bucket
            assert self.s3_key
            return

        assert self.mailbox_id
        filename = self._get_filename(is_report)

        s3_folder = f"inbound/{self.mailbox_id}"

        if self.config.use_legacy_inbound_location:
            self.s3_bucket = self.mailbox_params[self.mailbox_id]["params"][
                INBOUND_BUCKET
            ].strip()
            s3_folder = (
                self.mailbox_params[self.mailbox_id]["params"][INBOUND_FOLDER]
                .strip()
                .strip("/")
            )
        else:
            self.s3_bucket = self.config.mesh_bucket

        self.s3_key = f"{s3_folder}/{filename}"

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
            response = self.s3.MultipartUploadPart(
                self.s3_bucket,
                self.s3_key,
                self.aws_upload_id,
                self.aws_current_part_id,  # type: ignore[arg-type]
            ).upload(Body=buffer, ContentLength=content_length)
        except ClientError as e:
            self.response.update({"statusCode": int(HTTPStatus.INTERNAL_SERVER_ERROR)})
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
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ):
        metadata = metadata or {}
        content_type = content_type or "application/octet-stream"
        self.s3.Object(self.s3_bucket, self.s3_key).put(
            Body=buffer, ContentType=content_type, Metadata=metadata
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
            multipart_upload = self.s3.Object(
                self.s3_bucket, self.s3_key
            ).initiate_multipart_upload(
                Metadata=metadata_from_headers(self.http_response.headers),
                ContentType=get_content_type(self.http_response),
            )

            self.aws_upload_id = multipart_upload.id
            self.log_object.write_log(
                "MESHFETCH0005a",
                None,
                {
                    "key": self.s3_key,
                    "bucket": self.s3_bucket,
                    "upload_id": self.aws_upload_id,
                },
            )
        except ClientError as e:
            self.response.update({"statusCode": int(HTTPStatus.INTERNAL_SERVER_ERROR)})
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
                    "PARTS": {
                        "Parts": self.aws_part_etags[:200]
                    },  # this could be 10,000 ... slice for logs
                },
            )
            self.s3.MultipartUpload(
                self.s3_bucket, self.s3_key, self.aws_upload_id
            ).complete(MultipartUpload={"Parts": self.aws_part_etags})

        except ClientError as e:
            self.response.update({"statusCode": int(HTTPStatus.INTERNAL_SERVER_ERROR)})
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
                "file_name": os.path.basename(self.s3_key),
                "s3_bucket": self.s3_bucket,
                "s3_key": self.s3_key,
            }
        )

    def get_chunk(self, message_id, chunk_num=1) -> Response:
        """Return a response object for a MESH chunk"""

        response = self.mesh_client.retrieve_message_chunk(
            message_id=message_id, chunk_num=chunk_num
        )

        response.raw.decode_content = True

        return response

    def acknowledge_message(self, message_id):
        """
        Acknowledge receipt of the last message from the mailbox.
        """

        self.mesh_client.acknowledge_message(message_id)
        self.log_object.write_log(
            "MESHMBOX0006",
            None,
            {"message_id": message_id},
        )


# create instance of class in global space
# this ensures initial setup of logging/config is only done on cold start
app = MeshFetchMessageChunkApplication()


def lambda_handler(event, context):
    """Standard lambda_handler"""
    return app.main(event, context)
