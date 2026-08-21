"""Inventory-to-stand integration test without physical connections."""

from pathlib import Path

from pydantic import SecretStr

from hardware_test.devices import Analyzer, Dut
from hardware_test.factory import create_stand
from hardware_test.inventory import get_stand, load_inventory
from hardware_test.settings import CredentialSettings, Settings, SshCredentialSettings


def test_inventory_factories_and_stand_compose(tmp_path: Path) -> None:
    path = tmp_path / "stands.yaml"
    path.write_text(
        """version: 1
device_files: [devices.yaml]
stands:
  example:
    devices: {dut: dut-01, analyzer: analyzer-01}
""",
        encoding="utf-8",
    )
    (tmp_path / "devices.yaml").write_text(
        """version: 1
devices:
  dut-01:
    type: dut
    model: example-dut
    transport: {type: ssh, ssh: {host: 192.0.2.10, credentials: default-ssh}}
  analyzer-01:
    type: analyzer
    model: example-analyzer
    transport: {type: ssh, ssh: {host: 192.0.2.11, credentials: default-ssh}}
""",
        encoding="utf-8",
    )
    credential = SshCredentialSettings(username="tester", password=SecretStr("secret"))
    settings = Settings(
        _env_file=None,
        credentials=CredentialSettings(default_ssh=credential),
    )

    inventory = load_inventory(path)
    stand = create_stand(inventory, get_stand(inventory, "example"), settings)

    assert isinstance(stand.dut, Dut)
    assert isinstance(stand.analyzer, Analyzer)
    assert stand.dut.model == "example-dut"
