"""Autonomous Quantum Log Diagnostic Parser (Method Matrix v4 §16).

Parses standard output and error streams from quantum chemical codes (ORCA, CFOUR, CREST)
upon calculation failure, identifies failure signatures according to the standardized failure
taxonomy, and synthesizes automated remediation directives.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Union


class FailureCategory:
    SCF_NON_CONVERGENCE = "SCF_NON_CONVERGENCE"
    GRID_INSTABILITY = "GRID_INSTABILITY"
    OPTIMIZER_DIVERGENCE = "OPTIMIZER_DIVERGENCE"
    MEMORY_SCRATCH_EXHAUSTION = "MEMORY_SCRATCH_EXHAUSTION"
    SYNTAX_OR_DECK_ERROR = "SYNTAX_OR_DECK_ERROR"
    UNKNOWN_FAILURE = "UNKNOWN_FAILURE"


class QuantumLogDiagnosticParser:
    """Parses quantum calculation logs and suggests automated remediation strategies."""

    # Taxonomy signatures mapped to failure categories
    SIGNATURES: Dict[str, List[re.Pattern[str]]] = {
        FailureCategory.SCF_NON_CONVERGENCE: [
            re.compile(r"SCF\s+NOT\s+CONVERGED", re.IGNORECASE),
            re.compile(r"OPTIMIZATION\s+RUN\s+DID\s+NOT\s+CONVERGE", re.IGNORECASE),
            re.compile(r"Maximum\s+number\s+of\s+iterations\s+reached", re.IGNORECASE),
            re.compile(r"DIIS\s+error", re.IGNORECASE),
            re.compile(r"Energy\s+change\s+too\s+large", re.IGNORECASE),
            re.compile(r"SCF\s+failed\s+to\s+converge", re.IGNORECASE),
        ],
        FailureCategory.GRID_INSTABILITY: [
            re.compile(r"Numerical\s+instability\s+in\s+DFT\s+grid", re.IGNORECASE),
            re.compile(r"Integration\s+weights\s+sum", re.IGNORECASE),
            re.compile(r"Grid\s+error", re.IGNORECASE),
            re.compile(r"Radial\s+grid\s+overflow", re.IGNORECASE),
        ],
        FailureCategory.OPTIMIZER_DIVERGENCE: [
            re.compile(r"GEOMETRY\s+OPTIMIZATION\s+FAILED", re.IGNORECASE),
            re.compile(r"Trust\s+radius\s+too\s+small", re.IGNORECASE),
            re.compile(r"Gradient\s+norm\s+exploded", re.IGNORECASE),
            re.compile(r"Internal\s+coordinates\s+error", re.IGNORECASE),
            re.compile(r"Hessian\s+not\s+positive\s+definite", re.IGNORECASE),
            re.compile(r"Step\s+rejection\s+limit\s+exceeded", re.IGNORECASE),
            re.compile(r"gradient\s+explosion", re.IGNORECASE),
        ],
        FailureCategory.MEMORY_SCRATCH_EXHAUSTION: [
            re.compile(r"Out\s+of\s+memory", re.IGNORECASE),
            re.compile(r"ALLOCATION\s+FAILED", re.IGNORECASE),
            re.compile(r"No\s+space\s+left\s+on\s+device", re.IGNORECASE),
            re.compile(r"disk\s+full", re.IGNORECASE),
            re.compile(r"scratch\s+directory\s+full", re.IGNORECASE),
            re.compile(r"Insufficient\s+memory", re.IGNORECASE),
            re.compile(r"Memory\s+allocation\s+error", re.IGNORECASE),
        ],
        FailureCategory.SYNTAX_OR_DECK_ERROR: [
            re.compile(r"Unknown\s+keyword", re.IGNORECASE),
            re.compile(r"Syntax\s+error\s+in\s+input", re.IGNORECASE),
            re.compile(r"Basis\s+set\s+not\s+found", re.IGNORECASE),
            re.compile(r"CFOUR\s+execution\s+aborted", re.IGNORECASE),
        ],
    }

    REMEDIATIONS: Dict[str, Dict[str, Any]] = {
        FailureCategory.SCF_NON_CONVERGENCE: {
            "directives": [
                "Switch to damped SCF or SlowConv protocol (! SlowConv)",
                "Increase max iterations: %scf MaxIter 300 end",
                "Apply level-shifting: %scf Shift 0.2 ShiftErr 0.001 end",
                "Start with lower-level guess (e.g., PModel or Hueckel)",
            ],
            "input_patch": "! SlowConv\n%scf\n  MaxIter 300\n  Shift 0.2\n  ShiftErr 0.001\nend",
        },
        FailureCategory.GRID_INSTABILITY: {
            "directives": [
                "Switch from loose grid to dynamic grid progression (defgrid1 -> defgrid3)",
                "Tighten radial integration grid: ! DefGrid3",
            ],
            "input_patch": "! DefGrid3",
        },
        FailureCategory.OPTIMIZER_DIVERGENCE: {
            "directives": [
                "Enforce model Hessian (InHess XTB2 or Lindh) instead of exact Hessian (§8B.3)",
                "Tighten %geom trust radii: %geom Trust 0.10 MaxStep 0.15 end",
                "Engage GEDIIS step interpolation algorithm",
            ],
            "input_patch": "%geom\n  InHess XTB2\n  Trust 0.10\n  MaxStep 0.15\nend",
        },
        FailureCategory.MEMORY_SCRATCH_EXHAUSTION: {
            "directives": [
                "Clamp %maxcore to 0.80 * RAM_free (§8A)",
                "Redirect scratch directory ($COCH_SCRATCH) to high-speed NVMe mount",
                "Enable disk-saving RI/DLPNO integral approximations",
            ],
            "input_patch": "%maxcore <clamped_memory_mb>\n# Redirect $COCH_SCRATCH to local scratch mount",
        },
        FailureCategory.SYNTAX_OR_DECK_ERROR: {
            "directives": [
                "Verify input deck syntax against software manual",
                "Check for basis set typos or missing element parameters",
            ],
            "input_patch": "# Verify deck spelling and format",
        },
        FailureCategory.UNKNOWN_FAILURE: {
            "directives": [
                "Check system exit code and consult complete execution log",
            ],
            "input_patch": "# Diagnostic inspection required",
        },
    }

    @classmethod
    def parse_log_text(cls, log_content: str, engine: str = "ORCA") -> Dict[str, Any]:
        """Parses log string content and classifies failures."""
        detected_categories: List[str] = []
        matched_lines: List[str] = []

        lines = log_content.splitlines()
        for line_idx, line in enumerate(lines):
            for category, patterns in cls.SIGNATURES.items():
                for pat in patterns:
                    if pat.search(line):
                        if category not in detected_categories:
                            detected_categories.append(category)
                        matched_lines.append(f"Line {line_idx + 1}: {line.strip()}")
                        break

        primary_category = (
            detected_categories[0] if detected_categories else FailureCategory.UNKNOWN_FAILURE
        )
        remediation_info = cls.REMEDIATIONS.get(
            primary_category, cls.REMEDIATIONS[FailureCategory.UNKNOWN_FAILURE]
        )

        return {
            "engine": engine.upper(),
            "failure_detected": bool(detected_categories),
            "primary_failure": primary_category,
            "all_categories": detected_categories,
            "matched_lines": matched_lines[:10],
            "recommended_directives": remediation_info["directives"],
            "suggested_patch": remediation_info["input_patch"],
        }

    @classmethod
    def parse_file(cls, file_path: Union[str, Path], engine: str = "ORCA") -> Dict[str, Any]:
        """Reads and parses an output log file from disk."""
        path_obj = Path(file_path).resolve()
        if not path_obj.is_file():
            raise FileNotFoundError(f"Log file does not exist: {path_obj}")

        content = path_obj.read_text(encoding="utf-8", errors="ignore")
        result = cls.parse_log_text(content, engine=engine)
        result["file_path"] = str(path_obj)
        return result

    @classmethod
    def to_json(cls, diagnostic_payload: Dict[str, Any], indent: int = 2) -> str:
        """Serializes diagnostic report into JSON string for Voila/Jupyter GUI display."""
        return json.dumps(diagnostic_payload, indent=indent)
