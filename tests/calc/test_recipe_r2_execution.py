"""R2 input contracts and exact counterpoise algebra without simulated engines."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from cochem_base.calc.recipe_r2_execution import (
    R2ReferenceError,
    R2ReferenceManifest,
    ReferenceArtifact,
    build_r2_leg_deck,
    counterpoise_bracket,
    execute_recipe_r2,
    load_r2_references,
    parse_reference_geometry_state,
    read_dimer_gradient,
)


def _deck_contract() -> R2ReferenceManifest:
    """Metadata used solely to exercise serialization, never execution evidence."""
    artifact = {"path": "external-reference-required", "sha256": "0" * 64}
    return R2ReferenceManifest.model_validate(
        {
            "schema_version": "cochem.r2-reference/1",
            "monomers": [
                {
                    "atom_indices": group,
                    "charge": 0,
                    "multiplicity": 1,
                    "method": "CCSD(T)/CBS",
                    "basis_cardinal_pair": [3, 4],
                    "basis_family": "cc-pVXZ",
                    "source_uri": "urn:cochem:serialization-input",
                    "geometry": artifact,
                    "lower_cardinal_output": artifact,
                    "upper_cardinal_output": artifact,
                }
                for group in ([0, 1], [2, 3])
            ],
        }
    )


SYMBOLS = ["H", "H", "H", "H"]
COORDINATES = np.asarray([[0, 0, 0], [0, 0, 0.74], [0, 0, 3], [0, 0, 3.74]])


def test_five_leg_decks_freeze_only_dimer_internal_dofs_and_preserve_ghost_states():
    contracts = _deck_contract()
    decks = {
        leg: build_r2_leg_deck(
            leg, SYMBOLS, COORDINATES, contracts, charge=0, multiplicity=1, cores=1, maxcore_mb=256
        )
        for leg in ["dimer", "monomer_a", "monomer_b", "ghost_a", "ghost_b"]
    }
    dimer = decks["dimer"][0]
    assert dimer.count("%geom") == 1
    assert "{ B 0 1 C }" in dimer and "{ B 2 3 C }" in dimer
    assert "{ B 1 2 C }" not in dimer
    assert "InHess XTB2" in dimer and "Calc_Hess" not in dimer
    for leg, (deck, _, _, _) in decks.items():
        assert "wB97M-V def2-QZVPP def2/J RIJCOSX TightSCF DEFGRID3" in deck
        assert "D3BJ" not in deck and "D4" not in deck
        if leg != "dimer":
            assert "%geom" not in deck and "TightOpt" not in deck
    assert decks["monomer_a"][1] == ["H", "H"]
    assert decks["ghost_a"][1] == ["H", "H", "H:", "H:"]
    assert decks["ghost_b"][1] == ["H:", "H:", "H", "H"]
    assert np.array_equal(decks["ghost_a"][2], COORDINATES)


def test_counterpoise_algebra_requires_all_five_values_and_orders_bracket():
    # Arithmetic inputs establish the definition, not claimed engine measurements.
    energies = {
        "dimer": -2.3,
        "monomer_a": -1.0,
        "monomer_b": -1.0,
        "ghost_a": -1.01,
        "ghost_b": -1.02,
    }
    result = counterpoise_bracket(energies)
    assert result["uncorrected_interaction_hartree"] == pytest.approx(-0.3)
    assert result["counterpoise_interaction_hartree"] == pytest.approx(-0.27)
    assert result["bsse_correction_hartree"] == pytest.approx(0.03)
    with pytest.raises(ValueError, match="five"):
        counterpoise_bracket({"dimer": -2.3})
    with pytest.raises(ValueError, match="BSSE"):
        counterpoise_bracket({**energies, "ghost_a": -0.8})
    with pytest.raises(ValueError, match="finite"):
        counterpoise_bracket({**energies, "ghost_a": float("nan")})


def test_reference_contract_rejects_wrong_level_cardinals_and_overlapping_atoms():
    data = _deck_contract().model_dump(mode="json")
    data["monomers"][0]["basis_cardinal_pair"] = [2, 3]
    with pytest.raises(ValidationError, match="cardinal"):
        R2ReferenceManifest.model_validate(data)
    data = _deck_contract().model_dump(mode="json")
    data["monomers"][0]["method"] = "r2SCAN-3c"
    with pytest.raises(ValidationError):
        R2ReferenceManifest.model_validate(data)
    data = _deck_contract().model_dump(mode="json")
    data["monomers"][1]["atom_indices"] = [1, 2]
    with pytest.raises(ValidationError, match="disjoint"):
        R2ReferenceManifest.model_validate(data)


def test_reference_files_are_required_and_digest_tampering_fails(tmp_path):
    source = tmp_path / "reference.xyz"
    source.write_text("2\nphysical geometry input\nH 0 0 0\nH 0 0 0.74\n")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    item = ReferenceArtifact(path=Path("reference.xyz"), sha256=digest)
    assert item.verify(tmp_path) == source
    source.write_text(source.read_text().replace("0.74", "0.75"))
    with pytest.raises(R2ReferenceError, match="digest"):
        item.verify(tmp_path)
    manifest = tmp_path / "references.json"
    manifest.write_text(_deck_contract().model_dump_json())
    with pytest.raises(FileNotFoundError):
        load_r2_references(manifest, SYMBOLS, COORDINATES, charge=0, multiplicity=1)


def test_missing_reference_fails_before_creating_a_production_workdir(tmp_path):
    work = tmp_path / "run"
    with pytest.raises(FileNotFoundError):
        execute_recipe_r2(SYMBOLS, COORDINATES, tmp_path / "absent.json", work_dir=work)
    assert not work.exists()
    with pytest.raises(ValueError, match="frequency"):
        execute_recipe_r2(
            SYMBOLS, COORDINATES, tmp_path / "absent.json", work_dir=work, is_freq=True
        )


def test_incomplete_or_unmatched_gradient_checkpoint_cannot_certify_residuals(tmp_path):
    path = tmp_path / "calculation.engrad"
    path.write_text("# incomplete physical artifact\n4\n-2.3\n")
    with pytest.raises(ValueError, match="incomplete"):
        read_dimer_gradient(path, SYMBOLS, COORDINATES)


@pytest.mark.skipif(
    not os.environ.get("COCHEM_R2_REFERENCE_MANIFEST"),
    reason="Actual ORCA and supplied validated CCSD(T)/CBS reference artifacts are required",
)
def test_actual_recipe_r2_orca_five_leg_acceptance(tmp_path):
    reference_path = Path(os.environ["COCHEM_R2_REFERENCE_MANIFEST"])
    geometry_path = Path(os.environ["COCHEM_R2_DIMER_XYZ"])
    from cochem_base.calc.calculation_service import parse_run_geometry

    symbols, coordinates = parse_run_geometry(geometry_path.read_text())
    result = execute_recipe_r2(
        symbols,
        coordinates,
        reference_path,
        work_dir=tmp_path / "physical-r2",
        registry_path=os.environ.get("COCHEM_CONFIG"),
        cores=1,
    )
    assert set(result["legs"]) == {"dimer", "monomer_a", "monomer_b", "ghost_a", "ghost_b"}
    assert result["frozen_monomer_integrity"]["maximum_internal_drift_angstrom"] < 1e-6
    assert (
        result["counterpoise"]["bracket_lower_hartree"]
        <= result["counterpoise"]["bracket_upper_hartree"]
    )
    assert not result["residual_gradient_warning"]


def test_method_label_and_checksum_alone_cannot_certify_benchmark_output(tmp_path):
    from cochem_base.calc.recipe_r2_execution import validate_reference_output

    declaration = tmp_path / "method-declaration.json"
    declaration.write_text(json.dumps({"method": "CCSD(T)/CBS", "basis": "cc-pVTZ"}))
    with pytest.raises(R2ReferenceError, match="Unsupported or incomplete"):
        validate_reference_output(declaration, "cc-pVTZ")


def test_reference_coordinate_parser_preserves_identity_and_requires_electronic_state():
    # A grammar example, with no completion/energy markers and no benchmark claim.
    text = """Total Charge       Charge        .... 0
