variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-west-1"
}

variable "gpu_instance_type" {
  description = "Instance type for the GPU box running vLLM. Stopped by default; only billed while running."
  type        = string
  default     = "g4dn.xlarge"
}

variable "gateway_instance_type" {
  description = "Instance type for the always-on gateway VM. Kept tiny (ARM) to match the project's ~$3/mo idle-gateway cost target."
  type        = string
  default     = "t4g.nano"
}

variable "gateway_ingress_cidr" {
  description = "CIDR allowed to reach the gateway's app port (e.g. \"203.0.113.4/32\" for your own IP). No default on purpose -- must be set explicitly in terraform.tfvars so the gateway is never silently left open to the world."
  type        = string
}

variable "gateway_port" {
  description = "Port the gateway's OpenAI-compatible API listens on."
  type        = number
  default     = 8000
}

variable "vllm_port" {
  description = "Port vLLM's OpenAI-compatible API listens on, on the GPU box."
  type        = number
  default     = 8000
}

variable "alert_email" {
  description = "Email address for the AWS Budgets alert."
  type        = string
  default     = "lukeodair398@gmail.com"
}

variable "monthly_budget_usd" {
  description = "Monthly budget threshold in USD that triggers an alert."
  type        = number
  default     = 20
}

variable "gpu_ami_id" {
  description = "AMI ID for the GPU instance. Leave null to launch a stock Ubuntu AMI until the Packer bake (infra/ami/) produces a real vLLM+weights image; set it to that image's ID afterwards."
  type        = string
  default     = null
}

variable "gpu_root_volume_gb" {
  description = "Root EBS volume size (GB) for the GPU instance -- needs to fit the model weights plus the vLLM/Python environment."
  type        = number
  default     = 100
}
