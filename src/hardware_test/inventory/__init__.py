"""Validated physical equipment inventory."""

from hardware_test.inventory.loader import get_stand, load_inventory
from hardware_test.inventory.models import (
    ConsoleSessionInventoryConfig,
    DeviceConfig,
    DeviceInventory,
    Inventory,
    PicocomOverSshTransportConfig,
    PySerialOverSshTransportConfig,
    PySerialTransportConfig,
    SshConnectionInventoryConfig,
    SshTransportConfig,
    StandConfig,
    StandInventory,
)

__all__ = [
    "ConsoleSessionInventoryConfig",
    "DeviceConfig",
    "DeviceInventory",
    "Inventory",
    "PicocomOverSshTransportConfig",
    "PySerialOverSshTransportConfig",
    "PySerialTransportConfig",
    "SshConnectionInventoryConfig",
    "SshTransportConfig",
    "StandConfig",
    "StandInventory",
    "get_stand",
    "load_inventory",
]
