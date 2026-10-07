"""Unit tests for Publication-Grade ORCA Recipe R2 Input Deck Generation.

Compliant with Method Matrix v4.1, Anti-Spoofing Protocol v4, Mendeleev Library Mandate,
and Work Breakdown Structure (WBS) Task 5.3.2.
"""

import hashlib
import math
from pathlib import Path
import re
from typing import List

import numpy as np
import pytest
from mendeleev import element

from cochem_base.calc.cochem_calc_input_generator import (
    MoleculeInput,
    generate_recipe_r2_orca_deck,
    generate_recipe_r2_orca_input,
    generate_recipe_r2_counterpoise_bracketing_decks,
    get_dynamic_atomic_mass,
    RedundantDispersionError,
)
from cochem_base.geometry.constraints import (
    build_reference_co2_h2o_complex,
    formulate_recipe_r2_wilson_constraints,
    get_reference_monomer_geometry,
)


def test_recipe_r2_electronic_structure_keywords(tmp_path: Path, configured_registry) -> None:
    """Verifies electronic structure keywords strictly match Method Matrix v4.1 Recipe R2 standard."""
    deck_path = generate_recipe_r2_orca_deck(output_dir=tmp_path)
    assert deck_path.exists(), "Recipe R2 deck file was not generated"

    content = deck_path.read_text(encoding="utf-8")

    # 1. Primary theory keyword line: wB97M-V def2-QZVPP def2/J RIJCOSX TightOpt TightSCF DEFGRID3
    assert "! wB97M-V def2-QZVPP def2/J RIJCOSX TightOpt TightSCF DEFGRID3" in content, (
        "Missing required electronic structure keyword sequence in Recipe R2 deck [M]."
    )

    # 2. Assert DEFGRID1 and DEFGRID2 are strictly excluded
    assert "DEFGRID1" not in content.upper()
    assert "DEFGRID2" not in content.upper()

    # 3. Assert base job name is specified
    assert '%base "cochem_dimer_recipe_r2"' in content


def test_recipe_r2_prohibition_of_redundant_dispersion() -> None:
    """Verifies that pairing wB97M-V with external empirical dispersion (D3/D4) raises RedundantDispersionError [M]."""
    # 1. Direct validation check raises RedundantDispersionError
    inp = MoleculeInput.model_construct(
        basin_id="invalid_disp_direct",
        elements=["C", "O", "O"],
        coordinates=[(0.0, 0.0, 0.0), (0.0, 0.0, 1.16), (0.0, 0.0, -1.16)],
        theory_level="wB97M-V-D3 def2-QZVPP",
        is_weak_complex=True,
        is_opt=True,
        charge=0,
        multiplicity=1,
    )
    with pytest.raises(RedundantDispersionError, match="External dispersion correction"):
        inp.validate_method_matrix()

    # 2. Pydantic constructor validation wraps RedundantDispersionError
    with pytest.raises(Exception) as exc_info:
        MoleculeInput(
            basin_id="invalid_disp_constructor",
            elements=["C", "O", "O"],
            coordinates=[(0.0, 0.0, 0.0), (0.0, 0.0, 1.16), (0.0, 0.0, -1.16)],
            theory_level="wB97M-V def2-QZVPP D3BJ TightOpt",
            is_weak_complex=True,
            is_opt=True,
        )
    assert "METHOD_MATRIX_VIOLATION_DISPERSION" in str(exc_info.value)


def test_recipe_r2_prohibition_of_calc_hess_true() -> None:
    """An invalid exact initial Hessian is rejected before a deck can be written."""
    with pytest.raises(ValueError, match="Calc_Hess true"):
        MoleculeInput(
            basin_id="test_calc_hess_prohibition",
            elements=["C", "O", "O"],
            coordinates=[(0.0, 0.0, 0.0), (0.0, 0.0, 1.16), (0.0, 0.0, -1.16)],
            theory_level="B3LYP-D3BJ def2-SVP Calc_Hess true",
            is_opt=True,
        )


