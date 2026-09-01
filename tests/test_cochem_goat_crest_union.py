"""# zero-stub anti-spoofing engine
Unit tests for cochem_geom.cochem_goat_crest_union adhering to Method Matrix v4 §9B.
"""

import json
import math
import tempfile
from pathlib import Path

import numpy as np
import pytest

from cochem_geom.cochem_goat_crest_union import (
    ConformerData,
    CRESTConfig,
    CRESTRunner,
    GOATConfig,
    GOATCRESTUnionOrchestrator,
    GOATCRESTUnionResult,
    ORCAGOATRunner,
    UnionCoverageDiagnostics,
    UnionFilterConfig,
    compute_boltzmann_weights,
    compute_inertia_tensor,
    get_atomic_mass,
    get_atomic_number,
    get_element_symbol,
    kabsch_align,
    parse_xyz_string,
    read_xyz_ensemble,
    two_stage_deduplicate,
    write_xyz_ensemble,
)


def test_mendeleev_dynamic_mass_resolution():
    """Verify live Mendeleev dynamic mass resolution adhering to Mendeleev Mass Mandate."""
    # Hydrogen
    h_mass = get_atomic_mass("H")
    assert abs(h_mass - 1.008) < 0.01

    # Carbon
    c_mass = get_atomic_mass("C")
    assert abs(c_mass - 12.011) < 0.01

    # Oxygen
    o_mass = get_atomic_mass("O")
    assert abs(o_mass - 15.999) < 0.01

    # Nitrogen
    n_mass = get_atomic_mass("N")
    assert abs(n_mass - 14.007) < 0.01

    assert get_atomic_number("C") == 6
    assert get_atomic_number("O") == 8
    assert get_element_symbol(6) == "C"
    assert get_element_symbol(8) == "O"


def test_inertia_tensor_and_rotational_constants():
    """Verify principal moments of inertia, rotational constants (A >= B >= C), and inertial defect."""
    # Planar water molecule geometry (C2v)
    symbols = ["O", "H", "H"]
    coords = np.array([
        [0.000000, 0.000000, 0.117400],
        [0.000000, 0.757000, -0.469600],
        [0.000000, -0.757000, -0.469600],
    ], dtype=np.float64)

    masses = np.array([get_atomic_mass(s) for s in symbols], dtype=np.float64)
    moments, axes, (a_mhz, b_mhz, c_mhz), delta = compute_inertia_tensor(coords, masses)

    # Moments: Ia <= Ib <= Ic
    assert moments[0] <= moments[1] <= moments[2]

    # Rotational constants: A >= B >= C in MHz
    assert a_mhz >= b_mhz >= c_mhz > 0.0

    # For a strictly planar molecule (all x = 0), inertial defect Delta = Ic - Ia - Ib should be ~0.0
    assert abs(delta) < 1e-5


def test_kabsch_alignment_reflection_ban():
    """Verify Kabsch alignment with strict SO(3) determinant reflection ban."""
    # Geometry 1: Asymmetric 4-atom cluster
    coords1 = np.array([
        [0.0, 0.0, 0.0],
        [1.2, 0.0, 0.0],
        [0.0, 1.4, 0.0],
        [0.0, 0.0, 1.6],
    ], dtype=np.float64)

    # Create a pure rotation + translation
    theta = 0.5
    rot_z = np.array([
        [np.cos(theta), -np.sin(theta), 0.0],
        [np.sin(theta), np.cos(theta), 0.0],
        [0.0, 0.0, 1.0],
    ])
    coords2 = (coords1 @ rot_z.T) + np.array([2.5, -1.0, 3.2])

    aligned, rmsd = kabsch_align(coords2, coords1, enforce_reflection_ban=True)
    assert rmsd < 1e-7

    # Enantiomer reflection (invert z axis)
    coords_enantiomer = coords1.copy()
    coords_enantiomer[:, 2] *= -1.0

    # With reflection ban, enantiomer should have non-zero RMSD
    _, rmsd_chiral = kabsch_align(coords_enantiomer, coords1, enforce_reflection_ban=True)
    assert rmsd_chiral > 0.1


