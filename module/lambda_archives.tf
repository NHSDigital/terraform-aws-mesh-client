
locals {
  python_dir = "${local.abs_path}/../src"
}

resource "null_resource" "mesh_aws_client_dependencies" {
  triggers = {
    requirements = filesha256("${local.python_dir}/requirements.txt")
    build_script = filesha256("${path.module}/pack-deps.sh")
    exists       = fileexists("${path.module}/dist/deps/python/mesh_client/__init__.py") ? "0" : timestamp()

  }
  provisioner "local-exec" {
    command = "/bin/bash ${path.module}/pack-deps.sh ${local.abs_path}"
  }
}

data "archive_file" "deps" {
  type        = "zip"
  source_dir  = "${local.abs_path}/dist/deps"
  output_path = "${local.abs_path}/dist/deps.zip"

  depends_on = [
    null_resource.mesh_aws_client_dependencies
  ]
}

resource "aws_lambda_layer_version" "mesh_aws_client_dependencies" {
  filename            = data.archive_file.deps.output_path
  layer_name          = "mesh_aws_client_dependencies"
  source_code_hash    = data.archive_file.deps.output_base64sha256
  compatible_runtimes = [local.python_runtime]
}


resource "null_resource" "mesh_aws_client" {
  triggers = {
    source_dir   = sha256(join("", [for f in fileset(local.python_dir, "*") : filesha256("${local.python_dir}/${f}")]))
    build_script = filesha256("${local.abs_path}/pack-app.sh")
    exists       = fileexists("${path.module}/dist/app/py.typed") ? "0" : timestamp()
  }
  provisioner "local-exec" {
    command = "/bin/bash ${local.abs_path}/pack-app.sh ${local.abs_path} ${var.mesh_env}"
  }
  depends_on = [
    null_resource.mesh_aws_client_dependencies
  ]
}

data "archive_file" "app" {
  type        = "zip"
  source_dir  = "${local.abs_path}/dist/app"
  output_path = "${local.abs_path}/dist/app.zip"

  depends_on = [
    null_resource.mesh_aws_client,
    null_resource.mesh_aws_client_dependencies
  ]
}