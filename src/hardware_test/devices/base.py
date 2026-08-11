"""Shared device lifecycle behavior."""

from hardware_test.transport import Transport


class Device:
    """A physical device accessed through an injected transport."""

    def __init__(self, transport: Transport, model: str) -> None:
        self._transport = transport
        self.model = model

    def connect(self) -> None:
        """Connect the device transport."""
        self._transport.connect()

    def close(self) -> None:
        """Close the device transport."""
        self._transport.close()
