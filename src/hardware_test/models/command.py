"""Command execution results."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Captured result of a transport command."""

    stdout: str
    stderr: str
    exit_code: int
