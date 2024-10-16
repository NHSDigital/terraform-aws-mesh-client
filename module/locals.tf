locals {
  name = "${var.name_prefix}-mesh"

  abs_path = abspath(path.module)

  mesh_url = {
    local       = "https://mesh_sandbox"
    integration = "https://msg.intspineservices.nhs.uk"
    production  = "https://mesh-sync.spineservices.nhs.uk"
  }

  common_env_vars = {
    Environment         = local.name              # remove in 3.0 ( in flight lambdas )
    use_secrets_manager = var.use_secrets_manager # remove in 3.0 ( in flight lambdas )

    ENVIRONMENT               = local.name # not the mesh_env .. ssm/secrets prefix
    USE_SECRETS_MANAGER       = var.use_secrets_manager
    VERIFY_SSL                = var.verify_ssl
    VERIFY_CHECKS_COMMON_NAME = var.verify_checks_common_name

    MESH_URL    = local.mesh_url[var.mesh_env]
    MESH_BUCKET = aws_s3_bucket.mesh.bucket

    DDB_LOCK_TABLE_NAME = aws_dynamodb_table.lock_table.name

    CHUNK_SIZE         = var.chunk_size
    CRUMB_SIZE         = var.crumb_size == null ? var.chunk_size : var.crumb_size
    NEVER_COMPRESS     = var.never_compress
    COMPRESS_THRESHOLD = var.compress_threshold

    CA_CERT_CONFIG_KEY        = data.aws_ssm_parameter.ca_cert.name
    CLIENT_CERT_CONFIG_KEY    = data.aws_ssm_parameter.client_cert.name
    CLIENT_KEY_CONFIG_KEY     = data.aws_ssm_parameter.client_key[0].name
    SHARED_KEY_CONFIG_KEY     = data.aws_ssm_parameter.shared_key[0].name
    MAILBOXES_BASE_CONFIG_KEY = "/${local.name}/mesh/mailboxes"

    SEND_MESSAGE_STEP_FUNCTION_ARN = "arn:aws:states:${var.region}:${var.account_id}:stateMachine:${local.send_message_name}"
    GET_MESSAGES_STEP_FUNCTION_ARN = "arn:aws:states:${var.region}:${var.account_id}:stateMachine:${local.get_messages_name}"

    GET_MESSAGES_PAGE_LIMIT = var.get_messages_page_limit

    USE_SENDER_FILENAME         = var.use_sender_filename
    USE_LEGACY_INBOUND_LOCATION = var.use_legacy_inbound_location
    USE_S3_KEY_FOR_MEX_FILENAME = var.use_s3_key_for_mex_filename

  }

  mesh_ips = {
    integration = [
      "3.11.177.31/32", "35.177.15.89/32", "3.11.199.83/32",       # Blue
      "35.178.64.126/32", "18.132.113.121/32", "18.132.31.159/32", # Green

    ]
    production = [
      "18.132.56.40/32", "3.11.193.200/32", "35.176.248.137/32", # Blue
      "3.10.194.216/32", "35.176.231.190/32", "35.179.50.16/32"  # Green
    ]
  }

  vpc_enabled = var.vpc_id == "" ? false : true

  secrets_kms_key_ids = (
    var.use_secrets_manager ? compact(toset(concat(
      data.aws_secretsmanager_secret.shared_key[*].kms_key_id,
      data.aws_secretsmanager_secret.client_key[*].kms_key_id,
      data.aws_secretsmanager_secret.mailbox_password[*].kms_key_id
    ))) : toset([])
  )

  secrets_kms_key_arns = [for key_id in local.secrets_kms_key_ids : "arn:aws:kms:${var.region}:${var.account_id}:key/${key_id}"]

  secrets_arns = (
    var.use_secrets_manager ? compact(concat(
      data.aws_secretsmanager_secret.shared_key[*].arn,
      data.aws_secretsmanager_secret.client_key[*].arn,
      data.aws_secretsmanager_secret.mailbox_password[*].arn
    )) : toset([])
  )

  python_runtime = "python3.11"
  lambda_timeout = 300
}
