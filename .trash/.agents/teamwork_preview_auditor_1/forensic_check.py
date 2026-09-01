"""Forensic validation and adversarial audit suite for agent metadata and artifacts.

Audits template content parity, personal path leakages across all directories,
zero-mock mandate compliance in worker workspaces, and delivers structured JSON/text reports.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from enum import Enum
import glob
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from cochem_base.path_sanitization import (
    find_path_leaks,
    get_agent_templates_dir,
    get_agents_dir,
    leak_patterns,
    sanitize_local_paths,
)


class MatchStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    MISSING = "MISSING"
    SKIPPED = "SKIPPED"


class TemplateMatchDetail(BaseModel):
    file_name: str
    status: MatchStatus
    message: str = ""


class TemplateParityReport(BaseModel):
    source_count: int = 0
    target_count: int = 0
    passed_count: int = 0
    failed_count: int = 0
    missing_count: int = 0
    is_clean: bool = True
    details: List[TemplateMatchDetail] = Field(default_factory=list)


class LeakDetail(BaseModel):
    file_rel_path: str
    line_number: int
    line_content: str
    placeholder: str = ""


class LeakScanReport(BaseModel):
    files_scanned: int = 0
    leak_count: int = 0
    is_clean: bool = True
    leaks: List[LeakDetail] = Field(default_factory=list)


class WorkerAnomalyDetail(BaseModel):
    worker_name: str
    is_clean: bool = True
    mock_violations: List[str] = Field(default_factory=list)
    missing_required_files: List[str] = Field(default_factory=list)


class WorkerIntegrityReport(BaseModel):
    workers_checked: int = 0
    clean_workers: int = 0
    is_clean: bool = True
    details: List[WorkerAnomalyDetail] = Field(default_factory=list)


class ForensicSuiteReport(BaseModel):
    timestamp: str
    content_match: TemplateParityReport
    agent_leak_scan: LeakScanReport
    subdirectory_leak_scan: LeakScanReport
    worker_integrity: WorkerIntegrityReport
    is_clean: bool = True


def check_template_content_parity(
    source_dir: Optional[Path] = None, target_dir: Optional[Path] = None
) -> TemplateParityReport:
    """Compares source template files against sanitized target agent markdown files."""
    s_dir = Path(source_dir) if source_dir is not None else get_agent_templates_dir()
    t_dir = Path(target_dir) if target_dir is not None else get_agents_dir()

    report = TemplateParityReport()

    if not s_dir.exists() or not s_dir.is_dir():
        report.details.append(
            TemplateMatchDetail(
                file_name="<ALL>",
                status=MatchStatus.SKIPPED,
                message=f"Source template directory does not exist: {s_dir}",
            )
        )
        report.is_clean = True
        return report

    source_files = sorted(s_dir.glob("*.agent.md"))
    report.source_count = len(source_files)

    for sf in source_files:
        fname = sf.name
        tf = t_dir / fname

        if not tf.exists():
            report.missing_count += 1
            report.details.append(
                TemplateMatchDetail(
                    file_name=fname,
                    status=MatchStatus.MISSING,
                    message=f"Target file {tf} does not exist",
                )
            )
            continue

        report.target_count += 1
        s_raw = sf.read_text(encoding="utf-8").replace("\r\n", "\n")
        t_raw = tf.read_text(encoding="utf-8").replace("\r\n", "\n")

        s_san = sanitize_local_paths(s_raw)

        if s_san == t_raw:
            report.passed_count += 1
            report.details.append(
                TemplateMatchDetail(
                    file_name=fname,
                    status=MatchStatus.PASS,
                    message="Identical after path sanitization",
                )
            )
        else:
            report.failed_count += 1
            report.details.append(
                TemplateMatchDetail(
                    file_name=fname,
                    status=MatchStatus.FAIL,
                    message="Content mismatch between template and agent markdown",
                )
            )

    report.is_clean = report.failed_count == 0 and report.missing_count == 0
    return report


def check_agent_md_leaks(target_dir: Optional[Path] = None) -> LeakScanReport:
    """Scans all *.agent.md files in the target agents directory for personal path leaks."""
    t_dir = Path(target_dir) if target_dir is not None else get_agents_dir()
    report = LeakScanReport()

    if not t_dir.exists():
        return report

    agent_files = sorted(t_dir.glob("*.agent.md"))
    report.files_scanned = len(agent_files)
    patterns = leak_patterns()

    for af in agent_files:
        try:
            lines = af.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue

        for lineno, line in enumerate(lines, 1):
            for pat, placeholder in patterns:
                if pat.search(line):
                    report.leak_count += 1
                    report.leaks.append(
                        LeakDetail(
                            file_rel_path=af.name,
                            line_number=lineno,
                            line_content=line.strip(),
                            placeholder=placeholder,
                        )
                    )

    report.is_clean = report.leak_count == 0
    return report


def check_subdirectory_leaks(target_dir: Optional[Path] = None) -> LeakScanReport:
    """Scans subdirectories and metadata files for hardcoded absolute paths."""
    t_dir = Path(target_dir) if target_dir is not None else get_agents_dir()
    report = LeakScanReport()

    if not t_dir.exists():
        return report

    patterns = leak_patterns()

    for root, _dirs, files in os.walk(t_dir):
        for file in files:
            fpath = Path(root) / file
            rel = str(fpath.relative_to(t_dir))

            # Skip auditor's own folder and ORIGINAL_REQUEST.md
            if rel.startswith("teamwork_preview_auditor_1") or rel == "ORIGINAL_REQUEST.md":
                continue
            # Skip .agent.md files (handled in check_agent_md_leaks)
            if file.endswith(".agent.md"):
                continue

            report.files_scanned += 1
            try:
                content = fpath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for lineno, line in enumerate(content.splitlines(), 1):
                for pat, placeholder in patterns:
                    if pat.search(line):
                        report.leak_count += 1
                        report.leaks.append(
                            LeakDetail(
                                file_rel_path=rel,
                                line_number=lineno,
                                line_content=line.strip(),
                                placeholder=placeholder,
                            )
                        )

    report.is_clean = report.leak_count == 0
    return report


def check_worker_integrity(target_dir: Optional[Path] = None) -> WorkerIntegrityReport:
    """Audits worker workspace directories for zero-mock mandate compliance."""
    t_dir = Path(target_dir) if target_dir is not None else get_agents_dir()
    report = WorkerIntegrityReport()

    if not t_dir.exists():
        return report

    worker_dirs = [
        p for p in t_dir.iterdir()
        if p.is_dir() and (p.name.startswith("teamwork_preview_") or p.name.startswith("worker_")) and p.name != "teamwork_preview_auditor_1"
    ]
    report.workers_checked = len(worker_dirs)

    mock_regex = re.compile(r'\b(?:MagicMock|unittest\.mock|unittest\.mock\.patch|mocker\.patch)\b')

    for wd in worker_dirs:
        detail = WorkerAnomalyDetail(worker_name=wd.name)

        # Scan for mock imports/usages
        for py_file in wd.rglob("*.py"):
            try:
                code = py_file.read_text(encoding="utf-8", errors="ignore")
                for line in code.splitlines():
                    if mock_regex.search(line):
                        detail.mock_violations.append(f"{py_file.name}: {line.strip()}")
            except Exception:
                continue

        if detail.mock_violations:
            detail.is_clean = False
        else:
            report.clean_workers += 1

        report.details.append(detail)

    report.is_clean = (report.clean_workers == report.workers_checked)
    return report


def run_forensic_suite(
    source_dir: Optional[Path] = None,
    target_dir: Optional[Path] = None,
    verbose: bool = True,
) -> ForensicSuiteReport:
    """Executes all forensic checks and returns a consolidated ForensicSuiteReport."""
    s_dir = source_dir or get_agent_templates_dir()
    t_dir = target_dir or get_agents_dir()

    c_match = check_template_content_parity(s_dir, t_dir)
    a_leaks = check_agent_md_leaks(t_dir)
    s_leaks = check_subdirectory_leaks(t_dir)
    w_integrity = check_worker_integrity(t_dir)

    is_overall_clean = (
        c_match.is_clean
        and a_leaks.is_clean
        and s_leaks.is_clean
        and w_integrity.is_clean
    )

    report = ForensicSuiteReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        content_match=c_match,
        agent_leak_scan=a_leaks,
        subdirectory_leak_scan=s_leaks,
        worker_integrity=w_integrity,
        is_clean=is_overall_clean,
    )

    if verbose:
        print("==================================================")
        print("=== FORENSIC CHECK REPORT                      ===")
        print(f"=== Status: {'CLEAN' if is_overall_clean else 'VIOLATIONS FOUND':<34} ===")
        print("==================================================")
        print(f"Template Parity: {'PASS' if c_match.is_clean else 'FAIL'} ({c_match.passed_count}/{c_match.source_count})")
        print(f"Agent Leaks:     {'PASS' if a_leaks.is_clean else 'FAIL'} ({a_leaks.leak_count} leaks in {a_leaks.files_scanned} files)")
        print(f"Subdir Leaks:    {'PASS' if s_leaks.is_clean else 'FAIL'} ({s_leaks.leak_count} leaks in {s_leaks.files_scanned} files)")
        print(f"Worker Mocks:    {'PASS' if w_integrity.is_clean else 'FAIL'} ({w_integrity.clean_workers}/{w_integrity.workers_checked} clean)")

    return report


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint for forensic validation."""
    parser = argparse.ArgumentParser(description="CoChem Forensic Verification Audit Suite")
    parser.add_argument("--json", action="store_true", help="Output results as structured JSON")
    parser.add_argument("--source-dir", type=str, default=None, help="Path to source template directory")
    parser.add_argument("--target-dir", type=str, default=None, help="Path to target agents directory")
    args = parser.parse_args(argv)

    src = Path(args.source_dir) if args.source_dir else None
    tgt = Path(args.target_dir) if args.target_dir else None

    report = run_forensic_suite(source_dir=src, target_dir=tgt, verbose=not args.json)

    if args.json:
        print(json.dumps(report.model_dump(), indent=2))

    return 0 if report.is_clean else 1


if __name__ == "__main__":
    sys.exit(main())

