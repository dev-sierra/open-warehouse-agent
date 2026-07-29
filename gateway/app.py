"""FastAPI app: the OpenAI-compatible proxy + lifecycle endpoints.

build_app() is written against gateway.state.GatewayController only, so it
never has to know whether the backing ComputeBackend is the local
FakeGPUBackend or a real AWS-backed one later.
"""

from __future__ import annotations

import asyncio
import secrets
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response

from gateway.state import GatewayController


def build_app(controller: GatewayController, *, token: str) -> FastAPI:
    def require_bearer_token(request: Request) -> None:
        scheme, _, credential = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not secrets.compare_digest(credential, token):
            raise HTTPException(status_code=401, detail="invalid or missing bearer token")

    reaper_stop = asyncio.Event()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        reaper_task = asyncio.create_task(controller.run_idle_reaper(stop_event=reaper_stop))
        yield
        reaper_stop.set()
        await reaper_task

    app = FastAPI(lifespan=lifespan)

    @app.post("/v1/chat/completions", dependencies=[Depends(require_bearer_token)])
    async def chat_completions(request: Request) -> Response:
        if not await controller.ensure_ready():
            return Response(
                content="warming up",
                status_code=503,
                headers={"Retry-After": "5"},
            )

        body = await request.body()
        async with httpx.AsyncClient(base_url=controller.backend.base_url) as client:
            upstream = await client.post(
                "/chat/completions",
                content=body,
                headers={"content-type": "application/json"},
            )
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            media_type=upstream.headers.get("content-type", "application/json"),
        )

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"state": controller.state.value}

    return app
