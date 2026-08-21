"""Pydantic models for declarative inventory data."""

from pathlib import Path, PurePosixPath
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from hardware_test.models import SshHostKeyPolicy


class SshConnectionInventoryConfig(BaseModel):
    """Inventory data for an SSH endpoint; secrets are referenced by name."""

    model_config = ConfigDict(extra="forbid")

    host: str
    port: int = Field(default=22, ge=1, le=65535)
    credentials: str
    host_key_policy: SshHostKeyPolicy | None = None


class ConsoleSessionInventoryConfig(BaseModel):
    """Inventory data used to prepare an interactive console session."""

    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1)
    initial_prompt_suffix: str = Field(default="# ", min_length=1)
    login_prompt: str = Field(default="login:", min_length=1)
    password_prompt: str = Field(default="Password:", min_length=1)
    credentials: str | None = None

    @field_validator("prompt", "initial_prompt_suffix", "login_prompt", "password_prompt")
    @classmethod
    def validate_console_marker(cls, value: str) -> str:
        """Keep console markers suitable for line-oriented synchronization."""
        if any(character in value for character in "\0\r\n"):
            raise ValueError("prompt must not contain control characters")
        return value


class SshTransportConfig(BaseModel):
    """Direct SSH transport inventory data."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["ssh"]
    ssh: SshConnectionInventoryConfig


class PicocomOverSshTransportConfig(BaseModel):
    """Remote serial-console connection reached through SSH and picocom."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["picocom_over_ssh"]
    ssh: SshConnectionInventoryConfig
    serial_device: str
    baudrate: int = Field(default=115200, gt=0)
    console: ConsoleSessionInventoryConfig

    @field_validator("serial_device")
    @classmethod
    def validate_serial_device(cls, value: str) -> str:
        """Require one explicit remote device path below /dev."""
        if any(character in value for character in "\0\r\n"):
            raise ValueError("serial_device must not contain control characters")
        path = PurePosixPath(value)
        if (
            not path.is_absolute()
            or path == PurePosixPath("/dev")
            or not path.is_relative_to("/dev")
            or ".." in path.parts
        ):
            raise ValueError("serial_device must be an absolute path below /dev")
        return value


class PySerialTransportConfig(BaseModel):
    """Local serial-console connection opened directly through pyserial."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["pyserial"]
    serial_device: str
    baudrate: int = Field(default=115200, gt=0)
    console: ConsoleSessionInventoryConfig

    @field_validator("serial_device")
    @classmethod
    def validate_serial_device(cls, value: str) -> str:
        """Require one explicit local device path below /dev."""
        return PicocomOverSshTransportConfig.validate_serial_device(value)


class PySerialOverSshTransportConfig(BaseModel):
    """Remote pyserial helper connection reached through SSH."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["pyserial_over_ssh"]
    ssh: SshConnectionInventoryConfig
    serial_device: str
    baudrate: int = Field(default=115200, gt=0)
    console: ConsoleSessionInventoryConfig

    @field_validator("serial_device")
    @classmethod
    def validate_serial_device(cls, value: str) -> str:
        """Require one explicit remote device path below /dev."""
        return PicocomOverSshTransportConfig.validate_serial_device(value)


TransportConfig = Annotated[
    SshTransportConfig
    | PicocomOverSshTransportConfig
    | PySerialTransportConfig
    | PySerialOverSshTransportConfig,
    Field(discriminator="type"),
]


class DeviceConfig(BaseModel):
    """Physical device and its connection configuration."""

    model_config = ConfigDict(extra="forbid")

    type: str
    model: str
    transport: TransportConfig


class StandConfig(BaseModel):
    """Logical role mapping for one physical test stand."""

    model_config = ConfigDict(extra="forbid")

    description: str | None = None
    capabilities: set[str] = Field(default_factory=set)
    devices: dict[str, str]


class DeviceInventory(BaseModel):
    """Physical device definitions loaded from a dedicated YAML file."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    devices: dict[str, DeviceConfig]


class StandInventory(BaseModel):
    """Stand definitions and their relative physical-device inventory sources."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    device_files: list[Path] = Field(min_length=1)
    stands: dict[str, StandConfig]


class Inventory(BaseModel):
    """Top-level inventory with validated stand-to-device references."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    devices: dict[str, DeviceConfig]
    stands: dict[str, StandConfig]

    @model_validator(mode="after")
    def validate_device_references(self) -> Self:
        missing = {
            f"{stand_name}.{role}": device_name
            for stand_name, stand in self.stands.items()
            for role, device_name in stand.devices.items()
            if device_name not in self.devices
        }
        if missing:
            references = ", ".join(f"{role} -> {device}" for role, device in missing.items())
            raise ValueError(f"Unknown device references: {references}")
        return self
