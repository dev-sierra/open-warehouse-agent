# Bakes vLLM + the Qwen2.5-7B-Instruct weights onto a disk image, so the
# runtime GPU instance (infra/terraform/gpu.tf) never needs internet access
# to serve requests -- everything it needs is already on disk. Built from
# AWS's Deep Learning Base AMI (NVIDIA drivers pre-installed) rather than a
# stock Ubuntu image plus hand-rolled CUDA driver install, to avoid
# driver/CUDA version-matching problems.
#
# This is a one-off, explicitly-run build -- NOT part of `terraform apply`.
# Running `packer build` here spins up a temporary g4dn.xlarge instance for
# the duration of the bake (real GPU billing, ~$0.53/hr, for maybe 15-30
# minutes) and needs the Terraform-created public subnet to already exist.

source "amazon-ebs" "vllm_qwen" {
  region        = var.aws_region
  instance_type = var.builder_instance_type
  subnet_id     = var.subnet_id
  ssh_username  = "ubuntu"

  source_ami_filter {
    filters = {
      name                = "Deep Learning Base OSS Nvidia Driver GPU AMI (Ubuntu 22.04)*"
      root-device-type    = "ebs"
      virtualization-type = "hvm"
    }
    most_recent = true
    owners      = ["amazon"]
  }

  ami_name        = "owa-vllm-qwen-{{timestamp}}"
  ami_description = "vLLM + Qwen2.5-7B-Instruct weights pre-baked, for the open-warehouse-agent GPU box"

  launch_block_device_mappings {
    device_name           = "/dev/sda1"
    volume_size           = 100
    volume_type           = "gp3"
    delete_on_termination = true
  }

  tags = {
    Name = "owa-vllm-qwen"
  }
}

build {
  sources = ["source.amazon-ebs.vllm_qwen"]

  provisioner "shell" {
    script = "scripts/install.sh"
  }
}
