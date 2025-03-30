config {
  #Enables module inspection
  call_module_type = "all"
  force = false
}

plugin "aws" {
    enabled = true
    version = "0.30.0"
    source  = "github.com/terraform-linters/tflint-ruleset-aws"
}