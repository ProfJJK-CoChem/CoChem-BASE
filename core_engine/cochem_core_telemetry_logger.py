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
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-TelemetryLogger")

class TelemetryLogger:
    def __init__(self, log_dir: str = None, verbosity: str = "info"):
        self.log_dir = os.path.abspath(log_dir) if log_dir else os.path.expanduser("~/CoChem_Artifacts/Logs")
        self.verbosity = verbosity.lower()
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Regex Traps for Numerical Instability
        self.nan_trap = re.compile(r'(NaN|Infinity|Inf)', re.IGNORECASE)
        self.overlap_trap = re.compile(r'eigenvalue.*?<\s*1\.?0*e-0?[6-9]', re.IGNORECASE)
        self.saddle_trap = re.compile(r'(internal instability|symmetry breaking|saddle point)', re.IGNORECASE)
        
        # Extract delta E values to catch ping-pong convergence failure
        self.delta_e_pattern = re.compile(r'dE\s*=\s*([-+]?\d*\.\d+[eE]?[-+]?\d*)')
        self.scf_history = deque(maxlen=5)

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
                # If variance of last 5 delta-E's is near zero but value is large
                # we are stuck in a ping-pong oscillation loop.
                var = sum(abs(x - sum(self.scf_history)/5) for x in self.scf_history)/5
                if var < 1e-8 and abs(self.scf_history[-1]) > 1e-3:
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
        
        with open(log_path, "w") as f:
            f.write(f"--- CoChem-CORE Telemetry Trace for {job_name} ---\n")
            f.write(f"Exit Code: {exit_code}\n\n")
            
            for line in stdout_history:
                f.write(line + "\n")
                
            # If POSIX kill signal (e.g. 139 = SIGSEGV)
            if exit_code in [139, 134, -11]: 
                f.write("\n\n!!! CRITICAL SEGMENTATION FAULT (Exit Code 139) !!!\n")
                f.write("Dumping last 256 bytes of STDERR as Hexadecimal Trace:\n")
                raw_err = "".join(stderr_history[-20:]).encode('utf-8', errors='replace')
                hex_dump = raw_err[-256:].hex(' ', 2)
                for i in range(0, len(hex_dump), 48):
                    f.write(f"0x{i:04X}: {hex_dump[i:i+48]}\n")
                    
            f.write(self._generate_json_ld_footer(job_name, exit_code, active_hash))
            
        logger.info(f"Log finalized and archived: {log_path}")
        
        # Post-Completion Immutable Locking
        os.chmod(log_path, 0o444)
        logger.info(f"Immutability lock (read-only) applied to {log_path}")
        
        return log_path

# If executed directly for testing
if __name__ == "__main__":
    logger_test = TelemetryLogger(verbosity="info")
    
    # Test 1: Trap Detection (Oscillation)
    print("Testing Oscillation Trap...")
    safe1 = logger_test.process_stream_chunk("SCF Iteration 12: dE = 0.5")
    safe2 = logger_test.process_stream_chunk("SCF Iteration 13: dE = -0.4")
    safe3 = logger_test.process_stream_chunk("SCF Iteration 14: dE = 0.5")
    safe4 = logger_test.process_stream_chunk("SCF Iteration 15: dE = -0.4")
    safe5 = logger_test.process_stream_chunk("SCF Iteration 16: dE = 0.5")
    print(f"Status after Ping-Pong: {safe5} (Expected: False)")