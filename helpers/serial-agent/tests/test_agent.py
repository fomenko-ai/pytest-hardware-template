"""Standalone serial-agent tests without physical equipment."""

import base64
from pathlib import Path
from typing import cast

import pytest

from hardware_serial_agent.agent import SerialAgent, SerialConnection
from hardware_serial_agent.protocol import AgentError, Request


class FakeSerialConnection:
    def __init__(self) -> None:
        self.timeout: float | None = None
        self.written = b""
        self.closed = False

    def read(self, size: int) -> bytes:
        return b"device output"[:size]

    def write(self, data: bytes) -> int:
        self.written += data
        return len(data)

    def reset_input_buffer(self) -> None:
        pass

    def reset_output_buffer(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


def _request(operation: str, **values: object) -> Request:
    return cast(Request, {"version": 1, "operation": operation, **values})


def test_agent_opens_device_and_transfers_data(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeSerialConnection()
    created: list[dict[str, object]] = []

    def create_connection(**kwargs: object) -> SerialConnection:
        created.append(kwargs)
        return cast(SerialConnection, connection)

    monkeypatch.setattr(Path, "is_char_device", lambda _: True)
    agent = SerialAgent(create_connection)

    response, _ = agent.handle(_request("open", device="/dev/ttyUSB0", baudrate=115200))
    write_response, _ = agent.handle(
        _request("write", data=base64.b64encode(b"status\r").decode("ascii"))
    )
    read_response, _ = agent.handle(_request("read", size=6, timeout=0.25))
    _, should_stop = agent.handle(_request("close"))

    assert response["ok"] is True
    assert created == [
        {
            "port": "/dev/ttyUSB0",
            "baudrate": 115200,
            "timeout": 0.0,
            "write_timeout": 30.0,
            "exclusive": True,
        }
    ]
    assert write_response["written"] == 7
    assert connection.written == b"status\r"
    assert read_response["data"] == base64.b64encode(b"device").decode("ascii")
    assert connection.timeout == 0.25
    assert should_stop
    assert connection.closed


def test_agent_rejects_io_before_open() -> None:
    agent = SerialAgent()

    with pytest.raises(AgentError) as raised:
        agent.handle(_request("read", size=1, timeout=0.0))

    assert raised.value.code == "not_open"
