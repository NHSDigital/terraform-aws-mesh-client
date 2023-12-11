locals {
  name = "${var.name_prefix}-mesh"

  abs_path = abspath(path.module)

  mesh_url = {
    local       = "https://mesh_sandbox"
    integration = "https://msg.intspineservices.nhs.uk"
    production  = "https://mesh-sync.spineservices.nhs.uk"
  }

  mesh_ips = {
    integration = [
      "3.11.177.31/32", "35.177.15.89/32", "3.11.199.83/32",       # Blue
      "35.178.64.126/32", "18.132.113.121/32", "18.132.31.159/32", # Green

    ]
    production = [
      "18.132.56.40/32", "3.11.193.200/32", "35.176.248.137/32", # Blue
      "3.10.194.216/32", "35.176.231.190/32", "35.179.50.16/32"  # Green
    ]
  }

  vpc_enabled = var.config.vpc_id == "" ? false : true

  egress_cidrs = toset(local.vpc_enabled ? (var.config.environment == "production" ? local.mesh_ips.production : local.mesh_ips.integration) : [])
  egress_sg_ids = toset(local.vpc_enabled ?
    concat(
      length(data.aws_vpc_endpoint.ssm) == 0 ? [] : data.aws_vpc_endpoint.ssm.0.security_group_ids,
      length(data.aws_vpc_endpoint.sfn) == 0 ? [] : data.aws_vpc_endpoint.sfn.0.security_group_ids,
      length(data.aws_vpc_endpoint.kms) == 0 ? [] : data.aws_vpc_endpoint.kms.0.security_group_ids,
      length(data.aws_vpc_endpoint.lambda) == 0 ? [] : data.aws_vpc_endpoint.lambda.0.security_group_ids,
      length(data.aws_vpc_endpoint.logs) == 0 ? [] : data.aws_vpc_endpoint.logs.0.security_group_ids,
    ) : []
  )

  egress_prefix_list_ids = toset(local.vpc_enabled ?
    concat(
      length(data.aws_vpc_endpoint.s3) == 0 ? [] : [data.aws_vpc_endpoint.s3.0.prefix_list_id]
    ) : []
  )



  python_runtime = "python3.11"
  lambda_timeout = 300
}
