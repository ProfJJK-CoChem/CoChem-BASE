"""Native engine acceptance; these cases never replace xTB with a test engine."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

from cli import CalculationMatrixConfig, _parse_run_geometry
from cochem_base.calc.xtb_execution import accept_xtb_result, validate_xtb_config

WATER = "O 0 0 0\nH 0.7586 0 0.5043\nH -0.7586 0 0.5043"
ROOT = Path(__file__).resolve().parents[2]


def _config(**changes):
    values = dict(geometry=WATER, engine="xtb", method="GFN2-xTB", basis_set="built-in", theory_tier="T1")
    values.update(changes)
    return CalculationMatrixConfig(**values)


@pytest.mark.parametrize("changes", [
    {"is_freq": True}, {"is_vpt2": True}, {"recipe": "R1"}, {"product_class": "A"},
    {"basis_set": "def2-TZVP"}, {"theory_tier": "T4"}, {"implicit_solvation": "CPCM"},
    {"frozen_monomer_indices": []}, {"multiplicity": 3}, {"charge": 1},
    {"method": "B3LYP-D4"}, {"grid_stage": 1}, {"ab_initio_relaxed": True},
])
def test_unsupported_scientific_requests_cannot_be_silently_ignored(changes):
    with pytest.raises(ValueError):
        validate_xtb_config(_config(**changes), ["O", "H", "H"])


@pytest.mark.parametrize("method,tier", [("GFN2-xTB", "T1"), ("GFN-FF", "T0")])
@pytest.mark.parametrize("optimize", [False, True])
def test_real_cli_calculation_and_atomic_publication(tmp_path, method, tier, optimize):
    binary = shutil.which(os.environ.get("XTB_CMD", "xtb"))
    if binary is None:
        pytest.skip("Native xTB executable required; configure XTB_CMD")
    config = _config(method=method, theory_tier=tier, is_opt=optimize)
    config_path = tmp_path / "config.json"
    config_path.write_text(config.model_dump_json(), encoding="utf-8")
    published = tmp_path / "results"
    environment = dict(os.environ, XTB_CMD=binary, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
    completed = subprocess.run(
        [sys.executable, str(ROOT / "cli.py"), "run", "--config", str(config_path),
         "--threads", "1", "--scratch", str(tmp_path / "scratch"), "--output", str(published), "--json"],
        cwd=ROOT, env=environment, capture_output=True, text=True, timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    execution = json.loads(completed.stdout)
    assert execution["status"] == "EXECUTION_VERIFIED" and execution["engine"] == "xtb"
    assert execution["output_dir"] == str(published)
    result = json.loads((published / "result.json").read_text())
    assert result["converged"] is True and result["scope"] == "screening"
    assert result["optimization_converged"] is (True if optimize else None)
    assert math.isfinite(result["energy_hartree"])
    assert result["elements"] == ["O", "H", "H"]
    assert (published / "xtb.out.sha256").is_file()
    assert (published / "input.xyz.sha256").is_file()
    assert not Path(execution["scratch_dir"]).exists()

    # Revalidate actual engine evidence after removing its normal-termination
    # marker. A process exit code alone must not create a successful result.
    stdout = (published / "xtb.out").read_text()
    stderr = (published / "stderr.log").read_text()
    if method == "GFN2-xTB":
        absent_scc = re.sub(r"convergence criteria satisfied after \d+ iterations", "", stdout, flags=re.I)
        config.method = " gFn2-xTb "
        (published / "result.json").unlink()
        with pytest.raises(RuntimeError, match="SCC convergence evidence"):
            accept_xtb_result(subprocess.CompletedProcess([], 0, absent_scc, stderr), published,
                              config, ["O", "H", "H"], _parse_run_geometry)
        assert not (published / "result.json").exists()
    incomplete = subprocess.CompletedProcess([], 0, stdout.replace("normal termination of xtb", ""),
                                              stderr.replace("normal termination of xtb", ""))
    (published / "result.json").unlink(missing_ok=True)
    with pytest.raises(RuntimeError, match="did not terminate normally"):
        accept_xtb_result(incomplete, published, config, ["O", "H", "H"], _parse_run_geometry)
    assert not (published / "result.json").exists()
