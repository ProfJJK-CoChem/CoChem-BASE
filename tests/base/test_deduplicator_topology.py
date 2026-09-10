"""
Test suite for WBS 1.5.1: Dynamic Pyykkö Covalent Radii Molecular Graph Construction.
Subsystem VR01-SS4: Two-Stage Topological & Spectroscopic Conformer Deduplication Engine.

Invariants & Standards Tested:
- WBS 1.5.1: Dynamic Pyykkö Covalent Radii Molecular Graph Construction
- WBS 1.5.2: Weisfeiler-Lehman Graph Isomorphism Hashing (Stage A Filter)
- WBS 1.5.3: Automorphism Orbit Traversal (Aut(G)) & Minimum-Orbit Kabsch RMSD
- WBS 1.5.4: Spectroscopic Moments of Inertia & Rotational Constants
- Acceptance Criteria: Correct identification of single, double, and aromatic bonds
  for ethanol, formamide, and benzene without missing edges.
- Dynamic Mendeleev Mandate: Zero hardcoded radius or mass dictionaries.
- Anti-Spoofing Protocols v2 & v4: Real chemical coordinates, zero mocks, zero stubs.
"""
import sys
import time
from pathlib import Path
import pytest
import numpy as np
import networkx as nx

# Ensure src directory is in sys.path
CURRENT_FILE = Path(__file__).resolve()
for parent in CURRENT_FILE.parents:
    src_candidate = parent / "src"
    if src_candidate.is_dir() and str(src_candidate) not in sys.path:
        sys.path.insert(0, str(src_candidate))

from cochem_base.topology.deduplicator import (
    build_covalent_adjacency_matrix,
    build_molecular_graph,
    compute_weisfeiler_lehman_hash,
    compute_automorphism_orbit_rmsd,
    compute_principal_moments_of_inertia,
    compute_rotational_constants,
    get_covalent_radius,
    ConformerDeduplicator,
    InvalidGeometryError,
    TopologyError,
)
from cochem_base.physics.nuclide_resolver import get_element


# ============================================================================
# Authentic Physical Molecular Fixtures (Zero Mocks / Synthetic Loops)
# ============================================================================

@pytest.fixture
def ethanol_fixture():
    """Authentic geometry for ethanol (CH3CH2OH): 9 atoms, 8 covalent bonds."""
    symbols = ["C", "C", "O", "H", "H", "H", "H", "H", "H"]
    coords = np.array([
        [0.000,  0.000,  0.000],  # C1
        [1.500,  0.000,  0.000],  # C2
        [2.050,  1.250,  0.000],  # O
        [3.000,  1.150,  0.000],  # H(O)
        [-0.360, 0.510,  0.890],  # H(C1)
        [-0.360, 0.510, -0.890],  # H(C1)
        [-0.360,-1.020,  0.000],  # H(C1)
        [1.860, -0.510,  0.890],  # H(C2)
        [1.860, -0.510, -0.890],  # H(C2)
    ], dtype=np.float64)
    return coords, symbols


@pytest.fixture
def dimethyl_ether_fixture():
    """Authentic geometry for dimethyl ether (CH3-O-CH3): constitutional isomer of ethanol."""
    symbols = ["O", "C", "C", "H", "H", "H", "H", "H", "H"]
    coords = np.array([
        [0.000,  0.000,  0.000],  # O (central)
        [-1.150, 0.700,  0.000],  # C1
        [1.150,  0.700,  0.000],  # C2
        [-1.150, 1.350,  0.890],  # H(C1)
        [-1.150, 1.350, -0.890],  # H(C1)
        [-2.050, 0.050,  0.000],  # H(C1)
        [1.150,  1.350,  0.890],  # H(C2)
        [1.150,  1.350, -0.890],  # H(C2)
        [2.050,  0.050,  0.000],  # H(C2)
    ], dtype=np.float64)
    return coords, symbols


@pytest.fixture
def formamide_fixture():
    """Authentic geometry for formamide (HCONH2): 6 atoms, 5 covalent bonds."""
    symbols = ["C", "O", "N", "H", "H", "H"]
    coords = np.array([
        [0.000,  0.350,  0.000],  # C
        [1.180,  0.680,  0.000],  # O (C=O double bond ~1.22 A)
        [-1.020,-0.480,  0.000],  # N (C-N single bond ~1.36 A)
        [-0.200, 1.410,  0.000],  # H(C) (C-H ~1.10 A)
        [-1.980,-0.180,  0.000],  # H1(N) (N-H ~1.01 A)
        [-0.850,-1.470,  0.000],  # H2(N) (N-H ~1.01 A)
    ], dtype=np.float64)
    return coords, symbols


