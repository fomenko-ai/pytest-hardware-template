"""Device command contract integration tests using a fake transport."""

import pytest

from hardware_test.devices import Dut
from hardware_test.models import CommandResult, PowerShellCommand, TextCommand, UnixCommand
from tests.fakes import FakeTransport


@pytest.mark.parametrize(
    "command",
    [
        pytest.param(UnixCommand(query="example status", timeout=3.0), id="unix"),
        pytest.param(PowerShellCommand(query="Get-Service", timeout=3.0), id="powershell"),
    ],
)
def test_dut_preserves_text_command_and_result(command: TextCommand) -> None:
    expected = CommandResult(stdout="ready\n", stderr="", exit_code=0)
    transport = FakeTransport(expected)
    dut = Dut(transport, "example-model")

    result = dut.execute_command(command)

    assert result == expected
    assert transport.commands == [command]
