"""Unit tests for class-based hardware command helpers."""

import logging

import pytest

from hardware_test.devices import Dut
from hardware_test.models import CommandResult
from hardware_test.stand import TestStand
from tests.fakes import FakeTransport
from tests.hardware.base import BaseTest


def make_subject(result: CommandResult) -> tuple[BaseTest, TestStand, FakeTransport]:
    """Build the helper around an in-memory DUT transport."""
    transport = FakeTransport(result)
    stand = TestStand(devices={"dut": Dut(transport, "example-model")})
    return BaseTest(), stand, transport


def test_run_command_logs_and_delegates_to_dut(
    caplog: pytest.LogCaptureFixture,
) -> None:
    expected = CommandResult(stdout="ready\n", stderr="", exit_code=0)
    subject, stand, transport = make_subject(expected)

    with caplog.at_level(logging.INFO, logger="tests.hardware.base"):
        result = subject.run_command(
            stand,
            "show status",
            timeout=3.0,
        )

    assert result == expected
    assert transport.commands == [("show status", 3.0)]
    assert [record.getMessage() for record in caplog.records] == [
        "Run command: show status",
        "Command completed with exit code 0",
    ]


def test_run_and_check_command_returns_matching_result() -> None:
    expected = CommandResult(stdout="ready\n", stderr="", exit_code=0)
    subject, stand, _ = make_subject(expected)

    result = subject.run_and_check_command(
        stand,
        "show status",
        expected_stdout="ready",
        expected_stderr="",
    )

    assert result == expected


@pytest.mark.parametrize(
    (
        "result",
        "expected_stdout",
        "expected_stderr",
        "expected_exit_code",
        "message",
    ),
    [
        (
            CommandResult(stdout="ready", stderr="failed", exit_code=1),
            None,
            None,
            0,
            "Expected exit code 0, got 1",
        ),
        (
            CommandResult(stdout="starting", stderr="", exit_code=0),
            "ready",
            None,
            0,
            "Expected stdout 'ready', got 'starting'",
        ),
        (
            CommandResult(stdout="", stderr="warning", exit_code=0),
            None,
            "",
            0,
            "Expected stderr '', got 'warning'",
        ),
    ],
)
def test_check_command_reports_mismatch(
    result: CommandResult,
    expected_stdout: str | None,
    expected_stderr: str | None,
    expected_exit_code: int,
    message: str,
) -> None:
    with pytest.raises(AssertionError, match=message):
        BaseTest().check_command(
            result,
            expected_stdout=expected_stdout,
            expected_stderr=expected_stderr,
            expected_exit_code=expected_exit_code,
        )
