"""Example device-under-test API."""

from hardware_test.devices.base import Device
from hardware_test.models import CommandResult, DeviceStatus


class Dut(Device):
    """Neutral example API for the primary device under test."""

    def execute_command(
        self,
        command: str,
        timeout: float | None = None,
    ) -> CommandResult:
        """Execute a command exposed by the DUT command-line interface."""
        return self._transport.execute(command, timeout)

    def get_status(self) -> DeviceStatus:
        """Read status after a concrete project defines its device protocol."""
        raise NotImplementedError("Replace Dut.get_status with the project-specific protocol")