def test_boltzmann_weights_and_entropy():
    """Verify Boltzmann population weighting and conformational entropy calculations."""
    # Three conformers with relative energies: 0.0, 0.5, 1.2 kcal/mol
    energies_kcal = [0.0, 0.5, 1.2]
    weights, s_conf_cal, s_conf_j = compute_boltzmann_weights(energies_kcal, temperature_k=298.15)

    assert len(weights) == 3
    assert abs(sum(weights) - 1.0) < 1e-6
    # Lowest energy conformer has highest population
    assert weights[0] > weights[1] > weights[2]
    # S_conf > 0 for non-degenerate ensemble
    assert s_conf_cal > 0.0
    assert s_conf_j > 0.0
    assert abs(s_conf_j / s_conf_cal - 4.184) < 0.01


def test_two_stage_deduplication():
    """Verify Stage A (RMSD/Ethr) and Stage B (Spectroscopic Bthr) deduplication."""
    symbols = ["O", "H", "H"]
    coords_base = np.array([
        [0.0, 0.0, 0.1174],
        [0.0, 0.7570, -0.4696],
        [0.0, -0.7570, -0.4696],
    ], dtype=np.float64)

    # Conformer 1: Global minimum
    c1 = ConformerData(
        conformer_id="c1",
        symbols=symbols,
        atomic_numbers=[8, 1, 1],
        coordinates=coords_base,
        energy_hartree=-76.4000,
        source_engine="ORCA_GOAT",
    )

    # Conformer 2: Near duplicate of c1 (rotated and shifted, identical energy)
    rot_slight = np.array([
        [0.9999, -0.01, 0.0],
        [0.01, 0.9999, 0.0],
        [0.0, 0.0, 1.0],
    ])
    c2 = ConformerData(
        conformer_id="c2",
        symbols=symbols,
        atomic_numbers=[8, 1, 1],
        coordinates=(coords_base @ rot_slight.T) + 0.001,
        energy_hartree=-76.4000,
        source_engine="CREST",
    )

    # Conformer 3: Distinct geometry (stretched bond, 6.28 kcal/mol higher)
    coords_stretched = coords_base.copy()
    coords_stretched[1, 1] += 0.3
    c3 = ConformerData(
        conformer_id="c3",
        symbols=symbols,
        atomic_numbers=[8, 1, 1],
        coordinates=coords_stretched,
        energy_hartree=-76.3900,
        source_engine="ORCA_GOAT",
    )

    # Conformer 4: Out of energy window (> 12 kcal/mol = > 0.0191 Hartree)
    c4 = ConformerData(
        conformer_id="c4",
        symbols=symbols,
        atomic_numbers=[8, 1, 1],
        coordinates=coords_base + 0.5,
        energy_hartree=-76.3000,  # ~62.75 kcal/mol higher
        source_engine="CREST",
    )

    config = UnionFilterConfig(
        rthr=0.125,
        ethr=0.05,
        ewin=12.0,
        bthr=0.001,
    )

    unique_reps, clusters = two_stage_deduplicate([c1, c2, c3, c4], config)

    # c1 and c2 should merge into one cluster; c3 should be separate; c4 should be filtered out by ewin
    assert len(unique_reps) == 2
    assert unique_reps[0].conformer_id == "c1"
    assert unique_reps[1].conformer_id == "c3"
    assert len(clusters[0]) == 2  # contains c1 and c2


