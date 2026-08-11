"""Typed models for the neutral YAML parameterization example."""

from yaml_test_params.models import (
    BaseTestCase,
    BaseTestConfig,
    BaseTestConfigCollection,
    ParametrizeInteger,
    ParametrizeString,
)


class ParameterizedExampleTestCase(BaseTestCase):
    """One example case, possibly containing expandable values."""

    input_value: ParametrizeString
    expected_value: ParametrizeString
    repeat_count: ParametrizeInteger

    @property
    def arg_id(self) -> str:
        """Use the expanded case name as the pytest parameter ID."""
        return self.test_name


class ParameterizedExampleConfig(BaseTestConfig):
    """A named collection of parameterization examples."""

    test_cases: list[ParameterizedExampleTestCase]


class ParameterizedExampleConfigCollection(BaseTestConfigCollection):
    """Root model for parameterization example collections."""

    collection: list[ParameterizedExampleConfig]
