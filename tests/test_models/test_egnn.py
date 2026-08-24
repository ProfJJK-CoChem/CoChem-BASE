"""Zero-Mock Physics Contract & Unit Test Suite for Equivariant GNN (EGNN).
=============================================================================
Provides production-grade mathematical, symmetry, and physical validation of
EGNNLayer, EGNN (Equivariant3DGNN), EGNNModelConfig, GNNOutput, GNNForceOutput,
analytical force derivation via autograd, dynamic Mendeleev atomic mass queries,
pure state immutability, and full E(n) / SE(3) / O(3) equivariance and invariance.

Authoritative Standards & Physics Contracts:
- Method Matrix v4: Physics Contract, Invariance/Equivariance Bounds, Provenance Tags
- SWEBOK v3 / ISO 25010 Software Quality & Mathematical Correctness Standards
- Strict Zero-Mock Mandate: 100% real physical tensor mathematics, zero mocks/stubs
- Mendeleev Library Mandate: Dynamic atomic & isotopic mass resolution (no hardcoding)
- E(n) / SE(3) / O(3) Equivariance & Invariance:
    * Scalar energies: E(r @ R^T + t) == E(r)  [E(3) Invariant] [M]
    * Analytical forces: F(r @ R^T + t) == F(r) @ R^T  [E(3) Equivariant] [D]
    * Coordinate updates: pos_new(r @ R^T + t) == pos_new(r) @ R^T + t  [E(3) Equivariant] [D]
    * Invariant node features: h_new(r @ R^T + t) == h_new(r)  [E(3) Invariant] [D]
    * Net force conservation: sum_i F_i == 0  [Translational Invariance] [M]
    * O(3) Parity Reflections: E(r @ R_refl^T) == E(r), F(r @ R_refl^T) == F(r) @ R_refl^T [M]
- State Immutability: Geometric transformations are pure and functional (pos = pos + update)
- Provenance Tagging: Explicitly tag all tolerances, constants, and bounds with [M], [D], [E]
"""

from __future__ import annotations

import copy
import math
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

import mendeleev
import numpy as np
from pydantic import ValidationError
import pytest
import torch
import torch.nn as nn
import torch.nn.functional as F

# ==============================================================================
# 0. Dynamic Cross-Platform Path Resolution
# ==============================================================================

CURRENT_FILE = Path(__file__).resolve()
TESTS_DIR = CURRENT_FILE.parent.parent
REPO_ROOT = TESTS_DIR.parent
COCHEM_GEOM_DIR = os.environ.get("COCHEM_GEOM_DIR")

if COCHEM_GEOM_DIR:
    GEOM_ROOT = Path(COCHEM_GEOM_DIR).resolve()
elif (REPO_ROOT / "src" / "cochem_geom").exists():
    GEOM_ROOT = REPO_ROOT
elif (REPO_ROOT.parent / "CoChem-GEOM").exists():
    GEOM_ROOT = REPO_ROOT.parent / "CoChem-GEOM"
else:
    GEOM_ROOT = REPO_ROOT

for path_entry in [
    str(GEOM_ROOT / "src"),
    str(GEOM_ROOT / "scripts"),
    str(GEOM_ROOT),
    str(REPO_ROOT / "src"),
    str(REPO_ROOT),
]:
    if Path(path_entry).exists() and path_entry not in sys.path:
        sys.path.insert(0, path_entry)

# Import base contracts, constants, and operators
from cochem_geom.models.base_gnn import (
    ATOMIC_MASS_UNIT_KG,
    AVOGADRO_CONSTANT_MOL,
    BOHR_RADIUS_ANGSTROM,
    BOLTZMANN_CONSTANT_EV_K,
    BOLTZMANN_CONSTANT_J_K,
    DEFAULT_HIDDEN_CHANNELS,
    DEFAULT_MAX_Z,
    DEFAULT_NUM_LAYERS,
    DEFAULT_NUM_RADIAL,
    DEFAULT_RBF_CUTOFF,
    ELEMENTARY_CHARGE_C,
    EV_TO_HARTREE,
    HARTREE_TO_EV,
    HARTREE_TO_KCAL_MOL,
    KCAL_MOL_TO_EV,
    PLANCK_CONSTANT_J_S,
    ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ,
    SPEED_OF_LIGHT_M_S,
    STANDARD_TEMPERATURE_K,
    Base3DGNN,
    BaseGNNLayer,
    ConformerInputContract,
    GNNForceOutput,
    GNNModelConfig,
    GNNOutput,
    GNNPredictionContract,
    RadialBasisExpansion,
    apply_coordinate_delta,
    build_radius_graph,
    center_coordinates,
    compute_center_of_mass,
    compute_moment_of_inertia_tensor,
    compute_principal_rotational_constants,
    extract_gnn_inputs,
    generate_random_so3_rotation,
    get_atomic_masses,
    resolve_dynamic_mass,
    resolve_dynamic_monoisotopic_mass,
    rotate_coordinates,
    translate_coordinates,
    verify_se3_equivariance,
)

# Attempt import from dedicated egnn module or fallback to base_gnn Equivariant classes
try:
    from cochem_geom.models.egnn import (
        EGNN,
        EGNNLayer,
        EGNNModelConfig,
    )
except ImportError:
    from cochem_geom.models.base_gnn import (
        Equivariant3DGNN as EGNN,
        Equivariant3DInteractionBlock as EGNNLayer,
    )
    EGNNModelConfig = GNNModelConfig  # type: ignore[misc,assignment]


def compute_forces(model: Base3DGNN, data: Any) -> GNNForceOutput:
    """Compute analytical interatomic forces as negative energy gradient [D]."""
    pos, _, _, _, _ = extract_gnn_inputs(data)
    pos_grad = pos.clone().detach().requires_grad_(True)
    if isinstance(data, dict):
        data_grad = dict(data)
        data_grad["pos"] = pos_grad
    else:
        data_grad = copy.copy(data)
        setattr(data_grad, "pos", pos_grad)

    with torch.enable_grad():
        out = model(data_grad)
        energy = out.energy
        grad_outputs = torch.autograd.grad(
            outputs=energy.sum(),
            inputs=pos_grad,
            create_graph=model.training,
            retain_graph=model.training,
            allow_unused=True,
        )
        if grad_outputs[0] is not None:
            forces = -grad_outputs[0]
        else:
            forces = torch.zeros_like(pos_grad)

    return GNNForceOutput(
        energy=energy,
        forces=forces,
        atomic_energies=out.atomic_energies,
        pos_updated=out.pos_updated,
        metadata=out.metadata,
    )