def test_xyz_io_and_conformer_serialization(tmp_path: Path):
    """Verify multi-structure XYZ reading, writing, and parsing."""
    xyz_content = """3
ID=c1 | E=-76.40000000 Eh | dE=0.0000 kcal/mol | Source=ORCA_GOAT
O      0.00000000      0.00000000      0.11740000
H      0.00000000      0.75700000     -0.46960000
H      0.00000000     -0.75700000     -0.46960000
3
ID=c2 | E=-76.38000000 Eh | dE=12.5502 kcal/mol | Source=CREST
O      0.00000000      0.00000000      0.12000000
H      0.00000000      0.80000000     -0.46000000
H      0.00000000     -0.80000000     -0.46000000
"""
    confs = parse_xyz_string(xyz_content)
    assert len(confs) == 2
    assert confs[0].symbols == ["O", "H", "H"]
    assert abs(confs[0].energy_hartree - (-76.4000)) < 1e-6
    assert abs(confs[1].energy_hartree - (-76.3800)) < 1e-6

    # Test writing and reading back
    out_file = tmp_path / "test_ensemble.xyz"
    write_xyz_ensemble(confs, out_file)
    assert out_file.exists()

    reloaded = read_xyz_ensemble(out_file)
    assert len(reloaded) == 2
    assert reloaded[0].symbols == ["O", "H", "H"]


def test_goat_crest_union_orchestrator_pipeline(tmp_path: Path):
    """Verify complete GOATCRESTUnionOrchestrator pipeline execution with synthetic seeds and HDF5 export."""
    seed1_content = """3
ID=seed1 | E=-76.40000000 Eh
O      0.000000      0.000000      0.117400
H      0.000000      0.757000     -0.469600
H      0.000000     -0.757000     -0.469600
"""
    seed2_content = """3
ID=seed2 | E=-76.39000000 Eh
O      0.000000      0.000000      0.120000
H      0.000000      0.780000     -0.450000
H      0.000000     -0.780000     -0.450000
"""
    seed1_file = tmp_path / "seed1.xyz"
    seed2_file = tmp_path / "seed2.xyz"
    seed1_file.write_text(seed1_content, encoding="utf-8")
    seed2_file.write_text(seed2_content, encoding="utf-8")

    out_dir = tmp_path / "union_output"

    orchestrator = GOATCRESTUnionOrchestrator(
        goat_config=GOATConfig(maxen=12.0, n_workers=4),
        crest_config=CRESTConfig(ewin=12.0, threads=4),
        filter_config=UnionFilterConfig(ewin=12.0, rthr=0.125, ethr=0.05, bthr=0.001),
        output_dir=out_dir,
    )

    res = orchestrator.execute_union_pipeline(
        seed_paths=[seed1_file, seed2_file],
        run_mlff_scout=True,
        export_hdf5=True,
    )

    assert isinstance(res, GOATCRESTUnionResult)
    assert res.diagnostics.n_seeds == 2
    assert res.diagnostics.n_union_dedup >= 1
    assert "union_deduplicated_xyz" in res.output_files
    assert "diagnostics_json" in res.output_files
    assert "union_hdf5_pes" in res.output_files
    assert Path(res.output_files["union_deduplicated_xyz"]).exists()
    assert Path(res.output_files["diagnostics_json"]).exists()
    assert Path(res.output_files["union_hdf5_pes"]).exists()
    assert 0.0 <= res.diagnostics.jaccard_similarity <= 1.0
    assert res.diagnostics.union_gain_ratio >= 1.0
    assert res.diagnostics.conformational_entropy_cal_mol_k >= 0.0


