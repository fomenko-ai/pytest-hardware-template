"""TestStand lifecycle integration tests with in-memory transports."""

from hardware_test.devices import Analyzer, Dut
from hardware_test.stand import TestStand
from tests.fakes import FakeTransport


def test_stand_connects_and_closes_all_devices() -> None:
    dut_transport = FakeTransport()
    analyzer_transport = FakeTransport()
    stand = TestStand(
        devices={
            "dut": Dut(dut_transport, "example-dut"),
            "analyzer": Analyzer(analyzer_transport, "example-analyzer"),
        }
    )

    stand.connect()
    stand.close()

    assert dut_transport.connected
    assert dut_transport.closed
    assert analyzer_transport.connected
    assert analyzer_transport.closed
