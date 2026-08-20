"""Command execution requests and results."""

import shlex
from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class Command[QueryT: (str, bytes)]:
    """Transport command containing a textual or binary query."""

    query: QueryT
    timeout: float | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class TextCommand(Command[str]):
    """Command represented as text for a command interpreter."""

    def __post_init__(self) -> None:
        if not isinstance(self.query, str):
            raise TypeError(f"{type(self).__name__} query must be str")

    @property
    def text(self) -> str:
        """Return the text submitted to the command interpreter."""
        return self.query


@dataclass(frozen=True, slots=True, kw_only=True)
class UnixCommand(TextCommand):
    sudo: bool = False
    non_interactive: bool = False

    @property
    def sudo_text(self) -> str:
        return f"sudo {self.query}"

    @property
    def non_interactive_text(self) -> str:
        return f"sudo -n -- sh -c {shlex.quote(self.query)}"

    @property
    def text(self) -> str:
        if not self.sudo:
            return self.query
        if self.non_interactive:
            return self.non_interactive_text
        return self.sudo_text


@dataclass(frozen=True, slots=True, kw_only=True)
class PowerShellCommand(TextCommand):
    """Command executed by PowerShell."""


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Captured result of a transport command."""

    stdout: str
    stderr: str
    exit_code: int
