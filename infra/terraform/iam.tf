data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

# --- Gateway instance role: least-privilege start/stop/describe of the GPU
# instance only, plus read access to its own bearer token, plus SSM for
# management access (no SSH). ---

resource "aws_iam_role" "gateway" {
  name               = "owa-gateway"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
}

data "aws_iam_policy_document" "gateway_gpu_lifecycle" {
  # DescribeInstances doesn't support resource-level restriction in IAM, so
  # it's split into its own statement scoped to "*"; StartInstances and
  # StopInstances do support it and are scoped to just the GPU instance.
  statement {
    sid       = "DescribeInstances"
    actions   = ["ec2:DescribeInstances"]
    resources = ["*"]
  }

  statement {
    sid       = "StartStopGPU"
    actions   = ["ec2:StartInstances", "ec2:StopInstances"]
    resources = ["arn:aws:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:instance/${aws_instance.gpu.id}"]
  }

  statement {
    sid       = "ReadGatewayToken"
    actions   = ["ssm:GetParameter"]
    resources = [aws_ssm_parameter.gateway_token.arn]
  }
}

resource "aws_iam_role_policy" "gateway_gpu_lifecycle" {
  name   = "gpu-lifecycle"
  role   = aws_iam_role.gateway.id
  policy = data.aws_iam_policy_document.gateway_gpu_lifecycle.json
}

resource "aws_iam_role_policy_attachment" "gateway_ssm" {
  role       = aws_iam_role.gateway.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "gateway" {
  name = "owa-gateway"
  role = aws_iam_role.gateway.name
}

# --- GPU instance role: SSM management access only. ---

resource "aws_iam_role" "gpu" {
  name               = "owa-gpu"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
}

resource "aws_iam_role_policy_attachment" "gpu_ssm" {
  role       = aws_iam_role.gpu.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "gpu" {
  name = "owa-gpu"
  role = aws_iam_role.gpu.name
}
