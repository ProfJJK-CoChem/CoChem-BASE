"""Discovery contracts for BASE and separately delivered ecosystem modules.

Importable namespace packages and legacy compatibility files do not prove that
a scientific module is installed or that its calculations have been validated.
External distributions advertise metadata through the ``cochem.modules`` entry
point group. This namespace-level discovery never imports those providers. BASE's
student research service separately probes reviewed isolated installations and
their callable receiver contracts before enabling operations.
"""
from __future__ import annotations

from enum import Enum
from importlib import metadata
from typing import Literal

from pydantic import BaseModel, ConfigDict

ENTRY_POINT_GROUP = "cochem.modules"


class ModuleStatus(str, Enum):
    AVAILABLE = "available"
    NOT_INSTALLED = "not_installed"
    INSTALLED_PENDING_INTEGRATION = "installed_pending_integration"
    CONFLICTING_PROVIDERS = "conflicting_providers"


class ModuleCapability(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    module_id: str
    name: str
    responsibility: str
    status: ModuleStatus
    integration_contract: str = "cochem.module-handoff/1"
    providers: tuple[str, ...] = ()
    operations: tuple[str, ...] = ()
    execution_verified: Literal[False] = False


# Names from the ecosystem deployment contract are descriptions, not statements
# that repositories, dependencies, providers or scientific engines are present.
_MODULES = {
    "base": ("CoChem-BASE", "Ingestion, setup, execution orchestration and GUI"),
    "topos": ("CoChem-TOPOS", "Conformer and topology workflows"),
    "torq": ("CoChem-TORQ", "Torsional surfaces and coupled nuclear-motion workflows"),
    "spycfit": ("CoChem-SPYCFIT", "Spectroscopy fitting and export"),
    "scribe": ("CoChem-SCRIBE", "Scientific documents and reporting"),
    "dock": ("CoChem-DOCK", "Remote service and telemetry interface"),
    **{name: ("CoChem-" + name.upper(), "External ecosystem workflow") for name in (
        "node", "oracle", "bench", "kinetic", "lumos", "mage", "scan", "shift",
        "geom", "council", "cure", "ehs", "eval", "labs", "play", "pulse", "seed", "orb",
    )},
}
_CONSOLIDATED = {"core", "mint", "unity", "synap"}


def canonical_module_id(module_id: str) -> str:
    name = module_id.strip().lower().removeprefix("cochem-")
    name = "base" if name in _CONSOLIDATED else name
    if name not in _MODULES:
        raise ValueError(f"Unknown ecosystem module: {module_id!r}")
    return name


def get_module_capability(module_id: str) -> ModuleCapability:
    """Report observed provider metadata without claiming executed science."""
    name = canonical_module_id(module_id)
    title, responsibility = _MODULES[name]
    if name == "base":
        return ModuleCapability(
            module_id=name, name=title, responsibility=responsibility,
            status=ModuleStatus.AVAILABLE,
            operations=("setup", "ingest_artifact", "electronic_calculation", "inspect_hessian", "prepare_module_handoff",
                        "execute_module_handoff", "student_research"),
        )
    candidates = [ep for ep in metadata.entry_points(group=ENTRY_POINT_GROUP)
                  if ep.name.lower().removeprefix("cochem-") == name]
    providers = tuple(sorted(
        f"{ep.dist.name}=={ep.dist.version}:{ep.value}" if ep.dist else ep.value
        for ep in candidates
    ))
    status = (ModuleStatus.CONFLICTING_PROVIDERS if len(providers) > 1 else
              ModuleStatus.INSTALLED_PENDING_INTEGRATION if providers else ModuleStatus.NOT_INSTALLED)
    return ModuleCapability(module_id=name, name=title, responsibility=responsibility,
                            status=status, providers=providers)


def list_module_capabilities() -> tuple[ModuleCapability, ...]:
    return tuple(get_module_capability(name) for name in _MODULES)
