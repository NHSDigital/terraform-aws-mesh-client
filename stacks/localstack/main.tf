


module "main" {
  source = "../../module"

  mailbox_ids = ["X26ABC1", "X26ABC2", "X26ABC3"]

  name_prefix = "local"

  account_id = "000000000000"

  #  vpc_id = "something"

  depends_on = [
    aws_vpc_endpoint.s3,
    aws_vpc_endpoint.logs,
    aws_vpc_endpoint.kms,
    aws_vpc_endpoint.lambda,
    aws_vpc_endpoint.sfn,
    aws_vpc_endpoint.ssm,
    aws_ssm_parameter.mesh_url,
    aws_ssm_parameter.shared_key,
    aws_ssm_parameter.ca_cert,
    aws_ssm_parameter.client_cert,
    aws_ssm_parameter.client_key,
    aws_ssm_parameter.passwords,
    aws_ssm_parameter.verify_ssl,
    aws_secretsmanager_secret.mailbox_password
  ]

  # not supported in opensource cloudtrail
  cloudtrail_enabled = false

  mesh_env   = "local"
  subnet_ids = [aws_subnet.private.id]
  verify_ssl = false

  mailboxes = [
    {
      id                = "X26ABC1"
      outbound_mappings = []
    },
    {
      id                = "X26ABC2"
      outbound_mappings = []
    },
    {
      id                = "X26ABC3"
      outbound_mappings = []
    },
  ]

  get_messages_page_limit = 10
  get_messages_schedule   = "rate(31 days)" # this set this very rarely to allow tests to control invocation
  handshake_schedule      = "rate(31 days)" # this set this very rarely to allow tests to control invocation

  chunk_size         = 10 * 1024 * 1024
  crumb_size         = (1 * 1024 * 1024) - 7 # setting this to an odd setting for testing .. (generally leave this alone)
  compress_threshold = 5 * 1024 * 1024

  aws_s3_endpoint_prefix_list_id = aws_vpc_endpoint.s3.prefix_list_id
  aws_ssm_endpoint_sg_id         = tolist(aws_vpc_endpoint.ssm.security_group_ids)[0]
  aws_sfn_endpoint_sg_id         = tolist(aws_vpc_endpoint.sfn.security_group_ids)[0]
  aws_logs_endpoints_sg_id       = tolist(aws_vpc_endpoint.logs.security_group_ids)[0]
  aws_kms_endpoints_sg_id        = tolist(aws_vpc_endpoint.kms.security_group_ids)[0]
  aws_lambda_endpoints_sg_id     = tolist(aws_vpc_endpoint.lambda.security_group_ids)[0]
  aws_secrets_endpoints_sg_id    = tolist(aws_vpc_endpoint.secrets.security_group_ids)[0]

}



