
data "aws_ssm_parameter" "ca_cert" {
  name = "/${local.name}/mesh/MESH_CA_CERT"
}

moved {
  from = aws_ssm_parameter.ca_cert
  to   = data.aws_ssm_parameter.ca_cert
}

data "aws_ssm_parameter" "client_cert" {
  name = "/${local.name}/mesh/MESH_CLIENT_CERT"
}

moved {
  from = aws_ssm_parameter.client_cert
  to   = data.aws_ssm_parameter.client_cert
}

data "aws_ssm_parameter" "client_key" {
  count = var.use_secrets_manager ? 0 : 1
  name  = "/${local.name}/mesh/MESH_CLIENT_KEY"
}

moved {
  from = aws_ssm_parameter.client_key
  to   = data.aws_ssm_parameter.client_key
}

data "aws_ssm_parameter" "shared_key" {
  count = var.use_secrets_manager ? 0 : 1
  name  = "/${local.name}/mesh/MESH_SHARED_KEY"
}

moved {
  from = aws_ssm_parameter.shared_key
  to   = data.aws_ssm_parameter.shared_key
}

data "aws_ssm_parameter" "url" {
  name = "/${local.name}/mesh/MESH_URL"
}

moved {
  from = aws_ssm_parameter.url
  to   = data.aws_ssm_parameter.url
}

data "aws_ssm_parameter" "verify_ssl" { # remove in 3.0.0
  name = "/${local.name}/mesh/MESH_VERIFY_SSL"
}

moved {
  from = aws_ssm_parameter.verify_ssl
  to   = data.aws_ssm_parameter.verify_ssl
}


data "aws_ssm_parameter" "mailbox_password" {
  for_each = var.use_secrets_manager ? toset([]) : var.mailbox_ids
  name     = "/${local.name}/mesh/mailboxes/${each.key}/MAILBOX_PASSWORD"
}
