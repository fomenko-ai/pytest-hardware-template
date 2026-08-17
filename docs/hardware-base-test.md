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
            stand.dut,
            "example service restart",
            expected_stdout="restarted",
        )

        func_step_logger.log("Check service status")
        result = self.run_command(
            stand.dut,
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

## Group-specific base classes

When one hardware-test group repeatedly uses the same fixtures or helpers, its directory may have
a local `base.py`. The local base class inherits from the shared `BaseTest`, while behavior that is
specific to the group stays out of `tests/hardware/base.py`:

```python
# tests/hardware/recovery/base.py
import pytest

from hardware_test.devices import Dut
from hardware_test.stand import TestStand
from tests.hardware.base import BaseTest


class RecoveryBaseTest(BaseTest):
    @pytest.fixture(scope="class")
    @classmethod
    def dut(cls, stand: TestStand) -> Dut:
        """Expose the DUT logical role to every test in the class."""
        return stand.dut
```

```python
# tests/hardware/recovery/test_service.py
import pytest

from hardware_test.devices import Dut
from tests.hardware.recovery.base import RecoveryBaseTest as BaseTest


@pytest.mark.hardware
class TestServiceRecovery(BaseTest):
    def test_service_is_ready(self, dut: Dut) -> None:
        self.run_and_check_command(
            dut,
            "example service status",
            expected_stdout="ready",
        )
```

Declare class-scoped fixtures as class methods, with `@pytest.fixture` above `@classmethod`, and
accept `cls` instead of an instance `self` parameter. They may return devices from `TestStand`, but
the custom base class must not store the stand, a device, a transport, or other mutable runtime
state on itself. If a fixture changes device state, use `yield` with `try/finally` and restore that
state during teardown.

For a stand containing a DUT and additional equipment, see the
[multi-device stand example](multi-device-stands.md).
