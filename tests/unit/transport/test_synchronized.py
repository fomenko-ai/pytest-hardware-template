"""Synchronized transport tests."""

from threading import Event, Thread

from hardware_test.models import Command, CommandResult, UnixCommand
from hardware_test.transport import SynchronizedTransport


class BlockingTransport:
    """Transport that keeps its first command active until released."""

    def __init__(self) -> None:
        self.commands: list[Command[str] | Command[bytes]] = []
        self.first_started = Event()
        self.release_first = Event()

    def connect(self) -> None:
        pass

    def close(self) -> None:
        pass

    def execute(self, command: Command[str] | Command[bytes]) -> CommandResult:
        self.commands.append(command)
        if len(self.commands) == 1:
            self.first_started.set()
            assert self.release_first.wait(timeout=1.0)
        return CommandResult(stdout="ok", stderr="", exit_code=0)


def test_execute_serializes_commands() -> None:
    wrapped_transport = BlockingTransport()
    transport = SynchronizedTransport(wrapped_transport)
    first = UnixCommand("first")
    second = UnixCommand("second")
    second_attempted = Event()

    first_thread = Thread(target=transport.execute, args=(first,))

    def execute_second() -> None:
        second_attempted.set()
        transport.execute(second)

    second_thread = Thread(target=execute_second)
    first_thread.start()
    assert wrapped_transport.first_started.wait(timeout=1.0)
    second_thread.start()
    assert second_attempted.wait(timeout=1.0)

    assert wrapped_transport.commands == [first]

    wrapped_transport.release_first.set()
    first_thread.join(timeout=1.0)
    second_thread.join(timeout=1.0)

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert wrapped_transport.commands == [first, second]


def test_exclusive_context_allows_commands_from_owner() -> None:
    wrapped_transport = BlockingTransport()
    wrapped_transport.release_first.set()
    transport = SynchronizedTransport(wrapped_transport)
    command = UnixCommand("status")

    with transport.exclusive():
        result = transport.execute(command)

    assert result.exit_code == 0
    assert wrapped_transport.commands == [command]


def test_exclusive_context_blocks_commands_from_other_threads() -> None:
    wrapped_transport = BlockingTransport()
    wrapped_transport.release_first.set()
    transport = SynchronizedTransport(wrapped_transport)
    command = UnixCommand("status")
    attempted = Event()
    finished = Event()

    def execute() -> None:
        attempted.set()
        transport.execute(command)
        finished.set()

    thread = Thread(target=execute)
    with transport.exclusive():
        thread.start()
        assert attempted.wait(timeout=1.0)
        assert not finished.wait(timeout=0.05)
        assert wrapped_transport.commands == []

    thread.join(timeout=1.0)

    assert not thread.is_alive()
    assert finished.is_set()
    assert wrapped_transport.commands == [command]
