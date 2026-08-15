"""Client and ConsoleChannel adapter for the remote serial agent protocol."""

import base64
import binascii
import json
import time

import paramiko

from hardware_test.exceptions import TransportError, TransportTimeoutError

_PROTOCOL_VERSION = 1
_MAX_RESPONSE_BYTES = 1_048_576
_READ_SIZE = 65_535
_READ_TIMEOUT = 0.05
_POLL_INTERVAL = 0.01


class SerialAgentChannel:
    """Expose synchronous serial-agent requests as a byte-oriented console channel."""

    def __init__(self, channel: paramiko.Channel, request_timeout: float) -> None:
        self._channel = channel
        self._request_timeout = request_timeout
        self._response_buffer = bytearray()
        self._serial_buffer = bytearray()

    @property
    def closed(self) -> bool:
        return self._channel.closed or self._channel.exit_status_ready()

    def negotiate(self) -> str:
        """Verify the protocol and return the installed agent version."""
        response = self._request("hello")
        agent_version = response.get("agent_version")
        if not isinstance(agent_version, str) or not agent_version:
            raise TransportError("Serial agent returned an invalid version")
        return agent_version

    def open(self, device: str, baudrate: int) -> None:
        """Ask the agent to open one remote serial device."""
        self._request("open", device=device, baudrate=baudrate)

    def sendall(self, s: bytes) -> None:
        """Write one complete byte payload through the agent."""
        response = self._request("write", data=base64.b64encode(s).decode("ascii"))
        written = response.get("written")
        if isinstance(written, bool) or not isinstance(written, int) or written != len(s):
            raise TransportError(
                f"Serial agent reported a partial write: expected {len(s)}, got {written!r}"
            )

    def recv_ready(self) -> bool:
        if self._serial_buffer:
            return True
        if self.closed:
            return False
        response = self._request("read", size=_READ_SIZE, timeout=_READ_TIMEOUT)
        encoded = response.get("data")
        if not isinstance(encoded, str):
            raise TransportError("Serial agent returned invalid read data")
        try:
            self._serial_buffer.extend(base64.b64decode(encoded, validate=True))
        except (ValueError, binascii.Error) as error:
            raise TransportError("Serial agent returned invalid Base64 data") from error
        return bool(self._serial_buffer)

    def recv(self, nbytes: int) -> bytes:
        size = min(nbytes, len(self._serial_buffer))
        result = bytes(self._serial_buffer[:size])
        del self._serial_buffer[:size]
        return result

    def exit_status_ready(self) -> bool:
        return self._channel.exit_status_ready()

    def reset_input(self) -> None:
        """Discard local and agent-side buffered input."""
        self._serial_buffer.clear()
        self._request("reset_input")

    def close(self) -> None:
        """Request a clean agent shutdown and always close the SSH channel."""
        try:
            if not self.closed:
                self._request("close")
        except TransportError:
            pass
        finally:
            self._channel.close()

    def _request(self, operation: str, **values: object) -> dict[str, object]:
        if self.closed:
            raise TransportError(f"Serial agent exited before operation {operation!r}")
        request = {"version": _PROTOCOL_VERSION, "operation": operation, **values}
        self._channel.sendall(f"{json.dumps(request, separators=(',', ':'))}\n".encode())
        response = self._read_response(operation)
        if response.get("version") != _PROTOCOL_VERSION:
            raise TransportError("Serial agent returned an unsupported protocol version")
        if response.get("ok") is not True:
            raise TransportError(self._error_message(response, operation))
        return response

    def _read_response(self, operation: str) -> dict[str, object]:
        deadline = time.monotonic() + self._request_timeout
        while time.monotonic() < deadline:
            newline = self._response_buffer.find(b"\n")
            if newline >= 0:
                line = bytes(self._response_buffer[:newline])
                del self._response_buffer[: newline + 1]
                return self._decode_response(line)
            if self._channel.recv_ready():
                self._response_buffer.extend(self._channel.recv(65_535))
                if len(self._response_buffer) > _MAX_RESPONSE_BYTES:
                    raise TransportError("Serial agent response is too large")
            elif self._channel.exit_status_ready():
                raise TransportError(f"Serial agent exited during operation {operation!r}")
            else:
                time.sleep(_POLL_INTERVAL)
        raise TransportTimeoutError(f"Serial agent operation {operation!r} timed out")

    @staticmethod
    def _decode_response(line: bytes) -> dict[str, object]:
        try:
            value: object = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise TransportError("Serial agent returned invalid JSON") from error
        if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
            raise TransportError("Serial agent response must be a JSON object")
        return value

    @staticmethod
    def _error_message(response: dict[str, object], operation: str) -> str:
        error = response.get("error")
        if isinstance(error, dict):
            code = error.get("code")
            message = error.get("message")
            if isinstance(code, str) and isinstance(message, str):
                return f"Serial agent {code} during {operation!r}: {message}"
        return f"Serial agent rejected operation {operation!r}"
