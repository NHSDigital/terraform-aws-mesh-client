
data "aws_ssm_parameter" "ssm" {
  name = "/${local.name}/mesh/MESH_CA_CERT"
}

moved {
  from = aws_ssm_parameter.ca_cert
  to   = data.aws_ssm_parameter.ssm
}

data "aws_ssm_parameter" "client_cert" {
  name = "/${local.name}/mesh/MESH_CLIENT_CERT"
}

moved {
  from = aws_ssm_parameter.client_cert
  to   = data.aws_ssm_parameter.client_cert
}

data "aws_ssm_parameter" "client_key" {
  count = var.config.use_secrets_manager ? 0 : 1
  name  = "/${local.name}/mesh/MESH_CLIENT_KEY"
}

moved {
  from = aws_ssm_parameter.client_key
  to   = data.aws_ssm_parameter.client_key
}

data "aws_ssm_parameter" "shared_key" {
  count = var.config.use_secrets_manager ? 0 : 1
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

resource "aws_ssm_parameter" "verify_ssl" {
  name = "/${local.name}/mesh/MESH_VERIFY_SSL"
  type = "String"
  # This is effectively converting the bool type from Terraform to Python
  value = var.config.verify_ssl ? "True" : "False"
}
