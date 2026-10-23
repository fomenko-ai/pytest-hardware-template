"""Project-owned extension example; supply a fake client for offline execution.

This module is outside hardware_test and is not included in its wheel. A real project
places these definitions in its own package and implements ConsoleClient inside its
transport module using the chosen client library.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, SecretStr, TypeAdapter

from hardware_test.devices import Device
from hardware_test.exceptions import FactoryError, TransportError, UnsupportedCommandError
from hardware_test.factory import StandFactory, create_device, create_transport
from hardware_test.inventory import DeviceConfig, DeviceInventory, Inventory, TransportConfig
from hardware_test.inventory import load_inventory as load_builtin_inventory
from hardware_test.models import Command, CommandResult, TextCommand
from hardware_test.settings import CredentialSettings, Settings
from hardware_test.transport import LockableTransport, SynchronizedTransport


class TcpConsoleTransportConfig(BaseModel):
    """Physical endpoint and a reference to runtime credentials."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["tcp_console"]
    host: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535)
    credentials: str = Field(min_length=1)


type ProjectTransportConfig = Annotated[
    TransportConfig | TcpConsoleTransportConfig, Field(discriminator="type")
]


class BuiltinDeviceConfig(DeviceConfig[ProjectTransportConfig]):
    """Standard device APIs with either standard or project transports."""

    type: Literal["dut", "analyzer", "generator"]


class CustomMeterConfig(DeviceConfig[ProjectTransportConfig]):
    """A physical input selected when constructing the meter API."""

    type: Literal["custom_meter"]
    channel: int = Field(ge=1)


type ProjectDeviceConfig = Annotated[
    BuiltinDeviceConfig | CustomMeterConfig, Field(discriminator="type")
]


class TcpCredentialSettings(BaseModel):
    username: str
    password: SecretStr


class ProjectCredentialSettings(CredentialSettings):
    tcp: dict[str, TcpCredentialSettings] = Field(default_factory=dict)


class ProjectSettings(Settings):
    credentials: ProjectCredentialSettings = Field(default_factory=ProjectCredentialSettings)


class ConsoleClient(Protocol):
    """Client adapter private to the project's transport implementation."""

    def connect(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: SecretStr,
        timeout: float,
    ) -> None: ...

    def execute(self, query: str, *, timeout: float) -> CommandResult: ...

    def close(self) -> None: ...


class TcpConsoleTransport:
    """Map typed commands to a project client; opening happens only in connect."""

    def __init__(
        self,
        config: TcpConsoleTransportConfig,
        credentials: TcpCredentialSettings,
        settings: Settings,
        client: ConsoleClient,
    ) -> None:
        self._config = config
        self._credentials = credentials
        self._settings = settings
        self._client = client

    def connect(self) -> None:
        try:
            self._client.connect(
                host=self._config.host,
                port=self._config.port,
                username=self._credentials.username,
                password=self._credentials.password,
                timeout=self._settings.connect_timeout,
            )
        except OSError:
            self.close()
            raise TransportError("Cannot connect to TCP console") from None

    def close(self) -> None:
        try:
            self._client.close()
        except OSError:
            raise TransportError("Cannot close TCP console") from None

    def execute(self, command: Command[str] | Command[bytes]) -> CommandResult:
        if not isinstance(command, TextCommand):
            raise UnsupportedCommandError("TCP console requires TextCommand")
        timeout = command.timeout if command.timeout is not None else self._settings.command_timeout
        try:
            return self._client.execute(command.text, timeout=timeout)
        except OSError:
            raise TransportError("TCP console command failed") from None


class CustomMeter(Device):
    """A domain API independent of the transport's client library."""

    def __init__(self, transport: LockableTransport, model: str, channel: int) -> None:
        super().__init__(transport, model)
        self.channel = channel

    def measure(self) -> float:
        result = self._transport.execute(TextCommand(f"MEASURE {self.channel}"))
        if result.exit_code != 0:
            raise TransportError("Meter measurement failed")
        return float(result.stdout)


class ProjectDeviceFactory:
    def create(
        self,
        config: DeviceConfig[ProjectTransportConfig],
        transport: LockableTransport,
    ) -> Device:
        if isinstance(config, CustomMeterConfig):
            return CustomMeter(transport, config.model, channel=config.channel)
        return create_device(config, transport)


class ProjectTransportFactory:
    def __init__(
        self,
        settings: ProjectSettings,
        *,
        client_factory: Callable[[], ConsoleClient],
    ) -> None:
        self._settings = settings
        self._client_factory = client_factory

    def create(self, config: ProjectTransportConfig) -> LockableTransport:
        if isinstance(config, TcpConsoleTransportConfig):
            credentials = self._settings.credentials.tcp.get(config.credentials)
            if credentials is None:
                raise FactoryError(f"TCP credentials '{config.credentials}' are not configured")
            return SynchronizedTransport(
                TcpConsoleTransport(config, credentials, self._settings, self._client_factory())
            )
        return create_transport(config, self._settings)


def load_project_inventory(path: Path) -> Inventory[ProjectDeviceConfig]:
    """Use one explicit schema for every physical-device source."""
    return load_builtin_inventory(
        path,
        device_inventory_adapter=TypeAdapter(DeviceInventory[ProjectDeviceConfig]),
    )


def build_stand_factory(
    settings: ProjectSettings,
    *,
    client_factory: Callable[[], ConsoleClient],
) -> StandFactory[ProjectTransportConfig]:
    return StandFactory[ProjectTransportConfig](
        device_factory=ProjectDeviceFactory(),
        transport_factory=ProjectTransportFactory(settings, client_factory=client_factory),
    )
