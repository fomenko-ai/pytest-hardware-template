# Multi-device test stands

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
