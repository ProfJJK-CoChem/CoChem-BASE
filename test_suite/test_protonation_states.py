"""Comprehensive physical Zero-Mock test suite for cochem_base.io.protonation_states.

Validates:
- Strictly Unix LF line endings, standard UTF-8 encoding, and no BOM.
- Zero personal machine or local user path leakage.
- Backward compatibility and lazy resolution in cochem_base.io.
- Pydantic v2 data models (EuropePMCResult, EuropePMCResultList, EuropePMCResponse,
  ProtonationSpecies, AcidBaseEquilibrium, TitrationPoint).
- Monoprotic Henderson-Hasselbalch equations (deprotonation ratio, fraction protonated/deprotonated).
- Polyprotic equilibrium solvers (alpha fractions, average protonation number, net charge).
- Extreme pH boundary conditions (overflow/underflow resilience).
- Isoelectric point (pI) calculations for monoprotic/diprotic/polyprotic systems.
- Van Slyke differential buffer capacity (beta) and titration sweep simulation.
- Thermodynamic dissociation properties (Ka, Delta G° at standard state).
- Literature pKa heuristic text extraction (monoprotic and polyprotic).
- Authentic EuropePMC query schemas and network error handling.
- Species breakdown and pKa summary representations.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import cochem_base.io as io_pkg
from cochem_base.io.protonation_states import (
    LN_10,
    R_GAS_CONSTANT_KJ,
    STANDARD_TEMPERATURE_K,
    AcidBaseEquilibrium,
    EuropePMCResponse,
    EuropePMCResult,
    EuropePMCResultList,
    ProtonationSpecies,
    ProtonationStateAnalyzer,
    TitrationPoint,
    calculate_isoelectric_point,
    calculate_polyprotic_alpha,
    fraction_deprotonated,
    fraction_protonated,
    henderson_hasselbalch_ratio,
    parse_pka_text,
)
from cochem_base.path_sanitization import leak_patterns


@pytest.fixture
def protonation_states_file_path() -> Path:
    """Return absolute path to cochem_base/io/protonation_states.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_base" / "io" / "protonation_states.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


def test_file_encoding_and_lf_line_endings(protonation_states_file_path: Path) -> None:
    """Verify strictly Unix LF line endings (\n), standard UTF-8 encoding, and no BOM."""
    raw = protonation_states_file_path.read_bytes()
    assert b"\r\n" not in raw, "Found Windows CRLF (\r\n) line endings in protonation_states.py"
    assert b"\n" in raw, "Missing newline characters in protonation_states.py"
    assert not raw.startswith(b"\xef\xbb\xbf"), "Found UTF-8 BOM marker in protonation_states.py"



def test_zero_personal_path_leaks(protonation_states_file_path: Path) -> None:
    """Verify zero personal machine or local user path leakage in protonation_states.py."""
    lines = protonation_states_file_path.read_text(encoding="utf-8").splitlines()
    patterns = leak_patterns()
    leaks = []
    for lineno, line in enumerate(lines, 1):
        for pattern, placeholder in patterns:
            if pattern.search(line):
                leaks.append((lineno, placeholder, line.strip()))

    assert len(leaks) == 0, f"Detected personal path leaks in protonation_states.py: {leaks}"



def test_io_package_lazy_resolution() -> None:
    """Verify that cochem_base.io exports all expected symbols."""
    assert io_pkg.ProtonationStateAnalyzer is ProtonationStateAnalyzer
    assert io_pkg.EuropePMCResponse is EuropePMCResponse
    assert io_pkg.EuropePMCResult is EuropePMCResult
    assert io_pkg.EuropePMCResultList is EuropePMCResultList


