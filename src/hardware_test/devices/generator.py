"""Example stimulus generator API."""

from hardware_test.devices.base import Device


class Generator(Device):
    """Neutral example API for stimulus-generating equipment."""

    def configure(self) -> None:
        """Configure after a concrete project defines its device protocol."""
        raise NotImplementedError("Replace Generator.configure with the project-specific protocol")
