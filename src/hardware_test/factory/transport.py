"""Transport construction from inventory and secret settings."""

from hardware_test.exceptions import FactoryError
from hardware_test.inventory.models import (
    PicocomOverSshTransportConfig,
    PySerialOverSshTransportConfig,
    PySerialTransportConfig,
    SshTransportConfig,
    TransportConfig,
)
from hardware_test.settings import ConsoleCredentialSettings, Settings
from hardware_test.transport import (
    ConsoleSessionConfig,
    PicocomOverSshTransport,
    PySerialOverSshTransport,
    PySerialTransport,
    SshConnectionConfig,
    SSHTransport,
    Transport,
)


def create_transport(config: TransportConfig, settings: Settings) -> Transport:
    """Create a transport while resolving credentials outside inventory."""
    if isinstance(config, PySerialTransportConfig):
        return PySerialTransport(
            serial_device=config.serial_device,
            baudrate=config.baudrate,
            console=_create_console_config(config, settings),
            connect_timeout=settings.connect_timeout,
            command_timeout=settings.command_timeout,
        )

    ssh = _create_ssh_config(config, settings)
    if isinstance(config, PicocomOverSshTransportConfig):
        return PicocomOverSshTransport(
            ssh=ssh,
            serial_device=config.serial_device,
            baudrate=config.baudrate,
            console=_create_console_config(config, settings),
            connect_timeout=settings.connect_timeout,
            command_timeout=settings.command_timeout,
        )
    if isinstance(config, PySerialOverSshTransportConfig):
        return PySerialOverSshTransport(
            ssh=ssh,
            serial_device=config.serial_device,
            baudrate=config.baudrate,
            console=_create_console_config(config, settings),
            serial_agent_command=settings.serial_agent_command,
            connect_timeout=settings.connect_timeout,
            command_timeout=settings.command_timeout,
        )
    return SSHTransport(
        ssh=ssh,
        connect_timeout=settings.connect_timeout,
        command_timeout=settings.command_timeout,
    )


def _create_ssh_config(
    config: SshTransportConfig | PicocomOverSshTransportConfig | PySerialOverSshTransportConfig,
    settings: Settings,
) -> SshConnectionConfig:
    credentials = settings.credentials.get_ssh(config.credentials)
    if credentials is None:
        raise FactoryError(
            f"SSH credentials '{config.credentials}' are not configured in runtime settings"
        )
    return SshConnectionConfig(
        host=config.host,
        port=config.port,
        username=credentials.username,
        password=credentials.password,
        host_key_policy=config.host_key_policy or settings.ssh_host_key_policy,
        known_hosts_path=settings.ssh_known_hosts_path,
    )


def _create_console_config(
    config: PicocomOverSshTransportConfig
    | PySerialTransportConfig
    | PySerialOverSshTransportConfig,
    settings: Settings,
) -> ConsoleSessionConfig:
    credentials = _resolve_console_credentials(config.console_credentials, settings)
    return ConsoleSessionConfig(
        prompt=config.prompt,
        initial_prompt_suffix=config.initial_prompt_suffix,
        login_prompt=config.login_prompt,
        password_prompt=config.password_prompt,
        username=credentials.username if credentials is not None else None,
        password=credentials.password if credentials is not None else None,
    )


def _resolve_console_credentials(
    reference: str | None,
    settings: Settings,
) -> ConsoleCredentialSettings | None:
    if reference is None:
        return None
    credentials = settings.credentials.get_console(reference)
    if credentials is None:
        raise FactoryError(
            f"Console credentials '{reference}' are not configured in runtime settings"
        )
    return credentials
