from pathlib import Path

import pytest

from test_runner_service.settings import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    framework = tmp_path / "framework"
    inventory = tmp_path / "inventory"
    artifacts = tmp_path / "artifacts"
    framework.mkdir()
    inventory.mkdir()
    artifacts.mkdir()
    dockerfile = framework / "Dockerfile"
    dockerfile.write_text("FROM scratch\n", encoding="utf-8")
    inventory_file = inventory / "stands.yaml"
    inventory_file.write_text("stands: {}\n", encoding="utf-8")
    return Settings(
        _env_file=None,
        state_directory=tmp_path / "state",
        framework_source=framework,
        framework_dockerfile=dockerfile,
        inventory_file=inventory_file,
        artifacts_directory=artifacts,
        env_file=None,
        allowed_image_prefixes=("sha256:", "registry.example/"),
        log_poll_interval_seconds=0.001,
    )
