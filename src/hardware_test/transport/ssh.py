"""Paramiko-backed SSH transport."""

from pathlib import Path

import paramiko
from pydantic import SecretStr

from hardware_test.models import CommandResult, SshHostKeyPolicy
from hardware_test.transport.host_keys import configure_host_key_policy


class SSHTransport:
    """SSH implementation that keeps the client library behind Transport."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: SecretStr,
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
        self._connect_timeout = connect_timeout
        self._command_timeout = command_timeout
        self._client: paramiko.SSHClient | None = None

    def connect(self) -> None:
        """Open the SSH connection using strict known-host verification."""
        if self._client is not None:
            return
        client = paramiko.SSHClient()
        configure_host_key_policy(client, self._host_key_policy, self._known_hosts_path)
        client.connect(
            hostname=self._host,
            port=self._port,
            username=self._username,
            password=self._password.get_secret_value(),
            timeout=self._connect_timeout,
        )
        self._client = client

    def close(self) -> None:
        """Close the SSH connection if it is open."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def execute(self, command: str, timeout: float | None = None) -> CommandResult:
        """Execute a command and capture decoded output and exit status."""
        if self._client is None:
            raise RuntimeError("SSH transport is not connected")
        _, stdout, stderr = self._client.exec_command(
            command,
            timeout=timeout if timeout is not None else self._command_timeout,
        )
        return CommandResult(
            stdout=stdout.read().decode(),
            stderr=stderr.read().decode(),
            exit_code=stdout.channel.recv_exit_status(),
        )
