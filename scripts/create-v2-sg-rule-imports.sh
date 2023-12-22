#!/usr/bin/env bash

set -euxo pipefail

name_prefix="${1-}"
mesh_env="${2-}"


function usage() {
  echo "
please supply the module name_prefix and mesh_env, (production|integration)
usage ./create-v2-sg-rule-imports.sh {name_prefix} [production|integration]
"
}

if [[ -z "${name_prefix}" ]]; then
  usage
  exit 1
fi

if [[ "${mesh_env}" != "production" && "${mesh_env}" != "integration" ]]; then
  usage
  exit 1
fi

sg_check_send="${name_prefix}-mesh-check-send-parameters"
sg_fetch_chunk="${name_prefix}-mesh-fetch-message-chunk"
sg_poll_mailbox="${name_prefix}-mesh-poll-mailbox"
sg_send_chunk="${name_prefix}-mesh-send-message-chunk"


sg_check_send_id="$(aws ec2 describe-security-groups --group-names="${sg_check_send}" --query=SecurityGroups[0].GroupId --output text)"
sg_fetch_chunk_id="$(aws ec2 describe-security-groups --group-names="${sg_fetch_chunk}" --query=SecurityGroups[0].GroupId --output text)"
sg_poll_mailbox_id="$(aws ec2 describe-security-groups --group-names="${sg_poll_mailbox}" --query=SecurityGroups[0].GroupId --output text)"
sg_send_chunk_id="$(aws ec2 describe-security-groups --group-names="${sg_send_chunk}" --query=SecurityGroups[0].GroupId --output text)"

echo "
found sg ids:
${sg_check_send}: ${sg_check_send_id}
${sg_fetch_chunk}: ${sg_fetch_chunk_id}
${sg_poll_mailbox}: ${sg_poll_mailbox_id}
${sg_send_chunk}: ${sg_send_chunk_id}
"

if [[ -z "${sg_check_send_id}" || -z "${sg_fetch_chunk_id}" || -z "${sg_poll_mailbox_id}" || -z "${sg_send_chunk_id}" ]]; then
  echo "sg not found"
  exit 1
fi

if [[ "${sg_check_send_id}" == "None" || "${sg_fetch_chunk_id}" == "None" || "${sg_poll_mailbox_id}" == "None" || "${sg_send_chunk_id}" == "None" ]]; then
  echo "sg not found"
  exit 1
fi

s3_prefix_list_id=$(aws ec2 describe-prefix-lists --filters=Name=prefix-list-name,Values=com.amazonaws.eu-west-2.s3 --query=PrefixLists[0].PrefixListId --output text)

if [[ -z "${s3_prefix_list_id}" || "${s3_prefix_list_id}" == "None" ]]; then
  echo "s3 prefix list id not found"
  exit 1
fi


int_mesh_cidrs="3.11.177.31/32_35.177.15.89/32_3.11.199.83/32_35.178.64.126/32_18.132.113.121/32_18.132.31.159/32"
prod_mesh_cidrs="18.132.56.40/32_3.11.193.200/32_35.176.248.137/32_3.10.194.216/32_35.176.231.190/32_35.179.50.16/32"
mesh_cidrs="${prod_mesh_cidrs}"
if [[ "${mesh_env}" == "integration" ]]; then
  mesh_cidrs="${int_mesh_cidrs}"
fi


ssm_sg_id="$(aws ec2 describe-vpc-endpoints --filters=Name=service-name,Values=com.amazonaws.eu-west-2.ssm --query=VpcEndpoints[0].Groups[0].GroupId --output text)"
sfn_sg_id="$(aws ec2 describe-vpc-endpoints --filters=Name=service-name,Values=com.amazonaws.eu-west-2.states --query=VpcEndpoints[0].Groups[0].GroupId --output text)"
logs_sg_id="$(aws ec2 describe-vpc-endpoints --filters=Name=service-name,Values=com.amazonaws.eu-west-2.logs --query=VpcEndpoints[0].Groups[0].GroupId --output text)"
kms_sg_id="$(aws ec2 describe-vpc-endpoints --filters=Name=service-name,Values=com.amazonaws.eu-west-2.kms --query=VpcEndpoints[0].Groups[0].GroupId --output text)"
lambda_sg_id="$(aws ec2 describe-vpc-endpoints --filters=Name=service-name,Values=com.amazonaws.eu-west-2.lambda --query=VpcEndpoints[0].Groups[0].GroupId --output text)"
secrets_sg_id="$(aws ec2 describe-vpc-endpoints --filters=Name=service-name,Values=com.amazonaws.eu-west-2.secretsmanager --query=VpcEndpoints[0].Groups[0].GroupId --output text)"




echo "

terraform import 'module.mesh.aws_security_group_rule.check_send_mesh' '${sg_check_send_id}_egress_tcp_443_443_${mesh_cidrs}'
terraform import 'module.mesh.aws_security_group_rule.fetch_message_mesh' '${sg_fetch_chunk_id}_egress_tcp_443_443_${mesh_cidrs}'
terraform import 'module.mesh.aws_security_group_rule.poll_mailbox_mesh' '${sg_poll_mailbox_id}_egress_tcp_443_443_${mesh_cidrs}'
terraform import 'module.mesh.aws_security_group_rule.send_message_mesh' '${sg_send_chunk_id}_egress_tcp_443_443_${mesh_cidrs}'

