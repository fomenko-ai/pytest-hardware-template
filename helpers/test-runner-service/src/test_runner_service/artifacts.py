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

ALLOWED_ARTIFACTS = {
    "pytest.log": Path("pytest.log"),
    "junit.xml": Path("reports/junit.xml"),
    "report.html": Path("reports/report.html"),
}


def snapshot_run_directories(artifacts_directory: Path) -> set[Path]:
    return {path for path in artifacts_directory.iterdir() if path.is_dir()}


def find_result_directory(artifacts_directory: Path, previous: set[Path]) -> Path | None:
    candidates = [
        path
        for path in artifacts_directory.iterdir()
        if path.is_dir() and path not in previous and (path / "reports" / "junit.xml").is_file()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda candidate: candidate.stat().st_mtime)


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


def list_artifacts(run_directory: Path, url_prefix: str = "/v1/current/artifacts") -> ArtifactList:
    items = []
    for name, relative_path in ALLOWED_ARTIFACTS.items():
        path = run_directory / relative_path
        if path.is_file():
            items.append(
                ArtifactItem(
                    name=name,
                    size=path.stat().st_size,
                    download_url=f"{url_prefix}/{name}",
                )
            )
    return ArtifactList(items=items)


def list_artifact_runs(artifacts_directory: Path) -> ArtifactRunList:
    root = artifacts_directory.resolve()
    runs = []
    for path in artifacts_directory.iterdir():
        resolved = path.resolve()
        if not path.is_dir() or resolved.parent != root:
            continue
        artifacts = list_artifacts(path, f"/v1/artifact-runs/{path.name}")
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


def resolve_artifact(run_directory: Path, name: str) -> Path | None:
    relative_path = ALLOWED_ARTIFACTS.get(name)
    if relative_path is None:
        return None
    path = run_directory / relative_path
    return path if path.is_file() else None
