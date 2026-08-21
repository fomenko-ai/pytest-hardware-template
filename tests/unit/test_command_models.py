"""Command request model tests."""

from typing import cast

import pytest

from hardware_test.models import BinaryCommand, PowerShellCommand, UnixCommand


def test_unix_command_returns_plain_text_by_default() -> None:
    command = UnixCommand("uname -a", timeout=3.0)

    assert command.text == "uname -a"
    assert command.timeout == 3.0


def test_unix_command_accepts_query_by_keyword() -> None:
    command = UnixCommand(query="uname -a")

    assert command.text == "uname -a"


def test_binary_command_accepts_positional_query() -> None:
    command = BinaryCommand(b"\x01\x02", timeout=3.0)

    assert command.query == b"\x01\x02"
    assert command.timeout == 3.0


def test_binary_command_accepts_query_by_keyword() -> None:
    command = BinaryCommand(query=b"\x01\x02")

    assert command.query == b"\x01\x02"


def test_unix_command_adds_sudo_prefix() -> None:
    command = UnixCommand(query="echo ready > /root/status", sudo=True)

    assert command.sudo_text == "sudo echo ready > /root/status"
    assert command.text == command.sudo_text


def test_unix_command_quotes_complete_query_for_non_interactive_sudo() -> None:
    command = UnixCommand(
        query="echo ready > /root/status",
        sudo=True,
        non_interactive=True,
    )

    assert command.non_interactive_text == "sudo -n -- sh -c 'echo ready > /root/status'"
    assert command.text == command.non_interactive_text


def test_unix_command_ignores_non_interactive_without_sudo() -> None:
    command = UnixCommand(query="uname -a", non_interactive=True)

    assert command.text == "uname -a"


def test_powershell_command_preserves_query_text() -> None:
    command = PowerShellCommand(query="Get-Service | Where-Object Status -eq 'Running'")

    assert command.text == "Get-Service | Where-Object Status -eq 'Running'"


def test_text_command_rejects_binary_query_at_runtime() -> None:
    with pytest.raises(TypeError, match="UnixCommand query must be str"):
        UnixCommand(query=cast(str, b"uname -a"))


def test_binary_command_rejects_text_query_at_runtime() -> None:
    with pytest.raises(TypeError, match="BinaryCommand query must be bytes"):
        BinaryCommand(query=cast(bytes, "uname -a"))
