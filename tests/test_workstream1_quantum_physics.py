#!/usr/bin/env python3
"""
Workstream 1 Verification Suite: Core Quantum Physics Specialist
Validates:
1. TORQ: 3D Sinc-DVR grid, Constrained Monomer Relaxation with ORCA %geom Constraints, F(phi), V3/V6 fitting.
2. BENCH: ZORA/DKH/X2C relativistic core potentials, Boys-Bernardi counterpoise energy calculation, Grid5/FinalGrid6.
3. GEOM: Explicit graph branching for isotopic substitution, axis-resolved DBOC, Kraitchman condition number traps.
4. TOPOS: Jiggle-Quench Deduplication with Distance Matrix Hashing, process_conformer rotamer merging.
"""

import pytest
import numpy as np
import networkx as nx
from pathlib import Path
from ase import Atoms

# Imports
from Libraries.cochem_torq_grid import TorqGrid
from Libraries.cochem_torq_orca import TorqOrcaExecutor
from bench_core.orca_writer import generate_dlpno_ccsd_f12, generate_counterpoise_input, compute_counterpoise_corrected_energy
from cochem_geom_ingest_math import CoordinateStandardizer
from cochem_geom_fitter_optim import KraitchmanEngine
from core_engine.cochem_topos_crusher import ToposCrusher


# ---------------------------------------------------------------------------
# TORQ TESTS
# ---------------------------------------------------------------------------
def test_torq_3d_sinc_dvr_grid():
    syms = ["H", "O", "O", "H"]
    coords = [[0.0, 0.95, 0.0], [0.0, 0.0, 0.0], [1.4, 0.0, 0.0], [1.4, 0.95, 0.5]]
    graph = nx.Graph()
    graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
    
    gridder = TorqGrid(syms, coords, graph)
    dihedrals = [(0, 1, 2, 3), (0, 1, 2, 3), (0, 1, 2, 3)]
    grid_3d = gridder.generate_3d_sinc_dvr_grid(dihedrals, points_per_dim=3)
    assert len(grid_3d) > 0
    assert grid_3d[0]["sinc_dvr_point"] is True
    assert grid_3d[0]["is_3d_grid"] is True


def test_torq_constrained_monomer_relaxation():
    syms = ["H", "O", "O", "H"]
    coords = [[0.0, 0.95, 0.0], [0.0, 0.0, 0.0], [1.4, 0.0, 0.0], [1.4, 0.95, 0.5]]
    graph = nx.Graph()
    graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
    
    gridder = TorqGrid(syms, coords, graph)
    grid_pt = {"coordinates": coords, "dihedral_angles": {"(0, 1, 2, 3)": 30.0}}
    executor = TorqOrcaExecutor()
    
    relaxed_pt = gridder.relax_monomers_constrained_orca(grid_pt, executor=executor)
    assert "coordinates" in relaxed_pt
    assert relaxed_pt.get("monomer_relaxed") is True


def test_torq_orca_constrained_input_generation():
    executor = TorqOrcaExecutor()
    atom_coords = [["O", 0.0, 0.0, 0.0], ["H", 0.0, 0.75, 0.58], ["H", 0.0, -0.75, 0.58]]
    inp = executor._generate_orca_input(
        method="r2SCAN-3c", basis_set="", aux_basis="", scf_type="DIIS",
        atom_coords=atom_coords, extra_options="! OPT\n%geom\n  Constraints\n    { B 0 1 C }\n  end\nend\n"
    )
    assert "%geom" in inp
    assert "{ B 0 1 C }" in inp


def test_torq_f_phi_and_v3_v6_fitting():
    syms = ["H", "C", "C", "H"]
    coords = [[0.0, 0.0, -1.0], [0.0, 0.0, 0.0], [0.0, 0.0, 1.5], [0.0, 1.0, 2.5]]
    graph = nx.Graph()
    graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
    gridder = TorqGrid(syms, coords, graph)
    
    res_f = gridder.calculate_reduced_moment_of_inertia_F_phi(coords, rotating_top=[3], axis_start=1, axis_end=2)
    assert "I_top" in res_f
    assert "F_cm1" in res_f
    assert res_f["F_cm1"] > 0.0
    
    angles = [0.0, 60.0, 120.0, 180.0, 240.0, 300.0]
    energies = [0.0, 3.1, 0.1, 3.1, 0.1, 3.1]
    res_v = gridder.fit_v3_v6_barriers(angles, energies)
    assert "V3" in res_v
    assert "V6" in res_v
    assert res_v["V3"] is not None


