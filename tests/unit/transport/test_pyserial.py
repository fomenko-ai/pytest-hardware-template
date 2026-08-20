"""Direct pyserial transport tests without a physical serial device."""

from collections.abc import Callable
from typing import cast

import pytest
import serial
from pydantic import SecretStr

from hardware_test.exceptions import TransportError
from hardware_test.transport.config import ConsoleSessionConfig
from hardware_test.transport.pyserial import PySerialChannel, PySerialTransport, SerialConnection

AUTH_PROMPT = "Password:"


class FakeSerialConnection:
    def __init__(self, *, incoming: bytes = b"", chunk_size: int | None = None) -> None:
        self.is_open = True
        self.incoming = bytearray(incoming)
        self.written = bytearray()
        self.chunk_size = chunk_size
        self.write_handler: Callable[[bytes], int] | None = None

    @property
    def in_waiting(self) -> int:
        return len(self.incoming)

    def read(self, size: int = 1) -> bytes:
        result = bytes(self.incoming[:size])
        del self.incoming[:size]
        return result

    def write(self, data: bytes) -> int:
        if self.write_handler is not None:
            return self.write_handler(data)
        size = min(len(data), self.chunk_size or len(data))
        self.written.extend(data[:size])
        return size

    def close(self) -> None:
        self.is_open = False


def test_pyserial_channel_completes_partial_writes_and_reads_available_data() -> None:
    connection = FakeSerialConnection(incoming=b"console", chunk_size=2)
    channel = PySerialChannel(cast(SerialConnection, connection))

    channel.sendall(b"command")

    assert bytes(connection.written) == b"command"
    assert channel.recv_ready()
    assert channel.recv(4) == b"cons"
    assert channel.recv(10) == b"ole"


def test_pyserial_channel_closes_idempotently() -> None:
    connection = FakeSerialConnection()
    channel = PySerialChannel(cast(SerialConnection, connection))

    channel.close()
    channel.close()

    assert channel.closed


def test_pyserial_channel_wraps_serial_errors() -> None:
    connection = FakeSerialConnection()

    def fail(_: bytes) -> int:
        raise serial.SerialException("disconnected")

    connection.write_handler = fail

    with pytest.raises(TransportError, match="Serial write failed"):
        PySerialChannel(cast(SerialConnection, connection)).sendall(b"command")


def test_pyserial_transport_opens_and_prepares_console(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeSerialConnection(incoming=b"root@board:~# ")
    opened_with: dict[str, object] = {}

    def open_serial(**kwargs: object) -> FakeSerialConnection:
        opened_with.update(kwargs)
        return connection

    monkeypatch.setattr(serial, "Serial", open_serial)
    transport = PySerialTransport(
        serial_device="/dev/ttyACM0",
        baudrate=115200,
        console=ConsoleSessionConfig(
            prompt="__HARDWARE_TEST_PROMPT__# ",
            initial_prompt_suffix="# ",
            login_prompt="login:",
            password_prompt=AUTH_PROMPT,
            username="root",
            password=SecretStr("secret"),
        ),
        connect_timeout=0.1,
        command_timeout=0.1,
    )

    def respond_to_prompt(data: bytes) -> int:
        connection.written += data
        if data.startswith(b"export PS1="):
            connection.incoming.extend(b"__HARDWARE_TEST_PROMPT__# ")
        return len(data)

    connection.write_handler = respond_to_prompt

    transport.connect()
    transport.close()

    assert opened_with == {
        "port": "/dev/ttyACM0",
        "baudrate": 115200,
        "timeout": 0.0,
        "write_timeout": 0.1,
        "exclusive": True,
    }
    assert b"export PS1='__HARDWARE_TEST_PROMPT__# '\r" in connection.written
    assert not connection.is_open
