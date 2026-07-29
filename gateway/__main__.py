"""Entry point: uv run python -m gateway

Defaults to running the gateway locally against a FakeGPUBackend (see
fake_backend.py) — this simulates cold-start timing while proxying real
requests to a locally-running OpenAI-compatible server (Ollama, by default)
once "ready". Set OWA_GATEWAY_BACKEND=ec2 to run against the real AWS GPU
box instead (see ec2_backend.py) — swapping backends needs no changes to
gateway/app.py or gateway/state.py.
"""

from __future__ import annotations

import os

import boto3
import uvicorn

from gateway.app import build_app
from gateway.compute import ComputeBackend
from gateway.ec2_backend import EC2Backend
from gateway.fake_backend import FakeGPUBackend
from gateway.state import GatewayController

DEFAULT_BACKEND_BASE_URL = "http://localhost:11434/v1"
DEFAULT_IDLE_TIMEOUT_SECONDS = 300.0
DEFAULT_BOOT_SECONDS = 3.0
DEFAULT_VLLM_PORT = 8000
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def build_backend(name: str) -> ComputeBackend:
    """Turn OWA_GATEWAY_BACKEND into a ComputeBackend, "fake" by default.

    Mirrors mcp_server/backends.py:build_connector's dispatch-by-name shape.
    """
    if name == "fake":
        backend_base_url = os.environ.get("OWA_GATEWAY_BACKEND_BASE_URL", DEFAULT_BACKEND_BASE_URL)
        boot_seconds = float(os.environ.get("OWA_FAKE_GPU_BOOT_SECONDS", DEFAULT_BOOT_SECONDS))
        return FakeGPUBackend(base_url=backend_base_url, boot_seconds=boot_seconds)

    if name == "ec2":
        instance_id = os.environ["OWA_GPU_INSTANCE_ID"]
        region = os.environ.get("OWA_AWS_REGION")
        vllm_port = int(os.environ.get("OWA_VLLM_PORT", DEFAULT_VLLM_PORT))
        ec2_client = boto3.client("ec2", region_name=region)
        return EC2Backend(instance_id=instance_id, ec2_client=ec2_client, vllm_port=vllm_port)

    raise ValueError(f"unknown OWA_GATEWAY_BACKEND {name!r} — supported: fake, ec2")


def main() -> None:
    token = os.environ["OWA_GATEWAY_TOKEN"]
    backend_name = os.environ.get("OWA_GATEWAY_BACKEND", "fake")
    idle_timeout_seconds = float(
        os.environ.get("OWA_GATEWAY_IDLE_TIMEOUT_SECONDS", DEFAULT_IDLE_TIMEOUT_SECONDS)
    )
    host = os.environ.get("OWA_GATEWAY_HOST", DEFAULT_HOST)
    port = int(os.environ.get("OWA_GATEWAY_PORT", DEFAULT_PORT))

    backend = build_backend(backend_name)
    controller = GatewayController(backend, idle_timeout_seconds=idle_timeout_seconds)
    app = build_app(controller, token=token)

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
