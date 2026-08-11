"""Device construction from validated inventory."""

from collections.abc import Callable

from hardware_test.devices import Analyzer, Device, Dut, Generator
from hardware_test.exceptions import FactoryError
from hardware_test.inventory import DeviceConfig
from hardware_test.transport import Transport

DeviceConstructor = Callable[[Transport, str], Device]

_DEVICE_TYPES: dict[str, DeviceConstructor] = {
    "dut": Dut,
    "analyzer": Analyzer,
    "generator": Generator,
}


def create_device(config: DeviceConfig, transport: Transport) -> Device:
    """Create a typed device API selected by its inventory type."""
    try:
        constructor = _DEVICE_TYPES[config.type]
    except KeyError as error:
        supported = ", ".join(sorted(_DEVICE_TYPES))
        raise FactoryError(
            f"Unsupported device type '{config.type}'. Supported types: {supported}"
        ) from error
    return constructor(transport, config.model)
