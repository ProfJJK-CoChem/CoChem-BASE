"""Packaged wheel identity must agree exactly with the reviewed installer pin."""
import hashlib
import json
from pathlib import Path

from cochem_base.core_engine.orca_distribution_identity import reviewed_orca_distribution


def test_packaged_distribution_identity_matches_installer_bytes():
    raw = (Path(__file__).resolve().parents[2] / "scripts/orca-distribution.json").read_bytes()
    manifest, digest = reviewed_orca_distribution()
    assert manifest == json.loads(raw)
    assert digest == hashlib.sha256(raw).hexdigest()
    manifest["sha256"] = "changed caller data"
    assert reviewed_orca_distribution()[0] == json.loads(raw)
