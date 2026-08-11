"""Pytest command-line integration for inventory-backed hardware tests."""

import logging
from datetime import datetime
from pathlib import Path

import pytest

from hardware_test.logging import StepLogger


def pytest_configure(config: pytest.Config) -> None:
    """Write each pytest session log and JUnit report to one artifacts directory."""
    run_id = datetime.now().astimezone().strftime("%Y-%m-%d_%H-%M-%S_%f")
    run_dir = config.rootpath / "artifacts" / run_id
    reports_dir = run_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=False)
    log_path = run_dir / "pytest.log"
    log_path.touch(exist_ok=False)
    latest_candidate = run_dir / ".latest.log"
    latest_candidate.hardlink_to(log_path)
    latest_candidate.replace(config.rootpath / "artifacts" / "latest.log")
    config.option.log_file = str(log_path)
    config.option.xmlpath = reports_dir / "junit.xml"


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register hardware selection options."""
    group = parser.getgroup("hardware-test")
    group.addoption("--stand", help="inventory stand key used by hardware tests")
    group.addoption(
        "--inventory",
        type=Path,
        default=Path("inventory/stands.yaml"),
        help="path to YAML inventory (default: inventory/stands.yaml)",
    )


@pytest.fixture
def func_step_logger(request: pytest.FixtureRequest) -> StepLogger:
    """Provide an independently numbered step logger for one test function."""
    logger = logging.getLogger(request.node.name)
    return StepLogger(logger)


@pytest.fixture(scope="class")
def cls_step_logger(request: pytest.FixtureRequest) -> StepLogger:
    """Share step numbering between test methods in one class."""
    logger = logging.getLogger(request.node.name)
    return StepLogger(logger)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Apply suite markers and require a stand only for hardware tests."""
    suite_markers = {"unit", "integration", "hardware"}
    for item in items:
        path_parts = set(item.path.parts)
        for marker_name in suite_markers & path_parts:
            item.add_marker(marker_name)

    has_hardware_tests = any(item.get_closest_marker("hardware") is not None for item in items)
    hardware_path_requested = any(
        "hardware" in Path(str(argument)).parts for argument in config.args
    )
    if (has_hardware_tests or hardware_path_requested) and config.getoption("stand") is None:
        raise pytest.UsageError("Hardware tests require --stand")
