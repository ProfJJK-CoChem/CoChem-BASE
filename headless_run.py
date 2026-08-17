import os
import shutil
import sys
from pathlib import Path

import cochem_base.config_loader as config_loader
from setup.cochem_base_setup import provision_silo

# Setup paths and environment
BASE_ROOT = Path("d:/__CoChem/GitHub-Repo/CoChem-BASE").resolve()
sys.path.insert(0, str(BASE_ROOT))
os.environ['COCHEM_BASE_ROOT'] = str(BASE_ROOT)

def resolve_artifact_path(value):
    path = Path(os.path.expandvars(value)).expanduser()
    if not path.is_absolute():
        path = Path.home() / path
    return path.resolve()

print("==== TASK 1: New Install -> Create & Provision ====")
target_path = resolve_artifact_path(os.environ.get('COCHEM_ARTIFACT_DIR', 'CoChem_Artifacts'))
silo_path = target_path / 'Silos'
if silo_path.exists():
    print(f"Deleting previous Silos directory at {silo_path}...")
    shutil.rmtree(silo_path, ignore_errors=True)
silo_path.mkdir(parents=True, exist_ok=True)
print(f"Created CoChem_Artifacts/Silos at {silo_path}")
print("Setting up minimum environment...")
os.environ['COCHEM_ARTIFACT_DIR'] = str(target_path)



try:
    success, env_dir, already = provision_silo(str(target_path))
    if success:
        print("✅ New installation completed!")
    else:
        print("❌ Installation failed.")
except Exception as e:
    print(f"Error during setup: {e}")

print("\n==== TASK 2: Interface Env: Local-Windows (WSL), Calc Env: GitHub Actions ====")


get_modules_dir = config_loader.get_modules_dir
resolve_executable = config_loader.resolve_executable

# This simulates what the dropdowns do, and then we run tests
interface_env = 'Local-Windows (WSL)'
calc_env = 'GitHub Actions'
os.environ['COCHEM_INTERFACE_ENV'] = interface_env
os.environ['COCHEM_CALC_ENV'] = calc_env

orca_path = resolve_executable(None, env_var='ORCA_CMD', candidates=('orca',))
mpi_path = resolve_executable(None, env_var='MPI_CMD', candidates=('mpirun', 'mpiexec'))
os.environ['ORCA_CMD'] = orca_path
os.environ['MPI_CMD'] = mpi_path

print(f"Interface Env: {interface_env}")
print(f"Calc Env: {calc_env}")
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
    for _key, res in results.items():
        print(res['message'])
        if not res['status']:
            all_passed = False
    if all_passed:
        print("✅ Environment is fully ready to go!")
    else:
        print("❌ Tests failed.")
except Exception as e:
    print(f"❌ Error running tests: {e}")
