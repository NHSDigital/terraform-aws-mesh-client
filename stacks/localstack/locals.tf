
locals {
  vpc_cidr      = "10.254.69.0/24"
  config_prefix = "${var.env}-mesh"
  # secrets manager implementation does not currently work as no IAM permissions exist to access the secrets
  use_secrets_manager = false
}