.PHONY: demo-local gateway up demo-cloud down test lint

demo-local:
	uv run python -m data.seed_duckdb
	uv run python -m agent

gateway:
	uv run python -m gateway

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