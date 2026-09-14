"""Verify run context and failure capture using local pytest subprocesses."""

import html
import importlib.util
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from textwrap import dedent

import pytest


@pytest.mark.parametrize("collection_error", [False, True])
@pytest.mark.parametrize("allure_enabled", [False, True])
def test_run_context_survives_collection_and_matches_reports(
    tmp_path: Path, collection_error: bool, allure_enabled: bool
) -> None:
    if allure_enabled and importlib.util.find_spec("allure_pytest") is None:
        pytest.skip("install the allure group to exercise the optional adapter")
    repository = Path(__file__).resolve().parents[2]
    (tmp_path / "conftest.py").write_text(
        (repository / "tests" / "conftest.py").read_text(), encoding="utf-8"
    )
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\ntimeout=120\nlog_level=INFO\nlog_file_level=INFO\n"
        "junit_family=xunit2\njunit_logging=all\njunit_log_passing_tests=false\n",
        encoding="utf-8",
    )
    source = dedent("""\
        import logging
        import sys
        import pytest

        def test_pass() -> None:
            print("passing output")

        def test_fail() -> None:
            print("failure stdout")
            print("failure stderr", file=sys.stderr)
            logging.info("failure log")
            assert False, "failure traceback"

        @pytest.fixture
        def broken() -> None:
            print("setup output")
            raise RuntimeError("setup traceback")

        def test_setup_error(broken: None) -> None:
            pass
        """)
    if collection_error:
        source = 'raise RuntimeError("collection probe")\n'
    (tmp_path / "test_probe.py").write_text(source, encoding="utf-8")
    script = dedent("""\
        import sys
        from unittest.mock import patch
        import pytest
        import hardware_test.pytest_plugin

        args = ["--strict-markers", "-p", "no:pytest_reportportal", "test_probe.py"]
        if sys.argv[1] == "allure":
            args.append("--allure")
        with (
            patch("hardware_test.pytest_plugin._git_revision", return_value="a" * 40) as git,
            patch("socket.socket.connect", side_effect=AssertionError("network is forbidden")),
        ):
            result = pytest.main(args)
        git.assert_called_once()
        assert result == int(sys.argv[2])
        """)
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("RP_", "ALLURE_", "PYTEST_"))
    }
    result = subprocess.run(  # noqa: S603 -- fixed interpreter and test-owned script
        [
            sys.executable,
            "-c",
            script,
            "allure" if allure_enabled else "plain",
            "2" if collection_error else "1",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    reports = list((tmp_path / "artifacts").glob("*/reports"))
    assert len(reports) == 1
    report_dir = reports[0]
    log = (report_dir.parent / "pytest.log").read_text()
    assert log.count(" Run metadata ") == 1
    match = re.search(r'data-jsonblob="([^"]*)"', (report_dir / "report.html").read_text())
    assert match is not None
    report_environment = json.loads(html.unescape(match[1]))["environment"]
    assert report_environment["run_id"] == report_dir.parent.name
    assert report_environment["git_revision"] == "a" * 40
    assert "stand" not in report_environment
    assert "python_version" not in report_environment
    assert "pytest_version" not in report_environment
    for key in ("run_id", "git_revision"):
        assert f"{key}: {report_environment[key]}" in log
    junit = ET.parse(report_dir / "junit.xml")  # noqa: S314 -- local test-generated XML
    suite = junit.find("testsuite")
    assert suite is not None
    if collection_error:
        assert suite.find("properties") is None
        assert suite.get("errors") == "1"
    else:
        properties = {
            node.get("name"): node.get("value") for node in suite.findall("properties/property")
        }
        for key, value in properties.items():
            assert f"{key}: {value}" in log
        assert suite.get("tests") == "3"
        assert suite.get("failures") == "1"
        assert suite.get("errors") == "1"
        passed, failed, setup_error = suite.findall("testcase")
        assert passed.find("system-out") is None
        assert passed.find("system-err") is None
        assert "failure stdout" in failed.findtext("system-out", "")
        assert "failure log" in failed.findtext("system-out", "")
        assert "failure stderr" in failed.findtext("system-err", "")
        assert "failure traceback" in failed.findtext("failure", "")
        assert "setup traceback" in setup_error.findtext("error", "")
        # pytest omits setup capture when teardown passes and passing logs are disabled.
        assert setup_error.find("system-out") is None
    allure_file = report_dir.parent / "allure-results" / "environment.properties"
    assert allure_file.is_file() is allure_enabled
    if allure_enabled:
        metadata = dict(line.split("=", 1) for line in allure_file.read_text().splitlines())
        assert metadata["run_id"] == report_dir.parent.name
        assert metadata["git_revision"] == "a" * 40
        assert "stand" not in metadata
        for key, value in metadata.items():
            assert f"{key}: {value}" in log