# ---------------------------------------------------------------------------
# BENCH TESTS
# ---------------------------------------------------------------------------
def test_bench_zora_dkh_relativistic_potentials():
    coords = [("I", 0.0, 0.0, 0.0), ("H", 0.0, 0.0, 1.6)]
    inp_dkh = generate_dlpno_ccsd_f12(coords, basis="aug-cc-pVTZ", rel_mode="DKH2")
    assert "Relativistic DKH2" in inp_dkh
    assert "Grid5 FinalGrid6" in inp_dkh
    assert "aug-cc-pVTZ-DK" in inp_dkh

    inp_zora = generate_dlpno_ccsd_f12(coords, basis="aug-cc-pVTZ", rel_mode="ZORA")
    assert "ZORA" in inp_zora
    assert "Grid5 FinalGrid6" in inp_zora


def test_bench_counterpoise_energy_calculation():
    frag_a = [("O", 0.0, 0.0, 0.0), ("H", 0.0, 0.0, 0.95)]
    frag_b = [("H", 2.0, 0.0, 0.0), ("Cl", 3.2, 0.0, 0.0)]
    cp_inp = generate_counterpoise_input(frag_a, frag_b, basis="aug-cc-pVTZ", rel_mode="DKH2")
    assert "Grid5 FinalGrid6" in cp_inp["complex_input"]
    
    e_calc = compute_counterpoise_corrected_energy(
        e_complex=-500.100,
        e_monomer_a_cp=-250.040,
        e_monomer_b_cp=-250.050,
        e_monomer_a_raw=-250.035,
        e_monomer_b_raw=-250.045
    )
    assert abs(e_calc["delta_e_cp_hartree"] - (-0.010)) < 1e-5
    assert abs(e_calc["e_bsse_hartree"] - (0.010)) < 1e-5


# ---------------------------------------------------------------------------
# GEOM TESTS
# ---------------------------------------------------------------------------
def test_geom_explicit_isotope_branching_graph():
    standardizer = CoordinateStandardizer()
    res = standardizer.generate_isotope_branching_graph(["C", "H", "H", "H", "H"], {0: 13, 1: 2})
    assert "branches" in res
    assert "nodes" in res
    assert "graph" in res
    assert len(res["branches"]) == 2
    assert "parent_0" in res["nodes"]


def test_geom_axis_resolved_dboc_corrections():
    standardizer = CoordinateStandardizer()
    moments = np.array([10.0, 50.0, 60.0])
    masses = np.array([12.0, 1.0, 1.0, 1.0, 1.0])
    dboc_moments = standardizer.apply_born_oppenheimer_correction(moments, masses, is_isotopologue=True)
    assert len(dboc_moments) == 3
    assert np.all(dboc_moments > moments)


def test_geom_kraitchman_condition_number_traps():
    engine = KraitchmanEngine()
    parent_I = np.array([10.0, 50.0, 60.0])
    iso_I = np.array([10.0, 50.01, 60.01]) # Small near-axis shift
    report = engine.fit_rs_kraitchman(parent_I, iso_I, M_parent=16.0, delta_m=1.0, return_report=True)
    assert "coordinates" in report
    assert "condition_number" in report
    assert "trap_triggered" in report
    assert len(report["coordinates"]) == 3


# ---------------------------------------------------------------------------
# TOPOS TESTS
# ---------------------------------------------------------------------------
def test_topos_jiggle_quench_deduplication(tmp_path):
    h5_path = tmp_path / "topos_test.h5"
    crusher = ToposCrusher(hdf5_path=str(h5_path))
    
    water1 = Atoms('H2O', positions=[(0, 0, 0), (0, 0, 0.95), (0, 0.95, 0)])
    water2 = water1.copy()
    water2.positions += 0.001  # Slightly perturbed candidate
    
    res1 = crusher.process_conformer(water1, energy_kcal=-76.0)
    assert res1["status"] == "accepted"
    
    res2 = crusher.process_conformer(water2, energy_kcal=-76.0)
    assert res2["status"] == "duplicate"
