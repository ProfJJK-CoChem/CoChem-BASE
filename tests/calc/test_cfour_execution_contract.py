"""Input/resource/publication boundaries; no invented chemistry reference data."""
import json
import hashlib
import os
from pathlib import Path
import sys
import threading

import pytest

from cochem_base.calc.calculation_service import CalculationMatrixConfig, _engine_environment, _publish_run_artifacts
from cochem_base.calc.cfour_execution import _require_authorized_runtime_seal, execute_cfour, supported_cfour_request, write_cfour_input
from cochem_base.core_engine.cochem_core_subprocess_broker import SubprocessCancelledError, safe_subprocess_run
from cochem_base.core_engine.execution_authority import RegistryAuthorityViolationError
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


def test_native_openmp_broker_preserves_threads_in_a_slurm_environment(tmp_path):
    # An ordinary Python diagnostic process observes the actual child environment;
    # it is not a CFOUR executable and produces no chemistry reference data.
    environment = _engine_environment("cfour", 2, {"PATH": os.defpath, "SLURM_NTASKS": "2"})
    command = [sys.executable, "-c", "import json,os; print(json.dumps({key:os.environ.get(key) for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS')}))"]
    preserved = safe_subprocess_run(command, cwd=tmp_path, env=environment, sanitize_mpi=False,
                                    timeout=30, capture_output=True, text=True, required_disk_gb=.01)
    assert json.loads(preserved.stdout) == {"OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "1"}
    ordinary_mpi = safe_subprocess_run(command, cwd=tmp_path, env=environment, sanitize_mpi=True,
                                       timeout=30, capture_output=True, text=True, required_disk_gb=.01)
    assert json.loads(ordinary_mpi.stdout) == {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}


def test_first_observation_cannot_replace_the_authorized_runtime_seal():
    # Digests of actual different repository files exercise the identity boundary;
    # neither file is presented as a quantum binary or scientific checkpoint.
    source = Path(__file__).resolve()
    previous = hashlib.sha256(source.read_bytes()).hexdigest()
    changed = hashlib.sha256((source.parent / "test_scientific_job_boundaries.py").read_bytes()).hexdigest()
    assert previous != changed
    _require_authorized_runtime_seal(previous, previous)
    with pytest.raises(RegistryAuthorityViolationError, match="authorized Stage 0"):
        _require_authorized_runtime_seal(previous, changed)
    with pytest.raises(RegistryAuthorityViolationError, match="authorized Stage 0"):
        _require_authorized_runtime_seal(None, changed)


def test_pre_cancelled_cfour_request_uses_the_brokers_cancellation_type(tmp_path):
    cancelled = threading.Event()
    cancelled.set()
    directory = tmp_path / "cancelled-cfour"
    # Cancellation precedes runtime discovery/authorization, so no authority or
    # installed CFOUR is needed and no substitute engine is invoked.
    with pytest.raises(SubprocessCancelledError):
        execute_cfour(request(), ["H", "H"], [[0, 0, 0], [0, 0, .74]], directory=directory,
                      authority=None, environment={}, cancellation_event=cancelled)
    assert not directory.exists()


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
