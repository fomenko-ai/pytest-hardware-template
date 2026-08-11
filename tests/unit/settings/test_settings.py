"""Settings loading tests."""

import pytest
from pydantic import SecretStr

from hardware_test.settings import Settings


def test_settings_load_nested_ssh_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_TEST_CREDENTIALS__DEFAULT_SSH__USERNAME", "operator")
    monkeypatch.setenv("HARDWARE_TEST_CREDENTIALS__DEFAULT_SSH__PASSWORD", "secret")

    settings = Settings(_env_file=None)
    credentials = settings.credentials.get_ssh("default-ssh")

    assert credentials is not None
    assert credentials.username == "operator"
    assert isinstance(credentials.password, SecretStr)
    assert credentials.password.get_secret_value() == "secret"


def test_settings_do_not_expose_inventory_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_TEST_UNKNOWN_HOST", "192.0.2.99")

    settings = Settings(_env_file=None)

    assert not hasattr(settings, "unknown_host")
