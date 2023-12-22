resource "aws_kms_key" "mesh" {
  description             = local.name
  deletion_window_in_days = 14
  is_enabled              = true
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.mesh.json
}

resource "aws_kms_alias" "mesh" {
  name          = "alias/${local.name}"
  target_key_id = aws_kms_key.mesh.key_id
}

data "aws_iam_policy_document" "mesh" {

  statement {
    sid       = "Enable IAM User Permissions"
    effect    = "Allow"
    resources = ["*"]
    actions   = ["kms:*"]

    principals {
      type = "AWS"
      identifiers = [
        "arn:aws:iam::${var.account_id}:root"
      ]
    }
  }

  statement {
    sid       = "Allow cloudwatch access for log groups"
    effect    = "Allow"
    resources = ["*"]

    actions = [
      "kms:Encrypt*",
      "kms:Decrypt*",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:Describe*",
    ]

    condition {
      test     = "ArnLike"
      variable = "kms:EncryptionContext:aws:logs:arn"
      values = [
        "arn:aws:logs::${var.account_id}:*",
        "arn:aws:logs:${var.region}:${var.account_id}:*"
      ]
    }

    principals {
      type        = "Service"
      identifiers = ["logs.${var.region}.amazonaws.com"]
    }
  }

  statement {
    actions = [
      "kms:GenerateDataKey*",
    ]
    condition {
      test = "StringLike"
      values = [
        "arn:aws:cloudtrail:*:${var.account_id}:trail/*",
      ]
      variable = "kms:EncryptionContext:aws:cloudtrail:arn"
    }
    principals {
      identifiers = [
        "cloudtrail.amazonaws.com",
      ]
      type = "Service"
    }
    resources = [
      "*",
    ]
    sid = "Mesh Allow CloudTrail to encrypt logs"
  }

  statement {
    actions = [
      "kms:DescribeKey",
    ]
    principals {
      identifiers = [
        "cloudtrail.amazonaws.com",
      ]
      type = "Service"
    }
    resources = [
      "*",
    ]
    sid = "Mesh Allow CloudTrail to describe key"
  }
}
