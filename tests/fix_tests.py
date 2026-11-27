"""Maintenance helper to audit silo-setup test files for environment requirements.

Zero-mock compliant replacement for the legacy environment-migration helper.
Scans ``tests/test_silo_setup_*.py`` relative to this directory and reports
referenced host environment keys without mutating test files or relying on
test-time environment patching.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Dict, List

ENV_KEYS: tuple[str, ...] = (
    "CODESPACES",
    "COCHEM_CALCULATION_OS",
    "SLURM_JOB_ID",
    "COCHEM_OS_TARGET",
)

_ENV_LOOKUP_RE = re.compile(r'os\.environ\.get\(\s*["\']([A-Z0-9_]+)["\']')


def audit_silo_setup_tests(tests_dir: Path | None = None) -> Dict[str, List[str]]:
    """Return a mapping of silo-setup test filenames to referenced env keys."""
    root = tests_dir or Path(__file__).resolve().parent
    findings: Dict[str, List[str]] = {}
    for path in sorted(root.glob("test_silo_setup_*.py")):
        content = path.read_text(encoding="utf-8")
        matched = sorted(
            {key for key in _ENV_LOOKUP_RE.findall(content) if key in ENV_KEYS}
        )
        findings[path.name] = matched
    return findings


def main() -> int:
    """Print environment precondition summary for silo-setup test modules."""
    findings = audit_silo_setup_tests()
    for filename, keys in findings.items():
        summary = ", ".join(keys) if keys else "none"
        print(f"{filename}: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
