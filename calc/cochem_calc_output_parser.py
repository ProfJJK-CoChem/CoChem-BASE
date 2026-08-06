#!/usr/bin/env python3
"""
CoChem-CORE Stage 2.4: Quantum Parser
Enforces strict SCF convergence checks (ΔE < 10^-7), QCSchema JSON-LD exports, 
and applies immutable POSIX read-only locks (chmod 0o444).
"""

import os
import re
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-QuantumParser")

class QuantumParser:
    def __init__(self, artifact_dir: str = None):
        self.artifact_base = Path(artifact_dir) if artifact_dir else Path.home() / "CoChem_Artifacts" / "Scratch"
        self.scf_threshold = 1e-7

    def verify_scf_convergence(self, log_path: Path) -> bool:
        delta_e_pattern = re.compile(r"dE\s*=\s*([-+]?\d*\.\d+[eE]?[-+]?\d*)")
        last_de = None
        
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                match = delta_e_pattern.search(line)
                if match:
                    last_de = abs(float(match.group(1)))
                    
                if "TERMINATED NORMALLY" in line:
                    if last_de is not None and last_de < self.scf_threshold:
                        return True
                    else:
                        logger.error(f"❌ Pseudo-Convergence detected! Final ΔE ({last_de}) >= {self.scf_threshold}")
                        return False
        return False

    def parse_to_qcschema(self, log_path: Path, basin_id: str) -> dict:
        final_energy = None
        energy_pattern = re.compile(r"FINAL SINGLE POINT ENERGY\s+([-+]?\d+\.\d+)")
        
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                match = energy_pattern.search(line)
                if match: final_energy = float(match.group(1))
                    
        if final_energy is None:
            raise ValueError("Could not extract FINAL SINGLE POINT ENERGY from log.")
            
        return {
            "@context": "https://w3id.org/ro/qcschema",
            "schema_name": "qcschema_molecule",
            "schema_version": "1.0",
            "basin_id": basin_id,
            "properties": {"return_energy": final_energy, "scf_iterations": "converged"},
            "provenance": {"creator": "CoChem-CORE", "engine": "ORCA 6.1.1"}
        }

    def apply_immutable_lock(self, file_path: Path) -> None:
        if file_path.exists():
            os.chmod(file_path, 0o444)

    def process_artifact(self, basin_id: str) -> bool:
        log_path = self.artifact_base / f"{basin_id}_job.out"
        json_path = self.artifact_base / f"{basin_id}_qcschema.json"
        
        if not log_path.exists() or not self.verify_scf_convergence(log_path):
            return False
            
        schema = self.parse_to_qcschema(log_path, basin_id)
        with open(json_path, 'w') as f: json.dump(schema, f, indent=4)
            
        self.apply_immutable_lock(log_path)
        self.apply_immutable_lock(json_path)
        return True