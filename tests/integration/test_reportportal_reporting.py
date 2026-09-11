"""Exercise optional reporting agents with a fake ReportPortal client and no sockets."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
@pytest.mark.parametrize("allure_enabled", [False, True])
def test_reportportal_keeps_local_artifacts_and_reports_test_lifecycle(
    tmp_path: Path,
    allure_enabled: bool,
) -> None:
    if importlib.util.find_spec("pytest_reportportal") is None:
        pytest.skip("install the reportportal group to exercise the optional agent")
    if allure_enabled and importlib.util.find_spec("allure_pytest") is None:
        pytest.skip("install the allure group to exercise both optional agents")
    repository = Path(__file__).resolve().parents[2]
    (tmp_path / "conftest.py").write_text(
        (repository / "tests" / "conftest.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    # Mirror repository logging defaults, including the logger that otherwise prints API keys.
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\ntimeout=120\nlog_level=INFO\nlog_file_level=DEBUG\n"
        "muted_loggers=paramiko\n    pytest_reportportal.service\n",
        encoding="utf-8",
    )
    (tmp_path / "test_example.py").write_text(
        "import logging\nimport pytest\n"
        "from hardware_test.logging import StepLogger\n"
        "def test_pass() -> None:\n"
        "    StepLogger(logging.getLogger(__name__)).log('reporting integration step')\n"
        "    assert 2 + 2 == 4\n"
        "def test_fail() -> None:\n"
        "    assert False, 'intentional failure'\n"
        "@pytest.mark.skip(reason='intentional skip')\n"
        "def test_skip() -> None:\n"
        "    pass\n",
        encoding="utf-8",
    )
    script = """
from unittest.mock import MagicMock, patch
import pytest

pytest.register_assert_rewrite("pytest_reportportal")
client = MagicMock()
client.get_project_settings.return_value = {}
client.start_launch.return_value = "fake-launch"
client.start_test_item.side_effect = [f"item-{i}" for i in range(50)]
with (
    patch("pytest_reportportal.service.create_client", return_value=client) as factory,
    patch("reportportal_client.logs.current", return_value=client),
    patch("socket.socket.connect", side_effect=AssertionError("network is forbidden")),
):
    args = ["test_example.py", "--strict-markers", "--reportportal",
            "--rp-endpoint", "http://unused.invalid", "--rp-project", "test_project",
            "--rp-launch", "fake-launch", "-o", "rp_log_level=INFO"]
    import sys
    if sys.argv[1] == "allure":
        args.append("--allure")
    result = pytest.main(args)
assert result == pytest.ExitCode.TESTS_FAILED
factory.assert_called_once()
client.start_launch.assert_called_once()
client.finish_launch.assert_called_once()
client.close.assert_called_once()
statuses = [call.kwargs.get("status") for call in client.finish_test_item.call_args_list]
assert "PASSED" in statuses and "FAILED" in statuses and "SKIPPED" in statuses, statuses
assert any("reporting integration step" in str(call) for call in client.log.call_args_list)
"""
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("RP_")
        and key not in {"PYTEST_ADDOPTS", "PYTEST_DISABLE_PLUGIN_AUTOLOAD"}
    }
    environment["RP_API_KEY"] = "fake-key-must-not-be-logged"
    result = subprocess.run(  # noqa: S603 - fixed interpreter and test-owned script
        [sys.executable, "-c", script, "allure" if allure_enabled else "reportportal"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    runs = list((tmp_path / "artifacts").glob("*/pytest.log"))
    assert len(runs) == 1
    log = runs[0].read_text(encoding="utf-8")
    assert "reporting integration step" in log
    assert "fake-key-must-not-be-logged" not in log + result.stdout + result.stderr
    assert (runs[0].parent / "reports" / "junit.xml").is_file()
    assert (runs[0].parent / "reports" / "report.html").is_file()
    assert (runs[0].parent / "allure-results").is_dir() is allure_enabled
