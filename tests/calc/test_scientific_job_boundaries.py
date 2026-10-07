"""Real filesystem/input contracts; these checks do not claim quantum acceptance."""
from pathlib import Path
import json
import os
import subprocess
import sys

import h5py
import numpy as np
import pytest

from cochem_base.calc.calculation_service import CalculationMatrixConfig, run_calculation
from cochem_base.interfaces.scientific_jobs import (
    calculation_capability, load_calculation_handoff, prepare_calculation_handoff,
)


GEOMETRY = "2\nHydrogen input\nH 0 0 0\nH 0 0 0.74\n"


def cfour_config(**updates):
    return CalculationMatrixConfig(geometry=GEOMETRY, engine="cfour", method="CCSD(T)",
                                    basis_set="cc-pVTZ", is_opt=False, **updates)


@pytest.mark.parametrize("engine,method,basis,is_freq,is_vpt2", [
    ("cfour", "CCSD(T)", "cc-pVTZ", False, False),
    ("cfour", "CCSD(T)", "cc-pVTZ", True, True),
    ("orca", "wB97M-V", "def2-QZVPP", True, True),
])
def test_native_pending_job_produces_handoff_without_scientific_result(tmp_path, engine, method, basis, is_freq, is_vpt2):
    config = CalculationMatrixConfig(geometry=GEOMETRY, engine=engine, method=method,
                                     basis_set=basis, is_opt=False, is_freq=is_freq, is_vpt2=is_vpt2)
    path = tmp_path / "config.json"
    path.write_text(config.model_dump_json())
    events = []
    result = run_calculation(path, scratch=tmp_path / "scratch", output=tmp_path / "pending",
                             registry_path=tmp_path / "deliberately-not-configured.json", on_event=events.append)
    assert result["status"] == "PENDING_INTEGRATION"
    assert result["scientific_execution_performed"] is False
    request = load_calculation_handoff(result["handoff_manifest"])
    assert request.calculation_config["method"] == method
    assert request.capability.adapter_status == "pending_integration"
    assert request.acceptance_scope == "input_validation_only"
    assert not (tmp_path / "pending/result.json").exists()
    assert not (tmp_path / "pending/execution_authority.json").exists()
    assert not any(event.get("status") in {"RUNNING", "EXECUTION_VERIFIED"} for event in events)
    if is_vpt2:
        assert "cubic_and_semidiagonal_quartic_force_field_with_units" in request.required_evidence


def test_handoff_checks_full_configuration_and_real_copied_dependencies(tmp_path):
    source = tmp_path / "molecule.xyz"
    source.write_text(GEOMETRY)
    # Real source bytes exercise opaque input integrity, not a claimed quantum checkpoint.
    dependency = Path(__file__).resolve()
    target = tmp_path / "request"
    prepare_calculation_handoff(cfour_config(is_vpt2=True), source, target,
                                dependency_files={"provider_contract.py": dependency})
    loaded = load_calculation_handoff(target / "handoff.json")
    assert loaded.dependencies["provider_contract.py"]["size_bytes"] == dependency.stat().st_size
    copied = target / "dependencies/provider_contract.py"
    copied.write_text(copied.read_text() + "\n# corruption\n")
    with pytest.raises(ValueError, match="checkpoint integrity"):
        load_calculation_handoff(target / "handoff.json")


def test_handoff_rejects_edited_acceptance_contract(tmp_path):
    source = tmp_path / "molecule.xyz"
    source.write_text(GEOMETRY)
    target = tmp_path / "request"
    prepare_calculation_handoff(cfour_config(is_vpt2=True), source, target)
    path = target / "handoff.json"
    data = json.loads(path.read_text())
    data["options"]["scientific_job"]["required_evidence"] = []
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="acceptance requirements"):
        load_calculation_handoff(path)


def test_public_boundary_rejects_absent_declared_hessian_and_incomplete_periodic_cell(tmp_path):
    source = tmp_path / "molecule.xyz"
    source.write_text(GEOMETRY)
    config = cfour_config(initial_hessian="READ", hessian_file=tmp_path / "absent.hess")
    with pytest.raises(FileNotFoundError):
        prepare_calculation_handoff(config, source, tmp_path / "missing_hessian")
    config = CalculationMatrixConfig(geometry=GEOMETRY, engine="qe", method="PBE", basis_set="PAW",
                                     product_class="B", periodic={}, is_opt=False)
    with pytest.raises(ValueError, match="cell_angstrom"):
        prepare_calculation_handoff(config, source, tmp_path / "invalid_periodic")


