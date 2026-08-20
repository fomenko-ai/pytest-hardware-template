"""Remote pyserial console accessed through the standalone SSH helper."""

import shlex

import paramiko

from hardware_test.exceptions import TransportError, UnsupportedCommandError
from hardware_test.models import Command, CommandResult, UnixCommand
from hardware_test.transport.config import ConsoleSessionConfig, SshConnectionConfig
from hardware_test.transport.console import LinuxConsoleSession
from hardware_test.transport.host_keys import configure_host_key_policy
from hardware_test.transport.serial_agent import SerialAgentChannel


class PySerialOverSshTransport:
    """Execute commands through pyserial running on a remote SSH stand."""

    def __init__(
        self,
        ssh: SshConnectionConfig,
        serial_device: str,
        baudrate: int,
        console: ConsoleSessionConfig,
        serial_agent_command: str,
        connect_timeout: float,
        command_timeout: float,
    ) -> None:
        self._ssh = ssh
        self._serial_device = serial_device
        self._baudrate = baudrate
        self._console_config = console
        self._serial_agent_command = self._validate_agent_command(serial_agent_command)
        self._connect_timeout = connect_timeout
        self._command_timeout = command_timeout
        self._client: paramiko.SSHClient | None = None
        self._channel: SerialAgentChannel | None = None
        self._console: LinuxConsoleSession | None = None

    def connect(self) -> None:
        """Open SSH, start the serial agent, and prepare the remote board shell."""
        if self._client is not None:
            return
        client = paramiko.SSHClient()
        configure_host_key_policy(client, self._ssh.host_key_policy, self._ssh.known_hosts_path)
        try:
            client.connect(
                hostname=self._ssh.host,
                port=self._ssh.port,
                username=self._ssh.username,
                password=self._ssh.password.get_secret_value(),
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
                config=self._console_config,
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

    def execute(self, command: Command[str] | Command[bytes]) -> CommandResult:
        """Execute one command through the prepared remote serial console."""
        if not isinstance(command, UnixCommand):
            raise UnsupportedCommandError(
                f"PySerialOverSshTransport does not support {type(command).__name__}"
            )
        if self._console is None:
            raise RuntimeError("PySerial-over-SSH transport is not connected")
        return self._console.execute(command)

    @staticmethod
    def _validate_agent_command(value: str) -> str:
        if any(character in value for character in "\0\r\n"):
            raise ValueError("serial_agent_command must not contain control characters")
        return value
