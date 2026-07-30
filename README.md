# open-warehouse-agent

Natural-language analytics over your cloud data warehouse (Snowflake, Databricks, DuckDB), answered by an open-weight model that runs on GPUs you control — spun up on demand, costing ~$0 when idle.

## Problem statement

Asking your warehouse a question in plain English today usually means one of two things:

- **Send your schema and query context to a third-party LLM API.** Convenient, but your table names, data shapes, and query results now leave your infrastructure and pass through someone else's model.
- **Run an open-weight model on a GPU you own.** Private, but a GPU big enough to serve an LLM costs real money whether or not anyone is asking it questions — often more per month than the warehouse itself.

This project does neither. It's a small, self-hosted agent stack: a warehouse connector exposed over MCP, and an open-weight model that runs on a GPU inside *your own cloud account* — a GPU that exists only while a question is actually being answered. Prompts, schema, and query results never leave infrastructure you control, and the expensive part of the stack costs nothing while idle.

## Architecture

Four components in three locations:

```
YOUR LAPTOP                              YOUR AWS ACCOUNT
┌────────────────────────┐               ┌───────────────────────────────┐
│ ① CLI chat (agent)     │───── (B) ───▶ │ ③ Gateway — tiny, always on   │
│        │               │               │        │ starts / stops        │
│       (A)              │               │        ▼                       │
│        ▼               │               │ ④ GPU box — big, usually OFF  │
│ ② MCP server           │               │    runs Qwen 2.5 7B via vLLM  │
│    + warehouse adapters│               └───────────────────────────────┘
└────────│───────────────┘
        (C)
         ▼
  Snowflake / Databricks / DuckDB  — your warehouses
```

- **① CLI chat (agent host)** — you type English questions; it runs the agent loop (send conversation to model → execute any tool the model requests → repeat until answered).
- **② MCP server (warehouse connector)** — exposes three tools (`list_tables`, `describe_table`, `run_query`); a pluggable adapter decides which warehouse they hit; enforces read-only SQL, row limits, and an audit log of every query.
- **③ Gateway** — a tiny, always-on micro-VM. Speaks an OpenAI-compatible API, wakes the GPU on the first request, stops it after an idle timeout. Exists because something has to listen 24/7, and it must not be the expensive machine.
- **④ GPU box** — runs vLLM serving **Qwen 2.5 7B Instruct** (chosen for reliable tool-calling; swappable for a larger Qwen variant later if quality demands it). **Stopped by default** — pennies of storage cost when off, nothing else.

Arrows: **(A)** CLI → MCP server (tool execution) · **(B)** CLI → gateway → GPU (the thinking path) · **(C)** MCP server → warehouse (the data path). Every arrow stays inside infrastructure you control — that's the privacy claim. The only expensive component exists only while you're asking questions — that's the cost claim.

## Threat model / privacy story

What never leaves your own cloud account:

- **Prompts and model output.** The model runs on a GPU you own; there is no third-party model API anywhere in the data or thinking path.
- **Query results.** Warehouse data flows from the warehouse to the MCP server to the model, all inside your account/network — never to an external inference provider.
- **Warehouse credentials.** Held by the MCP server/connector layer only, never passed to or through the model.

What the system enforces at the boundaries:

- **SELECT-only SQL.** Every query is parsed (via `sqlglot`) before execution; DML/DDL is rejected outright.
- **Row limits and query timeouts** on every `run_query` call, to bound both cost and blast radius of a bad query.
- **Full audit log** of every query executed, independent of the warehouse's own query history.
- **No public ingress on the GPU box.** Its security group only accepts traffic from the gateway — vLLM is never internet-reachable.
- **Bearer-token auth** between the CLI agent and the gateway.

## Cost model

- **Idle footprint: ~$8/month.** A tiny always-on gateway VM (~$3/mo) plus EBS storage for the baked AMI and model weights (~$5/mo) — the only cost when nobody is asking questions.
- **Active cost: pay only while the GPU is running**, roughly $0.80/hr for the target instance class. A typical dev/demo month (10–20 active hours) adds roughly $8–16.
- **Hard backstops against a forgotten GPU:** an idle reaper inside the gateway, an EventBridge scheduled auto-stop as a second line of defense, and a cloud budget alert. A misconfigured or crashed client cannot leave the GPU running indefinitely and silently burn money.

## Cold-start budget

The first request after idle finds the GPU stopped. That cold start — instance boot, vLLM startup, model load — is realistically **2–4 minutes**, and the user experience during that window is the product, not an afterthought:

- The gateway returns a clear "warming up" signal (503 + `Retry-After`, or an SSE keep-alive) rather than hanging or timing out silently.
- The gateway health-polls vLLM and only starts serving once the model is actually ready.
- Reducing this window — a baked AMI with weights already on disk, quantization, faster health-check polling — is an explicit, ongoing goal of the project, not just an implementation detail to hide.

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

## Quick start

