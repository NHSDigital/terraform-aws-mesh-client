# terraform-aws-mesh-client

Common code for MESH AWS serverless client, built and tested by NHS England

Release Notes
------------
see [CHANGE-LOG](CHANGE-LOG.md) for news on major changes


## Usage

# MESH Lambdas

A terraform module to provide AWS infrastructure capable of sending and receiving MESH messages

## Configuration

Example configuration required to use this module:

find the release you want from https://github.com/NHSDigital/terraform-aws-mesh-client/releases and substitute in the module version below ... e.g. ref=v1.0.1

```
module "mesh" {
  source = "git::https://github.com/nhsdigital/terraform-aws-mesh-client.git//module?ref=<version>

  name_prefix = "example-project"

  config = {
    environment = "integration"
    verify_ssl  = true
  }

  mailboxes = [
      {
        id = "X26OT178"
        outbound_mappings = [
          {
            dest_mailbox = "X26OT179"
            workflow_id  = "TESTWORKFLOW"
          }
        ]
      },
      {
        id                = "X26OT179"
        outbound_mappings = []
      }
    ]
}
```

Release versions will be pushed to Github as git tags, with the format `v<major>.<minor>.<patch>` such as `v1.0.1`

## Tagging

We do not tag any resources created by this module, to configure tags across all supported resources, use the provider level default tags

Below is an example passing in Spines preferred tags:

```
provider "aws" {
  region  = "eu-west-2"
  profile = "default"

  default_tags {
    tags = {
      TagVersion         = "1"
      Programme          = "example-programme"
      Project            = "example-project"
      DataClassification = "5"
      Environment        = "preprod"
      ServiceCategory    = "Silver"
      Tool               = "terraform"
    }
  }
}
```



