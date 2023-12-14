
moved {
  from = aws_secretsmanager_secret.client_key
  to   = data.aws_secretsmanager_secret.client_key
}

data "aws_secretsmanager_secret" "client_key" {
  count = var.use_secrets_manager ? 1 : 0
  name  = "/${local.name}/mesh/MESH_CLIENT_KEY"
}

moved {
  from = aws_secretsmanager_secret.shared_key
  to   = data.aws_secretsmanager_secret.shared_key
}

data "aws_secretsmanager_secret" "shared_key" {
  count = var.use_secrets_manager ? 1 : 0
  name  = "/${local.name}/mesh/MESH_SHARED_KEY"
}


data "aws_secretsmanager_secret" "mailbox_password" {
  for_each = var.use_secrets_manager ? var.mailbox_ids : toset([])
  name     = "/${local.name}/mesh/mailboxes/${each.key}/MAILBOX_PASSWORD"
}