def generate_random_o3_reflection(
    dtype: torch.dtype = torch.float32,
    device: Optional[Union[str, torch.device]] = None,
    seed: Optional[int] = None,
) -> torch.Tensor:
    """Generate a random improper orthogonal matrix in O(3) with det = -1.0 [D]."""
    r_so3 = generate_random_so3_rotation(dtype=dtype, device=device, seed=seed)
    # Apply parity reflection along z-axis
    reflection = torch.tensor(
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, -1.0]],
        dtype=dtype,
        device=r_so3.device,
    )
    return torch.matmul(reflection, r_so3)


# ==============================================================================
# Authentic Molecular Fixtures (Zero-Mock Mandate)
# ==============================================================================

@pytest.fixture
def water_molecule() -> Dict[str, Any]:
    """Authentic water (H2O, C2v symmetry) equilibrium Cartesian geometry [M]."""
    pos = torch.tensor(
        [
            [0.0000, 0.0000, 0.1173],    # O
            [0.0000, 0.7572, -0.4692],   # H1
            [0.0000, -0.7572, -0.4692],  # H2
        ],
        dtype=torch.float32,
    )
    z = torch.tensor([8, 1, 1], dtype=torch.long)
    symbols = ["O", "H", "H"]
    return {"pos": pos, "z": z, "symbols": symbols, "name": "water"}


@pytest.fixture
def methane_molecule() -> Dict[str, Any]:
    """Authentic methane (CH4, Td symmetry) equilibrium Cartesian geometry [M]."""
    pos = torch.tensor(
        [
            [0.0000, 0.0000, 0.0000],    # C
            [0.6276, 0.6276, 0.6276],    # H1
            [-0.6276, -0.6276, 0.6276],  # H2
            [-0.6276, 0.6276, -0.6276],  # H3
            [0.6276, -0.6276, -0.6276],  # H4
        ],
        dtype=torch.float32,
    )
    z = torch.tensor([6, 1, 1, 1, 1], dtype=torch.long)
    symbols = ["C", "H", "H", "H", "H"]
    return {"pos": pos, "z": z, "symbols": symbols, "name": "methane"}


@pytest.fixture
def benzene_molecule() -> Dict[str, Any]:
    """Authentic benzene (C6H6, D6h symmetry) planar planar ring geometry [M]."""
    pos = torch.tensor(
        [
            [0.0000, 1.3970, 0.0000],    # C1
            [1.2098, 0.6985, 0.0000],    # C2
            [1.2098, -0.6985, 0.0000],   # C3
            [0.0000, -1.3970, 0.0000],   # C4
            [-1.2098, -0.6985, 0.0000],  # C5
            [-1.2098, 0.6985, 0.0000],   # C6
            [0.0000, 2.4810, 0.0000],    # H1
            [2.1486, 1.2405, 0.0000],    # H2
            [2.1486, -1.2405, 0.0000],   # H3
            [0.0000, -2.4810, 0.0000],   # H4
            [-2.1486, -1.2405, 0.0000],  # H5
            [-2.1486, 1.2405, 0.0000],   # H6
        ],
        dtype=torch.float32,
    )
    z = torch.tensor([6, 6, 6, 6, 6, 6, 1, 1, 1, 1, 1, 1], dtype=torch.long)
    symbols = ["C", "C", "C", "C", "C", "C", "H", "H", "H", "H", "H", "H"]
    return {"pos": pos, "z": z, "symbols": symbols, "name": "benzene"}


@pytest.fixture
def ethanol_molecule() -> Dict[str, Any]:
    """Authentic ethanol (C2H6O) staggered conformer Cartesian geometry [M]."""
    pos = torch.tensor(
        [
            [-1.1879, -0.3829, 0.0000],  # C1
            [0.0000, 0.5526, 0.0000],    # C2
            [1.1867, -0.2472, 0.0000],   # O
            [-1.2467, -1.0202, 0.8856],  # H1
            [-1.2467, -1.0202, -0.8856], # H2
            [-2.0685, 0.2644, 0.0000],   # H3
            [0.0243, 1.1963, 0.8837],    # H4
            [0.0243, 1.1963, -0.8837],   # H5
            [1.9237, 0.3685, 0.0000],    # H6 (hydroxyl)
        ],
        dtype=torch.float32,
    )
    z = torch.tensor([6, 6, 8, 1, 1, 1, 1, 1, 1], dtype=torch.long)
    symbols = ["C", "C", "O", "H", "H", "H", "H", "H", "H"]
    return {"pos": pos, "z": z, "symbols": symbols, "name": "ethanol"}


@pytest.fixture
def uracil_molecule() -> Dict[str, Any]:
    """Authentic uracil (C4H4N2O2) planar pyrimidine base Cartesian geometry [M]."""
    pos = torch.tensor(
        [
            [-1.0820, -0.7100, 0.0000],  # N1
            [-1.1570, 0.6720, 0.0000],   # C2
            [-2.1970, 1.3090, 0.0000],   # O2
            [0.0890, 1.2980, 0.0000],    # N3
            [1.2910, 0.6480, 0.0000],    # C4
            [2.3380, 1.2720, 0.0000],    # O4
            [1.2060, -0.7930, 0.0000],   # C5
            [0.0610, -1.4110, 0.0000],   # C6
            [-1.9420, -1.2330, 0.0000],  # H1
            [0.1340, 2.3080, 0.0000],    # H3
            [2.1270, -1.3600, 0.0000],   # H5
            [0.0380, -2.4930, 0.0000],   # H6
        ],
        dtype=torch.float32,
    )
    z = torch.tensor([7, 6, 8, 7, 6, 8, 6, 6, 1, 1, 1, 1], dtype=torch.long)
    symbols = ["N", "C", "O", "N", "C", "O", "C", "C", "H", "H", "H", "H"]
    return {"pos": pos, "z": z, "symbols": symbols, "name": "uracil"}


@pytest.fixture(params=["water", "methane", "benzene", "ethanol", "uracil"])
def all_molecules(
    request: pytest.FixtureRequest,
    water_molecule: Dict[str, Any],
    methane_molecule: Dict[str, Any],
    benzene_molecule: Dict[str, Any],
    ethanol_molecule: Dict[str, Any],
    uracil_molecule: Dict[str, Any],
) -> Dict[str, Any]:
    """Parametrized fixture providing all 5 real molecular benchmarks [M]."""
    fixtures = {
        "water": water_molecule,
        "methane": methane_molecule,
        "benzene": benzene_molecule,
        "ethanol": ethanol_molecule,
        "uracil": uracil_molecule,
    }
    return fixtures[request.param]


# ==============================================================================
# 1. Fundamental Physical Constants & Provenance Tests
# ==============================================================================

