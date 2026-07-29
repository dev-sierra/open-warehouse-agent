# The always-on gateway VM. Sized to an ARM (Graviton) nano instance to
# match the README's ~$3/mo idle-gateway cost claim; our FastAPI/uvicorn/
# httpx stack all ship arm64 wheels, so this isn't a compatibility risk.

data "aws_ami" "gateway_base" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-arm64-server-*"]
  }
}

locals {
  # Prepares the box (base deps + a checkout of the repo) but deliberately
  # does not start `python -m gateway` -- there's no real vLLM backend for
  # it to point at yet without gateway/ec2_backend.py (a later stage).
  # Deploying/running the app here is next-stage work, alongside that.
  gateway_user_data = <<-EOF
    #!/bin/bash
    set -euo pipefail
    apt-get update
    apt-get install -y python3-pip git
    curl -LsSf https://astral.sh/uv/install.sh | sh
    git clone https://github.com/dev-sierra/open-warehouse-agent.git /opt/open-warehouse-agent
  EOF
}

resource "aws_instance" "gateway" {
  ami                         = data.aws_ami.gateway_base.id
  instance_type               = var.gateway_instance_type
  subnet_id                   = aws_subnet.public.id
  vpc_security_group_ids      = [aws_security_group.gateway.id]
  iam_instance_profile        = aws_iam_instance_profile.gateway.name
  associate_public_ip_address = true
  user_data                   = local.gateway_user_data

  tags = {
    Name = "owa-gateway"
  }
}
