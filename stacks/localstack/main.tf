module "main" {
  source = "../../module"

  mailbox_ids = ["X26ABC1", "X26ABC2", "X26ABC3"]

  name_prefix = "local"


  depends_on = [
    aws_vpc_endpoint.s3
  ]

  # not supported in opensource cloudtrail
  cloudtrail_enabled = false

}



