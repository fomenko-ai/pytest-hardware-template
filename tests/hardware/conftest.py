"""Fixtures that own physical test stand connections."""

from collections.abc import Iterator

import pytest

from hardware_test.exceptions import HardwareTestError
from hardware_test.factory import StandFactory
from hardware_test.inventory import Inventory, get_stand
from hardware_test.stand import TestStand


@pytest.fixture(scope="session")
def stand(
    pytestconfig: pytest.Config,
    inventory: Inventory,
    stand_factory: StandFactory,
) -> Iterator[TestStand]:
    """Connect the selected stand and always close all connections afterward."""
    stand_name: str | None = pytestconfig.getoption("stand")
    if stand_name is None:
        raise pytest.UsageError("Hardware tests require --stand")
    try:
        runtime_stand = stand_factory.create(inventory, get_stand(inventory, stand_name))
    except HardwareTestError as error:
        raise pytest.UsageError(str(error)) from error

    runtime_stand.connect()
    try:
        yield runtime_stand
    finally:
        runtime_stand.close()
