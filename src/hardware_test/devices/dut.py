"""Example device-under-test API."""

from hardware_test.devices.base import Device
from hardware_test.models import DeviceStatus


class Dut(Device):
    """Neutral example API for the primary device under test."""

    def get_status(self) -> DeviceStatus:
        """Read status after a concrete project defines its device protocol."""
        raise NotImplementedError("Replace Dut.get_status with the project-specific protocol")
