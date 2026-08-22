"""Pytest command-line integration for inventory-backed hardware tests."""

import logging
from collections.abc import Generator
from datetime import datetime
from inspect import getdoc
from pathlib import Path

import pytest

from hardware_test.logging import StepLogger
from hardware_test.scenarios import ScenarioError, load_scenario, parse_marker_sequence

_MUTED_LOG_LEVEL = logging.CRITICAL + 1
_MARKER_SEQUENCE_KEY = pytest.StashKey[tuple[str, ...]]()
logger = logging.getLogger(__name__)


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
    group.addoption(
        "-M",
        "--marker-sequence",
        help="run registered marker groups in comma-separated order",
    )
    group.addoption(
        "-S",
        "--scenario",
        help="run an ordered marker scenario from test-runs/scenarios/<name>.yaml",
    )
    group.addoption("--stand", help="inventory stand key used by hardware tests")
    group.addoption(
        "--inventory",
        type=Path,
        default=Path("inventory/stands.yaml"),
        help="path to YAML inventory (default: inventory/stands.yaml)",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Write each pytest session log and JUnit report to one artifacts directory."""
    marker_sequence = _get_marker_sequence(config)
    if marker_sequence:
        _validate_registered_markers(config, marker_sequence)
        config.stash[_MARKER_SEQUENCE_KEY] = tuple(marker_sequence)
        config.option.maxfail = 1

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


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Apply suite markers and require a stand only for hardware tests."""
    suite_markers = {"unit", "integration", "hardware"}
    for item in items:
        path_parts = set(item.path.parts)
        for marker_name in suite_markers & path_parts:
            item.add_marker(marker_name)

    marker_sequence = config.stash.get(_MARKER_SEQUENCE_KEY, ())
    if marker_sequence:
        _apply_marker_sequence(config, items, marker_sequence)

    has_hardware_tests = any(item.get_closest_marker("hardware") is not None for item in items)
    hardware_path_requested = not marker_sequence and any(
        "hardware" in Path(str(argument)).parts for argument in config.args
    )
    if (has_hardware_tests or hardware_path_requested) and config.getoption("stand") is None:
        raise pytest.UsageError("Hardware tests require --stand")


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


def _get_marker_sequence(config: pytest.Config) -> list[str]:
    """Resolve mutually exclusive command-line and named scenario selections."""
    marker_sequence = config.getoption("marker_sequence", default=None)
    scenario_name = config.getoption("scenario", default=None)
    if marker_sequence and scenario_name:
        raise pytest.UsageError("--marker-sequence and --scenario cannot be used together")

    try:
        if marker_sequence:
            return parse_marker_sequence(marker_sequence)
        if scenario_name:
            return load_scenario(config.rootpath, scenario_name).markers
    except ScenarioError as error:
        raise pytest.UsageError(str(error)) from error
    return []


def _validate_registered_markers(config: pytest.Config, marker_sequence: list[str]) -> None:
    """Reject sequence names not declared under pytest's strict marker configuration."""
    registered = {
        definition.partition(":")[0].partition("(")[0].strip()
        for definition in config.getini("markers")
    }
    unknown = [marker for marker in marker_sequence if marker not in registered]
    if unknown:
        raise pytest.UsageError(
            f"Marker '{unknown[0]}' is not registered. "
            "Register it in [tool.pytest.ini_options].markers."
        )


def _apply_marker_sequence(
    config: pytest.Config,
    items: list[pytest.Item],
    marker_sequence: tuple[str, ...],
) -> None:
    """Select and order collected items by their first and only scenario step."""
    grouped: dict[str, list[pytest.Item]] = {marker: [] for marker in marker_sequence}
    deselected: list[pytest.Item] = []

    for item in items:
        matching_markers = [
            marker for marker in marker_sequence if item.get_closest_marker(marker) is not None
        ]
        if len(matching_markers) > 1:
            markers = ", ".join(matching_markers)
            raise pytest.UsageError(
                f"Test '{item.nodeid}' belongs to multiple scenario steps: {markers}"
            )
        if matching_markers:
            grouped[matching_markers[0]].append(item)
        else:
            deselected.append(item)

    empty_marker = next((marker for marker, group in grouped.items() if not group), None)
    if empty_marker is not None:
        raise pytest.UsageError(
            f"Marker sequence requires '{empty_marker}', but no matching tests were collected."
        )

    if deselected:
        config.hook.pytest_deselected(items=deselected)
    items[:] = [item for marker in marker_sequence for item in grouped[marker]]


def _log_test_class(test_class: type[object] | None) -> None:
    """Log a test class name and its docstring, if the current test belongs to a class."""
    if test_class is None:
        return

    logger = logging.getLogger(test_class.__module__)
    description = getdoc(test_class) or "No description"
    header = f" {test_class.__name__} ".center(100, "=")
    logger.info("\n\n\n%s\n%s\n", header, description)
