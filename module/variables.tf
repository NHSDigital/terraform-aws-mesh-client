variable "name_prefix" {
  type        = string
  description = "Name to prefix on to the resources"
}

variable "region" {
  type    = string
  default = "eu-west-2"
}

variable "mesh_env" {
  type        = string
  description = "mesh environment (integration/production) .. will set the correct mesh url and egress cidrs for vpc lambdas too"

  validation {
    condition     = var.mesh_env == "integration" || var.mesh_env == "production" || var.mesh_env == "local"
    error_message = "mesh_env must be one of local/integration/production"
  }
}

variable "verify_ssl" {
  type        = bool
  default     = true
  description = "if false will set verify=false for requests to mesh (not recommended for production)"
}

variable "verify_checks_common_name" {
  type        = bool
  default     = true
  description = "will allow ssl verify to check the certificate common name"
}

variable "use_secrets_manager" {
  type        = bool
  default     = false
  description = "retrieve client certificate key and mailbox passwords from secrets manager rather than ssm"
}

variable "use_sender_filename" {
  type        = bool
  default     = false
  description = "if true the inbound mex-filename will be used as the filename for storage in s3 rather than {message_id}.dat"
}

variable "use_s3_key_for_mex_filename" {
  type        = bool
  default     = false
  description = "not recommended, if true the outgoing mex-filename header will be set using the os.path.basename(s3_object.key)"
}

variable "use_legacy_inbound_location" {
  type        = bool
  default     = false
  description = "if true the INBOUND_BUCKET/INBOUND_FOLDER locations from SSM will be used rather than a default of s3://{mesh-bucket}/inbound/{mailbox_id}/{filename}"
}


variable "chunk_size" {
  type        = number
  default     = 20 * 1024 * 1024
  description = "defines chunk_size used to partition send files when sending to MESH, applied before compression if your files are large and very compressible you may want to increase this"

  validation {
    condition     = 0 < var.chunk_size
    error_message = "must be greater than zero"
  }
}

variable "crumb_size" {
  type        = number
  default     = null
  description = "advanced, defines the s3 read/write buffer size ( should be lte chunk_size )"

  validation {
    condition     = var.crumb_size == null || 0 < var.crumb_size
    error_message = "must be null or between zero and chunk_size"
  }
}

variable "never_compress" {
  type        = bool
  default     = false
  description = "advanced, if set true, we will never attempt to compress chunks before sending to MESH, if you data is always pre-compressed you may want to set this, but preferably set the content-encoding on the file when storing in s3"
}

variable "compress_threshold" {
  type        = number
  default     = 20 * 1024 * 1024
  description = "advanced, defines the min size file to compress, set to zero to compress everything"

  validation {
    condition     = 0 <= var.compress_threshold
    error_message = "must be between zero and chunk_size"
  }
}

variable "vpc_id" {
  type        = string
  default     = ""
  description = "if set this will deploy the lambdas in the specified vpc and require VPC endpoints to access aws services"
}

variable "subnet_ids" {
  type        = set(string)
  description = "subnet ids that the lambdas will be attached to in the vpc"
}


variable "mailboxes" {
  description = "deprecated, legacy way of configuring outbound mappings"

  # TODO: mailboxes config can be removed in a future major release (3.0.0)
  type = list(object({
    id = string
    outbound_mappings = list(object({
      dest_mailbox = string
      workflow_id  = string
    }))
  }))

  default = []
}

variable "mailbox_ids" {
  type        = set(string)
  description = "list of your MESH mailbox_ids to poll for new messages"
}

variable "cloudwatch_retention_in_days" {
  description = "How many days to retain CloudWatch logs for"
  type        = number
  default     = 365
}

variable "cloudtrail_cloudwatch_log_retention_in_days" {
  type        = number
  default     = 30
  description = "separate configuration of the cloudtrail log retention"
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


variable "get_messages_enabled" {
  type        = bool
  default     = true
  description = "if set to false the poll for new messages will be disabled, you should 'almost never' set this or your mailbox(es) may overflow"
}

variable "mesh_s3_object_expiry_in_days" {
  default     = 60
  description = "days to retain mesh message objects in the s3 bucket, objects will be marked as non-current after x days and permanently deleted x days after that"
}

variable "mesh_s3_object_expiry_enabled" {
  type        = bool
  default     = false
  description = "recommended to set this to true and use alternative locations for long term storage of sent and received messages, where required"
}

variable "cloudtrail_enabled" {
  type        = bool
  default     = true
  description = "set this to false for localstack (where cloudtrail is not supported), this should be set to true for AWS environments or send message triggers will not fire"
}


variable "get_message_max_concurrency" {
  type        = number
  default     = 1
  description = "parallelism for get messages, if you are receiving lots of messages this may help achieve a higher throughput"
}

variable "get_messages_schedule" {
  # https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-rule-schedule.html
  type        = string
  default     = "rate(1 minute)"
  description = "schedule on which to check for new messages, it's recommended this is quite frequent, but it can be tweaked."
}

variable "handshake_schedule" {
  # https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-rule-schedule.html
  type        = string
  default     = "rate(1 hour)"
  description = "schedule on which to handshake with MESH, not recommended to do this more frequently than once per hour."
}

variable "fetch_message_ephemeral_storage_size" {
  type        = number
  default     = 1024
  description = "this is in MiB so 1024 is 1GiB, retrieved chunks are buffered to disk in the receiving lambda function, if you are are receiving high volumes of smaller messages, you may want to lower this"
}
