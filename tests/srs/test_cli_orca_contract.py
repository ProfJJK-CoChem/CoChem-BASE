"""Real CLI/deck/filesystem validation without substituting chemistry engines."""
from __future__ import annotations

import json
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

import psutil
import pytest

REPO = Path(__file__).resolve().parents[2]
WATER = "3\nwater\nO 0 0 0\nH 0.9572 0 0\nH -0.2399872 0.927297 0\n"


def _run(tmp_path: Path, *, engine: str = "orca", dry_run: bool = True, output: Path | None = None, process_probe: Path | None = None) -> subprocess.CompletedProcess[str]:
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"hardware": {
        "physical_cpu_cores": psutil.cpu_count(logical=False),
        "logical_cpu_cores": psutil.cpu_count(logical=True),
        "ram_gb": psutil.virtual_memory().total / 1024**3,
    }}), encoding="utf-8")
    if process_probe is not None:
        # Audited executable evidence for this telemetry-only rejection probe.
        # It never supplies accepted quantum output or a reference energy.
        from cochem_base.cochem_core_registry_schema import CoChemSystemConfig, EngineInfo
        authority = CoChemSystemConfig.create_default(auto_detect_hardware=True)
        authority.engines["orca"] = EngineInfo(status="found", path=str(process_probe),
                                           hash=hashlib.sha256(process_probe.read_bytes()).hexdigest()).model_dump()
        authority.hardware.maxcore_mb = 1024
        authority.update_checksum()
        registry.write_text(authority.model_dump_json(), encoding="utf-8")
    config = tmp_path / "matrix.json"
    config.write_text(json.dumps({
        "geometry": WATER, "engine": engine, "method": "B3LYP-D4", "basis_set": "def2-SVP",
        "product_class": "A", "theory_tier": "T4", "implicit_solvation": "CPCM(Water)",
    }), encoding="utf-8")
    command = [sys.executable, str(REPO / "cli.py"), "run", "--config", str(config), "--scratch", str(tmp_path / "scratch"), "--output", str(output or tmp_path / "results"), "--threads", "1", "--device", "cpu", "--json"]
    if dry_run:
        command.append("--dry-run")
    env = dict(os.environ, COCHEM_CONFIG=str(registry))
    if not dry_run:
        env["ORCA_CMD"] = str(process_probe or tmp_path / "required-physical-orca-is-absent")
    return subprocess.run(command, env=env, capture_output=True, text=True, timeout=60)


def test_cli_generates_real_orca_deck_and_marks_only_generation(tmp_path: Path) -> None:
    result = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "DECK_GENERATED"
    decks = list((tmp_path / "results").glob("*_job.inp"))
    assert len(decks) == 1
    text = decks[0].read_text()
    assert "! B3LYP D4 def2-SVP Opt" in text
    assert "CPCM(Water)" in text
    assert "nprocs 1" in text
    # A generated optimization requests margin below the independent 1e-5 gate.
    requested_max_gradient = re.findall(r"^\s*TolMaxG\s+(\S+)", text, re.M)
    assert len(requested_max_gradient) == 1
    assert 0 < float(requested_max_gradient[0]) < 1e-5
    assert "InHess XTB2" in text
    assert "* xyz 0 1" in text
    assert not (tmp_path / "results" / "calculation.property.txt").exists()
    assert not list((tmp_path / "results").glob("*_qcschema.json"))
    assert list((tmp_path / "results").glob("*.sha256"))


@pytest.mark.parametrize("engine,reason", [
    ("cfour", "not a valid CFOURCalcLevel"),
    ("xtb", "supports GFN2-xTB and GFN-FF screening only"),
])
def test_cli_unsupported_adapter_or_method_cannot_publish_success(tmp_path: Path, engine: str, reason: str) -> None:
    result = _run(tmp_path, engine=engine)
    assert result.returncode != 0
    assert reason in result.stderr
    assert not (tmp_path / "results").exists()


