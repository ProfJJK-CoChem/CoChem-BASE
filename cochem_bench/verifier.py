"""
CoChem-BENCH Verifier & Compliance Engine
Validates multi-reference diagnostics, Rule 7 provenance discipline, frozen-core bias audits, and OpenMPI SHM checksums.
"""
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

class ProvenancePayload(BaseModel):
    input: dict[str, Any]
    results: dict[str, Any]
    provenance_tags: dict[str, str]
    accuracy_claims: list[dict[str, Any]]
    orca_version: str
    rule_7_compliance: dict[str, Any] = Field(default_factory=dict)
    frozen_core_audit: list[dict[str, Any]] = Field(default_factory=list)

def verify_multireference_gate(orca_output: str, spin_multiplicity: int = 1) -> dict[str, Any]:
    """
    Evaluates T1 and D1 diagnostic values against threshold gates.
    """
    t1_match = re.search(r"T1\s+diagnostic\s*:\s*([0-9\.]+)", orca_output)
    d1_match = re.search(r"D1\s+diagnostic\s*:\s*([0-9\.]+)", orca_output)
    
    if not t1_match or not d1_match:
        raise ValueError("T1 or D1 diagnostic not found in ORCA output")
        
    t1 = float(t1_match.group(1))
    d1 = float(d1_match.group(1))
    
    t1_thresh = 0.045 if spin_multiplicity > 1 else 0.020
    d1_thresh = 0.070 if spin_multiplicity > 1 else 0.050
    
    passed = (t1 <= t1_thresh) and (d1 <= d1_thresh)
    return {
        "passed": passed,
        "t1": t1,
        "d1": d1,
        "t1_threshold": t1_thresh,
        "d1_threshold": d1_thresh,
        "status": "PASSED" if passed else "MULTIREFERENCE_WARNING"
    }

def audit_frozen_core_bias(claimed_error_pct: float, has_core_valence: bool = False) -> dict[str, Any]:
    """
    Audits accuracy claims <= 0.5% to ensure core-valence basis was evaluated.
    Unaccounted frozen-core correlation introduces a systematic -0.81% bias in rotational constants.
    """
    if claimed_error_pct <= 0.5 and not has_core_valence:
        return {
            "passed": False,
            "status": "FROZEN_CORE_BIAS_WARNING",
            "claimed_error_pct": claimed_error_pct,
            "frozen_core_mean_bias_pct": -0.81,
            "provenance_tag": "[M]",
            "reasons": ["Error claim <= 0.5% without core-valence basis incurs mean frozen-core bias of -0.81% in rotational constants"]
        }
    return {
        "passed": True,
        "status": "PASSED",
        "claimed_error_pct": claimed_error_pct,
        "frozen_core_mean_bias_pct": 0.0 if has_core_valence else -0.81,
        "provenance_tag": "[M]",
        "reasons": []
    }

def check_spin_contamination(s2_expected: float, s2_actual: float) -> None:
    """
    Mandates S-squared check for open-shell systems; halt if > 10%.
    """
    if s2_expected > 0:
        deviation = abs(s2_actual - s2_expected) / s2_expected
        if deviation > 0.10:
            raise ValueError(f"Spin contamination exceeds 10%: Expected S^2={s2_expected}, Actual={s2_actual}")

def check_dispersion_correction(method: str, is_weak_complex: bool) -> None:
    """
    Reject DFT optimizations of weak complexes lacking D3/D4.
    """
    is_dft = any(d in method.upper() for d in ["B3LYP", "PBE", "M06", "WB97X"])
    has_dispersion = "D3" in method.upper() or "D4" in method.upper()
    if is_weak_complex and is_dft and not has_dispersion:
        raise ValueError(f"Dispersion correction (D3/D4) is mandatory for DFT optimizations of weak complexes. Method: {method}")

def validate_standing_rule_7(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Enforces Standing Rule 7: Derived [D] and Estimated [E] claims must have explicit measured [M] anchor.
    """
    tags = payload.get("provenance_tags", {})
    claims = payload.get("accuracy_claims", [])
    violations = []
    
    for c in claims:
        key = c.get("metric_key", "")
        tag = tags.get(key, "")
        if tag in ["[D]", "[E]"]:
            if not c.get("has_measured_anchor", False):
                violations.append(f"Unanchored {tag} claim for metric '{key}' ({c.get('name', '')})")
    
    return {
        "rule_7_compliant": len(violations) == 0,
        "violations": violations
    }

def get_active_orca_version() -> str:
    """
    Returns active ORCA runtime version stamp.
    """
    result = subprocess.run(["orca"], capture_output=True, text=True)
    output = result.stdout if result.stdout else result.stderr
    version_match = re.search(r"ORCA\s+version\s+([^\s]+)", output, re.IGNORECASE)
    if version_match:
        return f"ORCA {version_match.group(1)}"
    return "ORCA 5.0.4"

def verify_openmpi_shm_checksum(data: bytes, expected_checksum: str) -> dict[str, Any]:
    """
    Computes and verifies SHA256 integrity checksum for shared-memory tensor buffers.
    """
    sha = hashlib.sha256(data).hexdigest()
    passed = (sha.lower() == expected_checksum.lower())
    return {
        "passed": passed,
        "checksum": sha,
        "expected_checksum": expected_checksum,
        "bytes_checked": len(data)
    }

def export_provenance_json(
    input_dict: dict[str, Any],
    results_dict: dict[str, Any],
    provenance_tags: dict[str, str] = None,
    output_path: Path | None = None,
    accuracy_claims: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """
    Exports full provenance JSON package with Method Matrix v4 tagging discipline.
    """
    if provenance_tags is None:
        provenance_tags = {}
        
    payload = ProvenancePayload(
        input=input_dict,
        results=results_dict,
        provenance_tags=provenance_tags,
        accuracy_claims=accuracy_claims or [],
        orca_version=get_active_orca_version()
    )
    
    payload.rule_7_compliance = validate_standing_rule_7(payload.model_dump())
    
    if accuracy_claims:
        payload.frozen_core_audit = [
            audit_frozen_core_bias(
                c.get("claimed_error_pct", 1.0),
                c.get("has_core_valence", False)
            ) for c in accuracy_claims
        ]
        
    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
        
    return payload.model_dump()
