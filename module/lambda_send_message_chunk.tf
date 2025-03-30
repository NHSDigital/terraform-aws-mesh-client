locals {
  send_message_chunk_name = "${local.name}-send-message-chunk"
}

#tfsec:ignore:aws-lambda-enable-tracing
resource "aws_lambda_function" "send_message_chunk" {
  function_name    = local.send_message_chunk_name
  filename         = data.archive_file.app.output_path
  handler          = "mesh_send_message_chunk_application.lambda_handler"
  runtime          = local.python_runtime
  timeout          = 15 * 60 // 15 minutes
  source_code_hash = data.archive_file.app.output_base64sha256
  role             = aws_iam_role.send_message_chunk.arn
  layers           = [aws_lambda_layer_version.mesh_aws_client_dependencies.arn]

  publish = true

  environment {
    variables = local.common_env_vars
  }

  dynamic "vpc_config" {
    for_each = local.vpc_enabled ? [local.vpc_enabled] : []
    content {
      subnet_ids         = var.subnet_ids
      security_group_ids = [aws_security_group.send_message_chunk[0].id]
    }
  }


  depends_on = [
    aws_cloudwatch_log_group.send_message_chunk,
    aws_iam_role_policy_attachment.send_message_chunk
  ]
}

resource "aws_cloudwatch_log_group" "send_message_chunk" {
  name              = "/aws/lambda/${local.send_message_chunk_name}"
  retention_in_days = var.cloudwatch_retention_in_days
  kms_key_id        = aws_kms_key.mesh.arn
  lifecycle {
    ignore_changes = [
      log_group_class, # localstack not currently returning this
    ]
  }
}

resource "aws_iam_role" "send_message_chunk" {
  name               = "${local.send_message_chunk_name}-role"
  description        = "${local.send_message_chunk_name}-role"
  assume_role_policy = data.aws_iam_policy_document.send_message_chunk_assume.json
}

data "aws_iam_policy_document" "send_message_chunk_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type = "Service"

      identifiers = [
        "lambda.amazonaws.com",
      ]
    }
  }
}

resource "aws_iam_role_policy_attachment" "send_message_chunk" {
  role       = aws_iam_role.send_message_chunk.name
  policy_arn = aws_iam_policy.send_message_chunk.arn
}

resource "aws_iam_role_policy_attachment" "send_message_chunk_lambda_insights" {
  role       = aws_iam_role.send_message_chunk.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchLambdaInsightsExecutionRolePolicy"
}

resource "aws_iam_policy" "send_message_chunk" {
  name        = "${local.send_message_chunk_name}-policy"
  description = "${local.send_message_chunk_name}-policy"
  policy      = data.aws_iam_policy_document.send_message_chunk.json
}

#tfsec:ignore:aws-iam-no-policy-wildcards
data "aws_iam_policy_document" "send_message_chunk" {
  statement {
    sid    = "CloudWatchAllow"
    effect = "Allow"

    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]

    resources = [
      "${aws_cloudwatch_log_group.send_message_chunk.arn}*"
    ]
  }

  statement {
    sid    = "SSMDescribe"
    effect = "Allow"

    actions = [
      "ssm:DescribeParameters"
    ]

    resources = [
      "arn:aws:ssm:eu-west-2:${var.account_id}:parameter/${local.name}/*"
    ]
  }

  statement {
    sid    = "SSMGet"
    effect = "Allow"

    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
      "ssm:GetParametersByPath"
    ]

    resources = [
      "arn:aws:ssm:eu-west-2:${var.account_id}:parameter/${local.name}/*",
      "arn:aws:ssm:eu-west-2:${var.account_id}:parameter/${local.name}"
    ]
  }

  statement {
    sid    = "KMSDecrypt"
    effect = "Allow"

    actions = [
      "kms:Decrypt"
    ]

    resources = concat(
      [aws_kms_alias.mesh.target_key_arn],
      var.use_secrets_manager ? local.secrets_kms_key_arns : []
    )
  }

  statement {
    sid    = "S3Allow"
    effect = "Allow"

    actions = [
      "s3:GetObject"
    ]

    resources = [
      aws_s3_bucket.mesh.arn,
      "${aws_s3_bucket.mesh.arn}/*"
    ]
  }
  statement {
    sid    = "DynamoDBAccess"
    effect = "Allow"

    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:DeleteItem",
      "dynamodb:UpdateItem", 
    ]

    resources = [
      "arn:aws:dynamodb:eu-west-2:${var.account_id}:table/${local.locktable_name}"
    ]
  }

  dynamic "statement" {
    for_each = var.use_secrets_manager ? [true] : []
    content {
      sid    = "Secrets"
      effect = "allow"
      actions = [
        "secretsmanager:DescribeSecret",
        "secretsmanager:GetSecretValue",
        "secretsmanager:ListSecretVersionIds",
      ]
      resources = local.secrets_arns
    }
  }

  dynamic "statement" {
    for_each = local.vpc_enabled ? [true] : []
    content {

      sid    = "EC2Interfaces"
      effect = "Allow"

      actions = [
        "ec2:CreateNetworkInterface",
        "ec2:DescribeNetworkInterfaces",
        "ec2:DeleteNetworkInterface",
        "ec2:AssignPrivateIpAddresses",
        "ec2:UnassignPrivateIpAddresses"
      ]

      resources = ["*"]
    }
  }

}
