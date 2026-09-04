"""Diagnostic Log Failure Triage and Remediation Engine for Electronic Structure Engines.

Parses stdout and stderr logs from ORCA, CFOUR, and xTB upon abnormal process exits,
identifies exact failure signatures, and synthesizes structured remediation guidance.

Method Matrix Reference: Method Matrix §16 (Failure Modes & Remediation Taxonomy).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union


@dataclass
class LogDiagnosticResult:
    """Structured diagnostic failure report and remediation plan."""

    is_failure: bool = False
    failure_mode: str = "NONE"
    matched_pattern: str = ""
    recommendations: list[str] = field(default_factory=list)
    remediation_summary: str = "Calculation completed normally with no known failure patterns."


class LogDiagnosticParser:
    """Diagnostic parser identifying computational failure modes in quantum engine output."""

    # Failure patterns and associated remediation strategies
    _FAILURE_SIGNATURES: list[dict] = [
        {
            "mode": "SCF_NON_CONVERGENCE",
            "regex": re.compile(
                r"(SCF NOT CONVERGED|Convergence failure|SCF failed to converge|The SCF has not converged|scf failed)",
                re.IGNORECASE,
            ),
            "recommendations": [
                "Increase SCF MaxIter from default to 150-200 (%scf MaxIter 150 end)",
                "Toggle Second-Order SCF orbital optimization (! SOSCF)",
                "Switch initial orbital guess strategy (! PModel or ! AutoStart)",
                "Increase orbital damping or DIIS convergence parameters",
            ],
            "summary": "SCF failed to converge within the allotted iteration limit.",
        },
        {
            "mode": "BASIS_LINEAR_DEPENDENCE",
            "regex": re.compile(
                r"(redundant basis functions|linear dependenc|small eigenvalues of overlap matrix)",
                re.IGNORECASE,
            ),
            "recommendations": [
                "Truncate diffuse basis functions (switch to def2-TZVP / def2-SVP)",
                "Lower Cholesky overlap linear dependence threshold (e.g. TolLinearDependence 1e-6)",
                "Prune outermost diffuse exponents from basis set",
            ],
            "summary": "Basis set exhibits near-linear dependence or small overlap eigenvalues.",
        },
        {
            "mode": "MEMORY_EXHAUSTION",
            "regex": re.compile(
                r"(Out of memory|allocation failed|Cannot allocate memory|insufficient memory)",
                re.IGNORECASE,
            ),
            "recommendations": [
                "Increase per-core memory allocation (%maxcore)",
                "Reduce MPI process count to preserve total available system RAM",
                "Switch from conventional to direct/RI integral transformation algorithms",
            ],
            "summary": "Process terminated due to dynamic memory allocation exhaustion.",
        },
        {
            "mode": "GEOMETRY_STEP_LIMIT",
            "regex": re.compile(
                r"(GEOMETRY OPTIMIZATION FAILED TO CONVERGE|Optimization failed|Number of steps exceeded|Maximum number of steps reached)",
                re.IGNORECASE,
            ),
            "recommendations": [
                "Switch coordinate system to Cartesian optimization (! CartesianOpt)",
                "Update model Hessian strategy using xTB or Lindh preconditioning (InHess XTB2)",
                "Increase geometry optimization step limit (%geom MaxStep / MaxIter end)",
            ],
            "summary": "Geometry optimization did not converge within the maximum step count.",
        },
    ]

    @classmethod
    def parse_text(cls, log_content: str) -> LogDiagnosticResult:
        """Analyzes log text to detect quantum chemistry engine failures.
        
        Args:
            log_content: Raw text content of calculation stdout/stderr log.
            
        Returns:
            LogDiagnosticResult containing identified failure mode and remediation recommendations.
        """
        if not log_content:
            return LogDiagnosticResult()

        for sig in cls._FAILURE_SIGNATURES:
            match = sig["regex"].search(log_content)
            if match:
                return LogDiagnosticResult(
                    is_failure=True,
                    failure_mode=sig["mode"],
                    matched_pattern=match.group(0),
                    recommendations=list(sig["recommendations"]),
                    remediation_summary=sig["summary"],
                )

        return LogDiagnosticResult()

    @classmethod
    def parse_file(cls, log_path: Union[Path, str]) -> LogDiagnosticResult:
        """Analyzes a log file on disk."""
        p = Path(log_path).resolve()
        if not p.exists():
            return LogDiagnosticResult(
                is_failure=True,
                failure_mode="FILE_NOT_FOUND",
                matched_pattern=str(p),
                recommendations=["Verify path to output log file"],
                remediation_summary=f"Log file not found: {p}",
            )

        content = p.read_text(encoding="utf-8", errors="ignore")
        return cls.parse_text(content)
