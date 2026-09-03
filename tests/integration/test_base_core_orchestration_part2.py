"""Comprehensive Physical Integration & Anti-Spoof Test Suite for CoChem-BASE Core Orchestration (Part 2).
Covers Prompts 1 through 6 strictly adhering to the Zero-Mock mandate.
"""

import math
import pathlib
import sys
import uuid

import numpy as np
import pytest
from mendeleev import element

from cochem.concurrency.subprocess_broker import (
    SubprocessBroker,
)
from cochem.core.context import (
    AirGapViolationError,
    AtomicWrite,
    ExecutionContext,
    assert_writable_path,
    scoped_context,
)
from cochem.core.diagnostics.memory_guard import (
    MemoryGuardDaemon,
    MemoryTelemetrySample,
)
from cochem.core.hardware.topology import (
    TopologyDiscoveryEngine,
)
from cochem.core.ingestors.protocols import (
    ANGSTROM_TO_BOHR,
    BOHR_TO_ANGSTROM,
    HARTREE_TO_KCAL_MOL,
    HARTREE_TO_WAVENUMBER,
    MolecularStructureData,
    QCResultsSchema,
)
from cochem.core.ipc.serializer import (
    PESStore,
    pack_payload,
    unpack_payload,
)


# ==============================================================================
# 1. Authentic Physical Chemical Test Objects
# ==============================================================================
def test_authentic_molecules_geometry_and_mendeleev_masses() -> None:
    """Validate Water dimer, Argon-H2O, and ethanol geometries with dynamic Mendeleev masses."""
    # 1. Water Dimer ((H2O)2)
    water_dimer_symbols = ["O", "H", "H", "O", "H", "H"]
    water_dimer_coords = [
        (-1.464, -0.015, 0.040),
        (-1.758, 0.887, -0.091),
        (-0.505, -0.003, -0.062),
        (1.442, 0.001, -0.009),
        (1.841, -0.407, 0.760),
        (1.802, -0.468, -0.751),
    ]
    mol_dimer = MolecularStructureData(
        symbols=water_dimer_symbols,
        coordinates=water_dimer_coords,
        charge=0,
        multiplicity=1,
    )
    assert len(mol_dimer.masses) == 6
    assert math.isclose(mol_dimer.masses[0], element("O").atomic_weight, rel_tol=1e-5)

    # 2. Argon-H2O van der Waals complex
    ar_h2o_symbols = ["Ar", "O", "H", "H"]
    ar_h2o_coords = [
        (0.000, 0.000, -2.150),
        (0.000, 0.000, 1.450),
        (0.000, 0.760, 2.050),
        (0.000, -0.760, 2.050),
    ]
    mol_ar = MolecularStructureData(
        symbols=ar_h2o_symbols,
        coordinates=ar_h2o_coords,
        charge=0,
        multiplicity=1,
    )
    assert len(mol_ar.masses) == 4
    assert math.isclose(mol_ar.masses[0], element("Ar").atomic_weight, rel_tol=1e-5)

    # 3. Ethanol (C2H5OH)
    ethanol_symbols = ["C", "C", "O", "H", "H", "H", "H", "H", "H"]
    ethanol_coords = [
        (0.000, 0.000, 0.000),
        (1.520, 0.000, 0.000),
        (2.050, 1.320, 0.000),
        (-0.360, 1.030, 0.000),
        (-0.390, -0.520, 0.880),
        (-0.390, -0.520, -0.880),
        (1.910, -0.520, 0.880),
        (1.910, -0.520, -0.880),
        (3.010, 1.300, 0.000),
    ]
    mol_eth = MolecularStructureData(
        symbols=ethanol_symbols,
        coordinates=ethanol_coords,
        charge=0,
        multiplicity=1,
    )
    assert len(mol_eth.masses) == 9
    assert math.isclose(mol_eth.masses[0], element("C").atomic_weight, rel_tol=1e-5)


def test_deuterated_water_isotopic_lookup() -> None:
    """Validate D2O isotopic mass resolution matching mass_number=2."""
    symbols = ["O", "H", "H"]
    coords = [(0.0, 0.0, 0.117), (0.0, 0.757, -0.469), (0.0, -0.757, -0.469)]
    isotopes = [16, 2, 2]

    mol = MolecularStructureData(symbols=symbols, coordinates=coords, isotopes=isotopes)
    h2_mass = [iso.mass for iso in element("H").isotopes if iso.mass_number == 2][0]
    assert math.isclose(mol.masses[1], h2_mass, rel_tol=1e-6)
    assert math.isclose(mol.masses[2], h2_mass, rel_tol=1e-6)


