import asyncio
from pathlib import Path

import pytest

from test_runner_service.docker_commands import DockerCommandBuilder
from test_runner_service.models import OperationStatus
from test_runner_service.processes import ProcessResult
from test_runner_service.settings import Settings
from test_runner_service.state import StateStore
from test_runner_service.worker import OperationCoordinator, RunnerBusyError
from tests.fakes import FakeProcessRunner


def test_build_records_inspected_image_id(settings: Settings) -> None:
    async def exercise() -> None:
        store = StateStore(settings.state_directory)
        store.initialize()
        runner = FakeProcessRunner(
            [ProcessResult(0, "build output"), ProcessResult(0, "sha256:built\n")]
        )
        coordinator = OperationCoordinator(
            settings,
            store,
            DockerCommandBuilder(settings),
            runner,
        )

        accepted = await coordinator.start_build("working-tree")
        await _wait_for_terminal(store)
        state = store.read()

        assert state is not None
        assert state.operation_id == accepted.operation_id
        assert state.status is OperationStatus.SUCCEEDED
        assert state.image_digest == "sha256:built"
        assert len(runner.commands) == 2

    asyncio.run(exercise())


def test_runner_rejects_second_operation(settings: Settings) -> None:
    async def exercise() -> None:
        store = StateStore(settings.state_directory)
        store.initialize()
        runner = FakeProcessRunner()
        runner.block = True
        coordinator = OperationCoordinator(
            settings,
            store,
            DockerCommandBuilder(settings),
            runner,
        )

        first = await coordinator.start_pull("registry.example/image@sha256:abc")
        with pytest.raises(RunnerBusyError) as raised:
            await coordinator.start_run("sha256:abc", "stand-01", "smoke")
        assert raised.value.state.operation_id == first.operation_id
        await coordinator.cancel()
        await _wait_for_terminal(store)

    asyncio.run(exercise())


def test_hardware_run_reads_new_junit_result(settings: Settings) -> None:
    async def exercise() -> None:
        store = StateStore(settings.state_directory)
        store.initialize()

        class ArtifactFakeRunner(FakeProcessRunner):
            async def run(self, command: tuple[str, ...], log_file: Path) -> ProcessResult:
                result = await super().run(command, log_file)
                run_directory = settings.artifacts_directory / "new-run"
                reports = run_directory / "reports"
                reports.mkdir(parents=True)
                (run_directory / "pytest.log").write_text("failure\n", encoding="utf-8")
                (reports / "junit.xml").write_text(
                    '<testsuites><testsuite tests="2" failures="1"/></testsuites>',
                    encoding="utf-8",
                )
                return result

        runner = ArtifactFakeRunner([ProcessResult(1, "failed")])
        coordinator = OperationCoordinator(
            settings,
            store,
            DockerCommandBuilder(settings),
            runner,
        )

        await coordinator.start_run("sha256:abc", "stand-01", "smoke")
        await _wait_for_terminal(store)
        state = store.read()

        assert state is not None
        assert state.status is OperationStatus.FAILED
        assert state.summary is not None
        assert state.summary.failed == 1
        assert state.artifact_directory is not None

    asyncio.run(exercise())


async def _wait_for_terminal(store: StateStore) -> None:
    for _ in range(100):
        state = store.read()
        if state is not None and state.status.is_terminal:
            return
        await asyncio.sleep(0.001)
    raise AssertionError("operation did not finish")
