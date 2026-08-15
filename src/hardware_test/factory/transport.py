"""Transport construction from inventory and secret settings."""

from hardware_test.exceptions import FactoryError
from hardware_test.inventory.models import (
    PicocomOverSshTransportConfig,
    PySerialOverSshTransportConfig,
    PySerialTransportConfig,
    TransportConfig,
)
from hardware_test.settings import ConsoleCredentialSettings, Settings
from hardware_test.transport import (
    PicocomOverSshTransport,
    PySerialOverSshTransport,
    PySerialTransport,
    SSHTransport,
    Transport,
)


def create_transport(config: TransportConfig, settings: Settings) -> Transport:
    """Create a transport while resolving credentials outside inventory."""
    if isinstance(config, PySerialTransportConfig):
        console_credentials = _resolve_console_credentials(config.console_credentials, settings)
        return PySerialTransport(
            serial_device=config.serial_device,
            baudrate=config.baudrate,
            prompt=config.prompt,
            initial_prompt_suffix=config.initial_prompt_suffix,
            login_prompt=config.login_prompt,
            password_prompt=config.password_prompt,
            console_username=(
                console_credentials.username if console_credentials is not None else None
            ),
            console_password=(
                console_credentials.password if console_credentials is not None else None
            ),
            connect_timeout=settings.connect_timeout,
            command_timeout=settings.command_timeout,
        )

    credentials = settings.credentials.get_ssh(config.credentials)
    if credentials is None:
        raise FactoryError(
            f"SSH credentials '{config.credentials}' are not configured in runtime settings"
        )
    host_key_policy = config.host_key_policy or settings.ssh_host_key_policy
    if isinstance(config, PicocomOverSshTransportConfig | PySerialOverSshTransportConfig):
        console_credentials = _resolve_console_credentials(config.console_credentials, settings)
    if isinstance(config, PicocomOverSshTransportConfig):
        return PicocomOverSshTransport(
            host=config.host,
            port=config.port,
            username=credentials.username,
            password=credentials.password,
            host_key_policy=host_key_policy,
            known_hosts_path=settings.ssh_known_hosts_path,
            serial_device=config.serial_device,
            baudrate=config.baudrate,
            prompt=config.prompt,
            initial_prompt_suffix=config.initial_prompt_suffix,
            login_prompt=config.login_prompt,
            password_prompt=config.password_prompt,
            console_username=(
                console_credentials.username if console_credentials is not None else None
            ),
            console_password=(
                console_credentials.password if console_credentials is not None else None
            ),
            connect_timeout=settings.connect_timeout,
            command_timeout=settings.command_timeout,
        )
    if isinstance(config, PySerialOverSshTransportConfig):
        return PySerialOverSshTransport(
            host=config.host,
            port=config.port,
            username=credentials.username,
            password=credentials.password,
            host_key_policy=host_key_policy,
            known_hosts_path=settings.ssh_known_hosts_path,
            serial_device=config.serial_device,
            baudrate=config.baudrate,
            prompt=config.prompt,
            initial_prompt_suffix=config.initial_prompt_suffix,
            login_prompt=config.login_prompt,
            password_prompt=config.password_prompt,
            console_username=(
                console_credentials.username if console_credentials is not None else None
            ),
            console_password=(
                console_credentials.password if console_credentials is not None else None
            ),
            serial_agent_command=settings.serial_agent_command,
            connect_timeout=settings.connect_timeout,
            command_timeout=settings.command_timeout,
        )
    return SSHTransport(
        host=config.host,
        port=config.port,
        username=credentials.username,
        password=credentials.password,
        host_key_policy=host_key_policy,
        known_hosts_path=settings.ssh_known_hosts_path,
        connect_timeout=settings.connect_timeout,
        command_timeout=settings.command_timeout,
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