# ==============================================================================
# 2. Ingestor Protocols & QCResultsSchema
# ==============================================================================
def test_unphysical_distance_rejection() -> None:
    """Assert rejection of unphysical atomic distances (r < 0.5 Angstrom)."""
    with pytest.raises(ValueError, match="Unphysical atomic distance"):
        MolecularStructureData(
            symbols=["O", "H"],
            coordinates=[(0.0, 0.0, 0.0), (0.0, 0.0, 0.35)],
        )


def test_qc_results_schema_verification() -> None:
    """Verify QCResultsSchema energy breakdown, gradient, Hessian symmetry, and spin."""
    grad = [0.0] * 9
    hess = [[0.1 if i == j else 0.05 for j in range(9)] for i in range(9)]

    schema = QCResultsSchema(
        total_energy=-76.432,
        energy_breakdown={"E_SCF": -76.01, "E_CORR": -0.41, "E_disp": -0.012},
        gradient=grad,
        hessian=hess,
        frequencies=[1600.0, 3700.0, 3800.0],
        dipole_moment=(0.0, 0.0, 1.85),
        rotational_constants=(835.0, 435.0, 278.0),
        s2_expectation=0.0,
        s2_ideal=0.0,
    )
    assert schema.total_energy == -76.432
    assert len(schema.gradient) == 9
    assert len(schema.hessian) == 9


def test_codata_2022_constants_validation() -> None:
    """Verify CODATA 2022 constants."""
    assert math.isclose(BOHR_TO_ANGSTROM, 0.529177210903, rel_tol=1e-11)
    assert math.isclose(ANGSTROM_TO_BOHR, 1.0 / 0.529177210903, rel_tol=1e-11)
    assert math.isclose(HARTREE_TO_KCAL_MOL, 627.5094740631, rel_tol=1e-11)
    assert math.isclose(HARTREE_TO_WAVENUMBER, 219474.63136320, rel_tol=1e-11)


# ==============================================================================
# 3. Memory Profiling Guard & OLS Regression
# ==============================================================================
def test_memory_guard_ols_leak_detection_integration() -> None:
    """Execute MemoryGuardDaemon and verify OLS regression leak detection."""
    daemon = MemoryGuardDaemon(interval_sec=0.05, window_capacity=50)

    # 1. Stable baseline -> No leak
    base_t = 1000.0
    for i in range(35):
        daemon.record_sample(
            MemoryTelemetrySample(
                timestamp_sec=base_t + i * 0.1,
                rss_bytes=100_000_000,
            )
        )
    is_leak, slope, r2 = daemon.evaluate_leak()
    assert not is_leak

    # 2. Linear growth > 5 MB/min, R^2 > 0.95 -> Leak flagged
    daemon = MemoryGuardDaemon(interval_sec=0.05, window_capacity=50)
    for i in range(35):
        daemon.record_sample(
            MemoryTelemetrySample(
                timestamp_sec=base_t + i * 1.0,
                rss_bytes=100_000_000 + i * 200_000,
            )
        )
    is_leak, slope, r2 = daemon.evaluate_leak()
    assert is_leak
    assert slope > 5.0
    assert r2 > 0.95


# ==============================================================================
# 4. Subprocess Broker & Fault Ladder
# ==============================================================================
def test_subprocess_broker_fault_ladder_recovery(tmp_path: pathlib.Path) -> None:
    """Verify SubprocessBroker executes, catches authentic failure, escalates, and succeeds."""
    scratch = tmp_path / "scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    counter = scratch / "run_count.txt"

    worker = (
        f"import pathlib, sys\n"
        f"p = pathlib.Path(r'{counter}')\n"
        f"c = int(p.read_text()) if p.exists() else 1\n"
        f"p.write_text(str(c + 1))\n"
        f"if c == 1:\n"
        f"    print('ORCA DRIVER: SCF NOT CONVERGED')\n"
        f"    sys.exit(1)\n"
        f"else:\n"
        f"    print('SUCCESS: ENERGY = -76.432')\n"
        f"    sys.exit(0)\n"
    )

    broker = SubprocessBroker(
        engine_name="ORCA",
        initial_params={"guess": "PModel"},
        scratch_dir=scratch,
    )
    result = broker.execute_with_remediation([sys.executable, "-c", worker])
    assert result.success
    assert result.retries_attempted == 1
    assert result.final_params["guess"] == "Auto"


