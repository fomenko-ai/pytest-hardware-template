import asyncio
import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from test_runner_service.docker_commands import DockerCommandBuilder
from test_runner_service.main import create_app
from test_runner_service.models import OperationStatus, ReportPortalStatus
from test_runner_service.processes import ProcessResult
from test_runner_service.reportportal import read_reportportal_result
from test_runner_service.settings import Settings
from test_runner_service.state import StateStore
from test_runner_service.worker import OperationCoordinator
from tests.fakes import FakeProcessRunner


@pytest.fixture
def reportportal_settings(settings: Settings) -> Settings:
    return Settings.model_validate(
        settings.model_dump()
        | {
            "reportportal_enabled": True,
            "reportportal_endpoint": "https://internal.example/rp",
            "reportportal_public_url": "https://reports.example",
            "reportportal_project": "hardware_tests",
            "reportportal_api_key": "fake-reporting-key",
        }
    )


@pytest.mark.parametrize("allure", [False, True])
def test_reportportal_commands_and_api_keep_secrets_server_side(
    reportportal_settings: Settings,
    allure: bool,
) -> None:
    configured = reportportal_settings.model_copy(update={"allure_enabled": allure})
    builder = DockerCommandBuilder(configured)
    build = builder.build_image("build-1")
    command = builder.run_tests("run-1", "pytest-run-1", "sha256:abc", "stand-01", "smoke")
    assert "INSTALL_REPORTPORTAL=true" in build
    assert ("INSTALL_ALLURE=true" in build) is allure
    assert ("--alluredir" in command) is allure
    assert "--reportportal" in command
    assert command[command.index("--rp-launch") + 1] == "run-1"
    assert command[command.index("--rp-endpoint") + 1] == "https://internal.example/rp"
    assert command[command.index("--env") + 1] == "RP_API_KEY"
    assert "fake-reporting-key" not in " ".join(command)
    assert "fake-reporting-key" not in repr(configured)
    with TestClient(create_app(configured, FakeProcessRunner())) as client:
        response = client.get("/v1/config")
    assert response.json()["reportportal_launches_url"] == (
        "https://reports.example/ui/#hardware_tests/launches/all"
    )
    assert "fake-reporting-key" not in response.text
    assert "internal.example" not in response.text


@pytest.mark.parametrize(
    "field",
    [
        "reportportal_endpoint",
        "reportportal_public_url",
        "reportportal_project",
        "reportportal_api_key",
    ],
)
def test_enabled_reportportal_requires_complete_configuration(
    reportportal_settings: Settings,
    field: str,
) -> None:
    with pytest.raises(ValidationError, match=f"TEST_RUNNER_{field.upper()}"):
        Settings.model_validate(reportportal_settings.model_dump() | {field: ""})


@pytest.mark.parametrize(
    "url",
    [
        "https://user:password@reports.example",
        "https://reports.example?token=secret",
        "https://reports.example/#project",
    ],
)
def test_reportportal_urls_reject_embedded_secrets_or_ui_fragments(
    settings: Settings,
    url: str,
) -> None:
    with pytest.raises(ValidationError, match="must not contain"):
        Settings.model_validate(settings.model_dump() | {"reportportal_public_url": url})


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("PASSED", "finished"),
        ("FAILED", "finished"),
        ("IN_PROGRESS", "incomplete"),
        ("INTERRUPTED", "incomplete"),
    ],
)
def test_lookup_maps_only_this_launch_and_closes_connection(
    reportportal_settings: Settings,
    status: str,
    expected: str,
) -> None:
    connection = Mock()
    response = connection.getresponse.return_value
    response.status = 200
    response.read.return_value = json.dumps(
        {
            "content": [
                {"id": 42, "name": "run-1", "status": status},
            ]
        }
    ).encode()
    with patch(
        "test_runner_service.reportportal.HTTPSConnection", return_value=connection
    ) as factory:
        result = read_reportportal_result(reportportal_settings, "run-1")
    factory.assert_called_once_with("internal.example", 443, timeout=5)
    connection.request.assert_called_once_with(
        "GET",
        "/rp/api/v1/hardware_tests/launch?filter.eq.name=run-1&page.size=2",
        headers={"Authorization": "Bearer fake-reporting-key"},
    )
    connection.close.assert_called_once()
    assert result["reportportal_status"] == expected
    assert (
        result["reportportal_url"] == "https://reports.example/ui/#hardware_tests/launches/all/42"
    )


