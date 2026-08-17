"""Shared command helpers for class-based hardware tests."""

import logging
import re

from hardware_test.devices import Dut
from hardware_test.models import CommandResult

logger = logging.getLogger(__name__)


class BaseTest:
    """Log, execute, and validate commands through the DUT domain API."""

    def run_command(
        self,
        dut: Dut,
        command: str,
        *,
        timeout: float | None = None,
    ) -> CommandResult:
        """Log and execute one DUT CLI command."""
        logger.info("Run command: %s", command)
        result = dut.execute_command(command, timeout)
        logger.info("Command completed with exit code %d", result.exit_code)
        return result

    def check_command(
        self,
        result: CommandResult,
        *,
        expected_stdout: str | None = None,
        expected_stderr: str | None = None,
        expected_exit_code: int = 0,
    ) -> None:
        """Assert that a command result matches the expected values."""
        assert result.exit_code == expected_exit_code, (
            f"Expected exit code {expected_exit_code}, got {result.exit_code}; "
            f"stderr={result.stderr!r}"
        )
        if expected_stdout is not None:
            assert result.stdout.strip() == expected_stdout, (
                f"Expected stdout {expected_stdout!r}, got {result.stdout.strip()!r}"
            )
        if expected_stderr is not None:
            assert result.stderr.strip() == expected_stderr, (
                f"Expected stderr {expected_stderr!r}, got {result.stderr.strip()!r}"
            )

    def check_stdout_contains(
        self,
        result: CommandResult,
        *expected_texts: str,
    ) -> None:
        """Assert that stdout contains every expected text fragment."""
        for text in expected_texts:
            assert text in result.stdout, (
                f"Expected stdout to contain {text!r}, got {result.stdout!r}"
            )

    def check_stderr_contains(
        self,
        result: CommandResult,
        *expected_texts: str,
    ) -> None:
        """Assert that stderr contains every expected text fragment."""
        for text in expected_texts:
            assert text in result.stderr, (
                f"Expected stderr to contain {text!r}, got {result.stderr!r}"
            )

    def check_stdout_contains_any(
        self,
        result: CommandResult,
        *expected_texts: str,
    ) -> None:
        """Assert that stdout contains at least one expected text fragment."""
        assert any(text in result.stdout for text in expected_texts), (
            f"Expected stdout to contain any of {expected_texts!r}, got {result.stdout!r}"
        )

    def check_stdout_matches(
        self,
        result: CommandResult,
        pattern: str,
    ) -> None:
        """Assert that stdout contains a regular-expression match."""
        assert re.search(pattern, result.stdout) is not None, (
            f"Expected stdout to match {pattern!r}, got {result.stdout!r}"
        )

    def run_and_check_command(
        self,
        dut: Dut,
        command: str,
        *,
        expected_stdout: str | None = None,
        expected_stderr: str | None = None,
        expected_exit_code: int = 0,
        timeout: float | None = None,
    ) -> CommandResult:
        """Run a DUT CLI command, validate it, and return its result."""
        result = self.run_command(
            dut,
            command,
            timeout=timeout,
        )
        self.check_command(
            result,
            expected_stdout=expected_stdout,
            expected_stderr=expected_stderr,
            expected_exit_code=expected_exit_code,
        )
        return result
