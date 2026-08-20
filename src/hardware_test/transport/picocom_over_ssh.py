"""Persistent picocom serial console reached through an SSH connection."""

import shlex
from pathlib import Path

import paramiko
from pydantic import SecretStr

from hardware_test.exceptions import TransportError, UnsupportedCommandError
from hardware_test.models import Command, CommandResult, SshHostKeyPolicy, UnixCommand
from hardware_test.transport.console import LinuxConsoleSession
from hardware_test.transport.host_keys import configure_host_key_policy


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
        host_key_policy: SshHostKeyPolicy = SshHostKeyPolicy.REJECT,
        known_hosts_path: Path | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._host_key_policy = host_key_policy
        self._known_hosts_path = known_hosts_path
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
        self._console: LinuxConsoleSession | None = None

    def connect(self) -> None:
        """Open SSH, start picocom, and establish a deterministic shell prompt."""
        if self._client is not None:
            return

        client = paramiko.SSHClient()
        configure_host_key_policy(client, self._host_key_policy, self._known_hosts_path)
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
            self._console = None
            client.close()
            raise

    def close(self) -> None:
        """Stop picocom and close the SSH resources."""
        channel = self._channel
        client = self._client
        self._channel = None
        self._client = None
        self._console = None
        try:
            if channel is not None:
                if not channel.closed:
                    channel.sendall(b"\x01\x18")
                channel.close()
        finally:
            if client is not None:
                client.close()

    def execute(self, command: Command[str] | Command[bytes]) -> CommandResult:
        """Execute one shell command and parse its output and exit status."""
        if not isinstance(command, UnixCommand):
            raise UnsupportedCommandError(
                f"PicocomOverSshTransport does not support {type(command).__name__}"
            )
        return self._console_session().execute(command)

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
        """Prepare the shared console session after picocom starts."""
        self._console_session().prepare()

    def _console_session(self) -> LinuxConsoleSession:
        channel = self._channel
        if channel is None or channel.closed:
            raise RuntimeError("Picocom-over-SSH transport is not connected")
        if self._console is None:
            self._console = LinuxConsoleSession(
                channel=channel,
                prompt=self._prompt,
                initial_prompt_suffix=self._initial_prompt_suffix,
                login_prompt=self._login_prompt,
                password_prompt=self._password_prompt,
                console_username=self._console_username,
                console_password=self._console_password,
                connect_timeout=self._connect_timeout,
                command_timeout=self._command_timeout,
            )
        return self._console
