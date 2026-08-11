"""Neutral device-output parsing tests."""

from hardware_test.models import DeviceStatus
from hardware_test.parsing import parse_device_status


def test_parse_known_status() -> None:
    assert parse_device_status(" READY\n") is DeviceStatus.READY


def test_parse_unknown_status() -> None:
    assert parse_device_status("vendor-specific") is DeviceStatus.UNKNOWN
