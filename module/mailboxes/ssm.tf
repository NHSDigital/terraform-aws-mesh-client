# these this whole module is here just to ensure that these original resources don't get deleted,
# this module can be removed in a future MAJOR release (once consumers are upgrade to this major )

moved {
  from = aws_ssm_parameter.mailbox_password
  to   = data.aws_ssm_parameter.mailbox_password
}

data "aws_ssm_parameter" "mailbox_password" {
  # detaching from state will move out of 'mailboxes' module in then next major release
  name = "/${var.name}/mesh/mailboxes/${var.mailbox_id}/MAILBOX_PASSWORD"
}

moved {
  from = aws_secretsmanager_secret.mailbox_password
  to   = data.aws_secretsmanager_secret.mailbox_password
}

data "aws_secretsmanager_secret" "mailbox_password" {
  count = 0 # detaching from state just in case any secret exists, will remove in next major
  name  = "/${var.name}/mesh/mailboxes/${var.mailbox_id}/MAILBOX_PASSWORD"
}


# TODO: the rest of these SSM params  can be removed completely in a future MAJOR (3.0.0) release,
# TODO: but to not  affect 'inflight' traffic 2.0.0,<3.0.0 should be applied first
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
# TODO: the rest of these SSM params  can be removed completely in a future MAJOR (3.0.0) release,
# TODO: but to not  affect 'inflight' traffic 2.0.0,<3.0.0 should be applied first