"""The gateway's lifecycle state machine.

GatewayController owns the STOPPED -> STARTING -> READY transitions around
one ComputeBackend, plus the idle reaper that stops the backend again after
inactivity. Kept decoupled from FastAPI/HTTP entirely so it can be unit
tested with a fake backend and short timeouts, no ASGI app involved — same
spirit as agent/loop.py being decoupled from the OpenAI SDK and MCP client.
"""

from __future__ import annotations

import asyncio
import time
from enum import Enum

from gateway.compute import ComputeBackend


class GatewayState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    READY = "ready"


class GatewayController:
    def __init__(
        self,
        backend: ComputeBackend,
        *,
        idle_timeout_seconds: float,
        poll_interval_seconds: float = 0.2,
    ) -> None:
        self._backend = backend
        self._idle_timeout_seconds = idle_timeout_seconds
        self._poll_interval_seconds = poll_interval_seconds
        self._state = GatewayState.STOPPED
        self._last_activity: float | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> GatewayState:
        return self._state

    @property
    def backend(self) -> ComputeBackend:
        return self._backend

    async def ensure_ready(self) -> bool:
        """Wake the backend if needed. Returns True once ready to serve now.

        False means the caller should tell the client to come back later
        (still starting) — never blocks until the backend is healthy.
        """
        async with self._lock:
            if self._state == GatewayState.STOPPED:
                self._state = GatewayState.STARTING
                await self._backend.start()

            if self._state == GatewayState.STARTING:
                if not await self._backend.is_healthy():
                    return False
                self._state = GatewayState.READY

            self._last_activity = time.monotonic()
            return True

    async def reap_if_idle(self) -> bool:
        """Stop the backend if it's been READY and idle past the timeout."""
        async with self._lock:
            if (
                self._state == GatewayState.READY
                and self._last_activity is not None
                and time.monotonic() - self._last_activity >= self._idle_timeout_seconds
            ):
                await self._backend.stop()
                self._state = GatewayState.STOPPED
                self._last_activity = None
                return True
        return False

    async def run_idle_reaper(self, *, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            await self.reap_if_idle()
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self._poll_interval_seconds)
            except TimeoutError:
                pass
