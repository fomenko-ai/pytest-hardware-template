"""Project reporting policy and shared framework-test fixtures."""

import logging
from collections.abc import Callable, Generator
from inspect import getdoc
from pathlib import Path

import pytest

from hardware_test.exceptions import HardwareTestError
from hardware_test.inventory import Inventory, load_inventory
from hardware_test.pytest_plugin import get_run_directory, get_run_metadata
from hardware_test.settings import Settings

_MUTED_LOG_LEVEL = logging.CRITICAL + 1
_REPORT_ENVIRONMENT_KEY = pytest.StashKey[dict[str, object]]()
_SUMMARY_WIDTH = 100

logger = logging.getLogger(__name__)


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register reporting options owned by this repository's tests."""
    group = parser.getgroup("hardware-test-reports")
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
        "--allure",
        action="store_true",
        help="write Allure results into the current artifacts run directory",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Configure the template's local reports and optional Allure collection."""
    if not config.pluginmanager.has_plugin("html"):
        raise pytest.UsageError("Template reports require: uv sync --group reporting")
    configured_loggers = config.getini("muted_loggers")
    cli_loggers = config.getoption("mute_logger", default=[])
    for logger_name in {*configured_loggers, *cli_loggers}:
        logging.getLogger(logger_name).setLevel(_MUTED_LOG_LEVEL)

    run_dir = get_run_directory(config)
    reports_dir = run_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=False)
    log_path = run_dir / "pytest.log"
    log_path.touch(exist_ok=False)
    latest_candidate = run_dir / ".latest.log"
    latest_candidate.hardlink_to(log_path)
    latest_candidate.replace(run_dir.parent / "latest.log")
    config.option.log_file = str(log_path)
    config.option.xmlpath = reports_dir / "junit.xml"
    config.option.htmlpath = reports_dir / "report.html"
    config.option.self_contained_html = True
    if not config.getoption("allure", default=False):
        return
    if not config.pluginmanager.has_plugin("allure_pytest"):
        raise pytest.UsageError("--allure requires the dependency group: uv sync --group allure")
    if config.getoption("allure_report_dir", default=None) is not None:
        raise pytest.UsageError("--allure and --alluredir cannot be used together")
    config.option.allure_report_dir = str(get_run_directory(config) / "allure-results")


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session: pytest.Session) -> None:
    """Publish shared run context before optional reporting agents start their launch."""
    config = session.config
    metadata = get_run_metadata(config)
    environment = config.stash.get(_REPORT_ENVIRONMENT_KEY, None)
    if environment is not None:
        environment.update(
            (name, value)
            for name, value in metadata.items()
            if name not in {"python_version", "pytest_version"}
        )
    lines = [
        "",
        " Run metadata ".center(_SUMMARY_WIDTH, "="),
        "",
        *(f"{name}: {value}" for name, value in metadata.items()),
        "",
        "=" * _SUMMARY_WIDTH,
        "",
    ]
    logger.info("\n%s", "\n".join(lines))
    allure_directory = config.getoption("allure_report_dir", default=None)
    if allure_directory is not None:
        results = Path(allure_directory)
        results.mkdir(parents=True, exist_ok=True)
        properties = "".join(
            f"{name}={_escape_property(value)}\n" for name, value in metadata.items()
        )
        (results / "environment.properties").write_text(properties, encoding="ascii")

    # pytest-reportportal 5.6.11 resolves CLI/INI/environment settings during configure.
    # Update that snapshot before its session-start hook sends the launch request.
    reporter = getattr(config, "_reporter_config", None)
    if reporter is not None and getattr(config, "_rp_enabled", False):
        attributes: list[str] = reporter.rp_launch_attributes or []
        reporter.rp_launch_attributes = [
            attribute for attribute in attributes if attribute.partition(":")[0] not in metadata
        ] + [f"{name}:{value}" for name, value in metadata.items()]


