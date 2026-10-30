"""Native engine acceptance; these cases never replace xTB with a test engine."""
from __future__ import annotations

import json
import hashlib
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest
from ci_tools.source_quarantine import source_paths

from cli import CalculationMatrixConfig, _parse_run_geometry
from cochem_base.calc.xtb_execution import accept_xtb_result, validate_xtb_config
from cochem_base.core_engine.scientific_telemetry import read_scientific_results

WATER = "O 0 0 0\nH 0.7586 0 0.5043\nH -0.7586 0 0.5043"
ROOT = Path(__file__).resolve().parents[2]

_NATIVE_CLI_BOOTSTRAP = r'''
import importlib.util, os, sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
arguments = sys.argv[2:]
context = ("COCHEM_SOURCE_QUARANTINE_ROOT", "COCHEM_SOURCE_QUARANTINE_ORIGINAL",
           "COCHEM_SOURCE_QUARANTINE_EVIDENCE", "COCHEM_SOURCE_QUARANTINE_REVISION")
if any(os.environ.get(key) for key in context):
    assert all(os.environ.get(key) for key in context)
    startup = sys.modules.get("sitecustomize")
    assert startup is not None and Path(startup.__file__).resolve() == root / "ci_tools/quarantine_startup/sitecustomize.py"
    guard = sys.modules.get("ci_tools.source_quarantine")
    assert guard is not None and Path(guard.__file__).resolve() == root / "ci_tools/source_quarantine.py"
    state = guard._active
    assert state is not None and state["copied"] == root == Path(os.environ[context[0]]).resolve()
    assert state["original"] == Path(os.environ[context[1]]).resolve()
    assert state["revision"] == os.environ[context[3]]
sys.path.insert(0, str(root))
from ci_tools.source_quarantine import source_paths
assert Path(sys.modules["ci_tools.source_quarantine"].__file__).resolve() == root / "ci_tools/source_quarantine.py"
sys.path[:0] = [path for path in source_paths(root) if path not in sys.path]
assert Path(importlib.util.find_spec("cli").origin).resolve() == root / "cli.py"
assert Path(importlib.util.find_spec("cochem_base.cli").origin).resolve() == root / "src/cochem_base/cli.py"
assert Path(importlib.util.find_spec("cochem_base.calc.calculation_service").origin).resolve() == root / "src/cochem_base/calc/calculation_service.py"
import cli
from cochem_base import cli as canonical_cli
from cochem_base.calc import calculation_service
assert Path(cli.__file__).resolve() == root / "cli.py"
assert Path(canonical_cli.__file__).resolve() == root / "src/cochem_base/cli.py"
assert cli.entrypoint is canonical_cli.entrypoint
assert Path(calculation_service.__file__).resolve() == root / "src/cochem_base/calc/calculation_service.py"
sys.argv = [str(root / "cli.py"), *arguments]
raise SystemExit(cli.entrypoint())
'''


def _config(**changes):
    values = dict(geometry=WATER, engine="xtb", method="GFN2-xTB", basis_set="built-in", theory_tier="T1")
    values.update(changes)
    return CalculationMatrixConfig(**values)


