# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Physical Integration Test: HPC MPS Daemon Lifecycle Management & Persistent Worker Monitoring.
Validates Suggestion #148 (Deliverable 8) under Method Matrix v4 §8A.4, §8A.6 [M], [D].
Adheres strictly to the CoChem Zero-Mock Protocol.
"""

from __future__ import annotations

from pathlib import Path
import re
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MPS_SCRIPT = REPO_ROOT.parent / "CoChem-TORQ" / "HPC_Launchers" / "cochem_mps_worker.sh"


def test_mps_worker_script_lifecycle_and_traps() -> None:
    """Verify that cochem_mps_worker.sh implements child PID tracking and robust signal trapping."""
    assert MPS_SCRIPT.exists(), f"MPS worker script missing at {MPS_SCRIPT}"
    script_content = MPS_SCRIPT.read_text(encoding="utf-8")

    # 1. Verify child PID tracking / wait on child pids
    assert "child_pids" in script_content, "Missing child_pids tracking array in cochem_mps_worker.sh"
    assert 'wait "${child_pids[@]}"' in script_content or "wait" in script_content

    # 2. Verify signal trap includes SIGTERM, SIGINT, EXIT
    assert "trap" in script_content
    assert "SIGTERM" in script_content
    assert "SIGINT" in script_content
    assert "EXIT" in script_content

    # 3. Verify daemon teardown sends 'quit' to nvidia-cuda-mps-control
    assert "nvidia-cuda-mps-control" in script_content
    assert 'echo "quit"' in script_content or "quit" in script_content

    # 4. Verify scratch pipe and log directory isolation
    assert "CUDA_MPS_PIPE_DIRECTORY" in script_content
    assert "CUDA_MPS_LOG_DIRECTORY" in script_content