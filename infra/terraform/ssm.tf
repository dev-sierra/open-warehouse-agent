# The gateway's bearer token (OWA_GATEWAY_TOKEN) is generated here and
# stored as a SecureString SSM parameter, rather than as a plain Terraform
# variable or embedded in user_data -- so it's never in state as plaintext,
# never typed by hand, and never appears in a shell history.

resource "random_password" "gateway_token" {
  length  = 32
  special = false
}

resource "aws_ssm_parameter" "gateway_token" {
  name  = "/owa/gateway/token"
  type  = "SecureString"
  value = random_password.gateway_token.result

  tags = {
    Name = "owa-gateway-token"
  }
}
