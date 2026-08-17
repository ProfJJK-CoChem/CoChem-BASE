import json
import os
import sys
from pathlib import Path

import cochem_base.config_loader as config_loader
from cochem_base.config_loader import get_artifact_dir, resolve_mapped_path
from setup.cochem_base_setup import _launch_silo_setup

BASE_ROOT = Path("d:/__CoChem/GitHub-Repo/CoChem-BASE").resolve()
if str(BASE_ROOT) not in sys.path:
    sys.path.insert(0, str(BASE_ROOT))
os.environ['COCHEM_BASE_ROOT'] = str(BASE_ROOT)

resolve_conda_executable = config_loader.resolve_conda_executable


def _map_artifact_dir(value: str) -> Path:
    artifact_dir = resolve_mapped_path(value, Path.home())
    os.environ["COCHEM_ARTIFACT_DIR"] = str(artifact_dir)
    return artifact_dir

print("--- TASK 1: New Install -> Create & Provision ---")
artifact_dir = _map_artifact_dir(str(get_artifact_dir()))
cfg_path = BASE_ROOT / ".cochem_env.json"
cfg = {"artifact_dir": str(artifact_dir)}
with open(cfg_path, "w", encoding="utf-8") as f:
    json.dump(cfg, f)




print(f"Launching silo setup script for {artifact_dir}...")
proc = _launch_silo_setup()
for line in iter(proc.stdout.readline, ''):
    print(line, end='')
proc.wait()
if proc.returncode == 0:
    print("✅ Silo build completed successfully.")
else:
    print(f"❌ Silo build failed with code {proc.returncode}")
    sys.exit(1)

print("\n--- TASK 2: Interface Env / Calc Env -> Set Paths & Test ---")
get_modules_dir = config_loader.get_modules_dir
resolve_executable = config_loader.resolve_executable

def resolve_tool_paths(orca_value=None, mpi_value=None):
    orca_path = resolve_executable(orca_value, env_var='ORCA_CMD', candidates=('orca',))
    mpi_path = resolve_executable(mpi_value, env_var='MPI_CMD', candidates=('mpirun', 'mpiexec'))
    return orca_path, mpi_path

detected_orca, detected_mpi = resolve_tool_paths()
orca_path, mpi_path = resolve_tool_paths(detected_orca, detected_mpi)

if orca_path:
    os.environ['ORCA_CMD'] = str(orca_path)
if mpi_path:
    os.environ['MPI_CMD'] = str(mpi_path)

print(f"ORCA Path: {orca_path}")
print(f"OpenMPI Path: {mpi_path}")
print("Running test suite...")

try:
    from test_suite.run_tests import run_all_preflight_checks
    results = run_all_preflight_checks(
        module_dir=str(get_modules_dir()),
        orca_path=orca_path,
        mpi_path=mpi_path,
    )
    all_passed = True
    for key, res in results.items():
        if key in ['modules', 'orca_single', 'orca_mpi']:
            print(res['message'])
            if not res['status']:
                all_passed = False
    if all_passed:
        print("✅ Environment is fully ready to go!")
    else:
        print("❌ Tests failed.")
        sys.exit(1)
except Exception as e:
    print(f"❌ Error running tests: {e}")
    sys.exit(1)
