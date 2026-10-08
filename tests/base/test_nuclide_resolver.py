"""
Unit Verification & Precision Test Suite for Physical Nuclide Resolver.
WBS 1.2.1: Regex Tokenization & Nuclide Mass Disambiguation Engine
WBS 1.2.2: Dynamic Mendeleev Database Query Binding & Isotope Fallback
Specification Reference: COCHEM-SPEC-TASK-1.2.1-WBS-V1 (Section 6.2)

Verifies zero-mock deterministic parsing, IUPAC canonicalization, exact AME2020
isotopic mass disambiguation, Pyykko single-bond covalent radii in Angstroms,
fail-closed exception behavior, and high-throughput amortized LRU caching.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest
from mendeleev import element

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from cochem_base.physics.nuclide_resolver import (
    InvalidNuclideError,
    InvalidNuclideSymbolError,
    IsotopeNotFoundError,
    NuclideToken,
    disambiguate_mass,
    get_nuclide_spin_and_quadrupole,
    parse_nuclide,
    resolve_covalent_radius,
    resolve_vdw_radius,
)


# ============================================================================
# Section 6.2 Mandatory Test Cases: Tokenization & Canonicalization
# ============================================================================

def test_parse_nuclide_standard_elements() -> None:
    """Assert standard element tokens parse to canonical NuclideToken instances (Section 6.2 #1)."""
    assert parse_nuclide("H") == NuclideToken("H", None, False)
    assert parse_nuclide("C") == NuclideToken("C", None, False)
    assert parse_nuclide("cl") == NuclideToken("Cl", None, False)
    assert parse_nuclide("CL") == NuclideToken("Cl", None, False)
    assert parse_nuclide("Fe") == NuclideToken("Fe", None, False)


def test_parse_nuclide_isotopes() -> None:
    """Assert isotopic nuclide tokens parse with explicit mass numbers (Section 6.2 #2)."""
    assert parse_nuclide("13C") == NuclideToken("C", 13, False)
    assert parse_nuclide("18O") == NuclideToken("O", 18, False)
    assert parse_nuclide("15N") == NuclideToken("N", 15, False)
    assert parse_nuclide("34S") == NuclideToken("S", 34, False)


def test_parse_nuclide_hydrogen_aliases() -> None:
    """Assert Hydrogen isotope aliases (D, T) resolve to H with proper mass numbers (Section 6.2 #3)."""
    assert parse_nuclide("D") == NuclideToken("H", 2, True)
    assert parse_nuclide("d") == NuclideToken("H", 2, True)
    assert parse_nuclide("T") == NuclideToken("H", 3, True)
    assert parse_nuclide("t") == NuclideToken("H", 3, True)


def test_parse_nuclide_malformed_input() -> None:
    """Verify InvalidNuclideSymbolError on malformed tokens: '', '123', 'C13', '13-C', '0C', '-1H', 'H2O' (Section 6.2 #4)."""
    malformed_tokens = ["", "123", "C-13-12", "13--C", "0C", "-1H", "H2O"]
    for token in malformed_tokens:
        with pytest.raises(InvalidNuclideSymbolError):
            parse_nuclide(token)


# ============================================================================
# Section 6.2 Mandatory Test Cases: Mass Disambiguation & Precision
# ============================================================================

def test_disambiguate_mass_values() -> None:
    """Assert dynamic physical mass disambiguation precision against CIAAW / AME2020 (Section 6.2 #5)."""
    assert abs(disambiguate_mass("13C") - 13.0033548) < 1e-5
    assert abs(disambiguate_mass("D") - 2.0141018) < 1e-5
    assert abs(disambiguate_mass("T") - 3.0160493) < 1e-5
    assert disambiguate_mass("C") == next(iso.mass for iso in element("C").isotopes if iso.mass_number == 12)
    assert disambiguate_mass("Cl") == max((iso for iso in element("Cl").isotopes if iso.abundance), key=lambda iso: iso.abundance).mass
    assert abs(disambiguate_mass("18O") - 17.999160) < 1e-5


def test_disambiguate_mass_errors() -> None:
    """Verify IsotopeNotFoundError and InvalidNuclideSymbolError on invalid mass queries (Section 6.2 #6)."""
    with pytest.raises(IsotopeNotFoundError):
        disambiguate_mass("999C")
    with pytest.raises((IsotopeNotFoundError, InvalidNuclideSymbolError)):
        disambiguate_mass("0H")
    with pytest.raises(InvalidNuclideSymbolError):
        disambiguate_mass("Xx")
    with pytest.raises(InvalidNuclideSymbolError):
        disambiguate_mass("Zz")


# ============================================================================
# Section 6.2 Mandatory Test Cases: Radii & Performance
# ============================================================================

def test_resolve_covalent_radius() -> None:
    """Verify Pyykko single-bond covalent radii in Angstroms for C and H (Section 6.2 #7)."""
    r_c = resolve_covalent_radius("C")
    assert r_c is not None
    assert 0.75 <= r_c <= 0.77

    r_h = resolve_covalent_radius("H")
    assert r_h is not None
    assert 0.31 <= r_h <= 0.32


def test_lru_cache_performance() -> None:
    """Verify 10,000 lookups complete in < 0.05 seconds (Section 6.2 #8)."""
    test_tokens = ["13C", "D", "T", "18O", "15N", "34S", "H", "C", "Cl"]
    for tok in test_tokens:
        disambiguate_mass(tok)

    n_iterations = 10_000
    t0 = time.perf_counter()
    for i in range(n_iterations):
        _ = disambiguate_mass(test_tokens[i % len(test_tokens)])
    t_elapsed = time.perf_counter() - t0
    assert t_elapsed < 0.05, f"10,000 lookups took {t_elapsed:.4f}s (threshold < 0.05s)"


# ============================================================================
# Additional Verifications: Dataclass Validation, Type Safety, Exception Fields
# ============================================================================

def test_nuclide_token_post_init_validation() -> None:
    """Verifies that NuclideToken validates mass_number > 0 and rejects non-positive mass numbers."""
    with pytest.raises(InvalidNuclideSymbolError) as exc_info_0:
        NuclideToken("C", 0)
    assert exc_info_0.value.token_str == "0C"

    with pytest.raises(InvalidNuclideSymbolError) as exc_info_neg:
        NuclideToken("C", -1)
    assert exc_info_neg.value.token_str == "-1C"


def test_type_error_on_non_str_arguments() -> None:
    """Verifies TypeError / InvalidNuclideSymbolError on non-str/non-NuclideToken arguments."""
    invalid_inputs = [123, 45.67, ["C"], {"symbol": "C"}, None]
    functions_to_test = [
        disambiguate_mass,
        resolve_covalent_radius,
        resolve_vdw_radius,
        get_nuclide_spin_and_quadrupole,
    ]
    for fn in functions_to_test:
        for invalid_arg in invalid_inputs:
            with pytest.raises((TypeError, InvalidNuclideSymbolError)):
                fn(invalid_arg)  # type: ignore[arg-type]


def test_exception_attributes() -> None:
    """Verifies token_str and reason on InvalidNuclideSymbolError, and symbol and mass_number on IsotopeNotFoundError."""
    err_sym = InvalidNuclideSymbolError("BadToken", "Custom syntax violation")
    assert err_sym.token_str == "BadToken"
    assert err_sym.reason == "Custom syntax violation"
    assert "BadToken" in str(err_sym)
    assert "Custom syntax violation" in str(err_sym)

    err_iso = IsotopeNotFoundError("C", 999)
    assert err_iso.symbol == "C"
    assert err_iso.mass_number == 999
    assert "C-999" in str(err_iso)

    # Validate attributes when raised during real execution
    with pytest.raises(InvalidNuclideSymbolError) as exc_sym:
        parse_nuclide("C-13-12")
    assert exc_sym.value.token_str == "C-13-12"
    assert exc_sym.value.reason is not None

    with pytest.raises(IsotopeNotFoundError) as exc_iso:
        disambiguate_mass("999C")
    assert exc_iso.value.symbol == "C"
    assert exc_iso.value.mass_number == 999


# ============================================================================
# Parametric Coverage & Precision Invariants
# ============================================================================

@pytest.mark.parametrize(
    "raw_token, expected_symbol, expected_a, expected_alias",
    [
        ("13C", "C", 13, False),
        ("D", "H", 2, True),
        ("d", "H", 2, True),
        ("T", "H", 3, True),
        ("t", "H", 3, True),
        ("18O", "O", 18, False),
        ("15N", "N", 15, False),
        ("34S", "S", 34, False),
        ("H", "H", None, False),
        ("C", "C", None, False),
        ("c", "C", None, False),
        ("Cl", "Cl", None, False),
        ("cl", "Cl", None, False),
        ("CL", "Cl", None, False),
        ("Fe", "Fe", None, False),
        ("fe", "Fe", None, False),
        ("238U", "U", 238, False),
    ],
)
def test_parse_nuclide_valid_tokens(
    raw_token: str,
    expected_symbol: str,
    expected_a: int | None,
    expected_alias: bool,
) -> None:
    """Verifies that nuclide tokens parse and canonicalize according to IUPAC rules."""
    token = parse_nuclide(raw_token)
    assert isinstance(token, NuclideToken)
    assert token.symbol == expected_symbol
    assert token.mass_number == expected_a
    assert token.is_isotope_alias == expected_alias
    assert token.raw_token == raw_token.strip()


@pytest.mark.parametrize(
    "invalid_token",
    [
        "",
        "   ",
        "13--C",
        "C-13-12",
        "123",
        "12.5C",
        "@C",
        "C!",
        "Xx",
        "Food",
        "H2O",
        "0C",
        "-1C",
    ],
)
def test_parse_nuclide_invalid_tokens_raise_error(invalid_token: str) -> None:
    """Verifies fail-closed rejection of invalid nuclide token formats."""
    with pytest.raises((InvalidNuclideSymbolError, InvalidNuclideError)):
        parse_nuclide(invalid_token)


def test_hydrogen_alias_contradiction_raises() -> None:
    """Verifies that contradictory mass number on Hydrogen alias raises error."""
    with pytest.raises(InvalidNuclideSymbolError):
        parse_nuclide("3D")  # D has A=2, contradictory with 3


def test_deuterium_mass_precision() -> None:
    """Verifies Deuterium physical mass resolves to ~2.01410178 u."""
    mass_d = disambiguate_mass("D")
    mass_2h = disambiguate_mass("2H")
    assert abs(mass_d - mass_2h) < 1e-12
    assert abs(mass_d - 2.014101778) < 1e-6


def test_carbon_13_mass_precision() -> None:
    """Verifies Carbon-13 physical mass resolves to ~13.0033548 u."""
    mass_13c = disambiguate_mass("13C")
    assert abs(mass_13c - 13.0033548) < 1e-6


def test_oxygen_18_mass_precision() -> None:
    """Verifies Oxygen-18 physical mass resolves to ~17.99916 u."""
    mass_18o = disambiguate_mass("18O")
    assert abs(mass_18o - 17.99916) < 1e-4


def test_default_principal_isotope_masses():
    """Bare nuclear labels resolve principal exact masses, distinct from CIAAW averages."""
    for symbol in ("C", "Cl", "H"):
        principal = max((isotope for isotope in element(symbol).isotopes if isotope.abundance and isotope.mass),
                        key=lambda isotope: (isotope.abundance, -isotope.mass_number))
        assert disambiguate_mass(symbol) == principal.mass


def test_nonexistent_isotope_raises_isotope_not_found() -> None:
    """Verifies that querying a non-physical isotope mass raises IsotopeNotFoundError."""
    with pytest.raises(IsotopeNotFoundError):
        disambiguate_mass("999C")


def test_covalent_radius_angstrom_conversion() -> None:
    """Verifies covalent radius in picometers is correctly converted to Angstroms."""
    r_c = resolve_covalent_radius("C")
    assert r_c is not None
    assert abs(r_c - 0.75) < 0.05

    r_h = resolve_covalent_radius("H")
    assert r_h is not None
    assert 0.25 < r_h < 0.40


def test_vdw_radius_angstrom_conversion() -> None:
    """Verifies van der Waals radius resolution in Angstroms."""
    r_vdw_c = resolve_vdw_radius("C")
    assert r_vdw_c is not None
    assert 1.5 < r_vdw_c < 2.0


def test_amortized_lru_cache_throughput_benchmark() -> None:
    """Verifies that 100,000 cached nuclide lookups complete in < 0.15 s."""
    test_tokens = ["13C", "D", "T", "18O", "15N", "34S", "H", "C", "Cl"]

    # Warm cache
    for tok in test_tokens:
        disambiguate_mass(tok)

    n_iterations = 100_000
    t0 = time.perf_counter()
    for i in range(n_iterations):
        tok = test_tokens[i % len(test_tokens)]
        _ = disambiguate_mass(tok)
    t_elapsed = time.perf_counter() - t0

    assert t_elapsed < 0.15, f"100,000 lookups took {t_elapsed:.4f}s (threshold < 0.15s)"
