import httpx

from gateway.ec2_backend import EC2Backend

INSTANCE_ID = "i-0deadbeef00000000"


class _FakeEc2Client:
    def __init__(self, *, state: str = "stopped", private_ip: str | None = None) -> None:
        self.state = state
        self.private_ip = private_ip
        self.start_calls: list[list[str]] = []
        self.stop_calls: list[list[str]] = []
        self.describe_error: Exception | None = None

    def start_instances(self, *, InstanceIds: list[str]) -> None:
        self.start_calls.append(InstanceIds)
        self.state = "running"

    def stop_instances(self, *, InstanceIds: list[str]) -> None:
        self.stop_calls.append(InstanceIds)
        self.state = "stopped"

    def describe_instances(self, *, InstanceIds: list[str]) -> dict:
        if self.describe_error is not None:
            raise self.describe_error
        instance: dict = {"State": {"Name": self.state}}
        if self.private_ip is not None:
            instance["PrivateIpAddress"] = self.private_ip
        return {"Reservations": [{"Instances": [instance]}]}


class _FakeHttpResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class _FakeHttpClient:
    def __init__(self, *, healthy: bool = True, raises: bool = False) -> None:
        self.healthy = healthy
        self.raises = raises
        self.requested_urls: list[str] = []

    async def get(self, url: str, *, timeout: float) -> _FakeHttpResponse:
        self.requested_urls.append(url)
        if self.raises:
            raise httpx.ConnectError("connection refused")
        return _FakeHttpResponse(200 if self.healthy else 503)


async def test_is_healthy_false_while_instance_pending():
    ec2 = _FakeEc2Client(state="pending")
    backend = EC2Backend(
        instance_id=INSTANCE_ID, ec2_client=ec2, vllm_port=8000, http_client=_FakeHttpClient()
    )

    assert await backend.is_healthy() is False
    assert backend.base_url == ""


async def test_is_healthy_false_when_running_but_vllm_not_ready():
    ec2 = _FakeEc2Client(state="running", private_ip="10.0.1.5")
    http = _FakeHttpClient(healthy=False)
    backend = EC2Backend(instance_id=INSTANCE_ID, ec2_client=ec2, vllm_port=8000, http_client=http)

    assert await backend.is_healthy() is False
    assert http.requested_urls == ["http://10.0.1.5:8000/health"]


async def test_is_healthy_true_once_running_and_vllm_ready():
    ec2 = _FakeEc2Client(state="running", private_ip="10.0.1.5")
    backend = EC2Backend(
        instance_id=INSTANCE_ID,
        ec2_client=ec2,
        vllm_port=8000,
        http_client=_FakeHttpClient(healthy=True),
    )

    assert await backend.is_healthy() is True
    assert backend.base_url == "http://10.0.1.5:8000/v1"


async def test_is_healthy_false_when_health_check_connection_fails():
    ec2 = _FakeEc2Client(state="running", private_ip="10.0.1.5")
    backend = EC2Backend(
        instance_id=INSTANCE_ID,
        ec2_client=ec2,
        vllm_port=8000,
        http_client=_FakeHttpClient(raises=True),
    )

    assert await backend.is_healthy() is False


async def test_is_healthy_false_on_describe_instances_error():
    ec2 = _FakeEc2Client(state="running", private_ip="10.0.1.5")
    ec2.describe_error = RuntimeError("throttled")
    backend = EC2Backend(
        instance_id=INSTANCE_ID, ec2_client=ec2, vllm_port=8000, http_client=_FakeHttpClient()
    )

    assert await backend.is_healthy() is False


async def test_start_calls_start_instances_with_instance_id():
    ec2 = _FakeEc2Client()
    backend = EC2Backend(
        instance_id=INSTANCE_ID, ec2_client=ec2, vllm_port=8000, http_client=_FakeHttpClient()
    )

    await backend.start()

    assert ec2.start_calls == [[INSTANCE_ID]]


async def test_stop_calls_stop_instances_and_clears_base_url():
    ec2 = _FakeEc2Client(state="running", private_ip="10.0.1.5")
    backend = EC2Backend(
        instance_id=INSTANCE_ID, ec2_client=ec2, vllm_port=8000, http_client=_FakeHttpClient()
    )
    await backend.is_healthy()
    assert backend.base_url != ""

    await backend.stop()

    assert ec2.stop_calls == [[INSTANCE_ID]]
    assert backend.base_url == ""
