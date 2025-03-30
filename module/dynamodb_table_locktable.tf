locals {
  locktable_name = "${local.name}-lock-table"
}

#tfsec:ignore:aws-dynamodb-enable-at-rest-encryption
resource "aws_dynamodb_table" "lock_table" {
  name           = local.locktable_name
  billing_mode   = "PROVISIONED"
  read_capacity  = 20
  write_capacity = 20
  hash_key       = "LockName"
  stream_enabled = false
  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  attribute {
    name = "LockName"
    type = "S"
  }

  attribute {
    name = "LockType"
    type = "S"
  }

  attribute {
    name = "LockOwner"
    type = "S"
  }

  global_secondary_index {
    name            = "LockTypeOwnerTableIndex"
    hash_key        = "LockType"
    range_key       = "LockOwner"
    write_capacity  = 5
    read_capacity   = 5
    projection_type = "KEYS_ONLY"
  }
}