"""SSH transport unit tests with the client library isolated."""

import pytest
from pydantic import SecretStr

from hardware_test.models import PowerShellCommand, SshHostKeyPolicy, TextCommand, UnixCommand
from hardware_test.transport.config import SshConnectionConfig
from hardware_test.transport.ssh import SSHTransport


@pytest.mark.parametrize(
    "command",
    [
        pytest.param(UnixCommand(query="uname -a"), id="unix"),
        pytest.param(PowerShellCommand(query="Get-Service"), id="powershell"),
    ],
)
def test_ssh_transport_requires_connection(command: TextCommand) -> None:
    transport = SSHTransport(
        ssh=SshConnectionConfig(
            host="192.0.2.10",
            port=22,
            username="tester",
            password=SecretStr("secret"),
            host_key_policy=SshHostKeyPolicy.REJECT,
            known_hosts_path=None,
        ),
        connect_timeout=1.0,
        command_timeout=2.0,
    )

    with pytest.raises(RuntimeError, match="not connected"):
        transport.execute(command)