def test_native_cli_child_proves_source_origins_without_calculation(tmp_path):
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                       PYTHONPATH=os.pathsep.join(source_paths(ROOT)))
    child = subprocess.run([sys.executable, "-B", "-c", _NATIVE_CLI_BOOTSTRAP, str(ROOT), "--help"],
        cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=45)
    assert child.returncode == 0, child.stdout + child.stderr
    assert "usage:" in child.stdout.lower()
    assert not list(tmp_path.rglob("result.json"))


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
    environment = dict(os.environ, XTB_CMD=binary, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
                       PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=os.pathsep.join(source_paths(ROOT)))
    completed = subprocess.run(
        [sys.executable, "-B", "-c", _NATIVE_CLI_BOOTSTRAP, str(ROOT), "run", "--config", str(config_path),
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

    from cochem_base.interfaces.student_reports import (
        observation_from_completed_local_calculation, build_isomer_report,
    )
    if method == "GFN2-xTB":
        record = observation_from_completed_local_calculation(execution, results_directory=published)
        assert record["energy_hartree"] == result["energy_hartree"]
        assert record["method"]["basis"] is None
        assert record["minimum_verified"] is False
        assert record["electronic_state"] == {"charge": result["charge"], "multiplicity": result["multiplicity"]}
        assert record["source"]["path"] == str(published / "result.json")
        report = build_isomer_report([record], populations=False)
        assert report["rows"][0]["energy_hartree"] == result["energy_hartree"]
        assert "population_fraction" not in report["rows"][0]
        with pytest.raises(ValueError, match="verified minimum"):
            build_isomer_report([record], populations=True)
        with pytest.raises(ValueError, match="completed local execution receipt"):
            observation_from_completed_local_calculation({**execution, "dry_run": True}, results_directory=published)
        _assert_local_registration_refusals(execution, published)
        # Corrupt this test's owned evidence only, then restore its exact bytes.
        context = published / "matrix_config.validated.json"
        original_context = context.read_bytes()
        original_sidecar = context.with_name(context.name + ".sha256").read_bytes()
        try:
            context.write_text("{}\n")
            with pytest.raises(ValueError, match="checksum"):
                build_isomer_report([record], populations=False)
        finally:
            context.write_bytes(original_context)
            context.with_name(context.name + ".sha256").write_bytes(original_sidecar)
    else:
        with pytest.raises(ValueError, match="GFN2-xTB"):
            observation_from_completed_local_calculation(execution, results_directory=published)

    if optimize:
        evidence = result["optimization_evidence"]
        assert evidence["optimizer"] == "SciPy BFGS with native xTB analytic gradients"
        assert evidence["evaluations"] > 2
        assert evidence["gradient_norm_hartree_per_bohr"] <= 1e-4
        records = read_scientific_results(result["telemetry_job_id"], store_path=result["telemetry_path"])
        measured = [row["gradient_source"] for row in records["metadata"] if "gradient_source" in row]
        assert len(measured) == evidence["evaluations"]
        assert len(records["gradients_hartree_per_bohr"]) >= len(measured)
        for source in measured:
            checkpoint = published / source["gradient_artifact"]["path"]
            assert hashlib.sha256(checkpoint.read_bytes()).hexdigest() == source["gradient_artifact"]["sha256"]
            assert source["record_kind"] == "measured_optimization_gradient_evaluation"
            assert source["gradient_artifact"]["unit"] == "hartree/bohr"

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


def _assert_local_registration_refusals(execution, published):
    """Corrupt a genuinely produced owned bundle, then restore every byte."""
    from cochem_base.interfaces.student_reports import observation_from_completed_local_calculation
    cases = [
        ("matrix_config.validated.json", "missing_charge", None),
        ("matrix_config.validated.json", "charge", True),
        ("matrix_config.validated.json", "charge", 2),
        ("matrix_config.validated.json", "basis_set", "def2-TZVP"),
        ("matrix_config.validated.json", "missing_basis", None),
        ("result.json", "charge", False),
        ("result.json", "multiplicity", 1.0),
        ("result.json", "method", "GFN-FF"),
        ("result.json", "engine", "orca"),
        ("result.json", "converged", False),
        ("result.json", "energy_hartree", float("nan")),
        ("result.json", "nuclides", ["18O", "H", "H"]),
        ("result.json", "string_coordinates", None),
        ("execution.json", "status", "REJECTED"),
    ]
    for filename, field, value in cases:
        path = published / filename
        sidecar = path.with_name(path.name + ".sha256")
        original, checksum = path.read_bytes(), sidecar.read_bytes()
        try:
            data = json.loads(original)
            if field == "missing_charge":
                del data["charge"]
            elif field == "missing_basis":
                del data["basis_set"]
            elif field == "string_coordinates":
                data["coordinates_angstrom"] = [[str(value) for value in row] for row in data["coordinates_angstrom"]]
            else:
                data[field] = value
            path.write_text(json.dumps(data) + "\n")
            # Renew the byte checksum so the semantic refusal is really reached.
            sidecar.write_text(hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name + "\n")
            with pytest.raises(ValueError):
                observation_from_completed_local_calculation(execution, results_directory=published)
        finally:
            path.write_bytes(original)
            sidecar.write_bytes(checksum)
        assert path.read_bytes() == original and sidecar.read_bytes() == checksum
    intermediate = published / "evaluation-0000"
    if intermediate.is_dir():
        with pytest.raises((ValueError, OSError)):
            observation_from_completed_local_calculation(execution, results_directory=intermediate)
    for filename in ("matrix_config.validated.json", "xtb.out.sha256"):
        path = published / filename
        original = path.read_bytes()
        try:
            path.unlink()
            with pytest.raises(ValueError):
                observation_from_completed_local_calculation(execution, results_directory=published)
        finally:
            path.write_bytes(original)


def test_two_actual_local_calculated_structures_export_electronic_differences(tmp_path):
    """Two native single points are calculated structures, not proven isomers."""
    from cochem_base.calc.calculation_service import run_calculation
    from cochem_base.interfaces.student_reports import (
        HARTREE_KJ_MOL, observation_from_completed_local_calculation,
        build_isomer_report, export_report,
    )
    binary = shutil.which(os.environ.get("XTB_CMD", "xtb"))
    if binary is None:
        pytest.skip("Native xTB executable required; configure XTB_CMD")
    records = []
    completed = []
    for index, geometry in enumerate((WATER, "O 0 0 0\nH 0.80 0 0.55\nH -0.80 0 0.55")):
        directory = tmp_path / f"calculated-structure-{index}"
        directory.mkdir()
        config_path = directory / "config.json"
        config_path.write_text(_config(geometry=geometry, is_opt=False).model_dump_json())
        receipt = run_calculation(config_path, scratch=directory / "scratch", output=directory / "Results", threads=1)
        records.append(observation_from_completed_local_calculation(receipt, results_directory=directory / "Results"))
        completed.append((receipt, directory / "Results"))
    assert records[0]["energy_hartree"] != records[1]["energy_hartree"]
    report = build_isomer_report(records, populations=False)
    reference = min(record["energy_hartree"] for record in records)
    for row, record in zip(report["rows"], records, strict=True):
        assert row["energy_hartree"] == record["energy_hartree"]
        assert row["relative_energy_kj_mol"] == (record["energy_hartree"] - reference) * HARTREE_KJ_MOL
        assert "population_fraction" not in row
    assert report["title"] == "Structure energy differences"
    assert all(record["minimum_verified"] is False for record in records)
    paths = export_report(report, tmp_path / "report")
    assert "relative_energy_kj_mol" in Path(paths["table.csv"]).read_text()
    with pytest.raises(ValueError, match="verified minimum"):
        build_isomer_report(records, populations=True)
    from ui.voila_layout.cochem_gui import CoChemGUI
    gui = CoChemGUI()
    for receipt, directory in completed:
        gui._register_completed_local_calculation(receipt, directory)
    labels = tuple(label for label, index in gui.research_isomer_choices.options)
    assert labels == ("Local calculation 1 · GFN2-xTB · Electronic energy",
                      "Local calculation 2 · GFN2-xTB · Electronic energy")
    for receipt, directory in reversed(completed):
        gui._register_completed_local_calculation(receipt, directory)
    assert tuple(label for label, index in gui.research_isomer_choices.options) == labels
    assert [record["local_calculation_number"] for record in gui._research_observations] == [1, 2]
    assert [record["source"]["path"] for record in gui._research_observations] == [str(directory / "result.json") for receipt, directory in completed]
