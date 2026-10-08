"""Real Mendeleev lookup, typed label, ghost and archival provenance contracts."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import json
from pathlib import Path

import numpy as np
import pytest
from mendeleev import element

from cochem_base.geometry.nuclide_geometry import (
    HISTORICAL_AVERAGE_MASS_CONVENTION, PRINCIPAL_MASS_CONVENTION,
    resolve_nuclear_identity, validate_nuclear_identity_metadata,
)
from cochem_base.physics.isotopes import (
    NormalizedNuclide, ZeroMassSystemError, clear_mass_cache,
    get_atomic_mass, get_isotope_mass, get_mass_cache_telemetry, get_nuclide_mass,
    is_ghost_atom, normalize_nuclide_symbol, warmup_mass_cache,
)
from cochem_base.physics.nuclide_resolver import InvalidNuclideSymbolError


@pytest.mark.parametrize("label", ["13C", "13-C", "13_C", "C13", "C-13", "C_13"])
def test_normalization_preserves_the_real_isotope_across_all_documented_spellings(label):
    assert normalize_nuclide_symbol(label) == NormalizedNuclide("C", 13, False)
    isotope = next(isotope for isotope in element("C").isotopes if isotope.mass_number == 13)
    assert get_nuclide_mass(label) == isotope.mass
    assert resolve_nuclear_identity([label]).mass_numbers == (13,)


@pytest.mark.parametrize("label,parent", [("Gh_C", "C"), ("Gh-O", "O"), ("Bq_H", "H"),
    ("X_N", "N"), ("C_Gh", "C"), ("Ghost-C", "C"), ("O-Bq", "O")])
def test_ghost_basis_parent_is_retained_but_contributes_no_mass(label, parent):
    assert is_ghost_atom(label)
    assert normalize_nuclide_symbol(label) == NormalizedNuclide("Gh_" + parent, None, True)
    assert np.float64(get_nuclide_mass(label)).tobytes() == np.float64(0.0).tobytes()
    qualified = resolve_nuclear_identity(["C", label], allow_ghosts=True)
    assert qualified.nuclides == ("C", "Gh_" + parent)
    assert qualified.mass_numbers == (None, None)
    assert qualified.masses_u[1] == 0.0
    with pytest.raises(ValueError, match="counterpoise"):
        resolve_nuclear_identity(["C", label])


def test_all_ghost_systems_and_unknown_or_contradictory_isotopes_fail_closed():
    with pytest.raises(ZeroMassSystemError):
        resolve_nuclear_identity(["Gh_C", "Bq", "X_N"], allow_ghosts=True)
    assert not is_ghost_atom("Xe")
    assert get_nuclide_mass("Xe") > 0
    for label in ("@C", "0C", "123", "13C12", "-C", "Gh_Invalid"):
        with pytest.raises(InvalidNuclideSymbolError):
            normalize_nuclide_symbol(label)
    for label, number in (("C999", None), ("C", 999), ("13C", 12), ("Gh_O", 16)):
        with pytest.raises(ValueError):
            get_isotope_mass(label, number)
    with pytest.raises(ValueError, match="explicit isotope"):
        get_nuclide_mass("Tc")


def test_principal_defaults_agree_with_dynamic_database_and_do_not_invent_assignments():
    labels = ["C", "Cl", "O", "H", "D", "13-C"]
    identity = resolve_nuclear_identity(labels)
    assert identity.mass_numbers == (None, None, None, None, 2, 13)
    assert identity.metadata["mass_convention"] == PRINCIPAL_MASS_CONVENTION
    for label, measured in zip(labels[:4], identity.masses_u[:4]):
        principal = max((isotope for isotope in element(label).isotopes if isotope.abundance and isotope.mass),
                        key=lambda isotope: (isotope.abundance, -isotope.mass_number))
        assert measured == principal.mass
    assert get_atomic_mass("C") == element("C").atomic_weight
    assert identity.masses_u[0] != get_atomic_mass("C")


def test_historical_average_metadata_is_validated_without_relabeling():
    # Mass provenance contract only: no calculated energy or convergence is invented.
    labels = ["C", "H", "13C"]
    current = resolve_nuclear_identity(labels).metadata
    historical = dict(current, mass_convention=HISTORICAL_AVERAGE_MASS_CONVENTION,
                      masses_u=[get_atomic_mass(label) for label in labels])
    original = json.dumps(historical, sort_keys=True)
    assert validate_nuclear_identity_metadata(labels, historical, allow_historical=True) == historical
    assert json.dumps(historical, sort_keys=True) == original
    with pytest.raises(ValueError):
        validate_nuclear_identity_metadata(labels, historical)
    mislabeled = dict(historical, mass_convention=PRINCIPAL_MASS_CONVENTION)
    with pytest.raises(ValueError):
        validate_nuclear_identity_metadata(labels, mislabeled, allow_historical=True)


def test_real_warmed_cache_records_observed_timing_and_is_consistent_across_16_threads(tmp_path):
    clear_mass_cache()
    assert get_mass_cache_telemetry().avg_latency_ns is None
    evidence = warmup_mass_cache()
    assert evidence["cache_maxsize"] == 4096
    assert evidence["measured_isotope_count"] > 0
    assert evidence["cached_query_median_ns"] > 0
    labels = ["C", "13C", "D", "18O", "Cl", "Gh_O"] * 100
    expected = [get_nuclide_mass(label) for label in labels]
    with ThreadPoolExecutor(max_workers=16) as executor:
        actual = list(executor.map(get_nuclide_mass, labels))
    assert actual == expected
    telemetry = get_mass_cache_telemetry()
    assert telemetry.hit_count > 0 and telemetry.miss_count > 0
    assert 0 < telemetry.hit_ratio <= 1
    assert telemetry.avg_latency_ns > 0
    Path(tmp_path / "measured-mass-cache.json").write_text(
        json.dumps({"warmup": evidence, "telemetry": asdict(telemetry)}, indent=2) + "\n", encoding="utf-8",
    )
    assert evidence["cached_query_median_ns"] < 500
