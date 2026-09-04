"""Unit and integration tests for Deliverable 5: Universal Tripartite Workspace Air-Gap & Cross-Platform Local Scratch Resolution (Suggestion #105).

Mandated by Method Matrix v4 (§8A, §8C) and Anti-Spoofing Protocol v4.
Strict Zero-Mock Mandate: Authentic filesystem validation.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import pytest

from Libraries.cochem_torq_environment import (
    resolve_hpc_safe_scratch,
    atomic_promote_to_store,
)


def test_resolve_hpc_safe_scratch_windows_priority(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Verify resolve_hpc_safe_scratch prioritizes LOCALAPPDATA/TEMP over Path.home() roaming profile."""
    sandbox_localapp = tmp_path / "LocalAppData"
    sandbox_temp = tmp_path / "LocalTemp"
    sandbox_localapp.mkdir(parents=True, exist_ok=True)
    sandbox_temp.mkdir(parents=True, exist_ok=True)

    monkeypatch.delenv("COCH_SCRATCH", raising=False)
    monkeypatch.delenv("COCHEM_SCRATCH_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(sandbox_localapp))
    monkeypatch.setenv("TEMP", str(sandbox_temp))

    # Force win32 platform check
    monkeypatch.setattr(sys, "platform", "win32")

    scratch_dir = resolve_hpc_safe_scratch()
    assert scratch_dir.exists()
    assert sandbox_localapp in scratch_dir.parents or sandbox_temp in scratch_dir.parents

    # Crucial: Must never fall back to roaming network share
    home_scratch = Path.home() / ".cochem" / "scratch"
    assert scratch_dir != home_scratch


def test_atomic_promote_to_store_with_sha256(tmp_path: Path):
    """Verify atomic promotion from T_scr to T_store via os.replace with accompanying SHA-256 validation."""
    t_scr = tmp_path / "scratch"
    t_store = tmp_path / "store"
    t_scr.mkdir(parents=True, exist_ok=True)
    t_store.mkdir(parents=True, exist_ok=True)

    candidate_file = t_scr / "result_candidate.json"
    content = b'{"status": "CONVERGED", "energy": -76.4321}'
    candidate_file.write_bytes(content)
    expected_hash = hashlib.sha256(content).hexdigest()

    # Promote to T_store
    final_path, digest_path = atomic_promote_to_store(candidate_file, t_store)

    assert final_path.exists()
    assert final_path.parent == t_store
    assert not candidate_file.exists()  # Atomic replace moved it from T_scr

    # Verify SHA-256 companion file
    assert digest_path.exists()
    digest_text = digest_path.read_text(encoding="utf-8")
    assert expected_hash in digest_text
