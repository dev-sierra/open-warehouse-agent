output "aws_region" {
  value = var.aws_region
}

output "vpc_id" {
  value = aws_vpc.main.id
}

output "public_subnet_id" {
  description = "Pass this to infra/ami/'s Packer build as -var subnet_id=<this>."
  value       = aws_subnet.public.id
}

output "gateway_public_ip" {
  value = aws_instance.gateway.public_ip
}

output "gateway_instance_id" {
  value = aws_instance.gateway.id
}

output "gpu_instance_id" {
  value = aws_instance.gpu.id
}
