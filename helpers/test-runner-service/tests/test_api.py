import time

from fastapi.testclient import TestClient

from test_runner_service.main import create_app
from test_runner_service.processes import ProcessResult
from test_runner_service.settings import Settings
from tests.fakes import FakeProcessRunner


def test_build_api_and_html(settings: Settings) -> None:
    runner = FakeProcessRunner(
        [ProcessResult(0, "build output"), ProcessResult(0, "sha256:built\n")]
    )
    with TestClient(create_app(settings, runner)) as client:
        index = client.get("/")
        accepted = client.post("/v1/images/build", json={"revision": "working-tree"})
        state = _wait_for_terminal(client)

    assert index.status_code == 200
    assert "Hardware Test Runner" in index.text
    assert accepted.status_code == 202
    assert state["status"] == "succeeded"
    assert state["image_digest"] == "sha256:built"


def test_api_rejects_untrusted_image(settings: Settings) -> None:
    with TestClient(create_app(settings, FakeProcessRunner())) as client:
        response = client.post(
            "/v1/runs",
            json={
                "image": "untrusted.example/image:latest",
                "stand": "stand-01",
                "scenario": "smoke",
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "image reference is not allowed"


def test_api_reports_busy_runner(settings: Settings) -> None:
    runner = FakeProcessRunner()
    runner.block = True
    with TestClient(create_app(settings, runner)) as client:
        first = client.post(
            "/v1/images/pull",
            json={"reference": "registry.example/image@sha256:abc"},
        )
        second = client.post(
            "/v1/runs",
            json={"image": "sha256:abc", "stand": "stand-01", "scenario": "smoke"},
        )
        cancel = client.post("/v1/current/cancel")

    assert first.status_code == 202
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "runner_busy"
    assert cancel.status_code == 200


def _wait_for_terminal(client: TestClient) -> dict[str, object]:
    terminal = {
        "succeeded",
        "passed",
        "failed",
        "cancelled",
        "timed_out",
        "infrastructure_error",
        "interrupted",
    }
    for _ in range(100):
        response = client.get("/v1/current")
        state: dict[str, object] = response.json()
        if state["status"] in terminal:
            return state
        time.sleep(0.001)
    raise AssertionError("operation did not finish")
