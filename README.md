# mesh-client-aws-serverless

Common code for MESH AWS serverless client, built to spec and tested by NHS Digital Solutions Assurance, using the

## Installation

Simply add the pre-built package to your python environment.

The latest version can be obtained with the following curl command if your system has it present:

```
package_version=$(curl -SL https://github.com/NHSDigital/mesh-client-aws-serverless/releases/latest | grep -Po 'Release v\K(\d+.\d+.\d+)' | head -n1)
```

Or you can set a specific version:

```
package_version="0.0.1"
```

Alternatively the main page of this repo will display the latest version i.e. 0.2.3, and previous versions can be searched, which you can substitute in place of `${package_version}` in the below commands.

### PIP

```
pip install https://github.com/NHSDigital/mesh-client-aws-serverless/releases/download/v${package_version}/mesh_client_aws_serverless-${package_version}-py3-none-any.whl
```

### requirements.txt

```
https://github.com/NHSDigital/mesh-client-aws-serverless/releases/download/v${package_version}/mesh_client_aws_serverless-${package_version}-py3-none-any.whl
```

### Poetry

```
poetry add https://github.com/NHSDigital/mesh-client-aws-serverless/releases/download/v${package_version}/mesh_client_aws_serverless-${package_version}-py3-none-any.whl
```

## Usage

# Mesh Lambdas

A terraform module to provide AWS infrastructure capable of sending and recieving Mesh messages

## Configuration

Example configuration required to use this module:

find the release you want from https://github.com/NHSDigital/terraform-aws-mesh-client/releases and substitute in the module version below ... e.g. ref=v0.2.1

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

Release versions will be pushed to Github as git tags, with the format `v<major>.<minor>.<patch>` such as `v0.0.1`

## Tagging

We do not tag any resources created by this module, to configure tags across all supported resources, use the provider level default tags

Below is an example passing in Spines prefferred tags:

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



