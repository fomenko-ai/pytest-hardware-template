"""Reusable in-memory test doubles for transports."""

from hardware_test.models import Command, CommandResult


class FakeTransport:
    """Transport double that records lifecycle and commands without I/O."""

    def __init__(self, result: CommandResult | None = None) -> None:
        self.connected = False
        self.closed = False
        self.commands: list[Command[str] | Command[bytes]] = []
        self.result = result or CommandResult(stdout="ok", stderr="", exit_code=0)

    def connect(self) -> None:
        self.connected = True

    def close(self) -> None:
        self.closed = True

    def execute(self, command: Command[str] | Command[bytes]) -> CommandResult:
        self.commands.append(command)
        return self.result
