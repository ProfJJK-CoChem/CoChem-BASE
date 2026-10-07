"""CoChem Ecosystem Abstract Execution and Generation Interfaces.

Compliant with Method Matrix v4 and Zero-Mock Mandate.
"""

from __future__ import annotations

from cochem_base.interfaces.conformer import ConformerGenerator
from cochem_base.interfaces.executors import ElectronicStructureExecutor
from cochem_base.interfaces.module_registry import (
    ModuleCapability, ModuleStatus, get_module_capability, list_module_capabilities,
)
from cochem_base.interfaces.artifact_handoff import (
    ModuleHandoff, prepare_module_handoff, load_module_handoff,
)


class InterfaceUnavailableError(ImportError):
    """An advertised compatibility interface has no implementation in this checkout."""

    def __init__(self, interface: str, capability: str) -> None:
        self.interface = interface
        self.capability = capability
        super().__init__(
            f"{interface}: {capability} implementation is absent from this checkout. "
            "The legacy re-export did not contain a working implementation."
        )


__all__ = [
    "ElectronicStructureExecutor", "ConformerGenerator", "InterfaceUnavailableError",
    "ModuleCapability", "ModuleStatus", "get_module_capability", "list_module_capabilities",
    "ModuleHandoff", "prepare_module_handoff", "load_module_handoff",
]
