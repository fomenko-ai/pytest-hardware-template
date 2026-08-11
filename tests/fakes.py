"""Reusable in-memory test doubles for transports."""

from hardware_test.models import CommandResult


class FakeTransport:
    """Transport double that records lifecycle and commands without I/O."""

    def __init__(self, result: CommandResult | None = None) -> None:
        self.connected = False
        self.closed = False
        self.commands: list[tuple[str, float | None]] = []
        self.result = result or CommandResult(stdout="ok", stderr="", exit_code=0)

    def connect(self) -> None:
        self.connected = True

    def close(self) -> None:
        self.closed = True

    def execute(self, command: str, timeout: float | None = None) -> CommandResult:
        self.commands.append((command, timeout))
        return self.result
