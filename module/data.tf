data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

data "aws_vpc_endpoint" "s3" {
  count        = local.vpc_enabled ? 1 : 0
  vpc_id       = var.config.vpc_id
  service_name = "com.amazonaws.${var.region}.s3"
}

data "aws_vpc_endpoint" "ssm" {
  count        = local.vpc_enabled ? 1 : 0
  vpc_id       = var.config.vpc_id
  service_name = "com.amazonaws.${var.region}.ssm"
}

data "aws_vpc_endpoint" "lambda" {
  count        = local.vpc_enabled ? 1 : 0
  vpc_id       = var.config.vpc_id
  service_name = "com.amazonaws.${var.region}.lambda"
}

data "aws_vpc_endpoint" "sfn" {
  count        = local.vpc_enabled ? 1 : 0
  vpc_id       = var.config.vpc_id
  service_name = "com.amazonaws.${var.region}.states"
}

data "aws_vpc_endpoint" "logs" {
  count        = local.vpc_enabled ? 1 : 0
  vpc_id       = var.config.vpc_id
  service_name = "com.amazonaws.${var.region}.logs"
}

data "aws_vpc_endpoint" "kms" {
  count        = local.vpc_enabled ? 1 : 0
  vpc_id       = var.config.vpc_id
  service_name = "com.amazonaws.${var.region}.kms"
}
