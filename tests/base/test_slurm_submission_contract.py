"""Actual staging and shell checks without inventing a Slurm scheduler or job."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from cochem_base.calc.slurm_submission import (
    execute_staged_calculation, generate_slurm_script, memory_megabytes,
    sanitize_slurm_parameter, stage_calculation, submit_slurm_job, validate_slurm_walltime,
)


def molecular_job():
    return {"geometry": "O 0 0 0\nH 0 -0.757 0.587\nH 0 0.757 0.587\n",
            "engine": "xtb", "method": "GFN2-xTB", "basis_set": "built-in",
            "is_opt": True, "timeout_seconds": 120}


@pytest.mark.parametrize("memory,expected", [("512MB", 512), ("1G", 1024), ("2GiB", 2048)])
def test_explicit_memory_units(memory, expected):
    assert memory_megabytes(memory) == expected


@pytest.mark.parametrize("memory", ["0GB", "-1GB", "1TB", "2048", "1GB;touch bad", "NaN"])
def test_memory_injection_and_ambiguous_units_rejected(memory):
    with pytest.raises(ValueError):
        memory_megabytes(memory)


@pytest.mark.parametrize("name", ["job\n#SBATCH --output=elsewhere", "job;echo bad", "$(touch injected)", "job with spaces"])
def test_slurm_parameters_reject_control_injection(name):
    with pytest.raises(ValueError):
        sanitize_slurm_parameter("job_name", name)


@pytest.mark.parametrize("walltime", ["00:00:00", "49:00:00", "01:60:00", "1-24:00:00", "1:00:00\n#SBATCH--bad"])
def test_walltime_requires_real_bounded_duration(walltime):
    with pytest.raises(ValueError):
        validate_slurm_walltime(walltime)


def test_legacy_unstaged_input_cannot_generate_executable_script():
    with pytest.raises(ValueError, match="config_path"):
        generate_slurm_script(input_deck_path="missing.inp; touch injection")


def test_multinode_does_not_masquerade_as_supported_shared_memory_job(tmp_path):
    with pytest.raises(ValueError, match="exactly one node"):
        stage_calculation(molecular_job(), tmp_path / "job", nodes=2)


def test_unconfigured_scientific_provider_does_not_become_slurm_calculation(tmp_path):
    config = molecular_job()
    config.update(engine="cfour", method="CCSD(T)", basis_set="cc-pVDZ")
    with pytest.raises(ValueError, match="connected native"):
        stage_calculation(config, tmp_path / "job")


def test_actual_deck_staging_safe_bash_and_no_local_execution_fallback(tmp_path):
    from cochem_base.config_loader import resolve_config_path
    from cochem_base.core.cochem_core_registry_manager import load_system_config

    registry = resolve_config_path()
    assert load_system_config(registry).hpc.scheduler == "local", "This boundary test requires the local CPU acceptance host"
    staged = tmp_path / "staged spaces $(touch should-not-exist)"
    script = stage_calculation(molecular_job(), staged, registry_path=registry, ntasks_per_node=1, mem="512MB")
    source = script.read_text()
    assert "#SBATCH --nodes=1" in source and "#SBATCH --ntasks=1" in source
    assert "#SBATCH --cpus-per-task=1" in source and "module load" not in source
    assert "matrix_input.inp" not in source and "OMPI_MCA_pml" not in source
    assert json.loads((staged / "calculation.json").read_text())["geometry"] == molecular_job()["geometry"]
    assert execute_staged_calculation(staged / "job_manifest.json", validate_only=True)["status"] == "VALIDATED_INPUT_ONLY"
    checked = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True, timeout=15)
    assert checked.returncode == 0, checked.stderr
    environment = {key: value for key, value in os.environ.items() if not key.startswith("SLURM_")}
    invoked = subprocess.run(["bash", str(script)], cwd=tmp_path, env=environment,
                             capture_output=True, text=True, timeout=30)
    assert invoked.returncode != 0
    assert "no local fallback" in invoked.stderr
    assert not (staged / "results" / "calculation" / "result.json").exists()
    assert "PENDING_CLUSTER_CONFIGURATION" in submit_slurm_job(script)
    assert not list(tmp_path.rglob("should-not-exist"))
    manifest = json.loads((staged / "job_manifest.json").read_text())
    assert manifest["scientific_execution_performed"] is False
    assert manifest["allocation_authority"].startswith("declared_request_only")
    assert "engine_sha256" not in manifest
    # Alter real staged bytes and verify the package refuses execution/dispatch.
    with (staged / "calculation.json").open("a") as stream:
        stream.write(" ")
    with pytest.raises(ValueError, match="altered"):
        submit_slurm_job(script)


def test_planned_compute_allocation_is_not_limited_by_login_node(tmp_path):
    from cochem_base.calc.slurm_generator import SlurmGenerator
    from cochem_base.config_loader import resolve_config_path
    from cochem_base.core.cochem_core_registry_manager import load_system_config

    registry = resolve_config_path()
    host = load_system_config(registry).hardware
    requested = max(host.allocatable_compute_cores, SlurmGenerator().get_physical_core_limit()) + 1
    memory_gb = int(host.ram_gb) + 1
    script = stage_calculation(molecular_job(), tmp_path / "planned-job", registry_path=registry,
                               ntasks_per_node=requested, mem=f"{memory_gb}GB")
    manifest = json.loads((script.parent / "job_manifest.json").read_text())
    assert manifest["cores"] == requested
    assert manifest["memory_mb"] == memory_gb * 1024
    assert manifest["allocation_authority"].startswith("declared_request_only")
    assert f"#SBATCH --cpus-per-task={requested}" in script.read_text()
    assert not (script.parent / "results").exists()


def test_gui_stages_actual_selected_configuration_in_real_child(tmp_path):
    from cochem_base.config_loader import resolve_config_path

    program = '''import json, pathlib, sys
from ui.voila_layout.cochem_gui import CoChemGUI
ui = CoChemGUI()
ui.matrix_engine.value = "XTB"
ui.matrix_geometry.value = "O 0 0 0\\nH 0 -0.757 0.587\\nH 0 0.757 0.587\\n"
ui.artifact_output_path.value = sys.argv[1]
ui.tasks_per_node_input.value = 1
ui.mem_input.value = "512MB"
ui._on_slurm_submit_clicked(None)
root = pathlib.Path(sys.argv[1])
manifest = list(root.glob("SlurmStaging/*/job_manifest.json"))
assert len(manifest) == 1, ui.slurm_status_output.value
content = json.loads(manifest[0].read_text())
assert content["engine"] == "xtb"
assert content["scientific_execution_performed"] is False
assert "PENDING_CLUSTER_CONFIGURATION" in ui.slurm_status_output.value
print("GUI_SLURM_STAGING_VERIFIED")
'''
    environment = dict(os.environ, COCHEM_CONFIG=str(resolve_config_path()), COCHEM_ARTIFACT_DIR=str(tmp_path / "ui"),
                       COCHEM_HEADLESS="1", QT_QPA_PLATFORM="offscreen")
    child = subprocess.run([sys.executable, "-c", program, str(tmp_path / "ui")], env=environment,
                           capture_output=True, text=True, timeout=60)
    assert child.returncode == 0, child.stderr + child.stdout
    assert "GUI_SLURM_STAGING_VERIFIED" in child.stdout


@pytest.mark.parametrize("changes", [
    {"initial_hessian": "invalid"}, {"recipe": "R1"},
    {"is_freq": True, "grid_stage": 2}, {"product_class": "B", "theory_tier": "T2"},
])
def test_planned_orca_job_cannot_bypass_native_method_policy(tmp_path, changes):
    config = molecular_job()
    config.update(engine="orca", method="HF", basis_set="STO-3G")
    config.update(changes)
    from cochem_base.exceptions import MethodMatrixViolationError
    with pytest.raises((ValueError, MethodMatrixViolationError)) as rejected:
        stage_calculation(config, tmp_path / "invalid-policy")
    assert "authority" not in str(rejected.value).lower()
    assert not (tmp_path / "invalid-policy").exists()
