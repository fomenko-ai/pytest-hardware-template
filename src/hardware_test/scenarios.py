"""Loading and validation for ordered pytest marker scenarios."""

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, field_validator

_SCENARIO_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_MARKER_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ScenarioError(ValueError):
    """Raised when a test-run scenario cannot be resolved or validated."""


class ScenarioConfig(BaseModel):
    """One named sequence of registered pytest markers."""

    model_config = ConfigDict(extra="forbid")

    name: str
    markers: list[str]

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Require a filename-safe scenario name."""
        if _SCENARIO_NAME_PATTERN.fullmatch(value) is None:
            raise ValueError("must contain only letters, numbers, underscores, and hyphens")
        return value

    @field_validator("markers")
    @classmethod
    def validate_markers(cls, values: list[str]) -> list[str]:
        """Normalize and validate a non-empty sequence of unique marker names."""
        markers = [value.strip() for value in values]
        if not markers:
            raise ValueError("must contain at least one marker")
        invalid = [marker for marker in markers if _MARKER_NAME_PATTERN.fullmatch(marker) is None]
        if invalid:
            raise ValueError(f"contains invalid marker name '{invalid[0]}'")
        duplicate = _first_duplicate(markers)
        if duplicate is not None:
            raise ValueError(f"contains duplicate marker '{duplicate}'")
        return markers


def parse_marker_sequence(value: str) -> list[str]:
    """Parse the comma-separated value accepted by ``--marker-sequence``."""
    try:
        return ScenarioConfig(name="command-line", markers=value.split(",")).markers
    except ValueError as error:
        raise ScenarioError(f"Invalid marker sequence: {error}") from error


def load_scenario(rootpath: Path, name: str) -> ScenarioConfig:
    """Load one scenario from the conventional test-runs directory."""
    if _SCENARIO_NAME_PATTERN.fullmatch(name) is None:
        raise ScenarioError(
            f"Invalid scenario name '{name}': use only letters, numbers, underscores, and hyphens"
        )

    path = rootpath / "test-runs" / "scenarios" / f"{name}.yaml"
    try:
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
        scenario = ScenarioConfig.model_validate(content)
    except OSError as error:
        raise ScenarioError(f"Cannot read scenario '{name}' from '{path}': {error}") from error
    except yaml.YAMLError as error:
        raise ScenarioError(f"Invalid YAML in scenario '{name}' at '{path}': {error}") from error
    except ValueError as error:
        raise ScenarioError(f"Invalid scenario '{name}' at '{path}': {error}") from error

    if scenario.name != name:
        raise ScenarioError(
            f"Scenario file '{path}' declares name '{scenario.name}', expected '{name}'"
        )
    return scenario


def _first_duplicate(values: list[str]) -> str | None:
    """Return the first repeated value while preserving declaration order."""
    seen: set[str] = set()
    for value in values:
        if value in seen:
            return value
        seen.add(value)
    return None
