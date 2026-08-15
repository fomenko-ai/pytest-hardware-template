"""Remote pyserial console accessed through the standalone SSH helper."""

import shlex
from pathlib import Path

import paramiko
from pydantic import SecretStr

from hardware_test.exceptions import TransportError
from hardware_test.models import CommandResult, SshHostKeyPolicy
from hardware_test.transport.console import LinuxConsoleSession
from hardware_test.transport.host_keys import configure_host_key_policy
from hardware_test.transport.serial_agent import SerialAgentChannel


class PySerialOverSshTransport:
    """Execute commands through pyserial running on a remote SSH stand."""

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
        serial_agent_command: str,
        connect_timeout: float,
        command_timeout: float,
        host_key_policy: SshHostKeyPolicy = SshHostKeyPolicy.REJECT,
        known_hosts_path: Path | None = None,
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
        self._serial_agent_command = self._validate_agent_command(serial_agent_command)
        self._connect_timeout = connect_timeout
        self._command_timeout = command_timeout
        self._host_key_policy = host_key_policy
        self._known_hosts_path = known_hosts_path
        self._client: paramiko.SSHClient | None = None
        self._channel: SerialAgentChannel | None = None
        self._console: LinuxConsoleSession | None = None

    def connect(self) -> None:
        """Open SSH, start the serial agent, and prepare the remote board shell."""
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
            ssh_transport = client.get_transport()
            if ssh_transport is None or not ssh_transport.is_active():
                raise TransportError("SSH connection became inactive before serial agent started")
            ssh_channel = ssh_transport.open_session(timeout=self._connect_timeout)
            ssh_channel.exec_command(shlex.quote(self._serial_agent_command))
            channel = SerialAgentChannel(ssh_channel, self._command_timeout)
            channel.negotiate()
            channel.open(self._serial_device, self._baudrate)
            console = LinuxConsoleSession(
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
            self._client = client
            self._channel = channel
            self._console = console
            console.prepare()
        except Exception:
            if self._channel is not None:
                self._channel.close()
            self._client = None
            self._channel = None
            self._console = None
            client.close()
            raise

    def close(self) -> None:
        """Close the remote serial device, helper channel, and SSH client."""
        channel = self._channel
        client = self._client
        self._channel = None
        self._client = None
        self._console = None
        try:
            if channel is not None:
                channel.close()
        finally:
            if client is not None:
                client.close()

    def execute(self, command: str, timeout: float | None = None) -> CommandResult:
        """Execute one command through the prepared remote serial console."""
        if self._console is None:
            raise RuntimeError("PySerial-over-SSH transport is not connected")
        return self._console.execute(command, timeout)

    @staticmethod
    def _validate_agent_command(value: str) -> str:
        if any(character in value for character in "\0\r\n"):
            raise ValueError("serial_agent_command must not contain control characters")
        return value
