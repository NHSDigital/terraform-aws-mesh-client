resource "aws_s3_bucket" "mesh" {
  bucket = local.name
}


resource "aws_s3_bucket_lifecycle_configuration" "mesh" {
  bucket = aws_s3_bucket.mesh.id

  rule {
    id     = "ExpireMeshObjects"
    status = var.mesh_s3_object_expiry_enabled ? "Enabled" : "Disabled"

    abort_incomplete_multipart_upload {
      days_after_initiation = 3
    }

    expiration {
      days = var.mesh_s3_object_expiry_in_days
    }

    noncurrent_version_expiration {
      noncurrent_days = var.mesh_s3_object_expiry_in_days
    }

    filter {
    }

  }

}

resource "aws_s3_bucket_server_side_encryption_configuration" "mesh" {
  bucket = aws_s3_bucket.mesh.bucket
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.mesh.key_id
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_logging" "mesh" {
  bucket        = aws_s3_bucket.mesh.bucket
  target_bucket = aws_s3_bucket.s3logs.id
  target_prefix = "bucket_logs/"
}


resource "aws_s3_bucket_versioning" "mesh" {
  bucket = aws_s3_bucket.mesh.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_ownership_controls" "mesh" {
  bucket = aws_s3_bucket.mesh.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}



resource "aws_s3_bucket_public_access_block" "mesh" {
  bucket = aws_s3_bucket.mesh.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "mesh_bucket_policy" {
  bucket = aws_s3_bucket.mesh.id
  policy = data.aws_iam_policy_document.mesh_bucket_policy.json
}

data "aws_iam_policy_document" "mesh_bucket_policy" {
  statement {
    sid = "AllowSSLRequestsOnly"
    actions = [
      "s3:*",
    ]
    effect = "Deny"
    resources = [
      "arn:aws:s3:::${local.name}",
      "arn:aws:s3:::${local.name}/*",
    ]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test = "Bool"
      values = [
        "false",
      ]

      variable = "aws:SecureTransport"
    }
  }
  statement {
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions = [
      "s3:*",
    ]
    resources = [
      "arn:aws:s3:::${local.name}",
      "arn:aws:s3:::${local.name}/*",
    ]
    condition {
      test = "NumericLessThan"
      values = [
        1.2,
      ]

      variable = "s3:TlsVersion"
    }
  }
}
