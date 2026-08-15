"""Inventory model and loader tests."""

from pathlib import Path

import pytest

from hardware_test.exceptions import InventoryError, UnknownStandError
from hardware_test.inventory import (
    Inventory,
    PicocomOverSshTransportConfig,
    PySerialOverSshTransportConfig,
    PySerialTransportConfig,
    SshTransportConfig,
    get_stand,
    load_inventory,
)
from hardware_test.models import SshHostKeyPolicy


def _inventory_data() -> dict[str, object]:
    return {
        "version": 1,
        "devices": {
            "device-01": {
                "type": "dut",
                "model": "example",
                "transport": {
                    "type": "ssh",
                    "host": "192.0.2.10",
                    "credentials": "default-ssh",
                },
            }
        },
        "stands": {"stand-01": {"devices": {"dut": "device-01"}}},
    }


def _write_device_inventory(path: Path, device_name: str, host: str) -> None:
    path.write_text(
        f"""version: 1
devices:
  {device_name}:
    type: dut
    model: example
    transport: {{type: ssh, host: {host}, credentials: default-ssh}}
""",
        encoding="utf-8",
    )


def test_inventory_validates_device_references() -> None:
    data = _inventory_data()
    data["stands"] = {"stand-01": {"devices": {"dut": "missing"}}}

    with pytest.raises(ValueError, match=r"stand-01\.dut -> missing"):
        Inventory.model_validate(data)


def test_load_inventory_uses_safe_validated_yaml(tmp_path: Path) -> None:
    path = tmp_path / "stands.yaml"
    path.write_text(
        """version: 1
device_files: [devices.yaml]
stands:
  stand-01:
    devices: {dut: device-01}
""",
        encoding="utf-8",
    )
    _write_device_inventory(tmp_path / "devices.yaml", "device-01", "192.0.2.10")

    inventory = load_inventory(path)

    transport = inventory.devices["device-01"].transport
    assert isinstance(transport, SshTransportConfig)
    assert transport.port == 22


def test_load_inventory_wraps_validation_errors(tmp_path: Path) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text("version: 1\ndevice_files: [devices.yaml]\nstands: invalid\n", encoding="utf-8")

    with pytest.raises(InventoryError, match="Invalid inventory"):
        load_inventory(path)


def test_load_inventory_reports_missing_device_source(tmp_path: Path) -> None:
    path = tmp_path / "stands.yaml"
    path.write_text(
        "version: 1\ndevice_files: [missing.yaml]\nstands: {}\n",
        encoding="utf-8",
    )

    with pytest.raises(InventoryError, match=r"missing\.yaml"):
        load_inventory(path)


def test_load_inventory_merges_multiple_device_sources(tmp_path: Path) -> None:
    path = tmp_path / "stands.yaml"
    path.write_text(
        "version: 1\ndevice_files: [devices-a.yaml, devices-b.yaml]\nstands: {}\n",
        encoding="utf-8",
    )
    _write_device_inventory(tmp_path / "devices-a.yaml", "device-a", "192.0.2.10")
    _write_device_inventory(tmp_path / "devices-b.yaml", "device-b", "192.0.2.11")

    inventory = load_inventory(path)

    assert set(inventory.devices) == {"device-a", "device-b"}


def test_load_inventory_rejects_duplicate_device_ids(tmp_path: Path) -> None:
    path = tmp_path / "stands.yaml"
    path.write_text(
        "version: 1\ndevice_files: [devices-a.yaml, devices-b.yaml]\nstands: {}\n",
        encoding="utf-8",
    )
    _write_device_inventory(tmp_path / "devices-a.yaml", "duplicate", "192.0.2.10")
    _write_device_inventory(tmp_path / "devices-b.yaml", "duplicate", "192.0.2.11")

    with pytest.raises(InventoryError) as raised:
        load_inventory(path)

    message = str(raised.value)
    assert "Duplicate device IDs: duplicate" in message
    assert "devices-a.yaml" in message
    assert "devices-b.yaml" in message


def test_unknown_stand_lists_available_names() -> None:
    inventory = Inventory.model_validate(_inventory_data())

    with pytest.raises(UnknownStandError) as raised:
        get_stand(inventory, "stand-99")

    assert str(raised.value) == ("Unknown stand 'stand-99'.\n\nAvailable stands:\n- stand-01")


@pytest.mark.parametrize(
    "serial_device",
    [
        "/dev/serial/by-path/platform-example-port0",
        "/dev/serial/by-id/usb-example-port0",
        "/dev/ttyUSB0",
        "/dev/ttyACM0",
    ],
)
def test_picocom_transport_accepts_explicit_device_paths(serial_device: str) -> None:
    config = PicocomOverSshTransportConfig(
        type="picocom_over_ssh",
        host="192.0.2.10",
        credentials="default-ssh",
        serial_device=serial_device,
        prompt="__HARDWARE_TEST_PROMPT__# ",
    )

    assert config.serial_device == serial_device


@pytest.mark.parametrize(
    "serial_device",
    ["ttyUSB0", "/var/serial/ttyUSB0", "/dev", "/dev/../etc/passwd"],
)
def test_picocom_transport_rejects_device_paths_outside_dev(serial_device: str) -> None:
    with pytest.raises(ValueError, match="absolute path below /dev"):
        PicocomOverSshTransportConfig(
            type="picocom_over_ssh",
            host="192.0.2.10",
            credentials="default-ssh",
            serial_device=serial_device,
            prompt="__HARDWARE_TEST_PROMPT__# ",
        )


def test_inventory_parses_per_device_host_key_policy() -> None:
    config = PicocomOverSshTransportConfig(
        type="picocom_over_ssh",
        host="192.0.2.10",
        credentials="default-ssh",
        host_key_policy="warn",
        serial_device="/dev/ttyUSB0",
        prompt="__HARDWARE_TEST_PROMPT__# ",
    )

    assert config.host_key_policy is SshHostKeyPolicy.WARN


@pytest.mark.parametrize(
    ("transport_type", "expected_type"),
    [
        ("pyserial", PySerialTransportConfig),
        ("pyserial_over_ssh", PySerialOverSshTransportConfig),
    ],
)
def test_inventory_parses_pyserial_transports(
    transport_type: str,
    expected_type: type[PySerialTransportConfig | PySerialOverSshTransportConfig],
) -> None:
    transport: dict[str, object] = {
        "type": transport_type,
        "serial_device": "/dev/ttyACM0",
        "prompt": "__HARDWARE_TEST_PROMPT__# ",
    }
    if transport_type == "pyserial_over_ssh":
        transport.update(host="192.0.2.10", credentials="default-ssh")
    data = _inventory_data()
    devices = data["devices"]
    assert isinstance(devices, dict)
    device = devices["device-01"]
    assert isinstance(device, dict)
    device["transport"] = transport

    inventory = Inventory.model_validate(data)

    assert isinstance(inventory.devices["device-01"].transport, expected_type)
