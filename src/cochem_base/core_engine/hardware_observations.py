"""Preserve measured, negative and unavailable ISA observations distinctly."""

from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter

_OPTIONAL_BOOL = TypeAdapter(bool | None)


def synchronize_avx512_observation(data: dict[str, Any]) -> None:
    """Normalize aliases without treating unavailable values as false.

    Both supplied aliases must describe the same observation. A missing value
    authorizes no accelerated execution and remains explicitly unknown.
    """
    names = ("avx_512_capable", "avx512_support")
    supplied = [_OPTIONAL_BOOL.validate_python(data[name]) for name in names if name in data]
    if len(supplied) == 2 and supplied[0] is not supplied[1]:
        raise ValueError("Conflicting AVX-512 observations in hardware aliases")
    observation = supplied[0] if supplied else None
    data.update({name: observation for name in names})
