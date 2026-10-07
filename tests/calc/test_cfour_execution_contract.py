"""Input/resource/publication boundaries; no invented chemistry reference data."""
import json
import os
from pathlib import Path

import pytest

from cochem_base.calc.calculation_service import CalculationMatrixConfig, _engine_environment, _publish_run_artifacts
from cochem_base.calc.cfour_execution import supported_cfour_request, write_cfour_input
from cochem_base.interfaces.scientific_jobs import calculation_capability


GEOMETRY = "H 0 0 0\nH 0 0 .74\n"


def request(**changes):
    values = dict(geometry=GEOMETRY, engine="cfour", method="HF", basis_set="STO-3G", is_opt=False)
    values.update(changes)
    return CalculationMatrixConfig(**values)


@pytest.mark.parametrize("changes", [
    {"method": "CCSD(T)", "is_freq": True}, {"method": "MP2", "is_opt": True, "initial_hessian": "BFGS"},
    {"is_vpt2": True}, {"multiplicity": 3}, {"method": "CC3"}, {"grid_stage": 3},
    {"is_opt": True, "initial_hessian": "XTB2"}, {"is_opt": True, "initial_hessian": "Lindh"},
    {"basis_set": "def2-TZVP"}, {"basis_set": "def2-TZVPP"},
    {"product_class": "A"}, {"product_class": "B"}, {"product_class": "C"},
])
def test_unvalidated_cfour_operation_has_no_native_execution_capability(changes):
    config = request(**changes)
    assert not supported_cfour_request(config)
    assert calculation_capability(config).adapter_status == "pending_integration"


def test_cfour_optimizer_requires_explicit_bfgs_and_does_not_claim_science():
    config = request(is_opt=True, initial_hessian="BFGS")
    assert supported_cfour_request(config)
    capability = calculation_capability(config)
    assert capability.adapter_status == "connected"
    assert capability.scientific_execution_performed is False
    assert capability.executable_authorization == "required_at_execution"


def test_cfour_basis_keyword_injection_cannot_generate_a_native_deck(tmp_path):
    with pytest.raises(ValueError, match="plain supported basis label"):
        write_cfour_input(tmp_path, request(basis_set="STO-3G,VIB=EXACT"), ["H", "H"], [[0, 0, 0], [0, 0, .74]])
    assert not (tmp_path / "ZMAT").exists()


def test_cfour_openmp_cannot_enable_nested_blas_teams():
    inherited = {"PATH": os.defpath, "OMP_NUM_THREADS": "8", "OPENBLAS_NUM_THREADS": "8"}
    environment = _engine_environment("cfour", 2, inherited)
    assert environment["OMP_NUM_THREADS"] == "2"
    assert environment["OPENBLAS_NUM_THREADS"] == environment["MKL_NUM_THREADS"] == "1"
    assert environment["BLIS_NUM_THREADS"] == environment["GOTO_NUM_THREADS"] == "1"
    assert inherited["OMP_NUM_THREADS"] == inherited["OPENBLAS_NUM_THREADS"] == "8"


@pytest.mark.parametrize("memory", [0, -1, True, 512.5])
def test_invalid_global_memory_never_reaches_cfour_input(tmp_path, memory):
    with pytest.raises(ValueError, match="positive integer MB"):
        write_cfour_input(tmp_path, request(), ["H", "H"], [[0, 0, 0], [0, 0, .74]], memory_mb=memory)
    assert not (tmp_path / "ZMAT").exists()


def test_published_job_never_follows_runtime_links_or_distributes_basis_payload(tmp_path):
    sandbox, published = tmp_path / "sandbox", tmp_path / "published"
    sandbox.mkdir()
    # Real repository source bytes exercise file exclusion; this is not a
    # pretend basis or quantum output and is never interpreted as either.
    source = Path(__file__).resolve()
    (sandbox / "GENBAS").write_bytes(source.read_bytes())
    (sandbox / "ECPDATA").write_bytes(source.read_bytes())
    if os.name != "nt":
        # The packaged CFOUR runtime and these runtime links require Linux.
        # Basis-file exclusion itself is checked on every platform.
        (sandbox / "runtime-link").symlink_to(source)
    report = sandbox / "input_validation.json"
    report.write_text(json.dumps({"scope": "filesystem boundary only"}))
    _publish_run_artifacts(sandbox, published)
    assert sorted(path.name for path in published.iterdir()) == ["input_validation.json", "input_validation.json.sha256"]
