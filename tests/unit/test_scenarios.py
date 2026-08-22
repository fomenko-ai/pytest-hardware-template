"""Tests for ordered marker scenario loading and validation."""

from pathlib import Path

import pytest

from hardware_test.scenarios import ScenarioError, load_scenario, parse_marker_sequence


def _write_scenario(root: Path, name: str, content: str) -> Path:
    """Write one scenario beneath the conventional project directory."""
    path = root / "test-runs" / "scenarios" / f"{name}.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_load_scenario_validates_and_normalizes_markers(tmp_path: Path) -> None:
    _write_scenario(
        tmp_path,
        "recovery",
        """\
name: recovery
markers:
  - clean
  - " recovery_check "
""",
    )

    scenario = load_scenario(tmp_path, "recovery")

    assert scenario.name == "recovery"
    assert scenario.markers == ["clean", "recovery_check"]


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("clean,,check", "invalid marker name"),
        ("clean,check,clean", "duplicate marker 'clean'"),
        ("clean,bad-marker", "invalid marker name 'bad-marker'"),
    ],
)
def test_parse_marker_sequence_rejects_invalid_values(value: str, message: str) -> None:
    with pytest.raises(ScenarioError, match=message):
        parse_marker_sequence(value)


def test_load_scenario_rejects_unknown_scenario(tmp_path: Path) -> None:
    with pytest.raises(ScenarioError, match="Cannot read scenario 'missing'"):
        load_scenario(tmp_path, "missing")


def test_load_scenario_rejects_invalid_yaml(tmp_path: Path) -> None:
    _write_scenario(tmp_path, "broken", "name: broken\nmarkers: [clean\n")

    with pytest.raises(ScenarioError, match="Invalid YAML in scenario 'broken'"):
        load_scenario(tmp_path, "broken")


def test_load_scenario_rejects_mismatched_name(tmp_path: Path) -> None:
    _write_scenario(tmp_path, "recovery", "name: another\nmarkers: [clean]\n")

    with pytest.raises(ScenarioError, match="declares name 'another', expected 'recovery'"):
        load_scenario(tmp_path, "recovery")


def test_load_scenario_rejects_path_traversal(tmp_path: Path) -> None:
    with pytest.raises(ScenarioError, match="Invalid scenario name"):
        load_scenario(tmp_path, "../recovery")
