"""Mailbox class that handles all the complexity of talking to MESH API"""
import contextlib
import os
import tempfile
from collections.abc import Generator
from io import BytesIO
from typing import Any, NamedTuple, Optional, Union

from aws_lambda_powertools.shared.functions import strtobool
from mesh_client import MeshClient, optional_header_map
from requests import HTTPError, Response
from spine_aws_common.logger import Logger

from mesh_client_aws_serverless.mesh_common import MeshCommon


class MeshMessage(NamedTuple):
    """Named tuple for holding Mesh Message info"""

    content: Generator[bytes, None, None]
    file_name: str = ""
    src_mailbox: str = ""
    dest_mailbox: str = ""
    workflow_id: str = ""
    message_id: str = ""
    will_compress: bool = False
    metadata: Optional[dict] = None


class HandshakeFailure(Exception):
    """Handshake failed"""

    def __init__(self, msg=None):
        super().__init__()
        self.msg = msg


_OPTIONAL_SEND_ARGS = {v.lower(): k for k, v in optional_header_map().items()}


class MeshMailbox:
    """Mailbox class that handles all the complexity of talking to MESH API"""

    AUTH_SCHEMA_NAME = "NHSMESH"

    MESH_CA_CERT = "MESH_CA_CERT"
    MESH_CLIENT_CERT = "MESH_CLIENT_CERT"
    MESH_CLIENT_KEY = "MESH_CLIENT_KEY"
    MESH_SHARED_KEY = "MESH_SHARED_KEY"
    MESH_URL = "MESH_URL"
    MESH_VERIFY_SSL = "MESH_VERIFY_SSL"
    MESH_HOSTNAME_CHECKS_COMMON_NAME = "MESH_HOSTNAME_CHECKS_COMMON_NAME"
    MAILBOX_PASSWORD = "MAILBOX_PASSWORD"
    INBOUND_BUCKET = "INBOUND_BUCKET"
    INBOUND_FOLDER = "INBOUND_FOLDER"
    ALLOWED_SENDERS = "ALLOWED_SENDERS"
    ALLOWED_RECIPIENTS = "ALLOWED_RECIPIENTS"
    ALLOWED_WORKFLOW_IDS = "ALLOWED_WORKFLOW_IDS"

    VERSION = "1.0.0"

    def __init__(self, log_object: Logger, mailbox: str, environment: str):
        self.mailbox = mailbox
        self.environment = environment
        self.temp_dir_object: Optional[tempfile.TemporaryDirectory] = None
        self.params: dict[str, Any] = {}
        self.log_object = log_object
        self.client_cert_file: Optional[tempfile._TemporaryFileWrapper] = None
        self.client_key_file: Optional[tempfile._TemporaryFileWrapper] = None
        self.ca_cert_file: Optional[tempfile._TemporaryFileWrapper] = None

        self.maybe_verify_ssl = True
        self._client: Optional[MeshClient] = None

    @property
    def client(self) -> MeshClient:
        if not self._client:
            raise ValueError("MeshClient has not been intialised")
        return self._client

    def __enter__(self):
        self._setup()

        verify: Union[bool, str] = False
        if self.maybe_verify_ssl:
            assert self.ca_cert_file
            verify = self.ca_cert_file.name

        hostname_checks_common_name = strtobool(
            self.params.get(MeshMailbox.MESH_HOSTNAME_CHECKS_COMMON_NAME, "True")
        )
        assert self.client_key_file
        assert self.client_cert_file

        self._client = MeshClient(
            url=self.params[MeshMailbox.MESH_URL],
            mailbox=self.mailbox,
            password=self.params[MeshMailbox.MAILBOX_PASSWORD],
            shared_key=self.params[MeshMailbox.MESH_SHARED_KEY],
            cert=(self.client_cert_file.name, self.client_key_file.name),
            verify=verify,
            hostname_checks_common_name=hostname_checks_common_name,
            transparent_compress=False,
            application_name=f"AWS Serverless=={MeshMailbox.VERSION}",
        ).__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            self._client.close()
        self._clean_up()

    def _setup(self) -> None:
        """Get mailbox config from SSM parameter store"""
        self.log_object.write_log(
            "MESHMBOX0001",
            None,
            {"mailbox": self.mailbox, "environment": self.environment},
        )

        common_params = MeshCommon.get_params(f"/{self.environment}/mesh")
        mailbox_params = MeshCommon.get_params(
            f"/{self.environment}/mesh/mailboxes/{self.mailbox}"
        )
        self.params = {**common_params, **mailbox_params}
        self.maybe_verify_ssl = strtobool(
            self.params.get(MeshMailbox.MESH_VERIFY_SSL, "True")
        )
        self._write_certs_to_files()

    def _clean_up(self) -> None:
        """Clear up after use"""
        self.log_object.write_log(
            "MESHMBOX0007",
            None,
            {"mailbox": self.mailbox, "environment": self.environment},
        )
        if self.client_cert_file:
            filename = self.client_cert_file.name
            self.client_cert_file.close()
            with contextlib.suppress(FileNotFoundError):
                os.remove(filename)
        if self.client_key_file:
            filename = self.client_key_file.name
            self.client_key_file.close()
            with contextlib.suppress(FileNotFoundError):
                os.remove(filename)
        if self.ca_cert_file:
            filename = self.ca_cert_file.name
            self.ca_cert_file.close()
            with contextlib.suppress(FileNotFoundError):
                os.remove(filename)

    def get_param(self, param) -> str:
        """Shortcut to get a parameter"""
        return self.params.get(param, None)  # type: ignore[no-any-return]

    def _write_certs_to_files(self) -> None:
        """Write the certificates to a local file"""
        self.log_object.write_log("MESHMBOX0002", None, None)

        self.temp_dir_object = tempfile.TemporaryDirectory()
        temp_dir = self.temp_dir_object.name

        # store as temporary files for the mesh client / requests library
        self.client_cert_file = tempfile.NamedTemporaryFile(dir=temp_dir, delete=False)
        client_cert = self.params[MeshMailbox.MESH_CLIENT_CERT]
        self.client_cert_file.write(client_cert.encode("utf-8"))
        self.client_cert_file.seek(0)

        self.client_key_file = tempfile.NamedTemporaryFile(dir=temp_dir, delete=False)
        client_key = self.params[MeshMailbox.MESH_CLIENT_KEY]
        self.client_key_file.write(client_key.encode("utf-8"))
        self.client_key_file.seek(0)

        self.ca_cert_file = None
        if self.maybe_verify_ssl:
            self.ca_cert_file = tempfile.NamedTemporaryFile(dir=temp_dir, delete=False)
            assert self.ca_cert_file
            ca_cert = self.params[MeshMailbox.MESH_CA_CERT]
            self.ca_cert_file.write(ca_cert.encode("utf-8"))
            self.ca_cert_file.seek(0)

    def handshake(self) -> int:
        """
        Do an authenticated handshake with the MESH server
        """

        try:
            self.client.handshake()
        except HTTPError as ex:
            self.log_object.write_log(
                "MESHMBOX0004", None, {"http_status": ex.response.status_code}
            )
            raise HandshakeFailure from ex

        self.log_object.write_log("MESHMBOX0004", None, {"http_status": 200})

        return 200

    def _send_args_from_metadata(
        self, mesh_message_object: MeshMessage
    ) -> dict[str, str]:
        if not mesh_message_object.metadata:
            return {}

        return {
            _OPTIONAL_SEND_ARGS[key.lower()]: value
            for key, value in mesh_message_object.metadata.items()
            if key.lower() in _OPTIONAL_SEND_ARGS
        }

    def send_chunk(
        self,
        mesh_message_object: MeshMessage,
        number_of_chunks: int = 1,
        chunk_num: int = 1,
    ):
        """Send a chunk from a stream"""

        kwargs = {
            "workflow_id": mesh_message_object.workflow_id,
            "filename": mesh_message_object.file_name,
        }
        if chunk_num > 1:
            kwargs["message_id"] = mesh_message_object.message_id

        kwargs.update(self._send_args_from_metadata(mesh_message_object))

        chunk = BytesIO(b"".join(chunk for chunk in mesh_message_object.content))

        response = self.client.send_chunk(
            recipient=mesh_message_object.dest_mailbox,
            chunk=chunk,
            chunk_num=chunk_num,
            total_chunks=number_of_chunks,
            compress=mesh_message_object.will_compress,
            **kwargs,
        )
        response.raw.decode_content = True

        message_id = mesh_message_object.message_id
        if chunk_num == 1:
            message_id = response.json()["message_id"]

        self.log_object.write_log(
            "MESHSEND0007",
            None,
            {
                "file": mesh_message_object.file_name,
                "http_status": response.status_code,
                "message_id": message_id,
                "chunk_num": chunk_num,
                "max_chunk": number_of_chunks,
            },
        )
        return response

    def get_chunk(self, message_id, chunk_num=1) -> Response:
        """Return a response object for a MESH chunk"""

        response = self.client.retrieve_message_chunk(
            message_id=message_id, chunk_num=chunk_num
        )

        response.raw.decode_content = True
        chunk_range = response.headers.get("Mex-Chunk-Range", "1:1")
        number_of_chunks = int(chunk_range.split(":")[1])
        number_of_chunks = chunk_num == number_of_chunks
        self.log_object.write_log(
            "MESHSEND0001b",
            None,
            {
                "message_id": message_id,
                "chunk_num": chunk_num,
                "max_chunk": number_of_chunks,
            },
        )
        # for 3 out of 5 fetch tests Mex-Chunk-Range does not exist is this ok?
        # log chunk of chunk_max for message_id
        return response

    def list_messages(self) -> list[str]:
        """Return a list of messages in the mailbox in the form:
        [
            '20220610195418651944_2202CC',
            '20220613142621549393_6430C9'
        ]
        """

        message_ids = self.client.list_messages()
        self.log_object.write_log(
            "MESHMBOX0005",
            None,
            {
                "mailbox": self.mailbox,
                "message_count": len(message_ids),
            },
        )
        return message_ids

    def acknowledge_message(self, message_id):
        """
        Acknowledge receipt of the last message from the mailbox.
        """

        self.client.acknowledge_message(message_id)
        self.log_object.write_log(
            "MESHMBOX0006",
            None,
            {"message_id": message_id},
        )