class TestPhysicalConstantsEGNN:
    """Test suite verifying fundamental physical constants and conversion factors."""

    def test_speed_of_light_exact(self) -> None:
        """Verify CODATA speed of light in vacuum is exact [M]."""
        assert SPEED_OF_LIGHT_M_S == 299792458.0

    def test_planck_constant_exact(self) -> None:
        """Verify CODATA Planck constant is exact [M]."""
        assert math.isclose(PLANCK_CONSTANT_J_S, 6.62607015e-34, rel_tol=1e-12)

    def test_boltzmann_constant_exact(self) -> None:
        """Verify CODATA Boltzmann constant in Joules and eV [M]."""
        assert math.isclose(BOLTZMANN_CONSTANT_J_K, 1.380649e-23, rel_tol=1e-12)
        assert math.isclose(BOLTZMANN_CONSTANT_EV_K, 8.617333262145e-5, rel_tol=1e-8)

    def test_hartree_ev_conversion_consistency(self) -> None:
        """Verify Hartree to eV reciprocal consistency: HARTREE_TO_EV * EV_TO_HARTREE == 1 [D]."""
        product = HARTREE_TO_EV * EV_TO_HARTREE
        assert math.isclose(product, 1.0, rel_tol=1e-7)

    def test_hartree_to_kcal_mol(self) -> None:
        """Verify conversion factor 1 Hartree = 627.509... kcal/mol [D]."""
        assert math.isclose(HARTREE_TO_KCAL_MOL, 627.509474, rel_tol=1e-4)


# ==============================================================================
# 2. Dynamic Mendeleev Library Atomic Mass Resolution Tests
# ==============================================================================

class TestDynamicMendeleevMassResolution:
    """Test suite verifying dynamic Mendeleev library atomic mass queries without hardcoding."""

    @pytest.mark.parametrize(
        ("symbol", "z_expected", "approx_mass"),
        [
            ("H", 1, 1.008),
            ("C", 6, 12.011),
            ("N", 7, 14.007),
            ("O", 8, 15.999),
            ("P", 15, 30.974),
            ("S", 16, 32.06),
            ("Cl", 17, 35.45),
        ],
    )
    def test_dynamic_mass_resolution_symbols(
        self, symbol: str, z_expected: int, approx_mass: float
    ) -> None:
        """Verify dynamic mass lookup via Mendeleev matches experimental atomic weights [M]."""
        mass_sym = resolve_dynamic_mass(symbol)
        mass_z = resolve_dynamic_mass(z_expected)
        assert math.isclose(mass_sym, mass_z, rel_tol=1e-6)
        assert math.isclose(mass_sym, approx_mass, rel_tol=0.01)

    def test_get_atomic_masses_tensor(self, ethanol_molecule: Dict[str, Any]) -> None:
        """Verify batch tensor mass extraction for ethanol (C2H6O) [M]."""
        z = ethanol_molecule["z"]
        masses = get_atomic_masses(z)
        assert isinstance(masses, torch.Tensor)
        assert masses.shape == (9,)
        assert masses.dtype == torch.float32
        # C atoms ~ 12.011, O atom ~ 15.999, H atoms ~ 1.008
        assert math.isclose(masses[0].item(), 12.011, rel_tol=1e-2)
        assert math.isclose(masses[2].item(), 15.999, rel_tol=1e-2)
        assert math.isclose(masses[3].item(), 1.008, rel_tol=1e-2)

    def test_center_of_mass_invariance_under_translation(
        self, water_molecule: Dict[str, Any]
    ) -> None:
        """Verify mass-weighted COM translates strictly additively: COM(r + t) = COM(r) + t [D]."""
        pos = water_molecule["pos"]
        z = water_molecule["z"]
        com_orig = compute_center_of_mass(pos, atomic_numbers=z)

        shift = torch.tensor([5.2, -3.1, 8.4], dtype=torch.float32)
        pos_shifted = translate_coordinates(pos, shift)
        com_shifted = compute_center_of_mass(pos_shifted, atomic_numbers=z)

        expected_com = com_orig + shift
        torch.testing.assert_close(com_shifted, expected_com, atol=1e-5, rtol=1e-5)

    def test_moment_of_inertia_rotational_invariance(
        self, methane_molecule: Dict[str, Any]
    ) -> None:
        """Verify eigenvalues of inertia tensor are invariant under SO(3) rotations [D]."""
        pos = methane_molecule["pos"]
        z = methane_molecule["z"]

        i_base = compute_moment_of_inertia_tensor(pos, atomic_numbers=z)
        eigs_base, _ = torch.sort(torch.linalg.eigvalsh(i_base))

        rot = generate_random_so3_rotation()
        pos_rot = rotate_coordinates(pos, rot)
        i_rot = compute_moment_of_inertia_tensor(pos_rot, atomic_numbers=z)
        eigs_rot, _ = torch.sort(torch.linalg.eigvalsh(i_rot))

        torch.testing.assert_close(eigs_base, eigs_rot, atol=1e-4, rtol=1e-4)

    def test_principal_rotational_constants_methane_spherical_top(
        self, methane_molecule: Dict[str, Any]
    ) -> None:
        """Verify methane (Td) behaves as a spherical top: A == B == C [M]."""
        pos = methane_molecule["pos"]
        z = methane_molecule["z"]
        rot_consts = compute_principal_rotational_constants(pos, atomic_numbers=z)
        assert rot_consts.shape == (3,)
        a, b, c = rot_consts[0].item(), rot_consts[1].item(), rot_consts[2].item()
        assert a > 0.0
        assert math.isclose(a, b, rel_tol=1e-3)
        assert math.isclose(b, c, rel_tol=1e-3)


# ==============================================================================
# 3. Pure State Immutability & Geometric Operators Tests
# ==============================================================================

