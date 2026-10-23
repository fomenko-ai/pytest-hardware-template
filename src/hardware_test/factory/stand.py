"""Composition of a runtime stand from inventory models."""

from hardware_test.devices import Device
from hardware_test.factory.contracts import DeviceFactory, InventoryView, TransportFactory
from hardware_test.factory.devices import BuiltinDeviceFactory
from hardware_test.factory.transport import BuiltinTransportFactory
from hardware_test.inventory import Inventory, StandConfig, TransportConfig
from hardware_test.settings import Settings
from hardware_test.stand import TestStand


class StandFactory[TransportConfigT = TransportConfig]:
    """Compose a stand using explicitly injected device and transport factories."""

    def __init__(
        self,
        device_factory: DeviceFactory[TransportConfigT],
        transport_factory: TransportFactory[TransportConfigT],
    ) -> None:
        self._device_factory = device_factory
        self._transport_factory = transport_factory

    def create(self, inventory: InventoryView[TransportConfigT], config: StandConfig) -> TestStand:
        """Map physical devices to roles, reusing one instance per physical ID."""
        physical_devices: dict[str, Device] = {}
        devices_by_role: dict[str, Device] = {}

        for role, device_name in config.devices.items():
            device = physical_devices.get(device_name)
            if device is None:
                device_config = inventory.devices[device_name]
                transport = self._transport_factory.create(device_config.transport)
                device = self._device_factory.create(device_config, transport)
                physical_devices[device_name] = device
            devices_by_role[role] = device

        return TestStand(devices=devices_by_role)


def create_stand(inventory: Inventory, config: StandConfig, settings: Settings) -> TestStand:
    """Create a stand using the standard inventory types and runtime settings."""
    return StandFactory(
        device_factory=BuiltinDeviceFactory(),
        transport_factory=BuiltinTransportFactory(settings),
    ).create(inventory, config)
