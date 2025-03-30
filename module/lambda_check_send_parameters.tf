locals {
  check_send_parameters_name = "${local.name}-check-send-parameters"
}


#tfsec:ignore:aws-lambda-enable-tracing
resource "aws_lambda_function" "check_send_parameters" {
  function_name    = local.check_send_parameters_name
  filename         = data.archive_file.app.output_path
  handler          = "mesh_check_send_parameters_application.lambda_handler"
  runtime          = local.python_runtime
  timeout          = 60
  source_code_hash = data.archive_file.app.output_base64sha256
  role             = aws_iam_role.check_send_parameters.arn
  layers           = [aws_lambda_layer_version.mesh_aws_client_dependencies.arn]

  publish = true

  environment {
    variables = local.common_env_vars
  }

  dynamic "vpc_config" {
    for_each = local.vpc_enabled ? [local.vpc_enabled] : []
    content {
      subnet_ids         = var.subnet_ids
      security_group_ids = [aws_security_group.check_send_parameters[0].id]
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.check_send_parameters,
    aws_iam_role_policy_attachment.check_send_parameters
  ]
}

resource "aws_cloudwatch_log_group" "check_send_parameters" {
  name              = "/aws/lambda/${local.check_send_parameters_name}"
  retention_in_days = var.cloudwatch_retention_in_days
  kms_key_id        = aws_kms_key.mesh.arn
  lifecycle {
    ignore_changes = [
      log_group_class, # localstack not currently returning this
    ]
  }
}

resource "aws_iam_role" "check_send_parameters" {
  name               = "${local.check_send_parameters_name}-role"
  description        = "${local.check_send_parameters_name}-role"
  assume_role_policy = data.aws_iam_policy_document.check_send_parameters_assume.json
}

data "aws_iam_policy_document" "check_send_parameters_assume" {
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

resource "aws_iam_role_policy_attachment" "check_send_parameters" {
  role       = aws_iam_role.check_send_parameters.name
  policy_arn = aws_iam_policy.check_send_parameters.arn
}

resource "aws_iam_policy" "check_send_parameters" {
  name        = "${local.check_send_parameters_name}-policy"
  description = "${local.check_send_parameters_name}-policy"
  policy      = data.aws_iam_policy_document.check_send_parameters.json
}

#tfsec:ignore:aws-iam-no-policy-wildcards
data "aws_iam_policy_document" "check_send_parameters" {
  statement {
    sid    = "CloudWatchAllow"
    effect = "Allow"

    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]

    resources = [
      aws_cloudwatch_log_group.check_send_parameters.arn,
      "${aws_cloudwatch_log_group.check_send_parameters.arn}:*"
    ]
  }

  statement {
    sid    = "SSMDescribe"
    effect = "Allow"

    actions = [
      "ssm:DescribeParameters"
    ]

    resources = ["*"]
  }

  statement {
    sid    = "SSMAllow"
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

    resources = [
      aws_kms_alias.mesh.target_key_arn
    ]
  }

  statement {
    sid    = "S3Allow"
    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:ListBucket",
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

resource "aws_iam_role_policy_attachment" "check_send_lambda_insights" {
  role       = aws_iam_role.check_send_parameters.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchLambdaInsightsExecutionRolePolicy"
}

resource "aws_iam_role_policy_attachment" "check_send_parameters_check_sfn" {
  role       = aws_iam_role.check_send_parameters.name
  policy_arn = aws_iam_policy.check_send_parameters_check_sfn.arn
}

resource "aws_iam_policy" "check_send_parameters_check_sfn" {
  name        = "${local.check_send_parameters_name}-check-sfn-policy"
  description = "${local.check_send_parameters_name}-check-sfn-policy"
  policy      = data.aws_iam_policy_document.check_send_parameters_check_sfn.json
}

#tfsec:ignore:aws-iam-no-policy-wildcards
data "aws_iam_policy_document" "check_send_parameters_check_sfn" {
  statement {
    sid    = "SFNList"
    effect = "Allow"

    actions = [
      "states:ListExecutions",
      "states:ListStateMachines"
    ]

    resources = [
      "arn:aws:states:eu-west-2:${var.account_id}:stateMachine:*",
      aws_sfn_state_machine.get_messages.arn,
      aws_sfn_state_machine.send_message.arn
    ]
  }

  statement {
    sid    = "SFNAllow"
    effect = "Allow"

    actions = [
      "states:DescribeExecution",
    ]

    resources = [
      "${replace(aws_sfn_state_machine.get_messages.arn, "stateMachine", "execution")}*",
      "${replace(aws_sfn_state_machine.send_message.arn, "stateMachine", "execution")}*"
    ]
  }

  
}
