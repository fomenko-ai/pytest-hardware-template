"""Tests for shared pytest plugin configuration."""

import logging
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from hardware_test.pytest_plugin import (
    _log_test_class,
    get_run_directory,
    pytest_configure,
    pytest_runtest_makereport,
    pytest_terminal_summary,
)

pytest_plugins = ["pytester"]


class DescribedTestClass:
    """Check recovery after a service restart."""


def test_test_class_name_and_description_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger=__name__):
        _log_test_class(DescribedTestClass)

    header = " DescribedTestClass ".center(100, "-")
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
    config = Mock()
    config.rootpath = tmp_path
    config.option = Mock()
    config.stash = pytest.Stash()
    config.getini.return_value = []
    config.getoption.return_value = []

    pytest_configure(config)

    log_path = Path(config.option.log_file)
    junit_path = Path(config.option.xmlpath)
    html_path = Path(config.option.htmlpath)
    latest_path = tmp_path / "artifacts" / "latest.log"
    assert log_path.name == "pytest.log"
    assert junit_path == log_path.parent / "reports" / "junit.xml"
    assert html_path == log_path.parent / "reports" / "report.html"
    assert config.option.self_contained_html is True
    assert junit_path.parent.is_dir()
    assert latest_path.samefile(log_path)
    assert get_run_directory(config) == log_path.parent

    log_path.write_text("Step 1: Configure analyzer\n")

    assert latest_path.read_text() == "Step 1: Configure analyzer\n"


def test_pytest_session_generates_self_contained_html_report(pytester: pytest.Pytester) -> None:
    pytester.makepyfile("def test_example():\n    assert True\n")

    result = pytester.runpytest_subprocess("-q")

    result.assert_outcomes(passed=1)
    reports = list(pytester.path.glob("artifacts/*/reports/report.html"))
    assert len(reports) == 1
    report = reports[0].read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in report
    assert '<style type="text/css">' in report
    assert "<script>" in report


def test_pytest_configure_mutes_configured_and_cli_loggers(tmp_path: Path) -> None:
    def getoption(name: str, default: object = None) -> object:
        return ["urllib3"] if name == "mute_logger" else default

    config = Mock(spec=pytest.Config)
    config.rootpath = tmp_path
    config.option = Mock()
    config.stash = pytest.Stash()
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


def test_terminal_summary_is_logged() -> None:
    terminalreporter = Mock(spec=pytest.TerminalReporter)
    terminalreporter._numcollected = 6
    terminalreporter._session_start = Mock()
    terminalreporter._session_start.elapsed.return_value.seconds = 1.25
    terminalreporter.stats = {
        "passed": [Mock(count_towards_summary=True) for _ in range(3)],
        "skipped": [Mock(count_towards_summary=True)],
        "deselected": [Mock(count_towards_summary=True) for _ in range(2)],
    }

    with patch("hardware_test.pytest_plugin.logger") as logger_mock:
        pytest_terminal_summary(terminalreporter, pytest.ExitCode.OK)

    logger_mock.info.assert_called_once_with(
        "\n\n\n%s",
        "======================================= Test session summary "
        "=======================================\n"
        "\n"
        "Total: 4\n"
        "\n"
        "Passed: 3\n"
        "Failed: 0\n"
        "Skipped: 1\n"
        "Errors: 0\n"
        "\n"
        "Duration: 1.25s\n"
        "\n"
        "Exit code: 0\n"
        "\n"
        "====================================================================================================",
    )


def test_terminal_summary_lists_failed_test_phases() -> None:
    terminalreporter = Mock(spec=pytest.TerminalReporter)
    terminalreporter._numcollected = 3
    terminalreporter._session_start = Mock()
    terminalreporter._session_start.elapsed.return_value.seconds = 2.5
    call_failure = Mock(
        nodeid="tests/unit/test_device.py::test_command",
        when="call",
        count_towards_summary=True,
    )
    setup_error = Mock(
        nodeid="tests/integration/test_stand.py::test_connect",
        when="setup",
        count_towards_summary=True,
    )
    teardown_error = Mock(
        nodeid="tests/integration/test_stand.py::test_disconnect",
        when="teardown",
        count_towards_summary=True,
    )
    terminalreporter.stats = {
        "failed": [call_failure],
        "error": [setup_error, teardown_error],
    }

    with patch("hardware_test.pytest_plugin.logger") as logger_mock:
        pytest_terminal_summary(terminalreporter, pytest.ExitCode.TESTS_FAILED)

    logger_mock.info.assert_called_once_with(
        "\n\n\n%s",
        "======================================= Test session summary "
        "=======================================\n"
        "\n"
        "Total: 3\n"
        "\n"
        "Passed: 0\n"
        "Failed: 1\n"
        "Skipped: 0\n"
        "Errors: 2\n"
        "\n"
        "Duration: 2.50s\n"
        "\n"
        "Exit code: 1\n"
        "\n"
        "\n"
        "Failed tests:\n"
        "  - tests/unit/test_device.py::test_command\n"
        "  - tests/integration/test_stand.py::test_connect [setup]\n"
        "  - tests/integration/test_stand.py::test_disconnect [teardown]\n"
        "\n"
        "====================================================================================================",
    )