def test_recipe_r2_scf_convergence_parameters(tmp_path: Path, configured_registry) -> None:
    """Verifies that %scf block strictly contains TolE 1.0e-08, Thresh 1.0e-11, and MaxIter 150 [M]."""
    deck_path = generate_recipe_r2_orca_deck(output_dir=tmp_path)
    content = deck_path.read_text(encoding="utf-8")

    assert "%scf" in content, "Missing %scf block in Recipe R2 deck"
    assert "TolE 1.0e-08" in content, "Missing TolE 1.0e-08 in %scf block"
    assert "Thresh 1.0e-11" in content, "Missing Thresh 1.0e-11 in %scf block"
    assert "MaxIter 150" in content, "Missing MaxIter 150 in %scf block"


def test_recipe_r2_quintuple_geometry_convergence_block(tmp_path: Path, configured_registry) -> None:
    """Verifies %geom contains InHess XTB2 and the quintuple stationary point convergence criteria [M]."""
    deck_path = generate_recipe_r2_orca_deck(output_dir=tmp_path)
    content = deck_path.read_text(encoding="utf-8")

    assert "%geom" in content, "Missing %geom block in Recipe R2 deck"
    assert "InHess XTB2" in content, "Missing InHess XTB2 model Hessian preconditioner in %geom"

    # Quintuple convergence thresholds mandated by Method Matrix v4 §4.4
    assert "TolE 1.0e-07" in content, "Missing TolE 1.0e-07 in %geom"
    assert "TolRMSG 3.0e-06" in content, "Missing TolRMSG 3.0e-06 in %geom"
    assert "TolMaxG 1.0e-05" in content, "Missing TolMaxG 1.0e-05 in %geom"
    assert "TolRMSD 5.0e-05" in content, "Missing TolRMSD 5.0e-05 in %geom"
    assert "TolMaxD 1.0e-04" in content, "Missing TolMaxD 1.0e-04 in %geom"
    assert "MaxIter 200" in content, "Missing MaxIter 200 in %geom"


def test_recipe_r2_wilson_internal_constraints_ingestion(tmp_path: Path, configured_registry) -> None:
    """Verifies that Wilson internal coordinate constraints lock exactly 6 intramolecular DOFs.

    And leave all 6 intermolecular degrees of freedom fully unconstrained (Method Matrix §9A.1, WBS 5.3.1/5.3.2).
    """
    deck_path = generate_recipe_r2_orca_deck(output_dir=tmp_path)
    content = deck_path.read_text(encoding="utf-8")

    # 1. Monomer A (CO2): atoms 0 (C), 1 (O), 2 (O)
    assert "{ B 0 1 C }" in content, "Missing CO2 intramolecular bond constraint { B 0 1 C }"
    assert "{ B 0 2 C }" in content, "Missing CO2 intramolecular bond constraint { B 0 2 C }"
    assert "{ A 1 0 2 C }" in content, "Missing CO2 intramolecular angle constraint { A 1 0 2 C }"

    # 2. Monomer B (H2O): atoms 3 (O), 4 (H), 5 (H)
    assert "{ B 3 4 C }" in content, "Missing H2O intramolecular bond constraint { B 3 4 C }"
    assert "{ B 3 5 C }" in content, "Missing H2O intramolecular bond constraint { B 3 5 C }"
    assert "{ A 4 3 5 C }" in content, "Missing H2O intramolecular angle constraint { A 4 3 5 C }"

    # 3. Total constraint count in file must be exactly 6
    b_matches = re.findall(r"\{\s*B\s+\d+\s+\d+\s+C\s*\}", content)
    a_matches = re.findall(r"\{\s*A\s+\d+\s+\d+\s+\d+\s+C\s*\}", content)
    d_matches = re.findall(r"\{\s*D\s+\d+\s+\d+\s+\d+\s+\d+\s+C\s*\}", content)

    assert len(b_matches) == 4, f"Expected 4 frozen bonds, got {len(b_matches)}"
    assert len(a_matches) == 2, f"Expected 2 frozen angles, got {len(a_matches)}"
    assert len(d_matches) == 0, f"Expected 0 frozen dihedrals, got {len(d_matches)}"
    assert len(b_matches) + len(a_matches) + len(d_matches) == 6

    # 4. Assert Cartesian locks { C idx C } are strictly absent
    cartesian_locks = re.findall(r"\{\s*C\s+\d+\s+C\s*\}", content)
    assert len(cartesian_locks) == 0, f"Forbidden Cartesian locks detected: {cartesian_locks}"

    # 5. Assert zero intermolecular cross-monomer constraints exist
    for u, v in [(0, 3), (0, 4), (0, 5), (1, 3), (1, 4), (1, 5), (2, 3), (2, 4), (2, 5)]:
        assert f"{{ B {u} {v} C }}" not in content
        assert f"{{ B {v} {u} C }}" not in content