def test_europe_pmc_pydantic_models() -> None:
    """Test Pydantic v2 models for EuropePMC response parsing."""
    raw_json = (
        '{"version": "6.8.0", "hitCount": 1, "resultList": {"result": ['
        '{"id": "12345", "source": "MED", "pmid": "12345", "doi": "10.1000/182", '
        '"title": "pKa determination of acetic acid", "abstractText": "The measured pKa is 4.76."}'
        ']}}'
    )
    resp = EuropePMCResponse.model_validate_json(raw_json)
    assert resp.hitCount == 1
    assert len(resp.resultList.result) == 1
    res = resp.resultList.result[0]
    assert res.pmid == "12345"
    assert res.abstractText == "The measured pKa is 4.76."
    assert res.title == "pKa determination of acetic acid"

    # Test empty defaults
    empty_resp = EuropePMCResponse()
    assert empty_resp.hitCount == 0
    assert len(empty_resp.resultList.result) == 0


def test_monoprotic_analyzer_initialization() -> None:
    """Test initialization and properties of monoprotic systems."""
    # Standard valid initialization
    analyzer = ProtonationStateAnalyzer(4.76, provenance="[E: NIST-AcOH]", name="Acetic Acid")
    assert analyzer.pka == 4.76
    assert analyzer.pka_values == (4.76,)
    assert analyzer.provenance == "[E: NIST-AcOH]"
    assert analyzer.name == "Acetic Acid"
    assert not analyzer.is_polyprotic
    assert analyzer.num_dissociation_steps == 1
    assert analyzer.num_species == 2
    assert analyzer.charge_fully_protonated == 0

    # Non-bracketed provenance fallback
    fallback_analyzer = ProtonationStateAnalyzer(3.5, provenance="Unbracketed Source")
    assert fallback_analyzer.provenance == "[MISSING DATA]"

    # Invalid initialization inputs
    with pytest.raises(ValueError, match="At least one pKa value must be provided"):
        ProtonationStateAnalyzer([])

    with pytest.raises(ValueError, match="Invalid pKa value"):
        ProtonationStateAnalyzer(float("nan"))

    with pytest.raises(ValueError, match="Invalid pKa value"):
        ProtonationStateAnalyzer(float("inf"))


def test_monoprotic_henderson_hasselbalch_exact_math() -> None:
    """Test mathematically exact Henderson-Hasselbalch calculations for acetic acid (pKa = 4.76)."""
    pka = 4.76
    analyzer = ProtonationStateAnalyzer(pka, provenance="[E]")

    # pH == pKa: [A-]/[HA] == 1.0, fraction protonated == 0.5
    assert math.isclose(analyzer.calculate_deprotonation_ratio(4.76), 1.0, rel_tol=1e-9)
    assert math.isclose(analyzer.calculate_fraction_protonated(4.76), 0.5, rel_tol=1e-9)
    assert math.isclose(analyzer.calculate_fraction_deprotonated(4.76), 0.5, rel_tol=1e-9)

    # pH == pKa + 1 (5.76): [A-]/[HA]== 10.0, fraction protonated == 1/11
    assert math.isclose(analyzer.calculate_deprotonation_ratio(5.76), 10.0, rel_tol=1e-9)
    assert math.isclose(analyzer.calculate_fraction_protonated(5.76), 1.0 / 11.0, rel_tol=1e-9)
    assert math.isclose(analyzer.calculate_fraction_deprotonated(5.76), 10.0 / 11.0, rel_tol=1e-9)

    # pH == pKa - 1 (3.76): [A-]/[HA]== 0.1, fraction protonated == 10/11
    assert math.isclose(analyzer.calculate_deprotonation_ratio(3.76), 0.1, rel_tol=1e-9)
    assert math.isclose(analyzer.calculate_fraction_protonated(3.76), 10.0 / 11.0, rel_tol=1e-9)
    assert math.isclose(analyzer.calculate_fraction_deprotonated(3.76), 1.0 / 11.0, rel_tol=1e-9)

    # Standalone functional solvers
    assert math.isclose(henderson_hasselbalch_ratio(4.76, 4.76), 1.0, rel_tol=1e-9)
    assert math.isclose(fraction_protonated(4.76, 4.76), 0.5, rel_tol=1e-9)
    assert math.isclose(fraction_deprotonated(4.76, 4.76), 0.5, rel_tol=1e-9)


