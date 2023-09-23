resource "aws_ssm_parameter" "ca_cert" {
  name  = "/${local.name}/mesh/MESH_CA_CERT"
  type  = "SecureString"
  value = "To Replace"

  lifecycle {
    ignore_changes = [
      value
    ]
  }
}
resource "aws_ssm_parameter" "client_cert" {
  name  = "/${local.name}/mesh/MESH_CLIENT_CERT"
  type  = "SecureString"
  value = "To Replace"

  lifecycle {
    ignore_changes = [
      value
    ]
  }
}
resource "aws_ssm_parameter" "client_key" {
  count = var.config.use_secrets_manager == false ? 1 : 0
  name  = "/${local.name}/mesh/MESH_CLIENT_KEY"
  type  = "SecureString"
  value = "To Replace"

  lifecycle {
    ignore_changes = [
      value
    ]
  }
}

resource "aws_ssm_parameter" "shared_key" {
  count = var.config.use_secrets_manager == false ? 1 : 0
  name  = "/${local.name}/mesh/MESH_SHARED_KEY"
  type  = "SecureString"
  value = "To Replace"

  lifecycle {
    ignore_changes = [
      value
    ]
  }
}

resource "aws_ssm_parameter" "url" {
  name  = "/${local.name}/mesh/MESH_URL"
  type  = "String"
  value = local.mesh_url[var.config.environment]
}

resource "aws_ssm_parameter" "verify_ssl" {
  name = "/${local.name}/mesh/MESH_VERIFY_SSL"
  type = "String"
  # This is effectively converting the bool type from Terraform to Python
  value = var.config.verify_ssl ? "True" : "False"
}
