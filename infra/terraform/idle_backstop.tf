# A hard nightly backstop, independent of the gateway's own (still-deferred)
# idle reaper: a small Lambda force-stops the GPU instance every night,
# regardless of activity. Per the README's threat model, this is the
# "second line of defense" against a forgotten or crashed client leaving the
# GPU running and silently burning money.

data "archive_file" "idle_backstop" {
  type        = "zip"
  output_path = "${path.module}/build/idle_backstop.zip"

  source {
    filename = "index.py"
    content  = <<-PY
      import os

      import boto3

      def handler(event, context):
          boto3.client("ec2").stop_instances(InstanceIds=[os.environ["GPU_INSTANCE_ID"]])
    PY
  }
}

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "idle_backstop" {
  name               = "owa-idle-backstop"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

data "aws_iam_policy_document" "idle_backstop_policy" {
  statement {
    sid       = "StopGPU"
    actions   = ["ec2:StopInstances"]
    resources = ["arn:aws:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:instance/${aws_instance.gpu.id}"]
  }

  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"]
  }
}

resource "aws_iam_role_policy" "idle_backstop" {
  name   = "stop-gpu"
  role   = aws_iam_role.idle_backstop.id
  policy = data.aws_iam_policy_document.idle_backstop_policy.json
}

resource "aws_lambda_function" "idle_backstop" {
  function_name    = "owa-idle-backstop"
  role             = aws_iam_role.idle_backstop.arn
  handler          = "index.handler"
  runtime          = "python3.12"
  filename         = data.archive_file.idle_backstop.output_path
  source_code_hash = data.archive_file.idle_backstop.output_base64sha256
  timeout          = 30

  environment {
    variables = {
      GPU_INSTANCE_ID = aws_instance.gpu.id
    }
  }
}

data "aws_iam_policy_document" "scheduler_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "idle_backstop_scheduler" {
  name               = "owa-idle-backstop-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume_role.json
}

resource "aws_iam_role_policy" "idle_backstop_scheduler_invoke" {
  name = "invoke-lambda"
  role = aws_iam_role.idle_backstop_scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "lambda:InvokeFunction"
        Resource = aws_lambda_function.idle_backstop.arn
      }
    ]
  })
}

resource "aws_scheduler_schedule" "idle_backstop_nightly" {
  name       = "owa-idle-backstop-nightly"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(0 3 * * ? *)"
  schedule_expression_timezone = "UTC"

  target {
    arn      = aws_lambda_function.idle_backstop.arn
    role_arn = aws_iam_role.idle_backstop_scheduler.arn
  }
}
