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

```terraform
module "mesh" {
  source = "git::https://github.com/nhsdigital/terraform-aws-mesh-client.git//module?ref=<version>"

  name_prefix = "${var.env}-example-project"
  mesh_env    = "production"  # local/production/integration
  vpc_id      = aws_vpc.my_vpc.id
  subnet_ids  = aws_subnet.private.*.id
  
  mailbox_ids = ["X26ABC123", "X26ABC456"]  # your mesh mailbox id(s)
  verify_ssl  = true  # set false for local

  get_message_max_concurrency = 10 

  compress_threshold = 1 * 1024 * 1024

  # vpc endpoints are required if deploying the module into a VPC
  aws_s3_endpoint_prefix_list_id = aws_vpc_endpoint.s3.prefix_list_id
  aws_ssm_endpoint_sg_id         = tolist(aws_vpc_endpoint.ssm.security_group_ids)[0]
  aws_sfn_endpoint_sg_id         = tolist(aws_vpc_endpoint.sfn.security_group_ids)[0]
  aws_logs_endpoints_sg_id       = tolist(aws_vpc_endpoint.logs.security_group_ids)[0]
  aws_kms_endpoints_sg_id        = tolist(aws_vpc_endpoint.kms.security_group_ids)[0]
  aws_lambda_endpoints_sg_id     = tolist(aws_vpc_endpoint.lambda.security_group_ids)[0]
  aws_secrets_endpoints_sg_id    = tolist(aws_vpc_endpoint.secrets.security_group_ids)[0]
  
  # region = "eu-west-2"
  # verify_checks_common_name = false 
  # cloudtrail_enabled = false  # (set false for localstack) 
  # use_secrets_manager = true  # use secrets manager for storage of keys or passowrds rather than SSM
  # use_sender_filename = true  # allow the sender to define the filename to store in your s3 bucket ( not recommeded )
  # use_legacy_inbound_location = true # support for v1 outbound mapping of send parameters via SSM
  # chunk_size = number # size of chunks to send to MESH ( advanced tuning ), leave as default if you don't need to tune
  # crumb_size = number # size of buffer reading from s3 or from MESH (very advanced tuning), leave as default if you don't need to tune  
  # never_compress = true  # disable all outbound compression, regardless of `mex-content-compress` instruction or `compress_threshold`
  
}
```

