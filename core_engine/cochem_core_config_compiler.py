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

class ECPValidationError(ValueError):
    """Raised when a heavy element lacks a required ECP definition."""
    pass

# =============================================================================
# ABSTRACTED HPC SCHEDULER STRATEGIES (Suggestion #4)
# =============================================================================
class SchedulerStrategy(ABC):
    @abstractmethod
    def build_submission_script(self, job_name: str, command: str, nodes: int, cpus: int, **kwargs) -> str:
        """Abstract method for rendering HPC submission scripts."""
        ...


class SlurmStrategy(SchedulerStrategy):
    def __init__(self, walltime: str = "24:00:00", partition: str = "compute"):
        self.walltime = walltime
        self.partition = partition

    def build_submission_script(self, job_name: str, command: str, nodes: int, cpus: int, walltime: str = None, partition: str = None) -> str:
        wtime = walltime or self.walltime
        part = partition or self.partition
        return f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --nodes={nodes}
#SBATCH --ntasks-per-node={cpus}
#SBATCH --time={wtime}
#SBATCH --partition={part}

export OMP_NUM_THREADS={cpus}
export MKL_NUM_THREADS={cpus}
srun --mpi=pmi2 {command}
"""

class PBSStrategy(SchedulerStrategy):
    def __init__(self, walltime: str = "24:00:00"):
        self.walltime = walltime

    def build_submission_script(self, job_name: str, command: str, nodes: int, cpus: int, walltime: str = None, **kwargs) -> str:
        wtime = walltime or self.walltime
        return f"""#!/bin/bash
#PBS -N {job_name}
#PBS -l nodes={nodes}:ppn={cpus}
#PBS -l walltime={wtime}

export OMP_NUM_THREADS={cpus}
export MKL_NUM_THREADS={cpus}
mpirun -np {nodes * cpus} {command}
"""

class LocalStrategy(SchedulerStrategy):
    def build_submission_script(self, job_name: str, command: str, nodes: int, cpus: int, **kwargs) -> str:
        return f"""#!/bin/bash
export OMP_NUM_THREADS={cpus}
export MKL_NUM_THREADS={cpus}
{command}
"""

# =============================================================================
# COMPILER CORE
# =============================================================================
class ConfigCompiler:
    def __init__(self, target_scheduler: str = "local", walltime: str = "24:00:00", partition: str = "compute"):
        if target_scheduler.lower() == "slurm":
            self.scheduler = SlurmStrategy(walltime=walltime, partition=partition)
        elif target_scheduler.lower() == "pbs":
            self.scheduler = PBSStrategy(walltime=walltime)
        else:
            self.scheduler = LocalStrategy()

    def enforce_semver_pinning(self, engine_name: str, actual_version: str, min_required: str) -> bool:
        """Strict Semantic Versioning Gatekeeper."""
        if not actual_version:
            logger.error(f"Version string is empty or missing for dependency {engine_name}.")
            raise ValueError(f"Version string is empty or missing for dependency {engine_name}")
            
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
                atomic_num = el.atomic_number
            except Exception as e:
                # Fallback if mendeleev lookup fails
                atomic_num = 0
            
            if atomic_num > 36 and sym not in defined_ecps:
                raise ECPValidationError(f"Heavy element {sym} (Z={atomic_num}) missing ECP specification")

    def generate_execution_package(self, job_name: str, engine_command: str, params: Dict[str, Any], nodes: int = 1, cpus: int = 4, walltime: str = None, partition: str = None) -> Tuple[str, str]:
        """Immutable SHA-256 Parameter Hashing & Scheduler Injection."""
        # Serialize parameters deterministically for hashing
        param_str = json.dumps(params, sort_keys=True)
        config_hash = hashlib.sha256(param_str.encode()).hexdigest()
        
        # Build execution header with hash provenance
        script_body = self.scheduler.build_submission_script(job_name, engine_command, nodes, cpus, walltime=walltime, partition=partition)
        provenance_header = f"\n# COCHEM_EXEC_HASH: {config_hash}\n"
        
        full_script = provenance_header + script_body
        logger.info(f"Compiled execution package for job '{job_name}' with SHA-256 hash: {config_hash[:12]}")
        
        return config_hash, full_script

# If executed directly for testing
if __name__ == "__main__":
    compiler = ConfigCompiler(target_scheduler="slurm", walltime="12:00:00", partition="gpu")
    
    # Test SemVer check
    compiler.enforce_semver_pinning("ORCA", "6.1.1", "6.1.0")
    
    # Test Mendeleev ECP Check
    try:
        compiler.validate_ecp_requirements(["C", "H", "I"], defined_ecps={"I": "def2-TZVPP-ECP"})
        print("ECP Validation Success")
    except ECPValidationError as e:
        print(e)
        
    print("Config Compiler initialized successfully.")