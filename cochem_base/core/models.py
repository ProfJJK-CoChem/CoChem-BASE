from enum import Enum
from pathlib import Path
import os
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class ProductClassEnum(str, Enum):
    CLASS_A = "Product_A_DeNovo"
    CLASS_B = "Product_B_SemiExperimental"
    CLASS_C = "Product_C_Differences"

class ConcurrencyTag(str, Enum):
    CPU_BOUND = "C"
    GPU_BOUND = "G"
    PIPELINEABLE = "P"
    SERIAL_BOTTLENECK = "S"

class FrozenMonomerFlag(str, Enum):
    RELAXED = "relaxed"
    FROZEN_ISOLATED = "frozen-iso"
    FROZEN_IN_COMPLEX = "frozen-inc"

class TierRowConfig(BaseModel):
    tier_id: str = Field(..., description="Tier ID string, e.g., T3O-12h")
    category: str = Field(..., description="T1 (Search), T2 (PES), T3 (Geom), T4 (Vib), T5 (Interaction)")
    walltime_seconds: int = Field(..., description="Wall-clock budget in seconds")
    method_string: str = Field(..., description="Exact electronic structure method keyword")
    basis_set: str = Field(..., description="Primary orbital basis set")
    auxiliary_basis: Optional[str] = Field(None, description="Auxiliary fitting basis set")
    accuracy_window_mhz: Dict[str, float] = Field(..., description="Target search window at 12 GHz")
    concurrency_tags: List[ConcurrencyTag] = Field(..., description="Resource concurrency classification")
    state_in_dependencies: List[str] = Field(default_factory=list, description="Required input states")
    state_out_artifacts: List[str] = Field(default_factory=list, description="Emitted state artifacts")
    frozen_monomer_mode: FrozenMonomerFlag = Field(default=FrozenMonomerFlag.RELAXED, description="Frozen-monomer mode")
    provenance_tag: str = Field(..., description="[M], [D], or [E] tag for accuracy claim")

    @field_validator("provenance_tag")
    @classmethod
    def validate_provenance_tag(cls, v: str) -> str:
        if v not in ["[M]", "[D]", "[E]"]:
            raise ValueError("Provenance tag must be one of [M], [D], [E]")
        return v

class ProductClassConfig(BaseModel):
    product_class: ProductClassEnum
    target_accuracy_b0_percent: float = Field(..., description="B0 target accuracy percentage")
    search_window_12ghz_mhz: float = Field(..., description="Search window width at 12 GHz")
    mandatory_spend_priority: List[str] = Field(..., description="Ordered list of compute spend priorities (§3.3)")

class MethodMatrixV4(BaseModel):
    version: str = Field("4.0.0", description="Method Matrix specification version")
    product_classes: Dict[str, ProductClassConfig] = Field(default_factory=dict)
    tier_rows: Dict[str, TierRowConfig] = Field(default_factory=dict)
    concurrency_guards: Dict[str, bool] = Field(default_factory=dict)

# Backward Compatibility Migration Wrappers
class ToposStage(BaseModel):
    goat_crest_union: Optional[str] = Field(default=None, description="Path to GOAT/CREST union conformer ensemble")
    smiles_string: Optional[str] = None
    temperature: float = Field(default=298.15, gt=0, description="Standard thermodynamic temperature (K)")
    pressure_atm: float = Field(default=1.0, gt=0, description="Standard thermodynamic pressure (atm)")
    multiplicity: int = Field(default=1, ge=1)
    charge: int = Field(default=0)
    s_squared_threshold: float = Field(default=0.10, description="Halt if S^2 error > 10% for open-shell systems")

class GeomTorqStage(BaseModel):
    """GeomTorqStage model with Method Matrix dispersion correction and grid tightening enforced."""
    frozen_monomer_opt: Optional[str] = Field(default=None, description="Path to frozen-monomer optimization output")
    crest_screening: Optional[Dict] = Field(default_factory=dict)
    dispersion_correction: str = Field("D4", pattern="^(D3|D4|D3BJ|D4BJ)$", description="Must include D3/D4 dispersion")
    hessian_preconditioner: str = Field("InHess XTB2", pattern="^(InHess XTB2|Lindh)$", description="Never use Calc_Hess true")
    grid_start: str = Field("defgrid1", description="Optimization start loose grid")
    grid_final: str = Field("defgrid3", description="Optimization tighten near minimum grid")

class IntermolecularConvergence(BaseModel):
    tol_max_g: float = Field(1e-5, description="TolMaxG 1e-5 for weak complexes")
    bsse_correction_applied: bool = Field(True, description="Must apply BSSE correction")

class KineticLumosStage(BaseModel):
    dft_dispersion_opt: Optional[str] = Field(default=None, description="DFT optimization with D3/D4 enforced")
    dlpno_ccsd_t: Optional[float] = None
    intermolecular: IntermolecularConvergence = Field(default_factory=IntermolecularConvergence)

class SpycfitShiftStage(BaseModel):
    split_conformal_assignment: Optional[Dict] = Field(default_factory=dict, description="Split-conformal replacement for Bayesian anchor")

class CorrelationMatrix(BaseModel):
    v4_matrix: MethodMatrixV4 = Field(default_factory=MethodMatrixV4)
    topos: ToposStage = Field(default_factory=ToposStage)
    geom_torq: GeomTorqStage = Field(default_factory=GeomTorqStage)
    kinetic_lumos: KineticLumosStage = Field(default_factory=KineticLumosStage)
    spycfit_shift: SpycfitShiftStage = Field(default_factory=SpycfitShiftStage)

class CoChemConfig(CorrelationMatrix):
    """Main CoChem Configuration enforcing Method Matrix v4 compliance."""
    project_name: str = Field(..., description="Name of the CoChem project")
    artifacts_dir: Path = Field(
        default_factory=lambda: Path(os.environ.get("COCHEM_ARTIFACTS_DIR", str(Path.home() / "cochem_artifacts"))),
        description="Configurable artifacts directory"
    )
    workflow_id: str = Field(default="default_workflow", description="Unique identifier for the execution")