def _escape_property(value: str) -> str:
    """Encode a Java properties value without losing whitespace or Unicode."""
    escaped: list[str] = []
    for character in value:
        if character in "\\ =:#!":
            escaped.append(f"\\{character}")
        elif "!" <= character <= "~":
            escaped.append(character)
        else:
            encoded = character.encode("utf-16-be")
            escaped.extend(
                f"\\u{int.from_bytes(encoded[index : index + 2]):04x}"
                for index in range(0, len(encoded), 2)
            )
    return "".join(escaped)


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


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter,
    exitstatus: pytest.ExitCode,
) -> None:
    """Log the test-session result and the node IDs of failed reports."""
    duration = terminalreporter._session_start.elapsed().seconds
    lines = [
        " Test session summary ".center(_SUMMARY_WIDTH, "="),
        "",
        f"Total: {_selected_test_count(terminalreporter)}",
        "",
        f"Passed: {_summary_count(terminalreporter, 'passed')}",
        f"Failed: {_summary_count(terminalreporter, 'failed')}",
        f"Skipped: {_summary_count(terminalreporter, 'skipped')}",
        f"Errors: {_summary_count(terminalreporter, 'error')}",
        "",
        f"Duration: {duration:.2f}s",
        "",
        f"Exit code: {int(exitstatus)}",
    ]

    failed_reports = [
        report
        for category in ("failed", "error")
        for report in terminalreporter.stats.get(category, ())
        if getattr(report, "count_towards_summary", True)
    ]
    if failed_reports:
        lines.extend(("", "", "Failed tests:"))
        for report in failed_reports:
            nodeid = getattr(report, "nodeid", "unknown")
            phase = getattr(report, "when", None)
            phase_suffix = f" [{phase}]" if phase not in (None, "call") else ""
            lines.append(f"  - {nodeid}{phase_suffix}")

    lines.extend(("", "=" * _SUMMARY_WIDTH))
    logger.info("\n\n\n%s", "\n".join(lines))


def _selected_test_count(terminalreporter: pytest.TerminalReporter) -> int:
    """Return the number of collected tests selected for this session."""
    return terminalreporter._numcollected - _summary_count(terminalreporter, "deselected")


def _summary_count(terminalreporter: pytest.TerminalReporter, category: str) -> int:
    """Count reports that pytest includes in its terminal summary."""
    return sum(
        getattr(report, "count_towards_summary", True)
        for report in terminalreporter.stats.get(category, ())
    )


@pytest.hookimpl(optionalhook=True)
def pytest_metadata(metadata: dict[str, object], config: pytest.Config) -> None:
    """Keep the report environment available for session-start metadata."""
    config.stash[_REPORT_ENVIRONMENT_KEY] = metadata


@pytest.fixture(scope="session", autouse=True)
def record_run_metadata(
    pytestconfig: pytest.Config,
    record_testsuite_property: Callable[[str, object], None],
) -> Generator[None]:
    """Copy the session's shared run facts into the standard JUnit suite."""
    for name, value in get_run_metadata(pytestconfig).items():
        record_testsuite_property(name, value)
    try:
        yield
    finally:
        pass  # Metadata recording acquires no resources that need cleanup.


@pytest.fixture(scope="class", autouse=True)
def log_test_class(request: pytest.FixtureRequest) -> None:
    """Log the test class name and description once before its tests."""
    _log_test_class(request.cls)


def _log_test_class(test_class: type[object] | None) -> None:
    """Log a test class name and its docstring, if the current test belongs to a class."""
    if test_class is None:
        return

    logger = logging.getLogger(test_class.__module__)
    description = getdoc(test_class) or "No description"
    header = f" {test_class.__name__} ".center(100, "-")
    logger.info("\n\n\n%s\n%s\n", header, description)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item,
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    """Record failed test phases in the template's diagnostic log."""
    report = yield
    if report.failed:
        logger.error(
            "Test failed: %s [%s]\n%s",
            item.nodeid,
            report.when,
            report.longreprtext,
        )
    return report
