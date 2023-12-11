

resource "aws_secretsmanager_secret" "mailbox_password" {
  for_each    = local.use_secrets_manager ? local.local_mailboxes : []
  name        = "/${local.config_prefix}/mesh/mailboxes/${each.key}/MAILBOX_PASSWORD"
  description = "/${local.config_prefix}/mesh/mailboxes/${each.key}/MAILBOX_PASSWORD"
}


resource "aws_secretsmanager_secret_version" "mailbox_password" {
  for_each      = local.use_secrets_manager ? local.local_mailboxes : []
  secret_id     = "/${local.config_prefix}/mesh/mailboxes/${each.key}/MAILBOX_PASSWORD"
  secret_string = "password"
}