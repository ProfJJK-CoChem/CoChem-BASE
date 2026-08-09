import os
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

# Configure basic logging for the router
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# We attempt to import the existing broker. If this script is run in isolation 
# (e.g., during testing before the full package is assembled), we fallback to standard subprocess.
try:
    from core_engine.cochem_core_subprocess_broker import SubprocessBroker
    HAS_BROKER = True
except ImportError:
    logging.warning("SubprocessBroker not found in core_engine. Falling back to native subprocess.")
    HAS_BROKER = False


class ExecutionRouter:
    """
    Core Execution Router for the CoChem pipeline.
    Acts as the definitive switchboard, polling the Golden Registry and dynamically 
    forking workloads between local execution and remote HPC schedulers.
    """
    
class ExecutionRouter:
    """
    Core Execution Router for the CoChem pipeline.
    Acts as the definitive switchboard, polling the Golden Registry and dynamically 
    forking workloads between local execution and remote HPC schedulers.
    """
    
    def __init__(self, registry_path: Optional[str] = None):
        """
        Initializes the router and loads the Golden Registry.
        """
        if registry_path:
            self.registry_path = Path(registry_path)
        else:
            artifact_dir = os.environ.get("COCHEM_ARTIFACT_DIR")
            base_dir = Path(artifact_dir) if artifact_dir else (Path.home() / "CoChem_Artifacts")
            self.registry_path = base_dir / "Registry" / "cochem_system_config.json"
        
        self.registry = self._load_registry()

    def _load_registry(self) -> Dict[str, Any]:
        """
        Reads the immutable hardware and routing rules defined during Stage 0.
        """
        if not self.registry_path.exists():
            logging.error(f"Registry missing at {self.registry_path}. Returning safe fallback config.")
            # Return a fallback configuration if registry doesn't exist for safety
            return {
                "execution": {"default_engine": "subprocess"},
                "engines": {}
            }
            
        try:
            with open(self.registry_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse registry: {e}. Defaulting to safe fallback.")
            return {"execution": {"default_engine": "subprocess"}, "engines": {}}

    def resolve_execution_path(self, target_engine: str) -> str:
        """
        Stage 1.0: Registry Polling & Execution Path Resolution.
        Determines the safest path for the incoming computational payload.
        """
        exec_config = self.registry.get("execution", {})
        engines_config = self.registry.get("engines", {})
        
        # Determine base path (fallback to "subprocess" if missing)
        default_path = exec_config.get("default_engine", "subprocess")
        
        # Verify engine status if it exists in the registry
        if target_engine in engines_config:
            engine_status = engines_config[target_engine].get("status", "unknown")
            if engine_status != "ready":
                logging.warning(f"Engine '{target_engine}' status is '{engine_status}'. Proceeding with caution.")
        else:
            logging.warning(f"Engine '{target_engine}' not found in registry. Using default path.")
            
        logging.info(f"Resolved execution path for {target_engine}: {default_path}")
        return default_path

    def _dispatch_local(self, payload_command: str, cwd: str, env: Optional[Dict[str, str]] = None) -> int:
        """
        Stage 1.1: Local Dispatch (SubprocessBroker Handoff).
        Executes workloads natively on the local workstation.
        """
        logging.info(f"Dispatching locally: {payload_command} in {cwd}")
        
        # Merge environment variables safely to isolate MPI paths if necessary
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
            
        if HAS_BROKER:
            broker = SubprocessBroker(cwd=cwd, env=merged_env)
            return broker.execute(payload_command)
        else:
            # Fallback for isolated testing context
            try:
                result = subprocess.run(
                    payload_command, 
                    shell=True, 
                    cwd=cwd, 
                    env=merged_env,
                    check=False
                )
                return result.returncode
            except Exception as e:
                logging.error(f"Local execution failed: {e}")
                return -1

    def _dispatch_hpc(self, payload_command: str, job_name: str, cwd: str, 
                      cores: int = 4, mem_mb: int = 8192, wall_time: str = "24:00:00") -> str:
        """
        Stage 1.2: HPC Dispatch (SLURM Template Rendering & Submission).
        Bypasses local limitations by generating and submitting a .sbatch script.
        """
        # Read the template from registry or use a default string representation
        hpc_config = self.registry.get("hpc", {})
        template = hpc_config.get("sbatch_template", 
            "#!/bin/bash\n"
            "#SBATCH --job-name={job_name}\n"
            "#SBATCH --ntasks={cores}\n"
            "#SBATCH --mem={mem_mb}M\n"
            "#SBATCH --time={wall_time}\n"
            "\n"
            "{payload_command}\n"
        )
        
        # Render the template safely with explicit key replacement without crashing on bash variables
        replacements = {
            "{job_name}": str(job_name),
            "{cores}": str(cores),
            "{mem_mb}": str(mem_mb),
            "{wall_time}": str(wall_time),
            "{payload_command}": str(payload_command)
        }
        rendered_script = template
        for k, v in replacements.items():
            rendered_script = rendered_script.replace(k, v)


        target_sbatch = Path(cwd) / f"{job_name}_submit.sbatch"
        try:
            with open(target_sbatch, 'w') as f:
                f.write(rendered_script)
            logging.info(f"Generated SLURM script: {target_sbatch}")
            
            # Submit to queue and parse stdout for the Job ID
            result = subprocess.run(["sbatch", str(target_sbatch)], 
                                    capture_output=True, text=True, cwd=cwd)
            
            if result.returncode == 0:
                stdout = result.stdout.strip()
                logging.info(f"HPC Submission successful: {stdout}")
                # Parse something like "Submitted batch job 12345"
                parts = stdout.split()
                job_id = parts[-1] if parts else "UNKNOWN_ID"
                return job_id
            else:
                logging.error(f"SLURM submission failed: {result.stderr}")
                return "SUBMISSION_FAILED"
                
        except FileNotFoundError:
            logging.error("'sbatch' command not found. Are you on an HPC cluster?")
            return "HPC_NOT_AVAILABLE"

    def route_job(self, target_engine: str, payload_command: str, cwd: str, 
                  job_name: str = "cochem_job", **kwargs) -> Any:
        """
        Main entry point for routing a computational job based on the Golden Registry.
        """
        os.makedirs(cwd, exist_ok=True)
        path = self.resolve_execution_path(target_engine)
        
        if path == "sbatch":
            # Extract HPC specific kwargs with fallbacks
            cores = kwargs.get("cores", 4)
            mem_mb = kwargs.get("mem_mb", 8192)
            wall_time = kwargs.get("wall_time", "24:00:00")
            return self._dispatch_hpc(payload_command, job_name, cwd, cores, mem_mb, wall_time)
        else:
            # Default to local subprocess execution
            env_overrides = kwargs.get("env", None)
            return self._dispatch_local(payload_command, cwd, env_overrides)


if __name__ == "__main__":
    import tempfile
    
    # Create a dummy registry for testing
    temp_dir = tempfile.mkdtemp()
    test_registry = Path(temp_dir) / "test_config.json"
    mock_config = {
        "execution": {"default_engine": "subprocess"},
        "engines": {"orca": {"status": "ready"}}
    }
    with open(test_registry, 'w') as f:
        json.dump(mock_config, f)
        
    logging.info(f"Starting ExecutionRouter dry-run test with temp registry: {test_registry}")
    
    # Initialize Router
    router = ExecutionRouter(registry_path=str(test_registry))
    
    # 1. Test Local Dispatch Routing (Default)
    logging.info("--- Testing Local Routing ---")
    local_exit_code = router.route_job(
        target_engine="orca",
        payload_command="echo 'Running Mock ORCA via Subprocess'",
        cwd=temp_dir
    )
    logging.info(f"Local routing exited with code: {local_exit_code}")
    
    # 2. Test HPC Dispatch Routing (Override Registry)
    logging.info("--- Testing HPC Routing ---")
    mock_config["execution"]["default_engine"] = "sbatch"
    with open(test_registry, 'w') as f:
        json.dump(mock_config, f)
        
    router = ExecutionRouter(registry_path=str(test_registry))
    job_id = router.route_job(
        target_engine="orca",
        payload_command="echo 'Running Mock ORCA via SLURM'",
        cwd=temp_dir,
        job_name="mock_orca_job"
    )
    logging.info(f"HPC routing returned Job ID: {job_id}")