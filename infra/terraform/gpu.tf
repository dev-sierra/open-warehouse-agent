# The GPU box. Stopped by default is the *steady-state* posture -- Terraform
# itself has no "launch but stay stopped" option, so this comes up running
# on first apply. See the plan's runbook: stop it manually right after
# validating, or let the nightly EventBridge backstop (idle_backstop.tf)
# catch it. There's no live idle-reaper wired to this instance yet -- that's
# gateway/ec2_backend.py, a deferred stage.

data "aws_ami" "gpu_base" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

resource "aws_instance" "gpu" {
  # Falls back to a stock Ubuntu AMI until the Packer bake (infra/ami/)
  # produces a real vLLM+weights image; set var.gpu_ami_id afterwards.
  ami                    = coalesce(var.gpu_ami_id, data.aws_ami.gpu_base.id)
  instance_type          = var.gpu_instance_type
  subnet_id              = aws_subnet.private.id
  vpc_security_group_ids = [aws_security_group.gpu.id]
  iam_instance_profile   = aws_iam_instance_profile.gpu.name

  root_block_device {
    volume_type = "gp3"
    volume_size = var.gpu_root_volume_gb
  }

  tags = {
    Name = "owa-gpu"
  }
}