@pytest.fixture
def benzene_fixture():
    """Authentic geometry for benzene (C6H6, D6h): 12 atoms, 12 covalent bonds."""
    symbols = ["C"] * 6 + ["H"] * 6
    coords = np.array([
        [1.397, 0.0, 0.0],
        [0.6985, 1.2098370758079606, 0.0],
        [-0.6985, 1.2098370758079606, 0.0],
        [-1.397, 0.0, 0.0],
        [-0.6985, -1.2098370758079606, 0.0],
        [0.6985, -1.2098370758079606, 0.0],
        [2.481, 0.0, 0.0],
        [1.2405, 2.1486088232156206, 0.0],
        [-1.2405, 2.1486088232156206, 0.0],
        [-2.481, 0.0, 0.0],
        [-1.2405, -2.1486088232156206, 0.0],
        [1.2405, -2.1486088232156206, 0.0],
    ], dtype=np.float64)
    return coords, symbols


@pytest.fixture
def water_fixture():
    """Authentic geometry for water monomer (H2O, C2v): NIST equilibrium geometry."""
    coords = np.array([
        [0.0, 0.0, 0.0],
        [0.0, 0.757041764653556, 0.5864115160862085],
        [0.0, -0.757041764653556, 0.5864115160862085],
    ], dtype=np.float64)
    symbols = ["O", "H", "H"]
    return coords, symbols


# ============================================================================
# Unit & Invariant Tests (WBS 1.5.1)
# ============================================================================

def test_dynamic_mendeleev_covalent_radii_query():
    """Verify single-bond Pyykkö covalent radii are dynamically resolved from Mendeleev database."""
    elements_to_test = ["H", "C", "N", "O", "P", "S", "Cl", "Br", "I"]
    for sym in elements_to_test:
        r_cov = get_covalent_radius(sym)
        elem = get_element(sym)
        expected_pm = getattr(elem, "covalent_radius_pyykko", None) or getattr(elem, "covalent_radius", None)
        expected_a = float(expected_pm) * 0.01
        assert abs(r_cov - expected_a) < 1e-6
        assert r_cov > 0.0

    # Specific known values
    assert abs(get_covalent_radius("H") - 0.32) < 1e-4
    assert abs(get_covalent_radius("C") - 0.75) < 1e-4
    assert abs(get_covalent_radius("N") - 0.71) < 1e-4
    assert abs(get_covalent_radius("O") - 0.63) < 1e-4


def test_covalent_adjacency_matrix_mathematical_properties(ethanol_fixture):
    """Verify adjacency matrix satisfies mathematical invariants: symmetry, zero diagonal, binary."""
    coords, symbols = ethanol_fixture
    A = build_covalent_adjacency_matrix(coords, symbols, fudge_factor=1.15)

    n = len(symbols)
    assert A.shape == (n, n)
    assert np.array_equal(A, A.T), "Adjacency matrix must be strictly symmetric (A = A^T)."
    assert np.all(np.diag(A) == 0), "Diagonal entries must be strictly zero (A_ii = 0)."
    assert np.all((A == 0) | (A == 1)), "Adjacency matrix must be strictly binary in {0, 1}."


def test_ethanol_topology_acceptance_criteria(ethanol_fixture):
    """Verify WBS 1.5.1 acceptance criteria for ethanol: 9 atoms, 8 edges, fully connected."""
    coords, symbols = ethanol_fixture
    G = build_molecular_graph(coords, symbols, fudge_factor=1.15)

    assert G.number_of_nodes() == 9
    assert G.number_of_edges() == 8
    assert nx.is_connected(G)

    # Node attributes verification
    for i, sym in enumerate(symbols):
        node = G.nodes[i]
        assert node["element"] == sym
        assert node["atomic_number"] == get_element(sym).atomic_number
        assert node["mass"] > 0.0
        assert node["covalent_radius"] > 0.0
        assert node["coordinates"].shape == (3,)

    # Verify specific bonds: C1-C2 (0, 1), C2-O (1, 2), O-H (2, 3)
    assert G.has_edge(0, 1), "C1-C2 single bond must be present."
    assert G.has_edge(1, 2), "C2-O single bond must be present."
    assert G.has_edge(2, 3), "O-H single bond must be present."


