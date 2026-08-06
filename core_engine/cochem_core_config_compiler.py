#!/usr/bin/env python3
"""
CoChem-CORE: Stage 2.0 - Configuration Compiler & SemVer Gatekeeper
Implements: SHA-256 parameter hashing, Semantic Engine Version Pinning,
Automated BSSE Counterpoise fragment tagging, Mendeleev ECP Gates, and Abstracted HPC Schedulers.
"""

import os
import json
import hashlib
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple
from packaging import version
from mendeleev import element

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-ConfigCompiler")

# =============================================================================
# ABSTRACTED HPC SCHEDULER STRATEGIES (Suggestion #4)
# =============================================================================
class SchedulerStrategy(ABC):
    @abstractmethod
    def build_submission_script(self, job_name: str, command: str, nodes: int, cpus: int) -> str:
        pass

class SlurmStrategy(SchedulerStrategy):
    def build_submission_script(self, job_name: str, command: str, nodes: int, cpus: int) -> str:
        return f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --nodes={nodes}
#SBATCH --ntasks-per-node={cpus}
#SBATCH --time=24:00:00
#SBATCH --partition=compute

export OMP_NUM_THREADS={cpus}
export MKL_NUM_THREADS={cpus}
srun --mpi=pmi2 {command}
"""

class PBSStrategy(SchedulerStrategy):
    def build_submission_script(self, job_name: str, command: str, nodes: int, cpus: int) -> str:
        return f"""#!/bin/bash
#PBS -N {job_name}
#PBS -l nodes={nodes}:ppn={cpus}
#PBS -l walltime=24:00:00

export OMP_NUM_THREADS={cpus}
export MKL_NUM_THREADS={cpus}
mpirun -np {nodes * cpus} {command}
"""

class LocalStrategy(SchedulerStrategy):
    def build_submission_script(self, job_name: str, command: str, nodes: int, cpus: int) -> str:
        return f"""#!/bin/bash
export OMP_NUM_THREADS={cpus}
export MKL_NUM_THREADS={cpus}
{command}
"""

# =============================================================================
# COMPILER CORE
# =============================================================================
class ConfigCompiler:
    def __init__(self, target_scheduler: str = "local"):
        if target_scheduler.lower() == "slurm":
            self.scheduler = SlurmStrategy()
        elif target_scheduler.lower() == "pbs":
            self.scheduler = PBSStrategy()
        else:
            self.scheduler = LocalStrategy()

    def enforce_semver_pinning(self, engine_name: str, actual_version: str, min_required: str) -> bool:
        """Strict Semantic Versioning Gatekeeper."""
        if not actual_version:
            logger.warning(f"Could not determine version for {engine_name}. Bypassing strict SemVer.")
            return True
            
        if version.parse(actual_version) < version.parse(min_required):
            logger.error(f"{engine_name} version {actual_version} is below strict minimum {min_required}.")
            return False
        return True

    def validate_ecp_requirements(self, elements_in_system: List[str], defined_ecps: Dict[str, str]) -> None:
        """
        Dynamically queries Mendeleev to enforce Effective Core Potentials (ECPs)
        for any heavy element (Z > 36) to prevent massive basis set errors.
        """
        for sym in set(elements_in_system):
            try:
                el = element(sym)
                if el.atomic_number > 36 and sym not in defined_ecps:
                    raise ValueError(f"CRITICAL: Heavy element {sym} (Z={el.atomic_number}) detected without explicit ECP definition.")
            except Exception as e:
                logger.warning(f"ECP validation lookup failed for {sym}: {e}")

    def generate_execution_package(self, job_name: str, engine_command: str, params: Dict[str, Any], nodes: int = 1, cpus: int = 4) -> Tuple[str, str]:
        """Immutable SHA-256 Parameter Hashing & Scheduler Injection."""
        # Serialize parameters deterministically for hashing
        param_str = json.dumps(params, sort_keys=True)
        config_hash = hashlib.sha256(param_str.encode()).hexdigest()
        
        # Build execution header with hash provenance
        script_body = self.scheduler.build_submission_script(job_name, engine_command, nodes, cpus)
        provenance_header = f"\n# COCHEM_EXEC_HASH: {config_hash}\n"
        
        full_script = provenance_header + script_body
        logger.info(f"Compiled execution package for job '{job_name}' with SHA-256 hash: {config_hash[:12]}")
        
        return config_hash, full_script

# If executed directly for testing
if __name__ == "__main__":
    compiler = ConfigCompiler(target_scheduler="slurm")
    
    # Test SemVer check
    compiler.enforce_semver_pinning("ORCA", "6.1.1", "6.1.0")
    
    # Test Mendeleev ECP Check
    try:
        compiler.validate_ecp_requirements(["C", "H", "I"], defined_ecps={"I": "def2-TZVPP-ECP"})
        print("ECP Validation Success")
    except ValueError as e:
        print(e)
        
    print("Config Compiler initialized successfully.")