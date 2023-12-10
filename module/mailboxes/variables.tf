variable "name" {
  type = string
}
variable "bucket_id" {
  type = string
}
variable "mailbox" {
  type = object({
    id                   = string
    allowed_recipients   = optional(string)
    allowed_senders      = optional(string)
    allowed_workflow_ids = optional(string)
    outbound_mappings = list(object({
      dest_mailbox = string
      workflow_id  = string
    }))
  })
}
variable "mailbox_id" {
  type = string
}
variable "config" {
  type = object({
    environment         = string
    verify_ssl          = bool
    use_secrets_manager = bool
    vpc_id              = string
    subnet_ids          = list(string)

  })
}
variable "key_id" {
  type = string
}