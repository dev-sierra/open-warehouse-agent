"""Entry point: uv run python -m gateway

Runs the gateway locally against a FakeGPUBackend (see fake_backend.py) —
there's no real GPU to start/stop yet, so this simulates cold-start timing
while proxying real requests to a locally-running OpenAI-compatible server
(Ollama, by default) once "ready". Swapping in a real AWS-backed
ComputeBackend later needs no changes to gateway/app.py or gateway/state.py.
"""

from __future__ import annotations

import os

import uvicorn

from gateway.app import build_app
from gateway.fake_backend import FakeGPUBackend
from gateway.state import GatewayController

DEFAULT_BACKEND_BASE_URL = "http://localhost:11434/v1"
DEFAULT_IDLE_TIMEOUT_SECONDS = 300.0
DEFAULT_BOOT_SECONDS = 3.0
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def main() -> None:
    token = os.environ["OWA_GATEWAY_TOKEN"]
    backend_base_url = os.environ.get("OWA_GATEWAY_BACKEND_BASE_URL", DEFAULT_BACKEND_BASE_URL)
    idle_timeout_seconds = float(
        os.environ.get("OWA_GATEWAY_IDLE_TIMEOUT_SECONDS", DEFAULT_IDLE_TIMEOUT_SECONDS)
    )
    boot_seconds = float(os.environ.get("OWA_FAKE_GPU_BOOT_SECONDS", DEFAULT_BOOT_SECONDS))
    host = os.environ.get("OWA_GATEWAY_HOST", DEFAULT_HOST)
    port = int(os.environ.get("OWA_GATEWAY_PORT", DEFAULT_PORT))

    backend = FakeGPUBackend(base_url=backend_base_url, boot_seconds=boot_seconds)
    controller = GatewayController(backend, idle_timeout_seconds=idle_timeout_seconds)
    app = build_app(controller, token=token)

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
