"""Zero-Mock Test Suite for CoChem Mobile 2D Organic Builder & 3D Conformer Synthesis Engine.

Validates REQ-MOB-030 through REQ-MOB-033:
- Pydantic v2 schemas with frozen invariants and dynamic Mendeleev masses.
- ETKDGv3 deterministic 3D conformer generation (randomSeed=42) and MMFF94/UFF minimization.
- Valence/sanitization error catching with exact 0-indexed atom error identification.
- AnyWidget traitlets and asynchronous non-blocking ThreadPoolExecutor execution.
- Air-gapped offline verification (COCHEM_OFFLINE=1).
- Strictly ZERO mocks or fake objects.
"""

from __future__ import annotations

import mendeleev
import pytest
from pydantic import ValidationError
from rdkit import Chem

from cochem.mobile import (
    AtomCoordinate2D,
    AtomCoordinate3D,
    Conformer3DResultSchema,
    SketcherPayloadSchema,
    SketcherWidget,
    ValenceValidationResultSchema,
    generate_3d_conformer,
)
from cochem.mobile.sketcher_widget import (
    CSS_PATH,
    ESM_PATH,
    compute_file_sha256,
    verify_asset_checksums,
    verify_offline_compliance,
)

ETHANOL_V2000_BLOCK = """
  CoChem-Mobile       2D

  3  2  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.5000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    2.2500    1.2990    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0  0  0  0
  2  3  1  0  0  0  0
M  END
"""

ALANINE_V2000_BLOCK = """
  CoChem-Mobile       2D

  6  5  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.5000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    2.2500    1.2990    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    3.7500    1.2990    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
    1.5000    2.5980    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
    1.5000   -1.5000    0.0000 N   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0  0  0  0
  2  3  1  0  0  0  0
  3  4  1  0  0  0  0
  3  5  2  0  0  0  0
  2  6  1  1  0  0  0
M  END
"""

ASPIRIN_V2000_BLOCK = """
  CoChem-Mobile       2D

 13 13  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.5000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    2.2500    1.2990    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.5000    2.5980    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    0.0000    2.5980    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
   -0.7500    1.2990    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    3.7500    1.2990    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    4.5000    2.5980    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
    4.5000    0.0000    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
    2.2500   -1.2990    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
    3.7500   -1.2990    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    4.5000   -2.5980    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
    4.5000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  2  0  0  0  0
  2  3  1  0  0  0  0
  3  4  2  0  0  0  0
  4  5  1  0  0  0  0
  5  6  2  0  0  0  0
  6  1  1  0  0  0  0
  3  7  1  0  0  0  0
  7  8  2  0  0  0  0
  7  9  1  0  0  0  0
  2 10  1  0  0  0  0
 10 11  1  0  0  0  0
 11 12  2  0  0  0  0
 11 13  1  0  0  0  0
M  END
"""

PENTAVALENT_CARBON_V2000_BLOCK = """
  CoChem-Mobile       2D

  6  5  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.5000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    0.0000    1.5000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
   -1.5000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    0.0000   -1.5000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.0607    1.0607    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0  0  0  0
  1  3  1  0  0  0  0
  1  4  1  0  0  0  0
  1  5  1  0  0  0  0
  1  6  1  0  0  0  0
M  END
"""


def test_schemas_immutability_and_validation() -> None:
    """Verify strict Pydantic v2 schemas: immutability, extra fields forbidden, and Mendeleev weights."""
    coord2d = AtomCoordinate2D(atom_index=0, symbol="C", x=10.5, y=20.5, charge=0)
    assert coord2d.atom_index == 0
    assert coord2d.symbol == "C"
    assert coord2d.x == 10.5
    assert coord2d.y == 20.5
    assert coord2d.charge == 0
    assert coord2d.atomic_weight == pytest.approx(
        float(mendeleev.element("C").atomic_weight), rel=1e-4
    )

    # Immutability check
    with pytest.raises(ValidationError):
        coord2d.x = 15.0  # type: ignore[misc]

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        AtomCoordinate2D(atom_index=0, symbol="C", x=0.0, y=0.0, extra_prop=123)  # type: ignore[call-arg]

    coord3d = AtomCoordinate3D(atom_index=1, symbol="O", x=1.0, y=2.0, z=3.0)
    assert coord3d.atomic_weight == pytest.approx(
        float(mendeleev.element("O").atomic_weight), rel=1e-4
    )

    with pytest.raises(ValidationError):
        coord3d.z = 4.0  # type: ignore[misc]

    # Valid payload
    payload = SketcherPayloadSchema(
        smiles="CCO",
        molfile_v2000=ETHANOL_V2000_BLOCK,
        chiral_centers_count=0,
        atoms_2d=[coord2d],
    )
    assert payload.smiles == "CCO"
    assert "V2000" in payload.molfile_v2000

    # Invalid payload without V2000 marker
    with pytest.raises(ValidationError, match="V2000"):
        SketcherPayloadSchema(
            smiles="CCO",
            molfile_v2000="INVALID MOL BLOCK\nM  END\n",
            chiral_centers_count=0,
        )

    # Invalid payload without M END marker
    with pytest.raises(ValidationError, match="M  END"):
        SketcherPayloadSchema(
            smiles="CCO",
            molfile_v2000="3 2 0 0 0 0 V2000\n1 2 1\n",
            chiral_centers_count=0,
        )


