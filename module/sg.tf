
resource "aws_security_group" "lambdas" {
  count       = local.vpc_enabled ? 1 : 0
  name        = "${local.name}-lambdas"
  description = "sg for all mesh lambda functions"
  vpc_id      = var.vpc_id
}

resource "aws_security_group_rule" "mesh" {
  count             = local.vpc_enabled ? 1 : 0
  security_group_id = aws_security_group.lambdas.0.id
  type              = "egress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = var.mesh_env == "production" ? local.mesh_ips.production : local.mesh_ips.integration
  description       = "to mesh"
}

resource "aws_security_group_rule" "s3" {
  count             = local.vpc_enabled ? 1 : 0
  type              = "egress"
  security_group_id = aws_security_group.lambdas.0.id

  from_port       = 443
  to_port         = 443
  protocol        = "tcp"
  prefix_list_ids = [var.aws_s3_endpoint_prefix_list_id]
  description     = "to s3"
}

resource "aws_security_group_rule" "ssm" {
  count             = local.vpc_enabled ? 1 : 0
  type              = "egress"
  security_group_id = aws_security_group.lambdas.0.id

  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  source_security_group_id = var.aws_ssm_endpoint_sg_id
  description              = "to ssm"
}

resource "aws_security_group_rule" "sfn" {
  count             = local.vpc_enabled ? 1 : 0
  type              = "egress"
  security_group_id = aws_security_group.lambdas.0.id

  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  source_security_group_id = var.aws_sfn_endpoint_sg_id
  description              = "to sfn"
}

resource "aws_security_group_rule" "logs" {
  count             = local.vpc_enabled ? 1 : 0
  type              = "egress"
  security_group_id = aws_security_group.lambdas.0.id

  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  source_security_group_id = var.aws_logs_endpoints_sg_id
  description              = "to logs"
}

resource "aws_security_group_rule" "kms" {
  count             = local.vpc_enabled ? 1 : 0
  type              = "egress"
  security_group_id = aws_security_group.lambdas.0.id

  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  source_security_group_id = var.aws_kms_endpoints_sg_id
  description              = "to kms"
}

resource "aws_security_group_rule" "lambda" {
  count             = local.vpc_enabled ? 1 : 0
  type              = "egress"
  security_group_id = aws_security_group.lambdas.0.id

  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  source_security_group_id = var.aws_lambda_endpoints_sg_id
  description              = "to lambda"
}

resource "aws_security_group_rule" "secrets" {
  count             = local.vpc_enabled && var.use_secrets_manager ? 1 : 0
  type              = "egress"
  security_group_id = aws_security_group.lambdas.0.id

  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  source_security_group_id = var.aws_secrets_endpoints_sg_id
  description              = "to secrets"
}
