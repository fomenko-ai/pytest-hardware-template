"""Serial device ownership and request dispatch for the remote agent."""

from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Protocol, cast

import serial

from hardware_serial_agent import __version__
from hardware_serial_agent.protocol import (
    MAX_READ_BYTES,
    AgentError,
    Request,
    Response,
    decode_payload,
    encode_payload,
    require_int,
    require_string,
    require_timeout,
    success,
    validate_envelope,
    validate_fields,
)


class SerialConnection(Protocol):
    """Subset of pyserial used by the agent and its fakes."""

    timeout: float | None

    def read(self, size: int) -> bytes: ...

    def write(self, data: bytes) -> int | None: ...

    def reset_input_buffer(self) -> None: ...

    def reset_output_buffer(self) -> None: ...

    def close(self) -> None: ...


type SerialFactory = Callable[..., SerialConnection]


class SerialAgent:
    """Own one serial device and execute validated protocol operations."""

    def __init__(self, serial_factory: SerialFactory | None = None) -> None:
        self._serial_factory = serial_factory or cast(SerialFactory, serial.Serial)
        self._connection: SerialConnection | None = None

    def handle(self, request: Request) -> tuple[Response, bool]:
        """Handle one validated request and report whether the process should stop."""
        operation = validate_envelope(request)
        try:
            if operation == "hello":
                validate_fields(request, required=set())
                return success(agent_version=__version__), False
            if operation == "open":
                return self._open(request), False
            if operation == "write":
                return self._write(request), False
            if operation == "read":
                return self._read(request), False
            if operation == "reset_input":
                return self._reset_input(request), False
            if operation == "reset_output":
                return self._reset_output(request), False
            if operation == "close":
                validate_fields(request, required=set())
                self.close()
                return success(), True
            raise AgentError("unknown_operation", f"Unsupported operation: {operation}")
        except (serial.SerialException, OSError) as error:
            raise AgentError("serial_io", f"Serial operation failed: {error}") from error

    def close(self) -> None:
        """Close the owned device if it is open."""
        connection = self._connection
        self._connection = None
        if connection is not None:
            connection.close()

    def _open(self, request: Request) -> Response:
        validate_fields(request, required={"device", "baudrate"})
        if self._connection is not None:
            raise AgentError("already_open", "A serial device is already open")
        device = self._validate_device(require_string(request, "device"))
        baudrate = require_int(request, "baudrate", minimum=1, maximum=10_000_000)
        if not Path(device).is_char_device():
            raise AgentError("invalid_device", f"Serial device is not a character device: {device}")
        self._connection = self._serial_factory(
            port=device,
            baudrate=baudrate,
            timeout=0.0,
            write_timeout=30.0,
            exclusive=True,
        )
        return success()

    def _write(self, request: Request) -> Response:
        validate_fields(request, required={"data"})
        connection = self._require_connection()
        payload = decode_payload(request)
        written = connection.write(payload)
        return success(written=len(payload) if written is None else written)

    def _read(self, request: Request) -> Response:
        validate_fields(request, required={"size", "timeout"})
        connection = self._require_connection()
        size = require_int(request, "size", minimum=1, maximum=MAX_READ_BYTES)
        connection.timeout = require_timeout(request)
        return success(data=encode_payload(connection.read(size)))

    def _reset_input(self, request: Request) -> Response:
        validate_fields(request, required=set())
        self._require_connection().reset_input_buffer()
        return success()

    def _reset_output(self, request: Request) -> Response:
        validate_fields(request, required=set())
        self._require_connection().reset_output_buffer()
        return success()

    def _require_connection(self) -> SerialConnection:
        if self._connection is None:
            raise AgentError("not_open", "No serial device is open")
        return self._connection

    @staticmethod
    def _validate_device(value: str) -> str:
        if any(character in value for character in "\0\r\n"):
            raise AgentError("invalid_device", "device must not contain control characters")
        path = PurePosixPath(value)
        if (
            not path.is_absolute()
            or path == PurePosixPath("/dev")
            or not path.is_relative_to("/dev")
            or ".." in path.parts
        ):
            raise AgentError("invalid_device", "device must be an absolute path below /dev")
        return value
