"""Zero-Mock Unit and Integration Tests for Automated Citations Generator.

Validates:
- Strict Zero-Mock compliance (all tests run on physical disks using tmp_path).
- Authentic, validated BibTeX catalog records for all CoChem-BASE supported engines.
- Syntax validation of BibTeX records (balanced braces, mandatory fields: author, title, year).
- Engine registration and alias normalization.
- Intelligent Method Matrix method string decomposition and tracking.
- Deduplication of citations.
- Physical generation and formatting of cochem_citations.bib files.
- Markdown publication summary generation.
- Custom citation registration and syntax validation.
- Process-wide global CitationTracker singleton operations.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from cochem_base.provenance.citations import (
    CitationTracker,
    EngineCitation,
    clear_tracked_citations,
    deduplicate_bibtex_entries,
    extract_bibtex_keys,
    generate_bibtex_string,
    get_bibtex_catalog,
    get_global_citation_tracker,
    lookup_bibtex,
    normalize_engine_key,
    parse_and_validate_bibtex,
    track_engine,
    track_engines,
    track_method,
    write_citations_bib,
)


@pytest.fixture(autouse=True)
def reset_global_tracker() -> Iterator[None]:
    """Fixture that resets the global CitationTracker before each test."""
    clear_tracked_citations()
    yield
    clear_tracked_citations()


def test_authoritative_catalog_integrity() -> None:
    """Verifies that all catalog citations have valid BibTeX syntax and non-empty metadata."""
    catalog = get_bibtex_catalog()
    assert len(catalog) >= 18, f"Expected at least 18 engine citations, found {len(catalog)}"

    # Crucial quantum chemistry and spectroscopic engines
    critical_engines = [
        "orca",
        "cfour",
        "crest",
        "xtb",
        "gfn2_xtb",
        "pyscf",
        "gpu4pyscf",
        "psi4",
        "molpro",
        "mace",
        "mace_off23",
        "aimnet2",
        "abcluster",
        "r2scan_3c",
        "b97_3c",
        "wb97m_v",
        "dlpno_ccsd_t",
        "dft_d3",
        "dft_d4",
        "sapt",
        "spcat",
        "qcxms",
        "ase",
        "parsl",
        "rdkit",
    ]

    for eng in critical_engines:
        bibtex = lookup_bibtex(eng)
        assert bibtex is not None, f"Engine '{eng}' must be present in authoritative catalog"
        assert parse_and_validate_bibtex(bibtex), f"BibTeX syntax for '{eng}' failed validation"
        keys = extract_bibtex_keys(bibtex)
        assert len(keys) >= 1, f"No citation keys found for engine '{eng}'"


def test_alias_normalization() -> None:
    """Verifies that aliases resolve correctly to canonical catalog keys."""
    test_cases = [
        ("ORCA", "orca"),
        ("orca-6", "orca_v6"),
        ("orca_6.0", "orca_v6"),
        ("orca-5.0", "orca"),
        ("GOAT", "orca_v6"),
        ("c4", "cfour"),
        ("CREST", "crest"),
        ("imtd-gc", "crest_metadynamics"),
        ("GFN2-xTB", "gfn2_xtb"),
        ("gfn-xtb", "gfn2_xtb"),
        ("xtb", "xtb"),
        ("GFN-FF", "gfn_ff"),
        ("gpu-pyscf", "gpu4pyscf"),
        ("mace-off", "mace_off23"),
        ("mace-off23", "mace_off23"),
        ("r2scan-3c", "r2scan_3c"),
        ("wB97M-V", "wb97m_v"),
        ("dlpno-ccsd(t)", "dlpno_ccsd_t"),
        ("D3", "dft_d3"),
        ("dft-d4", "dft_d4"),
        ("Pickett", "spcat"),
        ("Parsl", "parsl"),
    ]

    for raw, expected in test_cases:
        norm = normalize_engine_key(raw)
        assert norm == expected, f"Expected '{raw}' -> '{expected}', got '{norm}'"
        assert lookup_bibtex(raw) is not None, f"lookup_bibtex failed for alias '{raw}'"


def test_bibtex_parser_and_validator() -> None:
    """Tests parse_and_validate_bibtex on valid, invalid, and deceptive BibTeX strings."""
    valid_bibtex = (
        "@article{Sample2026,\n"
        "  author = {Doe, John and Smith, Jane},\n"
        "  title = {A Quantum Chemical Method},\n"
        "  journal = {Journal of Chemical Physics},\n"
        "  year = {2026}\n"
        "}"
    )
    assert parse_and_validate_bibtex(valid_bibtex) is True

    # Valid conference/proceedings types
    valid_inproceedings = (
        "@inproceedings{Batatia2022MACE,\n"
        "  author = {Batatia, Ilyes},\n"
        "  title = {MACE Architecture},\n"
        "  booktitle = {NeurIPS},\n"
        "  year = {2022}\n"
        "}"
    )
    assert parse_and_validate_bibtex(valid_inproceedings) is True

    # Missing closing brace
    invalid_unbalanced = (
        "@article{Sample2026,\n"
        "  author = {Doe, John},\n"
        "  title = {Unbalanced Entry},\n"
        "  year = {2026}\n"
    )
    assert parse_and_validate_bibtex(invalid_unbalanced) is False

    # Deceptive fields (entitled, authority, yearbook) without real required keys
    deceptive_fields = (
        "@article{Sample2026,\n"
        "  authority = {Doe, John},\n"
        "  entitled = {A Quantum Chemical Method},\n"
        "  yearbook = {2026}\n"
        "}"
    )
    assert parse_and_validate_bibtex(deceptive_fields) is False

    # Empty string or non-bibtex
    assert parse_and_validate_bibtex("") is False
    assert parse_and_validate_bibtex("Not a bibtex entry") is False


def test_citation_tracker_registration() -> None:
    """Tests registration of engines on a local CitationTracker instance."""
    tracker = CitationTracker()
    assert tracker.get_tracked_engines() == []

    # Register single engine
    success = tracker.register_engine("ORCA", context="Geometry optimization of dimer")
    assert success is True
    assert "orca" in tracker.get_tracked_engines()

    # Register batch of engines
    count = tracker.register_engines(["cfour", "crest", "gfn2_xtb", "mace_off23"])
    assert count == 4
    tracked = tracker.get_tracked_engines()
    assert "cfour" in tracked
    assert "crest" in tracked
    assert "gfn2_xtb" in tracked
    assert "mace_off23" in tracked

    # Register unknown string
    assert tracker.register_engine("non_existent_engine_xyz") is False


def test_method_matrix_string_decomposition() -> None:
    """Verifies that compound Method Matrix method strings decompose into their constituent engines."""
    tracker = CitationTracker()

    # 1. r2SCAN-3c (tracks r2scan_3c and dft_d4)
    res = tracker.track_from_method_string("r2SCAN-3c")
    assert "r2scan_3c" in res
    assert "dft_d4" in res
    assert "r2scan_3c" in tracker.get_tracked_engines()
    assert "dft_d4" in tracker.get_tracked_engines()

    # 2. B97-3c (tracks b97_3c and dft_d3)
    tracker.clear()
    res = tracker.track_from_method_string("B97-3c/def2-mTZVP")
    assert "b97_3c" in res
    assert "dft_d3" in res

    # 3. CREST GFN2-xTB
    tracker.clear()
    res = tracker.track_from_method_string("crest seed01.xyz --nci --gfn2 --ewin 12")
    assert "crest" in res
    assert "gfn2_xtb" in res
    assert "xtb" in res

    # 4. wB97M-V/def2-QZVPP + D4
    tracker.clear()
    res = tracker.track_from_method_string("wB97M-V/def2-QZVPP with D4 dispersion")
    assert "wb97m_v" in res
    assert "dft_d4" in res

    # 5. DLPNO-CCSD(T)/cc-pVTZ
    tracker.clear()
    res = tracker.track_from_method_string("DLPNO-CCSD(T)/cc-pVTZ single point")
    assert "dlpno_ccsd_t" in res
    assert "orca" in res

    # 6. GOAT XTB2 PAL7
    tracker.clear()
    res = tracker.track_from_method_string("! GOAT XTB2 PAL7")
    assert "orca_v6" in res
    assert "gfn2_xtb" in res
    assert "xtb" in res

    # 7. ORCA 6.0 DLPNO-CCSD(T1)
    tracker.clear()
    res = tracker.track_from_method_string("ORCA 6.0 DLPNO-CCSD(T1)")
    assert "orca_v6" in res
    assert "dlpno_ccsd_t" in res
    assert "orca" in res

    # 8. iMTD-GC conformational sampling
    tracker.clear()
    res = tracker.track_from_method_string("iMTD-GC conformational search with ewin 6.0")
    assert "crest" in res


def test_substring_collision_immunity() -> None:
    """Verifies that regular English and chemistry words do not trigger accidental engine matches."""
    tracker = CitationTracker()

    # 'database' should NOT match 'ase'
    res = tracker.track_from_method_string("database_optimization")
    assert "ase" not in res
    assert len(res) == 0

    # 'phase' should NOT match 'ase'
    tracker.clear()
    res = tracker.track_from_method_string("gas_phase_thermo")
    assert "ase" not in res

    # 'c4h10' should NOT match 'cfour'
    tracker.clear()
    res = tracker.track_from_method_string("c4h10_conformer_search")
    assert "cfour" not in res

    # 'grimace' should NOT match 'mace'
    tracker.clear()
    res = tracker.track_from_method_string("grimace_potential_test")
    assert "mace" not in res
    assert "mace_off23" not in res

    # 'grid3' / 'grid4' should NOT match 'd3' / 'd4'
    tracker.clear()
    res = tracker.track_from_method_string("defgrid3 integration grid4")
    assert "dft_d3" not in res
    assert "dft_d4" not in res

    # 'd4h' / 'd3d' point group symmetry should NOT trigger dispersion d3/d4
    tracker.clear()
    res = tracker.track_from_method_string("D4h symmetry group and D3d point group")
    assert "dft_d3" not in res
    assert "dft_d4" not in res

    # 'parslip' / 'increase'
    tracker.clear()
    res = tracker.track_from_method_string("parslip increase base pair")
    assert "parsl" not in res
    assert "ase" not in res


def test_deduplication_of_bibtex_entries() -> None:
    """Verifies that duplicated citation keys (case-insensitive) are deduplicated while preserving order."""
    entry_1 = (
        "@article{Neese2022ORCA,\n"
        "  author = {Neese, Frank},\n"
        "  title = {ORCA 5.0},\n"
        "  year = {2022}\n"
        "}"
    )
    entry_2 = (
        "@article{Pracht2020CREST,\n"
        "  author = {Pracht, Philipp},\n"
        "  title = {CREST},\n"
        "  year = {2020}\n"
        "}"
    )
    entry_1_case_dup = (
        "@article{neese2022orca,\n"
        "  author = {Neese, Frank},\n"
        "  title = {ORCA 5.0 case variant},\n"
        "  year = {2022}\n"
        "}"
    )

    raw_list = [entry_1, entry_2, entry_1_case_dup]
    deduped = deduplicate_bibtex_entries(raw_list)
    assert len(deduped) == 2
    assert deduped[0] == entry_1
    assert deduped[1] == entry_2


def test_physical_bibtex_file_generation(tmp_path: Path) -> None:
    """Physical Zero-Mock test verifying that cochem_citations.bib is written and readable."""
    tracker = CitationTracker(default_output_dir=tmp_path)
    tracker.register_engines(["orca", "cfour", "crest", "r2scan_3c", "dft_d4"])

    out_file = tracker.write_bibtex_file()
    assert out_file.exists()
    assert out_file.is_file()
    assert out_file.name == "cochem_citations.bib"

    content = out_file.read_text(encoding="utf-8")
    assert "CoChem-BASE Automated Scientific Citations Bibliography" in content
    assert "@article{Neese2022ORCA" in content
    assert "@article{Matthews2020CFOUR" in content
    assert "@article{Pracht2020CREST" in content
    assert "@article{Grimme2021r2SCAN3c" in content
    assert "@article{Caldeweyher2019DFTD4" in content

    # Test custom output filepath
    custom_target = tmp_path / "subdir" / "my_custom_citations.bib"
    out_custom = tracker.write_bibtex_file(output_path=custom_target)
    assert out_custom.exists()
    assert out_custom.read_text(encoding="utf-8") == content


def test_markdown_summary_export(tmp_path: Path) -> None:
    """Verifies generation and physical export of the Markdown provenance summary table."""
    tracker = CitationTracker(default_output_dir=tmp_path)
    tracker.register_engines(["orca", "mace_off23", "spcat"])

    md_path = tmp_path / "citations_summary.md"
    md_content = tracker.export_summary_markdown(output_path=md_path)

    assert md_path.exists()
    assert "# CoChem-BASE Scientific Provenance & Citations Summary" in md_content
    assert "| **ORCA Quantum Chemistry Program** |" in md_content
    assert "| **MACE-OFF23 Transferable Force Field** |" in md_content
    assert "| **SPCAT Rotational Spectrum Prediction Engine** |" in md_content
    assert "```bibtex" in md_content


def test_markdown_summary_export_deduplication(tmp_path: Path) -> None:
    """Verifies that duplicate engine registrations do not produce duplicate Markdown table rows."""
    tracker = CitationTracker(default_output_dir=tmp_path)
    # Register duplicates
    tracker.register_engines(["orca", "ORCA", "orca", "crest", "crest"])

    md_content = tracker.export_summary_markdown()
    assert md_content.count("| **ORCA Quantum Chemistry Program** |") == 1
    assert md_content.count("| **CREST Conformer Sampling Engine** |") == 1


def test_custom_citation_registration() -> None:
    """Verifies that custom user citations can be registered and rendered."""
    tracker = CitationTracker()
    custom_bib = (
        "@article{CustomLab2026,\n"
        "  author = {Custom, Chemist and Colleague, Jane},\n"
        "  title = {Novel Reaction Coordinate Solver},\n"
        "  journal = {Journal of Computational Chemistry},\n"
        "  year = {2026},\n"
        "  doi = {10.1002/jcc.99999}\n"
        "}"
    )

    custom_entry = EngineCitation(
        engine_id="custom_solver",
        name="Custom Reaction Coordinate Solver",
        category="Reaction Path Engine",
        description="In-house transition state search engine.",
        bibtex=custom_bib,
        doi="10.1002/jcc.99999",
    )

    tracker.register_custom_citation(custom_entry)
    assert "custom_solver" in tracker.get_tracked_engines()

    bib_str = tracker.generate_bibtex_string()
    assert "@article{CustomLab2026" in bib_str

    # Test invalid custom citation rejection
    with pytest.raises(ValueError, match="Invalid BibTeX syntax"):
        bad_entry = EngineCitation(
            engine_id="bad_solver",
            name="Bad Solver",
            category="Failed",
            description="Failed",
            bibtex="Invalid non-bibtex string",
        )
        tracker.register_custom_citation(bad_entry)


def test_global_tracker_workflow(tmp_path: Path) -> None:
    """Tests the global module-level convenience API functions."""
    track_engine("orca", context="Single point energy")
    track_engines(["crest", "gfn2_xtb"])
    track_method("r2SCAN-3c/def2-mTZVPP with D4")

    global_tracker = get_global_citation_tracker()
    tracked = global_tracker.get_tracked_engines()

    assert "orca" in tracked
    assert "crest" in tracked
    assert "gfn2_xtb" in tracked
    assert "r2scan_3c" in tracked
    assert "dft_d4" in tracked

    bibtex_out = generate_bibtex_string()
    assert "@article{Neese2022ORCA" in bibtex_out
    assert "@article{Pracht2020CREST" in bibtex_out

    bib_file = write_citations_bib(output_path=tmp_path / "global_citations.bib")
    assert bib_file.exists()
    assert bib_file.stat().st_size > 0

    clear_tracked_citations()
    assert len(global_tracker.get_tracked_engines()) == 0


def test_src_layout_citations_standalone_mirror(tmp_path: Path) -> None:
    """Verifies that src/cochem_base/provenance/citations.py is a complete standalone mirror."""
    import importlib.util
    import sys

    src_citations_path = Path(__file__).resolve().parent.parent / "src" / "cochem_base" / "provenance" / "citations.py"
    assert src_citations_path.exists(), f"Missing src layout citations file at {src_citations_path}"

    spec = importlib.util.spec_from_file_location("src_cochem_citations", src_citations_path)
    assert spec is not None and spec.loader is not None
    src_mod = importlib.util.module_from_spec(spec)
    sys.modules["src_cochem_citations"] = src_mod
    spec.loader.exec_module(src_mod)

    # Validate catalog & tracker from src module
    catalog = src_mod.get_bibtex_catalog()
    assert len(catalog) >= 25

    tracker = src_mod.CitationTracker(default_output_dir=tmp_path)
    tracker.register_engines(["orca", "cfour", "crest", "r2scan_3c", "dft_d4", "mace_off23", "spcat"])
    assert len(tracker.get_tracked_engines()) == 7

    out_file = tracker.write_bibtex_file()
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "@article{Neese2022ORCA" in content
    assert "@article{Matthews2020CFOUR" in content
    assert "@article{Pickett1991SPCAT" in content

    md_summary = tracker.export_summary_markdown()
    assert "ORCA Quantum Chemistry Program" in md_summary
    assert "SPCAT Rotational Spectrum Prediction Engine" in md_summary

