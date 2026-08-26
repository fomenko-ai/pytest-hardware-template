import pytest

from test_runner_service.docker_commands import (
    DockerCommandBuilder,
    InvalidImageReferenceError,
)
from test_runner_service.settings import Settings


def test_build_command_uses_only_configured_paths(settings: Settings) -> None:
    command = DockerCommandBuilder(settings).build_image("build-123")

    assert command == (
        "docker",
        "build",
        "--file",
        str(settings.framework_dockerfile),
        "--tag",
        "local/hardware-tests:build-123",
        str(settings.framework_source),
    )


def test_run_command_matches_framework_runtime_contract(settings: Settings) -> None:
    command = DockerCommandBuilder(settings).run_tests(
        "run-123",
        "sha256:abc123",
        "stand-01",
        "hardware-smoke",
    )

    assert command == (
        "docker",
        "run",
        "--rm",
        "--name",
        "hardware-test-run-run-123",
        "--label",
        "test-runner.operation-id=run-123",
        "--pull",
        "never",
        "--volume",
        f"{settings.inventory_file.parent}:/runtime/inventory:ro",
        "--volume",
        f"{settings.artifacts_directory}:/app/artifacts",
        "sha256:abc123",
        "uv",
        "run",
        "pytest",
        "tests/hardware",
        "--scenario",
        "hardware-smoke",
        "--inventory",
        "/runtime/inventory/stands.yaml",
        "--stand",
        "stand-01",
    )


def test_remote_image_must_match_allowlist(settings: Settings) -> None:
    builder = DockerCommandBuilder(settings)

    with pytest.raises(InvalidImageReferenceError) as raised:
        builder.pull_image("untrusted.example/image@sha256:abc")

    assert str(raised.value) == "image reference is not allowed"
