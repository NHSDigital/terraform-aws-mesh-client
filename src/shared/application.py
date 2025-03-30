import os
from time import time
from typing import Any, TypedDict

from mesh_client import MeshClient, optional_header_map
from nhs_aws_helpers import (
    dynamodb_client,
    s3_resource,
    secrets_client,
    ssm_client,
    stepfunctions,
)
from spine_aws_common import LambdaApplication

from shared.common import (
    LockExists,
    LockReleaseDenied,
    acquire_lock,
    get_params,
    release_lock,
)
from shared.config import EnvConfig
from shared.send_parameters import SendParameters


class MailboxParams(TypedDict):
    params: dict[str, str]
    retrieved: float


MAILBOX_PARAMS_CACHE_TIME = 60

MAILBOX_PASSWORD = "MAILBOX_PASSWORD"
INBOUND_BUCKET = "INBOUND_BUCKET"
INBOUND_FOLDER = "INBOUND_FOLDER"

VERSION = "2.1.4"


_OPTIONAL_SEND_ARGS = {v.lower(): k for k, v in optional_header_map().items()}


class MESHLambdaApplication(LambdaApplication):
    def __init__(self, additional_log_config=None, load_ssm_params=False):
        super().__init__(additional_log_config, load_ssm_params)
        self.s3 = s3_resource()
        self.ssm = ssm_client()
        self.sfn = stepfunctions()
        self.secrets = secrets_client()
        self.ddb_client = dynamodb_client()
        self.config = EnvConfig()
        self.environment = self.config.environment
        self.mailbox_params: dict[str, MailboxParams] = {}
        self._common_params_retrieved = False
        _base_certs_dir = f"/tmp/{self.config.environment}/certs"
        self._base_certs_dir = _base_certs_dir
        self.ca_cert_path: str = f"{_base_certs_dir}/ca_cert.pem"
        self.client_cert_path: str = f"{_base_certs_dir}/client_cert.pem"
        self.client_key_path: str = f"{_base_certs_dir}/client_key.pem"
        self.shared_key: str = ""
        self.verify: str | bool = self.ca_cert_path if self.config.verify_ssl else False
        self.mailbox_id: str = ""
        self._mesh_client: MeshClient | None = None

    def start(self):
        raise NotImplementedError("this should be implemented in the derived class")

    def _acquire_lock(self, lock_name: str | None, execution_id: str | None):
        """
        Attempt to acquire the lock row for this lock name.
        It's ok for the lock row to exist as long as we (execution_id) are the owner.
        """
        if not lock_name or not execution_id:
            self.log_object.write_log(
                "MESHLOCK0006",
                None,
                {"lock_name": lock_name, "owner_id": execution_id},
            )
            return

        try:

            self.log_object.write_log(
                "MESHLOCK0001",
                None,
                {"lock_name": lock_name, "owner_id": execution_id},
            )

            acquire_lock(
                self.ddb_client,
                lock_name,
                execution_id,
            )

        except LockExists as e:
            if e.lock_owner == execution_id:
                self.log_object.write_log(
                    "MESHLOCK0004",
                    None,
                    {"lock_name": lock_name, "owner_id": execution_id},
                )
                return
            self.log_object.write_log(
                "MESHLOCK0005",
                None,
                {"lock_name": lock_name, "owner_id": execution_id},
            )
            raise e

    def _release_lock(self, lock_name: str, execution_id: str):
        """
        Release lock_name.
        Attempting to release a lock which isn't owned by execution_id will be denied and will result in a
        non-terminal warning.
        """
        if not lock_name or not execution_id:
            self.log_object.write_log(
                "MESHLOCK0007",
                None,
                {"lock_name": lock_name, "owner_id": execution_id},
            )
            return

        try:
            self.log_object.write_log(
                "MESHLOCK0002",
                None,
                {"lock_name": lock_name, "owner_id": execution_id},
            )
            release_lock(self.ddb_client, lock_name, execution_id)
        except LockReleaseDenied as ex:
            self.log_object.write_log(
                "MESHLOCK0003",
                None,
                {
                    "lock_name": ex.lock_name,
                    "execution_id": ex.execution_id,
                    "lock_owner": ex.lock_owner,
                },
            )

    def _required_common_params(self) -> tuple[list[str], list[str]]:
        if self._common_params_retrieved:
            # common params already initialised ( lambda cold start to refresh ) # .e.g add an env var
            return [], []

        required_secrets = []
        required_params = [self.config.client_cert_config_key]

        if self.config.verify_ssl:
            required_params.append(self.config.ca_cert_config_key)

        secrets_paths = [
            self.config.client_key_config_key,
            self.config.shared_key_config_key,
        ]
        if self.config.use_secrets_manager:
            required_secrets.extend(secrets_paths)
        else:
            required_params.extend(secrets_paths)

        return required_params, required_secrets

    def _save_common_params(self, params: dict[str, str]):
        if self._common_params_retrieved:
            return

        os.makedirs(self._base_certs_dir, exist_ok=True)

        if self.config.shared_key_config_key in params:
            self.shared_key = params[self.config.shared_key_config_key]

        if self.config.ca_cert_config_key in params:
            with open(self.ca_cert_path, "w", encoding="utf-8") as f:
                f.write(params[self.config.ca_cert_config_key])

        if self.config.client_cert_config_key in params:
            with open(self.client_cert_path, "w", encoding="utf-8") as f:
                f.write(params[self.config.client_cert_config_key])

        if self.config.client_key_config_key in params:
            with open(self.client_key_path, "w", encoding="utf-8") as f:
                f.write(params[self.config.client_key_config_key])

        self._common_params_retrieved = True

    def ensure_params(self, mailbox_id: str):
        mailbox_params = self.mailbox_params.get(mailbox_id)
        if mailbox_params and time() < (
            mailbox_params["retrieved"] + MAILBOX_PARAMS_CACHE_TIME
        ):
            return

        required_params, required_secrets = self._required_common_params()
        mailbox_base_path = f"{self.config.mailboxes_base_config_key}/{mailbox_id}/"
        password_path = f"{mailbox_base_path}{MAILBOX_PASSWORD}"
        if self.config.use_secrets_manager:
            required_secrets.append(password_path)
        else:
            required_params.append(password_path)

        if self.config.use_legacy_inbound_location:
            required_params.extend(
                [
                    f"{mailbox_base_path}{INBOUND_BUCKET}",
                    f"{mailbox_base_path}{INBOUND_FOLDER}",
                ]
            )

        params = get_params(
            parameter_names=set(required_params),
            secret_ids=set(required_secrets),
            ssm=self.ssm,
            secrets=self.secrets,
        )

        self.mailbox_params[mailbox_id] = MailboxParams(
            params={
                k.replace(f"{mailbox_base_path}", "", 1): v
                for k, v in params.items()
                if k.startswith(mailbox_base_path)
            },
            retrieved=time(),
        )

        self._save_common_params(params)

    def __enter__(self):
        assert self.mailbox_id

        self.ensure_params(self.mailbox_id)
        password = self.mailbox_params[self.mailbox_id]["params"].get(MAILBOX_PASSWORD)
        if password is None:
            raise AssertionError(f"password not found for {self.mailbox_id}")

        self._mesh_client = MeshClient(
            url=self.config.mesh_url,
            mailbox=self.mailbox_id,
            password=password,
            shared_key=self.shared_key.encode(encoding="utf-8"),
            cert=(self.client_cert_path, self.client_key_path),
            verify=self.verify,
            hostname_checks_common_name=self.config.verify_checks_common_name,
            transparent_compress=False,
            application_name=f"AWS Serverless=={VERSION}",
        ).__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._mesh_client:
            try:
                self._mesh_client.close()
            finally:
                self._mesh_client = None

    @property
    def mesh_client(self) -> MeshClient:
        if not self._mesh_client:
            raise ValueError("MeshClient has not been initialised")
        return self._mesh_client

    def is_same_mailbox_check(self, sf_input: dict[str, Any]) -> bool:
        sf_mailbox = sf_input.get("mailbox")

        if not sf_mailbox or not self.mailbox_id:
            self.log_object.write_log(
                "MESHPOLL0002a",
                None,
                {"mailbox": self.mailbox_id, "sf_mailbox": sf_mailbox},
            )
            return False

        return bool(sf_mailbox == self.mailbox_id)

    def is_send_for_same_file(
        self, sf_input: dict[str, Any], send_params: SendParameters
    ) -> bool:
        def _get_input_bucket_key() -> tuple[str | None, str | None]:
            body = sf_input.get("body")
            if body:
                input_params = body.get("send_params")
                if input_params:
                    return input_params.get("s3_bucket"), input_params.get("s3_key")

                bucket = body.get("bucket")
                if bucket:
                    return bucket, body.get("key")

            if sf_input.get("source") != "aws.s3":
                return None, None

            request_params = sf_input.get("detail", {}).get("requestParameters")
            if not request_params:
                return None, None

            return request_params.get("bucketName"), request_params.get("key")

        s3_bucket, s3_key = _get_input_bucket_key()

        if not s3_bucket or not s3_key:
            self.log_object.write_log(
                "MESHSEND0002a",
                None,
                {
                    "mailbox": send_params.sender,
                    "bucket": send_params.s3_bucket,
                    "key": send_params.s3_key,
                },
            )
            return False

        return send_params.s3_bucket == s3_bucket and send_params.s3_key == s3_key
