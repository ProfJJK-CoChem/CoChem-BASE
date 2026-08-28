# -*- coding: utf-8 -*-
"""CoChem-SpycFit ML: Core Pydantic Schemas, Resource Limits, and Provenance Models.

Defines Pydantic v2 strict configuration models, dynamic isotope mass retrieval
via the mendeleev library, tripartite air-gap path validation, and DAG FitState schemas.

Authoritative Standards:
- CoChem-SpycFit ML Global Architecture Reference (00_GLOBAL_SYSTEM_PROMPT.md)
- Mendeleev Dynamic Isotopes Mandate (No hardcoded atomic masses)
- Tripartite Workspace Air-Gap Architecture (Tier 1 Repo, Tier 2 Artifacts, Tier 3 Scratch)
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from mendeleev import element
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class HardwareTier(str, Enum):
    """Hardware execution tier hierarchy."""
    GPU = "GPU"
    TPU = "TPU"
    CPU = "CPU"
    MPS = "MPS"


class HardwareResourceLimits(BaseModel):
    """Hardware resource boundaries and allocation bounds."""
    model_config = ConfigDict(extra="forbid")

    mpi_threads: int = Field(
        default=1,
        ge=1,
        le=1024,
        description="Number of OpenMPI / execution threads allocated (1 <= threads <= 1024)",
    )
    max_vram_gb: float = Field(
        default=0.0,
        ge=0.0,
        description="Allocated GPU VRAM in gigabytes (must be >= 0.0)",
    )
    allowed_devices: List[str] = Field(
        default_factory=lambda: ["cpu"],
        description="List of allowed JAX/CUDA execution device strings",
    )
    timeout_seconds: float = Field(
        default=300.0,
        gt=0.0,
        description="Max execution timeout in seconds",
    )
    max_ram_gb: float = Field(
        default=16.0,
        gt=0.0,
        description="Max system RAM threshold in gigabytes",
    )


class TripartiteWorkspaceConfig(BaseModel):
    """Tripartite Workspace Air-Gap Architecture Configuration.

    Enforces strict separation across:
    - Tier 1: Immutable Repository (Read-only code)
    - Tier 2: Persistent Artifacts (Verified state-addressed outputs)
    - Tier 3: Ephemeral Scratch (Isolated subprocess sandboxes)
    """
    model_config = ConfigDict(extra="forbid")

    tier1_repo_root: Path = Field(
        description="Tier 1: Read-only repository root path"
    )
    tier2_artifacts_root: Path = Field(
        description="Tier 2: Persistent verified artifacts root path"
    )
    tier3_scratch_root: Optional[Path] = Field(
        default=None,
        description="Tier 3: Ephemeral scratch directory"
    )

    @field_validator("tier1_repo_root", "tier2_artifacts_root", mode="before")
    @classmethod
    def _validate_mandatory_path(cls, v: Union[str, Path]) -> Path:
        if isinstance(v, (str, Path)):
            p = Path(v).resolve()
            return p
        raise ValueError(f"Invalid path: {v}")

    @field_validator("tier3_scratch_root", mode="before")
    @classmethod
    def _validate_optional_path(cls, v: Optional[Union[str, Path]]) -> Optional[Path]:
        if v is None:
            return None
        return Path(v).resolve()

    @classmethod
    def resolve_from_environment(cls) -> TripartiteWorkspaceConfig:
        """Resolve tripartite paths from environment variables or defaults."""
        tier1 = os.environ.get("COCHEM_SRC")
        if tier1:
            t1_path = Path(tier1).resolve()
        else:
            t1_path = Path(__file__).resolve().parent

        tier2 = os.environ.get("COCHEM_ARTIFACTS") or os.environ.get("COCHEM_ARTIFACTS_ROOT")
        if tier2:
            t2_path = Path(tier2).resolve()
        else:
            t2_path = (Path.home() / "CoChem_Artifacts").resolve()

        tier3 = os.environ.get("COCHEM_STATE")
        t3_path = Path(tier3).resolve() if tier3 else None

        return cls(
            tier1_repo_root=t1_path,
            tier2_artifacts_root=t2_path,
            tier3_scratch_root=t3_path,
        )


class DynamicIsotopeRecord(BaseModel):
    """Dynamic atomic and isotopic mass record retrieved via mendeleev."""
    model_config = ConfigDict(frozen=True)

    symbol: str = Field(description="Element chemical symbol (e.g. 'C', 'H', 'O', 'S')")
    mass_number: Optional[int] = Field(default=None, description="Isotope mass number (A)")
    exact_mass_amu: float = Field(gt=0.0, description="Dynamic atomic mass in AMU")

    @classmethod
    def from_mendeleev(cls, symbol: str, mass_number: Optional[int] = None) -> DynamicIsotopeRecord:
        """Dynamically query mendeleev for element/isotope mass."""
        el = element(symbol)
        if mass_number is not None:
            exact_m = None
            if hasattr(el, "isotopes") and el.isotopes:
                for iso in el.isotopes:
                    if getattr(iso, "mass_number", None) == mass_number:
                        exact_m = getattr(iso, "mass", None)
                        break
            if exact_m is None:
                exact_m = float(el.mass)
            return cls(symbol=symbol, mass_number=mass_number, exact_mass_amu=float(exact_m))
        else:
            return cls(symbol=symbol, mass_number=None, exact_mass_amu=float(el.mass))

    @classmethod
    def calculate_molecular_mass(cls, formula_or_atoms: List[Tuple[str, int]]) -> float:
        """Calculate exact molecular mass dynamically using mendeleev."""
        total_mass = 0.0
        for sym, count in formula_or_atoms:
            el = element(sym)
            total_mass += float(el.mass) * count
        return total_mass


class FitStateCommitSchema(BaseModel):
    """Immutable cryptographic DAG state snapshot for spectroscopic assignments."""
    model_config = ConfigDict(frozen=True)

    state_id: str = Field(
        default="",
        description="SHA-256 hash uniquely identifying this state commit. Auto-computed if empty.",
    )
    parent_id: Optional[str] = Field(
        default=None,
        description="SHA-256 hash of parent state in DAG. None for root commit.",
    )
    timestamp_iso: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC ISO timestamp of state commit",
    )
    rotational_constants_mhz: Dict[str, float] = Field(
        default_factory=dict,
        description="Refined rotational constants (A, B, C, DJ, DJK, DK, etc.) in MHz",
    )
    dipole_moments_debye: Dict[str, float] = Field(
        default_factory=dict,
        description="Dipole moment components (mu_a, mu_b, mu_c) in Debye",
    )
    assigned_transitions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Assigned quantum transitions with frequencies, residuals, and tags",
    )
    ml_hyperparameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Serialized Gaussian Process hyperparameters and weights",
    )
    chi_squared: float = Field(
        default=0.0,
        ge=0.0,
        description="Global chi-squared fitting metric",
    )
    rms_residual_mhz: float = Field(
        default=0.0,
        ge=0.0,
        description="Root-mean-square frequency residual in MHz",
    )
    provenance_git_hash: str = Field(
        default="",
        description="Cryptographic Git commit hash of the executing codebase",
    )

    def compute_state_hash(self) -> str:
        """Compute canonical SHA-256 hash representing this state."""
        payload = {
            "parent_id": self.parent_id,
            "rotational_constants_mhz": {k: round(v, 8) for k, v in sorted(self.rotational_constants_mhz.items())},
            "dipole_moments_debye": {k: round(v, 8) for k, v in sorted(self.dipole_moments_debye.items())},
            "assigned_transitions": self.assigned_transitions,
            "ml_hyperparameters": self.ml_hyperparameters,
            "chi_squared": round(self.chi_squared, 8),
            "rms_residual_mhz": round(self.rms_residual_mhz, 8),
            "provenance_git_hash": self.provenance_git_hash,
        }
        canonical_str = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    @model_validator(mode="after")
    def _compute_state_id(self) -> FitStateCommitSchema:
        if not self.state_id:
            computed = self.compute_state_hash()
            object.__setattr__(self, "state_id", computed)
        return self


class ProvenanceLedgerEntry(BaseModel):
    """Cryptographic provenance audit ledger entry."""
    model_config = ConfigDict(frozen=True)

    entry_id: str = Field(description="Unique audit log entry identifier")
    timestamp_iso: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC ISO timestamp of ledger entry",
    )
    action: str = Field(description="Recorded action: COMMIT, REVERT, GP_RETRAIN, PARITY_CHECK")
    fit_state_id: str = Field(description="Associated FitState SHA-256 state ID")
    actor: str = Field(default="CoChem-CODER", description="Agent or user entity triggering action")
    checksum_sha256: str = Field(description="SHA-256 verification checksum")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Supplementary execution metadata")


class SpycFitMLConfig(BaseModel):
    """Master configuration schema for CoChem-SpycFit ML engine."""
    hardware: HardwareResourceLimits = Field(default_factory=HardwareResourceLimits)
    workspace: Optional[TripartiteWorkspaceConfig] = None
    gp_alpha: float = Field(default=1e-4, gt=0.0, description="GP noise regularization parameter")
    parity_warning_threshold_khz: float = Field(
        default=0.1,
        gt=0.0,
        description="Threshold in kHz for JAX vs SPFIT parity warning flag",
    )
    instrument_resolution_mhz: float = Field(
        default=0.05,
        gt=0.0,
        description="Instrument frequency linewidth resolution in MHz",
    )
    scan_window_size_mhz: float = Field(
        default=500.0,
        gt=0.0,
        description="Hardware-aware chunked scan window bandwidth in MHz",
    )
