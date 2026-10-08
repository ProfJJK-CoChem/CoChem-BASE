"""Frame acceptance from an archived native ORCA tensor; no engine substitution."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from cochem_base.calc.calculation_service import run_calculation
from cochem_base.calc.cochem_calc_input_generator import MoleculeInput
from cochem_base.calc.grid_execution import _stage_model
from cochem_base.core_engine.hardware_profiler import profile_hardware
from cochem_base.spectroscopy.artifacts import load_hessian_artifact


RECORDED = Path(__file__).parents[1] / "data/orca_6_1_1_water_hf_sto3g"


def recorded_geometry():
    artifact = load_hessian_artifact(RECORDED / "water.hess")
    return "\n".join([str(len(artifact.symbols)), "Exact geometry retained in the authentic ORCA Hessian"] +
                     [symbol + " " + " ".join(format(float(value), ".17g") for value in xyz)
                      for symbol, xyz in zip(artifact.symbols, artifact.coordinates_angstrom, strict=True)]) + "\n"


def test_dry_run_binds_real_checkpoint_to_exact_native_deck_frame(tmp_path):
    original = RECORDED / "water.hess"
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    geometry = recorded_geometry()
    hardware = profile_hardware()
    registry = tmp_path / "measured-hardware.json"
    registry.write_text(json.dumps({"hardware": {
        "physical_cpu_cores": min(hardware.physical_cores, len(hardware.available_cpu_ids)),
        "ram_mb": hardware.available_ram_bytes // 1024**2,
    }}))
    config = tmp_path / "request.json"
    config.write_text(json.dumps({"geometry": geometry, "engine": "orca", "method": "HF",
                                 "basis_set": "STO-3G", "is_opt": True,
                                 "initial_hessian": "READ", "hessian_file": str(original)}))
    publication = tmp_path / "publication"
    result = run_calculation(config, scratch=tmp_path / "scratch", output=publication,
                             registry_path=registry, threads=1, maxcore_mb=128, dry_run=True)
    assert result["status"] == "DECK_GENERATED"
    assert hashlib.sha256(original.read_bytes()).hexdigest() == digest
    binding = json.loads((publication / "scientific-inputs/frame-binding.json").read_text())
    alignment = json.loads((publication / "ingress_alignment.json").read_text())
    checkpoint = load_hessian_artifact(publication / "scientific-inputs/aligned.hess")
    np.testing.assert_allclose(checkpoint.coordinates_angstrom, alignment["coordinates_angstrom"],
                               atol=1e-12, rtol=0)
    original_tensor = load_hessian_artifact(publication / "scientific-inputs/original.hess")
    rotation = np.asarray(binding["rotation"])
    tensor_rotation = np.kron(np.eye(len(checkpoint.symbols)), rotation)
    np.testing.assert_allclose(checkpoint.hessian_hartree_bohr2,
                               tensor_rotation @ original_tensor.hessian_hartree_bohr2 @ tensor_rotation.T,
                               atol=1e-12, rtol=0)
    assert binding["uploaded_source_sha256"] == digest
    assert binding["scientific_execution_performed"] is False
    decks = list(publication.glob("*_job.inp"))
    assert len(decks) == 1 and 'InHess READ' in decks[0].read_text()


def test_unrelated_recorded_checkpoint_is_rejected_before_any_native_deck(tmp_path):
    original = RECORDED / "water.hess"
    geometry = recorded_geometry().splitlines()
    fields = geometry[-1].split()
    fields[1] = str(float(fields[1]) + 0.1)
    geometry[-1] = " ".join(fields)
    config = tmp_path / "request.json"
    config.write_text(json.dumps({"geometry": "\n".join(geometry) + "\n", "engine": "orca",
                                 "method": "HF", "basis_set": "STO-3G", "is_opt": True,
                                 "initial_hessian": "READ", "hessian_file": str(original)}))
    with pytest.raises(ValueError, match="geometry"):
        run_calculation(config, scratch=tmp_path / "scratch", output=tmp_path / "publication",
                        threads=1, maxcore_mb=128, dry_run=True)
    assert not list((tmp_path / "scratch").rglob("*_job.inp"))


def test_refined_grid_does_not_reuse_initial_tensor_at_a_changed_geometry():
    artifact = load_hessian_artifact(RECORDED / "water.hess")
    data = MoleculeInput(basin_id="recorded_checkpoint", elements=list(artifact.symbols),
                         coordinates=artifact.coordinates_angstrom.tolist(),
                         theory_level="PBE-D4 STO-3G", initial_hessian="READ",
                         hessian_file=artifact.path, is_opt=True)
    first = _stage_model(data, 1, data.coordinates)
    assert first.hessian_file == artifact.path and first.initial_hessian == "READ"
    transferred = artifact.coordinates_angstrom.copy()
    transferred[-1, 0] += 0.02
    second = _stage_model(data, 2, transferred.tolist())
    assert second.hessian_file is None and second.initial_hessian == "Lindh"
    np.testing.assert_array_equal(second.coordinates, transferred)
