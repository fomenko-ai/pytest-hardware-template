"""Transport construction from inventory and secret settings."""

from hardware_test.exceptions import FactoryError
from hardware_test.inventory.models import TransportConfig
from hardware_test.settings import Settings
from hardware_test.transport import SSHTransport, Transport


def create_transport(config: TransportConfig, settings: Settings) -> Transport:
    """Create a transport while resolving credentials outside inventory."""
    credentials = settings.credentials.get_ssh(config.credentials)
    if credentials is None:
        raise FactoryError(
            f"SSH credentials '{config.credentials}' are not configured in runtime settings"
        )
    return SSHTransport(
        host=config.host,
        port=config.port,
        username=credentials.username,
        password=credentials.password,
        connect_timeout=settings.connect_timeout,
        command_timeout=settings.command_timeout,
    )
