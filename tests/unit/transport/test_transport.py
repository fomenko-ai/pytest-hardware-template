"""SSH transport unit tests with the client library isolated."""

import pytest
from pydantic import SecretStr

from hardware_test.transport.ssh import SSHTransport


def test_ssh_transport_requires_connection() -> None:
    transport = SSHTransport(
        host="192.0.2.10",
        port=22,
        username="tester",
        password=SecretStr("secret"),
        connect_timeout=1.0,
        command_timeout=2.0,
    )

    with pytest.raises(RuntimeError, match="not connected"):
        transport.execute("example")
