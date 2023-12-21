locals {
  poll_mailbox_name = "${local.name}-poll-mailbox"
}

resource "aws_security_group" "poll_mailbox" {
  count       = local.vpc_enabled ? 1 : 0
  name        = local.poll_mailbox_name
  description = local.poll_mailbox_name
  vpc_id      = var.vpc_id
}

resource "aws_security_group_rule" "poll_mailbox_egress_cidr" {
  for_each          = local.egress_cidrs
  type              = "egress"
  security_group_id = aws_security_group.poll_mailbox.0.id
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = [each.key]
}

resource "aws_security_group_rule" "poll_mailbox_egress_sgs" {
  for_each          = local.egress_sg_ids
  type              = "egress"
  security_group_id = aws_security_group.poll_mailbox.0.id

  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  source_security_group_id = each.key
}

resource "aws_security_group_rule" "poll_mailbox_egress_prefix_list" {
  for_each          = local.egress_prefix_list_ids
  type              = "egress"
  security_group_id = aws_security_group.poll_mailbox.0.id

  from_port       = 443
  to_port         = 443
  protocol        = "tcp"
  prefix_list_ids = [each.key]
}

#tfsec:ignore:aws-lambda-enable-tracing
resource "aws_lambda_function" "poll_mailbox" {
  function_name    = local.poll_mailbox_name
  filename         = data.archive_file.app.output_path
  handler          = "mesh_poll_mailbox_application.lambda_handler"
  runtime          = local.python_runtime
  timeout          = local.lambda_timeout
  source_code_hash = data.archive_file.app.output_base64sha256
  role             = aws_iam_role.poll_mailbox.arn
  layers           = [aws_lambda_layer_version.mesh_aws_client_dependencies.arn]


  environment {
    variables = local.common_env_vars
  }

  dynamic "vpc_config" {
    for_each = local.vpc_enabled ? [local.vpc_enabled] : []
    content {
      subnet_ids         = var.subnet_ids
      security_group_ids = [aws_security_group.poll_mailbox[0].id]
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.poll_mailbox,
    aws_iam_role_policy_attachment.poll_mailbox
  ]
}

resource "aws_cloudwatch_log_group" "poll_mailbox" {
  name              = "/aws/lambda/${local.poll_mailbox_name}"
  retention_in_days = var.cloudwatch_retention_in_days
  kms_key_id        = aws_kms_key.mesh.arn
  lifecycle {
    ignore_changes = [
      log_group_class, # localstack not currently returning this
    ]
  }
}

resource "aws_iam_role" "poll_mailbox" {
  name               = "${local.poll_mailbox_name}-role"
  description        = "${local.poll_mailbox_name}-role"
  assume_role_policy = data.aws_iam_policy_document.poll_mailbox_assume.json
}

data "aws_iam_policy_document" "poll_mailbox_assume" {
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

resource "aws_iam_role_policy_attachment" "poll_mailbox" {
  role       = aws_iam_role.poll_mailbox.name
  policy_arn = aws_iam_policy.poll_mailbox.arn
}

resource "aws_iam_policy" "poll_mailbox" {
  name        = "${local.poll_mailbox_name}-policy"
  description = "${local.poll_mailbox_name}-policy"
  policy      = data.aws_iam_policy_document.poll_mailbox.json
}

#tfsec:ignore:aws-iam-no-policy-wildcards
data "aws_iam_policy_document" "poll_mailbox" {
  statement {
    sid    = "CloudWatchAllow"
    effect = "Allow"

    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]

    resources = [
      "${aws_cloudwatch_log_group.poll_mailbox.arn}*"
    ]
  }

  statement {
    sid    = "SSMDescribe"
    effect = "Allow"

    actions = [
      "ssm:DescribeParameters"
    ]

    resources = [
      "arn:aws:ssm:eu-west-2:${data.aws_caller_identity.current.account_id}:parameter/${local.name}/*"
    ]
  }

  statement {
    sid    = "SSMGet"
    effect = "Allow"

    actions = [
      "ssm:GetParametersByPath"
    ]

    resources = [
      "arn:aws:ssm:eu-west-2:${data.aws_caller_identity.current.account_id}:parameter/${local.name}/*",
      "arn:aws:ssm:eu-west-2:${data.aws_caller_identity.current.account_id}:parameter/${local.name}"
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

  dynamic "statement" {
    for_each = var.use_secrets_manager ? [true] : []
    content {
      sid    = "KMSDecrypt"
      effect = "Allow"

      actions = [
        "kms:Decrypt"
      ]

      resources = local.secrets_kms_key_arns

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

resource "aws_iam_role_policy_attachment" "poll_mailbox_lambda_insights" {
  role       = aws_iam_role.poll_mailbox.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchLambdaInsightsExecutionRolePolicy"
}


resource "aws_iam_role_policy_attachment" "poll_mailbox_check_sfn" {
  role       = aws_iam_role.poll_mailbox.name
  policy_arn = aws_iam_policy.poll_mailbox_check_sfn.arn
}

resource "aws_iam_policy" "poll_mailbox_check_sfn" {
  name        = "${local.poll_mailbox_name}-check-sfn-policy"
  description = "${local.poll_mailbox_name}-check-sfn-policy"
  policy      = data.aws_iam_policy_document.poll_mailbox_check_sfn.json
}

#tfsec:ignore:aws-iam-no-policy-wildcards
data "aws_iam_policy_document" "poll_mailbox_check_sfn" {
  statement {
    sid    = "SFNList"
    effect = "Allow"

    actions = [
      "states:ListExecutions",
      "states:ListStateMachines"
    ]

    resources = [
      "arn:aws:states:eu-west-2:${data.aws_caller_identity.current.account_id}:stateMachine:*",
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
