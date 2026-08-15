"""Remote serial-agent channel protocol tests with an in-memory SSH channel."""

import base64
import json
from typing import cast

import paramiko
import pytest

from hardware_test.exceptions import TransportError
from hardware_test.transport.serial_agent import SerialAgentChannel


class FakeSshChannel:
    def __init__(self) -> None:
        self.closed = False
        self.requests: list[dict[str, object]] = []
        self._responses: list[bytes] = []

    def sendall(self, data: bytes) -> None:
        request: object = json.loads(data)
        assert isinstance(request, dict)
        self.requests.append(request)
        operation = request["operation"]
        response: dict[str, object] = {"version": 1, "ok": True}
        if operation == "hello":
            response["agent_version"] = "0.1.0"
        elif operation == "write":
            encoded = request["data"]
            assert isinstance(encoded, str)
            response["written"] = len(base64.b64decode(encoded))
        elif operation == "read":
            response["data"] = base64.b64encode(b"board output").decode("ascii")
        self._responses.append(f"{json.dumps(response)}\n".encode())

    def recv_ready(self) -> bool:
        return bool(self._responses)

    def recv(self, size: int) -> bytes:
        del size
        return self._responses.pop(0)

    def exit_status_ready(self) -> bool:
        return False

    def close(self) -> None:
        self.closed = True


def test_serial_agent_channel_negotiates_and_transfers_bytes() -> None:
    ssh_channel = FakeSshChannel()
    channel = SerialAgentChannel(cast(paramiko.Channel, ssh_channel), request_timeout=0.1)

    assert channel.negotiate() == "0.1.0"
    channel.open("/dev/ttyUSB0", 115200)
    channel.sendall(b"status\r")
    assert channel.recv_ready()
    assert channel.recv(5) == b"board"
    assert channel.recv(100) == b" output"
    channel.close()

    assert [request["operation"] for request in ssh_channel.requests] == [
        "hello",
        "open",
        "write",
        "read",
        "close",
    ]
    assert ssh_channel.closed


def test_serial_agent_channel_reports_structured_agent_error() -> None:
    ssh_channel = FakeSshChannel()
    ssh_channel._responses.append(
        b'{"version":1,"ok":false,"error":{"code":"busy","message":"in use"}}\n'
    )
    channel = SerialAgentChannel(cast(paramiko.Channel, ssh_channel), request_timeout=0.1)

    with pytest.raises(TransportError, match=r"Serial agent busy.*in use"):
        channel.open("/dev/ttyUSB0", 115200)
