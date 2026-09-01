"""CoChem-GEOM: Root eval package alias for modular imports."""

from cochem_geom.eval.alignment import EPSILON_RMSD, kabsch_alignment
from eval.metrics import DEFAULT_COV_THRESHOLD, calculate_ensemble_metrics
from eval.qm_oracle import (
    DEFAULT_FMAX_EV_ANGSTROM,
    DEFAULT_MAX_STEPS,
    HARTREE_TO_EV,
    NativeXTBCalculator,
    QMOracle,
    QMOracleConfig,
    RelaxationResult,
    create_xtb_calculator,
    get_atomic_mass,
    get_xtb_binary_path,
    relax_conformer_xtb,
)

__all__ = [
    "DEFAULT_COV_THRESHOLD",
    "DEFAULT_FMAX_EV_ANGSTROM",
    "DEFAULT_MAX_STEPS",
    "EPSILON_RMSD",
    "HARTREE_TO_EV",
    "NativeXTBCalculator",
    "QMOracle",
    "QMOracleConfig",
    "RelaxationResult",
    "calculate_ensemble_metrics",
    "create_xtb_calculator",
    "get_atomic_mass",
    "get_xtb_binary_path",
    "kabsch_alignment",
    "relax_conformer_xtb",
]