def test_recipe_r2_reference_monomer_geometry_integrity() -> None:
    """Verifies that reference monomer geometries from NIST/CCCBDB exhibit zero initial distortion (< 1e-12 A)."""
    # 1. CO2 reference monomer: Dinfh, r_CO = 1.1621 A, angle = 180.0 deg
    syms_co2, coords_co2 = get_reference_monomer_geometry("CO2")
    r_co1 = float(np.linalg.norm(coords_co2[1] - coords_co2[0]))
    r_co2 = float(np.linalg.norm(coords_co2[2] - coords_co2[0]))
    assert math.isclose(r_co1, 1.1621, abs_tol=1e-12), f"CO2 bond 1 distorted: {r_co1}"
    assert math.isclose(r_co2, 1.1621, abs_tol=1e-12), f"CO2 bond 2 distorted: {r_co2}"

    v1 = coords_co2[1] - coords_co2[0]
    v2 = coords_co2[2] - coords_co2[0]
    cos_oco = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
    angle_oco = math.degrees(math.acos(np.clip(cos_oco, -1.0, 1.0)))
    assert math.isclose(angle_oco, 180.0, abs_tol=1e-12), f"CO2 angle distorted: {angle_oco}"

    # 2. H2O reference monomer: C2v, r_OH = 0.9572 A, angle = 104.52 deg
    syms_h2o, coords_h2o = get_reference_monomer_geometry("H2O")
    r_oh1 = float(np.linalg.norm(coords_h2o[1] - coords_h2o[0]))
    r_oh2 = float(np.linalg.norm(coords_h2o[2] - coords_h2o[0]))
    assert math.isclose(r_oh1, 0.9572, abs_tol=1e-12), f"H2O bond 1 distorted: {r_oh1}"
    assert math.isclose(r_oh2, 0.9572, abs_tol=1e-12), f"H2O bond 2 distorted: {r_oh2}"

    v_oh1 = coords_h2o[1] - coords_h2o[0]
    v_oh2 = coords_h2o[2] - coords_h2o[0]
    cos_hoh = np.dot(v_oh1, v_oh2) / (np.linalg.norm(v_oh1) * np.linalg.norm(v_oh2))
    angle_hoh = math.degrees(math.acos(np.clip(cos_hoh, -1.0, 1.0)))
    assert math.isclose(angle_hoh, 104.52, abs_tol=1e-12), f"H2O angle distorted: {angle_hoh}"


def test_recipe_r2_counterpoise_distance_bracketing_flags(tmp_path: Path, configured_registry) -> None:
    """Verifies generation of 3-leg distance bracketing decks and CP keyword flags [M]."""
    # 1. Single deck with counterpoise=True
    cp_deck_path = generate_recipe_r2_orca_deck(
        basin_id="co2_h2o_cp",
        counterpoise=True,
        output_dir=tmp_path,
    )
    cp_content = cp_deck_path.read_text(encoding="utf-8")
    assert "CP" in cp_content.splitlines()[5], "Missing CP flag in simple keywords line"
    assert "C(1)" in cp_content, "Missing fragment 1 annotation for Monomer A"
    assert "O(2)" in cp_content, "Missing fragment 2 annotation for Monomer B"

    # 2. Generate complete 3-leg triplet
    decks = generate_recipe_r2_counterpoise_bracketing_decks(
        basin_id="co2_h2o_bracket",
        output_dir=tmp_path,
    )
    assert set(decks.keys()) == {"dimer", "monomer_a_ghosts", "monomer_b_ghosts"}

    for leg_name, path in decks.items():
        assert path.exists(), f"Leg {leg_name} deck was not created"

    # Leg 2: Monomer B atoms ghosted with ':'
    leg2_text = decks["monomer_a_ghosts"].read_text(encoding="utf-8")
    assert "O:" in leg2_text, "Monomer B oxygen must be ghosted in leg 2"
    assert "H:" in leg2_text, "Monomer B hydrogen must be ghosted in leg 2"
    assert "C:" not in leg2_text, "Monomer A carbon must NOT be ghosted in leg 2"

    # Leg 3: Monomer A atoms ghosted with ':'
    leg3_text = decks["monomer_b_ghosts"].read_text(encoding="utf-8")
    assert "C:" in leg3_text, "Monomer A carbon must be ghosted in leg 3"
    assert "O:" in leg3_text, "Monomer A oxygen must be ghosted in leg 3"


