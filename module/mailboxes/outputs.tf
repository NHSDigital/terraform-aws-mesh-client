output "mailbox" {
  value = {
    bucket   = var.bucket_id
    inbound  = local.inbound_folder
    outbound = [for each in local.outbound_mappings : each.folder]
  }
}
