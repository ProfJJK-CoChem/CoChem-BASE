"""Regression checks for audited production entrypoint boundary gaps."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import h5py
import numpy as np
import pytest

from cochem_base.core import cochem_constants as constants
from cochem_base.intake.conformer_deduplication import ConformerCandidate, ConformerDeduplicator
from cochem_base.core_engine.scientific_telemetry import append_scientific_result, read_scientific_results
from cochem_base.topos_runner import TOPOSExecutionBroker, _normalize_ingress, _write_json


def test_public_conversion_consumers_use_one_registry():
    from cochem_base.core.glossary import UnitConversionConstants
    from cochem_base.core.models import BOHR_TO_ANGSTROM
    from cochem_base.formatters.cochem_inertial_defect_validator import ROTATIONAL_CONVERSION_MHZ_U_ANG2
    from cochem_base.mm.conference2.a7.propagate import CONV_MHZ_AMU_ANG2, CODATA_CONV_EXACT
    from cochem_base.cochem_spcat_bridge import CODATA2022

    assert BOHR_TO_ANGSTROM == UnitConversionConstants.BOHR_TO_ANGSTROM == constants.BOHR_TO_ANGSTROM
    assert UnitConversionConstants.AMU_TO_KG == CODATA2022.AMU_KG == constants.ATOMIC_MASS_UNIT_KG
    assert (ROTATIONAL_CONVERSION_MHZ_U_ANG2 == CONV_MHZ_AMU_ANG2 == CODATA_CONV_EXACT
            == CODATA2022.C_ROT == UnitConversionConstants.ROTATIONAL_INERTIA_CONVERSION
            == constants.C_ROT_MHZ_U_ANG2)


def test_scribe_guard_cannot_be_disabled_by_environment(tmp_path):
    environment = dict(os.environ, RESOURCE_GUARD="0", COCHEM_CONFIG=str(tmp_path / "missing-registry.json"))
    source = """
import json, sys
from pathlib import Path
from cochem_base.engines.scribe_engine import LocalLlamaEngine, DryRunEngine
root = Path(sys.argv[1])
engine = LocalLlamaEngine(model_path=root/'absent.gguf', audit_log_path=root/'audit.json')
assert engine.model is None
assert isinstance(engine._fallback_engine, DryRunEngine)
assert not engine.resource_guard_decision.allow_local_llm
assert 'registry' in engine.resource_guard_decision.reason.lower()
print(json.dumps({'mode':engine.resource_guard_decision.execution_mode}))
"""
    result = subprocess.run([sys.executable, "-c", source, str(tmp_path)], env=environment,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["mode"] in {"DRY_RUN", "EXTERNAL_API"}


def test_conformer_energy_disagreement_is_not_deduplicated():
    coords = np.array([[0., 0., 0.], [.95, 0., 0.], [-.23, .92, 0.]])
    candidates = [ConformerCandidate(str(index), ["O", "H", "H"], coords, energy,
                                     energy_unit="kcal/mol")
                  for index, energy in enumerate((0., .04, .06))]
    assert [candidate.energy for candidate in ConformerDeduplicator().deduplicate(candidates)] == [0., .06]


def test_topos_ingress_enforces_mass_weighted_frame():
    coordinates = np.array([[4., 5., 6.], [4.95, 5., 6.], [3.77, 5.92, 6.]])
    normalized, evidence = _normalize_ingress(["O", "H", "H"], coordinates)
    assert np.linalg.norm(np.average(normalized, axis=0, weights=evidence["masses_u"])) < 1e-12
    assert evidence["com_mass_residual_u_angstrom"] < 1e-12
    assert evidence["eckart_residual_u_angstrom2"] < 1e-10
    np.testing.assert_allclose(np.linalg.norm(coordinates[0] - coordinates[1]),
                               np.linalg.norm(normalized[0] - normalized[1]), atol=1e-14)


def test_topos_completion_waits_for_real_worker_exit(tmp_path):
    broker = TOPOSExecutionBroker(tmp_path / "scratch", tmp_path / "store")
    job_id = "topos_job_" + "c" * 32
    directory = broker.scratch_root / job_id
    directory.mkdir()
    _write_json(directory / "telemetry.json", {"status": "COMPLETED"})
    process = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(0.5)"])
    broker.active_processes[job_id] = process
    try:
        assert broker.poll_telemetry(job_id)["status"] == "RUNNING"
        process.wait(timeout=10)
        assert broker.poll_telemetry(job_id)["status"] == "COMPLETED"
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)


def test_scientific_telemetry_commits_only_supplied_observables(tmp_path):
    # Actual ASE EMT energy and forces supply this storage integration test.
    from ase.build import molecule
    from ase.calculators.emt import EMT
    atoms = molecule("H2")
    atoms.calc = EMT()
    energy = atoms.get_potential_energy() / constants.HARTREE_TO_EV
    gradient = -atoms.get_forces() * constants.BOHR_TO_ANGSTROM / constants.HARTREE_TO_EV
    target = tmp_path / "complexes.h5"
    append_scientific_result("physical", atoms.get_chemical_symbols(), atoms.positions, energy,
                            metadata={"engine": "ASE EMT", "kind": "energy"}, store_path=target)
    append_scientific_result("physical", atoms.get_chemical_symbols(), atoms.positions, energy,
                            gradients=gradient, metadata={"engine": "ASE EMT", "kind": "gradient"}, store_path=target)
    result = read_scientific_results("physical", store_path=target)
    assert result["energy_hartree"].tolist() == [energy, energy]
    assert result["gradient_record_indices"].tolist() == [1]
    np.testing.assert_allclose(result["gradients_hartree_per_bohr"][0], gradient)
    with pytest.raises(ValueError, match="finite energy"):
        append_scientific_result("physical", atoms.get_chemical_symbols(), atoms.positions,
                                float("nan"), store_path=target)
    with h5py.File(target, "r", swmr=True) as archive:
        assert archive["trajectories/physical/committed_records"][()] == 2
        assert archive["trajectories/physical/energy_hartree"].fletcher32
