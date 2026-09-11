from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from test_runner_service.api import create_router
from test_runner_service.auth import AuthenticationMiddleware, create_auth_router
from test_runner_service.docker_commands import DockerCommandBuilder, validate_required_paths
from test_runner_service.processes import AsyncioProcessRunner, ProcessRunner
from test_runner_service.settings import Settings
from test_runner_service.state import StateStore
from test_runner_service.worker import OperationCoordinator


def create_app(
    settings: Settings | None = None,
    process_runner: ProcessRunner | None = None,
) -> FastAPI:
    runtime_settings = settings or Settings()
    state_store = StateStore(runtime_settings.state_directory)
    runner = process_runner or AsyncioProcessRunner()
    coordinator = OperationCoordinator(
        runtime_settings,
        state_store,
        DockerCommandBuilder(runtime_settings),
        runner,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        state_store.initialize()
        validate_required_paths(runtime_settings)
        state_store.mark_interrupted()
        try:
            yield
        finally:
            await coordinator.shutdown()

    app = FastAPI(
        title="Hardware Test Runner",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(create_router(coordinator, state_store, runtime_settings))
    static_directory = Path(__file__).parent / "static"
    html = static_directory / "index.html"
    artifact_runs_html = static_directory / "artifact-runs.html"
    app.include_router(create_auth_router(runtime_settings, static_directory / "login.html"))
    app.add_middleware(AuthenticationMiddleware, settings=runtime_settings)

    @app.get("/", response_class=FileResponse, include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(html)

    @app.get("/artifact-runs", response_class=FileResponse, include_in_schema=False)
    async def artifact_runs() -> FileResponse:
        return FileResponse(artifact_runs_html)

    return app
