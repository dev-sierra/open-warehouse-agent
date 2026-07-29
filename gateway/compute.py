"""Compute backend protocol every "GPU box" implementation satisfies.

Mirrors connector.protocol.WarehouseConnector: gateway/app.py and
gateway/state.py are written against this protocol only, never a specific
backend. Today the only implementation is gateway.fake_backend.FakeGPUBackend
(see its docstring); a real AWS/EC2-backed implementation is future work
(the Terraform/AMI roadmap item) and can be swapped in with no changes to
the state machine or the FastAPI app.
"""

from __future__ import annotations

from typing import Protocol


class ComputeBackend(Protocol):
    """A start/stoppable compute box exposing an OpenAI-compatible API."""

    base_url: str

    async def start(self) -> None:
        """Begin booting the backend. Must not block until ready."""
        ...

    async def stop(self) -> None:
        """Tear the backend down (or mark it stopped)."""
        ...

    async def is_healthy(self) -> bool:
        """Whether the backend is booted and ready to serve requests."""
        ...
