"""End-to-end smoke checks for the disposable Docker DUT."""

import json

import pytest

from hardware_test.logging import StepLogger
from hardware_test.models import UnixCommand
from hardware_test.stand import TestStand
from tests.hardware.base import BaseTest


@pytest.mark.virtual_stand
class TestVirtualDut(BaseTest):
    """Verify the disposable DUT through the complete hardware stack."""

    def test_command_path(
        self,
        stand: TestStand,
        func_step_logger: StepLogger,
    ) -> None:
        func_step_logger.log("Check virtual DUT status")
        result = self.run_and_check_command(
            stand.dut,
            UnixCommand("virtual-device status"),
            expected_stderr="",
        )

        assert json.loads(result.stdout) == {"ready": True, "transport": "ssh"}
