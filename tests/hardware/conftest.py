"""Fixtures that own physical test stand connections."""

from collections.abc import Iterator

import pytest

from hardware_test.exceptions import HardwareTestError
from hardware_test.factory import create_stand
from hardware_test.inventory import Inventory, get_stand
from hardware_test.settings import Settings
from hardware_test.stand import TestStand


@pytest.fixture(scope="session")
def stand(
    pytestconfig: pytest.Config,
    inventory: Inventory,
    settings: Settings,
) -> Iterator[TestStand]:
    """Connect the selected stand and always close all connections afterward."""
    stand_name: str | None = pytestconfig.getoption("stand")
    if stand_name is None:
        raise pytest.UsageError("Hardware tests require --stand")
    try:
        runtime_stand = create_stand(inventory, get_stand(inventory, stand_name), settings)
    except HardwareTestError as error:
        raise pytest.UsageError(str(error)) from error

    runtime_stand.connect()
    try:
        yield runtime_stand
    finally:
        runtime_stand.close()
