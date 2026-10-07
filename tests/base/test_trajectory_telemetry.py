"""Real trajectory records and real ASE calculations exercise incremental publication."""
from __future__ import annotations

import io
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import pytest
from ase import Atoms
from ase.calculators.emt import EMT
from ase.io import write
from scipy.constants import physical_constants

from cochem_base.core_engine.scientific_telemetry import read_scientific_results
from cochem_base.core_engine.trajectory_telemetry import (
    IncompleteTrajectoryError,
    TrajectoryFormatError,
    XYZTrajectoryFollower,
    parse_xyz_frame,
)


_FIXTURE = Path(__file__).parents[1] / "fixtures/trajectories/xtb-6.7.1-water-optimization.xyz"


def _xtb_frames():
    lines = _FIXTURE.read_bytes().splitlines(keepends=True)
    return [b"".join(lines[index:index + 5]) for index in range(0, len(lines), 5)]


def _ase_frame():
    atoms = Atoms("Cu2", positions=[[0.0, 0.0, 0.0], [2.5, 0.0, 0.0]], calculator=EMT())
    energy_ev = atoms.get_potential_energy()
    atoms.get_forces()
    atoms.info["energy_unit"] = "eV"
    stream = io.StringIO()
    write(stream, atoms, format="extxyz")
    return stream.getvalue(), energy_ev


def test_native_xtb_frames_publish_original_energy_coordinates_and_provenance(tmp_path):
    store = tmp_path / "complexes.h5"
    follower = XYZTrajectoryFollower(_FIXTURE, "water", ["O", "H", "H"], source_format="xtb", store_path=store)
    assert follower.poll_once() == 5
    assert follower.poll_once() == 0
    assert follower.stop()["state"] == "stopped"
    records = read_scientific_results("water", store_path=store)
    assert len(records["energy_hartree"]) == 5
    assert records["energy_hartree"][0] == pytest.approx(-5.070222286727, abs=1e-12)
    assert records["energy_hartree"][-1] == pytest.approx(-5.070544444754, abs=1e-12)
    np.testing.assert_array_equal(records["coordinates_angstrom"][0], parse_xyz_frame(_xtb_frames()[0], elements=["O", "H", "H"], source_format="xtb").coordinates_angstrom)
    assert len(records["gradients_hartree_per_bohr"]) == 0
    assert records["metadata"][0]["trajectory_source"]["energy_unit_authority"] == "xtb_native_protocol"


def test_partial_frames_wait_and_resume_and_truncation_do_not_duplicate(tmp_path):
    first, second = _xtb_frames()[:2]
    path, store = tmp_path / "xtbopt.log", tmp_path / "complexes.h5"
    path.write_bytes(first[:-12])
    follower = XYZTrajectoryFollower(path, "water", ["O", "H", "H"], source_format="xtb", store_path=store)
    assert follower.poll_once() == 0
    assert follower.status["pending_bytes"] > 0
    with path.open("ab") as output:
        output.write(first[-12:] + second)
    assert follower.poll_once() == 2
    path.write_bytes(first)
    assert follower.poll_once() == 0
    with path.open("ab") as output:
        output.write(second + first)
    assert follower.poll_once() == 1  # A repeated physical frame at a later step is a new observation.
    assert follower.status["file_generations"] == 2
    follower.stop()
    restarted = XYZTrajectoryFollower(path, "water", ["O", "H", "H"], source_format="xtb", store_path=store)
    assert restarted.poll_once() == 0
    assert restarted.status["duplicates_skipped"] == 3
    restarted.stop()
    assert len(read_scientific_results("water", store_path=store)["energy_hartree"]) == 3


def test_ase_energy_conversion_requires_explicit_units_and_ignores_unmeasured_gradients(tmp_path):
    text, energy_ev = _ase_frame()
    parsed = parse_xyz_frame(text, elements=["Cu", "Cu"], source_format="extxyz")
    assert parsed.energy_hartree == pytest.approx(energy_ev / physical_constants["Hartree energy in eV"][0], abs=1e-14)
    unknown = text.replace("energy_unit=eV", "")
    with pytest.raises(TrajectoryFormatError, match="explicit"):
        parse_xyz_frame(unknown, elements=["Cu", "Cu"], source_format="extxyz")
    declared = parse_xyz_frame(unknown, elements=["Cu", "Cu"], source_format="extxyz", energy_unit="eV")
    assert declared.unit_authority == "caller"
    with pytest.raises(TrajectoryFormatError, match="disagree"):
        parse_xyz_frame(text, elements=["Cu", "Cu"], source_format="extxyz", energy_unit="Hartree")
    path = tmp_path / "ase.xyz"
    path.write_text(text)
    follower = XYZTrajectoryFollower(path, "copper", ["Cu", "Cu"], source_format="extxyz", store_path=tmp_path / "complexes.h5")
    follower.stop()
    records = read_scientific_results("copper", store_path=tmp_path / "complexes.h5")
    # ASE forces are not mislabeled or silently converted to Eh/bohr gradients.
    assert len(records["gradients_hartree_per_bohr"]) == 0