terraform import 'module.mesh.aws_security_group_rule.check_send_s3' '${sg_check_send_id}_egress_tcp_443_443_${s3_prefix_list_id}'
terraform import 'module.mesh.aws_security_group_rule.fetch_message_s3' '${sg_fetch_chunk_id}_egress_tcp_443_443_${s3_prefix_list_id}'
terraform import 'module.mesh.aws_security_group_rule.poll_mailbox_s3' '${sg_poll_mailbox_id}_egress_tcp_443_443_${s3_prefix_list_id}'
terraform import 'module.mesh.aws_security_group_rule.send_message_s3' '${sg_send_chunk_id}_egress_tcp_443_443_${s3_prefix_list_id}'

terraform import 'module.mesh.aws_security_group_rule.check_send_endpoints[\"${ssm_sg_id}\"]' '${sg_check_send_id}_egress_tcp_443_443_${ssm_sg_id}'
terraform import 'module.mesh.aws_security_group_rule.fetch_message_endpoints[\"${ssm_sg_id}\"]' '${sg_fetch_chunk_id}_egress_tcp_443_443_${ssm_sg_id}'
terraform import 'module.mesh.aws_security_group_rule.poll_mailbox_endpoints[\"${ssm_sg_id}\"]' '${sg_poll_mailbox_id}_egress_tcp_443_443_${ssm_sg_id}'
terraform import 'module.mesh.aws_security_group_rule.send_message_endpoints[\"${ssm_sg_id}\"]' '${sg_send_chunk_id}_egress_tcp_443_443_${ssm_sg_id}'

terraform import 'module.mesh.aws_security_group_rule.check_send_endpoints[\"${sfn_sg_id}\"]' '${sg_check_send_id}_egress_tcp_443_443_${sfn_sg_id}'
terraform import 'module.mesh.aws_security_group_rule.fetch_message_endpoints[\"${sfn_sg_id}\"]' '${sg_fetch_chunk_id}_egress_tcp_443_443_${sfn_sg_id}'
terraform import 'module.mesh.aws_security_group_rule.poll_mailbox_endpoints[\"${sfn_sg_id}\"]' '${sg_poll_mailbox_id}_egress_tcp_443_443_${sfn_sg_id}'
terraform import 'module.mesh.aws_security_group_rule.send_message_endpoints[\"${sfn_sg_id}\"]' '${sg_send_chunk_id}_egress_tcp_443_443_${sfn_sg_id}'

terraform import 'module.mesh.aws_security_group_rule.check_send_endpoints[\"${logs_sg_id}\"]' '${sg_check_send_id}_egress_tcp_443_443_${logs_sg_id}'
terraform import 'module.mesh.aws_security_group_rule.fetch_message_endpoints[\"${logs_sg_id}\"]' '${sg_fetch_chunk_id}_egress_tcp_443_443_${logs_sg_id}'
terraform import 'module.mesh.aws_security_group_rule.poll_mailbox_endpoints[\"${logs_sg_id}\"]' '${sg_poll_mailbox_id}_egress_tcp_443_443_${logs_sg_id}'
terraform import 'module.mesh.aws_security_group_rule.send_message_endpoints[\"${logs_sg_id}\"]' '${sg_send_chunk_id}_egress_tcp_443_443_${logs_sg_id}'

terraform import 'module.mesh.aws_security_group_rule.check_send_endpoints[\"${kms_sg_id}\"]' '${sg_check_send_id}_egress_tcp_443_443_${kms_sg_id}'
terraform import 'module.mesh.aws_security_group_rule.fetch_message_endpoints[\"${kms_sg_id}\"]' '${sg_fetch_chunk_id}_egress_tcp_443_443_${kms_sg_id}'
terraform import 'module.mesh.aws_security_group_rule.poll_mailbox_endpoints[\"${kms_sg_id}\"]' '${sg_poll_mailbox_id}_egress_tcp_443_443_${kms_sg_id}'
terraform import 'module.mesh.aws_security_group_rule.send_message_endpoints[\"${kms_sg_id}\"]' '${sg_send_chunk_id}_egress_tcp_443_443_${kms_sg_id}'

terraform import 'module.mesh.aws_security_group_rule.check_send_endpoints[\"${lambda_sg_id}\"]' '${sg_check_send_id}_egress_tcp_443_443_${lambda_sg_id}'
terraform import 'module.mesh.aws_security_group_rule.fetch_message_endpoints[\"${lambda_sg_id}\"]' '${sg_fetch_chunk_id}_egress_tcp_443_443_${lambda_sg_id}'
terraform import 'module.mesh.aws_security_group_rule.poll_mailbox_endpoints[\"${lambda_sg_id}\"]' '${sg_poll_mailbox_id}_egress_tcp_443_443_${lambda_sg_id}'
terraform import 'module.mesh.aws_security_group_rule.send_message_endpoints[\"${lambda_sg_id}\"]' '${sg_send_chunk_id}_egress_tcp_443_443_${lambda_sg_id}'

terraform import 'module.mesh.aws_security_group_rule.check_send_endpoints[\"${secrets_sg_id}\"]' '${sg_check_send_id}_egress_tcp_443_443_${secrets_sg_id}'
terraform import 'module.mesh.aws_security_group_rule.fetch_message_endpoints[\"${secrets_sg_id}\"]' '${sg_fetch_chunk_id}_egress_tcp_443_443_${secrets_sg_id}'
terraform import 'module.mesh.aws_security_group_rule.poll_mailbox_endpoints[\"${secrets_sg_id}\"]' '${sg_poll_mailbox_id}_egress_tcp_443_443_${secrets_sg_id}'
terraform import 'module.mesh.aws_security_group_rule.send_message_endpoints[\"${secrets_sg_id}\"]' '${sg_send_chunk_id}_egress_tcp_443_443_${secrets_sg_id}'

"
