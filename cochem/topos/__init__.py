"""CoChem-TOPOS: Pure Topological Molecular Graph Theory and Geometry Subsystem."""

from __future__ import annotations

from cochem.topos.canonicalization import (
    TopologicalCanonicalizer,
    compute_node_invariant,
    compute_smallest_rings,
)
from cochem.topos.clash import ClashPair, GeometricClashDetector
from cochem.topos.coarse_grain import GraphCrusherConfig, crush_macromolecule
from cochem.topos.diff import compute_topology_diff
from cochem.topos.exceptions import (
    BondPerceptionError,
    ChiralityAssignmentError,
    CoChemError,
    CoChemToposException,
    FingerprintGenerationError,
    FragmentationError,
    GraphSparsificationError,
    IsomorphismMismatchError,
    IsotopeResolutionError,
    MalformedRecordError,
    ParsingAirGapError,
    PharmacophoreExtractionError,
    ResonanceEnumerationError,
    SolventBuilderError,
    StericClashError,
    SymmetryPerceptionError,
    TopologicalCanonicalizationError,
    TopologyDiffError,
    TopologyError,
    ToposError,
    TPSACalculationError,
    UnparameterizedAtomError,
)
from cochem.topos.fingerprint import (
    compute_dice_similarity,
    compute_tanimoto_similarity,
    generate_ecfp4_fingerprint,
)
from cochem.topos.forcefield import (
    assign_forcefield_parameters,
    geometric_combine,
    lorentz_berthelot_combine,
)
from cochem.topos.fragmentation import (
    fragment_by_brics,
    fragment_by_recap,
)
from cochem.topos.graph import TopologyGraph
from cochem.topos.io import (
    Mol2StreamReader,
    Mol2Writer,
    SDFStreamReader,
    SDFWriter,
)
from cochem.topos.isotopes import (
    IsotopeManager,
    IsotopeNodeSpec,
    get_isotope_info,
    get_isotope_mass,
)
from cochem.topos.models import (
    AttachmentSite,
    BondOrderEdge,
    BondPerceptionResult,
    ECFP4FingerprintPayload,
    ForceFieldAssignmentResult,
    MoleculeRecord,
    NonBondedParameter,
    SubgraphDeltaRecord,
    SynthonRecord,
    TopologyDelta,
)
from cochem.topos.perception import perceive_bond_orders_from_xyz
from cochem.topos.pharmacophore import (
    PharmacophoreExtractor,
    PharmacophoreFeature,
    PharmacophoreFeatureSet,
)
from cochem.topos.resonance import (
    ResonanceEnsembleResult,
    ResonanceEnumerator,
    ResonanceStructure,
)
from cochem.topos.rings import (
    canonicalize_cycle,
    perceive_aromaticity,
    perceive_cycle_basis,
)
from cochem.topos.solvent import ExplicitSolventBuilder, SolventBox
from cochem.topos.sparsification import (
    GraphSparsifier,
    SparsifiedGraphResult,
    SparseEdge,
    load_pdb_topology,
)
from cochem.topos.stereochemistry import (
    assign_double_bond_stereo,
    assign_tetrahedral_chirality,
    compute_dihedral_angle,
)
from cochem.topos.symmetry import (
    TopologicalSymmetryAnalyzer,
    TopologicalSymmetryResult,
)
from cochem.topos.tpsa import (
    TPSACalculator,
    TPSAResult,
)
from cochem.topos.visualization import TOPOSpy3DmolWidget

__all__ = [
    "TopologyGraph",
    "GraphCrusherConfig",
    "crush_macromolecule",
    "perceive_cycle_basis",
    "perceive_aromaticity",
    "canonicalize_cycle",
    "assign_tetrahedral_chirality",
    "assign_double_bond_stereo",
    "compute_dihedral_angle",
    "TOPOSpy3DmolWidget",
    "GeometricClashDetector",
    "ClashPair",
    "CoChemError",
    "ToposError",
    "TopologyError",
    "StericClashError",
    "IsomorphismMismatchError",
    "ChiralityAssignmentError",
    "CoChemToposException",
    "SymmetryPerceptionError",
    "PharmacophoreExtractionError",
    "IsotopeResolutionError",
    "TPSACalculationError",
    "ResonanceEnumerationError",
    "GraphSparsificationError",
    "TopologicalSymmetryResult",
    "TopologicalSymmetryAnalyzer",
    "PharmacophoreFeature",
    "PharmacophoreFeatureSet",
    "PharmacophoreExtractor",
    "IsotopeNodeSpec",
    "IsotopeManager",
    "get_isotope_mass",
    "get_isotope_info",
    "TPSAResult",
    "TPSACalculator",
    "ResonanceStructure",
    "ResonanceEnsembleResult",
    "ResonanceEnumerator",
    "SparseEdge",
    "SparsifiedGraphResult",
    "GraphSparsifier",
    "load_pdb_topology",
    "SolventBuilderError",
    "TopologicalCanonicalizationError",
    "ExplicitSolventBuilder",
    "SolventBox",
    "TopologicalCanonicalizer",
    "compute_node_invariant",
    "compute_smallest_rings",
    # Chunk 11 additions
    "MalformedRecordError",
    "UnparameterizedAtomError",
    "BondPerceptionError",
    "ParsingAirGapError",
    "TopologyDiffError",
    "FragmentationError",
    "FingerprintGenerationError",
    "BondOrderEdge",
    "MoleculeRecord",
    "SubgraphDeltaRecord",
    "TopologyDelta",
    "AttachmentSite",
    "SynthonRecord",
    "NonBondedParameter",
    "ForceFieldAssignmentResult",
    "BondPerceptionResult",
    "ECFP4FingerprintPayload",
    "SDFStreamReader",
    "Mol2StreamReader",
    "SDFWriter",
    "Mol2Writer",
    "assign_forcefield_parameters",
    "lorentz_berthelot_combine",
    "geometric_combine",
    "fragment_by_brics",
    "fragment_by_recap",
    "perceive_bond_orders_from_xyz",
    "compute_topology_diff",
    "generate_ecfp4_fingerprint",
    "compute_tanimoto_similarity",
    "compute_dice_similarity",
]
