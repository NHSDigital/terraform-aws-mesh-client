

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
