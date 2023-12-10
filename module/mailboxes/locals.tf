

locals {
  inbound_folder = "inbound_${var.mailbox_id}"

  # unfortunately the outbound mappings does not currently work with the ssm parameters
  # this: for_each { for outbound_mapping in var.mailbox.outbound_mappings : var.mailbox_id => outbound_mapping }
  # created a map of one with the input mailbox_id as the key
  # suspect it should have been:
  # this: for_each { for outbound_mapping in var.mailbox.outbound_mappings : var.outbound_mapping.dest_mailbox => outbound_mapping }
  # plan is to remove SSM parameters as a means of configuring send so will retain for to avoid deleting SSM params
  first_outbound_mapping = length(coalesce(var.mailbox.outbound_mappings, [])) > 0 ? slice(var.mailbox.outbound_mappings, 0, 1) : []
  outbound_mappings = { for each in local.first_outbound_mapping : var.mailbox_id => {
    folder       = "outbound_${var.mailbox_id}_to_${each.dest_mailbox}"
    dest_mailbox = each.dest_mailbox
    workflow_id  = each.workflow_id
  } }


}