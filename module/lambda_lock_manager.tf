locals {
  lock_manager_name = "${local.name}-lock-manager"
}

resource "aws_lambda_function" "lock_manager" {
  function_name    = local.lock_manager_name
  filename         = data.archive_file.app.output_path
  handler          = "mesh_lock_manager_application.lambda_handler"
  runtime          = local.python_runtime
  timeout          = local.lambda_timeout
  source_code_hash = data.archive_file.app.output_base64sha256
  role             = aws_iam_role.lock_manager.arn
  layers           = [aws_lambda_layer_version.mesh_aws_client_dependencies.arn]

  publish = true

  environment {
    variables = local.common_env_vars
  }

  dynamic "vpc_config" {
    for_each = local.vpc_enabled ? [local.vpc_enabled] : []
    content {
      subnet_ids         = var.subnet_ids
      security_group_ids = [aws_security_group.lock_manager[0].id]
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.lock_manager,
  ]
}

resource "aws_cloudwatch_log_group" "lock_manager" {
  name              = "/aws/lambda/${local.lock_manager_name}"
  retention_in_days = var.cloudwatch_retention_in_days
  kms_key_id        = aws_kms_key.mesh.arn
  lifecycle {
    ignore_changes = [
      log_group_class, # localstack not currently returning this
    ]
  }
}

resource "aws_iam_role" "lock_manager" {
  name               = "${local.lock_manager_name}-role"
  description        = "${local.lock_manager_name}-role"
  assume_role_policy = data.aws_iam_policy_document.lock_manager_assume.json
}

data "aws_iam_policy_document" "lock_manager_assume" {
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

resource "aws_iam_role_policy_attachment" "lock_manager" {
  role       = aws_iam_role.lock_manager.name
  policy_arn = aws_iam_policy.lock_manager.arn
}

resource "aws_iam_policy" "lock_manager" {
  name        = "${local.lock_manager_name}-policy"
  description = "${local.lock_manager_name}-policy"
  policy      = data.aws_iam_policy_document.lock_manager.json
}

data "aws_iam_policy_document" "lock_manager" {
  statement {
    sid    = "CloudWatchAllow"
    effect = "Allow"

    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]

    resources = [
      "${aws_cloudwatch_log_group.lock_manager.arn}*"
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
    sid    = "DynamoDBDelete"
    effect = "Allow"

    actions = [
      "dynamodb:DeleteItem"
    ]

    resources = [
      "arn:aws:dynamodb:eu-west-2:${var.account_id}:table/${local.locktable_name}"
    ]
  }
}