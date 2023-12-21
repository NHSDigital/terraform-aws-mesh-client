output "lambas_sg_id" {
  value = local.vpc_enabled ? aws_security_group.lambdas.0.id : ""
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


