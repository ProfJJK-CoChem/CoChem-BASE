"""
Unit Verification Across IUPAC Periodic Table (Z=1..118) for CoChem Physical Nuclide Resolver.
Task 1.2.4: Unit Verification Across IUPAC Periodic Table Z=1..118
Target Module: src/cochem_base/physics/nuclide_resolver.py
Council Governance: Council Emergency Session 012 (COCHEM-COUNCIL-RES-012-8D-ZERO-TRUST)

Authoritative real-world physical unit test suite verifying zero-mock periodic table traversal,
AME2020/CIAAW standard terrestrial atomic weights, transuranic/synthetic element fallbacks,
superheavy boundary limits (Oganesson Z=118), fail-closed negative boundary trapping,
and multi-threaded concurrent query resilience.
"""
from __future__ import annotations

import concurrent.futures
import math
import sys
from pathlib import Path

import mendeleev
import pytest

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from cochem_base.physics.nuclide_resolver import (
    InvalidNuclideSymbolError,
    IsotopeNotFoundError,
    NuclideResolutionError,
    disambiguate_mass,
    parse_nuclide,
    resolve_covalent_radius,
)


# ============================================================================
# Task 1.2.4.1: IUPAC Periodic Table Traversal (Z=1 to Z=118)
# ============================================================================

def test_iupac_periodic_table_traversal_z_1_to_118() -> None:
    """Iterate through all 118 IUPAC elements (Z=1 to Z=118) and assert positive finite mass and covalent radius."""
    for z in range(1, 119):
        element_obj = mendeleev.element(z)
        symbol = element_obj.symbol

        natural = [iso for iso in element_obj.isotopes if iso.abundance and iso.mass]
        if natural:
            mass = disambiguate_mass(symbol)
            assert mass == max(natural, key=lambda iso: (iso.abundance, -iso.mass_number)).mass
        else:
            with pytest.raises(NuclideResolutionError, match="explicit isotope"):
                disambiguate_mass(symbol)
            measured = next(iso for iso in element_obj.isotopes if iso.mass is not None and iso.mass > 0)
            mass = disambiguate_mass(str(measured.mass_number) + symbol)
            assert mass == measured.mass
        assert math.isfinite(mass) and mass > 0.0, (
            f"Atomic mass for Z={z} ({symbol}) must be positive and finite, got {mass}."
        )

        r_cov = resolve_covalent_radius(symbol)
        assert r_cov is not None and r_cov > 0.0, (
            f"Covalent radius for Z={z} ({symbol}) must be positive and non-null, got {r_cov}."
        )


# ============================================================================
# Task 1.2.4.2: Standard Terrestrial Atomic Weight Parity
# ============================================================================

def test_principal_exact_mass_parity_stable_elements() -> None:
    """Physical defaults equal independently queried most-abundant measured isotopes."""
    for symbol in ("H", "C", "N", "O", "S", "Fe", "Au", "Pb"):
        principal = max((iso for iso in mendeleev.element(symbol).isotopes if iso.abundance and iso.mass),
                        key=lambda iso: (iso.abundance, -iso.mass_number))
        assert disambiguate_mass(symbol) == principal.mass


# ============================================================================
# Task 1.2.4.3: Synthetic & Transuranic Fallbacks
# ============================================================================

def test_synthetic_elements_require_explicit_measured_isotopes() -> None:
    for symbol in ("Tc", "Pm", "Po", "At", "Og"):
        with pytest.raises(NuclideResolutionError, match="explicit isotope"):
            disambiguate_mass(symbol)
        measured = next(iso for iso in mendeleev.element(symbol).isotopes if iso.mass is not None and iso.mass > 0)
        assert disambiguate_mass(str(measured.mass_number) + symbol) == measured.mass


# ============================================================================
# Task 1.2.4.4: Superheavy Oganesson Boundary
# ============================================================================

def test_superheavy_oganesson_boundary() -> None:
    """Assert terminal periodic table element Oganesson (Og, Z=118) resolves mass 294.0 +/- 1.0 u and positive radius."""
    og_isotope = next(iso for iso in mendeleev.element("Og").isotopes if iso.mass_number == 294)
    og_mass = disambiguate_mass("294Og")
    assert og_mass == og_isotope.mass
    assert abs(og_mass - 294.0) <= 1.0, (
        f"Oganesson mass {og_mass} deviates from expected 294.0 +/- 1.0 u."
    )

    r_cov_og = resolve_covalent_radius("Og")
    assert r_cov_og is not None and r_cov_og > 0.0, (
        f"Oganesson covalent radius must be positive, got {r_cov_og}."
    )


# ============================================================================
# Task 1.2.4.5: Negative Boundary & Typo Exception Trapping Suite
# ============================================================================

def test_negative_boundary_and_typo_exceptions() -> None:
    """Assert fail-closed typed exceptions on malformed symbols and out-of-bounds mass numbers."""
    invalid_nuclide_tokens = ["Xx", "Food", "123", "C12-13", "", "   "]
    for token in invalid_nuclide_tokens:
        with pytest.raises(InvalidNuclideSymbolError):
            disambiguate_mass(token)
        with pytest.raises(InvalidNuclideSymbolError):
            parse_nuclide(token)

    # Assert IsotopeNotFoundError raised on out-of-bounds mass numbers
    for token in ["50H", "999C"]:
        with pytest.raises(IsotopeNotFoundError):
            disambiguate_mass(token)

    # 0H tests non-physical zero mass number boundary
    with pytest.raises((IsotopeNotFoundError, InvalidNuclideSymbolError)):
        disambiguate_mass("0H")


# ============================================================================
# Task 1.2.4.6: Concurrent Multi-Threaded Query Resilience
# ============================================================================

def test_concurrency_periodic_table_queries() -> None:
    """Run concurrent queries across worker threads using concurrent.futures.ThreadPoolExecutor and assert zero errors."""
    symbols = []
    for z in range(1, 119):
        data = mendeleev.element(z)
        natural = [iso for iso in data.isotopes if iso.abundance and iso.mass]
        isotope = next(iso for iso in data.isotopes if iso.mass is not None and iso.mass > 0)
        symbols.append(data.symbol if natural else str(isotope.mass_number) + data.symbol)
    query_batch = symbols * 8

    def _query_element(symbol: str) -> tuple[float, float | None]:
        mass = disambiguate_mass(symbol)
        radius = resolve_covalent_radius(symbol)
        return mass, radius

    query_errors: list[Exception] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        future_to_sym = {executor.submit(_query_element, s): s for s in query_batch}
        for future in concurrent.futures.as_completed(future_to_sym):
            try:
                m, r = future.result()
                assert math.isfinite(m) and m > 0.0
                assert r is not None and r > 0.0
            except Exception as exc:
                query_errors.append(exc)

    assert len(query_errors) == 0, (
        f"Concurrent periodic table queries failed with {len(query_errors)} errors: {query_errors}"
    )
