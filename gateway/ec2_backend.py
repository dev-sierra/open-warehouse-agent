"""Real AWS-backed ComputeBackend: starts/stops the GPU EC2 instance via
boto3 and confirms vLLM itself is serving before reporting ready.

Mirrors gateway.fake_backend.FakeGPUBackend's shape exactly, so
gateway/state.py and gateway/app.py need no changes to use this instead —
see gateway/compute.py's ComputeBackend protocol docstring.
"""

from __future__ import annotations

import asyncio
from typing import Protocol

import httpx


class Ec2Client(Protocol):
    """The subset of boto3's EC2 client this backend calls.

    Lets tests inject a hand-rolled fake instead of a mocking library or
    moto, matching this repo's existing test style (see
    tests/test_gateway_app.py's _FakeUpstreamClient).
    """

    def start_instances(self, *, InstanceIds: list[str]) -> object: ...
    def stop_instances(self, *, InstanceIds: list[str]) -> object: ...
    def describe_instances(self, *, InstanceIds: list[str]) -> dict: ...


class EC2Backend:
    def __init__(
        self,
        *,
        instance_id: str,
        ec2_client: Ec2Client,
        vllm_port: int,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._instance_id = instance_id
        self._ec2 = ec2_client
        self._vllm_port = vllm_port
        self._http = http_client or httpx.AsyncClient()
        self.base_url = ""

    async def start(self) -> None:
        await asyncio.to_thread(self._ec2.start_instances, InstanceIds=[self._instance_id])

    async def stop(self) -> None:
        await asyncio.to_thread(self._ec2.stop_instances, InstanceIds=[self._instance_id])
        self.base_url = ""

    async def is_healthy(self) -> bool:
        # A transient AWS API error or network blip mid-boot should read as
        # "still starting," not crash the request that's polling us —
        # GatewayController.ensure_ready() calls this repeatedly and never
        # expects it to raise.
        try:
            instance = await self._describe_instance()
        except Exception:
            return False

        if instance.get("State", {}).get("Name") != "running":
            return False

        private_ip = instance.get("PrivateIpAddress")
        if not private_ip:
            return False

        self.base_url = f"http://{private_ip}:{self._vllm_port}/v1"
        return await self._vllm_ready(private_ip)

    async def _describe_instance(self) -> dict:
        response = await asyncio.to_thread(
            self._ec2.describe_instances, InstanceIds=[self._instance_id]
        )
        return response["Reservations"][0]["Instances"][0]

    async def _vllm_ready(self, private_ip: str) -> bool:
        # vLLM's liveness endpoint lives at the server root, not under /v1.
        try:
            response = await self._http.get(
                f"http://{private_ip}:{self._vllm_port}/health", timeout=2.0
            )
        except httpx.HTTPError:
            return False
        return response.status_code == 200
