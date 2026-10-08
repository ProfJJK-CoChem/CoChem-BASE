"""Real PAW calculations and input/authority rejection contracts."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from cochem_base.calc.periodic_execution import PeriodicCalculationConfig, write_periodic_input


BINARY = Path(os.environ.get("COCHEM_QE_BIN", "/workspace/cochem-silos/qe/usr/bin/pw.x"))
PSEUDO_DIR = Path(os.environ.get("COCHEM_QE_PSEUDO_DIR", "/workspace/cochem-runtime/qe-pseudo"))
FILES = {"Ga": "Ga.pbe-dn-kjpaw_psl.0.2.upf", "As": "As.pbe-n-kjpaw_psl.0.2.upf"}
CELL = [[0., 2.825, 2.825], [2.825, 0., 2.825], [2.825, 2.825, 0.]]
COORDINATES = [[0., 0., 0.], [1.4125, 1.4125, 1.4125]]
AVAILABLE = BINARY.is_file() and all((PSEUDO_DIR / name).is_file() for name in FILES.values())


def _settings() -> dict:
    return {"cell_angstrom": CELL, "pseudopotentials": {
        symbol: {"path": str(PSEUDO_DIR / name), "sha256": hashlib.sha256((PSEUDO_DIR / name).read_bytes()).hexdigest()}
        for symbol, name in FILES.items()}}


@pytest.mark.parametrize("updates,match", [
    ({"cell_angstrom": [[0., 0., 0.]] * 3}, "nondegenerate"),
    ({"pbc": [True, True, False]}, "three periodic"),
    ({"kpoints": [0, 2, 2]}, "Reciprocal mesh"),
    ({"ecutrho_ry": 10.}, "four times"),
])
def test_periodic_domain_rejects_invalid_cell_or_sampling(updates, match):
    with pytest.raises(ValueError, match=match):
        PeriodicCalculationConfig.model_validate({"cell_angstrom": CELL, "pseudopotentials": {}, **updates})


def test_paw_digest_spin_and_periodic_alias_rejections(tmp_path):
    assert AVAILABLE, "Install the pinned free QE/PAW stack with .scripts/install_qe_paw.py before acceptance tests"
    config = PeriodicCalculationConfig.model_validate(_settings())
    with pytest.raises(ValueError, match="closed-shell"):
        write_periodic_input(["Ga", "As"], COORDINATES, config, directory=tmp_path / "spin", multiplicity=3)
    with pytest.raises(ValueError, match="coincide"):
        write_periodic_input(["Ga", "As"], [[0, 0, 0], CELL[0]], config, directory=tmp_path / "coincident")
    corrupt = _settings()
    corrupt["pseudopotentials"]["Ga"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="digest"):
        write_periodic_input(["Ga", "As"], COORDINATES, PeriodicCalculationConfig.model_validate(corrupt), directory=tmp_path / "digest")
    assert not list(tmp_path.iterdir())


def test_real_shared_service_paw_scf_retains_cell_and_measured_telemetry(tmp_path):
    assert AVAILABLE, "Install the pinned free QE/PAW stack with .scripts/install_qe_paw.py before acceptance tests"
    from cochem_base.calc.periodic import ingest_periodic_structure
    from cochem_base.cochem_core_registry_schema import CoChemSystemConfig
    from cochem_base.core_engine.scientific_telemetry import read_scientific_results

    registry = CoChemSystemConfig.create_default(auto_detect_hardware=True)
    registry.engines = {"qe": {"status": "found", "path": str(BINARY), "hash": hashlib.sha256(BINARY.read_bytes()).hexdigest()}}
    registry = CoChemSystemConfig.model_validate(registry.model_dump())
    registry.update_checksum()
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(registry.model_dump_json(), encoding="utf-8")
    config = tmp_path / "config.json"
    structure = ingest_periodic_structure(Path(__file__).resolve().parents[2] / "examples/product_b/gaas_fractional.json")
    config.write_text(json.dumps({**structure.to_calculation_config({"pseudopotentials": _settings()["pseudopotentials"]}),
                                 "timeout_seconds": 90.}))
    output = tmp_path / "published"
    environment = {**os.environ, "COCHEM_CONFIG": str(registry_path), "COCHEM_ARTIFACT_DIR": str(tmp_path / "artifacts"),
                   "COCHEM_COMPLEXES_H5": str(tmp_path / "complexes.h5")}
    script = "from cochem_base.calc.calculation_service import run_calculation; import sys; run_calculation(sys.argv[1], output=sys.argv[2], scratch=sys.argv[3], threads=1, keep_scratch=True)"
    completed = subprocess.run([sys.executable, "-c", script, str(config), str(output), str(tmp_path / "scratch")],
                               env=environment, capture_output=True, text=True, timeout=120)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads((output / "periodic/result.json").read_text())
    assert result["status"] == "SCF_VERIFIED" and result["scf_converged"] is True
    assert result["energy_hartree"] < -200. and np.isfinite(result["energy_hartree"])
    assert result["metadata"]["engine_version"].startswith("6.7")
    assert result["metadata"]["accuracy_validated"] is False
    assert result["metadata"]["cpu_affinity"]
    np.testing.assert_allclose(result["cell_angstrom"], CELL, atol=1e-7)
    np.testing.assert_allclose(result["coordinates_angstrom"], COORDINATES, atol=1e-7)
    gradients = np.asarray(result["gradients_hartree_per_bohr"])
    assert gradients.shape == (2, 3) and np.isfinite(gradients).all()
    records = read_scientific_results(result["job_id"], store_path=tmp_path / "complexes.h5")
    assert result["nuclides"] == records["nuclides"] == list(structure.elements)
    assert result["nuclear_identity"] == records["nuclear_identity"]
    assert result["nuclear_identity"]["mass_source"] == "dynamic_mendeleev"
    assert records["energy_hartree"][0] == result["energy_hartree"]
    np.testing.assert_allclose(records["gradients_hartree_per_bohr"][0], gradients)
    assert "JOB DONE." in (output / "periodic/qe.out").read_text()
    ingress = json.loads((output / "ingress_alignment.json").read_text())
    assert ingress["method"] == "periodic_cell_frame_preserved"
    assert result["metadata"]["periodic"]["structure_provenance"]["source_sha256"] == structure.source.source_sha256
