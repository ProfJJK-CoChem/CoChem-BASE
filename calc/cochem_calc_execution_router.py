#!/usr/bin/env python3
"""
CoChem-CORE Stage 2.2: Execution Router
Module: calc/cochem_calc_execution_router.py
Purpose: Hardware-aware POSIX subprocess broker. Wraps heavy binaries,
         provides RAM-disk (/dev/shm) overflow protection, and guarantees zombie thread reaping.
"""

import os
import json
import time
import shutil
import signal
import psutil
import subprocess
import atexit
from pathlib import Path

class ExecutionRouter:
    def __init__(self):
        self.config = self._load_system_config()
        self.artifact_base = Path.home() / "CoChem_Artifacts" / "Scratch"
        self.artifact_base.mkdir(parents=True, exist_ok=True)
        self.active_processes = set()
        atexit.register(self._emergency_reaper)

    def _load_system_config(self) -> dict:
        base_dir = Path(__file__).resolve().parent.parent.parent
        config_path = base_dir / "cochem_system_config.json"
        if not config_path.exists():
            config_path = Path.home() / "CoChem_Artifacts" / "cochem_system_config.json"
        with open(config_path, "r") as f:
            return json.load(f)

    def _prepare_execution_environment(self) -> dict:
        clean_env = os.environ.copy()
        if "LD_LIBRARY_PATH" in clean_env:
            del clean_env["LD_LIBRARY_PATH"]
        cpus = str(self.config.get("hardware", {}).get("physical_cpu_cores", 4))
        clean_env["OMP_NUM_THREADS"] = cpus
        clean_env["MKL_NUM_THREADS"] = cpus
        return clean_env

    def _allocate_scratch_space(self, job_name: str, required_mb: int) -> Path:
        shm_path = Path("/dev/shm")
        if shm_path.exists() and shm_path.is_dir():
            free_mb = psutil.disk_usage(str(shm_path)).free / (1024 * 1024)
            if free_mb > (required_mb * 1.2):
                job_shm_dir = shm_path / f"cochem_{job_name}_{int(time.time())}"
                job_shm_dir.mkdir(parents=True, exist_ok=True)
                return job_shm_dir
        job_disk_dir = self.artifact_base / job_name
        job_disk_dir.mkdir(parents=True, exist_ok=True)
        return job_disk_dir

    def _reap_zombies(self, pid: int):
        try:
            parent = psutil.Process(pid)
            for child in parent.children(recursive=True):
                child.send_signal(signal.SIGKILL)
            parent.send_signal(signal.SIGKILL)
        except psutil.NoSuchProcess:
            pass 

    def _emergency_reaper(self):
        for pgid in self.active_processes:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except Exception:
                pass

    def execute_job(self, input_path: Path, required_mb: int = 4000) -> Path:
        input_path = Path(input_path).resolve()
        job_name = input_path.stem
        orca_path = self.config.get("engines", {}).get("orca", {}).get("path", "orca")
        
        execution_dir = self._allocate_scratch_space(job_name, required_mb)
        target_inp = execution_dir / input_path.name
        target_out = execution_dir / f"{job_name}.out"
        shutil.copy2(input_path, target_inp)

        clean_env = self._prepare_execution_environment()
        process = None
        try:
            with open(target_out, "w") as out_file:
                process = subprocess.Popen(
                    [orca_path, str(target_inp)],
                    stdout=out_file, stderr=subprocess.STDOUT,
                    cwd=str(execution_dir), env=clean_env, preexec_fn=os.setsid 
                )
            pgid = os.getpgid(process.pid)
            self.active_processes.add(pgid)
            process.wait()
            self.active_processes.remove(pgid)
        except (KeyboardInterrupt, Exception):
            if process: self._reap_zombies(process.pid)
            raise
        finally:
            if "/dev/shm" in str(execution_dir):
                for ext in [".out", ".gbw", ".xyz", ".engrad"]:
                    src = execution_dir / f"{job_name}{ext}"
                    if src.exists(): shutil.copy2(src, self.artifact_base / src.name)
                shutil.rmtree(execution_dir, ignore_errors=True)
                final_out_path = self.artifact_base / f"{job_name}.out"
            else:
                final_out_path = target_out

        return final_out_path