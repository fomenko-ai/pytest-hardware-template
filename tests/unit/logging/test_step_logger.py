"""Tests for numbered step logging and its pytest fixtures."""

import logging

import pytest

from hardware_test.logging import StepLogger


def test_step_logger_logs_numbered_messages(caplog: pytest.LogCaptureFixture) -> None:
    step = StepLogger(logging.getLogger("test.step_logger"))

    with caplog.at_level(logging.INFO):
        step.log("Connect to analyzer")
        step.log("Start measurement")

    assert caplog.messages == [
        "Step 1: Connect to analyzer",
        "Step 2: Start measurement",
    ]


class TestFunctionScopedStepLogger:
    """The function-scoped fixture starts from step one in every test."""

    def test_first_function(
        self,
        func_step_logger: StepLogger,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.INFO):
            func_step_logger.log("First function")

        assert caplog.messages == ["Step 1: First function"]

    def test_second_function(
        self,
        func_step_logger: StepLogger,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.INFO):
            func_step_logger.log("Second function")

        assert caplog.messages == ["Step 1: Second function"]


class TestClassScopedStepLogger:
    """The class-scoped fixture retains its counter between test methods."""

    def test_first_method(
        self,
        cls_step_logger: StepLogger,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.INFO):
            cls_step_logger.log("First method")

        assert caplog.messages == ["Step 1: First method"]

    def test_second_method(
        self,
        cls_step_logger: StepLogger,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.INFO):
            cls_step_logger.log("Second method")

        assert caplog.messages == ["Step 2: Second method"]
