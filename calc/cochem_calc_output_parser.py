#!/usr/bin/env python3
"""
CoChem-CORE Stage 2.4: Quantum Parser
Enforces strict SCF convergence checks (ΔE < 10^-7), QCSchema JSON-LD exports,
cryptographic SHA-256 artifact verification, and applies immutable POSIX read-only locks (chmod 0o444).
"""

import hashlib
import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class QCSchemaProperties(BaseModel):
    return_energy: float
    scf_iterations: int

class QCSchemaProvenance(BaseModel):
    creator: str
    engine: str
    log_sha256: str
    gbw_sha256: Optional[str] = None

class QCSchemaMolecule(BaseModel):
    context: str = Field(alias="@context")
    schema_name: str
    schema_version: str
    basin_id: str
    properties: QCSchemaProperties
    provenance: QCSchemaProvenance

from cochem_base.config_loader import get_artifact_dir, resolve_mapped_path  # noqa: E402

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-QuantumParser")


class QuantumParser:
    def __init__(self, artifact_dir: Optional[str] = None) -> None:
        if artifact_dir:
            self.artifact_base = resolve_mapped_path(artifact_dir, get_artifact_dir())
        else:
            self.artifact_base = get_artifact_dir() / "Scratch"
        self.artifact_base.mkdir(parents=True, exist_ok=True)
        self.scf_threshold = 1e-7

    def verify_scf_convergence(self, log_path: Path) -> bool:
        delta_e_pattern = re.compile(r"dE\s*=\s*([-+]?\d*\.\d+[eE]?[-+]?\d*)")
        last_de = None

        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()



        for line in content.splitlines():
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

    def verify_basis_saturation(self, log_path: Path) -> None:
        primary_pat = re.compile(r"^\s*(?:Number of basis functions|Basis Dimension|Basis Size)\s*(?:Dim\s*)?(?:\.{3,}|:)\s*(\d+)", re.IGNORECASE)
        aux_pat = re.compile(r"^\s*(?:Number of Aux.*basis functions|# of basis functions in Aux.*?|Auxiliary Basis Dimension|Auxiliary Basis Size)\s*(?:\.{3,}|:)\s*(\d+)", re.IGNORECASE)

        n_primary = None
        n_aux = None

        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                m1 = primary_pat.search(line)
                if m1:
                    val = int(m1.group(1))
                    n_primary = max(n_primary, val) if n_primary is not None else val

                m2 = aux_pat.search(line)
                if m2:
                    val = int(m2.group(1))
                    n_aux = max(n_aux, val) if n_aux is not None else val

        if n_primary is not None and n_aux is not None:
            if n_aux <= n_primary:
                logger.warning(f"[CROWN WARNING] Auxiliary Basis Under-saturation! N_aux ({n_aux}) <= N_primary ({n_primary}). Risk of severe Density Fitting accuracy loss.")

    def check_spin_contamination(self, log_path: Path, threshold: float = 0.1) -> bool:
        """
        Verifies spin contamination (<S**2> vs S*(S+1)) in open/closed shell calculations.
        Returns True if spin contamination is within acceptable limits (diff <= threshold).
        """
        s2_pat = re.compile(r"Expectation value of <S\*\*2>\s*:\s*([-+]?\d*\.\d+)")
        ideal_pat = re.compile(r"Ideal value S\*\(S\+1\)\s*:\s*([-+]?\d*\.\d+)")
        s2_val = None
        ideal_val = None
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                m1 = s2_pat.search(line)
                if m1:
                    s2_val = float(m1.group(1))
                m2 = ideal_pat.search(line)
                if m2:
                    ideal_val = float(m2.group(1))
        if s2_val is not None and ideal_val is not None:
            return abs(s2_val - ideal_val) <= threshold
        return True

    def parse_to_qcschema(self, log_path: Path, basin_id: str, log_sha256: str, gbw_sha256: Optional[str] = None) -> QCSchemaMolecule:
        final_energy = None
        scf_iterations = None
        energy_pattern = re.compile(r"FINAL SINGLE POINT ENERGY\s+([-+]?\d+\.\d+)")
        iter_pattern1 = re.compile(r"Total SCF iterations\s*:\s*(\d+)")
        iter_pattern2 = re.compile(r"SCF ITERATION\s+(\d+)", re.IGNORECASE)

        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                match = energy_pattern.search(line)
                if match:
                    final_energy = float(match.group(1))
                
                m1 = iter_pattern1.search(line)
                if m1:
                    scf_iterations = int(m1.group(1))
                
                m2 = iter_pattern2.search(line)
                if m2:
                    val = int(m2.group(1))
                    if scf_iterations is None or val > scf_iterations:
                        scf_iterations = val

        if final_energy is None:
            raise ValueError("[MISSING DATA] Could not extract FINAL SINGLE POINT ENERGY from log.")
        if scf_iterations is None:
            raise ValueError("[MISSING DATA] Could not extract SCF iterations from log.")

        return QCSchemaMolecule(
            **{"@context": "https://w3id.org/ro/qcschema"},
            schema_name="qcschema_molecule",
            schema_version="1.0",
            basin_id=basin_id,
            properties=QCSchemaProperties(return_energy=final_energy, scf_iterations=scf_iterations),
            provenance=QCSchemaProvenance(creator="CoChem-CORE", engine="ORCA 6.1.1", log_sha256=log_sha256, gbw_sha256=gbw_sha256)
        )

    def apply_immutable_lock(self, file_path: Path) -> None:
        if file_path.exists():
            file_path.chmod(0o444)

    def process_artifact(self, basin_id: str) -> bool:
        log_path = self.artifact_base / f"{basin_id}_job.out"
        json_path = self.artifact_base / f"{basin_id}_qcschema.json"
        gbw_path = self.artifact_base / f"{basin_id}_job.gbw"

        if not log_path.exists():
            raise FileNotFoundError(f"[MISSING DATA] Job log not found: {log_path}")

        if not self.verify_scf_convergence(log_path):
            return False

        if not self.check_spin_contamination(log_path):
            return False

        if not self.check_spin_contamination(log_path):
            return False

        self.verify_basis_saturation(log_path)

        # Compute SHA-256 for provenance
        with open(log_path, 'rb') as f:
            log_sha256 = hashlib.sha256(f.read()).hexdigest()
        
        gbw_sha256 = None
        if gbw_path.exists():
            with open(gbw_path, 'rb') as f:
                gbw_sha256 = hashlib.sha256(f.read()).hexdigest()

        schema = self.parse_to_qcschema(log_path, basin_id, log_sha256, gbw_sha256)

        # Write to a temporary file first for atomic POSIX-compliant write
        tmp_json_path = json_path.with_suffix(".json.tmp")
        schema_dict = schema.model_dump(by_alias=True) if hasattr(schema, 'model_dump') else schema.dict(by_alias=True)
        with open(tmp_json_path, 'w', encoding='utf-8') as f:
            json.dump(schema_dict, f, indent=4)

        os.replace(tmp_json_path, json_path)

        self.apply_immutable_lock(log_path)
        if gbw_path.exists():
            self.apply_immutable_lock(gbw_path)
        self.apply_immutable_lock(json_path)
        return True
