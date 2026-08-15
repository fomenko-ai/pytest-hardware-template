"""SSH host-key policy configuration tests without network access."""

from pathlib import Path

import paramiko
import pytest

from hardware_test.exceptions import TransportError
from hardware_test.models import SshHostKeyPolicy
from hardware_test.transport.host_keys import configure_host_key_policy


def _client(monkeypatch: pytest.MonkeyPatch) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    monkeypatch.setattr(client, "load_system_host_keys", lambda: None)
    monkeypatch.setattr(client, "load_host_keys", lambda filename: None)
    return client


@pytest.mark.parametrize(
    ("policy", "expected_type"),
    [
        (SshHostKeyPolicy.REJECT, paramiko.RejectPolicy),
        (SshHostKeyPolicy.WARN, paramiko.WarningPolicy),
        (SshHostKeyPolicy.ACCEPT_NEW, paramiko.AutoAddPolicy),
    ],
)
def test_configure_host_key_policy_selects_paramiko_policy(
    monkeypatch: pytest.MonkeyPatch,
    policy: SshHostKeyPolicy,
    expected_type: type[paramiko.MissingHostKeyPolicy],
) -> None:
    client = _client(monkeypatch)
    known_hosts_path = Path("/example/known_hosts")

    configure_host_key_policy(client, policy, known_hosts_path)

    assert isinstance(client._policy, expected_type)


def test_accept_new_requires_persistent_known_hosts_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(monkeypatch)

    with pytest.raises(TransportError, match="requires ssh_known_hosts_path"):
        configure_host_key_policy(client, SshHostKeyPolicy.ACCEPT_NEW, None)


def test_known_hosts_load_error_is_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)

    def fail_to_load(filename: str) -> None:
        raise FileNotFoundError(filename)

    monkeypatch.setattr(client, "load_host_keys", fail_to_load)

    with pytest.raises(TransportError, match="Cannot load SSH known-hosts file"):
        configure_host_key_policy(
            client,
            SshHostKeyPolicy.REJECT,
            Path("/missing/known_hosts"),
        )
