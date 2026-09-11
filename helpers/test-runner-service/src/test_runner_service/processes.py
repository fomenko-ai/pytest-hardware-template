import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

MAX_CAPTURED_OUTPUT = 65_536


@dataclass(frozen=True)
class ProcessResult:
    exit_code: int
    output: str


class ProcessRunner(Protocol):
    async def run(
        self,
        command: tuple[str, ...],
        log_file: Path,
        environment: dict[str, str] | None = None,
    ) -> ProcessResult: ...

    async def cancel(self, container_name: str | None) -> None: ...


class AsyncioProcessRunner:
    def __init__(self) -> None:
        self._process: asyncio.subprocess.Process | None = None

    async def run(
        self,
        command: tuple[str, ...],
        log_file: Path,
        environment: dict[str, str] | None = None,
    ) -> ProcessResult:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=os.environ | environment if environment is not None else None,
        )
        self._process = process
        output = ""
        try:
            if process.stdout is None:
                raise RuntimeError("subprocess output pipe is unavailable")
            with log_file.open("a", encoding="utf-8") as stream:
                while line := await process.stdout.readline():
                    text = line.decode(errors="replace")
                    stream.write(text)
                    stream.flush()
                    output = f"{output}{text}"[-MAX_CAPTURED_OUTPUT:]
            exit_code = await process.wait()
            return ProcessResult(exit_code=exit_code, output=output)
        finally:
            self._process = None

    async def cancel(self, container_name: str | None) -> None:
        if container_name is not None:
            stop = await asyncio.create_subprocess_exec(
                "docker",
                "stop",
                container_name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await stop.wait()
        process = self._process
        if process is not None and process.returncode is None:
            process.terminate()
