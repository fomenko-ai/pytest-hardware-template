from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TEST_RUNNER_",
        env_file=".env",
        extra="ignore",
    )

    state_directory: Path = Path("/runtime/state")
    framework_source: Path = Path("/opt/hardware-runner/framework")
    framework_dockerfile: Path = Path("/opt/hardware-runner/framework/Dockerfile")
    inventory_file: Path = Path("/opt/hardware-runner/inventory/stands.yaml")
    artifacts_directory: Path = Path("/opt/hardware-runner/artifacts")
    env_file: Path | None = None
    known_hosts_file: Path | None = None
    docker_network: str | None = None
    docker_devices: Annotated[tuple[str, ...], NoDecode] = ()
    allowed_image_prefixes: Annotated[tuple[str, ...], NoDecode] = ("sha256:",)
    operation_timeout_seconds: int = Field(default=3600, gt=0)
    log_poll_interval_seconds: float = Field(default=0.25, gt=0)

    @field_validator("docker_devices", "allowed_image_prefixes", mode="before")
    @classmethod
    def parse_comma_separated_tuple(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        return value
