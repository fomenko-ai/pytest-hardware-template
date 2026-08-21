"""Thread-safe serialization for access to one transport connection."""

from collections.abc import Generator
from contextlib import contextmanager
from threading import RLock

from hardware_test.models import Command, CommandResult
from hardware_test.transport.base import Transport


class SynchronizedTransport:
    """Serialize lifecycle operations and commands for one transport instance."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport
        self._lock = RLock()

    @property
    def transport(self) -> Transport:
        """Return the concrete transport wrapped by this transport."""
        return self._transport

    def connect(self) -> None:
        """Connect while holding exclusive access to the transport."""
        with self._lock:
            self._transport.connect()

    def close(self) -> None:
        """Close while holding exclusive access to the transport."""
        with self._lock:
            self._transport.close()

    def execute(self, command: Command[str] | Command[bytes]) -> CommandResult:
        """Execute one command without interleaving another operation."""
        with self._lock:
            return self._transport.execute(command)

    @contextmanager
    def exclusive(self) -> Generator[None]:
        """Prevent other threads from using the transport within the context."""
        with self._lock:
            yield
