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
    assert "Open HTML report" in index.text
    assert "Open Allure report" in index.text
    assert "All test artifacts" in index.text
    assert "All Allure reports" in index.text
    assert "a, a:visited { color: LinkText; }" in index.text
    assert 'aria-label="Report history"' in index.text
    assert "await refresh(false)" in index.text
    assert "showTerminalResult && state && state.report_url" in index.text
    assert "await refreshArtifacts(showTerminalResult)" in index.text
    assert "state.image_digest ?? state.image_reference" in index.text
    assert 'state.operation_type === "pull_image" && state.image_reference' in index.text
    assert 'document.querySelector("#stand").value = state.stand' in index.text
    assert 'document.querySelector("#scenario").value = state.scenario' in index.text
    assert accepted.status_code == 202
    assert state["status"] == "succeeded"
    assert state["image_digest"] == "sha256:built"


def test_artifact_history_and_allure_tree_links(settings: Settings) -> None:
    run_directory = settings.artifacts_directory / "2026-run"
    reports = run_directory / "reports"
    reports.mkdir(parents=True)
    (run_directory / "pytest.log").write_text("diagnostics\n", encoding="utf-8")
    (reports / "report.html").write_text("<!doctype html>", encoding="utf-8")
    configured = settings.model_copy(
        update={
            "allure_enabled": True,
            "allure_access_token": "ars1.secret",
            "allure_public_url": "https://allure.example/base/",
            "allure_repository": "hardware-project",
        }
    )

    with TestClient(create_app(configured, FakeProcessRunner())) as client:
        page = client.get("/artifact-runs")
        runs = client.get("/v1/artifact-runs")
        report = client.get("/v1/artifact-runs/2026-run/report.html")
        config = client.get("/v1/config")

    assert page.status_code == 200
    assert "Test artifact runs" in page.text
    assert "a, a:visited { color: LinkText; }" in page.text
    assert runs.json()["items"][0]["run_id"] == "2026-run"
    assert report.status_code == 200
    assert config.json() == {
        "allure_reports_url": ("https://allure.example/base/reports/tree?repo=hardware-project")
    }


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


def test_run_api_schema_has_readable_examples(settings: Settings) -> None:
    with TestClient(create_app(settings, FakeProcessRunner())) as client:
        schema = client.get("/openapi.json").json()

    properties = schema["components"]["schemas"]["RunTestsRequest"]["properties"]
    assert properties["image"]["examples"] == [
        "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    ]
    assert properties["stand"]["examples"] == ["virtual-stand"]
    assert properties["scenario"]["examples"] == ["virtual-smoke"]


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
