import asyncio

from gateway.state import GatewayController, GatewayState


class _FakeBackend:
    def __init__(self, *, healthy: bool = False) -> None:
        self.base_url = "http://backend.example"
        self.healthy = healthy
        self.start_calls = 0
        self.stop_calls = 0

    async def start(self) -> None:
        self.start_calls += 1

    async def stop(self) -> None:
        self.stop_calls += 1
        self.healthy = False

    async def is_healthy(self) -> bool:
        return self.healthy


async def test_ensure_ready_starts_backend_and_waits_for_healthy():
    backend = _FakeBackend()
    controller = GatewayController(backend, idle_timeout_seconds=100)

    assert await controller.ensure_ready() is False
    assert backend.start_calls == 1
    assert controller.state == GatewayState.STARTING

    backend.healthy = True

    assert await controller.ensure_ready() is True
    assert controller.state == GatewayState.READY


async def test_concurrent_ensure_ready_only_starts_backend_once():
    backend = _FakeBackend()
    controller = GatewayController(backend, idle_timeout_seconds=100)

    await asyncio.gather(*(controller.ensure_ready() for _ in range(5)))

    assert backend.start_calls == 1


async def test_reap_if_idle_is_noop_below_timeout():
    backend = _FakeBackend(healthy=True)
    controller = GatewayController(backend, idle_timeout_seconds=100)

    await controller.ensure_ready()

    assert await controller.reap_if_idle() is False
    assert controller.state == GatewayState.READY
    assert backend.stop_calls == 0


async def test_reap_if_idle_stops_backend_once_timeout_exceeded():
    backend = _FakeBackend(healthy=True)
    controller = GatewayController(backend, idle_timeout_seconds=0.05)

    await controller.ensure_ready()
    await asyncio.sleep(0.1)

    assert await controller.reap_if_idle() is True
    assert controller.state == GatewayState.STOPPED
    assert backend.stop_calls == 1


async def test_run_idle_reaper_stops_when_event_set():
    backend = _FakeBackend(healthy=True)
    controller = GatewayController(backend, idle_timeout_seconds=100, poll_interval_seconds=0.01)
    stop_event = asyncio.Event()

    task = asyncio.create_task(controller.run_idle_reaper(stop_event=stop_event))
    await asyncio.sleep(0.03)
    stop_event.set()

    await asyncio.wait_for(task, timeout=1)
