

resource "aws_vpc" "local" {
  cidr_block = local.vpc_cidr
}

resource "aws_subnet" "private" {
  vpc_id                  = aws_vpc.local.id
  cidr_block              = cidrsubnet(aws_vpc.local.cidr_block, 4, 0)
  availability_zone       = "eu-west-2a"
  map_public_ip_on_launch = false

  tags = {
    Name = "private"
  }
}

resource "aws_vpc_endpoint" "s3" {
  service_name = "com.amazonaws.${var.region}.s3"
  vpc_id       = aws_vpc.local.id
}

resource "aws_vpc_endpoint" "ssm" {
  service_name       = "com.amazonaws.${var.region}.ssm"
  vpc_id             = aws_vpc.local.id
  security_group_ids = [aws_security_group.dummy.id]
}

resource "aws_vpc_endpoint" "lambda" {
  service_name       = "com.amazonaws.${var.region}.lambda"
  vpc_id             = aws_vpc.local.id
  security_group_ids = [aws_security_group.dummy.id]
}

resource "aws_vpc_endpoint" "sfn" {
  service_name       = "com.amazonaws.${var.region}.states"
  vpc_id             = aws_vpc.local.id
  security_group_ids = [aws_security_group.dummy.id]
}

resource "aws_vpc_endpoint" "logs" {
  service_name       = "com.amazonaws.${var.region}.logs"
  vpc_id             = aws_vpc.local.id
  security_group_ids = [aws_security_group.dummy.id]
}

resource "aws_vpc_endpoint" "kms" {
  service_name       = "com.amazonaws.${var.region}.kms"
  vpc_id             = aws_vpc.local.id
  security_group_ids = [aws_security_group.dummy.id]
}

resource "aws_vpc_endpoint" "secrets" {
  service_name       = "com.amazonaws.${var.region}.secretsmanager"
  vpc_id             = aws_vpc.local.id
  security_group_ids = [aws_security_group.dummy.id]
}


resource "aws_security_group" "dummy" {
  name   = "dummy"
  vpc_id = aws_vpc.local.id
}