"""Stand factory tests."""

import pytest
from pydantic import SecretStr

from hardware_test.devices import Analyzer, Dut, Generator
from hardware_test.factory.stand import create_stand
from hardware_test.inventory import Inventory, get_stand
from hardware_test.settings import CredentialSettings, Settings, SshCredentialSettings


def _settings() -> Settings:
    credentials = SshCredentialSettings(username="tester", password=SecretStr("secret"))
    return Settings(
        _env_file=None,
        credentials=CredentialSettings(
            default_ssh=credentials,
            analyzer_default=credentials,
            generator_default=credentials,
        ),
    )


def _inventory(dut_type: str = "dut") -> Inventory:
    devices = {
        name: {
            "type": device_type,
            "model": f"example-{device_type}",
            "transport": {
                "type": "ssh",
                "host": f"192.0.2.{index}",
                "credentials": credential,
            },
        }
        for index, (name, device_type, credential) in enumerate(
            (
                ("dut-01", dut_type, "default-ssh"),
                ("analyzer-01", "analyzer", "analyzer-default"),
                ("generator-01", "generator", "generator-default"),
            ),
            start=10,
        )
    }
    return Inventory.model_validate(
        {
            "version": 1,
            "devices": devices,
            "stands": {
                "stand-01": {
                    "devices": {
                        "dut": "dut-01",
                        "analyzer": "analyzer-01",
                        "generator": "generator-01",
                    }
                }
            },
        }
    )


def test_stand_factory_maps_logical_roles() -> None:
    inventory = _inventory()

    stand = create_stand(inventory, get_stand(inventory, "stand-01"), _settings())

    assert isinstance(stand.dut, Dut)
    assert isinstance(stand.analyzer, Analyzer)
    assert isinstance(stand.generator, Generator)


def test_stand_factory_validates_role_type() -> None:
    inventory = _inventory(dut_type="analyzer")
    stand = create_stand(inventory, get_stand(inventory, "stand-01"), _settings())

    with pytest.raises(TypeError, match="Logical role 'dut' requires Dut"):
        _ = stand.dut


def test_stand_factory_maps_arbitrary_logical_roles() -> None:
    inventory = _inventory()
    config = get_stand(inventory, "stand-01")
    config.devices["analyzer_primary"] = "analyzer-01"

    stand = create_stand(inventory, config, _settings())

    assert isinstance(stand.device("analyzer_primary", Analyzer), Analyzer)


def test_stand_factory_reuses_physical_device_for_multiple_roles() -> None:
    inventory = _inventory()
    config = get_stand(inventory, "stand-01")
    config.devices["analyzer_primary"] = "analyzer-01"
    config.devices["analyzer_secondary"] = "analyzer-01"

    stand = create_stand(inventory, config, _settings())

    assert stand.devices["analyzer_primary"] is stand.devices["analyzer_secondary"]


def test_stand_reports_unknown_logical_role() -> None:
    inventory = _inventory()
    stand = create_stand(inventory, get_stand(inventory, "stand-01"), _settings())

    with pytest.raises(LookupError, match="Available roles: analyzer, dut, generator"):
        stand.device("missing", Analyzer)