def test_polyprotic_analyzer_initialization_and_sorting() -> None:
    """Test polyprotic system initialization with unsorted inputs (Phosphoric Acid)."""
    # Initialize with unsorted pKas
    analyzer = ProtonationStateAnalyzer(
        [12.38, 2.15, 7.20],
        provenance="[E: CRC-H3PO4]",
        charge_fully_protonated=0,
        name="Phosphoric Acid",
    )
    assert analyzer.pka == 2.15
    assert analyzer.pka_values == (2.15, 7.20, 12.38)
    assert analyzer.is_polyprotic
    assert analyzer.num_dissociation_steps == 3
    assert analyzer.num_species == 4
    assert len(analyzer) == 3
    assert analyzer[0] == 2.15
    assert analyzer[1] == 7.20
    assert analyzer[2] == 12.38
    assert list(iter(analyzer)) == [2.15, 7.20, 12.38]


def test_polyprotic_species_fractions_distribution() -> None:
    """Test mole fractions for phosphoric acid across the pH range."""
    analyzer = ProtonationStateAnalyzer([2.15, 7.20, 12.38], provenance="[E]")

    # Check at pH = 2.15: alpha_0 approx alpha_1 approx 0.5, alpha_2 approx 0, alpha_3 approx 0
    alphas_2_15 = analyzer.calculate_species_fractions(2.15)
    assert len(alphas_2_15) == 4
    assert math.isclose(sum(alphas_2_15), 1.0, abs_tol=1e-9)
    assert math.isclose(alphas_2_15[0], alphas_2_15[1], rel_tol=1e-2)
    assert alphas_2_15[2] < 1e-4
    assert alphas_2_15[3] < 1e-8

    # Check at pH = 7.20: alpha_1 approx alpha_2 approx 0.5
    alphas_7_20 = analyzer.calculate_species_fractions(7.20)
    assert math.isclose(sum(alphas_7_20), 1.0, abs_tol=1e-9)
    assert math.isclose(alphas_7_20[1], alphas_7_20[2], rel_tol=1e-2)

    # Check at pH = 12.38: alpha_2 approx alpha_3 approx 0.5
    alphas_12_38 = analyzer.calculate_species_fractions(12.38)
    assert math.isclose(sum(alphas_12_38), 1.0, abs_tol=1e-9)
    assert math.isclose(alphas_12_38[2], alphas_12_38[3], rel_tol=1e-2)

    # Extreme pH boundary safety: no overflow or NaN
    alphas_low = analyzer.calculate_species_fractions(-10.0)
    assert math.isclose(sum(alphas_low), 1.0, abs_tol=1e-9)
    assert math.isclose(alphas_low[0], 1.0, abs_tol=1e-6)

    alphas_high = analyzer.calculate_species_fractions(30.0)
    assert math.isclose(sum(alphas_high), 1.0, abs_tol=1e-9)
    assert math.isclose(alphas_high[3], 1.0, abs_tol=1e-6)


def test_average_protonation_and_net_charge() -> None:
    """Test average protonation number (n_bar) and net formal charge calculations."""
    # Phosphoric acid: H3PO4 (z0 = 0) -> H2PO4- -> HPO4(2-) -> PO4(3-)
    h3po4 = ProtonationStateAnalyzer([2.15, 7.20, 12.38], provenance="[E]", charge_fully_protonated=0)

    # Highly acidic pH = 0: H3PO4 dominant (n_bar approx 3, charge approx 0)
    assert math.isclose(h3po4.calculate_average_protonation_number(0.0), 3.0, abs_tol=0.01)
    assert math.isclose(h3po4.calculate_net_charge(0.0), 0.0, abs_tol=0.01)

    # pH = 7.20: equal mix of H2PO4- (charge -1) and HPO4(2-) (charge -2) => charge approx -1.5
    assert math.isclose(h3po4.calculate_average_protonation_number(7.20), 1.5, abs_tol=0.01)
    assert math.isclose(h3po4.calculate_net_charge(7.20), -1.5, abs_tol=0.01)

    # Highly basic pH = 14: PO4(3-) dominant (n_bar approx 0.02, charge approx -2.98)
    assert math.isclose(h3po4.calculate_average_protonation_number(14.0), 0.023, abs_tol=0.01)
    assert math.isclose(h3po4.calculate_net_charge(14.0), -2.977, abs_tol=0.01)