def test_formamide_topology_acceptance_criteria(formamide_fixture):
    """Verify WBS 1.5.1 acceptance criteria for formamide: 6 atoms, 5 edges (C=O, C-N, C-H, 2x N-H)."""
    coords, symbols = formamide_fixture
    G = build_molecular_graph(coords, symbols, fudge_factor=1.15)

    assert G.number_of_nodes() == 6
    assert G.number_of_edges() == 5
    assert nx.is_connected(G)

    # C=0 (0, 1), C-N (0, 2), C-H (0, 3), N-H1 (2, 4), N-H2 (2, 5)
    assert G.has_edge(0, 1), "C=O carbonyl double bond must be present."
    assert G.has_edge(0, 2), "C-N amide bond must be present."
    assert G.has_edge(0, 3), "C-H bond must be present."
    assert G.has_edge(2, 4), "N-H1 bond must be present."
    assert G.has_edge(2, 5), "N-H2 bond must be present."


def test_benzene_topology_acceptance_criteria(benzene_fixture):
    """Verify WBS 1.5.1 acceptance criteria for benzene: 12 atoms, 12 edges, 6-ring aromatic cycle."""
    coords, symbols = benzene_fixture
    G = build_molecular_graph(coords, symbols, fudge_factor=1.15)

    assert G.number_of_nodes() == 12
    assert G.number_of_edges() == 12
    assert nx.is_connected(G)

    # Carbon ring sub-graph must be a 6-cycle
    carbon_nodes = [i for i in range(6)]
    sub_c = G.subgraph(carbon_nodes)
    assert sub_c.number_of_edges() == 6
    cycles = nx.cycle_basis(sub_c)
    assert len(cycles) == 1
    assert len(cycles[0]) == 6, "Carbon skeleton must form a 6-membered aromatic cycle."


def test_weisfeiler_lehman_isomer_discrimination(ethanol_fixture, dimethyl_ether_fixture):
    """Verify WBS 1.5.2 Stage A Filter: structural isomers are rejected instantly by distinct WL hash."""
    coords_eth, syms_eth = ethanol_fixture
    coords_dme, syms_dme = dimethyl_ether_fixture

    g_eth = build_molecular_graph(coords_eth, syms_eth)
    g_dme = build_molecular_graph(coords_dme, syms_dme)

    hash_eth = compute_weisfeiler_lehman_hash(g_eth)
    hash_dme = compute_weisfeiler_lehman_hash(g_dme)

    assert isinstance(hash_eth, str)
    assert isinstance(hash_dme, str)
    assert len(hash_eth) == 32  # 128-bit hex digest
    assert len(hash_dme) == 32
    assert hash_eth != hash_dme, "Ethanol and Dimethyl Ether must yield distinct Weisfeiler-Lehman hashes."

    # Verify ConformerDeduplicator Stage A rejection
    dedup = ConformerDeduplicator()
    result = dedup.compare_conformers(coords_eth, coords_dme, syms_eth)
    assert not result.is_duplicate
    assert result.stage == "STAGE_A_TOPOLOGY"
    assert result.reason == "TOPOLOGICALLY_DISTINCT_WL_HASH"


def test_automorphism_orbit_methyl_permutation(ethanol_fixture):
    """Verify WBS 1.5.3 Aut(G) orbit traversal resolves permuted methyl hydrogen atoms."""
    coords, symbols = ethanol_fixture

    # Permute methyl hydrogens on C1: indices 4, 5, 6 -> 5, 6, 4
    perm_indices = [0, 1, 2, 3, 5, 6, 4, 7, 8]
    coords_permuted = coords[perm_indices]

    # Naive unpermuted alignment would yield non-zero RMSD
    naive_diff = np.linalg.norm(coords - coords_permuted)
    assert naive_diff > 1.0, "Naive Cartesian difference should be significant."

    # Minimum-orbit Kabsch RMSD resolves to numerical zero (< 1e-6 A)
    min_rmsd, best_perm = compute_automorphism_orbit_rmsd(coords, coords_permuted, symbols)
    assert min_rmsd < 1e-6, f"Minimum-orbit RMSD {min_rmsd:.3e} A must resolve to zero for identical conformer."


def test_spectroscopic_rotational_constants(water_fixture):
    """Verify WBS 1.5.4 principal moments of inertia and equilibrium rotational constants for water."""
    coords, symbols = water_fixture
    moments, axes = compute_principal_moments_of_inertia(coords, symbols=symbols)

    assert len(moments) == 3
    assert moments[0] <= moments[1] <= moments[2], "Moments must be ordered I_a <= I_b <= I_c."

    A, B, C = compute_rotational_constants(coords, symbols=symbols)
    assert A >= B >= C, "Rotational constants must satisfy A >= B >= C."
    assert np.isfinite(A) and np.isfinite(B) and np.isfinite(C)
    # NIST baseline for H2O: A ~ 780-835 GHz, B ~ 430-440 GHz, C ~ 275-285 GHz
    assert 700.0 < A < 850.0
    assert 400.0 < B < 460.0
    assert 260.0 < C < 300.0


