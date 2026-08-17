"""Pytest command-line integration for inventory-backed hardware tests."""

import logging
from collections.abc import Generator
from datetime import datetime
from inspect import getdoc
from pathlib import Path

import pytest

from hardware_test.logging import StepLogger

_MUTED_LOG_LEVEL = logging.CRITICAL + 1
logger = logging.getLogger(__name__)


def _log_test_class(test_class: type[object] | None) -> None:
    """Log a test class name and its docstring, if the current test belongs to a class."""
    if test_class is None:
        return

    logger = logging.getLogger(test_class.__module__)
    description = getdoc(test_class) or "No description"
    header = f" {test_class.__name__} ".center(100, "=")
    logger.info("\n\n\n%s\n%s\n", header, description)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item,
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    """Log failed test phases and stop the session when requested."""
    report = yield
    if report.failed:
        logger.error(
            "Test failed: %s [%s]\n%s",
            item.nodeid,
            report.when,
            report.longreprtext,
        )
    if report.failed and item.get_closest_marker("stop_on_fail") is not None:
        item.session.shouldstop = f"stopping after failure in {item.nodeid}"
    return report


def pytest_configure(config: pytest.Config) -> None:
    """Write each pytest session log and JUnit report to one artifacts directory."""
    configured_loggers = config.getini("muted_loggers")
    cli_loggers = config.getoption("mute_logger", default=[])
    for logger_name in {*configured_loggers, *cli_loggers}:
        logging.getLogger(logger_name).setLevel(_MUTED_LOG_LEVEL)

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
    parser.addini(
        "muted_loggers",
        "logger names muted during pytest runs",
        type="linelist",
        default=[],
    )
    group.addoption(
        "--mute-logger",
        action="append",
        default=[],
        help="mute a Python logger during the test run (may be repeated)",
    )
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


@pytest.fixture(scope="class", autouse=True)
def log_test_class(request: pytest.FixtureRequest) -> None:
    """Log the test class name and description once before its tests."""
    _log_test_class(request.cls)


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
