"""Typed construction boundaries for built-in and project factories."""

from collections.abc import Mapping
from typing import Protocol

from hardware_test.devices import Device
from hardware_test.inventory import DeviceConfig, TransportConfig
from hardware_test.transport import LockableTransport


class DeviceFactory[TransportConfigT = TransportConfig](Protocol):
    """Build a device from its full configuration and an injected transport."""

    def create(
        self,
        config: DeviceConfig[TransportConfigT],
        transport: LockableTransport,
    ) -> Device: ...


class TransportFactory[TransportConfigT = TransportConfig](Protocol):
    """Build a synchronized transport without opening a connection."""

    def create(self, config: TransportConfigT) -> LockableTransport: ...


class InventoryView[TransportConfigT = TransportConfig](Protocol):
    """Read-only device mapping needed to compose a stand."""

    @property
    def devices(self) -> Mapping[str, DeviceConfig[TransportConfigT]]: ...
