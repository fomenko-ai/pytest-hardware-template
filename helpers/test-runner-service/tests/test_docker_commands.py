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


def test_run_command_joins_configured_docker_network(settings: Settings) -> None:
    network_settings = settings.model_copy(update={"docker_network": "hardware-virtual-stand"})

    command = DockerCommandBuilder(network_settings).run_tests(
        "run-123",
        "sha256:abc123",
        "virtual-stand",
        "virtual-smoke",
    )

    network_index = command.index("--network")
    assert command[network_index : network_index + 2] == (
        "--network",
        "hardware-virtual-stand",
    )


def test_allure_enabled_build_and_run_commands(settings: Settings) -> None:
    allure_settings = settings.model_copy(
        update={"allure_enabled": True, "allure_access_token": "ars1.secret"}
    )
    builder = DockerCommandBuilder(allure_settings)

    build = builder.build_image("build-123")
    run = builder.run_tests("run-123", "sha256:abc123", "stand-01", "hardware-smoke")

    assert build[-3:] == ("--build-arg", "INSTALL_ALLURE=true", str(settings.framework_source))
    assert run[-1] == "--allure"


def test_allure_publisher_mounts_only_the_selected_run(settings: Settings) -> None:
    run_directory = settings.artifacts_directory / "run-123"
    command = DockerCommandBuilder(settings).publish_allure("run-123", run_directory)

    assert "ALLURE_ACCESS_TOKEN" in command
    assert "ars1" not in " ".join(command)
    assert f"{settings.framework_source}:/workspace/{settings.allure_repository}:ro" in command
    assert f"GIT_CONFIG_VALUE_0=/workspace/{settings.allure_repository}" in command
    assert f"{run_directory / 'allure-results'}:/results:ro" in command
    assert command[-4:] == (
        "generate",
        "/results",
        "--config",
        "/opt/allure/allurerc.mjs",
    )


def test_remote_image_must_match_allowlist(settings: Settings) -> None:
    builder = DockerCommandBuilder(settings)

    with pytest.raises(InvalidImageReferenceError) as raised:
        builder.pull_image("untrusted.example/image@sha256:abc")

    assert str(raised.value) == "image reference is not allowed"
