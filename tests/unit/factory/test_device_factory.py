"""Device factory tests."""

import pytest

from hardware_test.devices import Dut
from hardware_test.exceptions import FactoryError
from hardware_test.factory.devices import create_device
from hardware_test.inventory import DeviceConfig
from tests.fakes import FakeTransport


def _device_config(device_type: str) -> DeviceConfig:
    return DeviceConfig.model_validate(
        {
            "type": device_type,
            "model": "example-model",
            "transport": {
                "type": "ssh",
                "ssh": {"host": "192.0.2.10", "credentials": "default-ssh"},
            },
        }
    )


def test_device_factory_builds_dut() -> None:
    assert isinstance(create_device(_device_config("dut"), FakeTransport()), Dut)


def test_device_factory_reports_supported_types() -> None:
    with pytest.raises(FactoryError, match="Unsupported device type 'unknown'"):
        create_device(_device_config("unknown"), FakeTransport())
