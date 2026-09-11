import os
from pathlib import Path

from test_runner_service.artifacts import (
    find_result_directory,
    list_artifact_runs,
    list_artifacts,
    read_junit_summary,
    resolve_artifact,
    resolve_run_directory,
)


def test_junit_summary_and_artifact_listing(tmp_path: Path) -> None:
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
    artifacts = list_artifacts(run_directory)

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
    assert resolve_artifact(run_directory, "report.html") == html
    assert resolve_artifact(run_directory, "../../stands.yaml") is None


def test_result_directory_must_be_new_and_contain_junit(tmp_path: Path) -> None:
    old = tmp_path / "old"
    old.mkdir()
    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()
    complete = tmp_path / "complete" / "reports"
    complete.mkdir(parents=True)
    (complete / "junit.xml").write_text("<testsuites/>", encoding="utf-8")

    result = find_result_directory(tmp_path, {old})

    assert result == complete.parent


def test_artifact_runs_are_listed_newest_first(tmp_path: Path) -> None:
    older = tmp_path / "older-run"
    newer = tmp_path / "newer-run"
    older.mkdir()
    newer.mkdir()
    (older / "pytest.log").write_text("old\n", encoding="utf-8")
    (newer / "pytest.log").write_text("new\n", encoding="utf-8")
    os.utime(older, (1, 1))
    os.utime(newer, (2, 2))

    runs = list_artifact_runs(tmp_path)

    assert [run.run_id for run in runs.items] == ["newer-run", "older-run"]
    assert runs.items[0].items[0].download_url == "/v1/artifact-runs/newer-run/pytest.log"
    assert resolve_run_directory(tmp_path, "newer-run") == newer
    assert resolve_run_directory(tmp_path, "../outside") is None
