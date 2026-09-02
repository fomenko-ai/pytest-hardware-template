from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr, field_validator, model_validator
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
    auth_enabled: bool = False
    auth_username: str | None = None
    auth_password: SecretStr | None = None
    auth_session_secret: SecretStr | None = None
    auth_session_ttl_seconds: int = Field(default=604800, gt=0)
    auth_cookie_secure: bool = False

    @field_validator("docker_devices", "allowed_image_prefixes", mode="before")
    @classmethod
    def parse_comma_separated_tuple(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        return value

    @model_validator(mode="after")
    def validate_authentication_settings(self) -> Settings:
        if self.auth_enabled:
            required = {
                "TEST_RUNNER_AUTH_USERNAME": self.auth_username,
                "TEST_RUNNER_AUTH_PASSWORD": self.auth_password,
                "TEST_RUNNER_AUTH_SESSION_SECRET": self.auth_session_secret,
            }
            missing = [name for name, value in required.items() if not _has_secret_value(value)]
            if missing:
                raise ValueError(f"authentication requires: {', '.join(missing)}")
        return self


def _has_secret_value(value: str | SecretStr | None) -> bool:
    if isinstance(value, SecretStr):
        return bool(value.get_secret_value())
    return bool(value)
