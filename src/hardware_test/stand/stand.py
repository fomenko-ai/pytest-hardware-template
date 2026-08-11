"""A composed runtime view of a physical test stand."""

from dataclasses import dataclass
from typing import ClassVar

from hardware_test.devices import Analyzer, Device, Dut, Generator


@dataclass(slots=True)
class TestStand:
    """Devices assigned to stable logical roles for hardware tests."""

    __test__: ClassVar[bool] = False

    devices: dict[str, Device]

    def device[T: Device](self, role: str, expected_type: type[T]) -> T:
        """Return a logical-role device and validate its runtime type."""
        try:
            device = self.devices[role]
        except KeyError as error:
            available = ", ".join(sorted(self.devices)) or "none"
            raise LookupError(
                f"Unknown device role {role!r}. Available roles: {available}"
            ) from error
        if not isinstance(device, expected_type):
            raise TypeError(
                f"Logical role {role!r} requires {expected_type.__name__}, "
                f"got {type(device).__name__}"
            )
        return device

    def optional_device[T: Device](self, role: str, expected_type: type[T]) -> T | None:
        """Return an optional logical-role device and validate its runtime type."""
        if role not in self.devices:
            return None
        return self.device(role, expected_type)

    @property
    def dut(self) -> Dut:
        """Return the conventional DUT role."""
        return self.device("dut", Dut)

    @property
    def analyzer(self) -> Analyzer | None:
        """Return the conventional optional analyzer role."""
        return self.optional_device("analyzer", Analyzer)

    @property
    def generator(self) -> Generator | None:
        """Return the conventional optional generator role."""
        return self.optional_device("generator", Generator)

    def connect(self) -> None:
        """Connect every unique device in the stand."""
        connected: list[Device] = []
        try:
            for device in self._unique_devices:
                device.connect()
                connected.append(device)
        except Exception:
            for device in reversed(connected):
                device.close()
            raise

    def close(self) -> None:
        """Close every device, attempting cleanup even if one close fails."""
        first_error: Exception | None = None
        for device in reversed(self._unique_devices):
            try:
                device.close()
            except Exception as error:
                first_error = first_error or error
        if first_error is not None:
            raise first_error

    @property
    def _unique_devices(self) -> tuple[Device, ...]:
        """Return each configured runtime device once in logical-role order."""
        return tuple(dict.fromkeys(self.devices.values()))
