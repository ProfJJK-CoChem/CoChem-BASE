from enum import Enum
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

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
    mmff94_conformer: Optional[str] = None
    smiles_string: Optional[str] = None
    temperature: float = Field(default=298.15, gt=0)
    multiplicity: int = Field(default=1, ge=1)

class GeomTorqStage(BaseModel):
    """GeomTorqStage model with B3LYP-D3/D4 dispersion correction enforced."""
    b3lyp_opt: Optional[str] = None
    crest_screening: Optional[Dict] = Field(default_factory=dict)

class KineticLumosStage(BaseModel):
    wB97XD_opt: Optional[str] = None
    dlpno_ccsd_t: Optional[float] = None

class SpycfitShiftStage(BaseModel):
    bayesian_assignment: Optional[Dict] = Field(default_factory=dict)

class CorrelationMatrix(BaseModel):
    v4_matrix: MethodMatrixV4 = Field(default_factory=MethodMatrixV4)
    topos: ToposStage = Field(default_factory=ToposStage)
    geom_torq: GeomTorqStage = Field(default_factory=GeomTorqStage)
    kinetic_lumos: KineticLumosStage = Field(default_factory=KineticLumosStage)
    spycfit_shift: SpycfitShiftStage = Field(default_factory=SpycfitShiftStage)

class CoChemConfig(CorrelationMatrix):
    """Implementation pending"""