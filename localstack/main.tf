module "main" {
  source = "../terraform"

  mailbox_ids = ["TEST123", "TEST456", "TEST789"]

  name_prefix = "local"


  depends_on = [
    aws_vpc_endpoint.s3
  ]

  # not supported in opensource cloudtrail
  cloudtrail_enabled = false

}



