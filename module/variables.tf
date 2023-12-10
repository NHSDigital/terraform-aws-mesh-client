variable "name_prefix" {
  type        = string
  description = "Name to prefix on to the resources"
}

variable "region" {
  type    = string
  default = "eu-west-2"
}

variable "config" {
  description = "Shared Mesh configuration"

  type = object({
    environment         = string
    verify_ssl          = bool
    use_secrets_manager = bool
    vpc_id              = string
    subnet_ids          = list(string)
  })

  default = {
    environment         = "production"
    verify_ssl          = true
    use_secrets_manager = false
    vpc_id              = ""
    subnet_ids          = []
  }

  validation {
    condition     = var.config.environment == "integration" || var.config.environment == "production" || var.config.environment == "local"
    error_message = "The environment value must be \"local\", \"integration\" or \"production\"."
  }
}

variable "mailboxes" {
  description = "Configuration of Mesh mailboxes"

  # TODO make outbound_mappings optional
  type = list(object({
    id                   = string
    allowed_recipients   = optional(string)
    allowed_senders      = optional(string)
    allowed_workflow_ids = optional(string)
    outbound_mappings = list(object({
      dest_mailbox = string
      workflow_id  = string
    }))
  }))

  default = []
}

variable "mailbox_ids" {
  type = set(string)
}


variable "account_admin_role" {
  description = "Administrative Account Role used for policies that require owners, like KMS"
  type        = string
  default     = "NHSDAdminRole"
}

variable "cloudwatch_retention_in_days" {
  description = "How many days to retain CloudWatch logs for"
  type        = number
  default     = 365
}

variable "s3logs_retention_in_days" {
  description = "How many days to retain S3 object logs for"
  type        = number
  default     = 7

  validation {
    condition     = var.s3logs_retention_in_days >= 1
    error_message = "The s3logs_retention_in_days value must be greater than or equal to 1."
  }
}

variable "mesh_cloudwatch_log_retention_in_days" {
  type    = number
  default = 30
}

variable "get_messages_enabled" {
  type    = bool
  default = true
}

variable "mesh_s3_object_expiry_in_days" {
  default = 60
}

variable "mesh_s3_object_expiry_enabled" {
  type    = bool
  default = false
}

variable "cloudtrail_enabled" {
  type    = bool
  default = true
}


variable "get_message_max_concurrency" {
  type    = number
  default = 1
}


variable "get_messages_schedule" {
  # https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-rule-schedule.html
  type    = string
  default = "rate(1 minute)"
}

variable "handshake_schedule" {
  # https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-rule-schedule.html
  type    = string
  default = "rate(1 hour)"
}