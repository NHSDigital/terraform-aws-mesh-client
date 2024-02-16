output "send_message_sg_id" {
  value = local.vpc_enabled ? aws_security_group.send_message_chunk.0.id : ""
}

output "get_messages_sg_id" {
  value = local.vpc_enabled ? aws_security_group.fetch_message_chunk.0.id : ""
}

output "poll_mailbox_sg_id" {
  value = local.vpc_enabled ? aws_security_group.poll_mailbox.0.id : ""
}

output "mesh_s3_bucket_name" {
  value = aws_s3_bucket.mesh.bucket
}

output "mesh_s3_logs_bucket_name" {
  value = aws_s3_bucket.s3logs.bucket
}

output "mesh_kms_key_arn" {
  value = aws_kms_key.mesh.arn
}

output "step_function_get_messages_arn" {
  value = aws_sfn_state_machine.get_messages.arn
}

output "step_function_send_messages_arn" {
  value = aws_sfn_state_machine.send_message.arn
}

output "lambda_check_send_parameters_log_group_name" {
  value = aws_cloudwatch_log_group.check_send_parameters.name
}

output "lambda_fetch_message_chunk_log_group_name" {
  value = aws_cloudwatch_log_group.fetch_message_chunk.name
}

output "lambda_poll_mailbox_log_group_name" {
  value = aws_cloudwatch_log_group.poll_mailbox.name
}

output "lambda_send_message_chunk_log_group_name" {
  value = aws_cloudwatch_log_group.send_message_chunk.name
}

output "stepfunction_get_messages_log_group_name" {
  value = aws_cloudwatch_log_group.get_messages.name
}

output "stepfunction_send_messages_log_group_name" {
  value = aws_cloudwatch_log_group.send_messages.name
}
