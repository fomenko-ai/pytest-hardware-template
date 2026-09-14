from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree

from test_runner_service.models import (
    ArtifactItem,
    ArtifactList,
    ArtifactRun,
    ArtifactRunList,
    TestSummary,
)
from test_runner_service.settings import Settings


def configured_artifacts(settings: Settings) -> dict[str, Path]:
    return {
        name: path
        for name, path in (
            ("pytest.log", settings.pytest_log_path),
            ("junit.xml", settings.junit_path),
            ("report.html", settings.html_path),
        )
        if path is not None
    }


def resolve_report_path(run_directory: Path, relative_path: Path) -> Path:
    root = run_directory.resolve()
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError("report path escapes the session directory")
    return path


def read_junit_summary(junit_file: Path) -> TestSummary:
    root = ElementTree.parse(junit_file).getroot()  # noqa: S314 - generated local pytest XML.
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    total = sum(int(suite.attrib.get("tests", 0)) for suite in suites)
    failures = sum(int(suite.attrib.get("failures", 0)) for suite in suites)
    errors = sum(int(suite.attrib.get("errors", 0)) for suite in suites)
    skipped = sum(int(suite.attrib.get("skipped", 0)) for suite in suites)
    return TestSummary(
        total=total,
        passed=max(total - failures - errors - skipped, 0),
        failed=failures,
        errors=errors,
        skipped=skipped,
    )


def list_artifacts(
    run_directory: Path,
    settings: Settings,
    url_prefix: str = "/v1/current/artifacts",
) -> ArtifactList:
    items = []
    for name, relative_path in configured_artifacts(settings).items():
        path = resolve_report_path(run_directory, relative_path)
        if path.is_file():
            items.append(
                ArtifactItem(
                    name=name,
                    size=path.stat().st_size,
                    download_url=f"{url_prefix}/{name}",
                )
            )
    return ArtifactList(items=items)


def list_artifact_runs(settings: Settings) -> ArtifactRunList:
    artifacts_directory = settings.artifacts_directory
    root = artifacts_directory.resolve()
    runs = []
    for path in artifacts_directory.iterdir():
        resolved = path.resolve()
        if not path.is_dir() or resolved.parent != root:
            continue
        artifacts = list_artifacts(path, settings, f"/v1/artifact-runs/{path.name}")
        if not artifacts.items:
            continue
        runs.append(
            ArtifactRun(
                run_id=path.name,
                modified_at=datetime.fromtimestamp(path.stat().st_mtime, UTC),
                items=artifacts.items,
            )
        )
    runs.sort(key=lambda run: run.modified_at, reverse=True)
    return ArtifactRunList(items=runs)


def resolve_run_directory(artifacts_directory: Path, run_id: str) -> Path | None:
    root = artifacts_directory.resolve()
    path = (root / run_id).resolve()
    return path if path.parent == root and path.is_dir() else None


def resolve_artifact(run_directory: Path, settings: Settings, name: str) -> Path | None:
    relative_path = configured_artifacts(settings).get(name)
    if relative_path is None:
        return None
    path = resolve_report_path(run_directory, relative_path)
    return path if path.is_file() else None
