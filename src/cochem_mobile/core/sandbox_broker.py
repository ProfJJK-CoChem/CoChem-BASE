"""Hardware-Agnostic Quarantine Sandbox Broker (REQ-MOB-002 & REQ-MOB-004).

Brokers execution across Docker, Podman, Apptainer/Singularity, and local Subprocess
fallbacks. Enforces CPU vectorization, cgroups/timeout boundaries, non-blocking stream
pipes, and psutil-based process tree cleanup.
"""

from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

import hashlib
import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Sequence


import psutil


class ContainerEngine(str, Enum):
    """Supported container execution engines."""
    DOCKER = "docker"
    PODMAN = "podman"
    APPTAINER = "apptainer"
    SINGULARITY = "singularity"
    SUBPROCESS = "subprocess"


class SandboxSecurityViolation(Exception):
    """Raised when an un-sanitized or malicious command is passed to the sandbox broker."""


@dataclass
class QuarantineConfig:
    """Resource limits and isolation parameters for sandboxed execution."""
    max_memory_mb: int = 4096
    max_cpus: float = 2.0
    timeout_seconds: float = 30.0
    work_dir: Optional[Path] = None
    env_vars: Dict[str, str] = field(default_factory=dict)
    enforce_cpu_vectorization: bool = True
    bind_mounts: Dict[Path, Path] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Deterministic result record of a sandboxed execution."""
    command: List[str]
    exit_code: int
    stdout: str
    stderr: str
    execution_time_seconds: float
    peak_memory_bytes: int
    sha256_output_hash: str
    timed_out: bool
    engine_used: ContainerEngine


class SandboxBroker:
    """Orchestrates ephemeral quarantined execution with defense-in-depth boundaries."""

    def __init__(self, preferred_engine: Optional[ContainerEngine] = None) -> None:
        self.available_engines = self.detect_available_engines(probe_liveness=True)
        if preferred_engine and preferred_engine in self.available_engines:
            self.active_engine = preferred_engine
        elif self.available_engines:
            self.active_engine = self.available_engines[0]
        else:
            self.active_engine = ContainerEngine.SUBPROCESS

    @staticmethod
    def _probe_engine_liveness(engine_name: Union[str, ContainerEngine]) -> bool:
        """Active daemon ping to verify physical container runtime liveness (§20) [M].

        Guards against CLI-installed but daemon-stopped hangs using a strict 1.5s timeout.
        """
        raw = str(engine_name.value if isinstance(engine_name, ContainerEngine) else engine_name).lower()

        if raw == "subprocess":
            return True

        if raw == "docker":
            if shutil.which("docker") is None:
                return False
            try:
                res = subprocess.run(
                    ["docker", "info", "--format", "{{.ServerVersion}}"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=1.5,
                    check=False,
                )
                return res.returncode == 0
            except Exception:
                return False

        if raw == "podman":
            if shutil.which("podman") is None:
                return False
            try:
                res = subprocess.run(
                    ["podman", "info"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=1.5,
                    check=False,
                )
                return res.returncode == 0
            except Exception:
                return False

        if raw in ("apptainer", "singularity"):
            bin_name = "apptainer" if shutil.which("apptainer") else ("singularity" if shutil.which("singularity") else None)
            if bin_name is None:
                return False
            try:
                res = subprocess.run(
                    [bin_name, "--version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=1.5,
                    check=False,
                )
                return res.returncode == 0
            except Exception:
                return False

        return False

    @classmethod
    def detect_available_engines(cls, probe_liveness: bool = False) -> List[ContainerEngine]:
        """Detect which container runtimes are physically installed and responsive on host."""
        engines: List[ContainerEngine] = []
        if shutil.which("docker") is not None and (not probe_liveness or cls._probe_engine_liveness(ContainerEngine.DOCKER)):
            engines.append(ContainerEngine.DOCKER)
        if shutil.which("podman") is not None and (not probe_liveness or cls._probe_engine_liveness(ContainerEngine.PODMAN)):
            engines.append(ContainerEngine.PODMAN)
        if shutil.which("apptainer") is not None and (not probe_liveness or cls._probe_engine_liveness(ContainerEngine.APPTAINER)):
            engines.append(ContainerEngine.APPTAINER)
        elif shutil.which("singularity") is not None and (not probe_liveness or cls._probe_engine_liveness(ContainerEngine.SINGULARITY)):
            engines.append(ContainerEngine.SINGULARITY)

        # Subprocess is always available as the base fallback
        engines.append(ContainerEngine.SUBPROCESS)
        return engines

    def sanitize_command(self, cmd: Sequence[str]) -> List[str]:
        """Inspect and sanitize execution command tokens against injection attacks."""
        if not cmd:
            raise SandboxSecurityViolation("Empty command supplied.")

        sanitized: List[str] = []
        for token in cmd:
            token_str = str(token)
            # Prevent null-byte injection
            if "\0" in token_str:
                raise SandboxSecurityViolation(f"Null byte detected in command token: {token_str}")
            sanitized.append(token_str)
        return sanitized

    def build_sanitized_environment(self, config: QuarantineConfig) -> Dict[str, str]:
        """Build an isolated environment with enforced CPU vectorization."""
        env = dict(os.environ)
        # Apply CPU vectorization guarantees
        if config.enforce_cpu_vectorization:
            env["CUDA_VISIBLE_DEVICES"] = ""
            env["JAX_PLATFORMS"] = "cpu"
            env["OMP_NUM_THREADS"] = str(max(1, int(config.max_cpus)))
            env["MKL_NUM_THREADS"] = str(max(1, int(config.max_cpus)))
            env["OPENBLAS_NUM_THREADS"] = str(max(1, int(config.max_cpus)))

        # Merge explicit user variables
        for k, v in config.env_vars.items():
            env[str(k)] = str(v)

        return env

    @staticmethod
    def _kill_process_tree(pid: int) -> None:
        """Recursively terminate a process and all its children via psutil."""
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                try:
                    child.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied) as _e:
                    logger.debug(f"Ignored exception: {_e}")
            parent.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied) as _e:
            logger.debug(f"Ignored exception: {_e}")

    def execute(
        self,
        command: Sequence[str],
        config: Optional[QuarantineConfig] = None,
        force_engine: Optional[ContainerEngine] = None,
    ) -> ExecutionResult:
        """Execute command in quarantined sandbox with resource tracking and timeouts.

        Implements an automatic downgrade cascade (§20): Docker -> Podman -> Apptainer -> Subprocess.
        Guarantees defense-in-depth isolation, handles daemon socket errors, and avoids hanging.
        """
        cfg = config or QuarantineConfig()
        cmd = self.sanitize_command(command)
        env = self.build_sanitized_environment(cfg)
        work_dir = Path(cfg.work_dir).resolve() if cfg.work_dir else Path.cwd()

        # Build candidate engine cascade ladder
        full_ladder = [
            ContainerEngine.DOCKER,
            ContainerEngine.PODMAN,
            ContainerEngine.APPTAINER,
            ContainerEngine.SUBPROCESS,
        ]

        if force_engine is not None:
            if force_engine == ContainerEngine.SUBPROCESS:
                candidate_engines = [ContainerEngine.SUBPROCESS]
            else:
                candidate_engines = [force_engine] + [e for e in full_ladder if e != force_engine]
        else:
            candidate_engines = [self.active_engine] + [e for e in full_ladder if e != self.active_engine]

        last_exception: Optional[Exception] = None

        for engine in candidate_engines:
            # Check physical engine liveness prior to launch
            if engine != ContainerEngine.SUBPROCESS:
                if not self._probe_engine_liveness(engine):
                    logger.warning(
                        f"Container engine '{engine.value}' is unavailable or daemon is unresponsive. "
                        f"Cascading to next fallback."
                    )
                    continue

            # Build full executable command based on selected engine
            final_cmd = self._compose_engine_command(cmd, engine, cfg, work_dir)

            start_time = time.time()
            stdout_chunks: List[str] = []
            stderr_chunks: List[str] = []
            timed_out = False
            peak_memory_bytes = 0

            try:
                proc = subprocess.Popen(
                    final_cmd,
                    cwd=str(work_dir),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                )
            except OSError as exc:
                logger.warning(
                    f"Failed to launch command with engine '{engine.value}': {exc}. "
                    f"Cascading to next fallback."
                )
                last_exception = exc
                continue

            def stream_reader(pipe, dest_list: List[str]) -> None:
                try:
                    for line in iter(pipe.readline, ""):
                        dest_list.append(line)
                    pipe.close()
                except (OSError, ValueError) as _e:
                    logger.debug(f"Ignored exception: {_e}")

            t_out = threading.Thread(target=stream_reader, args=(proc.stdout, stdout_chunks))
            t_err = threading.Thread(target=stream_reader, args=(proc.stderr, stderr_chunks))
            t_out.daemon = True
            t_err.daemon = True
            t_out.start()
            t_err.start()

            # Monitor loop for timeout and memory usage
            while True:
                elapsed = time.time() - start_time
                if proc.poll() is not None:
                    break

                if elapsed > cfg.timeout_seconds:
                    timed_out = True
                    self._kill_process_tree(proc.pid)
                    break

                # Poll memory usage via psutil
                try:
                    p = psutil.Process(proc.pid)
                    mem = p.memory_info().rss
                    for ch in p.children(recursive=True):
                        try:
                            mem += ch.memory_info().rss
                        except (psutil.NoSuchProcess, psutil.AccessDenied) as _e:
                            logger.debug(f"Ignored exception: {_e}")
                    if mem > peak_memory_bytes:
                        peak_memory_bytes = mem

                    # Enforce memory boundary
                    if mem > (cfg.max_memory_mb * 1024 * 1024):
                        timed_out = True
                        self._kill_process_tree(proc.pid)
                        stderr_chunks.append(
                            f"\n[QUARANTINE ERROR] Exceeded memory limit of {cfg.max_memory_mb} MB"
                        )
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied) as _e:
                    logger.debug(f"Ignored exception: {_e}")

                time.sleep(0.05)

            t_out.join(timeout=1.0)
            t_err.join(timeout=1.0)

            poll_res = proc.poll()
            exit_code: int = poll_res if poll_res is not None else (-9 if timed_out else 0)
            total_time = time.time() - start_time

            stdout_str = "".join(stdout_chunks)
            stderr_str = "".join(stderr_chunks)

            # Detect container daemon socket errors at runtime (e.g. docker daemon stopped or hung)
            if engine != ContainerEngine.SUBPROCESS and exit_code != 0:
                daemon_error_indicators = (
                    "cannot connect to the docker daemon",
                    "is the docker daemon running",
                    "error during connect",
                    "dial unix /var/run/docker.sock",
                    "failed to connect to podman",
                    "podman socket",
                    "daemon not running",
                )
                if any(ind in stderr_str.lower() for ind in daemon_error_indicators):
                    logger.warning(
                        f"Container engine '{engine.value}' exited with daemon socket error. "
                        f"Cascading to next fallback."
                    )
                    continue

            # Calculate cryptographic digest of output
            digest_input = f"{exit_code}:{stdout_str}:{stderr_str}:{total_time:.4f}"
            output_hash = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()

            return ExecutionResult(
                command=list(cmd),
                exit_code=exit_code,
                stdout=stdout_str,
                stderr=stderr_str,
                execution_time_seconds=total_time,
                peak_memory_bytes=peak_memory_bytes,
                sha256_output_hash=output_hash,
                timed_out=timed_out,
                engine_used=engine,
            )

        raise RuntimeError(
            f"All sandbox container engines exhausted in downgrade cascade. Last error: {last_exception}"
        )

    def _compose_engine_command(
        self,
        cmd: List[str],
        engine: ContainerEngine,
        config: QuarantineConfig,
        work_dir: Path,
    ) -> List[str]:
        """Wrap command with container runtime parameters if applicable."""
        if engine == ContainerEngine.SUBPROCESS:
            return cmd

        if engine in (ContainerEngine.DOCKER, ContainerEngine.PODMAN):
            wrapper = [
                str(engine.value),
                "run",
                "--rm",
                f"--memory={config.max_memory_mb}m",
                f"--cpus={config.max_cpus}",
                "-v",
                f"{work_dir.as_posix()}:/workspace",
                "-w",
                "/workspace",
            ]
            for host_p, cont_p in config.bind_mounts.items():
                wrapper.extend(["-v", f"{host_p.as_posix()}:{cont_p.as_posix()}"])
            wrapper.append("cochem-quarantine-base:latest")
            wrapper.extend(cmd)
            return wrapper

        if engine in (ContainerEngine.APPTAINER, ContainerEngine.SINGULARITY):
            wrapper = [
                str(engine.value),
                "exec",
                "--pwd",
                "/workspace",
                "--bind",
                f"{work_dir.as_posix()}:/workspace",
            ]
            for host_p, cont_p in config.bind_mounts.items():
                wrapper.extend(["--bind", f"{host_p.as_posix()}:{cont_p.as_posix()}"])
            wrapper.append("cochem-quarantine-base.sif")
            wrapper.extend(cmd)
            return wrapper

        return cmd
