"""Domain exceptions raised by the hardware test framework."""


class HardwareTestError(Exception):
    """Base exception for expected framework failures."""


class InventoryError(HardwareTestError):
    """Raised when inventory data is invalid or cannot be resolved."""


class UnknownStandError(InventoryError):
    """Raised when a requested stand is absent from inventory."""


class FactoryError(HardwareTestError):
    """Raised when runtime objects cannot be constructed."""


class TransportError(HardwareTestError):
    """Raised when a transport cannot connect or complete an operation."""


class TransportTimeoutError(TransportError):
    """Raised when a transport operation exceeds its timeout."""


class UnsupportedCommandError(TransportError):
    """Raised when a transport cannot execute a command type."""
