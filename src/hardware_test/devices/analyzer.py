"""Example analyzer device API."""

from hardware_test.devices.base import Device
from hardware_test.models import Measurement


class Analyzer(Device):
    """Neutral example API for measurement equipment."""

    def measure(self) -> Measurement:
        """Measure after a concrete project defines its device protocol."""
        raise NotImplementedError("Replace Analyzer.measure with the project-specific protocol")
