"""Generic measurement value objects."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Measurement:
    """A named scalar measurement with a unit."""

    name: str
    value: float
    unit: str
