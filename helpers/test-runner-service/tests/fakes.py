import asyncio
from collections import deque
from pathlib import Path

from test_runner_service.processes import ProcessResult


class FakeProcessRunner:
    def __init__(self, results: list[ProcessResult] | None = None) -> None:
        self.results = deque(results or [])
        self.commands: list[tuple[str, ...]] = []
        self.environments: list[dict[str, str] | None] = []
        self.cancelled_containers: list[str | None] = []
        self.block = False
        self.release = asyncio.Event()

    async def run(
        self,
        command: tuple[str, ...],
        log_file: Path,
        environment: dict[str, str] | None = None,
    ) -> ProcessResult:
        self.commands.append(command)
        self.environments.append(environment)
        with log_file.open("a", encoding="utf-8") as stream:
            stream.write(f"$ {' '.join(command)}\n")
        if self.block:
            await self.release.wait()
        return self.results.popleft() if self.results else ProcessResult(0, "")

    async def cancel(self, container_name: str | None) -> None:
        self.cancelled_containers.append(container_name)
        self.release.set()
