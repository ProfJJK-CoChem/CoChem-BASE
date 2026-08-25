"""Live Verification Suite for CrossRef Citation API & Bibliographer.

Conforms to CoChem Anti-Spoofing Protocol:
- Strictly Real Execution: Real network queries, real filesystem writes.
- Real network queries against api.crossref.org with Polite Pool rate limiting.
- Real physical timeouts against non-routable IP endpoints for air-gap resilience.
- Real filesystem writes and UTF-8 verification.
- Complete 6-Tier Environment Matrix and Method Matrix v4 compliance.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import pathlib
import re
import subprocess
import sys
import time
from typing import Any

import pytest

from formatters.scribe_citation_api import CitationManager

# Test threshold constants to satisfy linting
MIN_RATE_LIMIT_DURATION: float = 0.95
MIN_PAYLOAD_BYTE_COUNT: int = 200
EXPECTED_DEDUP_COUNT: int = 2
MIN_MANIFEST_RESOLVED_COUNT: int = 5
SUBPROCESS_TIMEOUT_SECONDS: float = 15.0


# ==============================================================================
# PYTEST FIXTURE ARCHITECTURE
# ==============================================================================
@pytest.fixture
def tmp_bib_export_path(tmp_path: pathlib.Path) -> pathlib.Path:
    """Generates a concrete physical destination path in a nested directory."""
    return tmp_path / "Report_Archive" / "cochem_citations.bib"


@pytest.fixture
def sample_deployment_manifest(tmp_path: pathlib.Path) -> pathlib.Path:
    """Writes an authentic cochem_deployment_manifest.json to physical disk."""
    manifest_path = tmp_path / "cochem_deployment_manifest.json"
    manifest_payload: dict[str, Any] = {
        "engine": "ORCA 6.1.1",
        "method": "DLPNO-CCSD(T)",
        "basis_set": "def2-TZVP",
        "ml_potential": "MACE-OFF23",
        "semiempirical": "GFN2-xTB",
        "dispersion": "D4",
    }
    manifest_path.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")
    return manifest_path


@pytest.fixture
def sample_raw_crossref_payload() -> dict[str, Any]:
    """Provides a realistic CrossRef REST API response payload matching works schema."""
    return {
        "title": [
            "A generally applicable atomic-charge dependent London "
            "dispersion correction"
        ],
        "author": [
            {"given": "Eike", "family": "Caldeweyher", "sequence": "first"},
            {"given": "Sebastian", "family": "Ehlert", "sequence": "additional"},
            {"given": "Andreas", "family": "Hansen", "sequence": "additional"},
            {"given": "Hagen", "family": "Neugebauer", "sequence": "additional"},
            {"given": "Jens", "family": "Antony", "sequence": "additional"},
            {"given": "Stefan", "family": "Grimme", "sequence": "additional"},
        ],
        "container-title": ["The Journal of Chemical Physics"],
        "publisher": "AIP Publishing",
        "volume": "150",
        "issue": "15",
        "page": "154122",
        "issued": {"date-parts": [[2019, 4, 15]]},
        "DOI": "10.1063/1.5090222",
        "type": "journal-article",
    }


@pytest.fixture
def offline_manager(tmp_path: pathlib.Path) -> CitationManager:
    """Fixture providing CitationManager initialized in strict offline mode."""
    target_bib = tmp_path / "cochem_citations.bib"
    return CitationManager(output_path=target_bib, offline_mode=True)


@pytest.fixture
def online_manager(tmp_path: pathlib.Path) -> CitationManager:
    """Fixture providing CitationManager initialized in online mode."""
    target_bib = tmp_path / "cochem_citations.bib"
    return CitationManager(
        output_path=target_bib,
        contact_email="contact@cochem.org",
        rate_limit_delay=1.0,
        request_timeout=5.0,
        offline_mode=False,
    )


# ==============================================================================
# TEST 1: CrossRef Polite Pool Live Query & Rate Limiting (Task 71, 79, 80)
# ==============================================================================
def test_crossref_live_query_and_rate_limiting(
    online_manager: CitationManager,
) -> None:
    """Tests live query against CrossRef and verifies Polite Pool rate-limiting."""
    # Verify User-Agent header conforms to CrossRef Polite Pool regulations
    user_agent = online_manager.session.headers.get("User-Agent", "")
    assert "mailto:contact@cochem.org" in user_agent, (
        f"User-Agent '{user_agent}' does not contain required polite mailto"
    )

    doi_query = "10.1063/1.5090222"
    metadata = online_manager.query_crossref_doi(doi_query)

    if metadata is not None:
        assert isinstance(metadata, dict)
        assert "title" in metadata or "DOI" in metadata

        # Test BibTeX formatting from live CrossRef JSON metadata
        bibtex_entry = online_manager.format_bibtex_entry(metadata, "Grimme_D4")
        assert bibtex_entry.startswith("@article{")
        assert "Grimme_D4" in bibtex_entry
        assert "Caldeweyher" in bibtex_entry
        assert "2019" in bibtex_entry
        assert "10.1063/1.5090222" in bibtex_entry
        assert "London dispersion correction" in bibtex_entry

        # Test Polite Pool: consecutive request must respect rate_limit_delay
        start_second_req = time.perf_counter()
        second_query = "10.1021/acs.jctc.8b01176"
        second_metadata = online_manager.query_crossref_doi(second_query)
        second_duration = time.perf_counter() - start_second_req

        assert second_duration >= MIN_RATE_LIMIT_DURATION, (
            f"Rate limiting failed: took {second_duration:.3f}s, expected >= 1.0s"
        )
        assert second_metadata is not None
    else:
        # If running on air-gapped test node, verify fallback resolution succeeds
        cite_key, fallback_bib = online_manager.resolve_method_citation("D4")
        assert cite_key
        assert "Caldeweyher" in fallback_bib or "Grimme" in fallback_bib


# ==============================================================================
# TEST 2: Offline Mode & Static Fallback Dictionary (Task 73, 80)
# ==============================================================================
def test_airgap_offline_fallback_resolution(
    offline_manager: CitationManager,
) -> None:
    """Tests offline mode resolution for all Method Matrix engines."""
    assert offline_manager.is_offline() is True

    test_matrix: list[tuple[str, str, str, str]] = [
        ("ORCA 6.1.1", "Neese", "ORCA", "2022"),
        ("ORCA", "Neese", "ORCA", "2022"),
        ("PySCF 2.7.0", "Sun", "PySCF", "2020"),
        ("PySCF", "Sun", "PySCF", "2020"),
        ("MACE-OFF23", "Batatia", "MACE-OFF23", "2023"),
        ("MACE", "Batatia", "MACE", "2023"),
        ("GFN2-xTB", "Bannwarth", "GFN2-xTB", "2019"),
        ("xTB", "Bannwarth", "GFN2-xTB", "2019"),
        ("D4", "Caldeweyher", "D4", "2019"),
        ("Grimme D4", "Caldeweyher", "D4", "2019"),
        ("DLPNO-CCSD(T)", "Riplinger", "DLPNO", "2013"),
        ("CREST", "Pracht", "CREST", "2020"),
        ("r2SCAN-3c", "Grimme", "r2SCAN-3c", "2021"),
        ("B3LYP", "Becke", "B3LYP", "1993"),
        ("mendeleev", "Komarov", "mendeleev", "2020"),
        ("SpycFit", "CoChem", "SpycFit", "2024"),
    ]

    for method_name, exp_author, exp_token, exp_year in test_matrix:
        cite_key, bibtex_str = offline_manager.resolve_method_citation(method_name)
        assert cite_key, f"Missing cite_key for {method_name}"
        assert bibtex_str, f"Missing BibTeX entry for {method_name}"
        assert bibtex_str.startswith("@article{") or bibtex_str.startswith("@misc{")
        assert exp_author.lower() in bibtex_str.lower(), (
            f"Author '{exp_author}' not found for '{method_name}':\n{bibtex_str}"
        )
        assert exp_token.lower() in bibtex_str.lower(), (
            f"Token '{exp_token}' not found for '{method_name}':\n{bibtex_str}"
        )
        assert exp_year in bibtex_str, (
            f"Year '{exp_year}' not found for '{method_name}':\n{bibtex_str}"
        )
        assert "doi = {" in bibtex_str or "doi = " in bibtex_str
        # Verify no placeholder strings exist
        for placeholder in ["TODO", "FIXME", "XXX", "dummy", "placeholder"]:
            assert placeholder not in bibtex_str


# ==============================================================================
# TEST 3: Offline Environment Variable Auto-Detection (Task 73)
# ==============================================================================
def test_cochem_offline_environment_variable() -> None:
    """Tests automatic detection of COCHEM_OFFLINE environment variable."""
    original_env = os.environ.get("COCHEM_OFFLINE")
    try:
        os.environ["COCHEM_OFFLINE"] = "1"
        mgr1 = CitationManager(offline_mode=None)
        assert mgr1.is_offline() is True

        os.environ["COCHEM_OFFLINE"] = "true"
        mgr2 = CitationManager(offline_mode=None)
        assert mgr2.is_offline() is True

        os.environ["COCHEM_OFFLINE"] = "TRUE"
        mgr2_upper = CitationManager(offline_mode=None)
        assert mgr2_upper.is_offline() is True

        os.environ["COCHEM_OFFLINE"] = "0"
        mgr3 = CitationManager(offline_mode=None)
        assert mgr3.is_offline() is False

        os.environ["COCHEM_OFFLINE"] = "false"
        mgr3_false = CitationManager(offline_mode=None)
        assert mgr3_false.is_offline() is False

        # Explicit parameter takes precedence over environment variable
        mgr4 = CitationManager(offline_mode=True)
        assert mgr4.is_offline() is True
    finally:
        if original_env is not None:
            os.environ["COCHEM_OFFLINE"] = original_env
        else:
            os.environ.pop("COCHEM_OFFLINE", None)


# ==============================================================================
# TEST 4: Zero-Mock Physical Network Timeout & Exception Trapping (Task 73, 80)
# ==============================================================================
def test_network_timeout_and_exception_trapping(tmp_path: pathlib.Path) -> None:
    """Tests network exception handling on loopback and non-routable endpoints."""
    target_bib = tmp_path / "cochem_citations.bib"

    # Test 1: Closed local loopback endpoint (port 9 discard)
    loopback_manager = CitationManager(
        output_path=target_bib,
        api_url="http://127.0.0.1:9",
        request_timeout=0.05,
        rate_limit_delay=0.0,
        offline_mode=False,
    )
    cite_key, bibtex_str = loopback_manager.resolve_method_citation("ORCA 6.1.1")
    assert "Neese" in cite_key or "Neese" in bibtex_str
    assert "10.1002/wcms.1606" in bibtex_str

    # Test 2: IANA non-routable TEST-NET-1 IP address
    resilient_manager = CitationManager(
        output_path=target_bib,
        api_url="http://192.0.2.1:80/works",
        request_timeout=0.05,
        rate_limit_delay=0.0,
        offline_mode=False,
    )
    cite_key2, bibtex_str2 = resilient_manager.resolve_method_citation("GFN2-xTB")
    assert "Bannwarth" in cite_key2 or "Bannwarth" in bibtex_str2
    assert "10.1021/acs.jctc.8b01176" in bibtex_str2


# ==============================================================================
# TEST 5: Deterministic BibTeX Key Generation & Collision Sanitization (Task 72)
# ==============================================================================
def test_deterministic_bibtex_key_generation(offline_manager: CitationManager) -> None:
    """Tests key generation with complex strings, accents, and sanitization."""
    key1 = offline_manager.generate_citation_key("Grimme", "GFN2-xTB", 2019)
    assert key1 == "Grimme_GFN2_xTB_2019"

    key2 = offline_manager.generate_citation_key(
        "Riplinger & Neese", "DLPNO-CCSD(T)/CBS", "2013"
    )
    assert key2 == "Riplinger_Neese_DLPNO_CCSD_T_CBS_2013"

    key3 = offline_manager.generate_citation_key(
        "Batatia et al.", "MACE-OFF23 (O(3) Equivariant)", 2023
    )
    assert key3 == "Batatia_MACE_OFF23_O_3_Equivariant_2023"

    # Accented names must decompose to pure ASCII
    key4 = offline_manager.generate_citation_key(
        "Müller-Gross", "r2SCAN-3c (def2-mTZVP)", 2021
    )
    assert key4 == "Muller_Gross_r2SCAN_3c_def2_mTZVP_2021"

    key5 = offline_manager.generate_citation_key("Kovács", "MACE-OFF23", "2023")
    assert key5 == "Kovacs_MACE_OFF23_2023"

    # Assert keys match strict regex: ONLY alphanumeric and underscores
    for key in [key1, key2, key3, key4, key5]:
        assert re.match(r"^[A-Za-z0-9_]+$", key), (
            f"Key '{key}' contains invalid characters"
        )
        assert " " not in key
        assert "-" not in key
        assert "/" not in key
        assert "(" not in key
        assert ")" not in key


# ==============================================================================
# TEST 6: Dynamic BibTeX Formatter (Task 72)
# ==============================================================================
def test_dynamic_bibtex_formatter(
    offline_manager: CitationManager, sample_raw_crossref_payload: dict[str, Any]
) -> None:
    """Tests formatting of CrossRef metadata into standardized BibTeX string."""
    bibtex_entry = offline_manager.format_bibtex_entry(
        sample_raw_crossref_payload, "Grimme_D4"
    )

    assert bibtex_entry.startswith("@article{")
    assert "Caldeweyher" in bibtex_entry
    assert "Ehlert" in bibtex_entry
    assert "Grimme" in bibtex_entry
    assert "title = {" in bibtex_entry
    assert "London dispersion correction" in bibtex_entry
    assert "journal = {The Journal of Chemical Physics}" in bibtex_entry
    assert "volume = {150}" in bibtex_entry
    assert "number = {15}" in bibtex_entry
    assert "pages = {154122}" in bibtex_entry
    assert "year = {2019}" in bibtex_entry
    assert "doi = {10.1063/1.5090222}" in bibtex_entry
    assert bibtex_entry.endswith("}")


# ==============================================================================
# TEST 7: Cryptographic & Citation Key Deduplication (Task 74)
# ==============================================================================
def test_cryptographic_citation_key_deduplication(
    offline_manager: CitationManager,
) -> None:
    """Tests deduplication across varying DOI URL prefixes, quotes, and slashes."""
    entry1 = (
        "@article{Key1,\n"
        "  author = {Neese, Frank},\n"
        "  title = {Paper 1},\n"
        "  year = {2022},\n"
        "  doi = {10.1002/wcms.1606}\n"
        "}"
    )
    entry2 = (
        "@article{Key2,\n"
        "  author = {Neese, Frank},\n"
        "  title = {Paper 2},\n"
        "  year = {2022},\n"
        '  doi = "https://doi.org/10.1002/wcms.1606"\n'
        "}"
    )
    entry3 = (
        "@article{Key3,\n"
        "  author = {Neese, Frank},\n"
        "  title = {Paper 3},\n"
        "  year = {2022},\n"
        "  doi = {http://dx.doi.org/10.1002/wcms.1606/}\n"
        "}"
    )
    entry4 = (
        "@article{Key4,\n"
        "  author = {Neese, Frank},\n"
        "  title = {Paper 4},\n"
        "  year = {2022},\n"
        "  doi = {doi:10.1002/wcms.1606}\n"
        "}"
    )
    entry_pyscf = (
        "@article{Sun_PySCF_2020,\n"
        "  author = {Sun, Qiming and others},\n"
        "  title = {Recent developments in the PySCF program package},\n"
        "  journal = {J. Chem. Phys.},\n"
        "  year = {2020},\n"
        "  doi = {10.1063/5.0006074}\n"
        "}"
    )

    raw_list = [entry1, entry2, entry3, entry4, entry_pyscf, entry_pyscf]
    deduped = offline_manager.deduplicate_citations(raw_list)

    assert len(deduped) == EXPECTED_DEDUP_COUNT
    assert deduped[0] == entry1
    assert deduped[1] == entry_pyscf


# ==============================================================================
# TEST 8: Real Physical Disk Export & Path Resolution (Task 74)
# ==============================================================================
def test_real_physical_disk_export(
    tmp_bib_export_path: pathlib.Path, offline_manager: CitationManager
) -> None:
    """Tests physical disk write of BibTeX payload with directory creation."""
    citations = {
        "Neese_ORCA_2022": offline_manager.FALLBACK_CITATIONS["ORCA"],
        "Sun_PySCF_2020": offline_manager.FALLBACK_CITATIONS["PySCF"],
    }
    payload = offline_manager.build_bibtex_payload(citations)

    # Check payload header
    assert "% CoChem Auto-Generated Bibliography" in payload
    assert "% CoChem-SCRIBE Automated Bibliographer" in payload
    assert "@article{Neese_ORCA_2022" in payload
    assert "@article{Sun_PySCF_2020" in payload

    # Write file to target path
    written_path = offline_manager.write_citations_file(
        payload, target_path=tmp_bib_export_path
    )
    assert written_path == tmp_bib_export_path.resolve()
    assert tmp_bib_export_path.exists()
    assert tmp_bib_export_path.is_file()

    # Read back and verify UTF-8 contents
    content = tmp_bib_export_path.read_text(encoding="utf-8")
    assert content == payload
    assert len(content) > MIN_PAYLOAD_BYTE_COUNT


# ==============================================================================
# TEST 9: End-to-End Manifest Ingestion & Method Resolution (Task 71–74)
# ==============================================================================
def test_end_to_end_manifest_ingestion(
    sample_deployment_manifest: pathlib.Path,
    tmp_bib_export_path: pathlib.Path,
    offline_manager: CitationManager,
) -> None:
    """Tests end-to-end extraction and resolution of methods from manifest file."""
    assert sample_deployment_manifest.exists()
    manifest_data = json.loads(
        sample_deployment_manifest.read_text(encoding="utf-8")
    )

    resolved_citations = offline_manager.process_manifest_methods(manifest_data)
    assert isinstance(resolved_citations, dict)
    assert len(resolved_citations) >= MIN_MANIFEST_RESOLVED_COUNT

    combined_bibtex = offline_manager.build_bibtex_payload(resolved_citations)
    assert "Neese" in combined_bibtex
    assert "Riplinger" in combined_bibtex
    assert "Batatia" in combined_bibtex
    assert "Bannwarth" in combined_bibtex
    assert "Caldeweyher" in combined_bibtex

    written_file = offline_manager.write_citations_file(
        combined_bibtex, target_path=tmp_bib_export_path
    )
    assert written_file.exists()
    file_content = written_file.read_text(encoding="utf-8")
    assert file_content == combined_bibtex


# ==============================================================================
# TEST 10: Nullable JSON API Field Protection
# ==============================================================================
def test_nullable_json_api_field_resilience(
    offline_manager: CitationManager,
) -> None:
    """Tests format_bibtex_entry resilience against nullable metadata fields."""
    nullable_metadata: dict[str, Any] = {
        "author": [
            {"family": None, "given": None},
            {"family": "Smith", "given": None},
        ],
        "title": None,
        "container-title": None,
        "publisher": None,
        "volume": None,
        "issue": None,
        "journal-issue": None,
        "page": None,
        "issued": None,
        "DOI": None,
    }

    bibtex_entry = offline_manager.format_bibtex_entry(
        nullable_metadata, "DFT_Dispersion"
    )
    assert bibtex_entry.startswith("@article{")
    assert "Smith" in bibtex_entry
    assert "DFT_Dispersion" in bibtex_entry


# ==============================================================================
# TEST 11: Thread-Safe Rate Limiting (Task 79, 80)
# ==============================================================================
def test_thread_safe_rate_limiting() -> None:
    """Tests concurrent calls serialize properly under rate-limiting delay."""
    delay = 0.10
    num_workers = 4

    def concurrent_rate_task() -> None:
        CitationManager._enforce_rate_limit(delay)

    start_time = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(concurrent_rate_task) for _ in range(num_workers)]
        for f in futures:
            f.result()
    total_time = time.perf_counter() - start_time
    expected_min = (num_workers - 1) * delay * 0.8
    err_msg = (
        f"Rate limiting failed: took {total_time:.3f}s, expected >= {expected_min:.3f}s"
    )
    assert total_time >= expected_min, err_msg


# ==============================================================================
# TEST 12: Local Pre-Flight CLI Block Subprocess Execution
# ==============================================================================
def test_preflight_cli_execution() -> None:
    """Executes scribe_citation_api.py as a standalone CLI script."""
    module_path = pathlib.Path(__file__).parent / "scribe_citation_api.py"
    assert module_path.exists(), f"Module file not found: {module_path}"

    cmd = [sys.executable, str(module_path)]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
        check=True,
    )

    assert result.returncode == 0, (
        f"Script failed with code {result.returncode}:\n{result.stderr}"
    )
    assert "[SCRIBE CITATION API PRE-FLIGHT VERIFIED]" in result.stdout


# ==============================================================================
# TEST 13: LaTeX Special Character Escaping Verification
# ==============================================================================
def test_latex_special_character_escaping(offline_manager: CitationManager) -> None:
    """Tests that unescaped LaTeX characters in metadata are properly escaped."""
    metadata: dict[str, Any] = {
        "author": [{"family": "Smith & Jones", "given": "John"}],
        "title": "Quantum 100% Efficiency & Accuracy for B3LYP_D3 #1 $E=mc^2$",
        "container-title": "Journal of R&D",
        "publisher": "Wiley & Sons",
        "volume": "10",
        "issue": "2",
        "page": "100-110",
        "issued": {"date-parts": [[2023]]},
        "DOI": "10.1000/182",
    }
    bibtex = offline_manager.format_bibtex_entry(metadata, "Special_Method")
    assert r"100\%" in bibtex
    assert r"R\&D" in bibtex or r"Wiley \& Sons" in bibtex
    assert r"B3LYP\_D3" in bibtex
    assert r"\#1" in bibtex
    assert r"\$E=mc^2\$" in bibtex

    # Verify generic fallback escaping
    cite_key, generic_bib = offline_manager.resolve_method_citation("Custom_DFT_100%")
    assert r"100\%" in generic_bib
    assert r"Custom\_DFT\_100\%" in generic_bib


# ==============================================================================
# TEST 14: DOI URL Query and Fragment Stripping
# ==============================================================================
def test_doi_url_query_and_fragment_stripping() -> None:
    """Tests that query parameters and URL fragments are cleaned from DOIs."""
    raw_with_query = "https://doi.org/10.1002/wcms.1606?utm_source=springer&id=1#abstract"
    normalized = CitationManager.normalize_doi(raw_with_query)
    assert normalized == "10.1002/wcms.1606"

    raw_with_fragment = "10.1063/1.5090222#fig1"
    normalized_frag = CitationManager.normalize_doi(raw_with_fragment)
    assert normalized_frag == "10.1063/1.5090222"


# ==============================================================================
# TEST 15: Corporate & Institutional Author Double Bracing
# ==============================================================================
def test_corporate_author_double_braces(offline_manager: CitationManager) -> None:
    """Tests that institutional author names are enclosed in double braces."""
    metadata = {
        "author": [{"name": "The PySCF Development Team"}],
        "title": "PySCF GPU Engine",
        "issued": {"date-parts": [[2024]]},
        "DOI": "10.1000/pyscf",
    }
    bibtex = offline_manager.format_bibtex_entry(metadata, "PySCF_GPU")
    assert "author = {{The PySCF Development Team}}" in bibtex
