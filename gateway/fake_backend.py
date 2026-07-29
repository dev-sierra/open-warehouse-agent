"""A fake "GPU box" that simulates cold-start timing without AWS.

There's no real GPU to start/stop yet (that's the Terraform/AMI roadmap
item). This stands in for it: start() records a timestamp, and is_healthy()
only returns True once `boot_seconds` has elapsed — simulating the README's
2-4 minute cold start on a demo timescale. It doesn't touch the user's real
Ollama process; once "ready" it just points requests at wherever an
OpenAI-compatible server already lives (Ollama, for local dev), so proxied
requests get real answers rather than a stub response.
"""

from __future__ import annotations

import time


class FakeGPUBackend:
    def __init__(self, *, base_url: str, boot_seconds: float) -> None:
        self.base_url = base_url
        self._boot_seconds = boot_seconds
        self._started_at: float | None = None

    async def start(self) -> None:
        if self._started_at is None:
            self._started_at = time.monotonic()

    async def stop(self) -> None:
        self._started_at = None

    async def is_healthy(self) -> bool:
        if self._started_at is None:
            return False
        return time.monotonic() - self._started_at >= self._boot_seconds
