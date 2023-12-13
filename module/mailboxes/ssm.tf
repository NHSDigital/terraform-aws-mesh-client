resource "aws_ssm_parameter" "mailbox_allowed_senders" {
  # SSM does not support empty parameters
  count = var.mailbox.allowed_senders != null ? 1 : 0

  name  = "/${var.name}/mesh/mailboxes/${var.mailbox_id}/ALLOWED_SENDERS"
  type  = "String"
  value = var.mailbox.allowed_senders
}

resource "aws_ssm_parameter" "mailbox_allowed_recipients" {
  # SSM does not support empty parameters
  count = var.mailbox.allowed_recipients != null ? 1 : 0

  name  = "/${var.name}/mesh/mailboxes/${var.mailbox_id}/ALLOWED_RECIPIENTS"
  type  = "String"
  value = var.mailbox.allowed_recipients
}

resource "aws_ssm_parameter" "mailbox_allowed_workflow_ids" {
  # SSM does not support empty parameters
  count = var.mailbox.allowed_workflow_ids != null ? 1 : 0

  name  = "/${var.name}/mesh/mailboxes/${var.mailbox_id}/ALLOWED_WORKFLOW_IDS"
  type  = "String"
  value = var.mailbox.allowed_workflow_ids
}

moved {
  from = aws_ssm_parameter.mailbox_password
  to   = data.aws_ssm_parameter.mailbox_password
}

data "aws_ssm_parameter" "mailbox_password" {
  count = var.config.use_secrets_manager ? 0 : 1
  name  = "/${var.name}/mesh/mailboxes/${var.mailbox_id}/MAILBOX_PASSWORD"
}

moved {
  from = aws_secretsmanager_secret.mailbox_password
  to   = data.aws_secretsmanager_secret.mailbox_password
}

data "aws_secretsmanager_secret" "mailbox_password" {
  count = var.config.use_secrets_manager ? 1 : 0
  name  = "/${var.name}/mesh/mailboxes/${var.mailbox_id}/MAILBOX_PASSWORD"
}


resource "aws_ssm_parameter" "mailbox_inbound_bucket" {
  name  = "/${var.name}/mesh/mailboxes/${var.mailbox_id}/INBOUND_BUCKET"
  type  = "String"
  value = var.bucket_id
}

resource "aws_ssm_parameter" "mailbox_inbound_folder" {
  name  = "/${var.name}/mesh/mailboxes/${var.mailbox_id}/INBOUND_FOLDER"
  type  = "String"
  value = local.inbound_folder
}


# src_mailbox will always be the id of the parent mailbox variable
resource "aws_ssm_parameter" "outbound_mappings_src_mailbox" {
  for_each = local.outbound_mappings

  name  = "/${var.name}/mesh/mapping/${var.bucket_id}/${each.value.folder}/src_mailbox"
  type  = "String"
  value = var.mailbox_id
}

resource "aws_ssm_parameter" "outbound_mappings_dest_mailbox" {
  for_each = local.outbound_mappings

  name  = "/${var.name}/mesh/mapping/${var.bucket_id}/${each.value.folder}/dest_mailbox"
  type  = "String"
  value = each.value.dest_mailbox
}

resource "aws_ssm_parameter" "outbound_mappings_workflow_id" {
  for_each = local.outbound_mappings

  name  = "/${var.name}/mesh/mapping/${var.bucket_id}/${each.value.folder}/workflow_id"
  type  = "String"
  value = each.value.workflow_id
}