Release versions will be pushed to [releases](https://github.com/NHSDigital/terraform-aws-mesh-client/releases) as git tags, with the format `v<major>.<minor>.<patch>` such as `v1.0.1`

### Advanced Configuration
The module has many configuration options, rather than duplicate descriptions here, please see [variables.tf](module/variables.tf)

# Send File

Send a file by doing a 'put_object', Cloudtrail and cloudwatch event triggers will detect any file put into the bucket in the `outbound/*` location and send to MESH.
Details:
* MESH `mex-*` headers will be honoured and passed the [MESH Client](https://github.com/NHSDigital/mesh-client), where appropriate
* metadata will be inspected first for a `mex-from` (sender mailbox id), metadata parameter, if present this and other metadata will be used, if `mex-from` is not found, we will fall-back to using the outbound mappings as the source for `mex-from`, `mex-to` and `mex-workflowid`
* S3 object metadata supports a limited character set, and size; Metadata values should be encoded with the equivalent of [urllib.parse.quote_plus](https://docs.python.org/3/library/urllib.parse.html), e.g.  `s3_client.put_object(..., Metadata={"mex-subject": quote_plus(subject),..)` ... before sending to MESH the inverse `unquote_plus` will be applied.
* `mex-` metadata keys are case-insensitive, keys will be converted to lower case before comparison or sending to MESH.
* using s3 object metadata allows the configuration of many more mesh parameters, including but not limited to:
    * `mex-from` sender MESH mailbox id (your mailbox)
    * `mex-to` recipient MESH mailbox id (recipient mailbox)
    * `mex-workflowid` MESH workflow id
    * `mex-subject` (optional) 'free text' subject area,
    * `mex-localid` (optional) sender supplied unique identifier
    * `mex-filename` (optional) passthrough file name passed to recipient, if not set MESH will set a default file name of `{message_id}.dat`
    * `mex-content-compress` (optional) explicit instruction to compress the content before sending to MESH, this will override exclusions based on `mex-content-compressed` and `content-encoding`
    * `mex-content-compressed` (optional) passthrough indication this file is already compressed, if set the send application will never auto-compress, regardless of the file size and `compress_threshold` configured
    * `mex-content-encrypted` (optional) passthrough indicator to signify that the file has been encrypted (MESH does nothing with this)

## Example Send File
```python
from urllib.parse import quote_plus
from uuid import uuid4

import boto3

sender = "X26MYMAILBOXID"
recipient = "X26RECIPIENT"
my_id = uuid4().hex
bucket = "..."  # mesh outbound bucket
key = f"outbound/{sender}/{my_id}.json"
metadata = {
  "mex-From": sender,
  "mex-To": recipient,
  "mex-WorkflowId": "PATHOLOGY_RESULT",
  "mex-Subject": "my super subject $£% etc",
  "mex-LocalId": my_id,
}
metadata = {k: quote_plus(v) for k, v in metadata.items()}  # don't forget to escape metadata values

boto3.client("s3").put_object(
  Bucket=bucket, Key=key, ContentType="application/json", Metadata=metadata
)

```


# Receive File

By default, received files will be stored in the MESH s3 bucket in the pattern  `inbound/{recipient_mailbox_id}/{message_id}.dat` (or `inbound/{recipient_mailbox_id}/{message_id}.ctl` for reports). 
- It is possible to override this behaviour to support legacy usage and some customisation, though it's recommended to go with the defaults.
- MESH headers will be honoured and stored on the [S3 object metadata](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingMetadata.html):
- It's recommended to configure a Cloudwatch event trigger to monitor for new mesh messages and perform the appropriate action:

## Example terraform configuration

```terraform
resource "aws_cloudwatch_event_rule" "new_mesh_message" {
  name        = "${var.environment}-new-mesh-message"
  description = "new mesh message received"
  event_pattern = jsonencode({
    source = [
      "aws.s3"
    ]
    detail = {
      eventSource = [
        "s3.amazonaws.com"
      ]
      eventName = [
        "PutObject",
        "CompleteMultipartUpload"
      ]
      requestParameters = {
        bucketName = [
          module.mesh.mesh_s3_bucket_name
        ]
        key = [
          {
            prefix = "inbound/"
          }
        ]
      }
    }
  })
}

resource "aws_cloudwatch_event_target" "new_mesh_message" {
  rule      = aws_cloudwatch_event_rule.new_mesh_message.name
  target_id = "NewMessage"
  arn       = aws_lambda_function.new_mesh_message.arn
  role_arn  = "..."
}

resource "aws_lambda_function" "new_mesh_message" {
  function_name = "${var.environment}-new-mesh-message"
  handler       = "new_mesh_message.handler"
  role          = "..."
}
```
## Example new mesh message lambda function code: 
```python
import json
import logging
from typing import Any
from urllib.parse import unquote_plus

import boto3

s3 = boto3.resource("s3")

def on_new_message(_sender: str, _workflow_id: str, _payload: dict[str, Any]):
    raise NotImplementedError


def handler(event: dict[str, Any], _context=None):
    s3_bucket = event["detail"]["requestParameters"]["bucketName"]
    s3_key = event["detail"]["requestParameters"]["key"]

    new_message = s3.Object(bucket_name=s3_bucket, key=s3_key)
    
    mesh_metadata = {
        k.lower(): unquote_plus(v)
        for k, v in new_message.metadata
        if k.lower().startswith("mex-")
    }

    message_id = mesh_metadata["mex-messageid"]
    sender = mesh_metadata["mex-from"]
    recipient = mesh_metadata["mex-from"]
    workflow_id = mesh_metadata.get("mex-workflowid")
    message_type = mesh_metadata.get("mex-messagetype")
    
    logging.info(f"new mesh message: message_id={message_id} sender={sender} recipient={recipient} workflow_id={workflow_id} message_type={message_type}")
    
    if message_type == "REPORT":
        # todo: store report info, do I need to notify / report on failures?
        return 
    
    response = new_message.get()
    payload = json.loads(response["Body"].read())
    on_new_message(sender, workflow_id, payload)

```


