"""Safe loading and lookup functions for YAML inventory."""

from pathlib import Path
from typing import overload

import yaml
from pydantic import TypeAdapter, ValidationError

from hardware_test.exceptions import InventoryError, UnknownStandError
from hardware_test.inventory.models import DeviceInventory, Inventory, StandConfig, StandInventory


def _load_yaml(path: Path) -> object:
    """Read one YAML source with consistent inventory errors."""
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise InventoryError(f"Cannot read inventory '{path}': {error}") from error
    except yaml.YAMLError as error:
        raise InventoryError(f"Invalid inventory '{path}': {error}") from error


@overload
def load_inventory(path: Path) -> Inventory: ...


@overload
def load_inventory[DeviceConfigT](
    path: Path,
    *,
    device_inventory_adapter: TypeAdapter[DeviceInventory[DeviceConfigT]],
) -> Inventory[DeviceConfigT]: ...


def load_inventory[DeviceConfigT](
    path: Path,
    *,
    device_inventory_adapter: TypeAdapter[DeviceInventory[DeviceConfigT]] | None = None,
) -> Inventory[DeviceConfigT] | Inventory:
    """Load explicit sources, optionally validating a project device schema."""
    if device_inventory_adapter is None:
        return _load_inventory(path, TypeAdapter(DeviceInventory))
    return _load_inventory(path, device_inventory_adapter)


def _load_inventory[DeviceConfigT](
    path: Path,
    adapter: TypeAdapter[DeviceInventory[DeviceConfigT]],
) -> Inventory[DeviceConfigT]:
    """Load stand and physical-device sources into one validated inventory."""
    try:
        stand_inventory = StandInventory.model_validate(_load_yaml(path))
        devices: dict[str, DeviceConfigT] = {}
        device_sources: dict[str, Path] = {}

        for relative_path in stand_inventory.device_files:
            devices_path = path.parent / relative_path
            try:
                device_inventory = adapter.validate_python(_load_yaml(devices_path))
            except ValidationError as error:
                raise InventoryError(f"Invalid inventory '{devices_path}': {error}") from error
            duplicates = devices.keys() & device_inventory.devices.keys()
            if duplicates:
                details = ", ".join(
                    f"{name} ({device_sources[name]} and {devices_path})"
                    for name in sorted(duplicates)
                )
                raise InventoryError(f"Duplicate device IDs: {details}")

            devices.update(device_inventory.devices)
            device_sources.update(dict.fromkeys(device_inventory.devices, devices_path))

        return Inventory[DeviceConfigT](
            version=stand_inventory.version,
            devices=devices,
            stands=stand_inventory.stands,
        )
    except ValidationError as error:
        raise InventoryError(f"Invalid inventory '{path}': {error}") from error


def get_stand[DeviceConfigT](inventory: Inventory[DeviceConfigT], stand_name: str) -> StandConfig:
    """Return a named stand or raise an error listing available stands."""
    try:
        return inventory.stands[stand_name]
    except KeyError as error:
        available = "\n".join(f"- {name}" for name in sorted(inventory.stands)) or "- none"
        message = f"Unknown stand '{stand_name}'.\n\nAvailable stands:\n{available}"
        raise UnknownStandError(message) from error
