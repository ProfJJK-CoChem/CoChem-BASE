"""Catalog integrity, BibTeX syntax, and DOI format validation for provenance/citations.py."""
from __future__ import annotations

import re

from cochem_base.provenance.citations import (
    _ALIAS_MAP,
    _AUTHORITATIVE_BIBTEX_CATALOG,
    CitationTracker,
    extract_bibtex_keys,
    lookup_bibtex,
    normalize_engine_key,
    parse_and_validate_bibtex,
)

# Canonical CrossRef / ISO 26324 DOI prefix + suffix regex (e.g. 10.1021/acs.jpca.9b03157)
DOI_FORMAT_RE = re.compile(r"^10\.\d{4,9}/[^\s\"<>]+$")

# 21 expanded catalog entries with CrossRef-verified DOIs (None where canonical book chapter has no DOI)
EXPECTED_EXPANDED_ENTRIES: dict[str, str | None] = {
    "revdsd_pbep86_d4": "10.1021/acs.jpca.9b03157",
    "multiwfn": "10.1002/jcc.22885",
    "igmh": "10.1002/jcc.26812",
    "qtaim": "10.1021/cr00005a013",
    "nbo7": "10.1002/jcc.25873",
    "dlpno_led": "10.1021/acs.jctc.6b00523",
    "helgaker_cbs": "10.1016/S0009-2614(98)00111-0",
    "boys_bernardi_cp": "10.1080/00268977000101561",
    "surf_cp_ftmw": "10.1063/5.0311736",
    "kraitchman": "10.1119/1.1933338",
    "costain": "10.1063/1.1744602",
    "watson_reduction": None,
    "colbert_miller_dvr": "10.1063/1.462100",
    "neb_ts": "10.1021/acs.jctc.1c00462",
    "grimme_qrrho": "10.1002/chem.201200497",
    "smd": "10.1021/jp810292n",
    "giao": "10.1021/ja00179a005",
    "dp4_plus": "10.1021/acs.joc.5b02396",
    "steom_dlpno_ccsd": "10.1021/acs.jctc.9b00559",
    "nto": "10.1063/1.1558471",
    "orca_esd": "10.1063/1.5010895",
}


def test_every_catalog_entry_has_valid_bibtex_and_unique_key() -> None:
    """Every entry in _AUTHORITATIVE_BIBTEX_CATALOG must parse cleanly with balanced braces and a unique key."""
    seen_keys: dict[str, str] = {}
    for engine_id, entry in _AUTHORITATIVE_BIBTEX_CATALOG.items():
        assert entry.engine_id == engine_id
        assert entry.name.strip()
        assert entry.category.strip()
        assert entry.description.strip()
        assert parse_and_validate_bibtex(entry.bibtex), f"Invalid BibTeX syntax for {engine_id!r}"

        keys = extract_bibtex_keys(entry.bibtex)
        assert len(keys) == 1, f"Expected exactly 1 BibTeX key for {engine_id!r}, got {keys}"
        key_lower = keys[0].lower()
        assert key_lower not in seen_keys, (
            f"Duplicate BibTeX key {keys[0]!r} shared by {seen_keys[key_lower]!r} and {engine_id!r}"
        )
        seen_keys[key_lower] = engine_id


def test_every_catalog_doi_matches_iso_format_and_bibtex_field() -> None:
    """Every non-None DOI in the catalog must match valid DOI syntax and appear verbatim in the entry's BibTeX."""
    for engine_id, entry in _AUTHORITATIVE_BIBTEX_CATALOG.items():
        if entry.doi is None:
            # Entries without a DOI must still provide a URL or ISBN (e.g., NeurIPS proceedings, 1977 book chapter)
            assert entry.url or "isbn" in entry.bibtex.lower(), (
                f"Catalog entry {engine_id!r} without DOI must provide url or isbn"
            )
            continue

        assert DOI_FORMAT_RE.match(entry.doi), f"Malformed DOI {entry.doi!r} on {engine_id!r}"
        doi_match = re.search(r"doi\s*=\s*\{([^}]+)\}", entry.bibtex)
        assert doi_match is not None, f"Missing doi = {{...}} field in BibTeX for {engine_id!r}"
        assert doi_match.group(1) == entry.doi, (
            f"DOI mismatch on {engine_id!r}: field={entry.doi!r} vs bibtex={doi_match.group(1)!r}"
        )


def test_all_21_expanded_entries_present_with_verified_dois() -> None:
    """Confirm all 21 expanded scientific citations are registered with their verified DOIs."""
    for engine_id, expected_doi in EXPECTED_EXPANDED_ENTRIES.items():
        assert engine_id in _AUTHORITATIVE_BIBTEX_CATALOG, f"Missing expanded citation {engine_id!r}"
        entry = _AUTHORITATIVE_BIBTEX_CATALOG[engine_id]
        assert entry.doi == expected_doi, (
            f"Unexpected DOI for {engine_id!r}: got {entry.doi!r}, expected {expected_doi!r}"
        )
        assert lookup_bibtex(engine_id) == entry.bibtex

    # Verify Watson 1977 book chapter metadata explicitly
    watson = _AUTHORITATIVE_BIBTEX_CATALOG["watson_reduction"]
    assert "1977" in watson.bibtex
    assert "978-0-444-41588-2" in watson.bibtex
    assert "Durig" in watson.bibtex


def test_alias_map_points_exclusively_to_valid_catalog_entries() -> None:
    """Every alias in _ALIAS_MAP must resolve to an existing canonical entry in _AUTHORITATIVE_BIBTEX_CATALOG."""
    for alias, target in _ALIAS_MAP.items():
        assert target in _AUTHORITATIVE_BIBTEX_CATALOG, f"Alias {alias!r} points to missing target {target!r}"
        assert normalize_engine_key(alias) == target


def test_track_from_method_string_covers_expanded_methods() -> None:
    """Verify track_from_method_string detects every newly added method and spectroscopy workflow."""
    cases = [
        ("revDSD-PBEP86-D4/def2-QZVPP", {"revdsd_pbep86_d4", "dft_d4"}),
        ("Multiwfn IGMH and QTAIM topology analysis", {"multiwfn", "igmh", "qtaim"}),
        ("NBO 7.0 donor-acceptor analysis", {"nbo7"}),
        ("DLPNO-LED/cc-pVTZ interaction decomposition", {"dlpno_led", "orca"}),
        ("Helgaker CBS(T,Q) extrapolation with Boys-Bernardi counterpoise", {"helgaker_cbs", "boys_bernardi_cp"}),
        ("SURF CP-FTMW rotational spectrum with Kraitchman Costain Watson reduction", {"surf_cp_ftmw", "kraitchman", "costain", "watson_reduction"}),
        ("Colbert-Miller Sinc-DVR 1D anharmonic potential", {"colbert_miller_dvr"}),
        ("NEB-TS with Grimme qRRHO and SMD(water)", {"neb_ts", "orca", "grimme_qrrho", "smd"}),
        ("GIAO NMR shifts with DP4+ stereochemical probability", {"giao", "dp4_plus"}),
        ("STEOM-DLPNO-CCSD with NTO and ORCA ESD fluorescence", {"steom_dlpno_ccsd", "nto", "orca_esd", "orca"}),
    ]
    for method_str, expected_subset in cases:
        tracker = CitationTracker()
        detected = set(tracker.track_from_method_string(method_str))
        missing = expected_subset - detected
        assert not missing, f"Method string {method_str!r} missed expected citations {missing}; got {detected}"
