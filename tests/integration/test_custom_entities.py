"""Exercise the documented project extension with fake clients only."""

import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest
import yaml
from pydantic import SecretStr, ValidationError

from docs.examples.custom_entities import (
    ConsoleClient,
    CustomMeter,
    CustomMeterConfig,
    ProjectCredentialSettings,
    ProjectSettings,
    ProjectTransportFactory,
    TcpConsoleTransport,
    TcpConsoleTransportConfig,
    TcpCredentialSettings,
    build_stand_factory,
    load_project_inventory,
)
from hardware_test.devices import Dut
from hardware_test.exceptions import (
    FactoryError,
    InventoryError,
    TransportError,
    UnsupportedCommandError,
)
from hardware_test.inventory import get_stand, load_inventory
from hardware_test.models import BinaryCommand, CommandResult, TextCommand
from hardware_test.settings import SshCredentialSettings
from hardware_test.transport import SshConnectionConfig
from tests.fakes import FakeTransport


class FakeConsoleClient:
    """Record adapter inputs and emulate a meter without any sockets."""

    def __init__(self, *, fail_connect: bool = False, fail_execute: bool = False) -> None:
        self.connection: tuple[str, int, str, SecretStr, float] | None = None
        self.commands: list[tuple[str, float]] = []
        self.close_count = 0
        self.fail_connect = fail_connect
        self.fail_execute = fail_execute

    def connect(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: SecretStr,
        timeout: float,
    ) -> None:
        self.connection = host, port, username, password, timeout
        if self.fail_connect:
            raise OSError("fake connection failed")

    def execute(self, query: str, *, timeout: float) -> CommandResult:
        self.commands.append((query, timeout))
        if self.fail_execute:
            raise OSError("fake command failed")
        return CommandResult(stdout="3.3", stderr="", exit_code=0)

    def close(self) -> None:
        self.close_count += 1


def _settings() -> ProjectSettings:
    return ProjectSettings(
        _env_file=None,
        connect_timeout=7,
        command_timeout=11,
        credentials=ProjectCredentialSettings(
            default_ssh=SshCredentialSettings(username="operator", password=SecretStr("fake-ssh")),
            tcp={
                "meter_link": TcpCredentialSettings(username="tester", password=SecretStr("fake"))
            },
        ),
    )


def _device_data(device_type: str, transport_type: str) -> dict[str, object]:
    transport: dict[str, object]
    if transport_type == "ssh":
        transport = {
            "type": "ssh",
            "ssh": {"host": "192.0.2.30", "credentials": "default-ssh"},
        }
    else:
        transport = {
            "type": transport_type,
            "host": "192.0.2.30",
            "port": 9000,
            "credentials": "meter_link",
        }
    device: dict[str, object] = {
        "type": device_type,
        "model": "example-meter",
        "transport": transport,
    }
    if device_type == "custom_meter":
        device["channel"] = 2
    return device


def _write_inventory(tmp_path: Path, device: dict[str, object]) -> Path:
    equipment = tmp_path / "equipment"
    equipment.mkdir()
    (equipment / "meters.yaml").write_text(
        yaml.safe_dump({"version": 1, "devices": {"meter-01": device}}), encoding="utf-8"
    )
    path = tmp_path / "stands.yaml"
    path.write_text(
        "version: 1\ndevice_files: [equipment/meters.yaml]\nstands:\n"
        "  example:\n    devices: {reference_meter: meter-01, alias: meter-01}\n",
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("device_type", ["dut", "custom_meter"])
@pytest.mark.parametrize("transport_type", ["ssh", "tcp_console"])
def test_all_device_transport_combinations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, device_type: str, transport_type: str
) -> None:
    """Use real schema and factory dispatch, replacing only I/O implementations."""
    ssh_transports: list[FakeTransport] = []

    def fake_ssh(
        *, ssh: SshConnectionConfig, connect_timeout: float, command_timeout: float
    ) -> FakeTransport:
        assert ssh.host == "192.0.2.30"
        assert ssh.username == "operator"
        assert (connect_timeout, command_timeout) == (7, 11)
        transport = FakeTransport(CommandResult(stdout="3.3", stderr="", exit_code=0))
        ssh_transports.append(transport)
        return transport

    monkeypatch.setattr("hardware_test.factory.transport.SSHTransport", fake_ssh)
    clients: list[FakeConsoleClient] = []

    def client_factory() -> ConsoleClient:
        client = FakeConsoleClient()
        clients.append(client)
        return client

    inventory = load_project_inventory(
        _write_inventory(tmp_path, _device_data(device_type, transport_type))
    )
    factory = build_stand_factory(_settings(), client_factory=client_factory)
    stand = factory.create(inventory, get_stand(inventory, "example"))
    assert stand.devices["reference_meter"] is stand.devices["alias"]
    assert len(clients) + len(ssh_transports) == 1
    assert all(client.connection is None for client in clients)
    assert all(not transport.connected for transport in ssh_transports)
    if device_type == "custom_meter":
        config = inventory.devices["meter-01"]
        assert isinstance(config, CustomMeterConfig)
        assert config.channel == 2

    stand.connect()
    try:
        if device_type == "custom_meter":
            meter = stand.device("reference_meter", CustomMeter)
            assert meter.channel == 2
            assert meter.measure() == 3.3
        else:
            dut = stand.device("reference_meter", Dut)
            assert dut.execute_command(TextCommand("MEASURE 2")).stdout == "3.3"
    finally:
        stand.close()

    if clients:
        client = clients[0]
        assert client.connection is not None
        host, port, username, password, timeout = client.connection
        assert (host, port, username, timeout) == ("192.0.2.30", 9000, "tester", 7)
        assert password.get_secret_value() == "fake"
        assert client.commands == [("MEASURE 2", 11)]
        assert client.close_count == 1
    else:
        assert ssh_transports[0].closed


