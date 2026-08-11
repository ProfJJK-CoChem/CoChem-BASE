#!/usr/bin/env python3
"""
CoChem-CORE: Stage 4.0 - Telemetry, Stability, & Provenance Logger
Implements: Orbital Stability Regex Traps, SCF Oscillation Traps, 
Hardware Provenance Capture, Segfault Hex-Dumping, and JSON-LD Footer Generation.
"""

import os
import re
import json
import logging
import platform
import subprocess
from collections import deque
from datetime import datetime
from typing import Dict, Any, List, Optional
from cochem_base.config_loader import get_artifact_dir

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-TelemetryLogger")


class TelemetryLogger:
    def __init__(self, log_dir: Optional[str] = None, verbosity: str = "info") -> None:
        self.log_dir = os.path.abspath(log_dir) if log_dir else str(get_artifact_dir() / "Logs")
        self.verbosity = verbosity.lower()
        os.makedirs(self.log_dir, exist_ok=True)

        # Regex Traps for Numerical Instability
        self.nan_trap = re.compile(r'(NaN|Infinity|Inf)', re.IGNORECASE)
        self.overlap_trap = re.compile(r'eigenvalue.*?<\s*1\.?0*e-0?[6-9]', re.IGNORECASE)
        self.saddle_trap = re.compile(r'(internal instability|symmetry breaking|saddle point)', re.IGNORECASE)

        # Extract delta E values to catch ping-pong convergence failure
        self.delta_e_pattern = re.compile(r'dE\s*=\s*([-+]?\d*\.\d+[eE]?[-+]?\d*)')
        self.scf_history: deque = deque(maxlen=5)

    def _get_hardware_provenance(self) -> Dict[str, str]:
        """Captures static node identifiers for reproducibility."""
        return {
            "node_hostname": platform.node(),
            "kernel_version": platform.release(),
            "python_version": platform.python_version()
        }

    def process_stream_chunk(self, chunk: str) -> bool:
        """
        Analyzes a streaming block of text.
        Returns False if a fatal numerical trap is sprung.
        """
        if self.nan_trap.search(chunk):
            logger.error("FATAL: NaN/Infinity detected in matrix operation. Triggering abort.")
            return False

        if self.overlap_trap.search(chunk):
            logger.warning("WARNING: Near-linear dependence in basis set detected.")

        if self.saddle_trap.search(chunk):
            logger.warning("WARNING: Wavefunction instability detected. Check spin state.")

        # Ping-Pong Check
        match = self.delta_e_pattern.search(chunk)
        if match:
            de = float(match.group(1))
            self.scf_history.append(de)
            if len(self.scf_history) == 5:
                # Count sign reversals between consecutive iterations
                sign_flips = sum(1 for i in range(len(self.scf_history) - 1) if self.scf_history[i] * self.scf_history[i+1] < 0)
                abs_last = abs(self.scf_history[-1])
                # Trigger abort if energy changes alternate sign (sign_flips >= 3) and magnitude remains un-converged (> 1e-3)
                if sign_flips >= 3 and abs_last > 1e-3:
                    logger.error("FATAL: SCF Oscillation (Ping-Pong) detected. Triggering abort.")
                    return False
        return True

    def _generate_json_ld_footer(self, job_name: str, exit_code: int, config_hash: str) -> str:
        """Generates the QCSchema compliant JSON-LD footer."""
        ld_block = {
            "@context": "https://w3id.org/ro/qcschema",
            "job_id": job_name,
            "provenance": self._get_hardware_provenance(),
            "execution_hash": config_hash,
            "exit_code": exit_code,
            "timestamp_end": datetime.utcnow().isoformat()
        }
        return f"\n\n# --- COCHEM JSON-LD PROVENANCE FOOTER ---\n# {json.dumps(ld_block)}\n"

    def aggregate_and_lock(self, job_name: str, stdout_history: List[str], stderr_history: List[str], exit_code: int, active_hash: str) -> str:
        """
        Assembles the final log, performs hex dumping if a segfault occurred,
        appends the JSON-LD footer, and locks the file as Read-Only.
        """
        log_path = os.path.join(self.log_dir, f"{job_name}_telemetry.log")
        if os.path.exists(log_path):
            try:
                os.chmod(log_path, 0o666)
            except OSError:
                pass

        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"--- CoChem-CORE Telemetry Trace for {job_name} ---\n")
            f.write(f"Exit Code: {exit_code}\n\n")

            for line in stdout_history:
                f.write(line + "\n")

            if exit_code in [139, 134, -11]: 
                f.write("\n\n!!! CRITICAL SEGMENTATION FAULT (Exit Code 139) !!!\n")
                f.write("Dumping last 256 bytes of STDERR as Hexadecimal Trace:\n")
                raw_err = "".join(stderr_history[-20:]).encode('utf-8', errors='replace')
                hex_dump = raw_err[-256:].hex(' ', 2)
                for i in range(0, len(hex_dump), 48):
                    f.write(f"0x{i:04X}: {hex_dump[i:i+48]}\n")

            f.write(self._generate_json_ld_footer(job_name, exit_code, active_hash))

        logger.info(f"Log finalized and archived: {log_path}")

        try:
            os.chmod(log_path, 0o444)
            logger.info(f"Immutability lock (read-only) applied to {log_path}")
        except OSError as e:
            logger.warning(f"Could not set read-only permissions on {log_path}: {e}")

        return log_path


if __name__ == "__main__":
    logger_test = TelemetryLogger(verbosity="info")

    logger.info("Testing Oscillation Trap...")
    safe1 = logger_test.process_stream_chunk("SCF Iteration 12: dE = 0.5")
    safe2 = logger_test.process_stream_chunk("SCF Iteration 13: dE = -0.4")
    safe3 = logger_test.process_stream_chunk("SCF Iteration 14: dE = 0.5")
    safe4 = logger_test.process_stream_chunk("SCF Iteration 15: dE = -0.4")
    safe5 = logger_test.process_stream_chunk("SCF Iteration 16: dE = 0.5")
    logger.info(f"Status after Ping-Pong: {safe5} (Expected: False)")