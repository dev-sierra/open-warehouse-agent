resource "aws_security_group" "gateway" {
  name        = "owa-gateway"
  description = "Gateway: inbound from the operator CLI on the app port only; outbound anywhere (AWS API calls, proxying to the GPU box, SSM)."
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "OpenAI-compatible API, from the operator only"
    from_port   = var.gateway_port
    to_port     = var.gateway_port
    protocol    = "tcp"
    cidr_blocks = [var.gateway_ingress_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "owa-gateway"
  }
}

# No SSH ingress on either security group -- both instances are managed via
# SSM Session Manager instead (see iam.tf), matching the README's "no public
# ingress on the GPU box" stance and tightening the gateway's surface too.

# No egress block is declared here on purpose: the AWS provider removes the
# account's default "allow all" egress rule for any security group that
# declares inline ingress/egress blocks, so omitting egress entirely leaves
# the GPU box with zero possible *outbound*-initiated connections. Security
# groups are stateful, so it can still reply to the gateway's inbound vLLM
# requests -- it just can never open a new connection out.
resource "aws_security_group" "gpu" {
  name        = "owa-gpu"
  description = "GPU box: inbound only from the gateway security group; no public ingress; no outbound egress needed in steady state."
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "vLLM OpenAI-compatible API, from the gateway only"
    from_port       = var.vllm_port
    to_port         = var.vllm_port
    protocol        = "tcp"
    security_groups = [aws_security_group.gateway.id]
  }

  tags = {
    Name = "owa-gpu"
  }
}