def test_isoelectric_point_calculation() -> None:
    """Test isoelectric point (pI) calculations for diprotic and polyprotic ampholytes."""
    # 1. GLYCINE (diprotic ampholyte, +H3N-CH2-COOH -> +H3N-CH2-COO- -> H2N-CH2-COO-)
    # pKa1 = 2.34, pKa2 = 9.60, z0 = +1
    glycine = ProtonationStateAnalyzer([2.34, 9.60], provenance="[E: NIST]", charge_fully_protonated=1)
    expected_pi_gly = (2.34 + 9.60) / 2.0  # 5.97
    assert math.isclose(glycine.calculate_isoelectric_point(), expected_pi_gly, abs_tol=1e-5)
    assert math.isclose(glycine.calculate_net_charge(expected_pi_gly), 0.0, abs_tol=1e-5)

    # 2. GLUTAMIC ACID (acidic amino acid, z0 = +1, pKa1 = 2.19, pKa2 = 4.25, pKa3 = 9.67)
    # pI is between the two carboxyl groups: (2.19 + 4.25) / 2 = 3.22
    glu = ProtonationStateAnalyzer([2.19, 4.25, 9.67], provenance="[E: NIST]", charge_fully_protonated=1)
    expected_pi_glu = (2.19 + 4.25) / 2.0
    calc_pi_glu = glu.calculate_isoelectric_point()
    assert math.isclose(calc_pi_glu, expected_pi_glu, abs_tol=1e-2)
    assert math.isclose(glu.calculate_net_charge(calc_pi_glu), 0.0, abs_tol=1e-5)


    # 3. Standalone solver
    assert math.isclose(calculate_isoelectric_point([2.34, 9.60], charge_fully_protonated=1), 5.97, abs_tol=1e-5)

    # 4. Error case when charge cannot cross zero (e.g. z0 = -1 with all acidic groups)
    with pytest.raises(ValueError, match="No isoelectric crossing found"):
        calculate_isoelectric_point([2.15, 7.20, 12.38], charge_fully_protonated=-1)



def test_buffer_capacity_and_titration_simulation() -> None:
    """Test Van Slyke buffer capacity calculations and titration sweeps."""
    # Monoprotic acetate buffer (pKa = 4.76, C_total = 0.1 M)
    acetate = ProtonationStateAnalyzer(4.76, provenance="[E]", name="Acetate")

    # Buffer capacity has maximum at pH == pKa
    beta_at_pka = acetate.calculate_buffer_capacity(4.76, c_total=0.1)
    beta_off_pka_1 = acetate.calculate_buffer_capacity(3.76, c_total=0.1)
    beta_off_pka_2 = acetate.calculate_buffer_capacity(5.76, c_total=0.1)

    assert beta_at_pka > beta_off_pka_1
    assert beta_at_pka > beta_off_pka_2

    # Negative concentration error
    with pytest.raises(ValueError, match="Total buffer concentration cannot be negative"):
        acetate.calculate_buffer_capacity(7.0, c_total=-0.01)

    # Titration simulation
    curve = acetate.simulate_titration(ph_min=2.0, ph_max=8.0, step=0.5, c_total=0.05)
    assert len(curve) == 13
    for pt in curve:
        assert isinstance(pt, TitrationPoint)
        assert 2.0 <= pt.ph <= 8.0
        assert math.isclose(sum(pt.species_fractions), 1.0, abs_tol=1e-9)
        assert pt.dominant_species_index in (0, 1)

    # Simulation invalid inputs
    with pytest.raises(ValueError, match="must be strictly less than"):
        acetate.simulate_titration(ph_min=10.0, ph_max=5.0)

    with pytest.raises(ValueError, match="must be strictly positive"):
        acetate.simulate_titration(ph_min=2.0, ph_max=8.0, step=-0.5)


