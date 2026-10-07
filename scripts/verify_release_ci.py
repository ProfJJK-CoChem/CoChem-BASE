"""Bounded public CI checks and clean-wheel acceptance for the reviewed BASE release.

This deliberately does not replace the full canonical release-candidate gate or
licensed ORCA, ML-model, QE, GPU, Slurm and native scientific acceptance. Every
test selected here must run: skipped, deselected and xfailed cases fail the gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tomllib


ROOT = Path(__file__).resolve().parents[1]
HOSTED_TESTS = (
    "tests/base/test_native_grid_execution.py",
    "tests/base/test_native_crash_provenance.py",
    "tests/base/test_python_hook_swmr.py",
    "tests/base/test_gradient_telemetry.py",
    "tests/base/test_chain_integrity.py",
    "tests/calc/test_nuclide_ingress_handoff.py",
    "tests/ui/test_optional_licensed_engines.py",
    "tests/calc/test_cfour_execution_contract.py",
    "tests/base/test_cfour_provisioning.py",
    "tests/base/test_context_compression_contract.py",
    "tests/base/test_scribe_missing_observations.py",
    "tests/base/test_srs_runtime_foundations.py::test_crash_tail_preserves_exact_physical_stderr",
    "tests/base/test_srs_runtime_foundations.py::test_canonical_broker_persists_exact_crash_provenance",
    "tests/base/test_srs_runtime_foundations.py::test_optional_git_failure_preserves_real_broker_crash",
    "tests/base/test_srs_runtime_foundations.py::test_source_layout_git_failures_preserve_real_crash",
    "tests/base/test_srs_runtime_foundations.py::test_crash_source_identity_ignores_foreign_git_repository",
    "tests/base/test_srs_runtime_foundations.py::test_crash_source_identity_follows_linked_worktree",
    "tests/base/test_actions_calculation_contract.py",
    "tests/base/test_cli_memory_budget.py",
    "tests/base/test_stage0_authority_completion.py",
    "tests/base/test_module_handoff_contract.py",
    "tests/base/test_module_installer.py",
    "tests/base/test_module_execution.py",
    "tests/base/test_module_adapter_topos.py",
    "tests/base/test_module_adapter_torq.py",
    "tests/base/test_ingestion_watchdog_events.py",
    "tests/base/test_trajectory_telemetry.py",
    "tests/base/test_srs_execution_authority.py",
    "tests/base/test_srs_mass_geometry_contracts.py",
    "tests/base/test_grid_policy_contract.py",
    "tests/base/test_hosted_dashboard_runtime.py",
    "tests/base/test_orca_provisioning.py",
    "tests/base/test_openmpi_installer_contract.py",
    "tests/base/test_slurm_submission_contract.py",
    "tests/calc/test_orca_derivative_acceptance.py",
    "tests/calc/test_scientific_job_boundaries.py",
    "tests/calc/test_calculation_service_integrity.py",
    "tests/calc/test_scientific_policy.py",
    "tests/calc/test_xtb_cli_execution.py",
    "tests/calc/test_orca_input_tight_constraints.py",
    "tests/ui/test_gui_spectroscopy_inspector.py",
    "tests/ui/test_hessian_inspector.py",
    "tests/ui/test_cli_run_and_gui_parity.py",
)


def _environment() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items()
           if key not in {"PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE", "PYTEST_ADDOPTS", "PYTEST_PLUGINS"}}
    env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
               PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", QT_QPA_PLATFORM="offscreen",
               OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
    return env


def _run(command: list[str], directory: Path, environment: dict[str, str], log: Path,
         timeout: int = 1800) -> str:
    stderr_log = log.with_name(log.name + ".stderr.log")
    with log.open("w", encoding="utf-8") as stream, stderr_log.open("w", encoding="utf-8") as errors:
        result = subprocess.run(command, cwd=directory, env=environment, stdin=subprocess.DEVNULL,
                                stdout=stream, stderr=errors, timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError(f"{Path(command[0]).name} exited {result.returncode}; inspect {log} and {stderr_log}")
    return log.read_text(encoding="utf-8")


def regressions(output: Path) -> dict:
    from ci_tools.base_ci import evaluate_test_evidence, source_snapshot

    environment = _environment()
    before = source_snapshot(ROOT)
    (output / "source-before.json").write_text(json.dumps(before, indent=2) + "\n")
    outcomes = output / "pytest-outcomes.json"
    outcomes.unlink(missing_ok=True)
    command = [sys.executable, "-m", "pytest", "-c", str(ROOT / "pytest.ini"),
               "--rootdir", str(ROOT), "-p", "ci_tools.pytest_evidence", "-p", "pytest_asyncio.plugin",
               "--cochem-evidence", str(outcomes), "--junitxml", str(output / "pytest.xml"),
               "-q", *HOSTED_TESTS]
    completed = subprocess.run(command, cwd=ROOT, env=environment, check=False)
    after = source_snapshot(ROOT)
    (output / "source-after.json").write_text(json.dumps(after, indent=2) + "\n")
    if not outcomes.is_file():
        raise RuntimeError("Bounded pytest run did not produce actual outcome evidence")
    report = evaluate_test_evidence(json.loads(outcomes.read_text()), {"schema_version": 1, "deferred_tests": []})
    changed = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
    report.update(scope="Bounded public hosted regression set; not the full canonical release gate",
                  selected_test_files=list(HOSTED_TESTS), source_changed=changed,
                  command_exit_code=completed.returncode)
    report["passed"] = report["passed"] and completed.returncode == 0 and not changed
    return report


def wheel(output: Path) -> dict:
    """Build committed source externally and use only a fresh wheel installation."""
    environment = _environment()
    for key in ("COCHEM_ROOT", "COCHEM_WORKSPACE_ROOT", "COCHEM_WORKSPACE", "COCHEM_CONFIG", "VIRTUAL_ENV"):
        environment.pop(key, None)
    environment["COCHEM_ARTIFACT_DIR"] = str(output / "runtime")
    source = output / "reviewed-source"
    source.mkdir()
    archive = output / "reviewed-source.tar"
    revision = _run(["git", "rev-parse", "HEAD"], ROOT, environment, output / "revision.log", 30).strip()
    _run(["git", "archive", "--format=tar", "--output", str(archive), revision], ROOT,
         environment, output / "archive.log", 60)
    with tarfile.open(archive) as bundle:
        bundle.extractall(source, filter="data")
    expected_version = tomllib.loads((source / "pyproject.toml").read_text())["project"]["version"]
    distribution = output / "dist"
    _run([sys.executable, "-m", "build", "--outdir", str(distribution), str(source)],
         output, environment, output / "build.log")
    wheels = list(distribution.glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError("Expected exactly one freshly built BASE wheel")
    venv = output / "wheel-env"
    _run([sys.executable, "-m", "venv", str(venv)], output, environment, output / "venv.log", 120)
    binary_dir = venv / ("Scripts" if os.name == "nt" else "bin")
    python = binary_dir / ("python.exe" if os.name == "nt" else "python")
    command = binary_dir / ("cochem-cli.exe" if os.name == "nt" else "cochem-cli")
    _run([str(python), "-m", "pip", "install", "--disable-pip-version-check", str(wheels[0])],
         output, environment, output / "wheel-install.log")
    _run([str(python), "-m", "pip", "check"], output, environment, output / "pip-check.log", 60)
    for label, argv in (
        ("console-version", [str(command), "--version"]),
        ("module-version", [str(python), "-I", "-m", "cochem_base.cli", "--version"]),
    ):
        version = _run(argv, output, environment, output / f"{label}.log", 90)
        if f"CoChem-BASE {expected_version} " not in version:
            raise RuntimeError(f"Installed CLI does not report the reviewed {expected_version} version")
    _run([str(command), "run", "--help"], output, environment, output / "run-help.log", 90)
    isotope = json.loads(_run([str(command), "mass", "13C", "--json"], output, environment,
                              output / "isotope-mass.json", 90))
    requested = isotope.get("requested_isotope", {})
    if (isotope.get("symbol") != "C" or requested.get("mass_number") != 13
            or not isinstance(requested.get("mass"), (float, int))
            or not math.isfinite(requested["mass"]) or requested["mass"] <= 0):
        raise RuntimeError("Installed isotope database did not return the requested nuclide")
    # This is a real host hardware audit and generated deck, not an engine
    # execution. No ORCA binary or license is needed for the dry-run boundary.
    probe = """
