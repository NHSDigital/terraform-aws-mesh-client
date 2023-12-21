variable "name" {
  type = string
}
variable "bucket_id" {
  type = string
}
variable "mailbox" {
  type = object({
    id = string
    outbound_mappings = list(object({
      dest_mailbox = string
      workflow_id  = string
    }))
  })
}
variable "mailbox_id" {
  type = string
}
