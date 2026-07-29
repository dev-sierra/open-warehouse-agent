data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "owa"
  }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "owa"
  }
}

# Public subnet: has a route to the internet, hosts the always-on gateway
# (which the CLI agent needs to reach) and, temporarily, the Packer AMI
# builder instance.
resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.0.0/24"
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true

  tags = {
    Name = "owa-public"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "owa-public"
  }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# Private subnet: hosts the GPU box. Deliberately left on the VPC's default
# (main) route table -- which only carries the implicit local route, no path
# to the internet -- instead of adding a NAT Gateway. The GPU box doesn't
# need outbound internet access in steady state (vLLM + the model weights
# are baked into the AMI ahead of time; it only ever talks to the gateway),
# so a NAT Gateway would just be ~$32/month spent on a capability we never
# use, blowing well past this project's ~$8/month idle-cost target.
resource "aws_subnet" "private" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = data.aws_availability_zones.available.names[0]

  tags = {
    Name = "owa-private"
  }
}