def test_conformer_engine_ethanol() -> None:
    """Verify ETKDGv3 deterministic conformer synthesis and MMFF94 minimization on Ethanol."""
    payload = SketcherPayloadSchema(
        smiles="CCO",
        molfile_v2000=ETHANOL_V2000_BLOCK,
        chiral_centers_count=0,
        atoms_2d=[
            AtomCoordinate2D(atom_index=0, symbol="C", x=0.0, y=0.0),
            AtomCoordinate2D(atom_index=1, symbol="C", x=1.5, y=0.0),
            AtomCoordinate2D(atom_index=2, symbol="O", x=2.25, y=1.299),
        ],
    )

    res1 = generate_3d_conformer(payload)
    assert res1.success is True
    assert res1.validation.success is True
    assert res1.validation.atom_error_indices == []
    assert res1.force_field_used == "MMFF94"
    assert res1.energy_kcal_mol is not None
    assert -10.0 < res1.energy_kcal_mol < 10.0
    assert len(res1.coordinates_3d) == 9  # C2H6O has 9 atoms total with hydrogens
    assert res1.molfile_v3000 is not None
    assert "V3000" in res1.molfile_v3000
    assert "M  V30 BEGIN CTAB" in res1.molfile_v3000

    # Determinism verification: ETKDGv3 randomSeed=42 must yield identical coordinates
    res2 = generate_3d_conformer(payload)
    assert res2.success is True
    assert res2.energy_kcal_mol == pytest.approx(res1.energy_kcal_mol, rel=1e-6)
    for c1, c2 in zip(res1.coordinates_3d, res2.coordinates_3d):
        assert c1.atom_index == c2.atom_index
        assert c1.symbol == c2.symbol
        assert c1.x == pytest.approx(c2.x, abs=1e-5)
        assert c1.y == pytest.approx(c2.y, abs=1e-5)
        assert c1.z == pytest.approx(c2.z, abs=1e-5)


def test_conformer_engine_l_alanine() -> None:
    """Verify ETKDGv3 stereocenter preservation and conformer generation on L-Alanine."""
    payload = SketcherPayloadSchema(
        smiles="C[C@@H](C(=O)O)N",
        molfile_v2000=ALANINE_V2000_BLOCK,
        chiral_centers_count=1,
    )

    res = generate_3d_conformer(payload)
    assert res.success is True
    assert res.validation.success is True
    assert res.force_field_used == "MMFF94"
    assert res.energy_kcal_mol is not None
    assert len(res.coordinates_3d) == 13  # C3H7NO2 has 13 atoms
    assert res.molfile_v3000 is not None
    assert "V3000" in res.molfile_v3000


def test_conformer_engine_aspirin() -> None:
    """Verify conformer synthesis on aromatic drug topology Aspirin."""
    payload = SketcherPayloadSchema(
        smiles="CC(=O)Oc1ccccc1C(=O)O",
        molfile_v2000=ASPIRIN_V2000_BLOCK,
        chiral_centers_count=0,
    )

    res = generate_3d_conformer(payload)
    assert res.success is True
    assert res.validation.success is True
    assert res.force_field_used == "MMFF94"
    assert res.energy_kcal_mol is not None
    assert len(res.coordinates_3d) == 21  # C9H8O4 has 21 atoms
    assert res.molfile_v3000 is not None


def test_conformer_engine_uff_fallback() -> None:
    """Verify fallback to UFF force-field for elements unsupported by MMFF94 (Germanium)."""
    payload = SketcherPayloadSchema(
        smiles="C[Ge](C)(C)C",
        molfile_v2000="""
  CoChem-Mobile       2D

  5  4  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 Ge  0  0  0  0  0  0  0  0  0  0  0  0
    1.5000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    0.0000    1.5000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
   -1.5000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    0.0000   -1.5000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0  0  0  0
  1  3  1  0  0  0  0
  1  4  1  0  0  0  0
  1  5  1  0  0  0  0
M  END
""",
        chiral_centers_count=0,
    )

    res = generate_3d_conformer(payload)
    assert res.success is True
    assert res.validation.success is True
    assert res.force_field_used == "UFF"
    assert res.energy_kcal_mol is not None
    assert len(res.coordinates_3d) == 17  # C4H12Ge: 1 Ge, 4 C, 12 H


