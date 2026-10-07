"""Strict geometry and atomic artifact boundaries for the TOPOS adapter."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "module_adapter_topos.py"
SPEC = importlib.util.spec_from_file_location("base_topos_adapter_tests", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)


@pytest.mark.parametrize("comment", ["Water", ""])
def test_accepts_complete_xyz_with_blank_or_nonempty_comment(comment):
    geometry = f"3\n{comment}\nO 0 0 0\nH 0.757 0.587 0\nH -0.757 0.587 0\n"
    assert ADAPTER.validate_xyz_bytes(geometry.encode()) == 3


@pytest.mark.parametrize(
    "geometry",
    [
        "3\nMissing atom\nO 0 0 0\nH 0 0 1\n",
        "1\nExtra atom\nH 0 0 0\nH 0 0 1\n",
        "1\nMultiple frames\nH 0 0 0\n1\nOther\nH 0 0 1\n",
        "1\nUnknown symbol\nGhost 0 0 0\n",
        "1\nGhost center\nX 0 0 0\n",
        "1\nIsotope label\nD 0 0 0\n",
        "1\nNoncanonical case\nh 0 0 0\n",
        "1\nNonfinite\nH nan 0 0\n",
        "1\nNonfinite\nH 0 inf 0\n",
        "1\nUnbounded\nH 1e99 0 0\n",
        "1\nExtended properties\nH 0 0 0 arbitrary\n",
        "0\nEmpty\n",
        "2049\nToo many atoms\nH 0 0 0\n",
    ],
)
def test_rejects_incomplete_nonfinite_or_ambiguous_geometry(geometry):
    with pytest.raises(ValueError):
        ADAPTER.validate_xyz_bytes(geometry.encode())


def test_atomic_json_refuses_overwrite_and_nonfinite_results(tmp_path):
    output = tmp_path / "report.json"
    ADAPTER._write_exclusive_json(output, {"observed": 0.0})
    with pytest.raises(FileExistsError):
        ADAPTER._write_exclusive_json(output, {"replacement": True})
    assert json.loads(output.read_text()) == {"observed": 0.0}
    bad_output = tmp_path / "bad.json"
    with pytest.raises(ValueError):
        ADAPTER._write_exclusive_json(bad_output, {"observed": float("nan")})
    assert not bad_output.exists()
    assert not list(tmp_path.glob(".topos-result-*"))
