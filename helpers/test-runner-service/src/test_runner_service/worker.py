import asyncio
import re
from collections.abc import Coroutine
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from test_runner_service.artifacts import (
    find_result_directory,
    read_junit_summary,
    snapshot_run_directories,
)
from test_runner_service.docker_commands import DockerCommandBuilder
from test_runner_service.models import (
    AcceptedOperation,
    OperationState,
    OperationStatus,
    OperationType,
    ReportStatus,
)
from test_runner_service.processes import ProcessResult, ProcessRunner
from test_runner_service.settings import Settings
from test_runner_service.state import StateStore


class RunnerBusyError(RuntimeError):
    def __init__(self, state: OperationState) -> None:
        super().__init__("another operation is already running")
        self.state = state


class NoActiveOperationError(RuntimeError):
    """Raised when cancellation is requested without an active operation."""


class OperationCoordinator:
    def __init__(
        self,
        settings: Settings,
        state_store: StateStore,
        command_builder: DockerCommandBuilder,
        process_runner: ProcessRunner,
    ) -> None:
        self._settings = settings
        self._state_store = state_store
        self._command_builder = command_builder
        self._process_runner = process_runner
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._cancel_requested = False

    async def start_build(self, revision: str) -> AcceptedOperation:
        operation_id = self._new_id("build")
        state = OperationState.started(
            operation_id,
            OperationType.BUILD_IMAGE,
            OperationStatus.BUILDING,
            message=f"Building configured checkout revision '{revision}'",
        )
        command = self._command_builder.build_image(operation_id)
        reference = self._command_builder.local_build_reference(operation_id)
        await self._start(state, self._execute_image_operation(state, command, reference))
        return self._accepted(state)

    async def start_pull(self, reference: str) -> AcceptedOperation:
        command = self._command_builder.pull_image(reference)
        operation_id = self._new_id("pull")
        state = OperationState.started(
            operation_id,
            OperationType.PULL_IMAGE,
            OperationStatus.PULLING,
            image_reference=reference,
        )
        await self._start(state, self._execute_image_operation(state, command, reference))
        return self._accepted(state)

    async def start_run(self, image: str, stand: str, scenario: str) -> AcceptedOperation:
        operation_id = self._new_id("run")
        container_name = f"hardware-test-run-{operation_id}"
        state = OperationState.started(
            operation_id,
            OperationType.RUN_TESTS,
            OperationStatus.RUNNING,
            image_reference=image,
            stand=stand,
            scenario=scenario,
            container_name=container_name,
        )
        command = self._command_builder.run_tests(operation_id, image, stand, scenario)
        await self._start(state, self._execute_test_run(state, command))
        return self._accepted(state)

    async def cancel(self) -> OperationState:
        async with self._lock:
            state = self._state_store.read()
            if state is None or state.status.is_terminal or self._task is None:
                raise NoActiveOperationError
            self._cancel_requested = True
            await self._process_runner.cancel(state.container_name)
            return state

    async def shutdown(self) -> None:
        task = self._task
        if task is None or task.done():
            return
        state = self._state_store.read()
        await self._process_runner.cancel(state.container_name if state is not None else None)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def _start(self, state: OperationState, work: Coroutine[Any, Any, None]) -> None:
        async with self._lock:
            current = self._state_store.read()
            if self._task is not None and not self._task.done():
                work.close()
                if current is None:
                    raise RuntimeError("active task has no state")
                raise RunnerBusyError(current)
            self._cancel_requested = False
            self._state_store.reset_log()
            self._state_store.write(state)
            self._task = asyncio.create_task(work)

    async def _execute_image_operation(
        self,
        state: OperationState,
        command: tuple[str, ...],
        reference: str,
    ) -> None:
        try:
            result = await self._run_with_timeout(command)
            if self._cancel_requested:
                self._finish(state, OperationStatus.CANCELLED, result.exit_code)
                return
            if result.exit_code != 0:
                self._finish(state, OperationStatus.FAILED, result.exit_code)
                return
            inspect = await self._run_with_timeout(self._command_builder.inspect_image(reference))
            if inspect.exit_code != 0 or not inspect.output.strip():
                self._finish(
                    state,
                    OperationStatus.INFRASTRUCTURE_ERROR,
                    inspect.exit_code,
                    message="The prepared image could not be inspected",
                )
                return
            self._finish(
                state,
                OperationStatus.SUCCEEDED,
                0,
                image_reference=reference,
                image_digest=inspect.output.strip().splitlines()[-1],
            )
        except TimeoutError:
            await self._process_runner.cancel(None)
            self._finish(state, OperationStatus.TIMED_OUT, message="Image operation timed out")
        except Exception as error:
            self._finish(state, OperationStatus.INFRASTRUCTURE_ERROR, message=str(error))

    async def _execute_test_run(
        self,
        state: OperationState,
        command: tuple[str, ...],
    ) -> None:
        previous = snapshot_run_directories(self._settings.artifacts_directory)
        try:
            result = await self._run_with_timeout(command)
            if self._cancel_requested:
                self._finish(state, OperationStatus.CANCELLED, result.exit_code)
                return
            run_directory = find_result_directory(self._settings.artifacts_directory, previous)
            summary = None
            report_updates: dict[str, object] = {}
            if run_directory is not None:
                summary = read_junit_summary(run_directory / "reports" / "junit.xml")
                if self._settings.allure_enabled:
                    report_updates = await self._publish_allure(state, run_directory)
                    if self._cancel_requested:
                        self._finish(
                            state,
                            OperationStatus.CANCELLED,
                            result.exit_code,
                            artifact_directory=str(run_directory),
                            summary=summary,
                            **report_updates,
                        )
                        return
            status = OperationStatus.PASSED if result.exit_code == 0 else OperationStatus.FAILED
            self._finish(
                state,
                status,
                result.exit_code,
                artifact_directory=str(run_directory) if run_directory is not None else None,
                summary=summary,
                **report_updates,
            )
        except TimeoutError:
            await self._process_runner.cancel(state.container_name)
            self._finish(state, OperationStatus.TIMED_OUT, message="Hardware test run timed out")
        except Exception as error:
            self._finish(state, OperationStatus.INFRASTRUCTURE_ERROR, message=str(error))

    async def _publish_allure(
        self,
        state: OperationState,
        run_directory: Path,
    ) -> dict[str, object]:
        results_directory = run_directory / "allure-results"
        if not results_directory.is_dir():
            return {
                "report_status": ReportStatus.FAILED,
                "report_message": "The test image did not create Allure results",
            }

        publisher_name = f"allure-publish-{state.operation_id}"
        publishing = state.model_copy(update={"container_name": publisher_name})
        self._state_store.write(publishing)
        token = self._settings.allure_access_token
        if token is None:
            return {
                "report_status": ReportStatus.FAILED,
                "report_message": "Allure access token is unavailable",
            }
        command = self._command_builder.publish_allure(state.operation_id, run_directory)
        try:
            result = await self._run_with_timeout(
                command,
                {"ALLURE_ACCESS_TOKEN": token.get_secret_value()},
            )
        except TimeoutError:
            await self._process_runner.cancel(publisher_name)
            return {
                "report_status": ReportStatus.FAILED,
                "report_message": "Allure publication timed out",
            }
        except Exception:
            return {
                "report_status": ReportStatus.FAILED,
                "report_message": "Allure publication failed; inspect the operation log",
            }
        if result.exit_code != 0:
            return {
                "report_status": ReportStatus.FAILED,
                "report_message": "Allure publication failed; inspect the operation log",
            }
        return {
            "report_status": ReportStatus.PUBLISHED,
            "report_url": _published_report_url(result.output),
        }

    async def _run_with_timeout(
        self,
        command: tuple[str, ...],
        environment: dict[str, str] | None = None,
    ) -> ProcessResult:
        async with asyncio.timeout(self._settings.operation_timeout_seconds):
            return await self._process_runner.run(command, self._state_store.log_file, environment)

    def _finish(
        self,
        state: OperationState,
        status: OperationStatus,
        exit_code: int | None = None,
        **updates: object,
    ) -> None:
        finished = state.model_copy(
            update={
                "status": status,
                "finished_at": datetime.now(UTC),
                "exit_code": exit_code,
                "container_name": None,
                **updates,
            }
        )
        self._state_store.write(finished)

    @staticmethod
    def _new_id(prefix: str) -> str:
        return f"{prefix}-{uuid4().hex}"

    @staticmethod
    def _accepted(state: OperationState) -> AcceptedOperation:
        return AcceptedOperation(operation_id=state.operation_id, status=state.status)


def _published_report_url(output: str) -> str | None:
    urls = re.findall(r"https?://[^\s]+", output)
    return urls[-1].rstrip(".,;)\"]'") if urls else None
