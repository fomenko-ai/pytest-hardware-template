"""PySerial-over-SSH transport validation tests."""

import pytest
from pydantic import SecretStr

from hardware_test.transport.pyserial_over_ssh import PySerialOverSshTransport

AUTH_PROMPT = "Password:"


def test_pyserial_over_ssh_rejects_multiline_agent_command() -> None:
    with pytest.raises(ValueError, match="must not contain control characters"):
        PySerialOverSshTransport(
            host="192.0.2.10",
            port=22,
            username="tester",
            password=SecretStr("secret"),
            serial_device="/dev/ttyUSB0",
            baudrate=115200,
            prompt="__HARDWARE_TEST_PROMPT__# ",
            initial_prompt_suffix="# ",
            login_prompt="login:",
            password_prompt=AUTH_PROMPT,
            console_username=None,
            console_password=None,
            serial_agent_command="hardware-serial-helper\nmalicious-command",
            connect_timeout=0.1,
            command_timeout=0.1,
        )
