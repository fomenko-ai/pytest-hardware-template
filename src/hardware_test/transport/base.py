"""Interface implemented by device communication transports."""

from typing import Protocol, runtime_checkable

from hardware_test.models import Command, CommandResult


@runtime_checkable
class Transport(Protocol):
    """Minimal synchronous transport contract used by device APIs."""

    def connect(self) -> None: ...

    def close(self) -> None: ...

    def execute(self, command: Command[str] | Command[bytes]) -> CommandResult: ...
