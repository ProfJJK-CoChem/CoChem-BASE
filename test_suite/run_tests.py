from .test_environment import check_cochem_base_silo, check_artifacts_dir
from .test_modules import check_modules_installed
from .test_orca import run_single_core_orca_test
from .test_mpi import run_multi_core_orca_test

def run_all_preflight_checks(artifact_dir=None, module_dir=None, orca_path="orca"):
    """Runs all environment and testing suite checks for the UI."""
    results = {}
    
    # 1. Environment & Silo Check
    silo_ok, silo_msg = check_cochem_base_silo()
    results['silo'] = {'status': silo_ok, 'message': silo_msg}
    
    # 2. Artifact Directory Check
    art_ok, art_msg = check_artifacts_dir(artifact_dir)
    results['artifacts'] = {'status': art_ok, 'message': art_msg}
    
    # 3. Module Installation Check
    mod_ok, mod_msg = check_modules_installed(module_dir)
    results['modules'] = {'status': mod_ok, 'message': mod_msg}
    
    # 4. ORCA Single Core Test
    orca_ok, orca_msg = run_single_core_orca_test(orca_path)
    results['orca_single'] = {'status': orca_ok, 'message': orca_msg}
    
    # 5. ORCA Multi Core (MPI) Test
    mpi_ok, mpi_msg = run_multi_core_orca_test(orca_path)
    results['orca_mpi'] = {'status': mpi_ok, 'message': mpi_msg}
    
    return results

if __name__ == "__main__":
    import json
    print(json.dumps(run_all_preflight_checks(), indent=2))
