"""Root runtime settings loaded from environment variables."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from hardware_test.models import SshHostKeyPolicy
from hardware_test.settings.models import CredentialSettings


class Settings(BaseSettings):
    """Global runtime defaults and secrets; physical topology lives in inventory."""

    model_config = SettingsConfigDict(
        env_prefix="HARDWARE_TEST_",
        env_nested_delimiter="__",
        env_file=".env",
        extra="ignore",
    )

    credentials: CredentialSettings = Field(default_factory=CredentialSettings)
    inventory_path: Path = Path("inventory/stands.yaml")
    command_timeout: float = Field(default=30.0, gt=0)
    connect_timeout: float = Field(default=10.0, gt=0)
    ssh_host_key_policy: SshHostKeyPolicy = SshHostKeyPolicy.REJECT
    ssh_known_hosts_path: Path | None = None
    serial_agent_command: str = Field(default="hardware-serial-helper", min_length=1)
