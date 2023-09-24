
# these are deprecated resources, but trying to migrate to aws_s3_object could potentially delete the folders
# think a state rm / and remove these from terraform completely would be best
resource "aws_s3_bucket_object" "inbound" {
  bucket       = var.bucket_id
  key          = "inbound_${var.mailbox_id}/"
  acl          = "private"
  content_type = "application/x-directory"
}

resource "aws_s3_bucket_object" "outbound" {
  for_each = { for outbound_mapping in var.mailbox.outbound_mappings : var.mailbox_id => outbound_mapping }

  bucket       = var.bucket_id
  key          = "outbound_${var.mailbox_id}_to_${each.value.dest_mailbox}/"
  acl          = "private"
  content_type = "application/x-directory"
}
