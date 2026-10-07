"""TORQ must preserve absent evidence and must own the processes it reaps.

These are negative integrity checks and one genuine ASE calculation. They do
not impersonate an ORCA run or establish native GBW/ORCA acceptance.
"""
from pathlib import Path
import os
import subprocess
import sys

from ase import units
from ase.build import molecule
from ase.calculators.emt import EMT
import pytest
from pydantic import ValidationError

from cochem_base.cochem_torq_engine import (
    DispatchPayload,
    ExecutionContext,
    ORCAStepResult,
    SCFResult,
    _parse_orca_engrad_or_output,
    dynamic_wavefunction_propagation,
)


def test_real_emt_energy_does_not_imply_unreported_convergence() -> None:
    atoms = molecule("H2O")
    atoms.calc = EMT()
    measured_energy = atoms.get_potential_energy() / units.Hartree
    scf = SCFResult(point_idx=0, energy_hartree=measured_energy, coordinates=atoms.positions)
    step = ORCAStepResult(energy=measured_energy, coordinates=atoms.positions)
    assert scf.converged is None
    assert scf.vram_used_mb is None
    assert step.converged is None
    with pytest.raises(ValidationError):
        ORCAStepResult(coordinates=atoms.positions)
    with pytest.raises(ValidationError):
        ORCAStepResult(energy=measured_energy, coordinates=atoms.positions, converged="true")
    with pytest.raises(ValidationError):
        SCFResult(point_idx=0, energy_hartree=float("nan"), coordinates=atoms.positions)


def test_missing_and_invalid_output_cannot_become_zero_energy_or_gradient(tmp_path: Path) -> None:
    output_path = tmp_path / "missing.engrad"
    for text in ("", "ORCA TERMINATED NORMALLY", "FINAL SINGLE POINT ENERGY -1.0\nORCA TERMINATED NORMALLY"):
        with pytest.raises(ValueError, match="lacks complete"):
            _parse_orca_engrad_or_output(output_path, text, 1)
    output_path.write_text("# deliberately incomplete input for rejection\n1\n-1.0\n0.0\n")
    with pytest.raises(ValueError, match="incomplete"):
        _parse_orca_engrad_or_output(output_path, "", 1)
    output_path.write_text("1\nnan\n0\n0\n0\n")
    with pytest.raises(ValueError, match="finite"):
        _parse_orca_engrad_or_output(output_path, "", 1)


def test_tensor_archive_cannot_be_mislabeled_as_gbw(tmp_path: Path) -> None:
    atoms = molecule("H2O")
    atoms.calc = EMT()
    result = ORCAStepResult(energy=atoms.get_potential_energy() / units.Hartree,
                           coordinates=atoms.positions)
    payload = DispatchPayload(symbols=atoms.get_chemical_symbols(), coordinates=atoms.positions)
    context = ExecutionContext(custom_shm_dir=tmp_path / "shm", custom_artifacts_dir=tmp_path / "artifacts")
    with pytest.raises(ValueError, match="requires a nonempty"):
        dynamic_wavefunction_propagation(result, payload, context)
    for invalid_checkpoint in (b"\x89HDF\r\n\x1a\n", b"ORCA_GBW_CHECKPOINT_SEED_V61\n"):
        result.gbw_bytes = invalid_checkpoint
        with pytest.raises(ValueError, match="not an ORCA GBW"):
            dynamic_wavefunction_propagation(result, payload, context)
    assert not list((tmp_path / "shm").glob("*.gbw"))


def test_cleanup_reaps_owned_handle_and_preserves_other_callers_child(tmp_path: Path) -> None:
    program = '''
import subprocess, sys
from cochem_base.cochem_torq_engine import register_spawned_process, cleanup_all_cochem_processes
owned = subprocess.Popen([sys.executable, '-c', 'import sys; sys.stdin.readline()'], stdin=subprocess.PIPE, text=True)
unrelated = subprocess.Popen([sys.executable, '-c', 'import sys; sys.stdin.readline()'], stdin=subprocess.PIPE, text=True)
try:
    register_spawned_process(owned.pid, owned)
    cleanup_all_cochem_processes()
    assert owned.poll() is not None
    assert unrelated.poll() is None
finally:
    unrelated.communicate(input='done\\n', timeout=5)
    if owned.poll() is None:
        owned.kill()
    owned.wait(timeout=5)
'''
    completed = subprocess.run([sys.executable, "-c", program], cwd=tmp_path, env=os.environ.copy(),
                               capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stdout + completed.stderr