@pytest.mark.parametrize("mutation,match", [
    (lambda data: data.replace(b"-5.070222286727", b"nan"), "finite"),
    (lambda data: data.replace(b"O            ", b"C            "), "identities"),
    (lambda data: data.replace(b"0.06673584615717", b"inf"), "finite"),
    (lambda data: data.replace(b"energy:", b"unlabeled:"), "energy"),
    (lambda data: data.replace(b"gnorm:", b"energy_unit=eV gnorm:"), "Hartree"),
    (lambda data: data.replace(b"gnorm:", b"coordinates_unit=bohr gnorm:"), "Angstrom"),
])
def test_corrupted_complete_frames_are_rejected(mutation, match):
    with pytest.raises(TrajectoryFormatError, match=match):
        parse_xyz_frame(mutation(_xtb_frames()[0]), elements=["O", "H", "H"], source_format="xtb")


def test_incomplete_tail_and_missing_required_file_are_explicit(tmp_path):
    path = tmp_path / "xtbopt.log"
    path.write_bytes(_xtb_frames()[0][:-5])
    follower = XYZTrajectoryFollower(path, "incomplete", ["O", "H", "H"], source_format="xtb", store_path=tmp_path / "complexes.h5")
    with pytest.raises(IncompleteTrajectoryError):
        follower.stop()
    assert follower.status["state"] == "error"
    assert follower.status["pending_bytes"] > 0
    missing = XYZTrajectoryFollower(tmp_path / "absent.xyz", "missing", ["H"], source_format="orca", store_path=tmp_path / "complexes.h5", required=True)
    with pytest.raises(FileNotFoundError, match="Required"):
        missing.stop()


def test_original_engine_exception_survives_telemetry_failure_and_callback_runs(tmp_path):
    path = tmp_path / "xtbopt.log"
    errors = []
    follower = XYZTrajectoryFollower(path, "failed-engine", ["O", "H", "H"], source_format="xtb", store_path=tmp_path / "complexes.h5", on_error=errors.append)
    with pytest.raises(RuntimeError, match="actual producer failed") as caught:
        with follower:
            path.write_bytes(_xtb_frames()[0].replace(b"-5.070222286727", b"nan"))
            raise RuntimeError("actual producer failed")
    assert errors and isinstance(errors[0], TrajectoryFormatError)
    assert follower.error_event.is_set()
    assert any("Trajectory telemetry also failed" in note for note in caught.value.__notes__)


def test_documented_orca_native_comment_uses_hartree_without_claiming_engine_execution():
    # Parsing-only syntax check; coordinates/energy originate in the real xTB fixture.
    # Relabeling this comment does not make its energy an ORCA reference calculation.
    lines = _xtb_frames()[0].decode().splitlines()
    energy = lines[1].split()[1]
    lines[1] = f"Coordinates from ORCA-job parser-syntax-only E {energy}"
    frame = parse_xyz_frame("\n".join(lines) + "\n", elements=["O", "H", "H"], source_format="orca")
    assert frame.energy_hartree == float(energy)
    assert frame.unit_authority == "orca_native_protocol"


def test_external_ase_process_is_observed_before_it_finishes(tmp_path):
    path, release, store = tmp_path / "trajectory.xyz", tmp_path / "release", tmp_path / "complexes.h5"
    script = '''
import pathlib, sys, time
from ase import Atoms
from ase.calculators.emt import EMT
from ase.io import write
path, release = map(pathlib.Path, sys.argv[1:])
with path.open("w") as output:
    for step, distance in enumerate((2.4, 2.5, 2.6)):
        atoms = Atoms("Cu2", positions=[[0, 0, 0], [distance, 0, 0]], calculator=EMT())
        atoms.get_potential_energy()
        atoms.info["energy_unit"] = "eV"
        write(output, atoms, format="extxyz")
        output.flush()
        if step == 0:
            deadline = time.monotonic() + 15
            while not release.exists():
                if time.monotonic() > deadline:
                    raise RuntimeError("Observer did not receive the first real ASE energy")
                time.sleep(.01)
'''
    follower = XYZTrajectoryFollower(path, "live-ase", ["Cu", "Cu"], source_format="extxyz", store_path=store, poll_interval=0.01, required=True)
    process = None
    try:
        with follower:
            process = subprocess.Popen([sys.executable, "-c", script, str(path), str(release)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            deadline = time.monotonic() + 12
            while follower.status["frames_published"] < 1 and not follower.error_event.is_set():
                assert time.monotonic() < deadline
                assert process.poll() is None
                time.sleep(0.01)
            assert not follower.error_event.is_set(), follower.status
            assert process.poll() is None  # The real calculator process is still active.
            assert len(read_scientific_results("live-ase", store_path=store)["energy_hartree"]) == 1
            release.touch()
            _, stderr = process.communicate(timeout=12)
            assert process.returncode == 0, stderr.decode()
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
    assert follower.status["frames_published"] == 3
    assert follower.status["state"] == "stopped"
