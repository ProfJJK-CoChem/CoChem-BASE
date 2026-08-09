from pydantic import BaseModel, Field
from typing import Optional, List, Dict

class ToposStage(BaseModel):
    """Stage 1: Combinatorial Engine (TOPOS) Data"""
    mmff94_conformer: Optional[str] = Field(None, description="Path or string representing MMFF94 Conformer")
    smiles_string: Optional[str] = Field(None, description="SMILES string of the molecule")
    torsional_scan: Optional[List[float]] = Field(default_factory=list, description="Torsional scan coordinates")
    point_group_id: Optional[str] = Field(None, description="Point Group symmetry ID")
    z_matrix: Optional[str] = Field(None, description="Z-Matrix of the conformer")
    
    # GUI Suggestion: Scientific Error Prevention
    temperature: float = Field(298.15, ge=0.0, description="System temperature in Kelvin (cannot be negative)")
    multiplicity: int = Field(1, ge=1, description="Spin multiplicity (must be >= 1)")

class GeomTorqStage(BaseModel):
    """Stage 2: Precision Structure and Quantum Resonance (GEOM / TORQ)"""
    b3lyp_opt: Optional[str] = Field(None, description="B3LYP/6-31G(d) Geometry Optimization result path")
    crest_screening: Optional[Dict] = Field(default_factory=dict, description="CREST Conformational Screening results")
    anharmonic_freq: Optional[List[float]] = Field(default_factory=list, description="Anharmonic Frequencies")
    hessian_matrix: Optional[List[List[float]]] = Field(default_factory=list, description="Hessian Matrix")
    internal_coords: Optional[Dict] = Field(default_factory=dict, description="Internal coordinates mapping")

class KineticLumosStage(BaseModel):
    """Stage 3: Transition State & Excited State (KINETIC / LUMOS)"""
    wB97XD_opt: Optional[str] = Field(None, description="ωB97X-D/def2-TZVP results")
    dlpno_ccsd_t: Optional[float] = Field(None, description="DLPNO-CCSD(T) Energy")
    rrkm_rate_constants: Optional[Dict[str, float]] = Field(default_factory=dict, description="RRKM Rate Constants")
    uv_vis_tddft: Optional[Dict] = Field(default_factory=dict, description="UV-Vis TD-DFT spectral data")
    transition_state_opt: Optional[str] = Field(None, description="Transition State Geometry Opt result")

class SpycfitShiftStage(BaseModel):
    """Stage 4: Spectroscopy (SpycFit / SHIFT)"""
    bayesian_assignment: Optional[Dict] = Field(default_factory=dict, description="Bayesian Spectral Assignment")
    spectral_fitting: Optional[Dict] = Field(default_factory=dict, description="Fitted spectral parameters")
    nmr_shielding_tensor: Optional[List[List[float]]] = Field(default_factory=list, description="NMR Shielding Tensor")
    franck_condon_factors: Optional[List[float]] = Field(default_factory=list, description="Franck-Condon Factors")
    vibrational_modes: Optional[List[Dict]] = Field(default_factory=list, description="Vibrational Modes")

class CorrelationMatrix(BaseModel):
    """
    Central Method Pass-Through / Correlation Matrix
    Ensures strict typing between computational stages.
    """
    topos: ToposStage = Field(default_factory=ToposStage)
    geom_torq: GeomTorqStage = Field(default_factory=GeomTorqStage)
    kinetic_lumos: KineticLumosStage = Field(default_factory=KineticLumosStage)
    spycfit_shift: SpycfitShiftStage = Field(default_factory=SpycfitShiftStage)
    target_property: Optional[str] = Field(None, description="Final target property objective")