def test_cli_missing_real_engine_cannot_publish_success(tmp_path: Path) -> None:
    result = _run(tmp_path, dry_run=False)
    assert result.returncode != 0
    assert "real ORCA executable is required" in result.stderr
    assert not (tmp_path / "results").exists()


def test_cli_rejects_source_checkout_publication(tmp_path: Path) -> None:
    result = _run(tmp_path, output=REPO / "forbidden-calculation-output")
    assert result.returncode != 0
    assert "outside the source checkout" in result.stderr
    assert not (REPO / "forbidden-calculation-output").exists()


def test_nonzero_real_process_is_rejected_before_quantum_acceptance(tmp_path: Path) -> None:
    import pytest

    from cli import CalculationMatrixConfig, _accept_orca_result

    result = subprocess.run([sys.executable, "-c", "import sys; sys.stderr.write('intentional process failure'); sys.exit(7)"], capture_output=True, text=True, check=False)
    config = CalculationMatrixConfig(geometry=WATER)
    with pytest.raises(RuntimeError, match="exit code 7"):
        _accept_orca_result(result, tmp_path, "failure", config)
    assert (tmp_path / "stderr.log").read_text() == "intentional process failure"
    assert not (tmp_path / "failure_qcschema.json").exists()


def test_cli_integer_fields_reject_boolean_and_fractional_coercion() -> None:
    import pytest
    from pydantic import ValidationError

    from cli import CalculationMatrixConfig

    for field in ("charge", "multiplicity", "grid_stage"):
        for value in (True, 1.5):
            with pytest.raises(ValidationError):
                CalculationMatrixConfig(geometry=WATER, **{field: value})


@pytest.mark.skipif(os.name == "nt", reason="Executable script transport probe requires POSIX shebang")
def test_cli_live_integrity_failure_prevents_publication(tmp_path: Path) -> None:
    # This process tests rejected telemetry and lifecycle handling. It does not
    # compute, emulate, or claim successful electronic-structure output.
    probe = tmp_path / "integrity-transport-probe"
    marker = tmp_path / "unacceptable-continuation"
    probe.write_text(
        f"#!{sys.executable}\n"
        "import pathlib, time\n"
        "print('Expectation value of <S**2> : 0.08', flush=True)\n"
        "time.sleep(30)\n"
        f"pathlib.Path({str(marker)!r}).touch()\n",
        encoding="utf-8",
    )
    probe.chmod(0o700)
    result = _run(tmp_path, dry_run=False, process_probe=probe)
    assert result.returncode != 0
    assert "SPIN_CONTAMINATION_EXCEEDED" in result.stderr
    assert not marker.exists()
    assert not (tmp_path / "results").exists()
    assert not list((tmp_path / "scratch").rglob("execution.json"))
    assert not list((tmp_path / "scratch").rglob("*_qcschema.json"))
    assert "0.08" in next((tmp_path / "scratch").rglob("process_stdout.log")).read_text()
    rejection = json.loads(next((tmp_path / "scratch").rglob("execution_failure.json")).read_text())
    assert rejection["exception_type"] == "SpinContaminationError"
    assert rejection["details"]["routing_tier"] == "T9"


@pytest.mark.parametrize("dry_run", [False, True])
def test_cli_setup_preserves_corrupt_registry(tmp_path: Path, dry_run: bool) -> None:
    registry = tmp_path / "Registry" / "cochem_system_config.json"
    registry.parent.mkdir()
    original = b"{unreadable registry must be preserved"
    registry.write_bytes(original)
    command = [sys.executable, str(REPO / "cli.py"), "setup", "--phase", "1", "--artifact-dir", str(tmp_path), "--json"]
    if dry_run:
        command.append("--dry-run")
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert registry.read_bytes() == original
    if not dry_run:
        assert result.returncode != 0
        assert "registry_error" in json.loads(result.stdout)
    assert not (registry.parent / "setup_summary.json").exists()
    if dry_run:
        assert json.loads(result.stdout)["overall_status"] == "AUDIT_ONLY"
