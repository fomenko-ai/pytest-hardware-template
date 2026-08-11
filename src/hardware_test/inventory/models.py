"""Pydantic models for declarative inventory data."""

from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SshTransportConfig(BaseModel):
    """Connection data for an SSH endpoint; secrets are referenced by name."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["ssh"]
    host: str
    port: int = Field(default=22, ge=1, le=65535)
    credentials: str


TransportConfig = SshTransportConfig


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
