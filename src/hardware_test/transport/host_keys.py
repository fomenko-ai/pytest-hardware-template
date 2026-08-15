"""Shared Paramiko host-key verification configuration."""

from pathlib import Path

import paramiko

from hardware_test.exceptions import TransportError
from hardware_test.models import SshHostKeyPolicy


def configure_host_key_policy(
    client: paramiko.SSHClient,
    policy: SshHostKeyPolicy,
    known_hosts_path: Path | None,
) -> None:
    """Load trusted keys and configure handling of previously unknown hosts."""
    client.load_system_host_keys()
    if known_hosts_path is not None:
        path = known_hosts_path.expanduser()
        try:
            client.load_host_keys(str(path))
        except OSError as error:
            raise TransportError(f"Cannot load SSH known-hosts file: {path}") from error

    if policy is SshHostKeyPolicy.REJECT:
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
    elif policy is SshHostKeyPolicy.ACCEPT_NEW:
        if known_hosts_path is None:
            raise TransportError("SSH host-key policy 'accept_new' requires ssh_known_hosts_path")
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    else:
        client.set_missing_host_key_policy(paramiko.WarningPolicy())
