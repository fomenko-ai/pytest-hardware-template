"""Run the library plugin without project policy or reporting-plugin imports."""

import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest


@pytest.mark.parametrize("external_identity", [False, True])
def test_library_runtime_does_not_require_or_configure_reporters(
    tmp_path: Path, external_identity: bool
) -> None:
    (tmp_path / "pytest.ini").write_text("[pytest]\ntimeout=120\n", encoding="utf-8")
    (tmp_path / "test_runtime.py").write_text(
        dedent("""\
            from pathlib import Path
            import pytest
            from hardware_test.pytest_plugin import get_run_directory, get_run_metadata

            def test_context(pytestconfig: pytest.Config) -> None:
                directory = get_run_directory(pytestconfig)
                metadata = get_run_metadata(pytestconfig)
                assert directory.is_dir()
                assert not list(directory.iterdir())
                assert not (directory.parent / "latest.log").exists()
                assert metadata["run_id"] == directory.name
                assert "python_version" in metadata
                assert pytestconfig.getoption("log_file", default=None) is None
                assert pytestconfig.getoption("htmlpath", default=None) is None
                assert pytestconfig.getoption("xmlpath", default=None) is None
            """),
        encoding="utf-8",
    )
    script = dedent("""\
        import sys
        from importlib.abc import MetaPathFinder
        from importlib.metadata import requires

        class NoReporters(MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split(".")[0] in {
                    "pytest_html", "pytest_metadata", "allure_pytest", "allure_commons",
                    "pytest_reportportal", "reportportal_client",
                }:
                    raise AssertionError("reporter imported: " + fullname)

        sys.meta_path.insert(0, NoReporters())
        import pytest
        dependencies = requires("pytest-hardware-template") or []
        assert not any(dependency.startswith("pytest-html") for dependency in dependencies)
        args = ["--strict-markers", "-p", "hardware_test.pytest_plugin",
                "-p", "pytest_timeout", "-p", "no:junitxml", "test_runtime.py"]
        if sys.argv[1] == "external":
            args.extend(["--run-id", "external-run", "--artifacts-root", "output"])
        raise SystemExit(pytest.main(args))
        """)
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("PYTEST_", "RP_", "ALLURE_"))
    }
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    result = subprocess.run(  # noqa: S603 -- fixed interpreter and isolated local probe
        [sys.executable, "-c", script, "external" if external_identity else "generated"],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    root = tmp_path / ("output" if external_identity else "artifacts")
    directories = list(root.iterdir())
    assert len(directories) == 1
    assert list(directories[0].iterdir()) == []
    if external_identity:
        assert directories[0].name == "external-run"
