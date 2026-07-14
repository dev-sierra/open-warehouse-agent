.PHONY: demo-local up demo-cloud down test lint

demo-local:
	uv run python -m data.seed_duckdb
	@echo "Starting MCP server over stdio (Ctrl+C to stop)."
	@echo "TODO: replace this with the CLI agent loop once Phase 2 lands (agent/)."
	uv run python -m mcp_server

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