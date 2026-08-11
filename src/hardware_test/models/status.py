"""Device status value objects."""

from enum import StrEnum


class DeviceStatus(StrEnum):
    """Transport-independent high-level device status."""

    UNKNOWN = "unknown"
    READY = "ready"
    ERROR = "error"
