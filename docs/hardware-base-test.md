# Class-based hardware tests

Use `BaseTest` when several class-based hardware tests need the same command logging and result
checks. Keep stand preparation and cleanup in pytest fixtures so cleanup runs even when a command
or assertion in the test fails.

The following fictional example treats the DUT command-line interface as the interface under test.
Its commands and output do not describe a real device.

```python
from collections.abc import Iterator

import pytest

from hardware_test.logging import StepLogger
from hardware_test.stand import TestStand
from tests.hardware.base import BaseTest


@pytest.fixture
def prepared_test_mode(
    stand: TestStand,
    func_step_logger: StepLogger,
) -> Iterator[None]:
    """Enable a fictional test mode and always restore the default mode."""
    func_step_logger.log("Enable DUT test mode")
    setup_result = stand.dut.execute_command("example test-mode enable")
    assert setup_result.exit_code == 0, setup_result.stderr

    try:
        yield
    finally:
        func_step_logger.log("Restore DUT default mode")
        cleanup_result = stand.dut.execute_command("example test-mode disable")
        assert cleanup_result.exit_code == 0, cleanup_result.stderr


class TestServiceRecovery(BaseTest):
    def test_service_recovers(
        self,
        stand: TestStand,
        prepared_test_mode: None,
        func_step_logger: StepLogger,
    ) -> None:
        func_step_logger.log("Restart service")
        self.run_and_check_command(
            stand,
            "example service restart",
            expected_stdout="restarted",
        )

        func_step_logger.log("Check service status")
        result = self.run_command(
            stand,
            "example service status",
        )

        # Scenario-specific logic stays in the test.
        assert "degraded" not in result.stdout

        self.check_command(
            result,
            expected_stdout="ready",
            expected_stderr="",
        )
```

The session-scoped `stand` fixture owns connections. The function-scoped `prepared_test_mode`
fixture owns only the state it changes and restores that state in `finally`. A cleanup failure is
reported as a teardown failure instead of being silently ignored.

`BaseTest` writes command execution details through its ordinary module logger at `INFO` level and
validates command results, but it does not own the stand lifecycle or numbered test steps. The test
and its fixtures use `StepLogger` for significant scenario actions. Use `run_and_check_command`
for an immediate check and separate `run_command` from `check_command` when the test needs
additional logic between execution and the common assertions.

Do not put credentials or secrets in commands passed to these helpers because `run_command` logs
the command text. When a command is merely an implementation detail rather than the tested CLI,
hide it behind a named method on `Dut` and call that domain method from the test.
