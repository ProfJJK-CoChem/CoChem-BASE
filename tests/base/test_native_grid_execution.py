"""Grid execution planning and gates, using independently recorded derivatives."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest

from cochem_base.calc.cochem_calc_input_generator import MoleculeInput
from cochem_base.calc.grid_execution import (
    _lifecycle_telemetry_summary, _promotion_evidence, _stage_model, execute_orca_calculation, quadrature_execution_plan,
)
from cochem_base.exceptions import GridSpecificationError
from cochem_base.mm.quadrature_manager import GridStage, QuadratureManager


def molecule(**updates):
    return MoleculeInput(basin_id="hydrogen", elements=["H", "H"],
                         coordinates=[(0, 0, 0), (0, 0, 0.82)],
                         theory_level=updates.pop("theory_level", "PBE-D4 STO-3G"),
                         initial_hessian="Lindh", **updates)


@pytest.mark.parametrize("minimum,grids", [(None, [1, 2, 3]), (1, [1, 2, 3]), (2, [2, 3]), (3, [3])])
def test_dynamic_grid_sequence_respects_requested_minimum(minimum, grids):
    data = molecule(grid_stage=minimum)
    plan = quadrature_execution_plan(data)
    assert plan["stages"] == grids
    for stage in grids:
        actual = _stage_model(data, stage, data.coordinates)
        assert actual.grid_stage == stage
        assert actual.theory_level == data.theory_level
        assert actual.initial_hessian == "Lindh"


def test_explicit_keyword_minimum_remains_an_execution_minimum():
    data = molecule(theory_level="PBE-D4 STO-3G DEFGRID2")
    assert quadrature_execution_plan(data)["stages"] == [2, 3]
    with pytest.raises(GridSpecificationError):
        _stage_model(molecule(theory_level="PBE-D4 STO-3G", tier=4), 1, data.coordinates)


@pytest.mark.parametrize("tier,stages", [(3, [1, 2, 3]), (4, [2, 3]), (5, [3]), (7, [3]), (8, [3])])
def test_theory_tier_is_never_temporarily_lowered(tier, stages):
    data = molecule(tier=tier)
    assert quadrature_execution_plan(data)["stages"] == stages
    for stage in stages:
        assert _stage_model(data, stage, data.coordinates).tier == tier


@pytest.mark.parametrize("theory", ["HF STO-3G", "MP2 STO-3G", "CCSD(T) STO-3G", "CASSCF STO-3G"])
def test_no_dft_grid_progression_for_wavefunction_methods(theory):
    plan = quadrature_execution_plan(molecule(theory_level=theory))
    assert plan["stages"] == [1] and not plan["dynamic"]


@pytest.mark.parametrize("updates", [{"is_opt": False}, {"is_freq": True}, {"is_vpt2": True}])
def test_single_points_and_spectroscopy_do_not_run_coarse_optimization_stages(updates):
    plan = quadrature_execution_plan(molecule(**updates))
    assert not plan["dynamic"]
    assert plan["stages"] == ([1] if updates.get("is_opt") is False else [3])


def test_r2_and_metal_safeguards_remain_fixed_defgrid3():
    r2 = molecule(theory_level="wB97M-V def2-QZVPP", recipe="R2")
    assert quadrature_execution_plan(r2)["stages"] == [3]
    iron = MoleculeInput(basin_id="iron", elements=["Fe"], coordinates=[(0, 0, 0)],
                         theory_level="PBE-D4 def2-SVP", multiplicity=1, initial_hessian="Lindh")
    assert quadrature_execution_plan(iron)["stages"] == [3]


def recorded_water_evidence():
    from cochem_base.calc.calculation_service import parse_run_geometry
    from cochem_base.calc.cochem_calc_output_parser import QuantumParser
    from cochem_base.calc.orca_derivatives import accept_gradient
    directory = Path(__file__).parents[1] / "data" / "orca_6_1_1_water_hf_sto3g"
    elements, coordinates = parse_run_geometry((directory / "water.xyz").read_text())
    parser = QuantumParser(str(directory))
    convergence = parser.verify_geometry_convergence(directory / "water.out.txt")
    # These derivatives are an archived authentic ORCA result, not a process
    # substitute used to pretend that a refinement stage ran.
    from cochem_base.calc.recipe_r2_execution import read_dimer_gradient
    import numpy as np
    energy, _ = read_dimer_gradient(directory / "water.engrad", elements, np.asarray(coordinates))
    accepted = {"coordinates_angstrom": coordinates,
                **accept_gradient(directory / "water.engrad", elements, coordinates, energy, required=True)}
    return accepted, [{"coordinates_angstrom": [list(row) for row in coordinates]}], convergence


def test_grid_promotion_accepts_complete_recorded_native_derivatives():
    accepted, records, convergence = recorded_water_evidence()
    for stage in (1, 2):
        gate = _promotion_evidence(stage, accepted, records, convergence)
        assert gate["accepted"] and gate["next_grid"] == f"DEFGRID{stage + 1}"


@pytest.mark.parametrize("damage", ["missing_records", "large_gradient", "nonfinite_gradient", "large_energy", "large_step"])
def test_grid_promotion_rejects_damaged_measurements(damage):
    accepted, records, convergence = recorded_water_evidence()
    accepted, records = deepcopy(accepted), deepcopy(records)
    if damage == "missing_records":
        records = []
    elif damage == "large_gradient":
        accepted["gradients_hartree_per_bohr"][0][0] = 1e-3
    elif damage == "nonfinite_gradient":
        accepted["gradients_hartree_per_bohr"][0][0] = float("nan")
    elif damage == "large_energy":
        convergence["Energy change"] = 1e-3
    else:
        records[0]["coordinates_angstrom"][0][0] += 0.2
    with pytest.raises(GridSpecificationError):
        _promotion_evidence(2, accepted, records, convergence)


def test_proposal_measured_screening_gate_is_not_weaker_than_1e_minus_4():
    assert QuadratureManager.determine_next_stage(1, 1.0001e-4, 1e-8) == GridStage.STAGE_1
    assert QuadratureManager.determine_next_stage(1, 1e-4, 1e-8) == GridStage.STAGE_2


def test_cancelled_lifecycle_never_launches_or_authorizes_an_engine(tmp_path):
    from cochem_base.core_engine.cochem_core_subprocess_broker import SubprocessCancelledError
    event = threading.Event(); event.set()
    with pytest.raises(SubprocessCancelledError):
        execute_orca_calculation(SimpleNamespace(timeout_seconds=120), molecule(), directory=tmp_path,
            authority=None, environment={}, capability=None, registry_path=None,
            cancellation_event=event, telemetry_job_id="cancelled")
    assert not (tmp_path / "grid_stages").exists()


def stationary_native_log():
    import hashlib
    directory = Path(__file__).parents[1] / "data" / "orca_6_1_1_stationary_trah_dft"
    native = directory / "stationary.out.txt"
    assert hashlib.sha256(native.read_bytes()).hexdigest() == "8207b6f2fb87127ca5afa66a4cff7c998deb3ed411ad97f3773b1614351abb54"
    return native.read_text()


def test_stationary_restart_uses_its_own_measured_native_scf_energy_change(tmp_path):
    from cochem_base.calc.cochem_calc_output_parser import QuantumParser, _stationary_trah_energy_change
    content = stationary_native_log()
    actual_change = _stationary_trah_energy_change(content)
    assert actual_change is not None and 0 < actual_change < 1e-12
    log = tmp_path / "stationary-native.out"; log.write_text(content)
    assert QuantumParser(str(tmp_path)).verify_scf_convergence(log)


@pytest.mark.parametrize("damage", ["wrong_version", "missing_normal_end", "different_energy", "unconverged_density",
                                    "nonfinite_diis", "weak_scf_tolerance", "missing_residual", "extra_trah_cycle",
                                    "wrong_sentinel", "missing_energy"])
def test_stationary_restart_never_accepts_missing_or_failed_final_evidence(tmp_path, damage):
    from cochem_base.calc.cochem_calc_output_parser import QuantumParser
    content = stationary_native_log()
    earlier, final = content.rsplit("ORCA LEAN-SCF", 1)
    if damage == "wrong_version":
        earlier = earlier.replace("Program Version 6.1.1", "Program Version 6.0.0")
    elif damage == "missing_normal_end":
        final = final.replace("ORCA TERMINATED NORMALLY", "MISSING_NATIVE_TERMINATION")
    elif damage == "different_energy":
        final = final.replace("-1.15216810983588 Eh", "-1.15216710983588 Eh")
    elif damage == "unconverged_density":
        final = final.replace("Last MAX-Density change    ...    0.0000e+00", "Last MAX-Density change    ...    1.0000e-02")
    elif damage == "nonfinite_diis":
        final = final.replace("Last DIIS Error            ...    4.4409e-16", "Last DIIS Error            ...    NaN")
    elif damage == "weak_scf_tolerance":
        final = final.replace("Tolerance :   1.0000e-10", "Tolerance :   1.0000e-03")
    elif damage == "missing_residual":
        final = final.replace("Last Orbital Rotation", "Absent Orbital Rotation")
    elif damage == "extra_trah_cycle":
        final = final.replace("SCF CONVERGED AFTER   1 CYCLES", "SCF CONVERGED AFTER   2 CYCLES")
    elif damage == "wrong_sentinel":
        final = final.replace("Last Energy change         ...   -1.1522e+00", "Last Energy change         ...   -2.1522e+00")
    else:
        final = final.replace("Total Energy       :", "Missing energy       :")
    altered = earlier + "ORCA LEAN-SCF" + final
    assert altered != content
    log = tmp_path / "negative-stationary.out"; log.write_text(altered)
    assert QuantumParser(str(tmp_path)).verify_scf_convergence(log) is False


def test_large_geometry_provenance_stays_in_hash_bound_artifact_with_bounded_hdf5_metadata(tmp_path):
    import hashlib, json
    # Serialization stress data only, with no claimed engine calculation.
    stage = {"grid": "DEFGRID3", "coordinates_angstrom": [[float(i), 0.0, 0.0] for i in range(5000)],
             "handoff": {"unbounded_state": "x" * 100_000}}
    lifecycle = {"grids": ["DEFGRID3"], "dynamic": False, "completed_stages": [stage]}
    artifact = tmp_path / "grid_lifecycle.json"; artifact.write_text(json.dumps(lifecycle))
    before = artifact.read_bytes()
    metadata = _lifecycle_telemetry_summary(artifact, lifecycle)
    assert len(json.dumps(metadata).encode()) < 4096
    assert artifact.read_bytes() == before
    assert metadata["artifact"]["sha256"] == hashlib.sha256(before).hexdigest()
    assert len(json.loads(before)["completed_stages"][0]["coordinates_angstrom"]) == 5000