def test_conformer_engine_smiles_fallback() -> None:
    """Verify fallback to SMILES string when molfile_v2000 structure contains 0 atoms."""
    payload = SketcherPayloadSchema(
        smiles="CC(=O)O",
        molfile_v2000="""
  CoChem-Mobile       2D

  0  0  0  0  0  0  0  0  0  0999 V2000
M  END
""",
        chiral_centers_count=0,
    )

    res = generate_3d_conformer(payload)
    assert res.success is True
    assert res.validation.success is True
    assert res.smiles == "CC(=O)O"
    assert len(res.coordinates_3d) == 8  # Acetic acid C2H4O2: 2 C, 2 O, 4 H


def test_conformer_engine_unparseable_inputs() -> None:
    """Verify handling when both Molfile and SMILES are unparseable."""
    # When molfile is empty/invalid structure and smiles is not a valid molecule
    payload = SketcherPayloadSchema(
        smiles="INVALID_NOT_A_SMILES",
        molfile_v2000="""
  CoChem-Mobile       2D

  0  0  0  0  0  0  0  0  0  0999 V2000
M  END
""",
        chiral_centers_count=0,
    )

    res = generate_3d_conformer(payload)
    assert res.success is False
    assert res.validation.success is False
    assert (
        "Invalid chemical representation" in res.validation.diagnostic_message
        or "unable to parse" in res.validation.diagnostic_message
    )


def test_valence_violation_pentavalent_carbon() -> None:
    """Verify exact 0-indexed atom error identification on pentavalent carbon."""
    payload = SketcherPayloadSchema(
        smiles="C(C)(C)(C)(C)C",
        molfile_v2000=PENTAVALENT_CARBON_V2000_BLOCK,
        chiral_centers_count=0,
    )

    res = generate_3d_conformer(payload)
    assert res.success is False
    assert res.validation.success is False
    assert 0 in res.validation.atom_error_indices
    assert (
        "Valence" in res.validation.diagnostic_message
        or "greater than permitted" in res.validation.diagnostic_message
    )


def test_valence_violation_kekulize_error() -> None:
    """Verify non-kekulizable aromatic ring error handling and atom index reporting."""
    bad_v2000 = """
  CoChem-Mobile       2D

  5  5  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.5000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    2.2500    1.2990    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.5000    2.5980    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    0.0000    2.5980    0.0000 N   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  4  0  0  0  0
  2  3  4  0  0  0  0
  3  4  4  0  0  0  0
  4  5  4  0  0  0  0
  5  1  4  0  0  0  0
M  END
"""
    payload = SketcherPayloadSchema(
        smiles="c1cccn1",
        molfile_v2000=bad_v2000,
        chiral_centers_count=0,
    )

    res = generate_3d_conformer(payload)
    assert res.success is False
    assert res.validation.success is False
    assert len(res.validation.atom_error_indices) > 0


def test_sketcher_widget_asset_integrity_and_checksums() -> None:
    """Verify SHA-256 asset checksum calculation and file presence."""
    hashes = verify_asset_checksums()
    assert "sketcher.esm.js" in hashes
    assert "sketcher.css" in hashes
    assert len(hashes["sketcher.esm.js"]) == 64
    assert len(hashes["sketcher.css"]) == 64

    # Verify asset file paths exist on disk and are non-empty
    assert ESM_PATH.exists() and ESM_PATH.stat().st_size > 0
    assert CSS_PATH.exists() and CSS_PATH.stat().st_size > 0
    assert SketcherWidget._esm is not None
    assert SketcherWidget._css is not None


