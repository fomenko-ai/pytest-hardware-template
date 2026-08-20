"""Direct pyserial transport for a locally attached Linux console."""

from typing import Protocol, cast

import serial
from pydantic import SecretStr

from hardware_test.exceptions import TransportError, UnsupportedCommandError
from hardware_test.models import Command, CommandResult, UnixCommand
from hardware_test.transport.console import LinuxConsoleSession


class SerialConnection(Protocol):
    """Subset of pyserial used by the direct console channel."""

    is_open: bool

    @property
    def in_waiting(self) -> int: ...

    def read(self, size: int = 1) -> bytes: ...

    def write(self, data: bytes) -> int | None: ...

    def close(self) -> None: ...


class PySerialChannel:
    """Adapt a non-blocking pyserial connection to ConsoleChannel."""

    def __init__(self, connection: SerialConnection) -> None:
        self._connection = connection

    @property
    def closed(self) -> bool:
        return not self._connection.is_open

    def sendall(self, s: bytes) -> None:
        """Write the complete payload or fail instead of silently truncating it."""
        try:
            view = memoryview(s)
            while view:
                written = self._connection.write(view.tobytes())
                if written is None or written <= 0:
                    raise TransportError("Serial write completed without progress")
                view = view[written:]
        except (serial.SerialException, OSError) as error:
            raise TransportError("Serial write failed") from error

    def recv_ready(self) -> bool:
        try:
            return self._connection.in_waiting > 0
        except (serial.SerialException, OSError) as error:
            raise TransportError("Serial input status failed") from error

    def recv(self, nbytes: int) -> bytes:
        try:
            return self._connection.read(min(nbytes, self._connection.in_waiting))
        except (serial.SerialException, OSError) as error:
            raise TransportError("Serial read failed") from error

    def exit_status_ready(self) -> bool:
        return self.closed

    def close(self) -> None:
        try:
            self._connection.close()
        except (serial.SerialException, OSError) as error:
            raise TransportError("Serial close failed") from error


class PySerialTransport:
    """Execute commands in a Linux console attached to a local serial port."""

    def __init__(
        self,
        serial_device: str,
        baudrate: int,
        prompt: str,
        initial_prompt_suffix: str,
        login_prompt: str,
        password_prompt: str,
        console_username: str | None,
        console_password: SecretStr | None,
        connect_timeout: float,
        command_timeout: float,
    ) -> None:
        self._serial_device = serial_device
        self._baudrate = baudrate
        self._prompt = prompt
        self._initial_prompt_suffix = initial_prompt_suffix
        self._login_prompt = login_prompt
        self._password_prompt = password_prompt
        self._console_username = console_username
        self._console_password = console_password
        self._connect_timeout = connect_timeout
        self._command_timeout = command_timeout
        self._channel: PySerialChannel | None = None
        self._console: LinuxConsoleSession | None = None

    def connect(self) -> None:
        """Open the local serial port and prepare its Linux shell."""
        if self._channel is not None and not self._channel.closed:
            return
        try:
            connection = cast(
                SerialConnection,
                serial.Serial(
                    port=self._serial_device,
                    baudrate=self._baudrate,
                    timeout=0.0,
                    write_timeout=self._command_timeout,
                    exclusive=True,
                ),
            )
            channel = PySerialChannel(connection)
            console = LinuxConsoleSession(
                channel=channel,
                prompt=self._prompt,
                initial_prompt_suffix=self._initial_prompt_suffix,
                login_prompt=self._login_prompt,
                password_prompt=self._password_prompt,
                console_username=self._console_username,
                console_password=self._console_password,
                connect_timeout=self._connect_timeout,
                command_timeout=self._command_timeout,
            )
            self._channel = channel
            self._console = console
            console.prepare()
        except (serial.SerialException, OSError) as error:
            self.close()
            raise TransportError(f"Cannot open serial device: {self._serial_device}") from error
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        """Close the local serial device if it is open."""
        channel = self._channel
        self._channel = None
        self._console = None
        if channel is not None:
            channel.close()

    def execute(self, command: Command[str] | Command[bytes]) -> CommandResult:
        """Execute one command through the prepared serial console."""
        if not isinstance(command, UnixCommand):
            raise UnsupportedCommandError(
                f"PySerialTransport does not support {type(command).__name__}"
            )
        if self._console is None:
            raise RuntimeError("PySerial transport is not connected")
        return self._console.execute(command)
