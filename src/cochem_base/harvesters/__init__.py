"""CoChem-SCRIBE Harvesters Package."""

from .scribe_aggregator import (
    HARTREE_TO_KCAL_MOL,
    DataAggregator,
    ScribeAggregationError,
)


def __getattr__(name: str):
    """Load optional prompt-building dependencies only when requested."""
    if name == "PayloadBuilder":
        from .scribe_payload_builder import PayloadBuilder

        return PayloadBuilder
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "HARTREE_TO_KCAL_MOL",
    "DataAggregator",
    "ScribeAggregationError",
    "PayloadBuilder",
]
