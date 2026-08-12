"""Tests for shared pytest plugin configuration."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from hardware_test.pytest_plugin import pytest_configure, pytest_runtest_makereport


def test_default_timeout_is_enabled(pytestconfig: pytest.Config) -> None:
    assert pytestconfig.getini("timeout") == "120"


def test_pytest_configure_uses_one_run_directory(tmp_path: Path) -> None:
    config = Mock(spec=pytest.Config)
    config.rootpath = tmp_path
    config.option = Mock()

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

    report_hook = pytest_runtest_makereport(item)
    next(report_hook)
    with pytest.raises(StopIteration) as hook_result:
        report_hook.send(report)

    assert hook_result.value.value is report
    assert session.shouldstop == expected_shouldstop
