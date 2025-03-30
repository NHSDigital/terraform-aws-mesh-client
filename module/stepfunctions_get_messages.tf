locals {
  get_messages_name = "${local.name}-get-messages"
}

resource "aws_sfn_state_machine" "get_messages" {
  name     = local.get_messages_name
  type     = "STANDARD"
  role_arn = aws_iam_role.get_messages.arn

  publish = true

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.get_messages.arn}:*"
    include_execution_data = true
    level                  = "ALL"
  }

  depends_on = [
    aws_lambda_function.poll_mailbox,
    aws_lambda_function.fetch_message_chunk
  ]

  definition = jsonencode({
    Comment = local.get_messages_name
    StartAt = "Poll for messages"
    States = {
      Fail = {
        Type = "Fail"
      }
      "Failed?" = {
        Choices = [
          {
            Next          = "Poll complete release lock"
            NumericEquals = 204
            Variable      = "$.statusCode"
          },
          {
            Next                     = "Fail"
            NumericGreaterThanEquals = 300
            Variable                 = "$.statusCode"
          },
        ]
        Default = "For each waiting message"
        Type    = "Choice"
      }
      "For each waiting message" = {
        ItemsPath = "$.body.message_list"
        Iterator = {
          StartAt = "Fetch message chunk"
          States = {
            "Fetch message chunk" = {
              Next       = "Is this the last chunk?"
              OutputPath = "$.Payload"
              Parameters = {
                FunctionName = "${aws_lambda_function.fetch_message_chunk.arn}:${aws_lambda_function.fetch_message_chunk.version}"
                "Payload.$"  = "$"
              }
              Resource = "arn:aws:states:::lambda:invoke"
              Retry = [
                {
                  BackoffRate = 2
                  ErrorEquals = [
                    "Lambda.ServiceException",
                    "Lambda.AWSLambdaException",
                    "Lambda.SdkClientException",
                  ]
                  IntervalSeconds = 2
                  MaxAttempts     = 3
                },
              ]
              Type = "Task"
            }
            "File complete" = {
              "Type" = "Succeed"
            }
            "Is this the last chunk?" = {
              Choices = [
                {
                  BooleanEquals = true
                  Next          = "File complete"
                  Variable      = "$.body.complete"
                },
              ]
              Default = "Fetch message chunk"
              Type    = "Choice"
            }
          }
        }
        MaxConcurrency = var.get_message_max_concurrency
        Next           = "Were there exactly ${var.get_messages_page_limit} messages?"
        ResultPath     = null
        Type           = "Map"
      }
      "Poll complete" = {
        Type = "Succeed"
      }
      "Poll for messages" = {
        Next       = "Failed?"
        OutputPath = "$.Payload"
        Parameters = {
          FunctionName = "${aws_lambda_function.poll_mailbox.arn}:${aws_lambda_function.poll_mailbox.version}"
          Payload = {
            "EventDetail.$" = "$"
            "ExecutionId.$" = "$$.Execution.Id"
          }
        }
        Resource = "arn:aws:states:::lambda:invoke"
        Retry = [
          {
            BackoffRate = 2
            ErrorEquals = [
              "Lambda.ServiceException",
              "Lambda.AWSLambdaException",
              "Lambda.SdkClientException",
            ]
            IntervalSeconds = 2
            MaxAttempts     = 3
          },
          {
            ErrorEquals = [
              "States.TaskFailed"
            ],
            BackoffRate     = 1,
            IntervalSeconds = 300,
            MaxAttempts     = 2
          },
        ]
        Type = "Task"
      }
      "Were there exactly ${var.get_messages_page_limit} messages?" = {
        Choices = [
          {
            Next          = "Poll for messages"
            NumericEquals = var.get_messages_page_limit
            Variable      = "$.body.message_count"
          },
        ]
        Default = "Poll complete release lock"
        Type    = "Choice"
      }
      "Poll complete release lock" = {
        Next       = "Poll complete"
        OutputPath = "$.Payload"
        Parameters = {
          FunctionName = "${aws_lambda_function.lock_manager.arn}:${aws_lambda_function.lock_manager.version}"
          Payload = {
            "EventDetail.$" = "$"
            "Operation"     = "release"
          }
        }
        Resource = "arn:aws:states:::lambda:invoke"
        Retry = [
          {
            BackoffRate = 2
            ErrorEquals = [
              "Lambda.ServiceException",
              "Lambda.AWSLambdaException",
              "Lambda.SdkClientException",
            ]
            IntervalSeconds = 2
            MaxAttempts     = 3
          },
          {
            ErrorEquals = [
              "States.TaskFailed"
            ],
            BackoffRate     = 1,
            IntervalSeconds = 300,
            MaxAttempts     = 2
          },
        ]
        Type = "Task"
      }
    }
  })
}

resource "aws_cloudwatch_log_group" "get_messages" {
  name              = "/aws/states/${local.get_messages_name}"
  retention_in_days = var.cloudwatch_retention_in_days
  kms_key_id        = aws_kms_key.mesh.arn
  lifecycle {
    ignore_changes = [
      log_group_class, # localstack not currently returning this
    ]
  }
}

resource "aws_iam_role" "get_messages" {
  name               = local.get_messages_name
  description        = local.get_messages_name
  assume_role_policy = data.aws_iam_policy_document.get_messages_assume.json
}

data "aws_iam_policy_document" "get_messages_assume" {
  statement {
    actions = [
      "sts:AssumeRole"
    ]

    principals {
      type = "Service"

      identifiers = [
        "states.amazonaws.com",
      ]
    }
  }
}

resource "aws_iam_role_policy_attachment" "get_messages" {
  role       = aws_iam_role.get_messages.name
  policy_arn = aws_iam_policy.get_messages.arn
}

resource "aws_iam_policy" "get_messages" {
  name        = local.get_messages_name
  description = local.get_messages_name
  policy      = data.aws_iam_policy_document.get_messages.json
}

#tfsec:ignore:aws-iam-no-policy-wildcards
data "aws_iam_policy_document" "get_messages" {
  statement {
    sid    = "CloudWatchAllow"
    effect = "Allow"

    actions = [
      "logs:CreateLogDelivery",
      "logs:GetLogDelivery",
      "logs:UpdateLogDelivery",
      "logs:DeleteLogDelivery",
      "logs:ListLogDeliveries",
      "logs:PutResourcePolicy",
      "logs:DescribeResourcePolicies",
      "logs:DescribeLogGroups"
    ]

    # AWS Bug creating a policy too large if you use anything but "*" here
    # resulting in a failed terraform deployment
    # https://forums.aws.amazon.com/thread.jspa?threadID=321488
    resources = ["*"]
  }

  statement {
    sid    = "LamdaInvokeAllow"
    effect = "Allow"

    resources = [
      aws_lambda_function.fetch_message_chunk.arn,
      "${aws_lambda_function.fetch_message_chunk.arn}:*",
      aws_lambda_function.poll_mailbox.arn,
      "${aws_lambda_function.poll_mailbox.arn}:*",
      aws_lambda_function.lock_manager.arn,
      "${aws_lambda_function.lock_manager.arn}:*"
    ]

    actions = ["lambda:InvokeFunction"]
  }
}
