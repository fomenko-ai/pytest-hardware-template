"""Tests for repository-local Allure configuration."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from hardware_test.pytest_plugin import pytest_configure as configure_artifacts
from tests.conftest import _escape_property
from tests.conftest import pytest_configure as configure_allure


def _config(tmp_path: Path, options: dict[str, object], *, adapter_installed: bool) -> Mock:
    config = Mock()
    config.rootpath = tmp_path
    config.option = Mock()
    config.stash = pytest.Stash()
    config.getini.return_value = []
    config.getoption.side_effect = lambda name, default=None: options.get(name, default)
    config.pluginmanager.has_plugin.side_effect = lambda name: name == "html" or adapter_installed
    return config


def test_allure_results_use_the_standard_run_directory(tmp_path: Path) -> None:
    config = _config(tmp_path, {"allure": True}, adapter_installed=True)
    configure_artifacts(config)

    configure_allure(config)

    run_directory = Path(config.option.log_file).parent
    assert config.option.allure_report_dir == str(run_directory / "allure-results")


def test_allure_requires_dependency_group(tmp_path: Path) -> None:
    config = _config(tmp_path, {"allure": True}, adapter_installed=False)
    configure_artifacts(config)

    with pytest.raises(pytest.UsageError, match="uv sync --group allure"):
        configure_allure(config)


def test_allure_rejects_custom_results_directory_at_the_same_time(tmp_path: Path) -> None:
    config = _config(
        tmp_path,
        {"allure": True, "allure_report_dir": "custom-results"},
        adapter_installed=True,
    )
    configure_artifacts(config)

    with pytest.raises(pytest.UsageError, match="--allure and --alluredir"):
        configure_allure(config)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("run-123", "run-123"),
        (" a=b:c\\d\n\r\t#!", r"\ a\=b\:c\\d\u000a\u000d\u0009\#\!"),
        ("стенд 🧪", r"\u0441\u0442\u0435\u043d\u0434\ \ud83e\uddea"),
    ],
)
def test_allure_properties_escape_special_characters(value: str, expected: str) -> None:
    assert _escape_property(value) == expected
