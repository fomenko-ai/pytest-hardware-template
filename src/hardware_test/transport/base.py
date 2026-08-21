"""Interface implemented by device communication transports."""

from contextlib import AbstractContextManager
from typing import Protocol, runtime_checkable

from hardware_test.models import Command, CommandResult


@runtime_checkable
class Transport(Protocol):
    """Synchronous I/O contract implemented by concrete transports."""

    def connect(self) -> None: ...

    def close(self) -> None: ...

    def execute(self, command: Command[str] | Command[bytes]) -> CommandResult: ...


class LockableTransport(Transport, Protocol):
    """Transport contract supporting exclusive access for device APIs."""

    def exclusive(self) -> AbstractContextManager[None]: ...
