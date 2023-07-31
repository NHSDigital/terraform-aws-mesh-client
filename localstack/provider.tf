provider "aws" {

  region                      = "eu-west-2"
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_region_validation      = true

  access_key = "abc"
  secret_key = "123"

  s3_use_path_style = true

  endpoints {
    codeartifact     = "http://localhost:4567"
    cloudwatch       = "http://localhost:4567"
    cloudwatchevents = "http://localhost:4567"
    cloudwatchlogs   = "http://localhost:4567"
    cloudtrail       = "http://localhost:4567"
    dynamodb         = "http://localhost:4567"
    firehose         = "http://localhost:4567"
    iam              = "http://localhost:4567"
    kinesis          = "http://localhost:4567"
    lambda           = "http://localhost:4567"
    s3               = "http://localhost:4567"
    secretsmanager   = "http://localhost:4567"
    sqs              = "http://localhost:4567"
    ssm              = "http://localhost:4567"
    sns              = "http://localhost:4567"
    events           = "http://localhost:4567"
    ec2              = "http://localhost:4567"
    stepfunctions = "http://localhost:4567"
    sts              = "http://localhost:4567"
    kms              = "http://localhost:4567"

  }
}
