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
        operation_type=OperationType.RUN_TESTS,
        status=OperationStatus.RUNNING,
        created_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
    )

    store.write(state)
    store.log_file.write_text("old output\n", encoding="utf-8")
    store.reset_log()

    assert store.read() == state
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