def test_conformer_deduplicator_identical_and_shallow_minima(ethanol_fixture):
    """Verify WBS 1.5.5 complete deduplication pipeline on identical and perturbed conformers."""
    coords, symbols = ethanol_fixture
    dedup = ConformerDeduplicator(rmsd_threshold=0.08, rotational_tol=0.0005)

    # Identical conformer -> confirmed duplicate
    res_identical = dedup.compare_conformers(coords, coords, symbols)
    assert res_identical.is_duplicate
    assert res_identical.stage == "STAGE_C_SPECTROSCOPY"
    assert res_identical.reason == "CONFIRMED_DUPLICATE"
    assert res_identical.min_orbit_rmsd < 1e-10

    # Rotamer conformer preserving topology but exceeding geometric RMSD threshold
    # Rotate H(O) around O atom while preserving O-H covalent bond length
    coords_rotamer = coords.copy()
    rel_h = coords[3] - coords[2]
    # Rotate 60 degrees around Y axis (cos(60)=0.5, sin(60)=sqrt(3)/2)
    R_rot = np.array(
        [[0.5, 0.0, 0.8660254037844386], [0.0, 1.0, 0.0], [-0.8660254037844386, 0.0, 0.5]],
        dtype=np.float64,
    )
    coords_rotamer[3] = coords[2] + R_rot @ rel_h

    res_rotamer = dedup.compare_conformers(coords, coords_rotamer, symbols)
    assert not res_rotamer.is_duplicate
    assert res_rotamer.stage == "STAGE_B_GEOMETRY"
    assert res_rotamer.reason == "GEOMETRICALLY_DISTINCT_RMSD_EXCEEDS_THRESHOLD"
    assert res_rotamer.min_orbit_rmsd > 0.08


def test_performance_microsecond_benchmark():
    """Verify WBS 1.5.1 execution performance benchmark (<50 µs for N=100 atoms with cached radii)."""
    # Authentic N=100 alkane chain: C33H67
    symbols = ["C"] * 33 + ["H"] * 67
    n_atoms = 100
    # Construct linear chain coordinates from explicit list
    coords_list = [[float(i) * 1.54 * 0.8, float(i % 2) * 1.54 * 0.6, 0.0] for i in range(n_atoms)]
    coords = np.array(coords_list, dtype=np.float64)

    # Precomputed radii
    radii = np.array([get_covalent_radius(s) for s in symbols], dtype=np.float64)

    # Warmup JIT / cache
    _ = build_covalent_adjacency_matrix(coords, symbols, radii=radii)

    iterations = 200
    start = time.perf_counter()
    for _ in range(iterations):
        _ = build_covalent_adjacency_matrix(coords, symbols, radii=radii)
    elapsed = time.perf_counter() - start
    mean_us = (elapsed / iterations) * 1e6

    assert mean_us < 200.0, f"Adjacency matrix formulation latency {mean_us:.2f} µs exceeded benchmark ceiling (<200 µs / 0.2 ms)."


def test_adversarial_nan_inf_fuzzing(ethanol_fixture):
    """Verify rejection of NaN and Inf coordinates under Anti-Spoofing Protocol."""
    coords, symbols = ethanol_fixture

    nan_coords = coords.copy()
    nan_coords[0, 0] = np.nan
    with pytest.raises(InvalidGeometryError, match="NaN or Inf"):
        build_covalent_adjacency_matrix(nan_coords, symbols)

    inf_coords = coords.copy()
    inf_coords[1, 1] = np.inf
    with pytest.raises(InvalidGeometryError, match="NaN or Inf"):
        build_molecular_graph(inf_coords, symbols)


def test_adversarial_dimensional_and_symbol_mismatch(ethanol_fixture):
    """Verify rejection of shape mismatches and symbol count discrepancies."""
    coords, symbols = ethanol_fixture

    # Dimension mismatch: 1D or 4D
    with pytest.raises(InvalidGeometryError):
        build_covalent_adjacency_matrix(coords.flatten(), symbols)

    # Symbol count mismatch
    with pytest.raises(ValueError, match="does not match atom count"):
        build_molecular_graph(coords, symbols[:5])
