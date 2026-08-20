"""Picocom-over-SSH transport tests with an in-memory channel."""

import re
from collections.abc import Callable
from typing import cast

import paramiko
import pytest
from pydantic import SecretStr

from hardware_test.exceptions import TransportError, TransportTimeoutError
from hardware_test.models import SshHostKeyPolicy, UnixCommand
from hardware_test.transport.config import ConsoleSessionConfig, SshConnectionConfig
from hardware_test.transport.picocom_over_ssh import PicocomOverSshTransport

PROMPT = "__HARDWARE_TEST_PROMPT__# "
AUTH_PROMPT = "Password:"


class FakeChannel:
    """Minimal Paramiko channel behavior used by command execution."""

    def __init__(self, responder: Callable[[bytes], list[bytes]] | None = None) -> None:
        self.closed = False
        self.sent: list[bytes] = []
        self._responses: list[bytes] = []
        self._responder = responder or (lambda _: [])

    def sendall(self, data: bytes) -> None:
        self.sent.append(data)
        self._responses.extend(self._responder(data))

    def recv_ready(self) -> bool:
        return bool(self._responses)

    def recv(self, size: int) -> bytes:
        del size
        return self._responses.pop(0)

    def exit_status_ready(self) -> bool:
        return False

    def close(self) -> None:
        self.closed = True


def _transport(
    channel: FakeChannel,
    *,
    console_username: str | None = None,
    console_password: SecretStr | None = None,
) -> PicocomOverSshTransport:
    transport = PicocomOverSshTransport(
        ssh=_ssh_config(),
        serial_device="/dev/serial/by-path/platform-example-port0",
        baudrate=115200,
        console=_console_config(console_username, console_password),
        connect_timeout=0.1,
        command_timeout=0.1,
    )
    transport._channel = cast(paramiko.Channel, channel)
    return transport


def _ssh_config() -> SshConnectionConfig:
    return SshConnectionConfig(
        host="192.0.2.10",
        port=22,
        username="tester",
        password=SecretStr("secret"),
        host_key_policy=SshHostKeyPolicy.REJECT,
        known_hosts_path=None,
    )


def _console_config(
    username: str | None = None,
    password: SecretStr | None = None,
) -> ConsoleSessionConfig:
    return ConsoleSessionConfig(
        prompt=PROMPT,
        initial_prompt_suffix="# ",
        login_prompt="login:",
        password_prompt=AUTH_PROMPT,
        username=username,
        password=password,
    )


def test_execute_reads_packetized_output_and_exit_code() -> None:
    def respond(data: bytes) -> list[bytes]:
        submitted = data.decode().removesuffix("\r")
        token = re.search(r"(__HARDWARE_TEST_EXIT_[0-9a-f]+__)", submitted)
        assert token is not None
        return [
            f"{submitted}\r\nLinux board".encode(),
            f"-dev 6.1\r\n\r\n{token.group(1)}7\r\n{PROMPT}".encode(),
        ]

    channel = FakeChannel(respond)

    result = _transport(channel).execute(UnixCommand(query="uname -a"))

    assert result.stdout == "Linux board-dev 6.1\n"
    assert result.stderr == ""
    assert result.exit_code == 7
    assert b"eval 'uname -a'" in channel.sent[0]


def test_execute_times_out_without_a_response() -> None:
    with pytest.raises(TransportTimeoutError, match="Console command timed out"):
        _transport(FakeChannel()).execute(UnixCommand(query="uname -a", timeout=0.0))


def test_close_sends_picocom_exit_sequence_and_closes_channel() -> None:
    channel = FakeChannel()
    transport = _transport(channel)

    transport.close()
    transport.close()

    assert channel.sent == [b"\x01\x18"]
    assert channel.closed


def test_picocom_command_quotes_the_serial_device() -> None:
    transport = PicocomOverSshTransport(
        ssh=_ssh_config(),
        serial_device="/dev/serial/by-path/example port0",
        baudrate=9600,
        console=_console_config(),
        connect_timeout=0.1,
        command_timeout=0.1,
    )

    assert transport._picocom_command() == (
        "picocom --quiet --baud 9600 '/dev/serial/by-path/example port0'"
    )


def test_prepare_console_skips_login_for_an_open_shell() -> None:
    def respond(data: bytes) -> list[bytes]:
        if data == b"\r":
            return [b"root@board-dev:~# "]
        if data.startswith(b"export PS1="):
            return [data, PROMPT.encode()]
        return []

    channel = FakeChannel(respond)
    transport = _transport(
        channel,
        console_username="root",
        console_password=SecretStr("board-secret"),
    )

    transport._prepare_console()

    assert channel.sent == [b"\r", f"export PS1='{PROMPT}'\r".encode()]


def test_prepare_console_logs_in_when_credentials_are_requested() -> None:
    def respond(data: bytes) -> list[bytes]:
        responses = {
            b"\r": b"board-dev login:",
            b"root\r": b"Password:",
            b"board-secret\r": b"root@board-dev:~# ",
        }
        if data.startswith(b"export PS1="):
            return [data, PROMPT.encode()]
        response = responses.get(data)
        return [response] if response is not None else []

    channel = FakeChannel(respond)
    transport = _transport(
        channel,
        console_username="root",
        console_password=SecretStr("board-secret"),
    )

    transport._prepare_console()

    assert channel.sent == [
        b"\r",
        b"root\r",
        b"board-secret\r",
        f"export PS1='{PROMPT}'\r".encode(),
    ]


def test_prepare_console_rejects_login_without_console_credentials() -> None:
    channel = FakeChannel(lambda data: [b"board-dev login:"] if data == b"\r" else [])

    with pytest.raises(TransportError, match="credentials are not configured"):
        _transport(channel)._prepare_console()

    assert channel.sent == [b"\r"]
