"""Shared Linux shell session over a byte-oriented console channel."""

import re
import shlex
import time
from typing import Protocol
from uuid import uuid4

from pydantic import SecretStr

from hardware_test.exceptions import TransportError, TransportTimeoutError
from hardware_test.models import CommandResult, UnixCommand

_POLL_INTERVAL = 0.01


class ConsoleChannel(Protocol):
    """Minimal byte-channel behavior required by a Linux console session."""

    @property
    def closed(self) -> bool: ...

    def sendall(self, s: bytes) -> None: ...

    def recv_ready(self) -> bool: ...

    def recv(self, nbytes: int) -> bytes: ...

    def exit_status_ready(self) -> bool: ...


class LinuxConsoleSession:
    """Authenticate and execute commands in one persistent Linux console shell."""

    def __init__(
        self,
        channel: ConsoleChannel,
        prompt: str,
        initial_prompt_suffix: str,
        login_prompt: str,
        password_prompt: str,
        console_username: str | None,
        console_password: SecretStr | None,
        connect_timeout: float,
        command_timeout: float,
    ) -> None:
        self._channel = channel
        self._prompt = prompt
        self._initial_prompt_suffix = initial_prompt_suffix
        self._login_prompt = login_prompt
        self._password_prompt = password_prompt
        self._console_username = console_username
        self._console_password = console_password
        self._connect_timeout = connect_timeout
        self._command_timeout = command_timeout

    def prepare(self) -> None:
        """Detect the console state, authenticate when needed, and set PS1."""
        self._channel.sendall(b"\r")
        state = self._read_console_state()
        if state == self._prompt:
            return
        if state == self._login_prompt:
            self._send_console_username()
            state = self._read_console_state()
        if state == self._password_prompt:
            self._send_console_password()
            state = self._read_console_state(redact_password=True)
        if state in {self._login_prompt, self._password_prompt}:
            raise TransportError("Device console authentication failed")
        if state != self._initial_prompt_suffix and state != self._prompt:
            raise TransportError("Device console did not reach a recognized shell prompt")
        if state != self._prompt:
            self._channel.sendall(f"export PS1={shlex.quote(self._prompt)}\r".encode())
            self._read_until_any((self._prompt,), self._connect_timeout, "shell prompt")

    def execute(self, command: UnixCommand) -> CommandResult:
        """Execute one shell command and parse its output and exit status."""
        if self._channel.closed:
            raise RuntimeError("Console channel is closed")

        token = f"__HARDWARE_TEST_EXIT_{uuid4().hex}__"
        status_name = f"__hardware_test_status_{uuid4().hex}"
        submitted = (
            f"eval {shlex.quote(command.text)}; {status_name}=$?; "
            f"PS1={shlex.quote(self._prompt)}; "
            f"printf '\\n{token}%s\\n' \"${status_name}\""
        )
        self._channel.sendall(f"{submitted}\r".encode())

        response, exit_code = self._read_command_response(
            token,
            command.timeout if command.timeout is not None else self._command_timeout,
        )
        return CommandResult(
            stdout=self._remove_echo(response, submitted),
            stderr="",
            exit_code=exit_code,
        )

    def _read_console_state(self, *, redact_password: bool = False) -> str:
        markers = (
            self._prompt,
            self._login_prompt,
            self._password_prompt,
            self._initial_prompt_suffix,
        )
        return self._read_until_any(
            markers,
            self._connect_timeout,
            "device console state",
            redact_password=redact_password,
        )

    def _send_console_username(self) -> None:
        if self._console_username is None or self._console_password is None:
            raise TransportError(
                "Device console requires login, but console credentials are not configured"
            )
        self._channel.sendall(f"{self._console_username}\r".encode())

    def _send_console_password(self) -> None:
        if self._console_password is None:
            raise TransportError(
                "Device console requires a password, but console credentials are not configured"
            )
        self._channel.sendall(f"{self._console_password.get_secret_value()}\r".encode())

    def _read_until_any(
        self,
        markers: tuple[str, ...],
        timeout: float,
        context: str,
        *,
        redact_password: bool = False,
    ) -> str:
        buffer = bytearray()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._channel.recv_ready():
                buffer.extend(self._channel.recv(65535))
                normalized = self._normalize_bytes(buffer).decode(errors="replace")
                for marker in markers:
                    if normalized.endswith(marker):
                        return marker
            elif self._channel.exit_status_ready():
                raise TransportError(f"Console channel closed while waiting for {context}")
            else:
                time.sleep(_POLL_INTERVAL)
        partial = self._normalize_bytes(buffer).decode(errors="replace")
        if redact_password:
            partial = self._redact_console_password(partial)
        raise TransportTimeoutError(f"Timed out waiting for {context}; received: {partial!r}")

    def _read_command_response(self, token: str, timeout: float) -> tuple[str, int]:
        marker = re.compile(rf"\n{re.escape(token)}(-?\d+)\n")
        buffer = bytearray()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._channel.recv_ready():
                buffer.extend(self._channel.recv(65535))
                normalized = self._normalize_bytes(buffer).decode(errors="replace")
                match = marker.search(normalized)
                if match is not None and normalized[match.end() :].endswith(self._prompt):
                    return normalized[: match.start()], int(match.group(1))
            elif self._channel.exit_status_ready():
                raise TransportError("Console channel closed while a command was running")
            else:
                time.sleep(_POLL_INTERVAL)

        partial = self._normalize_bytes(buffer).decode(errors="replace")
        raise TransportTimeoutError(f"Console command timed out; received: {partial!r}")

    @staticmethod
    def _normalize_bytes(value: bytes | bytearray) -> bytes:
        return bytes(value).replace(b"\r\n", b"\n").replace(b"\r", b"\n")

    @staticmethod
    def _remove_echo(response: str, submitted: str) -> str:
        normalized = response.lstrip("\n")
        if normalized.startswith(submitted):
            normalized = normalized[len(submitted) :].lstrip("\n")
        return normalized

    def _redact_console_password(self, value: str) -> str:
        if self._console_password is None:
            return value
        return value.replace(self._console_password.get_secret_value(), "**********")
