"""Runtime allocation is independent of reports and cannot reuse another session."""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from hardware_test.pytest_plugin import get_run_directory, get_run_metadata, pytest_configure


def _config(root: Path, **options: object) -> Mock:
    config = Mock(spec=pytest.Config)
    config.rootpath = root
    config.stash = pytest.Stash()
    config.option = Mock()
    config.getoption.side_effect = lambda name, default=None: options.get(name, default)
    return config


def test_runtime_allocates_an_empty_session_without_report_options(tmp_path: Path) -> None:
    config = _config(tmp_path, run_id="operation-123")
    pytest_configure(config)

    directory = get_run_directory(config)
    assert directory == tmp_path / "artifacts" / "operation-123"
    assert directory.is_dir()
    assert list(directory.iterdir()) == []
    assert not (directory.parent / "latest.log").exists()
    assert (
        not {"log_file", "xmlpath", "htmlpath", "self_contained_html"} & vars(config.option).keys()
    )


@pytest.mark.parametrize("absolute", [False, True])
def test_artifacts_root_can_be_relative_or_absolute(tmp_path: Path, absolute: bool) -> None:
    root = tmp_path / "custom" if absolute else Path("custom")
    config = _config(tmp_path, run_id="run-123", artifacts_root=root)
    pytest_configure(config)
    assert get_run_directory(config) == tmp_path / "custom" / "run-123"


@pytest.mark.parametrize(
    "run_id", ["", ".", "..", "../escape", "/absolute", "a/b", r"a\b", " x", "x" * 129]
)
def test_invalid_external_id_is_rejected_before_allocation(tmp_path: Path, run_id: str) -> None:
    config = _config(tmp_path, run_id=run_id)
    with pytest.raises(pytest.UsageError, match="Invalid --run-id"):
        pytest_configure(config)
    assert not (tmp_path / "artifacts").exists()
    with pytest.raises(KeyError):
        get_run_directory(config)


@pytest.mark.parametrize("existing_kind", ["directory", "file", "symlink"])
def test_existing_session_is_never_reused(tmp_path: Path, existing_kind: str) -> None:
    root = tmp_path / "artifacts"
    root.mkdir()
    session = root / "existing"
    if existing_kind == "directory":
        session.mkdir()
    elif existing_kind == "file":
        session.write_text("existing content")
    else:
        outside = tmp_path / "outside"
        outside.mkdir()
        session.symlink_to(outside, target_is_directory=True)
    config = _config(tmp_path, run_id="existing")
    with pytest.raises(pytest.UsageError):
        pytest_configure(config)
    with pytest.raises(KeyError):
        get_run_directory(config)
    if existing_kind == "file":
        assert session.read_text() == "existing content"
    else:
        assert list(session.iterdir()) == []


def test_allocation_failure_does_not_publish_a_directory(tmp_path: Path) -> None:
    root = tmp_path / "file"
    root.write_text("not a directory")
    config = _config(tmp_path, run_id="run", artifacts_root=root)
    with pytest.raises(pytest.UsageError, match="Cannot create new session directory"):
        pytest_configure(config)
    with pytest.raises(KeyError):
        get_run_directory(config)


def test_metadata_is_collected_once_and_returned_as_an_independent_copy(tmp_path: Path) -> None:
    config = _config(tmp_path, run_id="metadata-run", stand="stand-01")
    pytest_configure(config)
    with patch("hardware_test.pytest_plugin._git_revision", return_value="revision") as revision:
        first = get_run_metadata(config)
        second = get_run_metadata(config)
    revision.assert_called_once_with(tmp_path)
    assert first == second
    assert first is not second
    assert first["run_id"] == "metadata-run"
    assert first["stand"] == "stand-01"
    assert first["git_revision"] == "revision"
    assert "scenario" not in first
    assert "marker_sequence" not in first


def test_generated_id_keeps_the_template_timestamp_format(tmp_path: Path) -> None:
    config = _config(tmp_path)
    pytest_configure(config)
    name = get_run_directory(config).name
    datetime.strptime(name, "%Y-%m-%d_%H-%M-%S_%f")
