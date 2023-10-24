

resource "aws_ssm_parameter" "mesh_url" {
  name  = "/${var.env}/mesh/MESH_URL"
  type  = "String"
  value = "https://mesh_sandbox"
}

locals {
  local_mailboxes = toset(["X26ABC1", "X26ABC2", "X26ABC3"])
}


resource "aws_ssm_parameter" "passwords" {

  for_each = local.local_mailboxes

  name  = "/${var.env}/mesh/mailboxes/${each.key}/MAILBOX_PASSWORD"
  type  = "SecureString"
  value = "password"
}
