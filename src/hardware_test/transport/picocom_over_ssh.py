"""Persistent picocom serial console reached through an SSH connection."""

import re
import shlex
import time
from uuid import uuid4

import paramiko
from pydantic import SecretStr

from hardware_test.exceptions import TransportError, TransportTimeoutError
from hardware_test.models import CommandResult

_POLL_INTERVAL = 0.01


class PicocomOverSshTransport:
    """Execute commands in a Linux serial console exposed by remote picocom."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: SecretStr,
        serial_device: str,
        baudrate: int,
        prompt: str,
        initial_prompt_suffix: str,
        login_prompt: str,
        password_prompt: str,
        console_username: str | None,
        console_password: SecretStr | None,
        connect_timeout: float,
        command_timeout: float,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._serial_device = serial_device
        self._baudrate = baudrate
        self._prompt = prompt
        self._initial_prompt_suffix = initial_prompt_suffix
        self._login_prompt = login_prompt
        self._password_prompt = password_prompt
        self._console_username = console_username
        self._console_password = console_password
        self._connect_timeout = connect_timeout
        self._command_timeout = command_timeout
        self._client: paramiko.SSHClient | None = None
        self._channel: paramiko.Channel | None = None

    def connect(self) -> None:
        """Open SSH, start picocom, and establish a deterministic shell prompt."""
        if self._client is not None:
            return

        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        try:
            client.connect(
                hostname=self._host,
                port=self._port,
                username=self._username,
                password=self._password.get_secret_value(),
                timeout=self._connect_timeout,
            )
            self._verify_serial_device(client)
            ssh_transport = client.get_transport()
            if ssh_transport is None or not ssh_transport.is_active():
                raise TransportError("SSH connection became inactive before picocom started")

            channel = ssh_transport.open_session(timeout=self._connect_timeout)
            channel.get_pty()
            channel.exec_command(self._picocom_command())
            self._client = client
            self._channel = channel

            self._prepare_console()
        except Exception:
            if self._channel is not None:
                self._channel.close()
            self._channel = None
            self._client = None
            client.close()
            raise

    def close(self) -> None:
        """Stop picocom and close the SSH resources."""
        channel = self._channel
        client = self._client
        self._channel = None
        self._client = None
        try:
            if channel is not None:
                if not channel.closed:
                    channel.sendall(b"\x01\x18")
                channel.close()
        finally:
            if client is not None:
                client.close()

    def execute(self, command: str, timeout: float | None = None) -> CommandResult:
        """Execute one shell command and parse its output and exit status."""
        channel = self._channel
        if channel is None or channel.closed:
            raise RuntimeError("Picocom-over-SSH transport is not connected")

        token = f"__HARDWARE_TEST_EXIT_{uuid4().hex}__"
        status_name = f"__hardware_test_status_{uuid4().hex}"
        submitted = (
            f"eval {shlex.quote(command)}; {status_name}=$?; "
            f"PS1={shlex.quote(self._prompt)}; "
            f"printf '\\n{token}%s\\n' \"${status_name}\""
        )
        channel.sendall(f"{submitted}\r".encode())

        response, exit_code = self._read_command_response(
            token,
            timeout if timeout is not None else self._command_timeout,
        )
        stdout = self._remove_echo(response, submitted)
        return CommandResult(stdout=stdout, stderr="", exit_code=exit_code)

    def _verify_serial_device(self, client: paramiko.SSHClient) -> None:
        path = shlex.quote(self._serial_device)
        command = f"test -c {path} && test -r {path} && test -w {path}"
        _, stdout, stderr = client.exec_command(command, timeout=self._connect_timeout)
        exit_code = stdout.channel.recv_exit_status()
        if exit_code != 0:
            detail = stderr.read().decode(errors="replace").strip()
            suffix = f": {detail}" if detail else ""
            raise TransportError(f"Serial device is unavailable: {self._serial_device}{suffix}")

    def _picocom_command(self) -> str:
        return f"picocom --quiet --baud {self._baudrate} {shlex.quote(self._serial_device)}"

    def _prepare_console(self) -> None:
        """Detect the console state, authenticate when needed, and set PS1."""
        channel = self._require_channel()
        channel.sendall(b"\r")
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
            channel.sendall(f"export PS1={shlex.quote(self._prompt)}\r".encode())
            self._read_until_prompt(self._connect_timeout)

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
        channel = self._require_channel()
        if self._console_username is None or self._console_password is None:
            raise TransportError(
                "Device console requires login, but console credentials are not configured"
            )
        channel.sendall(f"{self._console_username}\r".encode())

    def _send_console_password(self) -> None:
        channel = self._require_channel()
        if self._console_password is None:
            raise TransportError(
                "Device console requires a password, but console credentials are not configured"
            )
        channel.sendall(f"{self._console_password.get_secret_value()}\r".encode())

    def _read_until_any(
        self,
        markers: tuple[str, ...],
        timeout: float,
        context: str,
        *,
        redact_password: bool = False,
    ) -> str:
        channel = self._require_channel()
        buffer = bytearray()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if channel.recv_ready():
                buffer.extend(channel.recv(65535))
                normalized = self._normalize_bytes(buffer).decode(errors="replace")
                for marker in markers:
                    if normalized.endswith(marker):
                        return marker
            elif channel.exit_status_ready():
                raise TransportError(f"picocom exited while waiting for {context}")
            else:
                time.sleep(_POLL_INTERVAL)
        partial = self._normalize_bytes(buffer).decode(errors="replace")
        if redact_password:
            partial = self._redact_console_password(partial)
        raise TransportTimeoutError(f"Timed out waiting for {context}; received: {partial!r}")

    def _read_until_prompt(self, timeout: float) -> str:
        self._read_until_any((self._prompt,), timeout, "shell prompt")
        return self._prompt

    def _read_command_response(self, token: str, timeout: float) -> tuple[str, int]:
        channel = self._require_channel()
        marker = re.compile(rf"\n{re.escape(token)}(-?\d+)\n")
        buffer = bytearray()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if channel.recv_ready():
                buffer.extend(channel.recv(65535))
                normalized = self._normalize_bytes(buffer).decode(errors="replace")
                match = marker.search(normalized)
                if match is not None and normalized[match.end() :].endswith(self._prompt):
                    return normalized[: match.start()], int(match.group(1))
            elif channel.exit_status_ready():
                raise TransportError("picocom exited while a console command was running")
            else:
                time.sleep(_POLL_INTERVAL)

        partial = self._normalize_bytes(buffer).decode(errors="replace")
        raise TransportTimeoutError(f"Console command timed out; received: {partial!r}")

    def _require_channel(self) -> paramiko.Channel:
        if self._channel is None:
            raise RuntimeError("Picocom-over-SSH transport is not connected")
        return self._channel

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
