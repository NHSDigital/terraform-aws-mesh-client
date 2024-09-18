import os

from aws_lambda_powertools.shared.functions import strtobool

MiB = 1024 * 1024
DEFAULT_CRUMB_SIZE = (
    20 * MiB
)  # defaulting to same as chunk size but separately configurable
DEFAULT_CHUNK_SIZE = 20 * MiB
MIN_MULTIPART_SIZE = 5 * MiB


class EnvConfig:
    def __init__(self):
        self.environment = os.environ.get(
            "ENVIRONMENT", "default"
        )  # e.g. local-mesh (local.name in modue)
        self.mesh_url = os.environ.get("MESH_URL", "https://mesh_sandbox")
        self.mesh_bucket = os.environ.get("MESH_BUCKET", "")
        self.lock_table_name = os.environ.get("LOCK_TABLE_NAME", None)
        self.verify_ssl = bool(strtobool(os.environ.get("VERIFY_SSL", "true")))
        self.verify_checks_common_name = bool(
            strtobool(os.environ.get("VERIFY_CHECKS_COMMON_NAME", "true"))
        )
        self.use_secrets_manager = bool(
            strtobool(os.environ.get("USE_SECRETS_MANAGER", "false"))
        )
        self.use_sender_filename = bool(
            strtobool(os.environ.get("USE_SENDER_FILENAME", "false"))
        )
        self.use_s3_key_for_mex_filename = bool(
            strtobool(os.environ.get("USE_S3_KEY_FOR_MEX_FILENAME", "false"))
        )
        self.use_legacy_inbound_location = bool(
            strtobool(os.environ.get("USE_LEGACY_INBOUND_LOCATION", "false"))
        )
        self.never_compress = bool(strtobool(os.environ.get("NEVER_COMPRESS", "false")))

        self.chunk_size = max(int(os.environ.get("CHUNK_SIZE", DEFAULT_CHUNK_SIZE)), 10)

        self.crumb_size = max(
            min(int(os.environ.get("CRUMB_SIZE", DEFAULT_CRUMB_SIZE)), self.chunk_size),
            1,
        )

        self.compress_threshold = max(
            int(os.environ.get("COMPRESS_THRESHOLD", self.chunk_size)), 0
        )

        self.send_message_step_function_arn = os.environ.get(
            "SEND_MESSAGE_STEP_FUNCTION_ARN", "default"
        )
        self.get_messages_step_function_arn = os.environ.get(
            "GET_MESSAGES_STEP_FUNCTION_ARN", "default"
        )
        self.ca_cert_config_key = os.environ.get("CA_CERT_CONFIG_KEY", "not-set")
        self.client_cert_config_key = os.environ.get(
            "CLIENT_CERT_CONFIG_KEY", "not-set"
        )
        self.client_key_config_key = os.environ.get("CLIENT_KEY_CONFIG_KEY", "not-set")
        self.shared_key_config_key = os.environ.get("SHARED_KEY_CONFIG_KEY", "not-set")
        self.mailboxes_base_config_key = os.environ.get(
            "MAILBOXES_BASE_CONFIG_KEY", "not-set"
        )
        self.get_messages_page_limit = int(
            os.environ.get("GET_MESSAGES_PAGE_LIMIT", "500")
        )
