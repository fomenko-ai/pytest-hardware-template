"""Shared framework-test fixtures."""

from pathlib import Path

import pytest

from hardware_test.exceptions import HardwareTestError
from hardware_test.inventory import Inventory, load_inventory
from hardware_test.settings import Settings


@pytest.fixture(scope="session")
def settings() -> Settings:
    """Load global runtime settings once per session."""
    return Settings()


@pytest.fixture(scope="session")
def inventory(pytestconfig: pytest.Config, settings: Settings) -> Inventory:
    """Load inventory selected by CLI, falling back to the runtime default."""
    cli_path: Path = pytestconfig.getoption("inventory")
    path = cli_path or settings.inventory_path
    try:
        return load_inventory(path)
    except HardwareTestError as error:
        raise pytest.UsageError(str(error)) from error
