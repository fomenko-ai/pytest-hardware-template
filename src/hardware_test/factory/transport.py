"""Transport construction from inventory and secret settings."""

from hardware_test.exceptions import FactoryError
from hardware_test.inventory.models import PicocomOverSshTransportConfig, TransportConfig
from hardware_test.settings import Settings
from hardware_test.transport import PicocomOverSshTransport, SSHTransport, Transport


def create_transport(config: TransportConfig, settings: Settings) -> Transport:
    """Create a transport while resolving credentials outside inventory."""
    credentials = settings.credentials.get_ssh(config.credentials)
    if credentials is None:
        raise FactoryError(
            f"SSH credentials '{config.credentials}' are not configured in runtime settings"
        )
    if isinstance(config, PicocomOverSshTransportConfig):
        console_credentials = None
        if config.console_credentials is not None:
            console_credentials = settings.credentials.get_console(config.console_credentials)
            if console_credentials is None:
                raise FactoryError(
                    "Console credentials "
                    f"'{config.console_credentials}' are not configured in runtime settings"
                )
        return PicocomOverSshTransport(
            host=config.host,
            port=config.port,
            username=credentials.username,
            password=credentials.password,
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
    return SSHTransport(
        host=config.host,
        port=config.port,
        username=credentials.username,
        password=credentials.password,
        connect_timeout=settings.connect_timeout,
        command_timeout=settings.command_timeout,
    )
