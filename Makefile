.PHONY: demo-local gateway gateway-aws-start gateway-aws-stop gateway-aws-status up demo-cloud down test lint

demo-local:
	uv run python -m data.seed_duckdb
	uv run python -m agent

gateway:
	uv run python -m gateway

# Stop/start the *deployed* AWS gateway instance (not the local dev server
# above) -- a plain EC2 stop/start, so its disk is untouched and you're only
# paying a little EBS storage while it's off. Needs `terraform apply` to
# have already run in infra/terraform.
gateway-aws-start:
	aws ec2 start-instances \
		--region "$$(terraform -chdir=infra/terraform output -raw aws_region)" \
		--instance-ids "$$(terraform -chdir=infra/terraform output -raw gateway_instance_id)"

gateway-aws-stop:
	aws ec2 stop-instances \
		--region "$$(terraform -chdir=infra/terraform output -raw aws_region)" \
		--instance-ids "$$(terraform -chdir=infra/terraform output -raw gateway_instance_id)"

gateway-aws-status:
	aws ec2 describe-instances \
		--region "$$(terraform -chdir=infra/terraform output -raw aws_region)" \
		--instance-ids "$$(terraform -chdir=infra/terraform output -raw gateway_instance_id)" \
		--query "Reservations[0].Instances[0].State.Name" --output text

test:
	uv run pytest -v

lint:
	uv run ruff check .

up:
	@echo "TODO: terraform apply (Phase 3)"

demo-cloud:
	@echo "TODO: cold-start GPU demo (Phase 3)"

down:
	@echo "TODO: terraform destroy / stop GPU (Phase 3)"