def test_project_schema_is_required_for_custom_inventory(tmp_path: Path) -> None:
    path = _write_inventory(tmp_path, _device_data("custom_meter", "tcp_console"))
    with pytest.raises(InventoryError, match="Invalid inventory"):
        load_inventory(path)


@pytest.mark.parametrize("invalid", ["device_type", "transport_type", "channel", "secret", "port"])
def test_custom_inventory_rejects_invalid_data(tmp_path: Path, invalid: str) -> None:
    device = _device_data("custom_meter", "tcp_console")
    if invalid == "device_type":
        device["type"] = "unregistered"
    elif invalid == "transport_type":
        device = _device_data("custom_meter", "unregistered")
    elif invalid == "channel":
        device["channel"] = 0
    elif invalid == "secret":
        device["password"] = "fake"  # noqa: S105 -- deliberately invalid inventory fixture
    else:
        device["transport"] = {
            "type": "tcp_console",
            "host": "192.0.2.30",
            "port": 0,
            "credentials": "meter_link",
        }
    path = _write_inventory(tmp_path, device)
    with pytest.raises(InventoryError, match=r"equipment/meters\.yaml"):
        load_project_inventory(path)


def test_custom_schema_merges_sources_and_checks_global_ids(tmp_path: Path) -> None:
    path = _write_inventory(tmp_path, _device_data("custom_meter", "tcp_console"))
    second = tmp_path / "other.yaml"
    second.write_text(
        yaml.safe_dump({"version": 1, "devices": {"meter-02": _device_data("dut", "ssh")}}),
        encoding="utf-8",
    )
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "[equipment/meters.yaml]", "[equipment/meters.yaml, other.yaml]"
        ),
        encoding="utf-8",
    )
    inventory = load_project_inventory(path)
    assert set(inventory.devices) == {"meter-01", "meter-02"}
    assert isinstance(inventory.devices["meter-01"], CustomMeterConfig)

    second.write_text(
        second.read_text(encoding="utf-8").replace("meter-02", "meter-01"), encoding="utf-8"
    )
    with pytest.raises(InventoryError) as caught:
        load_project_inventory(path)
    assert "Duplicate device IDs: meter-01" in str(caught.value)
    assert "equipment/meters.yaml" in str(caught.value)
    assert "other.yaml" in str(caught.value)


def test_custom_inventory_checks_stand_references(tmp_path: Path) -> None:
    path = _write_inventory(tmp_path, _device_data("custom_meter", "tcp_console"))
    path.write_text(
        path.read_text(encoding="utf-8").replace("alias: meter-01", "alias: missing"),
        encoding="utf-8",
    )
    with pytest.raises(InventoryError, match=r"example\.alias -> missing"):
        load_project_inventory(path)


def test_missing_custom_credentials_fail_before_client_creation() -> None:
    def unexpected_client() -> ConsoleClient:
        pytest.fail("Client must not be constructed without credentials")

    factory = ProjectTransportFactory(
        ProjectSettings(_env_file=None), client_factory=unexpected_client
    )
    config = TcpConsoleTransportConfig(
        type="tcp_console", host="192.0.2.30", port=9000, credentials="missing"
    )
    with pytest.raises(FactoryError, match="TCP credentials 'missing' are not configured"):
        factory.create(config)


