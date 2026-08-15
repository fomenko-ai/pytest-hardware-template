"""Shared SSH configuration value types."""

from enum import StrEnum


class SshHostKeyPolicy(StrEnum):
    """Supported behavior for previously unknown SSH host keys."""

    REJECT = "reject"
    ACCEPT_NEW = "accept_new"
    WARN = "warn"
