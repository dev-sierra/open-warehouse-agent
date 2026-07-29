packer {
  required_plugins {
    amazon = {
      source  = "github.com/hashicorp/amazon"
      version = "~> 1.3"
    }
  }
}

variable "aws_region" {
  type    = string
  default = "us-west-1"
}

variable "subnet_id" {
  type        = string
  description = "Public subnet to build in -- needs internet access for the bake. Use the Terraform output: terraform -chdir=../terraform output -raw public_subnet_id"
}

variable "builder_instance_type" {
  type        = string
  default     = "g4dn.xlarge"
  description = "Needs a real GPU present so the driver/vLLM install can actually be verified, not just cross-compiled."
}
