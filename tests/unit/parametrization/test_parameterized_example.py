"""End-to-end example for the automatically loaded yaml-test-params plugin."""

from pathlib import Path

import pytest
from yaml_test_params.pytest import YamlConfigSource, yaml_parametrize

from tests.unit.parametrization.models import ParameterizedExampleConfigCollection

PROJECT_ROOT = Path(__file__).parents[3]
PARAMETERIZED_EXAMPLE_CONFIGS = YamlConfigSource(
    path=PROJECT_ROOT / "configs/common/parameterized-example.yaml",
    model=ParameterizedExampleConfigCollection,
)


class TestParameterizedExample:
    """Verify collection expansion through the public pytest plugin API."""

    @yaml_parametrize(PARAMETERIZED_EXAMPLE_CONFIGS, "parameterized-example")
    def test_parameters(
        self,
        request: pytest.FixtureRequest,
        test_name: str,
        input_value: str,
        expected_value: str,
        repeat_count: int,
    ) -> None:
        """Receive every validated YAML combination with a readable pytest ID."""
        expanded_cases = {
            (value, "accepted", count) for value in ("alpha", "beta") for count in range(1, 11)
        }
        expected_cases = expanded_cases | {("stable", "accepted", 0)}

        assert (input_value, expected_value, repeat_count) in expected_cases
        assert request.node.name == f"test_parameters[{test_name}]"

    def test_undecorated_test_is_not_parameterized(self) -> None:
        """Leave ordinary pytest tests untouched by the plugin."""
        assert True
