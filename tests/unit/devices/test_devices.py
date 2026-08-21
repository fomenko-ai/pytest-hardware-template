"""Device dependency-injection tests."""

import pytest

from hardware_test.devices import Analyzer, Device, Dut, Generator
from hardware_test.models import UnixCommand
from tests.fakes import FakeTransport


@pytest.mark.parametrize("device_type", [Dut, Analyzer, Generator])
def test_device_lifecycle_delegates_to_transport(device_type: type[Device]) -> None:
    transport = FakeTransport()
    device = device_type(transport, "example-model")

    device.connect()
    device.close()

    assert transport.connected
    assert transport.closed


def test_example_device_protocol_is_explicitly_unimplemented() -> None:
    device = Dut(FakeTransport(), "example-model")

    with pytest.raises(NotImplementedError, match="project-specific protocol"):
        device.get_status()


def test_device_exposes_exclusive_transport_access() -> None:
    transport = FakeTransport()
    device = Dut(transport, "example-model")

    with device.exclusive_connection():
        device.execute_command(UnixCommand("example status"))

    assert transport.commands == [UnixCommand("example status")]
