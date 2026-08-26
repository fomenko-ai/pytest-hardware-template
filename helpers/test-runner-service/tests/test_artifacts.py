from pathlib import Path

from test_runner_service.artifacts import find_result_directory, list_artifacts, read_junit_summary


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

    summary = read_junit_summary(junit)
    artifacts = list_artifacts(run_directory)

    assert summary.model_dump() == {
        "total": 5,
        "passed": 2,
        "failed": 1,
        "errors": 1,
        "skipped": 1,
    }
    assert [item.name for item in artifacts.items] == ["pytest.log", "junit.xml"]


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
