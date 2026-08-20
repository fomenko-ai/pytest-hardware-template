"""Example device-under-test API."""

from hardware_test.devices.base import Device
from hardware_test.models import CommandResult, DeviceStatus, TextCommand


class Dut(Device):
    """Neutral example API for the primary device under test."""

    def execute_command(
        self,
        command: TextCommand,
    ) -> CommandResult:
        """Execute a command exposed by the DUT command-line interface."""
        return self._transport.execute(command)

    def get_status(self) -> DeviceStatus:
        """Read status after a concrete project defines its device protocol."""
        raise NotImplementedError("Replace Dut.get_status with the project-specific protocol")
