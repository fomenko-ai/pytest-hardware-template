import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse

from test_runner_service.artifacts import (
    list_artifact_runs,
    list_artifacts,
    resolve_artifact,
    resolve_run_directory,
)
from test_runner_service.docker_commands import InvalidImageReferenceError
from test_runner_service.models import (
    AcceptedOperation,
    ArtifactList,
    ArtifactRunList,
    BuildImageRequest,
    OperationState,
    PullImageRequest,
    RunTestsRequest,
    UiConfig,
)
from test_runner_service.reportportal import launches_url
from test_runner_service.settings import Settings
from test_runner_service.state import StateStore
from test_runner_service.worker import (
    NoActiveOperationError,
    OperationCoordinator,
    RunnerBusyError,
)


def create_router(
    coordinator: OperationCoordinator,
    state_store: StateStore,
    settings: Settings,
) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/v1/current", response_model=OperationState | None)
    async def current() -> OperationState | None:
        return state_store.read()

    @router.get("/v1/config", response_model=UiConfig)
    async def ui_config() -> UiConfig:
        config = UiConfig(reportportal_launches_url=launches_url(settings))
        if settings.allure_enabled and settings.allure_public_url is not None:
            query = urlencode({"repo": settings.allure_repository})
            base_url = str(settings.allure_public_url).rstrip("/")
            config.allure_reports_url = f"{base_url}/reports/tree?{query}"
        return config

    @router.post(
        "/v1/images/build",
        response_model=AcceptedOperation,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def build_image(request: BuildImageRequest) -> AcceptedOperation:
        try:
            return await coordinator.start_build(request.revision)
        except RunnerBusyError as error:
            raise _busy_error(error) from error

    @router.post(
        "/v1/images/pull",
        response_model=AcceptedOperation,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def pull_image(request: PullImageRequest) -> AcceptedOperation:
        try:
            return await coordinator.start_pull(request.reference)
        except InvalidImageReferenceError as error:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error
        except RunnerBusyError as error:
            raise _busy_error(error) from error

    @router.post(
        "/v1/runs",
        response_model=AcceptedOperation,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def run_tests(request: RunTestsRequest) -> AcceptedOperation:
        try:
            return await coordinator.start_run(request.image, request.stand, request.scenario)
        except InvalidImageReferenceError as error:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error
        except RunnerBusyError as error:
            raise _busy_error(error) from error

    @router.post("/v1/current/cancel", response_model=OperationState)
    async def cancel() -> OperationState:
        try:
            return await coordinator.cancel()
        except NoActiveOperationError as error:
            raise HTTPException(status.HTTP_409_CONFLICT, "no active operation") from error

    @router.get("/v1/current/events")
    async def events() -> StreamingResponse:
        return StreamingResponse(
            _event_stream(state_store, settings.log_poll_interval_seconds),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @router.get("/v1/current/artifacts", response_model=ArtifactList)
    async def artifacts() -> ArtifactList:
        run_directory = _current_artifact_directory(state_store, settings)
        return list_artifacts(run_directory)

    @router.get("/v1/current/artifacts/{name}", response_class=FileResponse)
    async def artifact(name: str) -> FileResponse:
        run_directory = _current_artifact_directory(state_store, settings)
        path = resolve_artifact(run_directory, name)
        if path is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "artifact not found")
        if name == "report.html":
            return FileResponse(path)
        return FileResponse(path, filename=name)

    @router.get("/v1/artifact-runs", response_model=ArtifactRunList)
    async def artifact_runs() -> ArtifactRunList:
        return list_artifact_runs(settings.artifacts_directory)

    @router.get("/v1/artifact-runs/{run_id}/{name}", response_class=FileResponse)
    async def historical_artifact(run_id: str, name: str) -> FileResponse:
        run_directory = resolve_run_directory(settings.artifacts_directory, run_id)
        if run_directory is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "artifact run not found")
        path = resolve_artifact(run_directory, name)
        if path is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "artifact not found")
        if name == "report.html":
            return FileResponse(path)
        return FileResponse(path, filename=name)

    return router


def _busy_error(error: RunnerBusyError) -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        {
            "code": "runner_busy",
            "message": str(error),
            "operation_id": error.state.operation_id,
        },
    )


def _current_artifact_directory(state_store: StateStore, settings: Settings) -> Path:
    state = state_store.read()
    if state is None or state.artifact_directory is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "the current operation has no artifacts")
    path = Path(state.artifact_directory).resolve()
    artifacts_root = settings.artifacts_directory.resolve()
    if not path.is_relative_to(artifacts_root) or not path.is_dir():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "artifact directory is unavailable")
    return path


async def _event_stream(state_store: StateStore, poll_interval: float) -> AsyncIterator[str]:
    initial = state_store.read()
    operation_id = initial.operation_id if initial is not None else None
    offset = 0
    while True:
        try:
            with state_store.log_file.open("r", encoding="utf-8", errors="replace") as stream:
                stream.seek(offset)
                while line := stream.readline():
                    offset = stream.tell()
                    yield _sse(
                        "output", {"operation_id": operation_id, "text": line.rstrip("\n")}, offset
                    )
        except FileNotFoundError:
            pass

        state = state_store.read()
        if state is not None and state.operation_id != operation_id:
            yield _sse("reset", {"operation_id": state.operation_id}, 0)
            return
        if state is None or state.status.is_terminal:
            if state is not None:
                yield _sse("status", state.model_dump(mode="json"))
            return
        await asyncio.sleep(poll_interval)


def _sse(event: str, data: object, event_id: int | None = None) -> str:
    fields = []
    if event_id is not None:
        fields.append(f"id: {event_id}")
    fields.extend((f"event: {event}", f"data: {json.dumps(data, ensure_ascii=False)}", ""))
    return "\n".join(fields) + "\n"
