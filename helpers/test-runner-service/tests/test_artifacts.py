import os
from pathlib import Path

from test_runner_service.artifacts import (
    list_artifact_runs,
    list_artifacts,
    read_junit_summary,
    resolve_artifact,
    resolve_run_directory,
)
from test_runner_service.settings import Settings


def test_junit_summary_and_artifact_listing(tmp_path: Path, settings: Settings) -> None:
    run_directory = tmp_path / "2026-run"
    reports = run_directory / "reports"
    reports.mkdir(parents=True)
    (run_directory / "pytest.log").write_text("diagnostics\n", encoding="utf-8")
    junit = reports / "junit.xml"
    junit.write_text(
        '<testsuites><testsuite tests="5" failures="1" errors="1" skipped="1"/></testsuites>',
        encoding="utf-8",
    )
    html = reports / "report.html"
    html.write_text("<!doctype html><title>Test report</title>", encoding="utf-8")

    summary = read_junit_summary(junit)
    artifacts = list_artifacts(run_directory, settings)

    assert summary.model_dump() == {
        "total": 5,
        "passed": 2,
        "failed": 1,
        "errors": 1,
        "skipped": 1,
    }
    assert [item.name for item in artifacts.items] == [
        "pytest.log",
        "junit.xml",
        "report.html",
    ]
    assert resolve_artifact(run_directory, settings, "report.html") == html
    assert resolve_artifact(run_directory, settings, "../../stands.yaml") is None


def test_artifact_runs_are_listed_newest_first(tmp_path: Path, settings: Settings) -> None:
    settings = settings.model_copy(update={"artifacts_directory": tmp_path})
    older = tmp_path / "older-run"
    newer = tmp_path / "newer-run"
    older.mkdir()
    newer.mkdir()
    (older / "pytest.log").write_text("old\n", encoding="utf-8")
    (newer / "pytest.log").write_text("new\n", encoding="utf-8")
    os.utime(older, (1, 1))
    os.utime(newer, (2, 2))

    runs = list_artifact_runs(settings)

    assert [run.run_id for run in runs.items] == ["newer-run", "older-run"]
    assert runs.items[0].items[0].download_url == "/v1/artifact-runs/newer-run/pytest.log"
    assert resolve_run_directory(tmp_path, "newer-run") == newer
    assert resolve_run_directory(tmp_path, "../outside") is None


def test_configured_paths_keep_public_names_and_disabled_reports_hidden(
    tmp_path: Path, settings: Settings
) -> None:
    run_directory = tmp_path / "run"
    custom = run_directory / "custom"
    custom.mkdir(parents=True)
    log = custom / "session.txt"
    log.write_text("diagnostics\n", encoding="utf-8")
    configured = settings.model_copy(
        update={
            "pytest_log_path": Path("custom/session.txt"),
            "junit_path": None,
            "html_path": None,
        }
    )

    artifacts = list_artifacts(run_directory, configured)

    assert [item.name for item in artifacts.items] == ["pytest.log"]
    assert resolve_artifact(run_directory, configured, "pytest.log") == log
    assert resolve_artifact(run_directory, configured, "junit.xml") is None
    assert resolve_artifact(run_directory, configured, "report.html") is None
