"""Composition of a runtime stand from inventory models."""

from hardware_test.devices import Device
from hardware_test.factory.devices import create_device
from hardware_test.factory.transport import create_transport
from hardware_test.inventory import Inventory, StandConfig
from hardware_test.settings import Settings
from hardware_test.stand import TestStand


def create_stand(inventory: Inventory, config: StandConfig, settings: Settings) -> TestStand:
    """Resolve physical references and compose devices into logical stand roles."""
    physical_devices: dict[str, Device] = {}
    devices_by_role: dict[str, Device] = {}

    for role, device_name in config.devices.items():
        device = physical_devices.get(device_name)
        if device is None:
            device_config = inventory.devices[device_name]
            transport = create_transport(device_config.transport, settings)
            device = create_device(device_config, transport)
            physical_devices[device_name] = device
        devices_by_role[role] = device

    return TestStand(devices=devices_by_role)
