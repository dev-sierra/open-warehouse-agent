# open-warehouse-agent

Natural-language analytics over your cloud data warehouse (Snowflake, Databricks, DuckDB), answered by an open-weight model that runs on GPUs you control — spun up on demand, costing ~$0 when idle.

Full build plan: see `project-plan-warehouse-agent.md` in [personal/learning plan](../learning%20plan/project-plan-warehouse-agent.md) (Phase 0 design doc — problem statement, architecture, threat model, cost model — goes here once written).

## Status

Scaffolding only. No code yet.

## Repo layout

```
connector/             Connector protocol + snowflake / databricks / duckdb adapters
mcp_server/             FastMCP server exposing the connector tools
agent/                  CLI chat host: tool-calling loop, OpenAI-compatible client
gateway/                Lifecycle controller + OpenAI-compatible proxy (FastAPI)
infra/terraform/        VPC, gateway instance, GPU instance, IAM, SGs, EventBridge, budget alarm
infra/ami/              AMI bake (vLLM + model weights)
data/                   Synthetic finance data generator + per-backend seed scripts
tests/                  SELECT-only guards, adapter contract tests, gateway state machine
```
