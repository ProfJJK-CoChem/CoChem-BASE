import os
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from cochem_base.config_loader import resolve_config_path, load_system_config_dict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from core_engine.cochem_core_subprocess_broker import SubprocessBroker, safe_subprocess_run
    HAS_BROKER = True
except ImportError:
    logger.warning("SubprocessBroker not found in core_engine. Falling back to native subprocess.")
    HAS_BROKER = False
    safe_subprocess_run = None


class ExecutionRouter:
    """
    Core Execution Router for the CoChem pipeline.
    Acts as the definitive switchboard, polling the Golden Registry and dynamically 
    forking workloads between local execution and remote HPC schedulers.
    """

    def __init__(self, registry_path: Optional[str] = None) -> None:
        """Initializes the router and loads the Golden Registry."""
        if registry_path:
            self.registry_path = Path(registry_path)
        else:
            self.registry_path = resolve_config_path()

        self.registry = self._load_registry()

    def _load_registry(self) -> Dict[str, Any]:
        """Reads the immutable hardware and routing rules defined during Stage 0."""
        try:
            return load_system_config_dict(self.registry_path)
        except Exception as e:
            logger.error(f"Failed to parse registry at {self.registry_path}: {e}. Defaulting to safe fallback.")
            return {"execution": {"default_engine": "subprocess"}, "engines": {}}

    def resolve_execution_path(self, target_engine: str) -> str:
        """
        Stage 1.0: Registry Polling & Execution Path Resolution.
        Determines the safest path for the incoming computational payload.
        """
        exec_config = self.registry.get("execution", {})
        engines_config = self.registry.get("engines", {})

        default_path = exec_config.get("default_engine", "subprocess")

        if target_engine in engines_config:
            engine_status = engines_config[target_engine].get("status", "unknown")
            if engine_status != "ready":
                logger.warning(f"Engine '{target_engine}' status is '{engine_status}'. Proceeding with caution.")
        else:
            logger.warning(f"Engine '{target_engine}' not found in registry. Using default path.")

        logger.info(f"Resolved execution path for {target_engine}: {default_path}")
        return default_path

    def _dispatch_local(self, payload_command: str, cwd: str, env: Optional[Dict[str, str]] = None) -> int:
        """
        Stage 1.1: Local Dispatch (SubprocessBroker Handoff).
        Executes workloads natively on the local workstation.
        """
        logger.info(f"Dispatching locally: {payload_command} in {cwd}")

        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        if HAS_BROKER and SubprocessBroker:
            broker = SubprocessBroker(cwd=cwd, env=merged_env)
            return broker.execute(payload_command)
        else:
            try:
                if safe_subprocess_run:
                    res = safe_subprocess_run(payload_command, cwd=cwd, timeout=300.0, check=False, env=merged_env, shell=True)
                    return res.returncode
                else:
                    res = subprocess.run(payload_command, shell=True, cwd=cwd, env=merged_env, check=False, timeout=300.0)  # check=True timeout=300.0
                    return res.returncode
            except Exception as e:
                logger.error(f"Local execution failed: {e}")
                return -1

    def _dispatch_hpc(self, payload_command: str, job_name: str, cwd: str, 
                      cores: int = 4, mem_mb: int = 8192, wall_time: str = "24:00:00") -> str:
        """
        Stage 1.2: HPC Dispatch (SLURM Template Rendering & Submission).
        Bypasses local limitations by generating and submitting a .sbatch script.
        """
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
            with open(target_sbatch, 'w', encoding='utf-8') as f:
                f.write(rendered_script)
            logger.info(f"Generated SLURM script: {target_sbatch}")

            if safe_subprocess_run:
                result = safe_subprocess_run(["sbatch", str(target_sbatch)], cwd=cwd, timeout=60.0, check=True)
            else:
                result = subprocess.run(["sbatch", str(target_sbatch)], capture_output=True, text=True, cwd=cwd, timeout=60.0, check=True)

            stdout = result.stdout.strip() if result.stdout else ""
            logger.info(f"HPC Submission successful: {stdout}")
            parts = stdout.split()
            job_id = parts[-1] if parts else "UNKNOWN_ID"
            return job_id

        except FileNotFoundError:
            logger.error("'sbatch' command not found. Are you on an HPC cluster?")
            return "HPC_NOT_AVAILABLE"
        except Exception as e:
            logger.error(f"SLURM submission failed: {e}")
            return "SUBMISSION_FAILED"

    def route_job(self, target_engine: str, payload_command: str, cwd: str, 
                  job_name: str = "cochem_job", **kwargs: Any) -> Any:
        """Main entry point for routing a computational job based on the Golden Registry."""
        os.makedirs(cwd, exist_ok=True)
        path = self.resolve_execution_path(target_engine)

        if path == "sbatch":
            cores = kwargs.get("cores", 4)
            mem_mb = kwargs.get("mem_mb", 8192)
            wall_time = kwargs.get("wall_time", "24:00:00")
            return self._dispatch_hpc(payload_command, job_name, cwd, cores, mem_mb, wall_time)
        else:
            env_overrides = kwargs.get("env", None)
            return self._dispatch_local(payload_command, cwd, env_overrides)