"""Real micro-silo CASSCF/NEVPT2 recovery and strict scientific input checks."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import pytest

from cochem_base.analysis.electronic_sanitizer import SpinContaminationStreamValidator
from cochem_base.calc.t9_fallback import T9FallbackConfig, execute_with_t9_fallback, run_t9_fallback
from cochem_base.core_engine.cochem_core_subprocess_broker import safe_subprocess_run
from cochem_base.exceptions import SpinContaminationError


def config(**changes) -> T9FallbackConfig:
    values = dict(
        python_executable=os.environ.get("COCHEM_PYSCF_PYTHON", "/workspace/cochem-silos/pyscf/bin/python"),
        basis="6-31g", active_electrons=3, active_orbitals=[0, 1, 2],
        active_space_rationale="All three 1s-derived MOs and three electrons of neutral H3; full valence CAS",
        timeout_seconds=120,
    )
    values.update(changes)
    return T9FallbackConfig(**values)


def require_pyscf() -> None:
    if not config().python_executable.is_file():
        pytest.skip("Set COCHEM_PYSCF_PYTHON to the pinned isolated PySCF interpreter")


@pytest.fixture
def audited_pyscf_registry(tmp_path: Path):
    from cochem_base.config_loader import resolve_config_path
    from cochem_base.core_engine.execution_authority import authorize_engine_execution
    interpreter = config().python_executable
    if interpreter.is_file():
        # Reuse the actual eleven-phase authority on this machine. An executable
        # hash alone cannot establish the isolated interpreter's package contract.
        source = resolve_config_path(os.environ.get("COCHEM_ACCEPTANCE_REGISTRY"))
        authorize_engine_execution("pyscf", registry_path=source, executable=interpreter,
                                   cores=1, maxcore_mb=1024)
        path = tmp_path / "golden_registry.json"
        path.write_bytes(source.read_bytes())
        return path


@pytest.mark.parametrize("changes", [
    {"active_orbitals": [0, 0]}, {"active_orbitals": [-1, 0]},
    {"active_electrons": 7}, {"active_electrons": True},
    {"active_space_rationale": " "}, {"python_executable": "python"},
])
def test_active_space_cannot_be_invented_or_ambiguous(changes) -> None:
    with pytest.raises(ValueError):
        config(**changes)


def test_absent_active_space_preserves_typed_rejection(tmp_path: Path) -> None:
    error = SpinContaminationError("rejected", details={"routing_tier": "T9"})

    def primary():
        raise error

    with pytest.raises(SpinContaminationError) as caught:
        execute_with_t9_fallback(primary, None, directory=tmp_path / "t9")
    assert caught.value is error
    assert not (tmp_path / "t9").exists()


def test_other_failures_never_trigger_recovery(tmp_path: Path) -> None:
    def primary():
        raise RuntimeError("engine unavailable")

    with pytest.raises(RuntimeError, match="engine unavailable"):
        execute_with_t9_fallback(primary, config(), directory=tmp_path / "t9")
    assert not (tmp_path / "t9").exists()


def test_charge_and_active_spin_must_be_compatible(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="molecular charge and spin"):
        run_t9_fallback(
            config(active_electrons=2), elements=["H", "H", "H"],
            coordinates=[[0, 0, 0], [0, 0, 0.9], [0.7, 0, 1.4]],
            charge=0, multiplicity=2, directory=tmp_path / "t9",
            trigger=SpinContaminationError("rejected"),
        )
    assert not (tmp_path / "t9").exists()


@pytest.mark.parametrize("method", ["CASSCF", "NEVPT2"])
@pytest.mark.parametrize("coordinates", [
    [[0, 0, 0], [0, 0, 0.9], [0.7, 0, 1.4]],
    [[0, 0, -2], [0, 0, 0], [0, 0, 2.1]],
], ids=["bent-h3", "stretched-linear-h3"])
def test_actual_h3_recovery_after_live_contamination(method: str, coordinates, tmp_path: Path, audited_pyscf_registry: Path) -> None:
    """A telemetry transport fixture triggers a real H3 CAS(3,3) calculation.

    The diagnostic emitter is not an ORCA substitute or quantum benchmark; all
    recovery energies and spin values below come from the installed PySCF engine.
    """
    require_pyscf()
    continued = tmp_path / "continued"

    def primary():
        safe_subprocess_run(
            [sys.executable, "-c", "import pathlib,sys,time; print('Expectation value of <S**2> : 0.825', flush=True); time.sleep(30); pathlib.Path(sys.argv[1]).touch()", str(continued)],
            cwd=tmp_path, timeout=10, required_disk_gb=0,
            on_stdout_line=SpinContaminationStreamValidator(2),
        )

    result = execute_with_t9_fallback(
        primary, config(method=method), elements=["H", "H", "H"],
        coordinates=coordinates,
        charge=0, multiplicity=2, directory=tmp_path / "t9",
        registry_path=audited_pyscf_registry,
    )
    assert not continued.exists()
    assert result["status"] == "T9_FALLBACK_VERIFIED"
    assert result["method"] == method
    assert result["spin_square"] == pytest.approx(0.75, abs=1e-8)
    assert result["energy_hartree"] < -1
    if method == "NEVPT2":
        assert result["nevpt2_correction_hartree"] < 0
    assert result["scf_converged"] is True and result["casscf_converged"] is True
    assert result["convergence_settings"]["ci_solver_tolerance"] == 1e-12
    assert result["convergence_settings"]["casscf_orbital_gradient"] == 1e-6
    assert result["operation"] == "single_point"
    rejected = json.loads((tmp_path / "t9/rejected_single_reference.json").read_text())
    assert rejected["status"] == "REJECTED"
    assert rejected["details"]["routing_tier"] == "T9"
    assert (tmp_path / "t9/t9_verified.json").is_file()
    assert "SCF converged" in (tmp_path / "t9/stdout.log").read_text()


def test_wrong_engine_version_fails_without_verified_result(tmp_path: Path, audited_pyscf_registry: Path) -> None:
    require_pyscf()
    with pytest.raises(RuntimeError, match="failed"):
        run_t9_fallback(
            config(pyscf_version="0.0.0"), elements=["H", "H", "H"],
            coordinates=[[0, 0, 0], [0, 0, 0.9], [0.7, 0, 1.4]],
            charge=0, multiplicity=2, directory=tmp_path / "t9",
            trigger=SpinContaminationError("rejected"),
            registry_path=audited_pyscf_registry,
        )
    assert not (tmp_path / "t9/t9_verified.json").exists()
    assert "version drift" in (tmp_path / "t9/stderr.log").read_text()


def test_native_service_routes_live_failure_and_publishes_real_t9(tmp_path: Path) -> None:
    """Real ORCA UHF contamination must trigger real CAS(3,3)/NEVPT2 recovery.

    Free-only CI reports the licensed-engine prerequisite explicitly. The
    separately named transport tests above exercise early cancellation without
    registering their diagnostic emitter as a scientific engine.
    """
    from cochem_base.calc.calculation_service import run_calculation
    from cochem_base.core_engine.scientific_telemetry import read_scientific_results
    from scripts.verify_orca_scientific import verify_t9

    prerequisite = "Real licensed ORCA and an audited ORCA/PySCF registry are required for end-to-end T9 acceptance"
    binding = os.environ.get("COCHEM_CONFIG")
    if not binding or not Path(binding).is_file():
        pytest.skip(prerequisite)
    registry_path = Path(binding)
    engines = json.loads(registry_path.read_text()).get("engines", {})
    if any(engines.get(name, {}).get("status") not in {"found", "ready"} for name in ("orca", "pyscf")):
        pytest.skip(prerequisite)
    # Once installations are declared available, missing files, changed hashes,
    # invalid authority and scientific failures must fail rather than skip.
    config_path = tmp_path / "calculation.json"
    config_path.write_text(json.dumps({
        "geometry": "H 0 0 -2\nH 0 0 0\nH 0 0 2.1", "engine": "orca", "method": "UHF",
        "basis_set": "6-31g", "multiplicity": 2, "is_opt": False, "timeout_seconds": 180,
        "t9_fallback": config(python_executable=engines["pyscf"]["path"]).model_dump(mode="json"),
    }))
    events = []
    result = run_calculation(config_path, scratch=tmp_path / "scratch", output=tmp_path / "published",
                             threads=1, maxcore_mb=1024, on_event=events.append, registry_path=registry_path)
    assert result["status"] == "T9_FALLBACK_VERIFIED"
    assert result["engine"] == "pyscf" and result["requested_engine"] == "orca"
    assert result["original_single_reference_rejected"] is True
    assert (tmp_path / "published/t9/t9_verified.json").is_file()
    assert not list((tmp_path / "published").glob("*_qcschema.json"))
    assert any(event.get("status") == "RUNNING" for event in events)
    assert any(event.get("status") == "T9_FALLBACK_VERIFIED" for event in events)
    evidence = verify_t9(tmp_path / "published", engines["orca"]["hash"], engines["pyscf"]["hash"])
    assert evidence["primary_rejected"] is True
    assert evidence["recovery"]["spin_square"] == pytest.approx(0.75, abs=1e-6)
    fallback = result["fallback"]
    telemetry = read_scientific_results(fallback["telemetry_job_id"], store_path=fallback["telemetry_path"])
    assert telemetry["energy_hartree"][0] == fallback["energy_hartree"]
    assert telemetry["metadata"][0]["tier"] == "T9"


def test_native_pyscf_rhf_energy_and_gradient_are_real(tmp_path: Path, audited_pyscf_registry: Path) -> None:
    require_pyscf()
    from cochem_base.calc.calculation_service import run_calculation
    from cochem_base.core_engine.scientific_telemetry import read_scientific_results

    path = tmp_path / "rhf.json"
    path.write_text(json.dumps({"geometry": "H 0 0 0\nH 0 0 0.74", "engine": "pyscf",
                                "method": "RHF", "basis_set": "sto-3g", "is_opt": False, "theory_tier": "T2"}))
    result = run_calculation(path, scratch=tmp_path / "scratch", output=tmp_path / "rhf_results", threads=1,
                             registry_path=audited_pyscf_registry)
    assert result["status"] == "EXECUTION_VERIFIED" and result["engine"] == "pyscf"
    actual = json.loads((tmp_path / "rhf_results/result.json").read_text())
    assert actual["energy_hartree"] < -1 and actual["scf_converged"] is True
    telemetry = read_scientific_results(actual["telemetry_job_id"], store_path=actual["telemetry_path"])
    assert telemetry["gradients_hartree_per_bohr"].shape == (1, 2, 3)
    assert telemetry["energy_hartree"][0] == actual["energy_hartree"]
