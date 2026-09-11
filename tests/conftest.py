"""Shared framework-test fixtures."""

from pathlib import Path

import pytest

from hardware_test.exceptions import HardwareTestError
from hardware_test.inventory import Inventory, load_inventory
from hardware_test.pytest_plugin import get_run_directory
from hardware_test.settings import Settings


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register reporting options owned by this repository's tests."""
    group = parser.getgroup("hardware-test-reports")
    group.addoption(
        "--allure",
        action="store_true",
        help="write Allure results into the current artifacts run directory",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Configure optional repository-local Allure result collection."""
    if not config.getoption("allure", default=False):
        return
    if not config.pluginmanager.has_plugin("allure_pytest"):
        raise pytest.UsageError("--allure requires the dependency group: uv sync --group allure")
    if config.getoption("allure_report_dir", default=None) is not None:
        raise pytest.UsageError("--allure and --alluredir cannot be used together")
    config.option.allure_report_dir = str(get_run_directory(config) / "allure-results")


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
