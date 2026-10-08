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


def test_normalizes_all_requested_isotope_aliases(tmp_path: Path) -> None:
    source = tmp_path / "aliases.xyz"
    source.write_text("4\nisotope aliases\nC-13 0 0 0\nC13 0 0 1.4\nD 0 1 0\nT 0 0 2.4\n")
    symbols, _, _ = adapter.read_xyz(source)
    assert symbols == ["13C", "13C", "2H", "3H"]


def test_mixed_fragment_scan_masses_match_ingestion_and_preview() -> None:
    """Mixture weights move a mixed-element COM away from its nuclear COM."""
    import numpy as np
    from mendeleev import element
    from cochem_base.geometry.nuclide_geometry import resolve_nuclear_identity
    from cochem_base.interfaces.torq_research import scan_points_request

    symbols = ["H", "Cl", "O", "H", "H"]
    coordinates = np.asarray([[0, 0, 0], [1.3, 0, 0], [4, 0, 0],
                              [4.9572, 0, 0], [3.76, .9273, 0]], dtype=float)
    fragments = [[0, 1], [2, 3, 4]]
    options = {"method": {"name": "hf", "basis": "sto-3g"}, "charge": 0,
               "multiplicity": 1, "fragments": fragments,
               "distances_angstrom": [4.0], "cores": 1, "memory_mb": 512}
    elements, masses = adapter._scan_nuclear_masses(symbols)
    assert elements == symbols
    assert masses == list(resolve_nuclear_identity(symbols).masses_u)
    chlorine = element("Cl")
    principal = max((isotope for isotope in chlorine.isotopes if isotope.abundance),
                    key=lambda isotope: isotope.abundance)
    assert masses[1] == principal.mass
    assert masses[1] != chlorine.atomic_weight

    point = np.asarray(scan_points_request(symbols, coordinates.tolist(), options)[0]["geometry_angstrom"])
    centers = [np.average(point[group], axis=0, weights=np.asarray(masses)[group])
               for group in fragments]
    assert np.linalg.norm(centers[1] - centers[0]) == pytest.approx(4.0, abs=1e-12)
    mixture = np.asarray([float(element(symbol).atomic_weight) for symbol in symbols])
    mixture_centers = [np.average(point[group], axis=0, weights=mixture[group])
                       for group in fragments]
    assert abs(np.linalg.norm(mixture_centers[1] - mixture_centers[0]) - 4.0) > 1e-6


def test_scan_preserves_explicit_measured_isotopes_and_refuses_unassigned_radioelements() -> None:
    from mendeleev import element
    from cochem_base.geometry.nuclide_geometry import resolve_nuclear_identity

    symbols = ["13C", "37Cl", "18O", "D", "T"]
    elements, masses = adapter._scan_nuclear_masses(symbols)
    assert elements == ["C", "Cl", "O", "H", "H"]
    assert masses == list(resolve_nuclear_identity(symbols).masses_u)
    assert masses[1] == next(isotope.mass for isotope in element("Cl").isotopes
                             if isotope.mass_number == 37)
    with pytest.raises(ValueError, match="measured"):
        adapter._scan_nuclear_masses(["Tc"])
    with pytest.raises(ValueError, match="measured"):
        adapter._scan_nuclear_masses(["999C"])
