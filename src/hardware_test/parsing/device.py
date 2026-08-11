"""Neutral examples of converting device output into domain models."""

from hardware_test.models import DeviceStatus


def parse_device_status(value: str) -> DeviceStatus:
    """Parse a normalized status token without assuming a vendor protocol."""
    normalized = value.strip().lower()
    try:
        return DeviceStatus(normalized)
    except ValueError:
        return DeviceStatus.UNKNOWN
