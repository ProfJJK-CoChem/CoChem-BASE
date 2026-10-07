"""Classroom request boundaries; these tests do not replace real ORCA execution."""
import json
from pathlib import Path

import pytest

from cochem_base.exceptions import MethodMatrixViolationError
from scripts.run_actions_calculation import (
    MAX_JOB_BYTES, preflight_configuration, read_job_file, run_job,
    validate_configuration, validate_resources,
)

ROOT = Path(__file__).resolve().parents[2]


def water(**changes):
    data = json.loads((ROOT / "examples/jobs/water-single-point.json").read_text())
    data.update(changes)
    return data


def validate(data):
    return validate_configuration(json.dumps(data).encode(), data)


@pytest.mark.parametrize("name", ["water-single-point.json", "water-optimization.json", "water-harmonic.json"])
def test_committed_examples_are_native_embedded_geometry_jobs(name):
    _, contents, data = read_job_file(ROOT, "examples/jobs/" + name)
    config = validate_configuration(contents, data)
    assert config.engine == "orca" and config.timeout_seconds <= 1800


@pytest.mark.parametrize("path", ["../escape.json", "/tmp/escape.json", "nested/../job.json", "./job.json", "job.inp", "nested\\job.json"])
def test_input_path_cannot_escape_checkout_or_submit_raw_deck(tmp_path, path):
    with pytest.raises(ValueError, match="repository-relative"):
        read_job_file(tmp_path, path)


def test_symlink_file_and_symlink_directory_are_rejected(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    (actual / "job.json").write_text(json.dumps(water()))
    (tmp_path / "linked").symlink_to(actual, target_is_directory=True)
    (tmp_path / "linked.json").symlink_to(actual / "job.json")
    for path in ("linked/job.json", "linked.json"):
        with pytest.raises(ValueError, match="symlinks"):
            read_job_file(tmp_path, path)


def test_oversized_file_rejected_before_parsing(tmp_path):
    (tmp_path / "job.json").write_bytes(b" " * (MAX_JOB_BYTES + 1))
    with pytest.raises(ValueError, match="256 KiB"):
        read_job_file(tmp_path, "job.json")


@pytest.mark.parametrize("document", ['{"method":"HF","method":"MP2"}', '{"timeout_seconds":NaN}', '[]'])
def test_ambiguous_nonfinite_or_wrapped_json_is_rejected(tmp_path, document):
    (tmp_path / "job.json").write_text(document)
    with pytest.raises(ValueError):
        read_job_file(tmp_path, "job.json")


@pytest.mark.parametrize("cores,memory", [(0, 512), (3, 512), (True, 512), (1, 0), (2, 1025), (1, True)])
def test_resource_budget_cannot_be_bypassed(cores, memory):
    with pytest.raises(ValueError):
        validate_resources(cores, memory)


@pytest.mark.parametrize("changes", [
    {"engine": "xtb"}, {"hessian_file": "outside.hess"},
    {"r2_reference_manifest": "refs.json"}, {"t9_fallback": {}},
    {"periodic": {}}, {"initial_hessian": "READ"}, {"recipe": "R2"},
    {"is_vpt2": True}, {"timeout_seconds": 1801}, {"timeout_seconds": True},
    {"method": "HF Freq"}, {"method": "GOAT"}, {"method": "HF\n%pal nprocs 100 end"},
    {"basis_set": "def2-SVP PAL128"}, {"basis_set": "PAL128"},
    {"basis_set": "../file"}, {"implicit_solvation": "CPCM(Water) Freq"},
    {"method": "HF LooseSCF"}, {"method": "LooseSCF"},
    {"basis_set": "STO-3G LooseSCF"}, {"basis_set": "LooseSCF"},
    {"implicit_solvation": "CPCM(Water) LooseSCF"},
])
def test_external_inputs_unvalidated_operations_and_keyword_injection_rejected(changes):
    with pytest.raises(ValueError):
        preflight_configuration(water(**changes))


@pytest.mark.parametrize("changes", [{"is_opt": "false"}, {"charge": "0"}, {"arbitrary_shell": "touch injected"}])
def test_strict_model_rejects_coercion_and_unknown_fields(changes):
    with pytest.raises(ValueError):
        validate(water(**changes))


def test_atom_budget_is_not_only_a_text_size_limit():
    with pytest.raises(ValueError, match="50 atoms"):
        validate(water(geometry="\n".join(f"He {i} 0 0" for i in range(51))))


def test_incompatible_spin_is_rejected_before_engine_execution():
    with pytest.raises(ValueError, match="electron count"):
        validate(water(multiplicity=2))


@pytest.mark.parametrize("changes,reason", [
    ({"initial_hessian": "invalid"}, "initial Hessian"),
    ({"recipe": "R1"}, "r2SCAN-3c"),
    ({"is_freq": True, "grid_stage": 2}, "DEFGRID3"),
])
def test_invalid_native_options_fail_before_provisioning(changes, reason):
    data = water(**changes)
    with pytest.raises(ValueError, match=reason):
        preflight_configuration(data)
    with pytest.raises(ValueError, match=reason):
        validate(data)


@pytest.mark.parametrize("changes", [
    {"product_class": "B", "theory_tier": "T4"},
    {"theory_tier": "T50"},
    {"frozen_monomer_indices": [99]},
])
def test_shared_request_validator_enforces_the_actual_molecular_input_contract(changes):
    with pytest.raises((ValueError, MethodMatrixViolationError)):
        validate(water(**changes))


@pytest.mark.parametrize("optimize", [False, True])
def test_frequency_requests_with_explicit_tight_grid_remain_valid(optimize):
    config = validate(water(is_opt=optimize, is_freq=True, grid_stage=3))
    assert config.is_freq and config.is_opt is optimize and config.grid_stage == 3


def test_missing_registry_retains_submitted_input_and_failure_evidence(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()
    original = (json.dumps(water()) + "\n").encode()
    (repository / "job.json").write_bytes(original)
    output = tmp_path / "evidence"
    with pytest.raises(RuntimeError, match="Execution authority denied"):
        run_job(repository, "job.json", registry=tmp_path / "missing-registry.json", output=output, cores=1)
    assert (output / "submitted-job.json").read_bytes() == original
    report = json.loads((output / "calculation-report.json").read_text())
    manifest = json.loads((output / "publication-manifest.json").read_text())
    assert report["status"] == "failed" and report["scientific_execution_performed"] is False
    assert "submitted-job.json" in manifest and "calculation-report.json" in manifest
    with pytest.raises(FileExistsError):
        run_job(repository, "job.json", registry=tmp_path / "missing-registry.json", output=output, cores=1)


def test_validator_rejects_fields_that_do_not_match_submitted_bytes():
    allowed = water()
    injected = water(method="HF Freq")
    with pytest.raises(ValueError, match="differ"):
        validate_configuration(json.dumps(injected).encode(), allowed)


def test_shared_validator_rejects_ambiguous_duplicate_fields():
    data = water()
    contents = json.dumps(data)[:-1] + ',"method":"MP2"}'
    with pytest.raises(ValueError, match="Duplicate"):
        validate_configuration(contents.encode(), data)
