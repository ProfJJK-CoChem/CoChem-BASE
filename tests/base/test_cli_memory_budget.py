"""Real CLI parsing/deck boundaries; no electronic calculation is represented."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("maxcore_mb, accepted", [(128, True), (0, False), (10**12, False)])
def test_cli_memory_budget_reaches_native_deck_boundary(tmp_path, audited_registry, maxcore_mb, accepted):
    config = tmp_path / "input.json"
    config.write_text(json.dumps({"geometry": "H 0 0 0\nH 0 0 .74", "method": "HF",
                                  "basis_set": "STO-3G", "is_opt": False}))
    published = tmp_path / "published"
    completed = subprocess.run(
        [sys.executable, str(ROOT / "cli.py"), "run", "--config", str(config), "--threads", "1",
         "--maxcore-mb", str(maxcore_mb), "--dry-run", "--scratch", str(tmp_path / "scratch"),
         "--output", str(published), "--json"],
        env={**os.environ, "COCHEM_CONFIG": str(audited_registry)},
        capture_output=True, text=True, timeout=30,
    )
    if accepted:
        assert completed.returncode == 0, completed.stderr
        assert json.loads(completed.stdout)["status"] == "DECK_GENERATED"
        deck, = published.glob("*_job.inp")
        assert f"%maxcore {maxcore_mb}" in deck.read_text()
        assert not (published / "result.json").exists()
    else:
        assert completed.returncode != 0
        assert "memory" in completed.stderr.lower() or "maxcore_mb" in completed.stderr
        assert not published.exists()
