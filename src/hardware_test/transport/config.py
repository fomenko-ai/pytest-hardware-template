"""Resolved runtime configuration values shared by transports."""

from dataclasses import dataclass
from pathlib import Path

from pydantic import SecretStr

from hardware_test.models import SshHostKeyPolicy


@dataclass(frozen=True, slots=True)
class SshConnectionConfig:
    """Resolved parameters for an SSH connection."""

    host: str
    port: int
    username: str
    password: SecretStr
    host_key_policy: SshHostKeyPolicy
    known_hosts_path: Path | None


@dataclass(frozen=True, slots=True)
class ConsoleSessionConfig:
    """Resolved parameters for an interactive console session."""

    prompt: str
    initial_prompt_suffix: str
    login_prompt: str
    password_prompt: str
    username: str | None
    password: SecretStr | None
