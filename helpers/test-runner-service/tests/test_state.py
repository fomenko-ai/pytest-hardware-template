from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from test_runner_service.models import OperationState, OperationStatus, OperationType
from test_runner_service.settings import Settings
from test_runner_service.state import StateStore


def test_state_round_trip_and_log_reset(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state")
    store.initialize()
    state = OperationState(
        operation_id="run-123",
        run_id="pytest-run-456",
        operation_type=OperationType.RUN_TESTS,
        status=OperationStatus.RUNNING,
        created_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
    )

    store.write(state)
    store.log_file.write_text("old output\n", encoding="utf-8")
    store.reset_log()

    restored = store.read()
    assert restored == state
    assert restored is not None
    assert restored.run_id == "pytest-run-456"
    assert store.log_file.read_text(encoding="utf-8") == ""
    assert not store.state_file.with_suffix(".json.tmp").exists()


def test_active_state_is_marked_interrupted_after_restart(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state")
    store.initialize()
    state = OperationState.started(
        "pull-123",
        OperationType.PULL_IMAGE,
        OperationStatus.PULLING,
    )
    store.write(state)

    interrupted = store.mark_interrupted()

    assert interrupted is not None
    assert interrupted.status is OperationStatus.INTERRUPTED
    assert store.read() == interrupted


def test_comma_separated_environment_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "TEST_RUNNER_ALLOWED_IMAGE_PREFIXES",
        "sha256:,registry.example/hardware-tests@sha256:",
    )
    monkeypatch.setenv("TEST_RUNNER_DOCKER_DEVICES", "/dev/ttyUSB0,/dev/ttyUSB1")

    settings = Settings(_env_file=None)

    assert settings.allowed_image_prefixes == (
        "sha256:",
        "registry.example/hardware-tests@sha256:",
    )
    assert settings.docker_devices == ("/dev/ttyUSB0", "/dev/ttyUSB1")


def test_allure_requires_report_access_token_when_enabled() -> None:
    with pytest.raises(ValidationError, match="TEST_RUNNER_ALLURE_ACCESS_TOKEN"):
        Settings(_env_file=None, allure_enabled=True)


@pytest.mark.parametrize(
    "path",
    ["/absolute/report.xml", "../outside.xml", "reports/../../outside.xml", "."],
)
def test_report_paths_must_stay_below_session_directory(path: str) -> None:
    with pytest.raises(ValidationError, match="relative descendants"):
        Settings(_env_file=None, junit_path=path)


def test_empty_report_paths_disable_capabilities() -> None:
    settings = Settings(
        _env_file=None,
        pytest_log_path="",
        junit_path="",
        html_path="",
        allure_results_path="",
    )

    assert settings.pytest_log_path is None
    assert settings.junit_path is None
    assert settings.html_path is None
    assert settings.allure_results_path is None
