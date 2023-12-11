
locals {
  local_mailboxes = toset(["X26ABC1", "X26ABC2", "X26ABC3"])
}

resource "aws_ssm_parameter" "mesh_url" {
  name  = "/${local.config_prefix}/mesh/MESH_URL"
  type  = "String"
  value = "https://mesh_sandbox"
}

resource "aws_ssm_parameter" "shared_key" {
  name  = "/${local.config_prefix}/mesh/MESH_SHARED_KEY"
  type  = "String"
  value = "TestKey"
}

resource "aws_ssm_parameter" "ca_cert" {
  name  = "/${local.config_prefix}/mesh/MESH_CA_CERT"
  type  = "String"
  value = file("${path.module}/../../scripts/self-signed-ca/bundles/server-sub-ca-bundle.pem")
}

resource "aws_ssm_parameter" "client_cert" {
  name  = "/${local.config_prefix}/mesh/MESH_CLIENT_CERT"
  type  = "String"
  value = file("${path.module}/../../scripts/self-signed-ca/certs/client/valid/crt.pem")
}

resource "aws_ssm_parameter" "client_key" {
  name  = "/${local.config_prefix}/mesh/MESH_CLIENT_KEY"
  type  = "String"
  value = file("${path.module}/../../scripts/self-signed-ca/certs/client/valid/key.pem")
}

resource "aws_ssm_parameter" "passwords" {

  for_each = local.local_mailboxes

  name  = "/${local.config_prefix}/mesh/mailboxes/${each.key}/MAILBOX_PASSWORD"
  type  = "SecureString"
  value = "password"
}