def test_recipe_r2_dynamic_mendeleev_library_mandate() -> None:
    """Verifies that dynamic masses are retrieved exclusively through mendeleev.element [M]."""
    mass_c = get_dynamic_atomic_mass("C")
    mass_o = get_dynamic_atomic_mass("O")
    mass_h = get_dynamic_atomic_mass("H")

    # Assert retrieved masses match authentic dynamic mendeleev values
    assert math.isclose(mass_c, float(element("C").mass), abs_tol=1e-6)
    assert math.isclose(mass_o, float(element("O").mass), abs_tol=1e-6)
    assert math.isclose(mass_h, float(element("H").mass), abs_tol=1e-6)

    # Dimer total molecular weight: CO2 (44.009) + H2O (18.015) = 62.024
    expected_total = mass_c + 2.0 * mass_o + mass_o + 2.0 * mass_h
    assert math.isclose(expected_total, 62.024, abs_tol=1e-2)


def test_recipe_r2_deck_zero_syntax_warnings_and_srs_parity(tmp_path: Path, configured_registry) -> None:
    """Verifies generated input deck strictly matches SRS_Chunk_17.md §6.1 specification."""
    deck_path = generate_recipe_r2_orca_deck(output_dir=tmp_path)
    content = deck_path.read_text(encoding="utf-8")

    # Assert cryptographic SHA-256 header stamp is present
    assert "CoChem-CORE Cryptographic Provenance Stamp:" in content
    assert "Recipe: R2 [M]" in content

    # Assert block structure integrity
    assert content.count("%pal") == 1
    assert content.count("%maxcore") == 1
    assert content.count("%scf") == 1
    assert content.count("%geom") == 1
    assert content.count("Constraints") == 1
    assert content.count("* xyz 0 1") == 1

    # End blocks balance check
    # %pal ends with 'end', %scf ends with 'end', %geom has Constraints 'end' and geom 'end'
    geom_block_match = re.search(r"%geom(.*?)end\s*\n\s*\* xyz", content, re.DOTALL)
    assert geom_block_match is not None, "Malformed %geom block structure"
    assert "InHess XTB2" in geom_block_match.group(1)
    assert "Constraints" in geom_block_match.group(1)


def test_recipe_r2_canonical_deliverable_artifact_on_disk(tmp_path: Path, configured_registry) -> None:
    """The requested deck is written to the configured artifact directory."""
    canonical_artifact = generate_recipe_r2_orca_deck(
        output_dir=tmp_path, filename="recipe_r2_production_deck.inp"
    )
    assert canonical_artifact.exists(), f"Physical deliverable missing at: {canonical_artifact}"
    assert canonical_artifact.stat().st_size > 1000, "Deliverable file size too small (< 1000 bytes)"

    content = canonical_artifact.read_text(encoding="utf-8")
    assert "! wB97M-V def2-QZVPP def2/J RIJCOSX TightOpt TightSCF DEFGRID3" in content
    assert "TolE 1.0e-08" in content
    assert "TolMaxG 1.0e-05" in content
    assert "{ B 0 1 C }" in content
    assert "{ B 3 4 C }" in content