def test_hdf5_pes_store_export_and_readback(tmp_path: Path):
    """Verify MolSSI QCSchema compliant HDF5 PES export and round-trip verification."""
    from cochem_geom.cochem_goat_crest_union import export_union_to_hdf5
    from cochem_geom.data.pes_store import PESStore

    coords = np.array([
        [0.0, 0.0, 0.1174],
        [0.0, 0.7570, -0.4696],
        [0.0, -0.7570, -0.4696],
    ], dtype=np.float64)

    conf1 = ConformerData("c1", ["O", "H", "H"], [8, 1, 1], coords, -76.4000, source_engine="GOAT")
    conf2 = ConformerData("c2", ["O", "H", "H"], [8, 1, 1], coords + 0.1, -76.3800, source_engine="CREST")

    h5_file = tmp_path / "test_union_pes.h5"
    exported_path = export_union_to_hdf5([conf1, conf2], h5_file, max_atoms=20)
    assert exported_path is not None
    assert exported_path.exists()

    # Read back through PESStore
    store = PESStore(db_path=exported_path, mode="r")
    assert len(store) == 2

    rec0 = store.read_conformer(0)
    assert rec0["num_atoms"] == 3
    assert list(rec0["atomic_numbers"]) == [8, 1, 1]
    assert abs(rec0["return_energy"] - (-76.4000)) < 1e-6

    rec1 = store.read_conformer(1)
    assert rec1["num_atoms"] == 3
    assert list(rec1["atomic_numbers"]) == [8, 1, 1]
    assert abs(rec1["return_energy"] - (-76.3800)) < 1e-6
    store.close()


def test_orca_goat_runner_deck_generation(tmp_path: Path):
    """Verify Method Matrix §9B.3 Step 2 ORCA GOAT input deck generation."""
    xyz_path = tmp_path / "seed01.xyz"
    xyz_path.write_text("3\nWater\nO 0 0 0\nH 0 0 1\nH 0 1 0\n", encoding="utf-8")

    cfg = GOATConfig(maxen=12.0, conftemp=298.15, confdegen="auto", n_workers=8, gfnuphill=True, gfnff=True)
    runner = ORCAGOATRunner(config=cfg)
    deck = runner.generate_input_deck(xyz_path, charge=0, mult=1)

    assert "! GOAT XTB2 PAL8" in deck
    assert "maxen 12.00" in deck
    assert "conftemp 298.15" in deck
    assert "confdegen auto" in deck
    assert "gfnuphill" in deck
    assert "gfnff" in deck
    assert "* xyzfile 0 1 seed01.xyz" in deck


def test_crest_runner_command_generation():
    """Verify Method Matrix §9B.3 Step 3 CREST NCI command argument construction."""
    cfg = CRESTConfig(nci=True, gfn2=True, ewin=12.0, nocross=True, noreftopo=True, threads=8, niceprint=True)
    runner = CRESTRunner(config=cfg)
    cmd = runner.build_command("input.xyz")

    assert cmd[0] == "crest"
    assert cmd[1] == "input.xyz"
    assert "--nci" in cmd
    assert "--gfn2" in cmd
    assert "--ewin" in cmd
    assert "12.0" in cmd
    assert "--nocross" in cmd
    assert "--noreftopo" in cmd
    assert "-T" in cmd
    assert "8" in cmd
    assert "--niceprint" in cmd

    # Test wscal fallback
    cfg_wscal = CRESTConfig(wscal=0.9)
    runner_wscal = CRESTRunner(config=cfg_wscal)
    cmd_wscal = runner_wscal.build_command("input.xyz")
    assert "--wscal" in cmd_wscal
    assert "0.90" in cmd_wscal


def test_main_cli_execution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify CLI entrypoint main() execution."""
    from cochem_geom.cochem_goat_crest_union import main

    seed_file = tmp_path / "seed_cli.xyz"
    seed_file.write_text("3\nWater\nO 0.0 0.0 0.1174\nH 0.0 0.757 -0.4696\nH 0.0 -0.757 -0.4696\n", encoding="utf-8")
    out_dir = tmp_path / "cli_out"

    test_args = [
        "cochem_goat_crest_union.py",
        "--seeds", str(seed_file),
        "--output-dir", str(out_dir),
        "--ewin", "12.0",
        "--threads", "2",
    ]
    monkeypatch.setattr("sys.argv", test_args)

    ret = main()
    assert ret == 0
    assert (out_dir / "union_deduplicated.xyz").exists()
    assert (out_dir / "union_diagnostics_report.json").exists()

