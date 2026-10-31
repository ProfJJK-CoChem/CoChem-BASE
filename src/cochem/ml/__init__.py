"""Lazy supported BASE compatibility exports, without sibling TORQ imports."""

from __future__ import annotations

from importlib import import_module

from cochem_base.ml._legacy_api import unavailable_attribute

_MODULES = {
    "active_learning": "cochem.ml.active_learning",
    "conformal": "cochem.ml.conformal",
    "delta": "cochem.ml.delta",
    "models": "cochem.ml.models",
    "schemas": "cochem.ml.schemas",
}
_EXPORTS = {}
_UNAVAILABLE = ()


def __getattr__(name: str):
    if name in _MODULES:
        value = import_module(_MODULES[name])
    elif name in _EXPORTS:
        module_name, attribute = _EXPORTS[name]
        value = getattr(import_module(module_name), attribute)
    else:
        return unavailable_attribute(__name__, name, _UNAVAILABLE)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))


__all__ = ["active_learning", "conformal", "delta", "models", "schemas"]
