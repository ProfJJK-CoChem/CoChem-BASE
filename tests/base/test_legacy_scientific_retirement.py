"""Shipped compatibility paths cannot manufacture scientific observations."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

import h5py
import numpy as np
import pytest

from cochem_base.intake.structure_formats import parse_structure_text
from cochem_mobile.core.architecture import IngressValidationError, JobSubmission, MobileCloudEngine
from cochem_mobile.core.sandbox_broker import ContainerEngine
from cochem.runners.async_process_runner import AsyncProcessRunner


WATER = Path(__file__).parents[1] / "data/orca_6_1_1_water_hf_sto3g/water.xyz"


def _submission(engine, operation, **changes):
    record = parse_structure_text(WATER.read_text(), "xyz")[0]
    session = engine.session_manager.create_session()
    values = dict(symbols=record["symbols"], coordinates=record["coords"].tolist(),
                  calculation_type=operation, session_id=session.session_id)
    values.update(changes)
    return JobSubmission(**values), session, record


@pytest.mark.parametrize("operation", ["spectral_fit", "energy", "harmonic"])
def test_unconnected_mobile_science_is_rejected_without_process_or_energy(tmp_path, operation):
    engine = MobileCloudEngine(tmp_path / "runtime", preferred_engine=ContainerEngine.SUBPROCESS)
    try:
        submission, session, _ = _submission(engine, operation)
        with pytest.raises(IngressValidationError, match="canonical CoChem-BASE"):
            engine.submit_job(submission, auth_token=session.auth_token)
        assert not list(engine.sandboxes_dir.iterdir())
        assert engine.wal.read_records() == []
        assert engine.hdf5_writer.read_reader_mode()["energies"].size == 0
    finally:
        engine.close()


def test_mobile_structural_com_retains_exact_masses_without_scientific_energy(tmp_path):
    engine = MobileCloudEngine(tmp_path / "runtime", preferred_engine=ContainerEngine.SUBPROCESS)
    try:
        submission, session, record = _submission(engine, "center_of_mass")
        result = engine.submit_job(submission, auth_token=session.auth_token)
        assert result.status == "completed" and result.scientific_execution_performed is False
        output = json.loads(result.execution_result.stdout)
        assert output["operation"] == "center_of_mass" and output["energy_hartree"] is None
        masses = np.asarray(record["atomic_masses_daltons"])
        np.testing.assert_allclose(output["com"], np.sum(record["coords"] * masses[:, None], axis=0) / masses.sum(), atol=1e-15)
        stored = engine.hdf5_writer.read_reader_mode()
        assert stored["energies"].size == 0
        np.testing.assert_array_equal(stored["atomic_masses"], masses)
        assert engine.wal.read_records()[-1].payload["energy_hartree"] is None
    finally:
        engine.close()


def test_mobile_job_identity_cannot_redirect_its_runtime_files(tmp_path):
    engine = MobileCloudEngine(tmp_path / "runtime", preferred_engine=ContainerEngine.SUBPROCESS)
    try:
        submission, session, _ = _submission(engine, "center_of_mass", job_id="../../escaped")
        with pytest.raises(IngressValidationError, match="canonical UUID"):
            engine.submit_job(submission, auth_token=session.auth_token)
        assert not list(engine.sandboxes_dir.iterdir())
        assert not (tmp_path / "escaped").exists()
    finally:
        engine.close()


def test_generic_process_completion_cannot_publish_zero_as_measured_energy(tmp_path):
    source, artifacts, scratch = (tmp_path / name for name in ("source", "artifacts", "scratch"))
    source.mkdir()
    with AsyncProcessRunner(source, artifacts, scratch) as runner:
        # A real diagnostic child supplies no quantum result; completion timing
        # belongs to process telemetry with explicitly unavailable energy.
        result = asyncio.run(runner.dispatch_task("diagnostic", [sys.executable, "-c", "print('actual process diagnostics')"], cleanup_on_completion=False))
        assert result["exit_code"] == 0 and result["stdout"].strip() == "actual process diagnostics"
        with h5py.File(result["telemetry_file"], "r", swmr=True) as stream:
            assert np.isnan(stream["telemetry/energy"][0])
            assert not bool(stream["telemetry/energy_available"][0])
            assert float(stream["telemetry/walltime"][0]) == result["elapsed_seconds"]


@pytest.mark.parametrize("task_name", ["../outside", "/absolute", "a/b", "..", ""])
def test_generic_job_identifier_cannot_redirect_creation_or_cleanup(task_name, tmp_path):
    source, artifacts, scratch = (tmp_path / name for name in ("source", "artifacts", "scratch"))
    source.mkdir()
    with AsyncProcessRunner(source, artifacts, scratch) as runner:
        with pytest.raises(ValueError, match="task identifier"):
            asyncio.run(runner.dispatch_task(task_name, [sys.executable, "-c", "print('diagnostics')"]))
        with pytest.raises(ValueError, match="task identifier"):
            runner.cleanup_scratch(task_name)
        assert list(scratch.iterdir()) == []


def test_generic_runner_preserves_unowned_and_preexisting_job_inputs(tmp_path):
    source, artifacts, scratch = (tmp_path / name for name in ("source", "artifacts", "scratch"))
    source.mkdir()
    scratch.mkdir()
    other = scratch / "another-students-result"
    other.mkdir()
    retained = other / "original.xyz"
    original = WATER.read_bytes()
    retained.write_bytes(original)
    with AsyncProcessRunner(source, artifacts, scratch) as runner:
        with pytest.raises(FileExistsError):
            asyncio.run(runner.dispatch_task(other.name, [sys.executable, "-c", "print('diagnostics')"]))
        runner.cleanup_scratch(other.name)
        runner.cleanup_scratch()
        assert retained.read_bytes() == original
    assert retained.read_bytes() == original


@pytest.mark.parametrize("layout", [("source", "source/artifacts", "scratch"), ("source", "artifacts", "artifacts/scratch"), ("source", "artifacts", "source")])
def test_generic_runner_rejects_overlapping_planes_before_creating_outputs(layout, tmp_path):
    roots = [tmp_path / value for value in layout]
    with pytest.raises(PermissionError, match="must not overlap"):
        AsyncProcessRunner(*roots)
    assert list(tmp_path.iterdir()) == []