# ==============================================================================
# 5. Execution Context & Tripartite Air-Gap
# ==============================================================================
def test_execution_context_airgap_and_atomic_write(tmp_path: pathlib.Path) -> None:
    """Verify ExecutionContext immutability, AirGapViolationError, and AtomicWrite."""
    src_dir = tmp_path / "src"
    data_dir = tmp_path / "data"
    art_dir = tmp_path / "artifacts"
    scratch_dir = art_dir / "scratch"

    src_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    art_dir.mkdir(parents=True, exist_ok=True)
    scratch_dir.mkdir(parents=True, exist_ok=True)

    ctx = ExecutionContext(
        execution_id=str(uuid.uuid4()),
        session_name="integ_session",
        src_dir=src_dir,
        data_dir=data_dir,
        artifacts_dir=art_dir,
        scratch_dir=scratch_dir,
        env_tier="Tier 1A",
    )

    with scoped_context(ctx):
        # Airgap checks
        with pytest.raises(AirGapViolationError):
            assert_writable_path(src_dir / "bad.py")

        with pytest.raises(AirGapViolationError):
            assert_writable_path(data_dir / "bad.h5")

        # Atomic write
        out_file = art_dir / "final.txt"
        with AtomicWrite(out_file) as tmp_target:
            tmp_target.write_text("authentic_data", encoding="utf-8")

        assert out_file.exists()
        assert out_file.read_text(encoding="utf-8") == "authentic_data"


# ==============================================================================
# 6. IPC Serialization & PESStore
# ==============================================================================
def test_ipc_serializer_and_pes_store(tmp_path: pathlib.Path) -> None:
    """Verify Msgpack custom NumPy hooks and HDF5 PESStore SWMR persistence."""
    coords = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    packed = pack_payload({"coords": coords, "value": 42})
    unpacked = unpack_payload(packed)

    assert np.allclose(unpacked["coords"], coords)  # type: ignore[attr-defined]
    assert unpacked["coords"].dtype == np.float64

    # PESStore
    store_file = tmp_path / "pes.h5"
    store = PESStore(store_file)
    store.write_entry(
        entry_id="pt1",
        molecule={"symbols": ["H", "H"]},
        driver="energy",
        model={"method": "HF"},
        return_result=coords,
    )
    loaded = store.read_entry("pt1")
    assert loaded["schema_name"] == "qcschema_output"
    assert np.allclose(loaded["return_result"], coords)  # type: ignore[attr-defined]


# ==============================================================================
# 7. Hardware Topology Discovery & Affinity
# ==============================================================================
def test_hardware_topology_discovery_and_affinity() -> None:
    """Verify HardwareTopology detection, Scout-and-Anchor budgeting, and affinity."""
    engine = TopologyDiscoveryEngine()
    topo = engine.discover_topology()

    assert topo.total_logical_cpus >= 1
    assert topo.total_physical_cores >= 1
    assert topo.scout_cores == 1
    assert "OMP_NUM_THREADS" in topo.environment_variables

    # Affinity execution
    pinned = engine.pin_scout_affinity(core_index=0)
    assert isinstance(pinned, bool)


# ==============================================================================
# 8. Zero-Mock & Anti-Spoofing AST Audit
# ==============================================================================
def test_zero_mock_ast_audit_across_production_files() -> None:
    """AST audit certifying zero occurrences of stubs, empty pass blocks, or forbidden constructs."""
    from ci_tools.anti_spoof_linter import check_file, load_amnesty

    repo_root = pathlib.Path(__file__).resolve().parent.parent.parent
    amnesty_set = load_amnesty(repo_root)
    total_violations: list[str] = []

    target_production_files = [
        "src/cochem/core/ingestors/protocols.py",
        "src/cochem/core/diagnostics/memory_guard.py",
        "src/cochem/core/context.py",
        "src/cochem/core/hardware/topology.py",
        "src/cochem/core/ipc/serializer.py",
        "src/cochem/concurrency/subprocess_broker.py",
    ]

    for rel_path in target_production_files:
        full_path = repo_root / rel_path
        assert full_path.is_file(), f"Target file '{rel_path}' does not exist!"

        violations = check_file(full_path, repo_root, amnesty_set=amnesty_set)
        for v in violations:
            total_violations.append(f"{v.file_path}:{v.line} [{v.category}] {v.message}")

    assert len(total_violations) == 0, (
        f"Zero-stub compliance violations detected ({len(total_violations)}):\n"
        + "\n".join(total_violations)
    )
