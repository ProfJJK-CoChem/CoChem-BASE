#!/usr/bin/env python3
"""
CoChem-CORE: Stage 4.0 - Telemetry, Stability, & Provenance Logger
Implements: Orbital Stability Regex Traps, SCF Oscillation Traps,
Hardware Provenance Capture, Segfault Hex-Dumping, and JSON-LD Footer Generation.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import re
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from cochem_base.config_loader import get_artifact_dir

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-TelemetryLogger")

CRITICAL_SEGFAULT_EXIT_CODES = {139, 134, -11, 0xC0000005, -1073741819}


class TelemetryLogger:
    def __init__(self, log_dir: Optional[Union[str, Path]] = None, verbosity: str = "info") -> None:
        if log_dir:
            self.log_dir = Path(log_dir).resolve()
        else:
            self.log_dir = (get_artifact_dir() / "Logs").resolve()
        self.verbosity = verbosity.lower()
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self.warnings_count = 0
        self.errors_count = 0
        self._trap_events: List[Dict[str, Any]] = []

        # Regex Traps for Numerical Instability (strictly word bounded to avoid matching 'Infrared')
        self.nan_trap = re.compile(r'\b(NaN|Infinity|-?Inf)\b', re.IGNORECASE)
        self.overlap_trap = re.compile(r'eigenvalue.*?<\s*1\.?0*e-0?[6-9]', re.IGNORECASE)
        self.saddle_trap = re.compile(r'(internal instability|symmetry breaking|saddle point)', re.IGNORECASE)

        # Extract delta E values to catch ping-pong convergence failure
        self.delta_e_pattern = re.compile(r'dE\s*=\s*([-+]?\d*\.\d+[eE]?[-+]?\d*)')
        self.scf_history: deque[float] = deque(maxlen=5)

    def is_clean(self) -> bool:
        """Returns True if zero errors have been triggered."""
        with self._lock:
            return self.errors_count == 0

    def get_trap_events(self) -> List[Dict[str, Any]]:
        """Returns recorded trap events."""
        with self._lock:
            return list(self._trap_events)

    def reset_history(self) -> None:
        """Resets counters and histories."""
        with self._lock:
            self.warnings_count = 0
            self.errors_count = 0
            self.scf_history.clear()
            self._trap_events.clear()

    def _get_hardware_provenance(self) -> Dict[str, Any]:
        """Captures static node identifiers for reproducibility."""
        logical_cores = os.cpu_count() or 1
        return {
            "node_hostname": platform.node(),
            "kernel_version": platform.release(),
            "python_version": platform.python_version(),
            "system": platform.system(),
            "machine": platform.machine(),
            "logical_cpu_cores": logical_cores,
        }

    def process_stream_chunk(self, chunk: str) -> bool:
        """
        Analyzes a streaming block of text.
        Returns False if a fatal numerical trap is sprung.
        """
        with self._lock:
            if self.nan_trap.search(chunk):
                logger.error("FATAL: NaN/Infinity detected in matrix operation. Triggering abort.")
                self.errors_count += 1
                self._trap_events.append({"type": "FATAL_NAN_INFINITY", "chunk": chunk})
                return False

            if self.overlap_trap.search(chunk):
                logger.warning("WARNING: Near-linear dependence in basis set detected.")
                self.warnings_count += 1
                self._trap_events.append({"type": "WARN_NEAR_LINEAR_DEPENDENCE", "chunk": chunk})

            if self.saddle_trap.search(chunk):
                logger.warning("WARNING: Wavefunction instability detected. Check spin state.")
                self.warnings_count += 1
                self._trap_events.append({"type": "WARN_WAVEFUNCTION_INSTABILITY", "chunk": chunk})

            # Ping-Pong Check
            match = self.delta_e_pattern.search(chunk)
            if match:
                try:
                    de = float(match.group(1))
                    self.scf_history.append(de)
                    if len(self.scf_history) == 5:
                        # Count sign reversals between consecutive iterations
                        sign_flips = sum(
                            1 for i in range(len(self.scf_history) - 1)
                            if self.scf_history[i] * self.scf_history[i + 1] < 0
                        )
                        abs_last = abs(self.scf_history[-1])
                        # Trigger abort if energy changes alternate sign (sign_flips >= 3) and magnitude remains un-converged (> 1e-3)
                        if sign_flips >= 3 and abs_last > 1e-3:
                            logger.error("FATAL: SCF Oscillation (Ping-Pong) detected. Triggering abort.")
                            self.errors_count += 1
                            self._trap_events.append({"type": "FATAL_SCF_OSCILLATION", "chunk": chunk})
                            return False
                except ValueError:
                    pass

            return True

    def _generate_json_ld_footer(self, job_name: str, exit_code: int, config_hash: str) -> str:
        """Generates the QCSchema compliant JSON-LD footer."""
        ld_block = {
            "@context": "https://w3id.org/ro/qcschema",
            "job_id": job_name,
            "provenance": self._get_hardware_provenance(),
            "execution_hash": config_hash,
            "exit_code": exit_code,
            "status": "SUCCESS" if exit_code == 0 else "FAILED",
            "timestamp_end": datetime.now(timezone.utc).isoformat(),
        }
        return f"\n\n# --- COCHEM JSON-LD PROVENANCE FOOTER ---\n# {json.dumps(ld_block)}\n"

    def aggregate_and_lock(
        self,
        job_name: str,
        stdout_history: Sequence[str],
        stderr_history: Sequence[str],
        exit_code: int,
        active_hash: str,
    ) -> str:
        """
        Assembles the final log, performs hex dumping if a segfault occurred,
        appends the JSON-LD footer, and locks the file as Read-Only.
        """
        log_path = self.log_dir / f"{job_name}_telemetry.log"
        if log_path.exists():
            try:
                os.chmod(str(log_path), 0o666)
            except OSError:
                pass

        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"--- CoChem-CORE Telemetry Trace for {job_name} ---\n")
            f.write(f"Exit Code: {exit_code}\n\n")

            for line in stdout_history:
                f.write(line + "\n")

            if exit_code in CRITICAL_SEGFAULT_EXIT_CODES:
                f.write("\n\n!!! CRITICAL SEGMENTATION FAULT (Exit Code: %s) !!!\n" % exit_code)
                f.write("Dumping last 256 bytes of STDERR as Hexadecimal Trace:\n")
                raw_err = "".join(stderr_history[-20:]).encode('utf-8', errors='replace')
                if not raw_err:
                    raw_err = b"Segmentation fault core dumped\n"
                hex_dump = raw_err[-256:].hex(' ', 2)
                for i in range(0, len(hex_dump), 48):
                    f.write(f"0x{i:04X}: {hex_dump[i:i+48]}\n")

            f.write(self._generate_json_ld_footer(job_name, exit_code, active_hash))

        logger.info(f"Log finalized and archived: {log_path}")

        try:
            os.chmod(str(log_path), 0o444)
            logger.info(f"Immutability lock (read-only) applied to {log_path}")
        except OSError as e:
            logger.warning(f"Could not set read-only permissions on {log_path}: {e}")

        return str(log_path)


__all__ = [
    "CRITICAL_SEGFAULT_EXIT_CODES",
    "TelemetryLogger",
]

