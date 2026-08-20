# Multi-device test stands

This example stand combines a server, a USB-connected board, a conventional analyzer, and a
reference meter. The scenario tests both the server and the board, so each is exposed as a
separate logical role with the `Dut` domain API:

```text
TestStand -> server   -> SSHTransport -> server
          -> board    -> PicocomOverSshTransport -> SSH server -> picocom -> board
          -> analyzer -> SSHTransport -> analyzer
          -> reference_meter -> SSHTransport -> reference meter
```

The device inventory describes all four physical devices:

```yaml
devices:
  server_dut:
    type: dut
    model: example-linux-server
    transport:
      type: ssh
      host: 192.0.2.13
      credentials: default-ssh

  serial_board:
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
      server: server_dut
      board: serial_board
      analyzer: analyzer
      reference_meter: reference_meter
```

The session-scoped `stand` fixture constructs all devices, connects their transports, and closes
them after the test session. A group-local base class can expose the two `Dut` roles through typed
class-scoped fixture methods. Put this class in the test group's own `base.py`:

```python
# tests/hardware/serial_board/base.py
import pytest

from hardware_test.devices import Dut
from hardware_test.stand import TestStand
from tests.hardware.base import BaseTest


class SerialBoardBaseTest(BaseTest):
    @pytest.fixture(scope="class")
    @classmethod
    def server(cls, stand: TestStand) -> Dut:
        return stand.device("server", Dut)

    @pytest.fixture(scope="class")
    @classmethod
    def board(cls, stand: TestStand) -> Dut:
        return stand.device("board", Dut)
```

Tests inherit the local base and request only the roles they use:

```python
# tests/hardware/serial_board/test_output.py
import pytest

from hardware_test.devices import Analyzer, Dut
from hardware_test.logging import StepLogger
from hardware_test.models import UnixCommand
from hardware_test.stand import TestStand
from tests.hardware.serial_board.base import SerialBoardBaseTest as BaseTest


@pytest.mark.hardware
class TestSerialBoard(BaseTest):
    def test_board_output_level(
        self,
        server: Dut,
        board: Dut,
        stand: TestStand,
        func_step_logger: StepLogger,
    ) -> None:
        analyzer = stand.analyzer
        assert analyzer is not None
        reference_meter = stand.device("reference_meter", Analyzer)

        func_step_logger.log("Check server readiness")
        self.run_and_check_command(
            server,
            UnixCommand(query="example server status"),
            expected_stdout="ready",
        )

        func_step_logger.log("Check board test output")
        result = self.run_command(board, UnixCommand(query="example output status"))

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
uv run pytest tests/hardware/serial_board/test_output.py --stand serial-stand
```

Expose the SSH server as a logical device only because this scenario tests it directly. When a
server merely hosts `picocom`, keep it as an endpoint inside the board transport instead. The
`server` and `board` fixtures resolve public device APIs from `TestStand`; they do not reach into
the board's transport or take ownership of connection cleanup.
