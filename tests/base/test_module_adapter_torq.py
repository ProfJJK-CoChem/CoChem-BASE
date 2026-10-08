"""Input/artifact boundaries for the TORQ subprocess adapter (no provider doubles)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "module_adapter_torq.py"
_SPEC = importlib.util.spec_from_file_location("module_adapter_torq", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
adapter = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(adapter)


@pytest.mark.parametrize(
    "content",
    [
        "3\ntruncated\nO 0 0 0\nH 0 0 1\n",
        "2\nextra\nH 0 0 0\nH 0 0 1\nH 0 1 0\n",
        "2\nnonfinite\nH 0 0 0\nH 0 0 nan\n",
        "2\nnonfinite\nH 0 0 0\nH 0 0 inf\n",
        "2\ncoincident\nH 0 0 0\nH 0 0 0\n",
        "2\nbad symbol\nH 0 0 0\nH; 0 0 1\n",
        "2\nextra field\nH 0 0 0\nH 0 0 1 2\n",
        "1\nno molecular rotor\nHe 0 0 0\n",
    ],
)
def test_rejects_incomplete_or_invalid_geometry(tmp_path: Path, content: str) -> None:
    source = tmp_path / "invalid.xyz"
    source.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        adapter.read_xyz(source)


def test_preserves_explicit_isotope_symbols_and_origin_atom(tmp_path: Path) -> None:
    source = tmp_path / "isotope.xyz"
    source.write_text("2\nisotope\n13C 0 0 0\n18O 0 0 1.13\n", encoding="utf-8")
    symbols, positions, digest = adapter.read_xyz(source)
    assert symbols == ["13C", "18O"]
    assert positions == [[0.0, 0.0, 0.0], [0.0, 0.0, 1.13]]
    assert len(digest) == 64


def test_preserves_existing_artifact(tmp_path: Path) -> None:
    target = tmp_path / "result.json"
    original = b'{"observation": "retain"}\n'
    target.write_bytes(original)
    with pytest.raises(FileExistsError):
        adapter._publish_json(target, {"observation": "replacement"})
    assert target.read_bytes() == original
    assert list(tmp_path.iterdir()) == [target]


def test_rejects_nonfinite_report_before_creating_file(tmp_path: Path) -> None:
    target = tmp_path / "result.json"
    with pytest.raises(ValueError):
        adapter._publish_json(target, {"observation": float("nan")})
    assert not target.exists()


def test_publishes_strict_report(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "result.json"
    adapter._publish_json(target, {"observation": None, "reason": "undefined axis"})
    assert json.loads(target.read_text()) == {"observation": None, "reason": "undefined axis"}