class TestStateImmutabilityEGNN:
    """Test suite ensuring non-destructive functional updates and immutability."""

    def test_translate_coordinates_immutability(self, water_molecule: Dict[str, Any]) -> None:
        """Verify translation creates a new tensor without modifying the original in-place [D]."""
        pos = water_molecule["pos"].clone()
        pos_backup = pos.clone()
        shift = torch.tensor([1.0, 2.0, 3.0], dtype=torch.float32)

        translated = translate_coordinates(pos, shift)

        assert translated is not pos
        torch.testing.assert_close(pos, pos_backup, atol=0.0, rtol=0.0)
        torch.testing.assert_close(translated, pos + shift.view(1, 3), atol=1e-6, rtol=1e-6)

    def test_rotate_coordinates_immutability(self, ethanol_molecule: Dict[str, Any]) -> None:
        """Verify SO(3) rotation creates a new tensor without in-place mutation [D]."""
        pos = ethanol_molecule["pos"].clone()
        pos_backup = pos.clone()
        rot = generate_random_so3_rotation()

        rotated = rotate_coordinates(pos, rot)

        assert rotated is not pos
        torch.testing.assert_close(pos, pos_backup, atol=0.0, rtol=0.0)
        expected = torch.matmul(pos, rot.T)
        torch.testing.assert_close(rotated, expected, atol=1e-6, rtol=1e-6)

    def test_center_coordinates_immutability(self, benzene_molecule: Dict[str, Any]) -> None:
        """Verify coordinate centering produces new tensors leaving originals unchanged [D]."""
        pos = benzene_molecule["pos"].clone()
        pos_backup = pos.clone()

        centered, com = center_coordinates(pos)

        assert centered is not pos
        torch.testing.assert_close(pos, pos_backup, atol=0.0, rtol=0.0)
        assert centered.shape == pos.shape
        assert com.shape == (3,)
        # Centered coordinates mean is zero
        torch.testing.assert_close(centered.mean(dim=0), torch.zeros(3), atol=1e-6, rtol=1e-6)

    def test_apply_coordinate_delta_immutability(self) -> None:
        """Verify apply_coordinate_delta performs pos + delta immutably [D]."""
        pos = torch.randn(4, 3, dtype=torch.float32)
        pos_backup = pos.clone()
        delta = torch.randn(4, 3, dtype=torch.float32)

        updated = apply_coordinate_delta(pos, delta)

        assert updated is not pos
        torch.testing.assert_close(pos, pos_backup, atol=0.0, rtol=0.0)
        torch.testing.assert_close(updated, pos + delta, atol=1e-6, rtol=1e-6)

    def test_so3_rotation_matrix_orthogonality_and_determinant(self) -> None:
        """Verify generated SO(3) matrices have R^T R = I and det(R) = +1.0 [M]."""
        for seed in range(10):
            rot = generate_random_so3_rotation(seed=seed)
            assert rot.shape == (3, 3)
            # Orthogonality
            identity = torch.eye(3, dtype=rot.dtype, device=rot.device)
            r_rt = torch.matmul(rot, rot.T)
            rt_r = torch.matmul(rot.T, rot)
            torch.testing.assert_close(r_rt, identity, atol=1e-5, rtol=1e-5)
            torch.testing.assert_close(rt_r, identity, atol=1e-5, rtol=1e-5)
            # Determinant
            det = torch.linalg.det(rot).item()
            assert math.isclose(det, 1.0, abs_tol=1e-5)

    def test_o3_improper_rotation_determinant(self) -> None:
        """Verify generated O(3) reflection matrices have R^T R = I and det(R) = -1.0 [M]."""
        for seed in range(10):
            refl = generate_random_o3_reflection(seed=seed)
            assert refl.shape == (3, 3)
            identity = torch.eye(3, dtype=refl.dtype, device=refl.device)
            r_rt = torch.matmul(refl, refl.T)
            torch.testing.assert_close(r_rt, identity, atol=1e-5, rtol=1e-5)
            det = torch.linalg.det(refl).item()
            assert math.isclose(det, -1.0, abs_tol=1e-5)


# ==============================================================================
# 4. Pydantic v2 Configuration & Data Contracts Tests
# ==============================================================================

