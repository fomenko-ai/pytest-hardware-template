"""Transport factory tests."""

import pytest
from pydantic import SecretStr

from hardware_test.exceptions import FactoryError
from hardware_test.factory.transport import create_transport
from hardware_test.inventory import SshTransportConfig
from hardware_test.settings import CredentialSettings, Settings, SshCredentialSettings
from hardware_test.transport import SSHTransport


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
