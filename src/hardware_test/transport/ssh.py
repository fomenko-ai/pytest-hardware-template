"""Paramiko-backed SSH transport."""

import paramiko

from hardware_test.exceptions import UnsupportedCommandError
from hardware_test.models import Command, CommandResult, TextCommand
from hardware_test.transport.config import SshConnectionConfig
from hardware_test.transport.host_keys import configure_host_key_policy


class SSHTransport:
    """SSH implementation that keeps the client library behind Transport."""

    def __init__(
        self,
        ssh: SshConnectionConfig,
        connect_timeout: float,
        command_timeout: float,
    ) -> None:
        self._ssh = ssh
        self._connect_timeout = connect_timeout
        self._command_timeout = command_timeout
        self._client: paramiko.SSHClient | None = None

    def connect(self) -> None:
        """Open the SSH connection using strict known-host verification."""
        if self._client is not None:
            return
        client = paramiko.SSHClient()
        configure_host_key_policy(client, self._ssh.host_key_policy, self._ssh.known_hosts_path)
        client.connect(
            hostname=self._ssh.host,
            port=self._ssh.port,
            username=self._ssh.username,
            password=self._ssh.password.get_secret_value(),
            timeout=self._connect_timeout,
        )
        self._client = client

    def close(self) -> None:
        """Close the SSH connection if it is open."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def execute(self, command: Command[str] | Command[bytes]) -> CommandResult:
        """Execute a command and capture decoded output and exit status."""
        if not isinstance(command, TextCommand):
            raise UnsupportedCommandError(f"SSHTransport does not support {type(command).__name__}")
        if self._client is None:
            raise RuntimeError("SSH transport is not connected")
        _, stdout, stderr = self._client.exec_command(
            command.text,
            timeout=command.timeout if command.timeout is not None else self._command_timeout,
        )
        return CommandResult(
            stdout=stdout.read().decode(),
            stderr=stderr.read().decode(),
            exit_code=stdout.channel.recv_exit_status(),
        )
