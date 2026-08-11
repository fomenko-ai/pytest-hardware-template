"""Sequential test-step logging."""

import logging


class StepLogger:
    """Log numbered test steps while keeping the counter in memory."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger
        self._step = 0

    def log(self, message: str) -> None:
        """Log the next numbered step at INFO level."""
        self._step += 1
        self._logger.info("Step %d: %s", self._step, message)