def test_thermodynamic_properties_and_equilibria() -> None:
    """Test Ka and Delta G° calculations."""
    # Phosphoric acid: pKa = (2.15, 7.20, 12.38)
    analyzer = ProtonationStateAnalyzer([2.15, 7.20, 12.38], provenance="[E]")

    assert math.isclose(analyzer.dissociation_constant(1), 10**-2.15, rel_tol=1e-6)
    assert math.isclose(analyzer.dissociation_constant(2), 10**-7.20, rel_tol=1e-6)
    assert math.isclose(analyzer.dissociation_constant(3), 10**-12.38, rel_tol=1e-6)

    # Out of bounds step
    with pytest.raises(ValueError, match="Step 4 out of bounds"):
        analyzer.dissociation_constant(4)


    # Delta G  = 2.302585 * R * T * pKa
    dg1 = analyzer.standard_gibbs_free_energy(1, temperature_k=298.15)
    expected_dg1 = LN_10 * R_GAS_CONSTANT_KJ * 298.15 * 2.15
    assert math.isclose(dg1, expected_dg1, rel_tol=1e-6)

    # Check equilibria list
    eqs = analyzer.equilibria
    assert len(eqs) == 3
    assert isinstance(eqs[0], AcidBaseEquilibrium)
    assert eqs[0].step == 1
    assert eqs[0].pka == 2.15
    assert math.isclose(eqs[0].ka, 10**-2.15, rel_tol=1e-6)



def test_from_text_parser_heuristics() -> None:
    """Test literature regex heuristic parser across multiple patterns."""
    # Pattern: "pKa = 4.5"
    a1 = ProtonationStateAnalyzer.from_text_parser("The synthesized compound showed pKa = 4.5 in water.", source_id="PMID:1001")
    assert a1.pka == 4.5
    assert a1.provenance == "[D-UNVERIFIED: PMID:1001]"

    # Pattern: "pKa of 7.2"
    a2 = ProtonationStateAnalyzer.from_text_parser("Spectrophotometric titration revealed a pKa of 7.2 for the thiol group.", source_id="PMID:1002")
    assert a2.pka == 7.2

    # Pattern: "pKa: 3.8"
    a3 = ProtonationStateAnalyzer.from_text_parser("Thermodynamic parameters: pKa: 3.8 at 25 °C.", source_id="Paper-A")
    assert a3.pka == 3.8


    # Pattern: "pKa ~ 9.15" or "pKa is 9.15"
    a4 = ProtonationStateAnalyzer.from_text_parser("Calculated pKa is 9.15 under ionic strength 0.1 M.")
    assert a4.pka == 9.15

    # Negative pKa
    a5 = ProtonationStateAnalyzer.from_text_parser("Triflic acid has an extreme pKa = -14.7 in solution.")
    assert a5.pka == -14.7

    # Polyprotic text parsing
    poly_text = "Stepwise dissociation constants were found to be pKa1 = 2.15, pKa2 = 7.20, and pKa3 = 12.38."
    poly_analyzer = ProtonationStateAnalyzer.from_polyprotic_text(poly_text, source_id="PMID:2001")
    assert poly_analyzer.pka_values == (2.15, 7.20, 12.38)
    assert poly_analyzer.is_polyprotic


    # No match raises ValueError
    with pytest.raises(ValueError, match="Could not parse a valid pKa"):
        ProtonationStateAnalyzer.from_text_parser("This text has no acid dissociation constants.")

    with pytest.raises(ValueError, match="Could not parse any valid pKa"):
        ProtonationStateAnalyzer.from_polyprotic_text("No pKa values in this sentence.")


def test_species_breakdown_and_pka_summary() -> None:
    """Test species breakdown models and summary dictionaries."""
    diprotic = ProtonationStateAnalyzer([3.13, 4.76], provenance="[E: Test]", charge_fully_protonated=0, name="Dibasic Acid")
    breakdown = diprotic.get_species_breakdown(ph=4.0)
    assert len(breakdown) == 3
    for sp in breakdown:
        assert isinstance(sp, ProtonationSpecies)
        assert 0.0 <= sp.fraction <= 1.0


    summary = diprotic.pka_summary()
    assert summary["name"] == "Dibasic Acid"
    assert summary["is_polyprotic"] is True
    assert summary["pka_values"] == [3.13, 4.76]
    assert len(summary["equilibria"]) == 2