Zero-cloud-account path, DuckDB + a locally-served open-weight model via [Ollama](https://ollama.com):

```
ollama serve                        # if not already running
ollama pull qwen2.5:7b-instruct     # one-time model pull

uv sync
make demo-local   # seeds a local DuckDB warehouse, then runs the CLI chat agent
make test         # pytest: SQL-guard tests + adapter contract tests
make lint         # ruff
```

`make demo-local` seeds `data/warehouse.duckdb` and drops you into an interactive
chat prompt (`agent/cli.py`) that spawns the MCP server as a subprocess and talks
to Ollama over an OpenAI-compatible API — ask it questions about the seeded
orders/settlements data. Ctrl-D to quit.

Override `WAREHOUSE_BACKEND=snowflake` (plus `uv sync --extra snowflake` and the
`SNOWFLAKE_*` env vars — see `.env.example`) to point the MCP server at
Snowflake instead of DuckDB — see `mcp_server/backends.py`. Auth is
key-pair by default (see `infra/snowflake_bootstrap.py` for one-time
account setup); run `data/seed_snowflake.py` to seed the same synthetic
dataset.

Same idea for `WAREHOUSE_BACKEND=databricks` (`uv sync --extra databricks`,
`DATABRICKS_*` env vars). Auth is OAuth client-credentials via a scoped
service principal by default (see `infra/databricks_bootstrap.py` for
one-time catalog/schema setup); run `data/seed_databricks.py` to seed.

To try the gateway locally (`gateway/`) — the OpenAI-compatible proxy that will
eventually front the real AWS GPU box — run `make gateway` in one terminal
(needs `OWA_GATEWAY_TOKEN` set), then point the CLI agent at it instead of
Ollama directly: `OWA_LLM_BASE_URL=http://127.0.0.1:8000/v1 OWA_LLM_API_KEY=<same
token> uv run python -m agent`. There's no real GPU to start/stop yet, so the
gateway wakes a `FakeGPUBackend` that simulates the cold-start timing and then
proxies real requests to your local Ollama server — see `gateway/fake_backend.py`.

## Roadmap

- [x] **Data plane (DuckDB)** — connector protocol, DuckDB adapter, synthetic settlement dataset generator, FastMCP server with SELECT-only enforcement (`sqlglot`), row limits, and audit logging; CI running lint + adapter contract tests on every push.
- [x] **Data plane (Snowflake)** — adapter verified end-to-end against a live trial account: key-pair-authenticated service user with a scoped, SELECT-only role (see `infra/snowflake_bootstrap.py`), seeded via `data/seed_snowflake.py`, passing the full adapter contract test suite (`tests/test_snowflake_adapter.py`, live-gated on `SNOWFLAKE_ACCOUNT`).
- [x] **Local agent** — fully local dev loop: CLI chat host (`agent/`) driving the MCP server via an open-weight model served locally through Ollama, no cloud dependency required.
- [x] **Gateway service** — FastAPI OpenAI-compatible proxy (`gateway/`) with the start/stop lifecycle state machine, idle reaper, health-polling, bearer-token auth, and the "warming up" (503 + `Retry-After`) cold-start response, built against a `ComputeBackend` protocol so a real AWS-backed implementation can swap in later with no changes to the app or state machine. Currently wired to a `FakeGPUBackend` that simulates cold-start timing — no real GPU yet.
- [ ] **AWS inference plane** — Terraform for the VPC/gateway/GPU instance/IAM/security groups ✅, an AMI bake with vLLM + model weights, and a real EC2-backed `ComputeBackend` to replace the fake one ✅ (written, unit-tested against a fake AWS client via `OWA_GATEWAY_BACKEND=ec2`; not yet verified against a live instance — the GPU instance and AMI bake are both still blocked on a pending AWS GPU vCPU quota increase).
- [x] **Databricks adapter** — verified end-to-end against a live trial workspace on AWS: OAuth client-credentials auth via a scoped service principal (Databricks' built-in connector auth is Azure-only, so `connector/databricks_adapter.py` talks to the OIDC token endpoint directly), Unity Catalog catalog/schema + grants via `infra/databricks_bootstrap.py`, seeded via `data/seed_databricks.py`, passing the full adapter contract test suite (`tests/test_databricks_adapter.py`, live-gated on `DATABRICKS_SERVER_HOSTNAME`).
- [ ] **Polish** — a recorded end-to-end demo (question → GPU wakes → answer → GPU sleeps).

## Status

Data plane running against DuckDB, Snowflake, and Databricks: connector protocol, DuckDB adapter, Snowflake adapter (key-pair auth, scoped least-privilege role), Databricks adapter (OAuth client-credentials via a scoped service principal, Unity Catalog grants) — both cloud adapters verified end-to-end against live trial accounts — synthetic dataset generator, FastMCP server, and a passing CI-tested pytest suite. Local agent working end-to-end: CLI chat host + tool-calling loop against a local Ollama server, with test coverage on the loop, LLM wire-format translation, and MCP client. Gateway service working locally end-to-end (CLI → gateway → simulated GPU → Ollama), with test coverage on the state machine and the proxy app. AWS infra (VPC, gateway instance, IAM, budget alert) is applied and confirmed working; the real EC2-backed `ComputeBackend` (`gateway/ec2_backend.py`) is written and unit-tested, but the GPU instance itself and the AMI bake are both blocked on a pending AWS GPU vCPU quota increase, so it hasn't been exercised against a live instance yet.