def test_pending_request_preserves_original_coordinate_frame(tmp_path):
    from cochem_base.calc.calculation_service import parse_run_geometry
    config = cfour_config(is_vpt2=True)
    path = tmp_path / "input.json"
    path.write_text(config.model_dump_json())
    result = run_calculation(path, scratch=tmp_path / "scratch")
    request = load_calculation_handoff(result["handoff_manifest"])
    assert parse_run_geometry(request.calculation_config["geometry"]) == parse_run_geometry(GEOMETRY)
    alignment = json.loads((Path(result["scratch_dir"]) / "ingress_alignment.json").read_text())
    assert alignment["method"] == "pending_input_frame_preserved" and alignment["rotation"] is None


@pytest.mark.parametrize("changes", [{"multiplicity": 2}, {"method": "B3LYP"}])
def test_invalid_cfour_request_is_not_relabelled_pending(tmp_path, changes):
    data = cfour_config().model_dump(mode="json")
    data.update(changes)
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        run_calculation(path, scratch=tmp_path / "scratch", output=tmp_path / "pending")
    assert not (tmp_path / "pending").exists()


def test_connected_capability_does_not_claim_executable_or_scientific_validation():
    config = CalculationMatrixConfig(geometry=GEOMETRY, engine="pyscf", method="HF", basis_set="sto-3g", is_opt=False)
    capability = calculation_capability(config)
    assert capability.adapter_status == "connected"
    assert capability.scientific_execution_performed is False
    assert capability.executable_authorization == "required_at_execution"


def test_cfour_bridge_preserves_complete_anharmonic_request_without_execution(tmp_path):
    from cochem_base.core_engine.cochem_core_cfour_bridge import CFOURBridge, CFOURInputConfig
    bridge = CFOURBridge(cfour_executable="deliberately-uninstalled-cfour", scratch_root=tmp_path)
    config = CFOURInputConfig(basis="cc-pVTZ", memory_size_gb=3, scf_conv=12)
    result = bridge.dispatch_cfour_job("pending", ["H", "H"], np.array([[0, 0, 0], [0, 0, .74]]), config)
    assert result.status == "PENDING_INTEGRATION" and result.success is False
    assert result.observables is None and result.error_message is None
    request = load_calculation_handoff(result.handoff_manifest)
    assert request.provider_options["cfour_input"]["memory_size_gb"] == 3
    assert request.provider_options["cfour_input"]["scf_conv"] == 12


def test_chain_pending_state_has_no_result_and_cannot_be_promoted(tmp_path):
    from cochem_base.chain import Chain, ConvergenceFailureError, PendingStateRecord, Stage
    source = tmp_path / "geometry.xyz"
    source.write_text(GEOMETRY)
    config = cfour_config(is_freq=True, is_vpt2=True)
    chain = Chain(workdir=tmp_path / "chain", orca_cmd="deliberately-uninstalled-orca")
    stage = Stage("anharm", "CCSD(T) cc-pVTZ VPT2", engine="cfour",
                  blocks="*CFOUR(ANHARM=VPT2,SCF_CONV=12)", scientific_config=config.model_dump(mode="json"))
    pending = chain.run_stage(stage, source)
    assert isinstance(pending, PendingStateRecord)
    assert pending.energy_hartree is None and pending.converged is False
    request = load_calculation_handoff(pending.handoff_manifest)
    assert request.provider_options["chain_stage"]["blocks"] == stage.blocks
    assert request.dependencies["source_geometry.xyz"]["size_bytes"] == source.stat().st_size
    with h5py.File(chain.h5_path) as archive:
        group = archive["chain/anharm"]
        assert group.attrs["exit_status"] == "PENDING_INTEGRATION"
        assert "energy_hartree" not in group.attrs and "geometry" not in group
    with pytest.raises(ConvergenceFailureError, match="has not converged"):
        chain.run_stage(Stage("consumer", "wB97M-V def2-QZVPP", geom_from="anharm"))


def test_raw_vpt2_chain_points_to_structured_input_contract(tmp_path):
    from cochem_base.chain import Chain, Stage
    chain = Chain(workdir=tmp_path / "chain")
    with pytest.raises(ValueError, match="scientific_config"):
        chain.run_stage(Stage("unstructured", "wB97M-V def2-QZVPP VPT2"))


def test_cli_pending_integration_has_distinct_exit_code_and_durable_manifest(tmp_path):
    path = tmp_path / "input.json"
    path.write_text(cfour_config(is_vpt2=True).model_dump_json())
    repository = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [sys.executable, str(repository / "cli.py"), "run", "--config", str(path),
         "--scratch", str(tmp_path / "scratch"), "--output", str(tmp_path / "published"), "--json"],
        cwd=repository, capture_output=True, text=True, timeout=60,
        env={**os.environ, "COCHEM_ARTIFACT_DIR": str(tmp_path / "artifacts")},
    )
    assert completed.returncode == 3, completed.stdout + completed.stderr
    assert "PENDING_INTEGRATION" in completed.stdout
    assert "Traceback" not in completed.stderr and "Calculation was not accepted" not in completed.stderr
    load_calculation_handoff(tmp_path / "published/handoff/handoff.json")
    assert not (tmp_path / "published/result.json").exists()
