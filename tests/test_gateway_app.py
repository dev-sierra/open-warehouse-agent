import json

import httpx
import pytest

from gateway.app import build_app
from gateway.state import GatewayController

TOKEN = "secret-token"


class _FakeBackend:
    def __init__(self, *, healthy: bool) -> None:
        self.base_url = "http://fake-backend.example/v1"
        self.healthy = healthy
        self.start_calls = 0
        self.stop_calls = 0

    async def start(self) -> None:
        self.start_calls += 1

    async def stop(self) -> None:
        self.stop_calls += 1

    async def is_healthy(self) -> bool:
        return self.healthy


class _FakeUpstreamResponse:
    def __init__(self, content: bytes, status_code: int = 200) -> None:
        self.content = content
        self.status_code = status_code
        self.headers = {"content-type": "application/json"}


class _FakeUpstreamClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    async def __aenter__(self) -> "_FakeUpstreamClient":
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False

    async def post(self, path: str, *, content: bytes, headers: dict) -> _FakeUpstreamResponse:
        return _FakeUpstreamResponse(json.dumps({"echo": json.loads(content)}).encode())


@pytest.fixture
def client_for(monkeypatch):
    def _make(*, backend_healthy: bool):
        backend = _FakeBackend(healthy=backend_healthy)
        controller = GatewayController(backend, idle_timeout_seconds=100)
        app = build_app(controller, token=TOKEN)
        transport = httpx.ASGITransport(app=app)
        # Build the outer test client with the real httpx.AsyncClient first —
        # gateway/app.py shares this same httpx module, so patching the class
        # before construction would also break the client we're testing with.
        client = httpx.AsyncClient(transport=transport, base_url="http://test")
        monkeypatch.setattr("gateway.app.httpx.AsyncClient", _FakeUpstreamClient)
        return client, backend

    return _make


async def test_missing_token_returns_401(client_for):
    client, _ = client_for(backend_healthy=True)
    async with client:
        resp = await client.post("/v1/chat/completions", json={"model": "x"})
    assert resp.status_code == 401


async def test_invalid_token_returns_401(client_for):
    client, _ = client_for(backend_healthy=True)
    async with client:
        resp = await client.post(
            "/v1/chat/completions",
            json={"model": "x"},
            headers={"Authorization": "Bearer wrong-token"},
        )
    assert resp.status_code == 401


async def test_request_while_cold_returns_503_with_retry_after(client_for):
    client, backend = client_for(backend_healthy=False)
    async with client:
        resp = await client.post(
            "/v1/chat/completions",
            json={"model": "x"},
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
    assert resp.status_code == 503
    assert resp.headers["retry-after"] == "5"
    assert backend.start_calls == 1


async def test_request_once_healthy_proxies_through(client_for):
    client, _ = client_for(backend_healthy=True)
    async with client:
        resp = await client.post(
            "/v1/chat/completions",
            json={"model": "x", "messages": []},
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"echo": {"model": "x", "messages": []}}


async def test_healthz_reflects_state_through_lifecycle(client_for):
    client, _ = client_for(backend_healthy=True)
    async with client:
        resp = await client.get("/healthz")
        assert resp.json() == {"state": "stopped"}

        await client.post(
            "/v1/chat/completions",
            json={"model": "x"},
            headers={"Authorization": f"Bearer {TOKEN}"},
        )

        resp = await client.get("/healthz")
        assert resp.json() == {"state": "ready"}
