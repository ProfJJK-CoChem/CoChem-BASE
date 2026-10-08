"""Native execution ingress, recipe trajectory and explicit method contracts."""
from pathlib import Path
import json
import os
import subprocess
import sys

import pytest

from cochem_base.calc.calculation_service import _engine_environment, validate_frozen_monomer_trajectory
from cochem_base.calc.cochem_calc_input_generator import MoleculeInput, generate_pyscf_input
from cochem_base.exceptions import GridSpecificationError, TrajectoryDriftViolationError


@pytest.mark.parametrize("engine,threads,expected", [("orca", 2, "1"), ("orca", 1, "1"), ("xtb", 2, "2"), ("pyscf", 2, "2")])
def test_engine_thread_budget_reaches_real_process_without_inherited_oversubscription(
    engine: str, threads: int, expected: str,
) -> None:
    variables = ["OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"]
    if engine == "orca":
        variables += ["VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS"]
    inherited = {**os.environ, **dict.fromkeys(variables, "64")}
    environment = _engine_environment(engine, threads, inherited)
    # A real Python child observes execution settings. It is not a chemistry
    # engine and supplies no fabricated energy or quantum output.
    completed = subprocess.run(
        [sys.executable, "-I", "-c", "import json,os,sys; print(json.dumps({k:os.environ[k] for k in sys.argv[1:]}))", *variables],
        env=environment, capture_output=True, text=True, check=True, timeout=15,
    )
    assert json.loads(completed.stdout) == dict.fromkeys(variables, expected)
    assert all(inherited[name] == "64" for name in variables)


@pytest.mark.parametrize("middle_stretch", [0.0, 2e-6])
def test_full_trajectory_drift_detects_recovered_final_geometry(tmp_path: Path, middle_stretch: float) -> None:
    initial = [[0, 0, 0], [0, 0, 0.74], [0, 0, 4], [0, 0, 4.74]]
    middle = [[0, 0, 0], [0, 0, 0.74 + middle_stretch], [0, 0, 4], [0, 0, 4.74]]
    path = tmp_path / "trajectory.xyz"
    path.write_text("\n".join(["4", "trajectory"] + ["H " + " ".join(str(v) for v in xyz) for xyz in middle]) + "\n")
    if middle_stretch:
        with pytest.raises(TrajectoryDriftViolationError):
            validate_frozen_monomer_trajectory(path, ["H"] * 4, initial, initial)
    else:
        result = validate_frozen_monomer_trajectory(path, ["H"] * 4, initial, initial)
        assert result["maximum_internal_drift_angstrom"] == 0


def test_pyscf_never_substitutes_requested_dft_method(tmp_path: Path) -> None:
    molecule = MoleculeInput(basin_id="water", elements=["H", "H"], coordinates=[(0, 0, 0), (0, 0, 0.74)],
                             theory_level="PBE0 D4 def2-SVP", is_opt=False)
    with pytest.raises(ValueError, match="silently translated"):
        generate_pyscf_input(molecule, tmp_path)
    assert not list(tmp_path.iterdir())


def test_explicit_pyscf_hf_deck_runs_requested_basis(tmp_path: Path) -> None:
    interpreter = Path(os.environ.get("COCHEM_PYSCF_PYTHON", "/workspace/cochem-silos/pyscf/bin/python"))
    if not interpreter.is_file():
        pytest.skip("A real isolated PySCF interpreter is required")
    molecule = MoleculeInput(basin_id="hydrogen", elements=["H", "H"], coordinates=[(0, 0, 0), (0, 0, 0.74)],
                             theory_level="HF sto-3g", is_opt=False)
    deck = generate_pyscf_input(molecule, tmp_path)
    completed = subprocess.run([str(interpreter), "-I", str(deck)], cwd=tmp_path, capture_output=True, text=True,
                               env={**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}, timeout=60)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(deck.with_suffix(".result.json").read_text())
    assert result["method"] == "RHF" and result["basis"] == "sto-3g"
    assert result["scf_converged"] is True and result["energy_hartree"] < -1


def test_production_tier_cannot_request_low_quadrature() -> None:
    with pytest.raises(GridSpecificationError):
        MoleculeInput(basin_id="water", elements=["H", "H"], coordinates=[(0, 0, 0), (0, 0, 0.74)],
                      theory_level="wB97M-V def2-TZVP DEFGRID1", tier=5)


def test_composite_method_cannot_silently_change_basis() -> None:
    from cochem_base.calc.calculation_service import CalculationMatrixConfig
    geometry = "H 0 0 0\nH 0 0 0.74"
    config = CalculationMatrixConfig(geometry=geometry, method="r2SCAN-3c")
    assert config.basis_set is None
    with pytest.raises(ValueError, match="built-in composite basis"):
        CalculationMatrixConfig(geometry=geometry, method="r2SCAN-3c", basis_set="def2-TZVP")
    with pytest.raises(ValueError, match="built-in composite basis"):
        MoleculeInput(basin_id="hydrogen", elements=["H", "H"], coordinates=[(0, 0, 0), (0, 0, 0.74)],
                      theory_level="r2SCAN-3c def2-SVP")


def test_open_shell_native_admission_requires_scientific_t9_before_process(tmp_path: Path) -> None:
    from cochem_base.calc.calculation_service import CalculationMatrixConfig, run_calculation

    # The bent H3 starting geometry is an input, not a fabricated quantum result.
    # Portable configuration can be serialized before the remote worker binds its
    # audited PySCF executable; a physical native run must already have that bind.
    values = dict(geometry="H 0 0 0\nH 0 0 0.9\nH 0.7 0 1.4", engine="orca",
                  method="UHF", basis_set="6-31g", multiplicity=2, is_opt=False)
    configuration = CalculationMatrixConfig(**values)
    assert configuration.t9_fallback is None
    source = tmp_path / "request.json"
    source.write_text(configuration.model_dump_json())
    with pytest.raises(ValueError, match="explicit T9 active space"):
        run_calculation(source, scratch=tmp_path / "scratch", output=tmp_path / "results")
    assert not (tmp_path / "scratch").exists()
    assert not (tmp_path / "results").exists()
