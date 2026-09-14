from pathlib import Path
from typing import Annotated

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
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
    pytest_log_path: Path | None = Path("pytest.log")
    junit_path: Path | None = Path("reports/junit.xml")
    html_path: Path | None = Path("reports/report.html")
    allure_results_path: Path | None = Path("allure-results")
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
    allure_enabled: bool = False
    allure_publisher_image: str = "local/allure-publisher:3.17.0"
    allure_access_token: SecretStr | None = None
    allure_public_url: AnyHttpUrl | None = None
    allure_repository: str = Field(
        default="pytest-hardware-template",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    )
    reportportal_enabled: bool = False
    reportportal_endpoint: AnyHttpUrl | None = None
    reportportal_public_url: AnyHttpUrl | None = None
    reportportal_project: str = Field(default="", pattern=r"^[a-z0-9_-]*$")
    reportportal_api_key: SecretStr | None = None

    @field_validator(
        "pytest_log_path",
        "junit_path",
        "html_path",
        "allure_results_path",
        mode="before",
    )
    @classmethod
    def empty_report_path_is_disabled(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("pytest_log_path", "junit_path", "html_path", "allure_results_path")
    @classmethod
    def validate_report_path(cls, value: Path | None) -> Path | None:
        if value is not None and (value.is_absolute() or ".." in value.parts or value == Path()):
            raise ValueError("report paths must be relative descendants of the session directory")
        return value

    @field_validator("docker_devices", "allowed_image_prefixes", mode="before")
    @classmethod
    def parse_comma_separated_tuple(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        return value

    @field_validator("allure_public_url", mode="before")
    @classmethod
    def empty_allure_public_url_is_unset(cls, value: object) -> object:
        return None if value == "" else value

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

    @model_validator(mode="after")
    def validate_allure_settings(self) -> Settings:
        if self.allure_enabled:
            missing = []
            if not _has_secret_value(self.allure_access_token):
                missing.append("TEST_RUNNER_ALLURE_ACCESS_TOKEN")
            if self.allure_results_path is None:
                missing.append("TEST_RUNNER_ALLURE_RESULTS_PATH")
            if missing:
                raise ValueError(f"Allure publishing requires: {', '.join(missing)}")
        return self

    @field_validator("reportportal_endpoint", "reportportal_public_url", mode="before")
    @classmethod
    def empty_reportportal_url_is_unset(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("reportportal_endpoint", "reportportal_public_url")
    @classmethod
    def validate_reportportal_url(cls, value: AnyHttpUrl | None) -> AnyHttpUrl | None:
        if value is not None and (
            value.username or value.password or value.query or value.fragment
        ):
            raise ValueError("ReportPortal URLs must not contain credentials, query, or fragment")
        return value

    @model_validator(mode="after")
    def validate_reportportal_settings(self) -> Settings:
        if self.reportportal_enabled:
            required = {
                "TEST_RUNNER_REPORTPORTAL_ENDPOINT": self.reportportal_endpoint,
                "TEST_RUNNER_REPORTPORTAL_PUBLIC_URL": self.reportportal_public_url,
                "TEST_RUNNER_REPORTPORTAL_PROJECT": self.reportportal_project,
                "TEST_RUNNER_REPORTPORTAL_API_KEY": self.reportportal_api_key,
            }
            missing = [
                name
                for name, value in required.items()
                if not (value.get_secret_value() if isinstance(value, SecretStr) else value)
            ]
            if missing:
                raise ValueError(f"ReportPortal requires: {', '.join(missing)}")
        return self


def _has_secret_value(value: str | SecretStr | None) -> bool:
    if isinstance(value, SecretStr):
        return bool(value.get_secret_value())
    return bool(value)
