"""Exercise the real Allure adapter without ReportPortal, network, or hardware."""

import importlib.util
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from textwrap import dedent

import pytest


@pytest.mark.integration
def test_allure_reports_results_steps_attachments_and_keeps_local_artifacts(
    tmp_path: Path,
) -> None:
    if importlib.util.find_spec("allure_pytest") is None:
        pytest.skip("install the allure group to exercise the optional adapter")
    repository = Path(__file__).resolve().parents[2]
    (tmp_path / "conftest.py").write_text(
        (repository / "tests" / "conftest.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\ntimeout=120\nlog_level=INFO\nlog_file_level=DEBUG\n",
        encoding="utf-8",
    )
    (tmp_path / "test_example.py").write_text(
        dedent("""\
            import logging
            import allure
            import pytest
            from hardware_test.logging import StepLogger

            def test_pass() -> None:
                StepLogger(logging.getLogger(__name__)).log("allure integration action")
                with allure.step("Validate response"):
                    allure.attach("example response", name="response",
                                  attachment_type=allure.attachment_type.TEXT)

            def test_fail() -> None:
                assert False, "intentional failure"

            @pytest.mark.skip(reason="intentional skip")
            def test_skip() -> None:
                pass
            """),
        encoding="utf-8",
    )
    script = dedent("""\
        from unittest.mock import patch
        import pytest

        with patch("socket.socket.connect", side_effect=AssertionError("network is forbidden")):
            result = pytest.main(["test_example.py", "--strict-markers", "--allure",
                                  "-p", "no:pytest_reportportal"])
        assert result == pytest.ExitCode.TESTS_FAILED
        """)
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("RP_", "ALLURE_"))
        and key not in {"PYTEST_ADDOPTS", "PYTEST_DISABLE_PLUGIN_AUTOLOAD", "PYTEST_PLUGINS"}
    }
    result = subprocess.run(  # noqa: S603 - fixed interpreter and test-owned script
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    logs = list((tmp_path / "artifacts").glob("*/pytest.log"))
    assert len(logs) == 1
    run_directory = logs[0].parent
    assert "allure integration action" in logs[0].read_text(encoding="utf-8")
    assert (run_directory / "reports" / "junit.xml").is_file()
    assert (run_directory / "reports" / "report.html").is_file()
    results_directory = run_directory / "allure-results"
    junit = ET.parse(run_directory / "reports" / "junit.xml")  # noqa: S314 -- test-generated XML
    properties = {
        node.get("name"): node.get("value")
        for node in junit.findall("testsuite/properties/property")
    }
    environment_properties = (results_directory / "environment.properties").read_text()
    assert dict(line.split("=", 1) for line in environment_properties.splitlines()) == properties
    reports = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in results_directory.glob("*-result.json")
    ]
    assert len(reports) == 3
    by_name = {report["name"]: report for report in reports}
    assert {name: report["status"] for name, report in by_name.items()} == {
        "test_pass": "passed",
        "test_fail": "failed",
        "test_skip": "skipped",
    }
    assert "intentional failure" in by_name["test_fail"]["statusDetails"]["message"]
    assert "intentional skip" in by_name["test_skip"]["statusDetails"]["message"]
    step = by_name["test_pass"]["steps"][0]
    assert (step["name"], step["status"]) == ("Validate response", "passed")
    attachment = step["attachments"][0]
    assert (attachment["name"], attachment["type"]) == ("response", "text/plain")
    assert (results_directory / attachment["source"]).read_text() == "example response"
