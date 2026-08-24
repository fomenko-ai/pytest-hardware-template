"""Tests for the provider-independent containerized hardware-test launcher."""

import os
import stat
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "run-hardware-tests.sh"


@pytest.fixture
def launcher_environment(tmp_path: Path) -> tuple[dict[str, str], Path]:
    """Provide a fake Docker executable that records every received argument."""
    bin_directory = tmp_path / "fake bin"
    bin_directory.mkdir()
    docker = bin_directory / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'printf \'%s\\n\' "$@" > "${DOCKER_CAPTURE:?}"\n'
        'exit "${DOCKER_EXIT_CODE:-0}"\n'
    )
    docker.chmod(docker.stat().st_mode | stat.S_IXUSR)

    capture = tmp_path / "docker-arguments.txt"
    environment = os.environ.copy()
    environment["PATH"] = f"{bin_directory}{os.pathsep}{environment['PATH']}"
    environment["DOCKER_CAPTURE"] = str(capture)
    return environment, capture


def run_launcher(
    arguments: list[str],
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the launcher through its absolute, repository-controlled path."""
    return subprocess.run(  # noqa: S603
        [str(SCRIPT), *arguments],
        cwd=PROJECT_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def test_launcher_constructs_isolated_docker_run(
    tmp_path: Path,
    launcher_environment: tuple[dict[str, str], Path],
) -> None:
    environment, capture = launcher_environment
    inventory_directory = tmp_path / "inventory files"
    inventory_directory.mkdir()
    inventory = inventory_directory / "stands.yaml"
    inventory.write_text("version: 1\ndevice_files: []\nstands: {}\n")
    env_file = tmp_path / "runtime.env"
    env_file.write_text("HARDWARE_TEST_PASSWORD=not-a-real-secret\n")
    known_hosts = tmp_path / "known hosts"
    known_hosts.write_text("example.invalid ssh-ed25519 placeholder\n")
    artifacts = tmp_path / "test artifacts"

    result = run_launcher(
        [
            "--image",
            "hardware-tests@sha256:example",
            "--inventory",
            str(inventory),
            "--stand",
            "stand-01",
            "--scenario",
            "hardware_smoke",
            "--artifacts",
            str(artifacts),
            "--env-file",
            str(env_file),
            "--known-hosts",
            str(known_hosts),
            "--network",
            "host",
            "--device",
            "/dev/ttyUSB0",
            "--pull",
            "never",
        ],
        environment,
    )

    assert result.returncode == 0
    assert artifacts.is_dir()
    assert capture.read_text().splitlines() == [
        "run",
        "--rm",
        "--pull",
        "never",
        "--volume",
        f"{inventory_directory}:/runtime/inventory:ro",
        "--volume",
        f"{artifacts}:/app/artifacts",
        "--env-file",
        str(env_file),
        "--volume",
        f"{known_hosts}:/root/.ssh/known_hosts:ro",
        "--network",
        "host",
        "--device",
        "/dev/ttyUSB0",
        "hardware-tests@sha256:example",
        "uv",
        "run",
        "pytest",
        "tests/hardware",
        "--scenario",
        "hardware_smoke",
        "--inventory",
        "/runtime/inventory/stands.yaml",
        "--stand",
        "stand-01",
    ]


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ([], "--image is required"),
        (["--image", "image"], "--inventory is required"),
        (["--unknown"], "unknown option '--unknown'"),
    ],
)
def test_launcher_rejects_incomplete_or_unknown_options(
    arguments: list[str],
    message: str,
) -> None:
    result = run_launcher(arguments)

    assert result.returncode == 2
    assert message in result.stderr


@pytest.mark.parametrize(
    ("option", "value", "message"),
    [
        ("--stand", "../stand", "invalid stand name"),
        ("--scenario", "smoke; command", "invalid scenario name"),
        ("--pull", "sometimes", "invalid pull policy"),
        ("--image", "--privileged", "invalid image reference"),
    ],
)
def test_launcher_rejects_unsafe_selection_values(
    tmp_path: Path,
    option: str,
    value: str,
    message: str,
) -> None:
    inventory = tmp_path / "stands.yaml"
    inventory.touch()
    arguments = [
        "--image",
        "image",
        "--inventory",
        str(inventory),
        "--stand",
        "stand-01",
        "--scenario",
        "smoke",
        option,
        value,
    ]

    result = run_launcher(arguments)

    assert result.returncode == 2
    assert message in result.stderr


def test_launcher_returns_docker_exit_code(
    tmp_path: Path,
    launcher_environment: tuple[dict[str, str], Path],
) -> None:
    environment, _ = launcher_environment
    environment["DOCKER_EXIT_CODE"] = "7"
    inventory = tmp_path / "stands.yaml"
    inventory.touch()

    result = run_launcher(
        [
            "--image",
            "image",
            "--inventory",
            str(inventory),
            "--stand",
            "stand-01",
            "--scenario",
            "smoke",
            "--artifacts",
            str(tmp_path / "artifacts"),
        ],
        environment,
    )

    assert result.returncode == 7
