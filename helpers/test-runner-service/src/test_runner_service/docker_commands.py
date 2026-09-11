import re
from dataclasses import dataclass
from pathlib import Path

from test_runner_service.settings import Settings

IMAGE_REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/:@+-]*$")


class InvalidImageReferenceError(ValueError):
    """Raised when an image reference is not allowed by server policy."""


@dataclass(frozen=True)
class DockerCommandBuilder:
    settings: Settings

    def validate_remote_image(self, reference: str) -> None:
        if not IMAGE_REFERENCE_PATTERN.fullmatch(reference):
            raise InvalidImageReferenceError("invalid image reference")
        if not any(reference.startswith(prefix) for prefix in self.settings.allowed_image_prefixes):
            raise InvalidImageReferenceError("image reference is not allowed")

    def build_image(self, operation_id: str) -> tuple[str, ...]:
        tag = f"local/hardware-tests:{operation_id}"
        arguments = [
            "docker",
            "build",
            "--file",
            str(self.settings.framework_dockerfile),
            "--tag",
            tag,
        ]
        if self.settings.allure_enabled:
            arguments.extend(("--build-arg", "INSTALL_ALLURE=true"))
        arguments.append(str(self.settings.framework_source))
        return tuple(arguments)

    def pull_image(self, reference: str) -> tuple[str, ...]:
        self.validate_remote_image(reference)
        return ("docker", "pull", reference)

    def inspect_image(self, reference: str) -> tuple[str, ...]:
        return ("docker", "image", "inspect", "--format", "{{.Id}}", reference)

    def run_tests(
        self,
        operation_id: str,
        image: str,
        stand: str,
        scenario: str,
    ) -> tuple[str, ...]:
        self.validate_remote_image(image)
        inventory_directory = self.settings.inventory_file.parent
        inventory_filename = self.settings.inventory_file.name
        container_name = f"hardware-test-run-{operation_id}"
        arguments = [
            "docker",
            "run",
            "--rm",
            "--name",
            container_name,
            "--label",
            f"test-runner.operation-id={operation_id}",
            "--pull",
            "never",
            "--volume",
            f"{inventory_directory}:/runtime/inventory:ro",
            "--volume",
            f"{self.settings.artifacts_directory}:/app/artifacts",
        ]
        if self.settings.env_file is not None:
            arguments.extend(("--env-file", str(self.settings.env_file)))
        if self.settings.known_hosts_file is not None:
            arguments.extend(
                (
                    "--volume",
                    f"{self.settings.known_hosts_file}:/root/.ssh/known_hosts:ro",
                )
            )
        if self.settings.docker_network is not None:
            arguments.extend(("--network", self.settings.docker_network))
        for device in self.settings.docker_devices:
            arguments.extend(("--device", device))
        arguments.extend(
            (
                image,
                "uv",
                "run",
                "pytest",
                "tests/hardware",
                "--scenario",
                scenario,
                "--inventory",
                f"/runtime/inventory/{inventory_filename}",
                "--stand",
                stand,
            )
        )
        if self.settings.allure_enabled:
            arguments.append("--allure")
        return tuple(arguments)

    def publish_allure(self, operation_id: str, run_directory: Path) -> tuple[str, ...]:
        container_name = f"allure-publish-{operation_id}"
        repository_directory = f"/workspace/{self.settings.allure_repository}"
        return (
            "docker",
            "run",
            "--rm",
            "--name",
            container_name,
            "--env",
            "ALLURE_ACCESS_TOKEN",
            "--env",
            "GIT_CONFIG_COUNT=1",
            "--env",
            "GIT_CONFIG_KEY_0=safe.directory",
            "--env",
            f"GIT_CONFIG_VALUE_0={repository_directory}",
            "--volume",
            f"{self.settings.framework_source}:{repository_directory}:ro",
            "--volume",
            f"{run_directory / 'allure-results'}:/results:ro",
            "--workdir",
            repository_directory,
            self.settings.allure_publisher_image,
            "generate",
            "/results",
            "--config",
            "/opt/allure/allurerc.mjs",
        )

    def stop_container(self, operation_id: str) -> tuple[str, ...]:
        return ("docker", "stop", f"hardware-test-run-{operation_id}")

    def local_build_reference(self, operation_id: str) -> str:
        return f"local/hardware-tests:{operation_id}"


def validate_required_paths(settings: Settings) -> None:
    required: tuple[tuple[str, Path], ...] = (
        ("framework source", settings.framework_source),
        ("framework Dockerfile", settings.framework_dockerfile),
        ("inventory file", settings.inventory_file),
        ("artifacts directory", settings.artifacts_directory),
    )
    missing = [f"{name}: {path}" for name, path in required if not path.exists()]
    if missing:
        raise RuntimeError(f"required runtime paths do not exist: {', '.join(missing)}")
