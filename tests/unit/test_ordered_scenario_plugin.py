"""End-to-end tests for ordered marker selection in the pytest plugin."""

import pytest

pytest_plugins = ["pytester"]


def _configure_markers(pytester: pytest.Pytester, *markers: str) -> None:
    """Register scenario markers in an isolated pytest project."""
    definitions = ",\n".join(f'    "{marker}: scenario test step"' for marker in markers)
    pytester.makepyprojecttoml(
        f"""\
[tool.pytest.ini_options]
addopts = "--strict-markers"
markers = [
{definitions},
]
"""
    )


def _collected_nodeids(result: pytest.RunResult) -> list[str]:
    """Extract ordered node IDs from quiet collect-only output."""
    return [line for line in result.stdout.lines if "::" in line and not line.startswith("<")]


def test_marker_sequence_orders_groups_and_preserves_parameter_order(
    pytester: pytest.Pytester,
) -> None:
    _configure_markers(pytester, "step1", "step2")
    pytester.makepyfile(
        """\
import pytest

@pytest.mark.step2
@pytest.mark.parametrize("value", [1, 2])
def test_second(value):
    assert value

def test_unselected():
    assert True

@pytest.mark.step1
def test_first():
    assert True
"""
    )

    result = pytester.runpytest_subprocess("-M", "step1,step2", "--collect-only", "-q")

    assert result.ret == pytest.ExitCode.OK
    assert _collected_nodeids(result) == [
        "test_marker_sequence_orders_groups_and_preserves_parameter_order.py::test_first",
        "test_marker_sequence_orders_groups_and_preserves_parameter_order.py::test_second[1]",
        "test_marker_sequence_orders_groups_and_preserves_parameter_order.py::test_second[2]",
    ]


def test_named_scenario_loads_from_conventional_directory(pytester: pytest.Pytester) -> None:
    _configure_markers(pytester, "step1", "step2")
    scenario_path = pytester.path / "test-runs" / "scenarios" / "ordered.yaml"
    scenario_path.parent.mkdir(parents=True)
    scenario_path.write_text(
        "name: ordered\nmarkers:\n  - step1\n  - step2\n",
        encoding="utf-8",
    )
    pytester.makepyfile(
        """\
import pytest

@pytest.mark.step2
def test_second():
    assert True

@pytest.mark.step1
def test_first():
    assert True
"""
    )

    result = pytester.runpytest_subprocess("-S", "ordered", "--collect-only", "-q")

    assert result.ret == pytest.ExitCode.OK
    assert _collected_nodeids(result) == [
        "test_named_scenario_loads_from_conventional_directory.py::test_first",
        "test_named_scenario_loads_from_conventional_directory.py::test_second",
    ]


def test_marker_sequence_rejects_item_in_multiple_steps(pytester: pytest.Pytester) -> None:
    _configure_markers(pytester, "step1", "step2")
    pytester.makepyfile(
        """\
import pytest

@pytest.mark.step1
@pytest.mark.step2
def test_ambiguous():
    assert True
"""
    )

    result = pytester.runpytest_subprocess("-M", "step1,step2", "--collect-only", "-q")

    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*belongs to multiple scenario steps: step1, step2*"])


def test_marker_sequence_rejects_empty_group(pytester: pytest.Pytester) -> None:
    _configure_markers(pytester, "step1", "step2")
    pytester.makepyfile(
        """\
import pytest

@pytest.mark.step1
def test_first():
    assert True
"""
    )

    result = pytester.runpytest_subprocess("-M", "step1,step2", "--collect-only", "-q")

    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*requires 'step2', but no matching tests were collected*"])


def test_marker_sequence_rejects_unregistered_marker(pytester: pytest.Pytester) -> None:
    _configure_markers(pytester, "step1")
    pytester.makepyfile("def test_example():\n    assert True\n")

    result = pytester.runpytest_subprocess("-M", "unknown", "--collect-only", "-q")

    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*Marker 'unknown' is not registered*"])


def test_marker_sequence_and_scenario_are_mutually_exclusive(pytester: pytest.Pytester) -> None:
    _configure_markers(pytester, "step1")
    pytester.makepyfile("def test_example():\n    assert True\n")

    result = pytester.runpytest_subprocess(
        "-M",
        "step1",
        "-S",
        "ordered",
        "--collect-only",
        "-q",
    )

    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*--marker-sequence and --scenario cannot be used together*"])


def test_marker_sequence_stops_after_first_failure(pytester: pytest.Pytester) -> None:
    _configure_markers(pytester, "step1", "step2")
    sentinel = pytester.path / "step2-ran"
    pytester.makepyfile(
        f"""\
from pathlib import Path
import pytest

@pytest.mark.step1
def test_first():
    assert False

@pytest.mark.step2
def test_second():
    Path({str(sentinel)!r}).touch()
"""
    )

    result = pytester.runpytest_subprocess("-M", "step1,step2", "-q")

    result.assert_outcomes(failed=1)
    assert not sentinel.exists()


def test_pytest_without_scenario_options_preserves_collection_order(
    pytester: pytest.Pytester,
) -> None:
    _configure_markers(pytester, "step1", "step2")
    pytester.makepyfile(
        """\
import pytest

@pytest.mark.step2
def test_second():
    assert True

@pytest.mark.step1
def test_first():
    assert True
"""
    )

    result = pytester.runpytest_subprocess("--collect-only", "-q")

    assert result.ret == pytest.ExitCode.OK
    assert _collected_nodeids(result) == [
        "test_pytest_without_scenario_options_preserves_collection_order.py::test_second",
        "test_pytest_without_scenario_options_preserves_collection_order.py::test_first",
    ]