def test_custom_credentials_load_from_nested_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in tuple(os.environ):
        if name.startswith("HARDWARE_TEST_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("HARDWARE_TEST_CREDENTIALS__TCP__METER_LINK__USERNAME", "operator")
    monkeypatch.setenv("HARDWARE_TEST_CREDENTIALS__TCP__METER_LINK__PASSWORD", "fake-env-password")
    settings = ProjectSettings(_env_file=None)
    credentials = settings.credentials.tcp["meter_link"]
    assert credentials.username == "operator"
    assert isinstance(credentials.password, SecretStr)
    assert credentials.password.get_secret_value() == "fake-env-password"
    assert "fake-env-password" not in repr(settings)


def test_custom_credentials_load_from_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in tuple(os.environ):
        if name.startswith("HARDWARE_TEST_"):
            monkeypatch.delenv(name)
    path = tmp_path / ".env"
    path.write_text(
        "HARDWARE_TEST_CREDENTIALS__TCP__METER_LINK__USERNAME=operator\n"
        "HARDWARE_TEST_CREDENTIALS__TCP__METER_LINK__PASSWORD=fake-dotenv-password\n",
        encoding="utf-8",
    )
    settings = ProjectSettings(_env_file=path)
    credentials = settings.credentials.tcp["meter_link"]
    assert credentials.password.get_secret_value() == "fake-dotenv-password"


def test_failed_connection_closes_previous_and_partial_clients(tmp_path: Path) -> None:
    path = _write_inventory(tmp_path, _device_data("custom_meter", "tcp_console"))
    inventory = load_project_inventory(path)
    inventory.devices["meter-02"] = inventory.devices["meter-01"].model_copy()
    stand_config = get_stand(inventory, "example")
    stand_config.devices["second"] = "meter-02"
    clients = [FakeConsoleClient(), FakeConsoleClient(fail_connect=True)]
    pending = iter(clients)
    factory = build_stand_factory(_settings(), client_factory=lambda: next(pending))
    stand = factory.create(inventory, stand_config)

    with pytest.raises(TransportError, match="Cannot connect to TCP console"):
        stand.connect()

    assert [client.close_count for client in clients] == [1, 1]


def test_connection_is_closed_after_domain_operation_failure(tmp_path: Path) -> None:
    path = _write_inventory(tmp_path, _device_data("custom_meter", "tcp_console"))
    inventory = load_project_inventory(path)
    client = FakeConsoleClient(fail_execute=True)
    stand = build_stand_factory(_settings(), client_factory=lambda: client).create(
        inventory, get_stand(inventory, "example")
    )
    stand.connect()
    try:
        with pytest.raises(TransportError, match="TCP console command failed"):
            stand.device("reference_meter", CustomMeter).measure()
    finally:
        stand.close()
    assert client.close_count == 1


def test_custom_device_model_forbids_unexpected_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CustomMeterConfig.model_validate(
            {**_device_data("custom_meter", "tcp_console"), "unexpected": True}
        )


def test_custom_transport_uses_explicit_command_timeout() -> None:
    settings = _settings()
    client = FakeConsoleClient()
    transport = TcpConsoleTransport(
        TcpConsoleTransportConfig(
            type="tcp_console", host="192.0.2.30", port=9000, credentials="meter_link"
        ),
        settings.credentials.tcp["meter_link"],
        settings,
        client,
    )
    transport.execute(TextCommand("status", timeout=2))
    assert client.commands == [("status", 2)]


def test_custom_transport_rejects_binary_commands() -> None:
    client = FakeConsoleClient()
    transport = ProjectTransportFactory(_settings(), client_factory=lambda: client).create(
        TcpConsoleTransportConfig(
            type="tcp_console", host="192.0.2.30", port=9000, credentials="meter_link"
        )
    )
    with pytest.raises(UnsupportedCommandError, match="requires TextCommand"):
        transport.execute(BinaryCommand(b"status"))
    assert client.commands == []


@pytest.mark.parametrize("fail_test", [False, True])
def test_project_fixtures_inject_custom_entities_and_always_close(
    tmp_path: Path, fail_test: bool
) -> None:
    """Run the template lifecycle fixture in an isolated fake-only pytest project."""
    _write_inventory(tmp_path, _device_data("custom_meter", "tcp_console"))
    (tmp_path / "pytest.ini").write_text("[pytest]\ntimeout=120\n", encoding="utf-8")
    (tmp_path / "conftest.py").write_text(
        dedent("""\
            from pathlib import Path
            import pytest
            from docs.examples.custom_entities import (
                ProjectDeviceConfig, ProjectTransportConfig,
                build_stand_factory, load_project_inventory,
            )
            from hardware_test.factory import StandFactory
            from hardware_test.inventory import Inventory
            from tests.hardware.conftest import stand
            from tests.integration.test_custom_entities import FakeConsoleClient, _settings

            class RecordingClient(FakeConsoleClient):
                def close(self) -> None:
                    super().close()
                    Path("closed.txt").write_text(str(self.close_count), encoding="utf-8")

            @pytest.fixture(scope="session")
            def inventory() -> Inventory[ProjectDeviceConfig]:
                return load_project_inventory(Path("stands.yaml"))

            @pytest.fixture(scope="session")
            def stand_factory() -> StandFactory[ProjectTransportConfig]:
                return build_stand_factory(_settings(), client_factory=RecordingClient)
            """),
        encoding="utf-8",
    )
    (tmp_path / "test_extension.py").write_text(
        dedent(f"""\
            import pytest
            from docs.examples.custom_entities import CustomMeter
            from hardware_test.stand import TestStand

            def test_meter(stand: TestStand) -> None:
                assert stand.device("reference_meter", CustomMeter).measure() == 3.3
                if {fail_test!r}:
                    pytest.fail("intentional test failure")
            """),
        encoding="utf-8",
    )
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("PYTEST_", "HARDWARE_TEST_"))
    }
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--strict-markers",
            "-p",
            "hardware_test.pytest_plugin",
            "-p",
            "pytest_timeout",
            "--stand",
            "example",
            "test_extension.py",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == (1 if fail_test else 0), result.stdout + result.stderr
    assert (tmp_path / "closed.txt").read_text(encoding="utf-8") == "1"
