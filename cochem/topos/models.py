"""Pydantic v2 JSON-safe domain models for CoChem-TOPOS subsystem."""

from __future__ import annotations

from typing import Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field


class BondOrderEdge(BaseModel):
    """Represents a perceived chemical bond with fractional or integer order between two atoms."""

    model_config = ConfigDict(populate_by_name=True)

    atom_i: int = Field(..., description="0-based index of the first atom in the bond")
    atom_j: int = Field(..., description="0-based index of the second atom in the bond")
    bond_order: float = Field(..., ge=0.0, description="Bond order (e.g., 1.0, 1.5, 2.0, 3.0)")


class MoleculeRecord(BaseModel):
    """Represents an unmocked molecular structure with 3D coordinates and topological attributes."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(default="", description="Molecular identifier or title")
    elements: List[str] = Field(..., description="List of elemental symbols")
    coordinates: List[Tuple[float, float, float]] = Field(
        ..., description="3D Cartesian coordinates in Angstroms"
    )
    formal_charges: List[int] = Field(..., description="Formal charge of each atom")
    partial_charges: List[float] = Field(
        default_factory=list, description="Electrostatic partial charges"
    )
    chiral_flags: List[int] = Field(
        default_factory=list, description="MDL or IUPAC chiral flags"
    )
    radical_centers: List[int] = Field(
        default_factory=list, description="Indices of radical atom centers"
    )
    mass_numbers: List[int] = Field(
        default_factory=list, description="Explicit isotopic mass numbers"
    )
    bonds: List[Tuple[int, int, float]] = Field(
        ..., description="Normalized 0-based bond edges: (idx_a, idx_b, bond_order)"
    )
    properties: Dict[str, str] = Field(
        default_factory=dict, description="Metadata key-value pairs (e.g., SD tags)"
    )

    @property
    def num_atoms(self) -> int:
        """Returns total atom count."""
        return len(self.elements)

    @property
    def num_bonds(self) -> int:
        """Returns total bond count."""
        return len(self.bonds)


class SubgraphDeltaRecord(BaseModel):
    """Represents a disconnected subgraph added or deleted during topology comparison."""

    model_config = ConfigDict(populate_by_name=True)

    atom_indices: List[int] = Field(..., description="Original indices of atoms in this subgraph")
    elements: List[str] = Field(..., description="Element symbols of subgraph atoms")
    bonds: List[Tuple[int, int, float]] = Field(..., description="Internal 0-based bonds")
    smiles: str = Field(..., description="SMILES representation of the isolated subgraph")


class TopologyDelta(BaseModel):
    """Captures maximum common substructure mapping and localized chemical mutations."""

    model_config = ConfigDict(populate_by_name=True)

    atom_mapping: Dict[int, int] = Field(
        ..., description="Bijection mapping mol_a atom index to mol_b atom index"
    )
    element_mutations: List[Tuple[int, str, str]] = Field(
        ..., description="Mutations in mapped atoms: (idx_a, elem_a, elem_b)"
    )
    bond_order_mutations: List[Tuple[int, int, float, float]] = Field(
        ..., description="Bond order modifications: (idx_a, idx_b, bo_a, bo_b)"
    )
    subgraph_additions: List[SubgraphDeltaRecord] = Field(
        ..., description="Subgraphs present in mol_b but absent in mol_a"
    )
    subgraph_deletions: List[SubgraphDeltaRecord] = Field(
        ..., description="Subgraphs present in mol_a but absent in mol_b"
    )

    def to_markdown_table(self) -> str:
        """Formats the topology difference as a GitHub-flavored markdown table."""
        lines = [
            "### Topology Comparison Delta",
            f"- **Mapped Core Atoms**: {len(self.atom_mapping)}",
            f"- **Element Mutations**: {len(self.element_mutations)}",
            f"- **Bond Order Mutations**: {len(self.bond_order_mutations)}",
            f"- **Subgraphs Added**: {len(self.subgraph_additions)}",
            f"- **Subgraphs Deleted**: {len(self.subgraph_deletions)}",
            "",
            "| Metric | Mol A -> Mol B Detail |",
            "|---|---|",
        ]
        for idx_a, elem_a, elem_b in self.element_mutations:
            lines.append(f"| Element Mutation | Atom {idx_a}: {elem_a} -> {elem_b} |")
        for idx_a, idx_b, bo_a, bo_b in self.bond_order_mutations:
            lines.append(f"| Bond Mutation | ({idx_a}, {idx_b}): {bo_a:.1f} -> {bo_b:.1f} |")
        for sub in self.subgraph_additions:
            lines.append(f"| Subgraph Addition | `{sub.smiles}` ({len(sub.elements)} atoms) |")
        for sub in self.subgraph_deletions:
            lines.append(f"| Subgraph Deletion | `{sub.smiles}` ({len(sub.elements)} atoms) |")
        return "\n".join(lines)


class AttachmentSite(BaseModel):
    """Metadata describing a retrosynthetic disconnection attachment point."""

    model_config = ConfigDict(populate_by_name=True)

    anchor_atom_idx: int = Field(
        ..., description="0-based index into synthon coordinates/elements"
    )
    brics_class: int = Field(
        ..., description="BRICS or RECAP classification rule number (1-16)"
    )
    polarity: str = Field(
        default="neutral",
        description="Reaction directionality: donor, acceptor, neutral",
    )
    connection_vector: Tuple[float, float, float] = Field(
        ..., description="Cartesian vector pointing from anchor atom to severed partner"
    )
    severed_partner_element: str = Field(
        ..., description="Elemental symbol of the severed bonded neighbor"
    )


class SynthonRecord(BaseModel):
    """Represents a retrosynthetic chemical fragment with preserved 3D geometry and attachment points."""

    model_config = ConfigDict(populate_by_name=True)

    smiles: str = Field(..., description="Tagged or canonical SMILES of the synthon")
    elements: List[str] = Field(..., description="Element symbols for all synthon atoms")
    coordinates: List[Tuple[float, float, float]] = Field(
        ..., description="3D coordinates for all synthon atoms"
    )
    bonds: List[Tuple[int, int, float]] = Field(
        ..., description="Internal 0-based bond connectivity: (idx_a, idx_b, bo)"
    )
    attachment_sites: List[AttachmentSite] = Field(
        ..., description="Disconnection attachment sites on this synthon"
    )
    formal_charge: int = Field(default=0, description="Net formal charge of synthon")


class NonBondedParameter(BaseModel):
    """Non-bonded Lennard-Jones and van der Waals parameters."""

    model_config = ConfigDict(populate_by_name=True)

    atom_type: str = Field(..., description="Force field atom type label")
    sigma_nm: float = Field(..., description="Lennard-Jones sigma parameter in nanometers")
    epsilon_kj_mol: float = Field(..., description="Well depth epsilon in kJ/mol")
    r_min_half_angstrom: float = Field(
        ..., description="van der Waals radius R* (r_min / 2) in Angstroms"
    )
    epsilon_kcal_mol: float = Field(..., description="Well depth epsilon in kcal/mol")


class ForceFieldAssignmentResult(BaseModel):
    """Results of topological atom typing and forcefield parameter assignment."""

    model_config = ConfigDict(populate_by_name=True)

    atom_types: List[str] = Field(..., description="Assigned atom type for each atom")
    charges: List[float] = Field(..., description="Assigned partial atomic charges")
    bonded_parameters: Dict[str, List[float]] = Field(
        default_factory=dict, description="Bonded parameter lookup tables"
    )
    non_bonded_parameters: List[NonBondedParameter] = Field(
        ..., description="List of non-bonded parameters per atom"
    )
    forcefield_family: str = Field(
        ..., description="Forcefield family name ('GAFF2' or 'OPLS-AA')"
    )
    energy_unit: str = Field(..., description="Unit of energy ('kcal/mol' or 'kJ/mol')")
    distance_unit: str = Field(
        ..., description="Unit of distance ('angstrom' or 'nanometer')"
    )
    angle_unit: str = Field(default="degrees", description="Unit of angle")


class BondPerceptionResult(BaseModel):
    """Results of bare coordinate bond-order and formal charge perception."""

    model_config = ConfigDict(populate_by_name=True)

    bond_orders: List[BondOrderEdge] = Field(..., description="List of perceived bond edges")
    formal_charges: List[int] = Field(..., description="Assigned formal charge per atom")
    lone_pairs: List[int] = Field(..., description="Assigned lone pair count per atom")
    total_charge: int = Field(..., description="Conserved net molecular charge")


class ECFP4FingerprintPayload(BaseModel):
    """Topological circular fingerprint payload with folded bitvectors and feature counts."""

    model_config = ConfigDict(populate_by_name=True)

    bit_vector_1024: List[int] = Field(..., description="Folded 1024-bit representation")
    bit_vector_2048: List[int] = Field(..., description="Folded 2048-bit representation")
    on_bits_2048: List[int] = Field(..., description="Indices of active bits in 2048-bit vector")
    count_vector: Dict[int, int] = Field(
        ..., description="Mapping of bit position to feature count"
    )
    features_de_duplicated: int = Field(
        ..., description="Total count of duplicate subgraphs pruned"
    )


class ExitVector(BaseModel):
    """Exit vector and normal reference frame at a severed scaffold-substituent bond."""

    model_config = ConfigDict(frozen=True)
    anchor_idx: int = Field(..., ge=0, description="0-based atom index of scaffold anchor")
    substituent_idx: int = Field(..., ge=0, description="0-based atom index of substituent atom")
    anchor_coord: List[float] = Field(..., min_length=3, max_length=3, description="Anchor Cartesian [x, y, z] in Angstrom")
    vector: List[float] = Field(..., min_length=3, max_length=3, description="Unit direction vector [vx, vy, vz]")
    normal_vector: List[float] = Field(..., min_length=3, max_length=3, description="Reference normal vector [nx, ny, nz]")


class ScaffoldHopResult(BaseModel):
    """Result of scaffold replacement including 3D alignment and multi-objective scoring."""

    model_config = ConfigDict(frozen=True)
    candidate_smiles: str = Field(..., description="SMILES of generated candidate")
    aligned_coordinates: List[List[float]] = Field(..., description="Nx3 Cartesian coordinates in Angstrom")
    shape_tanimoto: float = Field(..., ge=0.0, le=1.0)
    electrostatic_tanimoto: float = Field(..., ge=0.0, le=1.0)
    strain_energy_kcal_mol: float = Field(...)
    composite_score: float = Field(..., ge=0.0, le=1.0)


class GeometricViolation(BaseModel):
    """Geometric parameter exceeding tolerance threshold."""

    model_config = ConfigDict(frozen=True)
    violation_type: Literal["bond_length", "bond_angle", "steric_clash"]
    atom_indices: List[int] = Field(..., min_length=2, max_length=3)
    measured_value: float = Field(..., description="Measured distance (Angstrom) or angle (degrees)")
    reference_value: float = Field(..., description="Reference expected value")
    z_score: float = Field(..., ge=0.0)


class GeometryValidationResult(BaseModel):
    """Validation report containing statistical plausibility and any geometric violations."""

    model_config = ConfigDict(frozen=True)
    is_physically_plausible: bool
    max_z_score: float = Field(..., ge=0.0)
    violations: List[GeometricViolation] = Field(default_factory=list)


class PyMOLExportResult(BaseModel):
    """Outcome and metadata from PyMOL session or script export."""

    model_config = ConfigDict(frozen=True)
    session_path: str = Field(..., description="Absolute path to exported .pse or .pml file")
    export_mode: Literal["headless_api", "cli_script_bundle"]
    colored_domains_count: int = Field(..., ge=0)
    metal_centers_rendered: int = Field(..., ge=0)
    file_size_bytes: int = Field(..., gt=0)


class PolyhedronScore(BaseModel):
    """Continuous Shape Measure score against a canonical coordination polyhedron."""

    model_config = ConfigDict(frozen=True)
    polyhedron_name: str = Field(..., description="Canonical geometry (e.g., 'Octahedral', 'Square_Planar')")
    cshm_value: float = Field(..., ge=0.0, description="Continuous Shape Measure value S_P(Q)")


class CoordinationCenter(BaseModel):
    """Perceived metal center coordination environment and geometry."""

    model_config = ConfigDict(frozen=True)
    metal_idx: int = Field(..., ge=0)
    metal_element: str = Field(..., min_length=1, max_length=2)
    coordination_number: int = Field(..., ge=1, le=12)
    assigned_geometry: str
    formal_oxidation_state: int
    ligand_atom_indices: List[int]
    is_chelated: bool
    hapticities: Dict[str, int] = Field(default_factory=dict, description="Ligand group to eta^n mapping")
    polyhedron_scores: List[PolyhedronScore] = Field(default_factory=list)


class CoordinationPerceptionResult(BaseModel):
    """Overall metal perception analysis across all metal centers."""

    model_config = ConfigDict(frozen=True)
    coordination_centers: List[CoordinationCenter] = Field(default_factory=list)
    unassigned_metal_indices: List[int] = Field(default_factory=list)
    total_metals_detected: int = Field(..., ge=0)


class TopologySanitizationResult(BaseModel):
    """Sanitized topology result with stripped counterions and neutralized formal charges."""

    model_config = ConfigDict(frozen=True)
    sanitized_smiles: str
    sanitized_coordinates: Optional[List[List[float]]] = None
    formal_net_charge: int
    is_zwitterion: bool
    removed_counterions: List[str] = Field(default_factory=list)
    retained_atom_count: int = Field(..., gt=0)

