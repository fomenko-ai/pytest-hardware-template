"""Tests for shared pytest plugin configuration."""

import logging
from pathlib import Path
from unittest.mock import Mock

import pytest

from hardware_test.pytest_plugin import (
    _log_test_class,
    pytest_configure,
    pytest_runtest_makereport,
)


class DescribedTestClass:
    """Check recovery after a service restart."""


def test_test_class_name_and_description_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger=__name__):
        _log_test_class(DescribedTestClass)

    header = " DescribedTestClass ".center(100, "=")
    assert caplog.messages == [f"\n\n\n{header}\nCheck recovery after a service restart.\n"]


def test_function_test_does_not_log_a_class(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        _log_test_class(None)

    assert caplog.messages == []


def test_default_timeout_is_enabled(pytestconfig: pytest.Config) -> None:
    assert pytestconfig.getini("timeout") == "120"


def test_paramiko_logger_is_muted_by_default(pytestconfig: pytest.Config) -> None:
    assert pytestconfig.getini("muted_loggers") == ["paramiko"]


def test_pytest_configure_uses_one_run_directory(tmp_path: Path) -> None:
    config = Mock(spec=pytest.Config)
    config.rootpath = tmp_path
    config.option = Mock()
    config.getini.return_value = []
    config.getoption.return_value = []

    pytest_configure(config)

    log_path = Path(config.option.log_file)
    junit_path = Path(config.option.xmlpath)
    latest_path = tmp_path / "artifacts" / "latest.log"
    assert log_path.name == "pytest.log"
    assert junit_path == log_path.parent / "reports" / "junit.xml"
    assert junit_path.parent.is_dir()
    assert latest_path.samefile(log_path)

    log_path.write_text("Step 1: Configure analyzer\n")

    assert latest_path.read_text() == "Step 1: Configure analyzer\n"


def test_pytest_configure_mutes_configured_and_cli_loggers(tmp_path: Path) -> None:
    def getoption(name: str, default: object = None) -> object:
        return ["urllib3"] if name == "mute_logger" else default

    config = Mock(spec=pytest.Config)
    config.rootpath = tmp_path
    config.option = Mock()
    config.getini.return_value = ["paramiko"]
    config.getoption.side_effect = getoption
    paramiko_logger = logging.getLogger("paramiko")
    urllib3_logger = logging.getLogger("urllib3")
    original_paramiko_level = paramiko_logger.level
    original_urllib3_level = urllib3_logger.level

    try:
        pytest_configure(config)

        assert paramiko_logger.level > logging.CRITICAL
        assert urllib3_logger.level > logging.CRITICAL
    finally:
        paramiko_logger.setLevel(original_paramiko_level)
        urllib3_logger.setLevel(original_urllib3_level)


@pytest.mark.parametrize(
    ("has_marker", "expected_shouldstop"),
    [(True, "stopping after failure in test_example.py::test_example"), (False, False)],
)
def test_stop_on_fail_marker_controls_session_stop(
    has_marker: bool,
    expected_shouldstop: str | bool,
) -> None:
    session = Mock(spec=pytest.Session)
    session.shouldstop = False
    item = Mock(spec=pytest.Item)
    item.session = session
    item.nodeid = "test_example.py::test_example"
    item.get_closest_marker.return_value = Mock() if has_marker else None
    report = Mock(spec=pytest.TestReport)
    report.failed = True
    report.when = "call"
    report.longreprtext = "AssertionError: expected 1, got 2"

    report_hook = pytest_runtest_makereport(item)
    next(report_hook)
    with pytest.raises(StopIteration) as hook_result:
        report_hook.send(report)

    assert hook_result.value.value is report
    assert session.shouldstop == expected_shouldstop


def test_failed_test_report_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    item = Mock(spec=pytest.Item)
    item.nodeid = "test_example.py::test_example"
    item.get_closest_marker.return_value = None
    report = Mock(spec=pytest.TestReport)
    report.failed = True
    report.when = "setup"
    report.longreprtext = "RuntimeError: fixture setup failed"

    report_hook = pytest_runtest_makereport(item)
    next(report_hook)
    with (
        caplog.at_level(logging.ERROR, logger="hardware_test.pytest_plugin"),
        pytest.raises(StopIteration),
    ):
        report_hook.send(report)

    assert caplog.messages == [
        "Test failed: test_example.py::test_example [setup]\nRuntimeError: fixture setup failed"
    ]
