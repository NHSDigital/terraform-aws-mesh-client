
resource "aws_security_group" "check_send_parameters" {
  count       = local.vpc_enabled ? 1 : 0
  name        = local.check_send_parameters_name
  description = local.check_send_parameters_name
  vpc_id      = var.vpc_id
}

locals {
  mesh_cidrs = var.mesh_env == "production" ? local.mesh_ips.production : local.mesh_ips.integration

  endpoint_sg_ids = toset(local.vpc_enabled ? compact([
    var.aws_ssm_endpoint_sg_id,
    var.aws_sfn_endpoint_sg_id,
    var.aws_logs_endpoints_sg_id,
    var.aws_kms_endpoints_sg_id,
    var.aws_lambda_endpoints_sg_id,
    var.aws_secrets_endpoints_sg_id,
  ]) : [])
}


resource "aws_security_group_rule" "check_send_mesh" {
  count             = local.vpc_enabled ? 1 : 0
  security_group_id = aws_security_group.check_send_parameters.0.id
  type              = "egress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = local.mesh_cidrs
  description       = "to mesh"
}

resource "aws_security_group_rule" "check_send_s3" {
  count             = local.vpc_enabled ? 1 : 0
  type              = "egress"
  security_group_id = aws_security_group.check_send_parameters.0.id

  from_port       = 443
  to_port         = 443
  protocol        = "tcp"
  prefix_list_ids = [var.aws_s3_endpoint_prefix_list_id]
  description     = "to s3"
}

resource "aws_security_group_rule" "check_send_endpoints" {
  for_each          = local.endpoint_sg_ids
  type              = "egress"
  security_group_id = aws_security_group.check_send_parameters.0.id

  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  source_security_group_id = each.key
  description              = "to endpoint"
}

resource "aws_security_group" "fetch_message_chunk" {
  count       = local.vpc_enabled ? 1 : 0
  name        = local.fetch_message_chunk_name
  description = local.fetch_message_chunk_name
  vpc_id      = var.vpc_id
}

resource "aws_security_group_rule" "fetch_message_mesh" {
  count             = local.vpc_enabled ? 1 : 0
  security_group_id = aws_security_group.fetch_message_chunk.0.id
  type              = "egress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = local.mesh_cidrs
  description       = "to mesh"
}

resource "aws_security_group_rule" "fetch_message_s3" {
  count             = local.vpc_enabled ? 1 : 0
  type              = "egress"
  security_group_id = aws_security_group.fetch_message_chunk.0.id

  from_port       = 443
  to_port         = 443
  protocol        = "tcp"
  prefix_list_ids = [var.aws_s3_endpoint_prefix_list_id]
  description     = "to s3"
}

resource "aws_security_group_rule" "fetch_message_endpoints" {
  for_each          = local.endpoint_sg_ids
  type              = "egress"
  security_group_id = aws_security_group.fetch_message_chunk.0.id

  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  source_security_group_id = each.key
  description              = "to endpoints"
}


resource "aws_security_group" "poll_mailbox" {
  count       = local.vpc_enabled ? 1 : 0
  name        = local.poll_mailbox_name
  description = local.poll_mailbox_name
  vpc_id      = var.vpc_id
}


resource "aws_security_group_rule" "poll_mailbox_mesh" {
  count             = local.vpc_enabled ? 1 : 0
  security_group_id = aws_security_group.poll_mailbox.0.id
  type              = "egress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = local.mesh_cidrs
  description       = "to mesh"
}

resource "aws_security_group_rule" "poll_mailbox_s3" {
  count             = local.vpc_enabled ? 1 : 0
  type              = "egress"
  security_group_id = aws_security_group.poll_mailbox.0.id

  from_port       = 443
  to_port         = 443
  protocol        = "tcp"
  prefix_list_ids = [var.aws_s3_endpoint_prefix_list_id]
  description     = "to s3"
}

resource "aws_security_group_rule" "poll_mailbox_endpoints" {
  for_each          = local.endpoint_sg_ids
  type              = "egress"
  security_group_id = aws_security_group.poll_mailbox.0.id

  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  source_security_group_id = each.key
  description              = "to endpoints"
}

resource "aws_security_group" "send_message_chunk" {
  count       = local.vpc_enabled ? 1 : 0
  name        = local.send_message_chunk_name
  description = local.send_message_chunk_name
  vpc_id      = var.vpc_id

}


resource "aws_security_group_rule" "send_message_mesh" {
  count             = local.vpc_enabled ? 1 : 0
  security_group_id = aws_security_group.send_message_chunk.0.id
  type              = "egress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = local.mesh_cidrs
  description       = "to mesh"
}

resource "aws_security_group_rule" "send_message_s3" {
  count             = local.vpc_enabled ? 1 : 0
  type              = "egress"
  security_group_id = aws_security_group.send_message_chunk.0.id

  from_port       = 443
  to_port         = 443
  protocol        = "tcp"
  prefix_list_ids = [var.aws_s3_endpoint_prefix_list_id]
  description     = "to s3"
}

resource "aws_security_group_rule" "send_message_endpoints" {
  for_each          = local.endpoint_sg_ids
  type              = "egress"
  security_group_id = aws_security_group.send_message_chunk.0.id

  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  source_security_group_id = each.key
  description              = "to endpoints"
}
