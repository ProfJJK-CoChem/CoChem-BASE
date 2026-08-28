#!/usr/bin/env python3
"""
cochem_base.cli -- Package export module for cli.py
Mandated by SRS Doc 2 Part 1 (§1.6) for headless command-line execution (python -m cochem_base.cli).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from cli import (  # noqa: E402
    PHASE_METADATA,
    TermColor,
    action_audit,
    action_clean,
    action_mass,
    action_phase,
    action_preflight,
    action_setup,
    action_status,
    build_cli_parser,
    execute_phase,
    handle_shutdown_signal,
    load_phase_callable,
    main,
    reap_zombie_processes,
)

__all__ = [
    "PHASE_METADATA",
    "TermColor",
    "action_audit",
    "action_clean",
    "action_mass",
    "action_phase",
    "action_preflight",
    "action_setup",
    "action_status",
    "build_cli_parser",
    "execute_phase",
    "handle_shutdown_signal",
    "load_phase_callable",
    "main",
    "reap_zombie_processes",
]

if __name__ == "__main__":
    sys.exit(main())
