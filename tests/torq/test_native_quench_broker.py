"""Actual native quenches and diagnostic-only processes; no output substitution.

The water geometry is read from a registered authentic ORCA input artifact.
Positive outputs are new measured xTB runs, with their own retained hashes.
Diagnostic programs below produce no scientific energy, gradient or spectrum.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

from cochem_torq.quench_broker import IPCTrajectoryQuenchBroker, QuenchMethodology, QuenchRequest


ROOT = Path(__file__).resolve().parents[2]
NATIVE_INPUT = ROOT / "tests/data/orca_6_1_1_water_hf_sto3g"


def water_request(methodology=QuenchMethodology.GFN2_XTB):
    source = json.loads((NATIVE_INPUT / "provenance.json").read_text())
    path = NATIVE_INPUT / "water.xyz"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == source["files"]["water.xyz"]["sha256"]
    rows = [line.split() for line in path.read_text().splitlines()[2:] if line.strip()]
    assert [row[0] for row in rows] == ["O", "H", "H"]
    return QuenchRequest(trajectory_id="native-water", frame_index=0, atomic_numbers=[8, 1, 1],
                         geometry_angstrom=[[float(value) for value in row[1:]] for row in rows],
                         nonconformity_score=1.0, calibration_threshold=0.5, methodology=methodology)


def native_binary():
    configured = os.environ.get("XTB_CMD") or os.environ.get("COCHEM_XTB_BIN") or "xtb"
    binary = shutil.which(configured)
    assert binary is not None, "These native quench regressions require the installed xTB binary"
    return binary


@pytest.mark.parametrize("methodology", list(QuenchMethodology))
def test_actual_native_quench_retains_measured_energy_geometry_and_method(tmp_path, methodology):
    binary = native_binary()
    request = water_request(methodology)
    response = IPCTrajectoryQuenchBroker(tmp_path / "manifest.json").dispatch_quench(request, timeout=60)
    directory, = (tmp_path / "quench_runs").iterdir()
    stdout = (directory / "stdout.log").read_text()
    energies = re.findall(r"\|\s*TOTAL ENERGY\s+([^\s]+)\s+Eh\s*\|", stdout)
    assert response.quenched_energy_hartree == float(energies[-1].replace("D", "E"))
    assert math.isfinite(response.quenched_energy_hartree) and response.converged
    assert len(response.quenched_geometry) == 3 and all(len(row) == 3 for row in response.quenched_geometry)
    assert response.methodology == methodology.value
    execution = json.loads((directory / "execution.json").read_text())
    assert execution["scope"] == "screening" and execution["status"] == "accepted"
    assert execution["command"][0] == binary and execution["returncode"] == 0
    if methodology == QuenchMethodology.GFN_FF:
        assert "--gfnff" in execution["command"] and "--gfn" not in execution["command"]
    else:
        assert execution["command"][-2:] == ["--gfn", "2"]
    # These are hashes of this run, not the archived ORCA output's provenance.
    artifacts = {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
                 for name in ("outlier.xyz", "xtbopt.xyz", "stdout.log", "stderr.log", "result.json")}
    (directory / "run-provenance.json").write_text(json.dumps({
        "scope": "Actual native xTB screening quench, no ab initio accuracy claim",
        "binary": binary, "binary_sha256": hashlib.sha256(Path(binary).read_bytes()).hexdigest(),
        "command": execution["command"], "method": response.methodology, "files": artifacts,
    }, indent=2))


def diagnostic_worker(tmp_path, binary):
    request = water_request()
    request_path = tmp_path / "request.json"
    request_path.write_text(request.model_dump_json())
    # A separate real process selects the diagnostic program through the same
    # environment contract as a native worker. No helper or subprocess is patched.
    code = """
import json, sys
from pathlib import Path
from cochem_torq.quench_broker import IPCTrajectoryQuenchBroker, QuenchExecutionError, QuenchRequest
request = QuenchRequest.model_validate_json(Path(sys.argv[1]).read_text())
try:
    IPCTrajectoryQuenchBroker(Path(sys.argv[2]) / 'manifest.json').dispatch_quench(request)
except QuenchExecutionError as error:
    print(json.dumps({'type': type(error).__name__, 'reason': str(error),
                      'returncode': error.returncode, 'directory': str(error.diagnostics_dir)}))
else:
    raise AssertionError('A diagnostic process cannot produce a scientific quench result')
"""
    environment = dict(os.environ, XTB_CMD=str(binary), PYTHONPATH=str(ROOT / "src"))
    completed = subprocess.run([sys.executable, "-c", code, str(request_path), str(tmp_path)],
                               env=environment, capture_output=True, text=True, timeout=60)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(completed.stdout)
    directory = Path(result["directory"])
    assert json.loads((directory / "execution.json").read_text())["status"] == "rejected"
    assert not (directory / "result.json").exists()
    return result, directory


def test_actual_nonzero_diagnostic_process_retains_output_and_cannot_use_emt(tmp_path):
    # Python actually attempts to interpret the XYZ input as source code. Its
    # SyntaxError is a process diagnostic, never a substitute calculation.
    result, directory = diagnostic_worker(tmp_path, sys.executable)
    assert result["type"] == "QuenchExecutionError" and result["returncode"] != 0
    assert "xTB process failed" in result["reason"]
    assert "SyntaxError" in (directory / "stderr.log").read_text()
    assert (directory / "stdout.log").is_file()


def test_actual_native_help_has_no_energy_and_cannot_be_a_successful_quench(tmp_path):
    binary = native_binary()
    diagnostic = tmp_path / "xtb-help-diagnostic"
    diagnostic.write_text(f"#!{sys.executable}\nimport os\nos.execv({binary!r}, [{binary!r}, '--help'])\n")
    diagnostic.chmod(0o755)
    result, directory = diagnostic_worker(tmp_path, diagnostic)
    assert result["type"] == "QuenchExecutionError" and result["returncode"] == 0
    assert "finite energy in Hartree is missing" in result["reason"]
    stdout = (directory / "stdout.log").read_text()
    assert "Usage: xtb" in stdout and "TOTAL ENERGY" not in stdout


def test_missing_selected_native_binary_cannot_fall_back_to_emt(tmp_path):
    result, directory = diagnostic_worker(tmp_path, tmp_path / "absent-xtb")
    assert result["type"] == "BinaryNotFoundError" and result["returncode"] is None
    assert "was not found" in result["reason"]
    assert "Cannot resolve selected xTB binary" in (directory / "stderr.log").read_text()
