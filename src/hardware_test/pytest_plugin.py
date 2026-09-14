"""Pytest command-line integration for inventory-backed hardware tests."""

import logging
import platform
import re
import shutil
import subprocess
from collections.abc import Generator, Mapping
from datetime import datetime
from pathlib import Path

import pytest

from hardware_test.logging import StepLogger
from hardware_test.scenarios import ScenarioError, load_scenario, parse_marker_sequence

_MARKER_SEQUENCE_KEY = pytest.StashKey[tuple[str, ...]]()
_RUN_DIRECTORY_KEY = pytest.StashKey[Path]()
_RUN_METADATA_KEY = pytest.StashKey[dict[str, str]]()
_RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register hardware selection options."""
    group = parser.getgroup("hardware-test")
    group.addoption("--run-id", help="explicit identity for this pytest session")
    group.addoption(
        "--artifacts-root",
        type=Path,
        help="artifact root (relative paths resolve against the pytest project root)",
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


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    """Configure execution and allocate a new artifact directory for this session."""
    marker_sequence = _get_marker_sequence(config)
    if marker_sequence:
        _validate_registered_markers(config, marker_sequence)
        config.stash[_MARKER_SEQUENCE_KEY] = tuple(marker_sequence)
        config.option.maxfail = 1

    supplied_id = config.getoption("run_id", default=None)
    run_id = (
        supplied_id
        if supplied_id is not None
        else datetime.now().astimezone().strftime("%Y-%m-%d_%H-%M-%S_%f")
    )
    if _RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise pytest.UsageError(
            "Invalid --run-id: use 1-128 ASCII letters, digits, dots, underscores or hyphens, "
            "starting with a letter or digit"
        )
    configured_root = config.getoption("artifacts_root", default=None)
    root = (config.rootpath / (configured_root or Path("artifacts"))).resolve()
    run_dir = root / run_id
    try:
        root.mkdir(parents=True, exist_ok=True)
        if run_dir.resolve().parent != root:
            raise pytest.UsageError("Session directory must stay within the artifacts root")
        run_dir.mkdir(exist_ok=False)
    except OSError as error:
        raise pytest.UsageError(
            f"Cannot create new session directory '{run_dir}': {error}"
        ) from error
    config.stash[_RUN_DIRECTORY_KEY] = run_dir


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
    """Stop the session after failure when requested by the test marker."""
    report = yield
    if report.failed and item.get_closest_marker("stop_on_fail") is not None:
        item.session.shouldstop = f"stopping after failure in {item.nodeid}"
    return report


def get_run_directory(config: pytest.Config) -> Path:
    """Return the artifact directory allocated for the current pytest session."""
    return config.stash[_RUN_DIRECTORY_KEY]


def _git_revision(root: Path) -> str | None:
    """Return the local checkout revision when Git is available."""
    git = shutil.which("git")
    if git is None:
        return None
    try:
        result = subprocess.run(  # noqa: S603 -- fixed read-only Git arguments, no shell
            [git, "-C", str(root), "rev-parse", "--verify", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except OSError, subprocess.TimeoutExpired:
        return None
    return result.stdout.strip() or None if result.returncode == 0 else None


def get_run_metadata(config: pytest.Config) -> Mapping[str, str]:
    """Return a copy of run facts, collecting them once after artifact configuration."""
    if _RUN_METADATA_KEY in config.stash:
        return config.stash[_RUN_METADATA_KEY].copy()
    properties = {
        "run_id": get_run_directory(config).name,
        "python_version": platform.python_version(),
        "pytest_version": pytest.__version__,
        "git_revision": _git_revision(config.rootpath),
        "stand": config.getoption("stand"),
        "scenario": config.getoption("scenario"),
        "marker_sequence": ",".join(config.stash.get(_MARKER_SEQUENCE_KEY, ())),
    }
    metadata = {name: value for name, value in properties.items() if value}
    config.stash[_RUN_METADATA_KEY] = metadata
    return metadata.copy()


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session: pytest.Session) -> None:
    """Collect shared run facts once before test collection."""
    get_run_metadata(session.config)


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
