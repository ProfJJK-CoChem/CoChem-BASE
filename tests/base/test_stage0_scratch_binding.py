"""Real storage and environment phases must agree on the selected scratch.

These native filesystem and CLI controls exercise project/node-path selection.
They do not claim execution on a Slurm allocation.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("node_local", [False, True])
def test_native_cli_audits_one_project_or_node_scratch(tmp_path, node_local):
    source_root = Path(__file__).resolve().parents[2]
    project = tmp_path / "selected-project"
    registry = project / "Registry"
    registry.mkdir(parents=True)
    stale = tmp_path / "another-project-scratch"
    stale.mkdir()
    node = tmp_path / "real-node-local-directory"
    node.mkdir()
    environment = {key: value for key, value in os.environ.items() if not key.startswith("SLURM_")}
    environment.update(
        PYTHONPATH=os.pathsep.join(str(source_root / entry) for entry in ("src", ".", "base", "Libraries")),
        PYTHONDONTWRITEBYTECODE="1", COCHEM_ARTIFACT_DIR=str(project),
        COCHEM_SCRATCH_DIR=str(stale), TMPDIR=str(stale),
    )
    if node_local:
        environment["SLURM_TMPDIR"] = str(node)
    program = """import json, os, pathlib, sys
from cochem_base.cli import execute_phase
from cochem_base.orchestrator.stage0_authority import Stage0AuthorityError, validate_stage0_scratch
import cochem_base.cli as cli
assert pathlib.Path(cli.__file__).resolve() == pathlib.Path(sys.argv[2]) / 'src/cochem_base/cli.py'
reports = {}
for number in (6, 7):
 success, status, report = execute_phase(number, output_dir=sys.argv[1], min_disk_space_gb=1)
 assert success, (number, status, report)
 reports[number] = report
scratch = validate_stage0_scratch(reports[6], reports[7])
changed = json.loads(json.dumps(reports[7]))
changed['scratch']['scratch_directory'] = sys.argv[3]
try:
 validate_stage0_scratch(reports[6], changed)
except Stage0AuthorityError as error:
 assert 'different scratch' in str(error)
else:
 raise AssertionError('Mismatched physically audited scratch was accepted')
changed = json.loads(json.dumps(reports[7]))
changed['injected_env_vars']['COCHEM_SCRATCH_DIR'] = sys.argv[3]
try:
 validate_stage0_scratch(reports[6], changed)
except Stage0AuthorityError as error:
 assert 'injected scratch' in str(error)
else:
 raise AssertionError('Mismatched native environment injection was accepted')
for variable in ('COCHEM_SCRATCH_DIR', 'TMPDIR', 'SLURM_TMPDIR'):
 changed = json.loads(json.dumps(reports[7]))
 # This physically resolves to the same directory from the actual child CWD.
 # Relative paths still cannot establish durable execution authority.
 changed['injected_env_vars'][variable] = os.path.relpath(scratch, pathlib.Path.cwd())
 assert pathlib.Path(changed['injected_env_vars'][variable]).resolve() == scratch
 try:
  validate_stage0_scratch(reports[6], changed)
 except Stage0AuthorityError as error:
  assert 'absolute audited path' in str(error)
 else:
  raise AssertionError('CWD-dependent relative environment authority was accepted')
print(json.dumps({'storage_scratch': reports[6]['storage_paths']['scratch_directory'],
 'execution_scratch': reports[7]['scratch']['scratch_directory'], 'validated_scratch': str(scratch),
 'injected_scratch': reports[7]['injected_env_vars']['COCHEM_SCRATCH_DIR'],
 'injected_tmpdir': reports[7]['injected_env_vars']['TMPDIR'],
 'physical_storage_free_gb': reports[6]['storage_paths']['free_disk_space_gb'],
 'actual_writable_probe': reports[7]['scratch']['is_writable'],
 'changed_report_refused': True, 'changed_injection_refused': True, 'relative_injections_refused': True}))
"""
    process = subprocess.run(
        [sys.executable, "-B", "-c", program, str(registry), str(source_root), str(stale)],
        cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=30, check=False,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    result = json.loads(process.stdout.strip().splitlines()[-1])
    expected = node.resolve() if node_local else project / "Scratch"
    for key in ("storage_scratch", "execution_scratch", "validated_scratch", "injected_scratch", "injected_tmpdir"):
        assert Path(result[key]) == expected
    assert result["physical_storage_free_gb"] >= 1
    assert result["actual_writable_probe"] is True
    assert result["changed_report_refused"] and result["changed_injection_refused"]
    assert result["relative_injections_refused"]
    assert expected.is_dir()
    assert not list(expected.glob(".cochem_scratch_probe_*"))
    assert not list(stale.iterdir()), "Fresh setup wrote another project's scratch"
    (tmp_path / "actual-scratch-route-receipt.json").write_text(json.dumps(result, indent=2) + "\n")