def test_equality_and_repr() -> None:
    """Test __repr__, __str__, and __eq__ dunder methods."""
    a1 = ProtonationStateAnalyzer(4.76, provenance="[E: NIST]", name="Acetic")
    a2 = ProtonationStateAnalyzer(4.76, provenance="[E: NIST]", name="Acetic")
    a3 = ProtonationStateAnalyzer(4.76, provenance="[E: Other]", name="Acetic")
    a4 = ProtonationStateAnalyzer([4.76, 9.25], provenance="[E: NIST]")

    assert a1 == a2
    assert a1 != a3
    assert a1 != a4
    assert a1 != "not an analyzer"

    assert "ProtonationStateAnalyzer(pka=4.7600" in repr(a1)
    assert "ProtonationStateAnalyzer(pka_values=(4.76, 9.25)" in repr(a4)
    assert str(a1) == repr(a1)


def test_query_europe_pmc_pka_error_handling() -> None:
    """Test error handling when EuropePMC network query fails or host is unreachable."""
    with pytest.raises(RuntimeError, match="EuropePMC API lookup failed"):
        ProtonationStateAnalyzer.query_europe_pmc_pka(
            "NonExistentChemicalX9999",
            timeout=0.001,
        )


def test_tetraprotic_edta_system() -> None:
    """Test complex tetraprotic acid equilibrium (EDTA: pKa = 2.00, 2.67, 6.16, 10.26)."""
    edta = ProtonationStateAnalyzer(
        [2.00, 2.67, 6.16, 10.26],
        provenance="[E: CRC]",
        charge_fully_protonated=0,
        name="EDTA",
    )
    assert edta.num_dissociation_steps == 4
    assert edta.num_species == 5

    # At pH = 1.0, H4Y is dominant (index 0)
    assert edta.dominant_species_index(1.0) == 0

    # At pH = 4.5, H2Y(2-) is dominant (index 2)
    assert edta.dominant_species_index(4.5) == 2

    # At pH = 12.0, Y(4-) is dominant (index 4)
    assert edta.dominant_species_index(12.0) == 4
    assert math.isclose(edta.calculate_net_charge(12.0), -3.98, abs_tol=0.05)


def test_conjugate_acid_bases() -> None:
    """Test basic species modeled via conjugate acid pKa (Ammonium, Pyridine)."""
    # Ammonium NH4+ -> NH3 + H+, pKa = 9.25, z0 = +1
    nh4 = ProtonationStateAnalyzer(9.25, provenance="[E: NIST]", charge_fully_protonated=1, name="Ammonium")
    assert math.isclose(nh4.calculate_net_charge(7.0), 0.994, abs_tol=0.01)
    assert math.isclose(nh4.calculate_net_charge(9.25), 0.50, abs_tol=0.01)
    assert math.isclose(nh4.calculate_net_charge(12.0), 0.002, abs_tol=0.01)

    # Pyridinium PyH+ -> Py + H+, pKa = 5.25, z0 = +1
    pyr = ProtonationStateAnalyzer(5.25, provenance="[E: NIST]", charge_fully_protonated=1, name="Pyridinium")
    assert math.isclose(pyr.calculate_fraction_protonated(5.25), 0.5, abs_tol=1e-6)
    assert math.isclose(pyr.calculate_fraction_deprotonated(5.25), 0.5, abs_tol=1e-6)


def test_custom_species_labels() -> None:
    """Test get_species_breakdown with custom user-supplied labels."""
    analyzer = ProtonationStateAnalyzer([2.15, 7.20], provenance="[E]", name="Diprotic")
    custom_labels = ["H2-System", "H-System(-1)", "De-System(-2)"]
    breakdown = analyzer.get_species_breakdown(ph=5.0, labels=custom_labels)
    assert len(breakdown) == 3
    assert breakdown[0].label == "H2-System"
    assert breakdown[1].label == "H-System(-1)"
    assert breakdown[2].label == "De-System(-2)"


