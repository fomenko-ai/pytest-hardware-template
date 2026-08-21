"""Shared device lifecycle behavior."""

from contextlib import AbstractContextManager

from hardware_test.transport import LockableTransport


class Device:
    """A physical device accessed through an injected transport."""

    def __init__(self, transport: LockableTransport, model: str) -> None:
        self._transport = transport
        self.model = model

    def connect(self) -> None:
        """Connect the device transport."""
        self._transport.connect()

    def close(self) -> None:
        """Close the device transport."""
        self._transport.close()

    def exclusive_connection(self) -> AbstractContextManager[None]:
        """Reserve the transport for an uninterrupted sequence of operations."""
        return self._transport.exclusive()
