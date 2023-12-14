module "main" {
  source = "../../module"

  mailbox_ids = ["X26ABC1", "X26ABC2", "X26ABC3"]

  name_prefix = "local"


  depends_on = [
    aws_vpc_endpoint.s3,
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

  get_messages_schedule = "rate(31 days)" # this set this very rarely to allow tests to control invocation
  handshake_schedule    = "rate(31 days)" # this set this very rarely to allow tests to control invocation

  chunk_size         = 10 * 1024 * 1024
  crumb_size         = (1 * 1024 * 1024) - 7 # setting this to an odd setting for testing .. (generally leave this alone)
  compress_threshold = 5 * 1024 * 1024

}