@pytest.mark.parametrize(
    "failure", ["timeout", "redirect", "unauthorized", "forbidden", "malformed", "missing", "wrong"]
)
def test_lookup_failure_is_separate_and_does_not_expose_response_or_secret(
    reportportal_settings: Settings,
    failure: str,
) -> None:
    connection = Mock()
    response = connection.getresponse.return_value
    response.status = {"redirect": 302, "unauthorized": 401, "forbidden": 403}.get(failure, 200)
    response.read.return_value = b'{"content": []}'
    if failure == "timeout":
        connection.request.side_effect = TimeoutError("fake-reporting-key")
    elif failure == "malformed":
        response.read.return_value = b"fake-reporting-key"
    elif failure == "wrong":
        response.read.return_value = (
            b'{"content": [{"id": 42, "name": "other", "status": "PASSED"}]}'
        )
    with patch("test_runner_service.reportportal.HTTPSConnection", return_value=connection):
        result = read_reportportal_result(reportportal_settings, "run-1")
    assert result["reportportal_status"] == "unavailable"
    assert "reportportal_url" not in result
    assert "fake-reporting-key" not in str(result)
    assert connection.request.call_count == 1
    connection.close.assert_called_once()


def test_disabled_reporting_does_not_open_connections(settings: Settings) -> None:
    with patch("test_runner_service.reportportal.HTTPSConnection") as connection:
        assert read_reportportal_result(settings, "run-1") == {}
    connection.assert_not_called()


@pytest.mark.parametrize(
    ("exit_code", "status"), [(0, OperationStatus.PASSED), (1, OperationStatus.FAILED)]
)
@pytest.mark.parametrize(
    "report_status", [ReportPortalStatus.FINISHED, ReportPortalStatus.UNAVAILABLE]
)
def test_worker_preserves_pytest_outcome_and_passes_key_only_in_environment(
    reportportal_settings: Settings,
    exit_code: int,
    status: OperationStatus,
    report_status: ReportPortalStatus,
) -> None:
    async def exercise() -> None:
        store = StateStore(reportportal_settings.state_directory)
        store.initialize()
        runner = FakeProcessRunner([ProcessResult(exit_code, "pytest output")])
        coordinator = OperationCoordinator(
            reportportal_settings,
            store,
            DockerCommandBuilder(reportportal_settings),
            runner,
        )
        with patch(
            "test_runner_service.worker.read_reportportal_result",
            return_value={
                "reportportal_status": report_status,
            },
        ) as lookup:
            accepted = await coordinator.start_run("sha256:abc", "stand-01", "smoke")
            async with asyncio.timeout(2):
                while (current := store.read()) is None or not current.status.is_terminal:
                    await asyncio.sleep(0.001)
        assert current.status is status
        assert current.exit_code == exit_code
        assert current.reportportal_status == report_status
        lookup.assert_called_once_with(reportportal_settings, accepted.operation_id)
        assert runner.environments == [{"RP_API_KEY": "fake-reporting-key"}]
        assert "fake-reporting-key" not in current.model_dump_json()
        assert "fake-reporting-key" not in store.log_file.read_text()

    asyncio.run(exercise())


@pytest.mark.parametrize("cancel", [False, True])
def test_interrupted_run_keeps_reportportal_result_separate(
    reportportal_settings: Settings,
    cancel: bool,
) -> None:
    async def exercise() -> None:
        class InterruptedRunner(FakeProcessRunner):
            async def run(
                self,
                command: tuple[str, ...],
                log_file: Path,
                environment: dict[str, str] | None = None,
            ) -> ProcessResult:
                if not cancel:
                    raise TimeoutError
                return await super().run(command, log_file, environment)

        store = StateStore(reportportal_settings.state_directory)
        store.initialize()
        runner = InterruptedRunner()
        runner.block = cancel
        coordinator = OperationCoordinator(
            reportportal_settings,
            store,
            DockerCommandBuilder(reportportal_settings),
            runner,
        )
        with patch(
            "test_runner_service.worker.read_reportportal_result",
            return_value={
                "reportportal_status": ReportPortalStatus.INCOMPLETE,
            },
        ):
            accepted = await coordinator.start_run("sha256:abc", "stand-01", "smoke")
            if cancel:
                await coordinator.cancel()
            async with asyncio.timeout(2):
                while (current := store.read()) is None or not current.status.is_terminal:
                    await asyncio.sleep(0.001)
        assert current.status is (
            OperationStatus.CANCELLED if cancel else OperationStatus.TIMED_OUT
        )
        assert current.reportportal_status is ReportPortalStatus.INCOMPLETE
        assert runner.cancelled_containers == [f"hardware-test-run-{accepted.operation_id}"]

    asyncio.run(exercise())
