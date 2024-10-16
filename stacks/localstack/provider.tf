provider "aws" {

  region                      = "eu-west-2"
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_region_validation      = true

  access_key = "abc"
  secret_key = "123"

  s3_use_path_style = true

  endpoints {
    codeartifact     = "http://localhost:4569"
    cloudwatch       = "http://localhost:4569"
    cloudwatchevents = "http://localhost:4569"
    cloudwatchlogs   = "http://localhost:4569"
    cloudtrail       = "http://localhost:4569"
    dynamodb         = "http://localhost:4569"
    firehose         = "http://localhost:4569"
    iam              = "http://localhost:4569"
    kinesis          = "http://localhost:4569"
    lambda           = "http://localhost:4569"
    s3               = "http://localhost:4569"
    secretsmanager   = "http://localhost:4569"
    sqs              = "http://localhost:4569"
    ssm              = "http://localhost:4569"
    sns              = "http://localhost:4569"
    ec2              = "http://localhost:4569"
    stepfunctions    = "http://localhost:4569"
    sts              = "http://localhost:4569"
    kms              = "http://localhost:4569"

  }
}