from pathlib import Path
import importlib.metadata, json, sys
import cochem_base
from cochem_base import _version
from cochem_base.core_engine.hardware_profiler import profile_hardware
from cochem_base.calc.calculation_service import CalculationMatrixConfig
from cochem_base.core_engine import cfour_runtime
expected_version = sys.argv[2]
assert importlib.metadata.version('CoChem-BASE') == expected_version
installation = Path(sys.prefix).resolve()
package_roots = [Path(path).resolve() for path in cochem_base.__path__]
assert package_roots and all(path.is_relative_to(installation) for path in package_roots)
assert Path(_version.__file__).resolve().is_relative_to(installation)
assert Path(cfour_runtime.__file__).resolve().is_relative_to(installation)
hardware = profile_hardware()
root = Path(sys.argv[1])
(root / 'hardware.json').write_text(json.dumps({'hardware': {
    'physical_cpu_cores': min(hardware.physical_cores, len(hardware.available_cpu_ids)),
    'ram_mb': hardware.available_ram_bytes // (1024 * 1024)}}))
config = CalculationMatrixConfig(geometry='H 0 0 0\\nH 0 0 0.74', engine='orca',
                                 method='HF', basis_set='STO-3G', is_opt=False)
(root / 'input.json').write_text(config.model_dump_json())
cfour = CalculationMatrixConfig(geometry='H 0 0 0\\nH 0 0 0.74', engine='cfour',
                               method='HF', basis_set='STO-3G', is_opt=False)
(root / 'cfour-input.json').write_text(cfour.model_dump_json())
print(json.dumps({'installed_module': str(Path(_version.__file__).resolve()),
                  'namespace_roots': list(map(str, package_roots)), 'version': expected_version}))
"""
    _run([str(python), "-I", "-c", probe, str(output), expected_version], output, environment, output / "installed-imports.json", 90)
    environment["COCHEM_CONFIG"] = str(output / "hardware.json")
    _run([str(command), "run", "--config", str(output / "input.json"), "--threads", "1",
          "--maxcore-mb", "128", "--dry-run", "--scratch", str(output / "scratch"),
          "--output", str(output / "generated-deck"), "--json"],
         output, environment, output / "deck-generation.json", 90)
    execution = json.loads((output / "generated-deck/execution.json").read_text())
    decks = list((output / "generated-deck").glob("*_job.inp"))
    if execution["status"] != "DECK_GENERATED" or len(decks) != 1:
        raise RuntimeError("Installed wheel did not generate the requested bounded ORCA input deck")
    deck = decks[0].read_text()
    keywords = {word for line in deck.splitlines() if line.startswith("!") for word in line.split()}
    if (not {"HF", "STO-3G"}.issubset(keywords)
            or not any(line.split() == ["%maxcore", "128"] for line in deck.splitlines())
            or not any(line.split() == ["nprocs", "1"] for line in deck.splitlines())):
        raise RuntimeError("Installed ORCA dry-run deck changed the requested method or resource limits")
    _run([str(command), "run", "--config", str(output / "cfour-input.json"), "--threads", "1",
          "--maxcore-mb", "128", "--dry-run", "--scratch", str(output / "cfour-scratch"),
          "--output", str(output / "cfour-generated-deck"), "--json"],
         output, environment, output / "cfour-deck-generation.json", 90)
    cfour_execution = json.loads((output / "cfour-generated-deck/execution.json").read_text())
    cfour_deck = (output / "cfour-generated-deck/ZMAT").read_text()
    if (cfour_execution["status"] != "DECK_GENERATED"
            or not all(keyword in cfour_deck for keyword in
                       ("CALC=HF", "BASIS=STO-3G", "UNITS=BOHR", "MEMORY_SIZE=128", "MEM_UNIT=MB"))):
        raise RuntimeError("Installed CFOUR dry-run deck changed its method, units or resource limits")
    _run([str(python), "-m", "pip", "freeze"], output, environment, output / "installed-dependencies.txt", 60)
    return {"passed": True, "scope": "Clean wheel installation, CLI, isotope database and actual dry-run deck; no chemistry execution",
            "source_revision": revision, "version": expected_version, "wheel": wheels[0].name,
            "wheel_sha256": hashlib.sha256(wheels[0].read_bytes()).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("regressions", "wheel"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    if output.is_relative_to(ROOT):
        parser.error("CI builds, installations and evidence must be outside the checkout")
    output.mkdir(parents=True, exist_ok=True)
    try:
        report = regressions(output) if args.stage == "regressions" else wheel(output)
    except Exception as error:
        report = {"passed": False, "error_type": type(error).__name__, "error": str(error)}
    (output / "acceptance.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