class TestEGNNDataContracts:
    """Test suite validating Pydantic v2 schemas and dataclass containers."""

    def test_egnn_model_config_defaults(self) -> None:
        """Verify default hyperparameter values in EGNNModelConfig [E]."""
        config = EGNNModelConfig()
        assert config.hidden_channels == DEFAULT_HIDDEN_CHANNELS
        assert config.num_layers == DEFAULT_NUM_LAYERS
        assert config.cutoff == DEFAULT_RBF_CUTOFF
        assert config.max_z == DEFAULT_MAX_Z
        assert config.aggr == "sum"
        assert config.activation == "silu"
        assert config.use_forces is True

    def test_egnn_model_config_custom_valid(self) -> None:
        """Verify custom valid configuration parameters."""
        config = EGNNModelConfig(
            hidden_channels=64,
            num_layers=3,
            cutoff=8.0,
            max_z=86,
            aggr="mean",
            activation="relu",
            dropout=0.1,
            energy_weight=1.0,
            force_weight=10.0,
        )
        assert config.hidden_channels == 64
        assert config.num_layers == 3
        assert config.cutoff == 8.0
        assert config.max_z == 86
        assert config.aggr == "mean"
        assert config.activation == "relu"
        assert config.dropout == 0.1

    def test_egnn_model_config_immutability(self) -> None:
        """Verify frozen configuration forbids field mutation."""
        config = EGNNModelConfig()
        with pytest.raises((ValidationError, TypeError)):
            config.hidden_channels = 256  # type: ignore[misc]

    def test_egnn_model_config_rejection_of_invalid_values(self) -> None:
        """Verify schema rejects negative cutoffs, invalid layers, or extra attributes."""
        with pytest.raises(ValidationError):
            EGNNModelConfig(cutoff=-1.0)
        with pytest.raises(ValidationError):
            EGNNModelConfig(num_layers=0)
        with pytest.raises(ValidationError):
            EGNNModelConfig(hidden_channels=4)  # ge=8
        with pytest.raises(ValidationError):
            EGNNModelConfig(invalid_extra_param="unknown")  # extra="forbid"

    def test_conformer_input_contract_valid_fixtures(
        self, all_molecules: Dict[str, Any]
    ) -> None:
        """Verify ConformerInputContract accepts all 5 authentic fixtures [M]."""
        pos = all_molecules["pos"].tolist()
        z = all_molecules["z"].tolist()
        contract = ConformerInputContract(
            num_atoms=len(z),
            atomic_numbers=z,
            positions=pos,
            energy=-76.432,
            forces=[[0.0, 0.0, 0.0] for _ in range(len(z))],
        )
        assert contract.num_atoms == len(z)
        assert len(contract.positions) == len(z)

    def test_conformer_input_contract_dimension_mismatch_fails(self) -> None:
        """Verify ConformerInputContract rejects mismatched positions or atomic numbers."""
        with pytest.raises(ValidationError):
            ConformerInputContract(
                num_atoms=3,
                atomic_numbers=[8, 1],  # len 2 != num_atoms 3
                positions=[[0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            )

    def test_gnn_prediction_contract_validation(self) -> None:
        """Verify GNNPredictionContract validates finite predictions and rejects NaNs [D]."""
        valid = GNNPredictionContract(
            num_graphs=2,
            total_energy=[-15.3, -42.1],
            num_nodes=5,
            forces=[[0.1, -0.2, 0.0] for _ in range(5)],
        )
        assert valid.num_graphs == 2

        with pytest.raises(ValidationError):
            GNNPredictionContract(
                num_graphs=1,
                total_energy=[float("nan")],  # NaN rejected
            )


# ==============================================================================
# 5. Dataclass Output Containers Tests
# ==============================================================================

class TestEGNNOutputContainers:
    """Test suite verifying GNNOutput and GNNForceOutput containers."""

    def test_gnn_output_operations(self) -> None:
        """Verify GNNOutput .to(), .detach(), .clone(), and .as_dict() immutability [D]."""
        energy = torch.tensor([[10.5]], requires_grad=True)
        nodes = torch.randn(3, 64, requires_grad=True)
        pos = torch.randn(3, 3)

        out = GNNOutput(
            energy=energy,
            node_features=nodes,
            pos_updated=pos,
            metadata={"mol": "water"},
        )

        # Indexing
        assert out["energy"] is energy
        assert out["node_features"] is nodes

        # Detach
        out_detached = out.detach()
        assert not out_detached.energy.requires_grad
        assert not out_detached.node_features.requires_grad

        # Clone
        out_cloned = out.clone()
        assert out_cloned.energy is not out.energy
        torch.testing.assert_close(out_cloned.energy, out.energy)

        # Dictionary conversion
        d = out.as_dict()
        assert "energy" in d
        assert "node_features" in d
        assert "pos_updated" in d

    def test_gnn_force_output_operations(self) -> None:
        """Verify GNNForceOutput container methods [D]."""
        energy = torch.tensor([[5.0]])
        forces = torch.randn(4, 3)
        force_out = GNNForceOutput(energy=energy, forces=forces)

        assert force_out["energy"] is energy
        assert force_out["forces"] is forces
        d = force_out.as_dict()
        assert "energy" in d
        assert "forces" in d


# ==============================================================================
# 6. EGNNLayer (Equivariant Message Passing Block) Tests
# ==============================================================================

class TestEGNNLayer:
    """Test suite validating individual EGNNLayer message passing, invariance, and equivariance."""

    def test_layer_initialization_and_forward_shape(self) -> None:
        """Verify EGNNLayer executes forward pass preserving tensor shapes [D]."""
        layer = EGNNLayer(hidden_channels=32)
        n_atoms = 5
        h = torch.randn(n_atoms, 32)
        pos = torch.randn(n_atoms, 3)
        edge_index = torch.tensor([[0, 1, 2, 3], [1, 2, 3, 0]], dtype=torch.long)

        h_new, pos_new = layer(h, pos, edge_index)

        assert h_new.shape == (n_atoms, 32)
        assert pos_new.shape == (n_atoms, 3)
        assert h_new is not h
        assert pos_new is not pos

    def test_layer_isolated_nodes_no_edges(self) -> None:
        """Verify EGNNLayer handles empty edge graph cleanly without error [D]."""
        layer = EGNNLayer(hidden_channels=16)
        h = torch.randn(3, 16)
        pos = torch.randn(3, 3)
        empty_edges = torch.empty((2, 0), dtype=torch.long)

        h_new, pos_new = layer(h, pos, empty_edges)

        torch.testing.assert_close(h_new, h)
        torch.testing.assert_close(pos_new, pos)

    def test_layer_so3_rotation_equivariance_and_invariance(
        self, water_molecule: Dict[str, Any]
    ) -> None:
        """Verify single EGNNLayer guarantees coordinate equivariance and feature invariance under SO(3) [D].

        $$pos_{\\text{new}}(r R^T) = pos_{\\text{new}}(r) R^T$$
        $$h_{\\text{new}}(r R^T) = h_{\\text{new}}(r)$$
        """
        torch.manual_seed(42)
        hidden_dim = 32
        layer = EGNNLayer(hidden_channels=hidden_dim)
        layer.eval()

        pos = water_molecule["pos"]
        n_atoms = pos.size(0)
        h = torch.randn(n_atoms, hidden_dim)

        # Radius graph within molecule
        edge_index, _ = build_radius_graph(pos, cutoff=5.0)

        # Baseline evaluation
        h_out_base, pos_out_base = layer(h, pos, edge_index)

        # Apply random SO(3) rotation
        rot = generate_random_so3_rotation(seed=123)
        pos_rot = rotate_coordinates(pos, rot)
        edge_index_rot, _ = build_radius_graph(pos_rot, cutoff=5.0)

        # Transformed evaluation
        h_out_rot, pos_out_rot = layer(h, pos_rot, edge_index_rot)

        # 1. Feature Invariance: h_new(r R^T) == h_new(r)
        torch.testing.assert_close(h_out_rot, h_out_base, atol=1e-5, rtol=1e-5)

        # 2. Coordinate Equivariance: pos_new(r R^T) == pos_new(r) @ R^T
        expected_pos_rot = rotate_coordinates(pos_out_base, rot)
        torch.testing.assert_close(pos_out_rot, expected_pos_rot, atol=1e-5, rtol=1e-5)

    def test_layer_spatial_translation_equivariance_and_invariance(
        self, ethanol_molecule: Dict[str, Any]
    ) -> None:
        """Verify single EGNNLayer guarantees coordinate equivariance and feature invariance under translation [D].

        $$pos_{\\text{new}}(r + t) = pos_{\\text{new}}(r) + t$$
        $$h_{\\text{new}}(r + t) = h_{\\text{new}}(r)$$
        """
        torch.manual_seed(42)
        hidden_dim = 32
        layer = EGNNLayer(hidden_channels=hidden_dim)
        layer.eval()

        pos = ethanol_molecule["pos"]
        n_atoms = pos.size(0)
        h = torch.randn(n_atoms, hidden_dim)
        edge_index, _ = build_radius_graph(pos, cutoff=5.0)

        h_out_base, pos_out_base = layer(h, pos, edge_index)

        shift = torch.tensor([3.5, -2.1, 7.8], dtype=torch.float32)
        pos_trans = translate_coordinates(pos, shift)
        edge_index_trans, _ = build_radius_graph(pos_trans, cutoff=5.0)

        h_out_trans, pos_out_trans = layer(h, pos_trans, edge_index_trans)

        # Feature Invariance
        torch.testing.assert_close(h_out_trans, h_out_base, atol=1e-5, rtol=1e-5)
        # Coordinate Equivariance
        expected_pos_trans = translate_coordinates(pos_out_base, shift)
        torch.testing.assert_close(pos_out_trans, expected_pos_trans, atol=1e-5, rtol=1e-5)

    def test_layer_o3_parity_reflection_equivariance(
        self, benzene_molecule: Dict[str, Any]
    ) -> None:
        """Verify EGNNLayer coordinate update is equivariant under O(3) parity reflection (det = -1) [D]."""
        torch.manual_seed(42)
        hidden_dim = 32
        layer = EGNNLayer(hidden_channels=hidden_dim)
        layer.eval()

        pos = benzene_molecule["pos"]
        n_atoms = pos.size(0)
        h = torch.randn(n_atoms, hidden_dim)
        edge_index, _ = build_radius_graph(pos, cutoff=5.0)

        h_out_base, pos_out_base = layer(h, pos, edge_index)

        refl = generate_random_o3_reflection(seed=77)
        pos_refl = rotate_coordinates(pos, refl)
        edge_index_refl, _ = build_radius_graph(pos_refl, cutoff=5.0)

        h_out_refl, pos_out_refl = layer(h, pos_refl, edge_index_refl)

        torch.testing.assert_close(h_out_refl, h_out_base, atol=1e-5, rtol=1e-5)
        expected_pos_refl = rotate_coordinates(pos_out_base, refl)
        torch.testing.assert_close(pos_out_refl, expected_pos_refl, atol=1e-5, rtol=1e-5)


# ==============================================================================
# 7. EGNN Full Architecture Execution Tests
# ==============================================================================

class TestEGNNArchitecture:
    """Test suite verifying full EGNN architecture execution across authentic molecular fixtures."""

    @pytest.mark.parametrize("hidden_channels", [32, 64])
    @pytest.mark.parametrize("num_layers", [2, 4])
    @pytest.mark.parametrize("aggr", ["sum", "mean"])
    def test_egnn_instantiation_various_configs(
        self, hidden_channels: int, num_layers: int, aggr: str
    ) -> None:
        """Verify EGNN instantiates cleanly across various hyperparameter settings [E]."""
        config = EGNNModelConfig(
            hidden_channels=hidden_channels,
            num_layers=num_layers,
            aggr=aggr,
        )
        model = EGNN(config)
        assert isinstance(model, nn.Module)
        assert model.get_num_parameters() > 0
        assert model.get_dtype() == torch.float32

    def test_egnn_forward_all_fixtures(self, all_molecules: Dict[str, Any]) -> None:
        """Verify EGNN forward pass produces finite, correctly shaped GNNOutput across all 5 molecules [M]."""
        torch.manual_seed(0)
        config = EGNNModelConfig(hidden_channels=32, num_layers=2, cutoff=6.0)
        model = EGNN(config)
        model.eval()

        out = model(all_molecules)

        assert isinstance(out, GNNOutput)
        assert out.energy.shape == (1, 1)
        assert torch.isfinite(out.energy).all()
        assert out.atomic_energies is not None
        assert out.atomic_energies.shape == (all_molecules["pos"].size(0), 1)
        assert out.node_features is not None
        assert out.node_features.shape == (all_molecules["pos"].size(0), 32)
        assert out.pos_updated is not None
        assert out.pos_updated.shape == all_molecules["pos"].shape

    def test_egnn_batched_forward_pass(
        self, water_molecule: Dict[str, Any], methane_molecule: Dict[str, Any]
    ) -> None:
        """Verify multi-molecule batch processing in EGNN [D]."""
        torch.manual_seed(0)
        config = EGNNModelConfig(hidden_channels=32, num_layers=2, cutoff=6.0)
        model = EGNN(config)
        model.eval()

        pos_w, z_w = water_molecule["pos"], water_molecule["z"]
        pos_m, z_m = methane_molecule["pos"], methane_molecule["z"]

        pos_batch = torch.cat([pos_w, pos_m], dim=0)
        z_batch = torch.cat([z_w, z_m], dim=0)
        batch_idx = torch.cat(
            [torch.zeros(pos_w.size(0), dtype=torch.long), torch.ones(pos_m.size(0), dtype=torch.long)]
        )

        batch_dict = {"pos": pos_batch, "z": z_batch, "batch": batch_idx}
        out_batch = model(batch_dict)

        assert out_batch.energy.shape == (2, 1)
        assert torch.isfinite(out_batch.energy).all()

        # Compare single-graph forward predictions
        out_w = model(water_molecule)
        out_m = model(methane_molecule)

        torch.testing.assert_close(out_batch.energy[0:1], out_w.energy, atol=1e-5, rtol=1e-5)
        torch.testing.assert_close(out_batch.energy[1:2], out_m.energy, atol=1e-5, rtol=1e-5)


# ==============================================================================
# 8. Full E(n) / SE(3) Symmetry & Physical Conservation Tests
# ==============================================================================

class TestEGNNPhysicalSymmetries:
    """Test suite rigorously verifying E(n) / SE(3) / O(3) physical symmetries and conservation laws."""

    def test_energy_so3_rotation_invariance(self, all_molecules: Dict[str, Any]) -> None:
        """Verify scalar potential energy is strictly invariant under random SO(3) rotations [M].

        $$E(\\mathbf{r} \\mathbf{R}^T) == E(\\mathbf{r})$$
        """
        torch.manual_seed(42)
        config = EGNNModelConfig(hidden_channels=32, num_layers=3, cutoff=6.0)
        model = EGNN(config)
        model.eval()

        pos = all_molecules["pos"]
        e_base = model(all_molecules).energy.item()

        for seed in [10, 20, 30]:
            rot = generate_random_so3_rotation(seed=seed)
            pos_rot = rotate_coordinates(pos, rot)
            mol_rot = {"pos": pos_rot, "z": all_molecules["z"]}
            e_rot = model(mol_rot).energy.item()

            assert math.isclose(e_base, e_rot, abs_tol=1e-4), (
                f"Energy not invariant under SO(3) for {all_molecules.get('name')}: "
                f"base={e_base}, rot={e_rot}"
            )

    def test_energy_spatial_translation_invariance(self, all_molecules: Dict[str, Any]) -> None:
        """Verify scalar potential energy is strictly invariant under 3D spatial translations [M].

        $$E(\\mathbf{r} + \\mathbf{t}) == E(\\mathbf{r})$$
        """
        torch.manual_seed(42)
        config = EGNNModelConfig(hidden_channels=32, num_layers=3, cutoff=6.0)
        model = EGNN(config)
        model.eval()

        pos = all_molecules["pos"]
        e_base = model(all_molecules).energy.item()

        for shift_vec in [[10.0, -5.0, 3.2], [-50.0, 25.0, -12.0], [100.0, 100.0, 100.0]]:
            shift = torch.tensor(shift_vec, dtype=torch.float32)
            pos_shift = translate_coordinates(pos, shift)
            mol_shift = {"pos": pos_shift, "z": all_molecules["z"]}
            e_shift = model(mol_shift).energy.item()

            assert math.isclose(e_base, e_shift, abs_tol=1e-4), (
                f"Energy not invariant under translation for {all_molecules.get('name')}: "
                f"base={e_base}, shift={e_shift}"
            )

    def test_energy_o3_parity_reflection_invariance(self, all_molecules: Dict[str, Any]) -> None:
        """Verify scalar potential energy is invariant under O(3) parity reflections (det = -1) [M].

        $$E(\\mathbf{r} \\mathbf{R}_{\\text{improper}}^T) == E(\\mathbf{r})$$
        """
        torch.manual_seed(42)
        config = EGNNModelConfig(hidden_channels=32, num_layers=3, cutoff=6.0)
        model = EGNN(config)
        model.eval()

        pos = all_molecules["pos"]
        e_base = model(all_molecules).energy.item()

        for seed in [1, 2, 3]:
            refl = generate_random_o3_reflection(seed=seed)
            pos_refl = rotate_coordinates(pos, refl)
            mol_refl = {"pos": pos_refl, "z": all_molecules["z"]}
            e_refl = model(mol_refl).energy.item()

            assert math.isclose(e_base, e_refl, abs_tol=1e-4), (
                f"Energy not invariant under O(3) reflection for {all_molecules.get('name')}: "
                f"base={e_base}, refl={e_refl}"
            )

    def test_force_so3_rotation_equivariance(self, all_molecules: Dict[str, Any]) -> None:
        """Verify analytical interatomic forces transform equivariantly under SO(3) rotations [D].

        $$\\mathbf{F}(\\mathbf{r} \\mathbf{R}^T) == \\mathbf{F}(\\mathbf{r}) \\mathbf{R}^T$$
        """
        torch.manual_seed(42)
        config = EGNNModelConfig(hidden_channels=32, num_layers=3, cutoff=6.0)
        model = EGNN(config)
        model.eval()

        pos = all_molecules["pos"]
        force_out_base = compute_forces(model, all_molecules)
        f_base = force_out_base.forces.detach()

        rot = generate_random_so3_rotation(seed=99)
        pos_rot = rotate_coordinates(pos, rot)
        mol_rot = {"pos": pos_rot, "z": all_molecules["z"]}

        force_out_rot = compute_forces(model, mol_rot)
        f_rot = force_out_rot.forces.detach()

        expected_f_rot = rotate_coordinates(f_base, rot)
        torch.testing.assert_close(
            f_rot, expected_f_rot, atol=1e-4, rtol=1e-4,
            msg=lambda msg: f"Forces not SO(3) equivariant on {all_molecules.get('name')}: {msg}"
        )

    def test_force_spatial_translation_equivariance(self, all_molecules: Dict[str, Any]) -> None:
        """Verify analytical interatomic forces are strictly invariant to translation [D].

        $$\\mathbf{F}(\\mathbf{r} + \\mathbf{t}) == \\mathbf{F}(\\mathbf{r})$$
        """
        torch.manual_seed(42)
        config = EGNNModelConfig(hidden_channels=32, num_layers=3, cutoff=6.0)
        model = EGNN(config)
        model.eval()

        pos = all_molecules["pos"]
        force_out_base = compute_forces(model, all_molecules)
        f_base = force_out_base.forces.detach()

        shift = torch.tensor([8.3, -12.4, 5.5], dtype=torch.float32)
        pos_shift = translate_coordinates(pos, shift)
        mol_shift = {"pos": pos_shift, "z": all_molecules["z"]}

        force_out_shift = compute_forces(model, mol_shift)
        f_shift = force_out_shift.forces.detach()

        torch.testing.assert_close(
            f_shift, f_base, atol=1e-4, rtol=1e-4,
            msg=lambda msg: f"Forces not translation invariant on {all_molecules.get('name')}: {msg}"
        )

    def test_force_o3_parity_reflection_equivariance(self, all_molecules: Dict[str, Any]) -> None:
        """Verify analytical interatomic forces transform equivariantly under O(3) reflection [D].

        $$\\mathbf{F}(\\mathbf{r} \\mathbf{R}_{\\text{improper}}^T) == \\mathbf{F}(\\mathbf{r}) \\mathbf{R}_{\\text{improper}}^T$$
        """
        torch.manual_seed(42)
        config = EGNNModelConfig(hidden_channels=32, num_layers=3, cutoff=6.0)
        model = EGNN(config)
        model.eval()

        pos = all_molecules["pos"]
        force_out_base = compute_forces(model, all_molecules)
        f_base = force_out_base.forces.detach()

        refl = generate_random_o3_reflection(seed=55)
        pos_refl = rotate_coordinates(pos, refl)
        mol_refl = {"pos": pos_refl, "z": all_molecules["z"]}

        force_out_refl = compute_forces(model, mol_refl)
        f_refl = force_out_refl.forces.detach()

        expected_f_refl = rotate_coordinates(f_base, refl)
        torch.testing.assert_close(
            f_refl, expected_f_refl, atol=1e-4, rtol=1e-4,
            msg=lambda msg: f"Forces not O(3) equivariant on {all_molecules.get('name')}: {msg}"
        )

    def test_net_force_conservation_zero_sum(self, all_molecules: Dict[str, Any]) -> None:
        """Verify net interatomic force is conserved (zero sum) for isolated molecules [M].

        $$\\sum_{i=1}^N \\mathbf{F}_i = \\mathbf{0}$$
        """
        torch.manual_seed(42)
        config = EGNNModelConfig(hidden_channels=32, num_layers=3, cutoff=8.0)
        model = EGNN(config)
        model.eval()

        force_out = compute_forces(model, all_molecules)
        net_force = force_out.forces.sum(dim=0)  # [3]
        net_norm = torch.norm(net_force, p=2).item()

        assert net_norm < 1e-4, (
            f"Net force not conserved on {all_molecules.get('name')}: "
            f"norm={net_norm}, vector={net_force.tolist()}"
        )

    def test_coordinate_update_se3_equivariance(self, all_molecules: Dict[str, Any]) -> None:
        """Verify updated coordinates from full EGNN transform equivariantly under SE(3) [D].

        $$\\mathbf{r}'(\\mathbf{r} \\mathbf{R}^T + \\mathbf{t}) == \\mathbf{r}'(\\mathbf{r}) \\mathbf{R}^T + \\mathbf{t}$$
        """
        torch.manual_seed(42)
        config = EGNNModelConfig(hidden_channels=32, num_layers=3, cutoff=6.0)
        model = EGNN(config)
        model.eval()

        pos = all_molecules["pos"]
        out_base = model(all_molecules)
        pos_up_base = out_base.pos_updated

        assert pos_up_base is not None

        rot = generate_random_so3_rotation(seed=88)
        shift = torch.tensor([2.0, -4.0, 1.5], dtype=torch.float32)
        pos_trans = rotate_coordinates(pos, rot) + shift.view(1, 3)
        mol_trans = {"pos": pos_trans, "z": all_molecules["z"]}

        out_trans = model(mol_trans)
        pos_up_trans = out_trans.pos_updated

        assert pos_up_trans is not None

        expected_pos_up_trans = rotate_coordinates(pos_up_base, rot) + shift.view(1, 3)
        torch.testing.assert_close(
            pos_up_trans, expected_pos_up_trans, atol=1e-4, rtol=1e-4,
            msg=lambda msg: f"Coordinate updates not SE(3) equivariant on {all_molecules.get('name')}: {msg}"
        )

    def test_verify_se3_equivariance_engine_helper(self, water_molecule: Dict[str, Any]) -> None:
        """Verify verify_se3_equivariance automated engine reports complete pass [D]."""
        torch.manual_seed(42)
        config = EGNNModelConfig(hidden_channels=32, num_layers=2, cutoff=6.0)
        model = EGNN(config)

        report = verify_se3_equivariance(model, water_molecule, atol=1e-4)

        assert isinstance(report, dict)
        assert report["energy_invariant"] is True
        assert report["force_equivariant"] is True
        assert report["forces_conserved"] is True
        assert report["coord_equivariant"] is True


# ==============================================================================
# 9. Autograd Backpropagation & Force Computation Tests
# ==============================================================================

class TestEGNNAutogradAndForces:
    """Test suite verifying analytical gradient derivation, finite difference checks, and training autograd."""

    def test_finite_difference_vs_autograd_forces(self, water_molecule: Dict[str, Any]) -> None:
        """Verify autograd analytical forces match numerical finite difference derivatives [D].

        $$F_{i, \\alpha}^{\\text{num}} \\approx -\\frac{E(r + \\epsilon e_{i, \\alpha}) - E(r - \\epsilon e_{i, \\alpha})}{2 \\epsilon}$$
        """
        torch.manual_seed(123)
        config = EGNNModelConfig(hidden_channels=32, num_layers=2, cutoff=6.0)
        model = EGNN(config)
        model.eval()

        pos = water_molecule["pos"]
        z = water_molecule["z"]
        eps = 1e-3  # Finite difference step

        # Analytical forces
        force_out = compute_forces(model, water_molecule)
        analytical_forces = force_out.forces.detach()

        # Numerical forces
        numerical_forces = torch.zeros_like(pos)
        n_atoms = pos.size(0)

        for i in range(n_atoms):
            for alpha in range(3):
                # Plus perturbation
                pos_plus = pos.clone()
                pos_plus[i, alpha] += eps
                e_plus = model({"pos": pos_plus, "z": z}).energy.item()

                # Minus perturbation
                pos_minus = pos.clone()
                pos_minus[i, alpha] -= eps
                e_minus = model({"pos": pos_minus, "z": z}).energy.item()

                numerical_forces[i, alpha] = -(e_plus - e_minus) / (2.0 * eps)

        torch.testing.assert_close(
            analytical_forces, numerical_forces, atol=2e-3, rtol=2e-2,
            msg=lambda msg: f"Analytical forces diverge from numerical finite differences: {msg}"
        )

    def test_parameter_gradient_backprop(self, methane_molecule: Dict[str, Any]) -> None:
        """Verify backpropagation produces valid gradients for all trainable parameters [D]."""
        config = EGNNModelConfig(hidden_channels=32, num_layers=2, cutoff=6.0)
        model = EGNN(config)
        model.train()

        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
        optimizer.zero_grad()

        force_out = compute_forces(model, methane_molecule)
        energy_pred = force_out.energy
        pos_pred = force_out.pos_updated

        # Target ground truth values for loss backpropagation
        target_energy = torch.tensor([[ -40.5 ]], dtype=torch.float32)
        target_pos = torch.randn_like(pos_pred)

        loss_e = F.mse_loss(energy_pred, target_energy)
        loss_pos = F.mse_loss(pos_pred, target_pos)
        total_loss = loss_e + loss_pos

        total_loss.backward()

        # Verify all parameters have non-zero, finite gradients
        has_grads = False
        for name, param in model.named_parameters():
            if param.requires_grad:
                assert param.grad is not None, f"Parameter {name} has None gradient"
                assert torch.isfinite(param.grad).all(), f"Parameter {name} has NaN/Inf gradient"
                if param.grad.abs().sum().item() > 0:
                    has_grads = True

        assert has_grads, "No parameters received non-zero gradients"

        optimizer.step()


# ==============================================================================
# 10. Robustness, Single Atom & Extreme Edge Cases Tests
# ==============================================================================

class TestEGNNExtremeCases:
    """Test suite verifying single-atom graphs, disconnected nodes, and extreme geometries."""

    def test_single_isolated_atom(self) -> None:
        """Verify EGNN handles single isolated atom (N=1, E=0) without crash [D]."""
        config = EGNNModelConfig(hidden_channels=16, num_layers=2, cutoff=5.0)
        model = EGNN(config)
        model.eval()

        single_atom = {
            "pos": torch.tensor([[0.0, 0.0, 0.0]], dtype=torch.float32),
            "z": torch.tensor([10], dtype=torch.long),  # Neon
        }

        out = model(single_atom)
        assert out.energy.shape == (1, 1)
        assert torch.isfinite(out.energy).all()

        force_out = compute_forces(model, single_atom)
        assert force_out.forces.shape == (1, 3)
        # Single atom force should be identically zero
        torch.testing.assert_close(force_out.forces, torch.zeros(1, 3), atol=1e-5, rtol=1e-5)

    def test_diatomic_molecule_potential_curve(self) -> None:
        """Verify EGNN on diatomic N2 molecule at varying interatomic separations [M]."""
        config = EGNNModelConfig(hidden_channels=32, num_layers=2, cutoff=5.0)
        model = EGNN(config)
        model.eval()

        distances = [0.8, 1.1, 1.5, 2.0, 3.0]
        energies: List[float] = []

        for d in distances:
            diatomic = {
                "pos": torch.tensor([[0.0, 0.0, 0.0], [0.0, 0.0, d]], dtype=torch.float32),
                "z": torch.tensor([7, 7], dtype=torch.long),  # N2
            }
            out = model(diatomic)
            energies.append(out.energy.item())

        # All energies must be finite
        assert all(math.isfinite(e) for e in energies)

    def test_deterministic_reproducibility(self, ethanol_molecule: Dict[str, Any]) -> None:
        """Verify identical predictions when initialized with same random seed [D]."""
        torch.manual_seed(999)
        config1 = EGNNModelConfig(hidden_channels=32, num_layers=2)
        model1 = EGNN(config1)
        model1.eval()
        out1 = model1(ethanol_molecule)

        torch.manual_seed(999)
        config2 = EGNNModelConfig(hidden_channels=32, num_layers=2)
        model2 = EGNN(config2)
        model2.eval()
        out2 = model2(ethanol_molecule)

        torch.testing.assert_close(out1.energy, out2.energy, atol=0.0, rtol=0.0)