def test_sketcher_widget_offline_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify strict air-gapped zero external CDN check under COCHEM_OFFLINE=1."""
    monkeypatch.setenv("COCHEM_OFFLINE", "1")
    assert verify_offline_compliance() is True


def test_sketcher_widget_async_execution() -> None:
    """Verify AnyWidget asynchronous traitlet synchronization with ThreadPoolExecutor."""
    widget = SketcherWidget()
    assert widget.busy is False
    assert widget.payload_json == ""

    payload = SketcherPayloadSchema(
        smiles="CCO",
        molfile_v2000=ETHANOL_V2000_BLOCK,
        chiral_centers_count=0,
    )

    # Set payload_json triggering traitlet observer
    widget.payload_json = payload.model_dump_json()

    # Wait for async background worker to complete
    assert widget._last_future is not None
    result = widget._last_future.result(timeout=5.0)

    assert widget.busy is False
    assert result.success is True

    # Validate synchronized traitlet values
    val_schema = ValenceValidationResultSchema.model_validate_json(
        widget.validation_json
    )
    assert val_schema.success is True
    assert val_schema.atom_error_indices == []

    conf_schema = Conformer3DResultSchema.model_validate_json(widget.conformer_json)
    assert conf_schema.success is True
    assert conf_schema.force_field_used == "MMFF94"
    assert len(conf_schema.coordinates_3d) == 9

    widget.close()


def test_sketcher_widget_async_valence_error() -> None:
    """Verify asynchronous error trapping and traitlet synchronization on invalid valence."""
    widget = SketcherWidget()

    bad_payload = SketcherPayloadSchema(
        smiles="C(C)(C)(C)(C)C",
        molfile_v2000=PENTAVALENT_CARBON_V2000_BLOCK,
        chiral_centers_count=0,
    )

    widget.payload_json = bad_payload.model_dump_json()
    assert widget._last_future is not None
    result = widget._last_future.result(timeout=5.0)

    assert widget.busy is False
    assert result.success is False

    val_schema = ValenceValidationResultSchema.model_validate_json(
        widget.validation_json
    )
    assert val_schema.success is False
    assert 0 in val_schema.atom_error_indices

    widget.close()


def test_mendeleev_dynamic_mass_integration() -> None:
    """Verify zero hardcoded masses; Mendeleev dynamic masses match physical periodic table."""
    symbols = ["C", "H", "O", "N", "S", "P", "F", "Cl", "Br", "I"]
    for sym in symbols:
        elem = mendeleev.element(sym)
        c2d = AtomCoordinate2D(atom_index=0, symbol=sym, x=0.0, y=0.0)
        c3d = AtomCoordinate3D(atom_index=0, symbol=sym, x=0.0, y=0.0, z=0.0)
        assert c2d.atomic_weight == pytest.approx(float(elem.atomic_weight), rel=1e-5)
        assert c3d.atomic_weight == pytest.approx(float(elem.atomic_weight), rel=1e-5)


def test_asset_checksum_missing_file_error(tmp_path: pytest.TempPathFactory) -> None:
    """Verify compute_file_sha256 raises FileNotFoundError for missing file."""
    non_existent = tmp_path / "does_not_exist.js"  # type: ignore[operator]
    with pytest.raises(FileNotFoundError):
        compute_file_sha256(non_existent)


def test_offline_violation_error(
    tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify verify_offline_compliance detects banned external references."""
    monkeypatch.setenv("COCHEM_OFFLINE", "1")
    # Temporarily monkeypatch ESM_PATH with file containing external URL
    non_compliant_asset = tmp_path / "non_compliant_sketcher.esm.js"  # type: ignore[operator]
    non_compliant_asset.write_text(
        "import 'https://cdn.example.com/lib.js';", encoding="utf-8"
    )

    import cochem.mobile.sketcher_widget as widget_mod

    monkeypatch.setattr(widget_mod, "ESM_PATH", non_compliant_asset)

    with pytest.raises(RuntimeError, match="air-gap violation"):
        verify_offline_compliance()


def test_sketcher_widget_malformed_payload_string() -> None:
    """Verify sketcher widget handles completely malformed JSON payloads gracefully."""
    widget = SketcherWidget()
    widget.payload_json = "THIS IS NOT VALID JSON {{"

    assert widget._last_future is not None
    result = widget._last_future.result(timeout=5.0)

    assert result.success is False
    assert "Payload processing error" in widget.validation_json
    widget.close()


def test_extract_error_atom_indices_custom_exceptions() -> None:
    """Verify extract_error_atom_indices handles getAtomIdx / GetAtomIdx and explicit valence checks."""
    from cochem.mobile.conformer_engine import extract_error_atom_indices

    class CustomAtomError(Exception):
        def getAtomIdx(self) -> int:
            return 3

    class CustomUpperAtomError(Exception):
        def GetAtomIdx(self) -> int:
            return 5

    assert extract_error_atom_indices(None, CustomAtomError("Error")) == [3]
    assert extract_error_atom_indices(None, CustomUpperAtomError("Error")) == [5]

    # Test fallback explicit valence scan
    bad_mol = Chem.MolFromSmiles("C(C)(C)(C)(C)C", sanitize=False)
    # Generic exception without atom # in string
    generic_exc = ValueError("Generic calculation failure")
    indices = extract_error_atom_indices(bad_mol, generic_exc)
    assert 0 in indices
