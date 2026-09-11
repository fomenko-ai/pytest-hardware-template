import asyncio
from pathlib import Path

import pytest
from pydantic import SecretStr

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
            async def run(
                self,
                command: tuple[str, ...],
                log_file: Path,
                environment: dict[str, str] | None = None,
            ) -> ProcessResult:
                result = await super().run(command, log_file, environment)
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


@pytest.mark.parametrize(("pytest_exit_code", "expected_status"), [(0, "passed"), (1, "failed")])
def test_allure_report_is_published_without_changing_pytest_outcome(
    settings: Settings,
    pytest_exit_code: int,
    expected_status: str,
) -> None:
    async def exercise() -> None:
        allure_settings = settings.model_copy(
            update={"allure_enabled": True, "allure_access_token": SecretStr("ars1.secret")}
        )
        store = StateStore(settings.state_directory)
        store.initialize()

        class AllureFakeRunner(FakeProcessRunner):
            async def run(
                self,
                command: tuple[str, ...],
                log_file: Path,
                environment: dict[str, str] | None = None,
            ) -> ProcessResult:
                result = await super().run(command, log_file, environment)
                if len(self.commands) == 1:
                    run_directory = settings.artifacts_directory / "allure-run"
                    reports = run_directory / "reports"
                    reports.mkdir(parents=True)
                    (run_directory / "allure-results").mkdir()
                    (reports / "junit.xml").write_text(
                        '<testsuite tests="1" failures="0"/>', encoding="utf-8"
                    )
                return result

        runner = AllureFakeRunner(
            [
                ProcessResult(pytest_exit_code, "pytest output"),
                ProcessResult(0, "Published https://allure.example/reports/abc.\n"),
            ]
        )
        coordinator = OperationCoordinator(
            allure_settings,
            store,
            DockerCommandBuilder(allure_settings),
            runner,
        )

        await coordinator.start_run("sha256:abc", "stand-01", "smoke")
        await _wait_for_terminal(store)
        state = store.read()

        assert state is not None
        assert state.status == expected_status
        assert state.exit_code == pytest_exit_code
        assert state.report_status == "published"
        assert state.report_url == "https://allure.example/reports/abc"
        assert runner.environments[-1] == {"ALLURE_ACCESS_TOKEN": "ars1.secret"}
        assert "ars1.secret" not in " ".join(runner.commands[-1])

    asyncio.run(exercise())


def test_allure_publication_failure_is_reported_separately(settings: Settings) -> None:
    async def exercise() -> None:
        allure_settings = settings.model_copy(
            update={"allure_enabled": True, "allure_access_token": SecretStr("ars1.secret")}
        )
        store = StateStore(settings.state_directory)
        store.initialize()

        class AllureFakeRunner(FakeProcessRunner):
            async def run(
                self,
                command: tuple[str, ...],
                log_file: Path,
                environment: dict[str, str] | None = None,
            ) -> ProcessResult:
                result = await super().run(command, log_file, environment)
                if len(self.commands) == 1:
                    run_directory = settings.artifacts_directory / "allure-run"
                    reports = run_directory / "reports"
                    reports.mkdir(parents=True)
                    (run_directory / "allure-results").mkdir()
                    (reports / "junit.xml").write_text(
                        '<testsuite tests="1" failures="0"/>', encoding="utf-8"
                    )
                return result

        runner = AllureFakeRunner(
            [ProcessResult(0, "pytest output"), ProcessResult(2, "publication failed")]
        )
        coordinator = OperationCoordinator(
            allure_settings,
            store,
            DockerCommandBuilder(allure_settings),
            runner,
        )

        await coordinator.start_run("sha256:abc", "stand-01", "smoke")
        await _wait_for_terminal(store)
        state = store.read()

        assert state is not None
        assert state.status is OperationStatus.PASSED
        assert state.report_status == "failed"
        assert state.report_message == "Allure publication failed; inspect the operation log"

    asyncio.run(exercise())


async def _wait_for_terminal(store: StateStore) -> None:
    for _ in range(100):
        state = store.read()
        if state is not None and state.status.is_terminal:
            return
        await asyncio.sleep(0.001)
    raise AssertionError("operation did not finish")
