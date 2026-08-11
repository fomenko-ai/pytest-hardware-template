"""Transport command contract integration test using a fake."""

from hardware_test.models import CommandResult
from tests.fakes import FakeTransport


def test_fake_transport_preserves_command_result() -> None:
    expected = CommandResult(stdout="ready\n", stderr="", exit_code=0)
    transport = FakeTransport(expected)

    result = transport.execute("example status", timeout=3.0)

    assert result == expected
    assert transport.commands == [("example status", 3.0)]