Multiplicity       Mult          .... 1
CARTESIAN COORDINATES (ANGSTROEM)
---------------------------------
H  0.000000  0.000000  0.000000
H  0.000000  0.000000  0.740000

"""
    result = parse_reference_geometry_state(text)
    assert result == {
        "elements": ["H", "H"],
        "coordinates_angstrom": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.74]],
        "charge": 0,
        "multiplicity": 1,
    }
    with pytest.raises(R2ReferenceError, match="Multiplicity"):
        parse_reference_geometry_state(text.replace("Multiplicity", "UndeclaredSpin"))
    with pytest.raises(R2ReferenceError, match="incompatible"):
        parse_reference_geometry_state(text.replace("Mult          .... 1", "Mult          .... 2"))
    with pytest.raises(R2ReferenceError, match="contradicts"):
        parse_reference_geometry_state(text + "Total Charge       Charge        .... 1\n")


def test_reference_coordinate_parser_rejects_absent_or_nonfinite_geometry():
    state_only = "Total Charge .... 0\nMultiplicity .... 1\n"
    with pytest.raises(R2ReferenceError, match="coordinates"):
        parse_reference_geometry_state(state_only)
    with pytest.raises(R2ReferenceError, match="Nonfinite"):
        parse_reference_geometry_state(
            state_only + "CARTESIAN COORDINATES (ANGSTROEM)\nHe nan 0 0\n"
        )
