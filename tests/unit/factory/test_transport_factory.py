"""Transport factory tests."""

import pytest
from pydantic import SecretStr

from hardware_test.exceptions import FactoryError
from hardware_test.factory.transport import create_transport
from hardware_test.inventory import (
    PicocomOverSshTransportConfig,
    PySerialOverSshTransportConfig,
    PySerialTransportConfig,
    SshTransportConfig,
)
from hardware_test.models import SshHostKeyPolicy
from hardware_test.settings import (
    ConsoleCredentialSettings,
    CredentialSettings,
    Settings,
    SshCredentialSettings,
)
from hardware_test.transport import (
    PicocomOverSshTransport,
    PySerialOverSshTransport,
    PySerialTransport,
    SSHTransport,
)


def _config() -> SshTransportConfig:
    return SshTransportConfig(type="ssh", host="192.0.2.10", port=2222, credentials="default-ssh")


def test_transport_factory_resolves_secret_from_settings() -> None:
    settings = Settings(
        _env_file=None,
        credentials=CredentialSettings(
            default_ssh=SshCredentialSettings(username="tester", password=SecretStr("secret"))
        ),
    )

    transport = create_transport(_config(), settings)

    assert isinstance(transport, SSHTransport)


def test_transport_factory_rejects_unknown_credentials() -> None:
    with pytest.raises(FactoryError, match="default-ssh"):
        create_transport(_config(), Settings(_env_file=None))


def test_transport_factory_creates_picocom_over_ssh_transport() -> None:
    config = PicocomOverSshTransportConfig(
        type="picocom_over_ssh",
        host="192.0.2.10",
        credentials="default-ssh",
        serial_device="/dev/serial/by-path/platform-example-port0",
        prompt="__HARDWARE_TEST_PROMPT__# ",
    )
    settings = Settings(
        _env_file=None,
        credentials=CredentialSettings(
            default_ssh=SshCredentialSettings(username="tester", password=SecretStr("secret"))
        ),
    )

    transport = create_transport(config, settings)

    assert isinstance(transport, PicocomOverSshTransport)


def test_transport_factory_resolves_console_credentials() -> None:
    config = PicocomOverSshTransportConfig(
        type="picocom_over_ssh",
        host="192.0.2.10",
        credentials="default-ssh",
        serial_device="/dev/ttyUSB0",
        prompt="__HARDWARE_TEST_PROMPT__# ",
        console_credentials="dut-console",
    )
    settings = Settings(
        _env_file=None,
        credentials=CredentialSettings(
            default_ssh=SshCredentialSettings(username="tester", password=SecretStr("secret")),
            console={
                "dut-console": ConsoleCredentialSettings(
                    username="root", password=SecretStr("board-secret")
                )
            },
        ),
    )

    transport = create_transport(config, settings)

    assert isinstance(transport, PicocomOverSshTransport)


def test_transport_factory_rejects_unknown_console_credentials() -> None:
    config = PicocomOverSshTransportConfig(
        type="picocom_over_ssh",
        host="192.0.2.10",
        credentials="default-ssh",
        serial_device="/dev/ttyUSB0",
        prompt="__HARDWARE_TEST_PROMPT__# ",
        console_credentials="missing-console",
    )
    settings = Settings(
        _env_file=None,
        credentials=CredentialSettings(
            default_ssh=SshCredentialSettings(username="tester", password=SecretStr("secret"))
        ),
    )

    with pytest.raises(FactoryError, match="missing-console"):
        create_transport(config, settings)


def test_transport_factory_uses_global_host_key_policy() -> None:
    settings = Settings(
        _env_file=None,
        credentials=CredentialSettings(
            default_ssh=SshCredentialSettings(username="tester", password=SecretStr("secret"))
        ),
        ssh_host_key_policy=SshHostKeyPolicy.WARN,
    )

    transport = create_transport(_config(), settings)

    assert isinstance(transport, SSHTransport)
    assert transport._host_key_policy is SshHostKeyPolicy.WARN


def test_transport_factory_prefers_inventory_host_key_policy() -> None:
    config = SshTransportConfig(
        type="ssh",
        host="192.0.2.10",
        credentials="default-ssh",
        host_key_policy=SshHostKeyPolicy.ACCEPT_NEW,
    )
    settings = Settings(
        _env_file=None,
        credentials=CredentialSettings(
            default_ssh=SshCredentialSettings(username="tester", password=SecretStr("secret"))
        ),
        ssh_host_key_policy=SshHostKeyPolicy.WARN,
    )

    transport = create_transport(config, settings)

    assert isinstance(transport, SSHTransport)
    assert transport._host_key_policy is SshHostKeyPolicy.ACCEPT_NEW


def test_transport_factory_creates_local_pyserial_without_ssh_credentials() -> None:
    config = PySerialTransportConfig(
        type="pyserial",
        serial_device="/dev/ttyACM0",
        prompt="__HARDWARE_TEST_PROMPT__# ",
    )

    transport = create_transport(config, Settings(_env_file=None))

    assert isinstance(transport, PySerialTransport)


def test_transport_factory_creates_pyserial_over_ssh() -> None:
    config = PySerialOverSshTransportConfig(
        type="pyserial_over_ssh",
        host="192.0.2.10",
        credentials="default-ssh",
        serial_device="/dev/ttyUSB0",
        prompt="__HARDWARE_TEST_PROMPT__# ",
    )
    settings = Settings(
        _env_file=None,
        serial_agent_command="/opt/hardware/bin/hardware-serial-helper",
        credentials=CredentialSettings(
            default_ssh=SshCredentialSettings(username="tester", password=SecretStr("secret"))
        ),
    )

    transport = create_transport(config, settings)

    assert isinstance(transport, PySerialOverSshTransport)
    assert transport._serial_agent_command == "/opt/hardware/bin/hardware-serial-helper"
