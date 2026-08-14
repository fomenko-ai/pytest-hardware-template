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

## Multi-device test stand

This example stand combines a USB-connected board, a conventional analyzer, and a reference meter
assigned to a project-specific logical role. The remote server remains an access endpoint of the
board's transport, not a device exposed directly to the test:

```text
TestStand -> dut      -> PicocomOverSshTransport -> SSH server -> picocom -> board
          -> analyzer -> SSHTransport -> analyzer
          -> reference_meter -> SSHTransport -> reference meter
```

The device inventory describes all three physical devices:

```yaml
devices:
  serial_dut:
    type: dut
    model: example-linux-board
    transport:
      type: picocom_over_ssh
      host: 192.0.2.13
      credentials: default-ssh
      serial_device: /dev/serial/by-path/platform-example-port0
      prompt: "__HARDWARE_TEST_PROMPT__# "
      console_credentials: dut-console

  analyzer:
    type: analyzer
    model: example-analyzer
    transport:
      type: ssh
      host: 192.0.2.21
      credentials: analyzer-default

  reference_meter:
    type: analyzer
    model: example-reference-meter
    transport:
      type: ssh
      host: 192.0.2.22
      credentials: analyzer-default
```

The stand inventory maps the physical devices to stable logical roles. `reference_meter` is an
additional role without a dedicated `TestStand` property:

```yaml
stands:
  serial-stand:
    description: Example server with a USB-connected board
    capabilities: [smoke, measurement]
    devices:
      dut: serial_dut
      analyzer: analyzer
      reference_meter: reference_meter
```

The session-scoped `stand` fixture constructs all devices, connects their transports, and closes
them after the test session. Conventional roles use properties such as `stand.dut` and
`stand.analyzer`. Additional roles use `stand.device()` with an expected domain API type:

```python
import pytest

from hardware_test.devices import Analyzer
from hardware_test.logging import StepLogger
from hardware_test.stand import TestStand
from tests.hardware.base import BaseTest


@pytest.mark.hardware
class TestSerialBoard(BaseTest):
    def test_board_output_level(
        self,
        stand: TestStand,
        prepared_test_mode: None,
        func_step_logger: StepLogger,
    ) -> None:
        analyzer = stand.analyzer
        assert analyzer is not None
        reference_meter = stand.device("reference_meter", Analyzer)

        func_step_logger.log("Check DUT test output")
        result = self.run_command(stand, "example output status")

        self.check_command(result, expected_stdout="enabled", expected_stderr="")

        func_step_logger.log("Measure DUT output level")
        measurement = analyzer.measure()

        func_step_logger.log("Measure reference output level")
        reference = reference_meter.measure()

        assert measurement.name == "output_level"
        assert measurement.unit == "V"
        assert 3.2 <= measurement.value <= 3.4
        assert reference.unit == "V"
        assert abs(measurement.value - reference.value) <= 0.1
```

Run the test by selecting the logical stand:

```bash
uv run pytest tests/hardware/test_serial_board.py --stand serial-stand
```

Do not expose the SSH server as another test device when it only hosts `picocom`. If a scenario
must also test or configure the server itself, introduce a dedicated server domain API and map it
to a separate logical role such as `host`; the test can then obtain it with
`stand.device("host", ExpectedHostType)`. The board must still be accessed through `stand.dut`,
without reaching into its transport.
