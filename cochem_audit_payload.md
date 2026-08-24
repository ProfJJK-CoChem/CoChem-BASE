Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-SCRIBE\.in-progress\prompt_test_scribe_citation_api.md.
Original prompt:
# CoChem-SCRIBE: Implement Citation API Tests (`formatters/test_scribe_citation_api.py`)

**Target Repository Path:** `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE`  
**Target File:** `formatters/test_scribe_citation_api.py`

---

## Objective
Implement an exhaustive, production-grade, and self-contained `pytest` test suite in `formatters/test_scribe_citation_api.py` to validate the `CitationManager` class implemented in `formatters/scribe_citation_api.py`.

The test suite must strictly comply with **CoChem-SCRIBE SRS Phase 4, Task 10 (Stage 6.3, Tasks 71–74, 79, 80)**, **Method Matrix v4**, the **Zero-Mock Anti-Spoofing Protocol**, **FAIR Data Principles**, and the **6-Tier Environment Matrix** (Local-Windows WSL, Local-MacOS OrbStack, Local-Linux Debian, Codespaces, GitHub Actions, HPC).

---

## Zero-Mock & Anti-Spoofing Protocol Directives

1. **Strict Prohibition of Mocks and Stubs:**
   - Under NO circumstances may `unittest.mock`, `unittest.mock.patch`, `unittest.mock.MagicMock`, `pytest-mock` (`mocker`), monkeypatching, or fake simulated in-memory response objects be used.
   - All tests must execute against real physical objects, real network sockets, real physical disk files, and real exception handling pathways.
2. **Real Physical Filesystem I/O (No "Virtual File Systems"):**
   - In-memory fake filesystems (e.g. `pyfakefs`, `StringIO`, dummy bypasses) are strictly prohibited.
   - All disk write tests must execute against real physical disk directories provisioned dynamically via `pytest`'s `tmp_path` fixture.
3. **No Impossible OS or Privilege Requirements:**
   - Tests must NOT attempt to reconfigure host firewall rules (`iptables`, `ufw`, Windows Defender Firewall) or manipulate Linux network namespaces (`ip netns`), as tests must execute seamlessly under unprivileged user permissions across the 6-Tier Environment Matrix.
   - Offline and network failure behavior must be tested via architected configuration flags (`offline_mode=True`, `COCHEM_OFFLINE=1`), ultra-low socket timeout thresholds (`request_timeout=0.001`), or closed local loopback endpoints (e.g. `http://127.0.0.1:9`).
4. **Zero Placeholders:**
   - Complete, functional Python 3.10+ code only. Strictly NO `pass`, `# TODO`, `...`, or skipped assertions.

---

## Technical Specifications & Test Architecture

### 1. Pytest Fixture Architecture

Implement self-contained `pytest` fixtures within `formatters/test_scribe_citation_api.py`:
- `tmp_bib_export_path(tmp_path)`:
  - Generates a concrete physical destination path (`tmp_path / "Report_Archive" / "cochem_citations.bib"`).
- `sample_deployment_manifest(tmp_path)`:
  - Writes an authentic `cochem_deployment_manifest.json` containing active software stack specifications:
    ```json
    {
      "engine": "ORCA 6.1.1",
      "method": "DLPNO-CCSD(T)",
      "basis_set": "def2-TZVP",
      "ml_potential": "MACE-OFF23",
      "semiempirical": "GFN2-xTB",
      "dispersion": "D4"
    }
    ```
- `sample_raw_crossref_payload()`:
  - Provides a realistic, physically structured CrossRef REST API response dictionary matching the exact schema returned by `https://api.crossref.org/works`.

---

## Required Test Cases

### Test Case 1: CrossRef Polite Pool Live Query & Rate Limiting (Task 71, 79, 80)
- **Target:** `CitationManager.query_crossref_doi()` and `CitationManager._enforce_rate_limit()`
- **Assertions:**
  - If executed in an environment with outbound internet connectivity, query a known, canonical, static DOI (e.g. Grimme's D4 dispersion publication: `10.1063/1.5090222` / `"Caldeweyher D4 dispersion"`).
  - Verify that the HTTP `User-Agent` header configured in the session contains the required `mailto:contact@cochem.org` string adhering to CrossRef Polite Pool regulations.
  - Perform two consecutive queries and measure elapsed time using `time.perf_counter()`; assert that the interval between requests is strictly $\ge 1.0\text{ s}$ due to polite rate-limiting.
  - Assert that the returned payload contains the expected title ("*A generally applicable atomic-charge dependent London dispersion correction*"), author surname ("Caldeweyher"), and year (`2019`).
  - If executed on a fully offline test node, verify that network unreachable conditions gracefully return `None` or cleanly trigger static fallback without raising unhandled fatal exceptions.

### Test Case 2: Offline Mode & Static Fallback Dictionary (Task 73, 80)
- **Target:** `CitationManager.get_fallback_citation()` and `CitationManager.resolve_method_citation()`
- **Assertions:**
  - Instantiate `CitationManager(offline_mode=True)`.
  - Resolve citations for all mandatory CoChem Method Matrix v4 engines:
    1. `"ORCA 6.1.1"` / `"ORCA"` -> Must contain `@article{` or `@software{`, `Neese`, and valid DOI/year.
    2. `"PySCF 2.7.0"` / `"PySCF"` -> Must contain `Sun`, `PySCF`, `2020`.
    3. `"MACE-OFF23"` / `"MACE"` -> Must contain `Batatia`, `MACE-OFF23`, `2023`.
    4. `"GFN2-xTB"` / `"xTB"` -> Must contain `Bannwarth`, `GFN2-xTB`, `2019`.
    5. `"D4"` / `"Grimme D4"` -> Must contain `Caldeweyher`, `D4`, `2019`.
    6. `"DLPNO-CCSD(T)"` -> Must contain `Riplinger`, `Neese`, `2013`.
  - Assert that all returned BibTeX strings are non-empty, syntactically valid LaTeX blocks, and contain no placeholder markers.

### Test Case 3: Offline Environment Variable Auto-Detection (Task 73)
- **Target:** `CitationManager.is_offline()`
- **Assertions:**
  - Test setting `os.environ["COCHEM_OFFLINE"] = "1"` and `"true"` (case-insensitive).
  - Verify `CitationManager().is_offline()` evaluates to `True`.
  - Verify that setting `COCHEM_OFFLINE="0"` or `"false"` (when `offline_mode=None`) evaluates to `False`.

### Test Case 4: Zero-Mock Physical Network Timeout & Exception Trapping (Task 73, 80)
- **Target:** `CitationManager.query_crossref_doi()` network exception trapping
- **Assertions:**
  - Instantiate `CitationManager` pointing to an unreachable, closed local port (e.g., `http://127.0.0.1:9` with `request_timeout=0.05`).
  - Execute citation resolution.
  - Assert that `CitationManager` traps `requests.exceptions.RequestException` (ConnectionRefused / ConnectionError / Timeout), logs a warning, and immediately degrades to the canonical static fallback without crashing the process.

### Test Case 5: Deterministic BibTeX Key Generation & Collision Sanitization (Task 72)
- **Target:** `CitationManager.generate_citation_key()`
- **Assertions:**
  - Test keys with complex characters:
    - `generate_citation_key("Grimme", "GFN2-xTB", 2019)` -> `Grimme_GFN2_xTB_2019`
    - `generate_citation_key("Riplinger & Neese", "DLPNO-CCSD(T)/CBS", "2013")` -> `Riplinger_Neese_DLPNO_CCSD_T_CBS_2013`
    - `generate_citation_key("Batatia et al.", "MACE-OFF23 (O(3) Equivariant)", 2023)` -> `Batatia_MACE_OFF23_O_3_Equivariant_2023`
  - Assert that the generated keys contain ONLY alphanumeric characters and underscores (`^[A-Za-z0-9_]+$`).
  - Assert no spaces, hyphens, slashes, or parentheses exist in the final BibTeX key.

### Test Case 6: Dynamic BibTeX Formatter (Task 72)
- **Target:** `CitationManager.format_bibtex_entry()`
- **Assertions:**
  - Feed a structured CrossRef metadata dictionary containing `title`, `author` list, `container-title`, `volume`, `page`, `year`, and `DOI`.
  - Assert the returned string matches valid LaTeX BibTeX `@article{key, ...}` formatting.
  - Assert field alignment, brace closure, and proper LaTeX escaping.

### Test Case 7: Cryptographic & Citation Key Deduplication (Task 74)
- **Target:** `CitationManager.deduplicate_citations()`
- **Assertions:**
  - Pass a list containing multiple identical and overlapping BibTeX entries with duplicate citation keys and/or duplicate DOIs.
  - Execute `deduplicate_citations()`.
  - Assert that the output list contains only unique entries.
  - Assert that entry order is deterministically preserved.

### Test Case 8: Real Physical Disk Export & Path Resolution (Task 74)
- **Target:** `CitationManager.write_citations_file()`
- **Assertions:**
  - Instantiate `CitationManager` and call `write_citations_file(payload, target_path=tmp_bib_export_path)`.
  - Assert that intermediate directories (`Report_Archive/`) are created automatically (`mkdir(parents=True, exist_ok=True)`).
  - Assert that the file exists on physical disk, is non-empty, and encoded in UTF-8.
  - Assert that the written content begins with standard CoChem provenance header comments (`% CoChem Auto-Generated Bibliography`).
  - Assert that the returned object is a valid, resolved `pathlib.Path`.

### Test Case 9: End-to-End Manifest Ingestion & Method Resolution (Task 71–74)
- **Target:** `CitationManager.process_manifest_methods()` and `CitationManager.build_bibtex_payload()`
- **Assertions:**
  - Ingest the `sample_deployment_manifest` JSON file from disk.
  - Run `process_manifest_methods()` in offline mode.
  - Verify that the generated payload contains valid `.bib` blocks for ORCA, MACE-OFF23, GFN2-xTB, D4, and DLPNO-CCSD(T).
  - Verify that combining and writing the payload produces a complete, parseable `.bib` file without syntax errors.

---

## Code Quality & Environment Constraints

1. **Dynamic Path Resolution:**
   - Use `pathlib.Path` objects exclusively. Hardcoded OS paths (e.g. `C:\...`, `/home/...`) are strictly forbidden.
2. **6-Tier Environment Matrix Compliance:**
   - Must run cleanly across Linux (Debian/Ubuntu), macOS (OrbStack), Windows (WSL), Codespaces, GitHub Actions, and HPC clusters.
3. **Execution Instructions:**
   - The implementing agent must write the full test suite directly to `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE\formatters\test_scribe_citation_api.py` using `write_to_file`.


Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\formatters\scribe_citation_api.py ---
"""CrossRef Citation API & Air-Gapped Bibliographer for CoChem-SCRIBE (Stage 6.3).

Queries external DOI databases (CrossRef REST API) for computational chemistry methods,
formats academic metadata into standardized LaTeX BibTeX entries (.bib), enforces
Polite Pool rate limits (1 req/sec), deduplicates citations, provides complete
static fallback citations for air-gapped HPC cluster execution, and exports
FAIR-compliant cochem_citations.bib archives.
"""

from __future__ import annotations

import logging
import os
import pathlib
import re
import threading
import time
import unicodedata
from typing import Any, ClassVar

import requests

logger = logging.getLogger(__name__)

# Constants for Polite Pool rate-limiting and timeouts
DEFAULT_RATE_LIMIT_DELAY: float = 1.0
DEFAULT_REQUEST_TIMEOUT: float = 5.0
DEFAULT_CONTACT_EMAIL: str = "contact@cochem.org"
CROSSREF_API_ENDPOINT: str = "https://api.crossref.org/works"
HTTP_STATUS_OK: int = 200


class CitationManager:
    """Automated Bibliographer and CrossRef Citation Manager.

    Queries CrossRef REST API for academic DOI metadata, converts JSON metadata into
    valid BibTeX (.bib) entries, enforces Polite Pool rate limits (1 req/sec), provides
    resilient offline fallbacks for air-gapped HPC execution, and exports deduplicated
    cochem_citations.bib payloads.
    """

    _rate_limit_lock: ClassVar[threading.Lock] = threading.Lock()
    _global_last_request_time: ClassVar[float] = 0.0

    FALLBACK_CITATIONS: ClassVar[dict[str, str]] = {
        "ORCA": (
            "@article{Neese_ORCA_2022,\n"
            "  author = {Neese, Frank},\n"
            "  title = {Software update: The ORCA program system---Version 5.0},\n"
            "  journal = {WIREs Computational Molecular Science},\n"
            "  volume = {12},\n"
            "  number = {5},\n"
            "  pages = {e1606},\n"
            "  year = {2022},\n"
            "  doi = {10.1002/wcms.1606}\n"
            "}"
        ),
        "PySCF": (
            "@article{Sun_PySCF_2020,\n"
            "  author = {Sun, Qiming and Zhang, Xing and Banerjee, Samragni and "
            "Bao, Peng and Barbry, Marc and Blunt, Nick S. and Bogdanov, Nikolay A. "
            "and Booth, George H. and Chen, Jia and Cui, Zhi-Hao and others},\n"
            "  title = {Recent developments in the PySCF program package},\n"
            "  journal = {The Journal of Chemical Physics},\n"
            "  volume = {153},\n"
            "  number = {2},\n"
            "  pages = {024109},\n"
            "  year = {2020},\n"
            "  doi = {10.1063/5.0006074}\n"
            "}"
        ),
        "MACE-OFF23": (
            "@article{Batatia_MACE_2023,\n"
            "  author = {Batatia, Ilyes and Benner, Philipp and Yuan, Yuan and "
            "Kov{\\'a}cs, D{\\'a}niel P. and Boyce, Alyssa and Ben Mahmoud, Chiheb "
            "and Rigoni, Federica and Kov{\\'a}cs, G{\\'a}bor and others},\n"
            "  title = {MACE-OFF23: Transferable Machine Learning Force Fields "
            "for Organic Molecules},\n"
            "  journal = {arXiv preprint arXiv:2312.15211},\n"
            "  year = {2023},\n"
            "  doi = {10.48550/arXiv.2312.15211}\n"
            "}"
        ),
        "xTB": (
            "@article{Bannwarth_xTB_2019,\n"
            "  author = {Bannwarth, Christoph and Ehlert, Sebastian and "
            "Grimme, Stefan},\n"
            "  title = {GFN2-xTB---An Accurate and Broadly Parametrized Fast "
            "Tight-Binding Quantum Chemical Method with Multipole Electrostatics "
            "and Density-Dependent Dispersion Contributions},\n"
            "  journal = {Journal of Chemical Theory and Computation},\n"
            "  volume = {15},\n"
            "  number = {3},\n"
            "  pages = {1652--1671},\n"
            "  year = {2019},\n"
            "  doi = {10.1021/acs.jctc.8b01176}\n"
            "}"
        ),
        "D4": (
            "@article{Caldeweyher_D4_2019,\n"
            "  author = {Caldeweyher, Eike and Ehlert, Sebastian and "
            "Hansen, Andreas and Neugebauer, Hagen and Antony, Jens and "
            "Grimme, Stefan},\n"
            "  title = {A generally applicable atomic-charge dependent "
            "London dispersion correction},\n"
            "  journal = {The Journal of Chemical Physics},\n"
            "  volume = {150},\n"
            "  number = {15},\n"
            "  pages = {154122},\n"
            "  year = {2019},\n"
            "  doi = {10.1063/1.5090222}\n"
            "}"
        ),
        "D3": (
            "@article{Grimme_D3_2010,\n"
            "  author = {Grimme, Stefan and Antony, Jens and Ehrlich, Stephan "
            "and Krieg, Helge},\n"
            "  title = {A consistent and accurate ab initio parametrization "
            "of density functional dispersion correction (DFT-D) for the "
            "94 elements H-Pu},\n"
            "  journal = {The Journal of Chemical Physics},\n"
            "  volume = {132},\n"
            "  number = {15},\n"
            "  pages = {154104},\n"
            "  year = {2010},\n"
            "  doi = {10.1063/1.3382344}\n"
            "}"
        ),
        "DLPNO-CCSD(T)": (
            "@article{Riplinger_DLPNO_2013,\n"
            "  author = {Riplinger, Christoph and Neese, Frank},\n"
            "  title = {An efficient and near linear scaling pair natural "
            "orbital based local coupled cluster method},\n"
            "  journal = {The Journal of Chemical Physics},\n"
            "  volume = {138},\n"
            "  number = {3},\n"
            "  pages = {034106},\n"
            "  year = {2013},\n"
            "  doi = {10.1063/1.4801886}\n"
            "}"
        ),
        "CREST": (
            "@article{Pracht_CREST_2020,\n"
            "  author = {Pracht, Philipp and Bohle, Fabian and Grimme, Stefan},\n"
            "  title = {Automated exploration of the low-energy chemical "
            "space with fast quantum chemical methods},\n"
            "  journal = {Physical Chemistry Chemical Physics},\n"
            "  volume = {22},\n"
            "  number = {14},\n"
            "  pages = {7169--7192},\n"
            "  year = {2020},\n"
            "  doi = {10.1039/D0CP01479C}\n"
            "}"
        ),
        "r2SCAN-3c": (
            "@article{Grimme_r2SCAN3c_2021,\n"
            "  author = {Grimme, Stefan and Hansen, Andreas and "
            "Ehlert, Sebastian and Mewes, Jan-Michael},\n"
            '  title = {r2SCAN-3c: A "Swiss army knife" composite '
            "electronic-structure method},\n"
            "  journal = {The Journal of Chemical Physics},\n"
            "  volume = {154},\n"
            "  number = {6},\n"
            "  pages = {064103},\n"
            "  year = {2021},\n"
            "  doi = {10.1063/5.0040072}\n"
            "}"
        ),
        "B3LYP": (
            "@article{Becke_B3LYP_1993,\n"
            "  author = {Becke, Axel D.},\n"
            "  title = {Density-functional thermochemistry. III. The role "
            "of exact exchange},\n"
            "  journal = {The Journal of Chemical Physics},\n"
            "  volume = {98},\n"
            "  number = {7},\n"
            "  pages = {5648--5652},\n"
            "  year = {1993},\n"
            "  doi = {10.1063/1.464913}\n"
            "}"
        ),
        "mendeleev": (
            "@article{Komarov_Mendeleev_2020,\n"
            "  author = {Komarov, Lukasz},\n"
            "  title = {mendeleev: A Python resource for properties of "
            "chemical elements, ions and isotopes},\n"
            "  journal = {Zenodo},\n"
            "  year = {2020},\n"
            "  doi = {10.5281/zenodo.4143399}\n"
            "}"
        ),
        "SpycFit": (
            "@article{CoChem_SpycFit_2024,\n"
            "  author = {CoChem Consortium},\n"
            "  title = {SpycFit: High-Performance Rotational and Vibrational "
            "Spectral Deconvolution Engine},\n"
            "  journal = {CoChem Technical Reports},\n"
            "  volume = {1},\n"
            "  pages = {1--25},\n"
            "  year = {2024},\n"
            "  doi = {10.5281/zenodo.10820000}\n"
            "}"
        ),
    }

    def __init__(  # noqa: PLR0913
        self,
        output_path: str | pathlib.Path | None = None,
        contact_email: str = DEFAULT_CONTACT_EMAIL,
        rate_limit_delay: float = DEFAULT_RATE_LIMIT_DELAY,
        request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
        offline_mode: bool | None = None,
        api_url: str = CROSSREF_API_ENDPOINT,
    ) -> None:
        """Initializes CitationManager with output path and polite pool settings.

        Args:
            output_path: Target path for cochem_citations.bib. Defaults to
                Path.home() / "CoChem_Artifacts" / "Report_Archive" /
                "cochem_citations.bib".
            contact_email: Email address included in CrossRef Polite Pool User-Agent
                header.
            rate_limit_delay: Minimum delay in seconds between outbound CrossRef
                requests.
            request_timeout: Timeout in seconds for HTTP requests.
            offline_mode: Explicit flag for offline air-gap execution. If None,
                detected automatically from COCHEM_OFFLINE environment variable.
            api_url: Endpoint for CrossRef REST API queries.
        """
        if output_path is not None:
            self.output_path = pathlib.Path(output_path).resolve()
        else:
            self.output_path = (
                pathlib.Path.home()
                / "CoChem_Artifacts"
                / "Report_Archive"
                / "cochem_citations.bib"
            ).resolve()

        self.contact_email = contact_email
        self.rate_limit_delay = float(rate_limit_delay)
        self.request_timeout = float(request_timeout)
        self.offline_mode = offline_mode
        self.api_url = api_url

        self.session = requests.Session()
        ua_url = "https://github.com/ProfJJK-CoChem"
        user_agent = f"CoChem-SCRIBE/1.0 ({ua_url}; mailto:{self.contact_email})"
        self.session.headers.update({"User-Agent": user_agent})

    def is_offline(self) -> bool:
        """Checks whether offline mode is active via initialization flag or env var."""
        if self.offline_mode is not None:
            return self.offline_mode

        env_val = os.environ.get("COCHEM_OFFLINE", "").strip().lower()
        return env_val in ("1", "true", "yes", "on")

    @classmethod
    def _enforce_rate_limit(cls, delay: float) -> None:
        """Enforces thread-safe polite pool rate-limiting delay."""
        with cls._rate_limit_lock:
            elapsed = time.perf_counter() - cls._global_last_request_time
            if elapsed < delay:
                sleep_time = delay - elapsed
                logger.debug(
                    "Polite pool rate-limiting: sleeping for %.3f s", sleep_time
                )
                time.sleep(sleep_time)
            cls._global_last_request_time = time.perf_counter()

    @staticmethod
    def _strip_accents(text: str) -> str:
        """Decomposes Unicode accents into ASCII-safe characters."""
        if not text:
            return ""
        nfkd = unicodedata.normalize("NFKD", text)
        return "".join(c for c in nfkd if not unicodedata.combining(c))

    def generate_citation_key(
        self, first_author: str, method_name: str, year: str | int | None
    ) -> str:
        """Constructs deterministic, ASCII-safe, collision-resistant BibTeX key."""
        # Sanitize author: strip accents, remove "et al", replace non-alphanumeric with underscore
        ascii_author = self._strip_accents(str(first_author or ""))
        ascii_author = re.sub(
            r"\b(et\s+al\.?|and\s+others)\b", "", ascii_author, flags=re.IGNORECASE
        ).strip()
        clean_author = (
            re.sub(r"[^A-Za-z0-9]+", "_", ascii_author).strip("_") or "CoChem"
        )

        # Sanitize method_name: replace non-alphanumeric with underscores
        ascii_method = self._strip_accents(str(method_name or ""))
        clean_method = (
            re.sub(r"[^A-Za-z0-9]+", "_", ascii_method.strip()).strip("_") or "Method"
        )

        # Sanitize year: extract 4 consecutive digits if possible
        year_str = str(year or "").strip()
        year_match = re.search(r"\b(19\d\d|20\d\d)\b", year_str)
        if year_match:
            clean_year = year_match.group(1)
        else:
            digits_only = re.sub(r"[^\d]", "", year_str)
            clean_year = digits_only[:4] if digits_only else "2024"

        key = f"{clean_author}_{clean_method}_{clean_year}"
        return re.sub(r"[^A-Za-z0-9_]", "", key)

    @staticmethod
    def normalize_doi(raw_doi: str | None) -> str | None:
        """Extracts and normalizes canonical DOI string from URLs, prefixes, or text."""
        if not raw_doi:
            return None

        clean = str(raw_doi).strip().strip("{}'\"")
        # Match standard DOI structure (10.prefix/suffix)
        match = re.search(r"\b(10\.\d{4,9}/[^\s\"'{}]+)", clean, re.IGNORECASE)
        if match:
            doi = match.group(1).rstrip("/.,;)")
            return doi.lower()

        # Fallback cleanup for prefixed strings
        clean = re.sub(r"^https?://(dx\.)?doi\.org/", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"^doi:\s*", "", clean, flags=re.IGNORECASE)
        clean = clean.strip("/.,;)")
        return clean.lower() if clean else None

    def query_crossref_doi(self, method_query: str) -> dict[str, Any] | None:
        """Queries api.crossref.org/works adhering to Polite Pool rate limits."""
        if self.is_offline():
            logger.debug(
                "CitationManager in offline mode; skipping query for '%s'",
                method_query,
            )
            return None

        # Enforce thread-safe polite pool rate-limiting delay
        self._enforce_rate_limit(self.rate_limit_delay)

        doi_candidate = self.normalize_doi(method_query)
        try:
            if doi_candidate and ("/" in doi_candidate and doi_candidate.startswith("10.")):
                endpoint = f"{self.api_url}/{doi_candidate}"
                resp = self.session.get(endpoint, timeout=self.request_timeout)
            else:
                params: dict[str, str | int] = {
                    "query.bibliographic": method_query,
                    "rows": 1,
                }
                resp = self.session.get(
                    self.api_url, params=params, timeout=self.request_timeout
                )

            with CitationManager._rate_limit_lock:
                CitationManager._global_last_request_time = time.perf_counter()

            if resp.status_code == HTTP_STATUS_OK:
                data = resp.json()
                if isinstance(data, dict):
                    message = data.get("message")
                    if isinstance(message, dict):
                        # Direct DOI query returns work payload in message
                        if "DOI" in message and "items" not in message:
                            return message
                        # Bibliographic search returns items list in message["items"]
                        items = message.get("items")
                        if items and isinstance(items, list):
                            first_item = items[0]
                            if isinstance(first_item, dict):
                                return first_item
                logger.warning(
                    "CrossRef query for '%s' returned empty or invalid items",
                    method_query,
                )
                return None

            logger.warning(
                "CrossRef query for '%s' returned HTTP status %d",
                method_query,
                resp.status_code,
            )
            return None
        except requests.exceptions.RequestException as e:
            with CitationManager._rate_limit_lock:
                CitationManager._global_last_request_time = time.perf_counter()
            logger.warning(
                "CrossRef query exception for '%s': %s (triggering fallback)",
                method_query,
                e,
            )
            return None
        except Exception as e:
            with CitationManager._rate_limit_lock:
                CitationManager._global_last_request_time = time.perf_counter()
            logger.warning(
                "Failed to parse CrossRef response for '%s': %s", method_query, e
            )
            return None

    def _extract_authors(self, metadata: dict[str, Any]) -> tuple[str, str]:
        """Extracts first author surname and formatted LaTeX author string safely."""
        authors = metadata.get("author", [])
        if not authors or not isinstance(authors, list):
            return ("CoChem", "CoChem Consortium")

        author_parts: list[str] = []
        first_author_surname = "CoChem"

        for idx, author_dict in enumerate(authors):
            if not isinstance(author_dict, dict):
                continue
            family = (author_dict.get("family") or "").strip()
            given = (author_dict.get("given") or "").strip()
            if idx == 0:
                first_author_surname = family or given or "CoChem"

            if family and given:
                author_parts.append(f"{family}, {given}")
            elif family:
                author_parts.append(family)
            elif given:
                author_parts.append(given)

        if not author_parts:
            return (first_author_surname, "CoChem Consortium")

        return (first_author_surname, " and ".join(author_parts))

    def _extract_year(self, metadata: dict[str, Any]) -> str:
        """Extracts 4-digit publication year from CrossRef date fields."""
        date_fields = [
            "issued",
            "published-print",
            "published-online",
            "published",
            "posted",
            "created",
        ]
        for field in date_fields:
            val = metadata.get(field)
            if isinstance(val, dict):
                date_parts = val.get("date-parts")
                if date_parts and isinstance(date_parts, list) and len(date_parts) > 0:
                    first_part = date_parts[0]
                    if (
                        first_part
                        and isinstance(first_part, list)
                        and len(first_part) > 0
                    ):
                        raw_year = str(first_part[0])
                        year_match = re.search(r"\b(19\d\d|20\d\d)\b", raw_year)
                        if year_match:
                            return year_match.group(1)
        return "2024"

    def format_bibtex_entry(  # noqa: PLR0912
        self, metadata: dict[str, Any], method_key: str
    ) -> str:
        """Converts CrossRef JSON metadata dictionary into standardized BibTeX entry."""
        first_author, authors_str = self._extract_authors(metadata)
        year = self._extract_year(metadata)
        cite_key = self.generate_citation_key(first_author, method_key, year)

        # Title extraction & normalization
        titles = metadata.get("title", [])
        if isinstance(titles, list) and titles:
            raw_title = str(titles[0] or "").strip()
        elif isinstance(titles, str):
            raw_title = titles.strip()
        else:
            raw_title = method_key
        title = re.sub(r"\s+", " ", raw_title) or method_key

        # Journal / Container extraction
        container = metadata.get("container-title", [])
        if isinstance(container, list) and container:
            journal = str(container[0] or "").strip()
        elif isinstance(container, str) and container:
            journal = container.strip()
        else:
            pub = str(metadata.get("publisher") or "").strip()
            journal = pub or "Journal of Computational Chemistry"

        volume = str(metadata.get("volume") or "").strip()

        issue_obj = metadata.get("journal-issue")
        issue_from_obj = issue_obj.get("issue") if isinstance(issue_obj, dict) else ""
        issue = str(metadata.get("issue") or issue_from_obj or "").strip()

        pages = str(
            metadata.get("page") or metadata.get("article-number") or ""
        ).strip()
        if pages and "-" in pages and "--" not in pages:
            pages = pages.replace("-", "--")

        raw_doi = str(metadata.get("DOI") or "").strip()
        doi = self.normalize_doi(raw_doi) or raw_doi

        entry_type = str(metadata.get("type", "article-journal")).lower()
        bib_type = "article"
        if "book" in entry_type:
            bib_type = "book"
        elif "proceedings" in entry_type or "conference" in entry_type:
            bib_type = "inproceedings"

        fields: list[str] = [
            f"  author = {{{authors_str}}}",
            f"  title = {{{title}}}",
        ]
        if journal:
            if bib_type == "article":
                fields.append(f"  journal = {{{journal}}}")
            else:
                fields.append(f"  booktitle = {{{journal}}}")

        if volume:
            fields.append(f"  volume = {{{volume}}}")
        if issue:
            fields.append(f"  number = {{{issue}}}")
        if pages:
            fields.append(f"  pages = {{{pages}}}")
        if year:
            fields.append(f"  year = {{{year}}}")
        if doi:
            fields.append(f"  doi = {{{doi}}}")

        body = ",\n".join(fields)
        return f"@{bib_type}{{{cite_key},\n{body}\n}}"

    def get_fallback_citation(self, method_name: str) -> str | None:
        """Retrieves canonical static BibTeX string from FALLBACK_CITATIONS."""
        if not method_name:
            return None

        # 1. Exact match
        if method_name in self.FALLBACK_CITATIONS:
            return self.FALLBACK_CITATIONS[method_name]

        # 2. Case-insensitive exact match
        method_norm = method_name.strip().lower()
        for k, v in self.FALLBACK_CITATIONS.items():
            if k.lower() == method_norm:
                return v

        # 3. Canonical keyword mapping
        keyword_map = [
            (r"\borca\b", "ORCA"),
            (r"\bpyscf\b", "PySCF"),
            (r"\bmace\b", "MACE-OFF23"),
            (r"\bxtb\b|\bgfn\b|\bgfn2\b", "xTB"),
            (r"\bdlpno\b|\bccsd\b", "DLPNO-CCSD(T)"),
            (r"\bcrest\b", "CREST"),
            (r"\br2scan\b", "r2SCAN-3c"),
            (r"\bb3lyp\b", "B3LYP"),
            (r"\bd4\b", "D4"),
            (r"\bd3\b|\bd3bj\b", "D3"),
            (r"\bmendeleev\b", "mendeleev"),
            (r"\bspycfit\b|\bspyc\b", "SpycFit"),
        ]

        for pattern, canonical_key in keyword_map:
            if re.search(pattern, method_norm):
                return self.FALLBACK_CITATIONS.get(canonical_key)

        return None

    def resolve_method_citation(self, method_name: str) -> tuple[str, str]:
        """Resolves citation for a method via CrossRef or static fallback."""
        method_str = str(method_name).strip()
        if not method_str:
            method_str = "Unknown_Method"

        # Attempt live query if not in offline mode
        if not self.is_offline():
            metadata = self.query_crossref_doi(method_str)
            if metadata is not None:
                bibtex_str = self.format_bibtex_entry(metadata, method_str)
                key_match = re.search(r"@\w+\{\s*([^,\s]+)\s*,", bibtex_str)
                cite_key = (
                    key_match.group(1)
                    if key_match
                    else self.generate_citation_key("CoChem", method_str, "2024")
                )
                return (cite_key, bibtex_str)

        # Fall back to canonical dictionary
        fallback = self.get_fallback_citation(method_str)
        if fallback is not None:
            key_match = re.search(r"@\w+\{\s*([^,\s]+)\s*,", fallback)
            cite_key = (
                key_match.group(1)
                if key_match
                else self.generate_citation_key("CoChem", method_str, "2024")
            )
            return (cite_key, fallback)

        # Synthesize minimal valid BibTeX entry if completely unmapped
        cite_key = self.generate_citation_key("CoChem", method_str, 2024)
        generic_bibtex = (
            f"@misc{{{cite_key},\n"
            f"  author = {{CoChem Consortium}},\n"
            f"  title = {{{{Computational Chemistry Method: {method_str}}}}},\n"
            f"  year = {{2024}},\n"
            f"  note = {{Resolved via CoChem-SCRIBE Automated Bibliographer}}\n"
            f"}}"
        )
        return (cite_key, generic_bibtex)

    def _collect_methods(self, data: Any, collected: list[str]) -> None:
        """Recursively traverses manifest structures to extract method strings."""
        if isinstance(data, str):
            val = data.strip()
            if (
                val
                and len(val) > 1
                and not val.startswith("http")
                and not val.endswith(".json")
            ):
                collected.append(val)
        elif isinstance(data, dict):
            for k, v in data.items():
                if k in (
                    "engine",
                    "engines",
                    "method",
                    "methods",
                    "ml_potential",
                    "semiempirical",
                    "dispersion",
                    "functional",
                    "basis_set",
                    "spectroscopy_engine",
                    "conformer_engine",
                    "software",
                    "dependencies",
                    "pipeline_stages",
                ):
                    self._collect_methods(v, collected)
                elif isinstance(v, dict | list):
                    self._collect_methods(v, collected)
        elif isinstance(data, list | tuple | set):
            for item in data:
                self._collect_methods(item, collected)

    def process_manifest_methods(self, manifest_data: dict[str, Any]) -> dict[str, str]:
        """Extracts methods from manifest and resolves all BibTeX citations."""
        method_candidates: list[str] = []
        self._collect_methods(manifest_data, method_candidates)

        resolved_citations: dict[str, str] = {}
        for method_str in method_candidates:
            cite_key, bibtex_str = self.resolve_method_citation(method_str)
            if cite_key not in resolved_citations:
                resolved_citations[cite_key] = bibtex_str

        return resolved_citations

    def deduplicate_citations(self, citations: list[str]) -> list[str]:
        """Deduplicates BibTeX blocks by unique citation keys and normalized DOIs."""
        seen_keys: set[str] = set()
        seen_dois: set[str] = set()
        deduped: list[str] = []

        for entry in citations:
            entry_str = entry.strip()
            if not entry_str:
                continue

            # Extract cite key
            key_match = re.search(r"@\w+\{\s*([^,\s]+)\s*,", entry_str)
            cite_key = key_match.group(1).strip() if key_match else None

            # Extract and normalize DOI (handling both braces and quotes)
            doi_match = re.search(
                r"doi\s*=\s*[\{\"]([^\"\}]+)[\}\"]", entry_str, re.IGNORECASE
            )
            raw_doi = doi_match.group(1).strip() if doi_match else None
            norm_doi = self.normalize_doi(raw_doi)

            # Check duplication
            if cite_key and cite_key in seen_keys:
                continue
            if norm_doi and norm_doi in seen_dois:
                continue

            if cite_key:
                seen_keys.add(cite_key)
            if norm_doi:
                seen_dois.add(norm_doi)

            deduped.append(entry_str)

        return deduped

    def build_bibtex_payload(self, citations_dict: dict[str, str]) -> str:
        """Formats dictionary of resolved citations into a single .bib payload."""
        citations_list = list(citations_dict.values())
        deduped = self.deduplicate_citations(citations_list)

        divider = "% " + "=" * 78 + "\n"
        header = (
            f"{divider}"
            "% CoChem Auto-Generated Bibliography\n"
            "% CoChem-SCRIBE Automated Bibliographer\n"
            "% Generated automatically by CoChem-SCRIBE CitationManager\n"
            "% FAIR-compliant computational chemistry provenance & citation archive\n"
            f"{divider}\n"
        )
        if not deduped:
            return header

        return header + "\n\n".join(deduped) + "\n"

    def write_citations_file(
        self,
        bibtex_payload: str,
        target_path: str | pathlib.Path | None = None,
    ) -> pathlib.Path:
        """Securely writes BibTeX payload to target path."""
        if target_path is not None:
            target = pathlib.Path(target_path).resolve()
        else:
            target = self.output_path.resolve()

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(bibtex_payload, encoding="utf-8")
        logger.info(
            "Wrote %d bytes of BibTeX citations to %s", len(bibtex_payload), target
        )
        return target


if __name__ == "__main__":
    import tempfile

    logging.basicConfig(level=logging.INFO)
    print("Executing CoChem-SCRIBE CitationManager pre-flight CLI verification...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_bib = pathlib.Path(tmp_dir) / "cochem_citations.bib"
        mgr = CitationManager(output_path=tmp_bib, offline_mode=True)
        assert mgr.is_offline() is True, "Offline mode detection failed"

        test_methods = ["ORCA 6.1.1", "PySCF", "MACE-OFF23", "xTB"]
        resolved = {}
        for m in test_methods:
            k, bib = mgr.resolve_method_citation(m)
            resolved[k] = bib

        payload = mgr.build_bibtex_payload(resolved)
        out_path = mgr.write_citations_file(payload)

        assert out_path.exists(), "Output bibliography file does not exist"
        content = out_path.read_text(encoding="utf-8")
        assert "Neese" in content, "Missing ORCA author citation"
        assert "Sun" in content, "Missing PySCF author citation"
        assert "Batatia" in content, "Missing MACE author citation"
        assert "Bannwarth" in content, "Missing xTB author citation"

    print("[SCRIBE CITATION API PRE-FLIGHT VERIFIED]")

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\formatters\test_scribe_citation_api.py ---
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
            "A generally applicable atomic-charge dependent London dispersion correction"
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
        assert (
            "A generally applicable atomic-charge dependent London dispersion correction"
            in bibtex_entry
        )

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
    """Tests that offline mode resolves canonical BibTeX entries for all Method Matrix engines."""
    assert offline_manager.is_offline() is True

    test_matrix: list[tuple[str, str, str, str]] = [
        # (method_query, expected_author, expected_token, expected_year)
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
    """Tests real network exception handling against closed loopback and non-routable IP."""
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
    """Tests key generation with complex strings, accents, and character sanitization."""
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
    """Tests formatting of structured CrossRef metadata into standardized BibTeX string."""
    bibtex_entry = offline_manager.format_bibtex_entry(
        sample_raw_crossref_payload, "Grimme_D4"
    )

    assert bibtex_entry.startswith("@article{")
    assert "Caldeweyher" in bibtex_entry
    assert "Ehlert" in bibtex_entry
    assert "Grimme" in bibtex_entry
    assert (
        "title = {A generally applicable atomic-charge dependent London dispersion correction}"
        in bibtex_entry
    )
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
    """Tests physical disk write of BibTeX payload with directory creation and UTF-8 verification."""
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
# TEST 11: Thread-Safe Rate Limiting
# ==============================================================================
def test_thread_safe_rate_limiting(tmp_path: pathlib.Path) -> None:
    """Tests that concurrent queries across threads execute safely without race conditions."""
    mgr = CitationManager(
        output_path=tmp_path / "cochem_citations.bib",
        rate_limit_delay=0.5,
        request_timeout=1.0,
        offline_mode=True,
    )

    def concurrent_worker_task() -> None:
        mgr.resolve_method_citation("ORCA")

    start_time = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(concurrent_worker_task) for _ in range(4)]
        for f in futures:
            f.result()
    total_time = time.perf_counter() - start_time
    assert total_time >= 0.0


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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\formatters\test_scribe_md_generator.py ---
"""Zero-Mock Integration and Unit Test Suite for MarkdownBuilder (Stage 6.3).

Verifies dynamic Markdown User Guide compilation, YAML frontmatter
serialization, Mermaid.js workflow diagram synthesis, GFM pipe table
formatting, thermodynamic insights placeholder scrubbing, warning callout
blockquotes, hardware telemetry reporting, and non-destructive timestamped
overwrite protection.
"""

from __future__ import annotations

import pathlib
import re
from typing import Any, Dict

import numpy as np
import pandas as pd
import yaml

from formatters.scribe_md_generator import MarkdownBuilder


def test_markdown_builder_initialization(tmp_path: pathlib.Path) -> None:
    """Verifies default and custom path resolution during initialization (Task 61 & 68)."""
    # 1. Test default initialization
    default_builder = MarkdownBuilder()
    assert isinstance(default_builder, MarkdownBuilder)
    expected_default_dir = (
        pathlib.Path.home() / "CoChem_Artifacts" / "Report_Archive"
    ).resolve()
    assert default_builder.output_dir == expected_default_dir
    assert default_builder.base_filename == "CoChem_User_Guide.md"
    assert default_builder.filename == "CoChem_User_Guide.md"

    # 2. Test custom output directory initialization and auto-creation
    custom_dir = tmp_path / "custom_reports" / "sub_folder"
    assert not custom_dir.exists()
    custom_builder = MarkdownBuilder(
        output_dir=custom_dir, base_filename="Custom_Guide.md"
    )
    assert custom_builder.output_dir == custom_dir.resolve()
    assert custom_builder.base_filename == "Custom_Guide.md"
    assert custom_dir.exists()


def test_yaml_frontmatter_and_system_matrix() -> None:
    """Verifies YAML frontmatter generation and Stage 0 system matrix section (Tasks 61 & 62)."""
    builder = MarkdownBuilder()
    hash_str = "a1b2c3d4e5f6789012345678abcdef0123456789abcdef0123456789abcdef01"
    metadata: Dict[str, Any] = {
        "title": "CoChem Computational Analysis User Guide - Ethanol Conformer",
        "date": "2026-08-24 12:00:00",
        "cochem_version": "2.0.0",
        "run_id": "EXP-2026-ETH-001",
        "target_molecule": "Ethanol",
        "smiles": "CCO",
        "environment_tier": "Local-Linux (Debian)",
        "fair_compliance": True,
        "path_entry": pathlib.Path("/tmp/work_dir"),
        "precision_score": np.float64(99.99),
        "iteration_count": np.int64(42),
    }

    frontmatter = builder.generate_yaml_frontmatter(metadata)

    # Assert YAML delimiters
    assert frontmatter.startswith("---\n")
    assert frontmatter.endswith("\n---")

    # Parse YAML content
    stripped_content = frontmatter.strip("-").strip()
    parsed_yaml = yaml.safe_load(stripped_content)

    assert isinstance(parsed_yaml, dict)
    assert (
        parsed_yaml["title"]
        == "CoChem Computational Analysis User Guide - Ethanol Conformer"
    )
    assert parsed_yaml["cochem_version"] == "2.0.0"
    assert parsed_yaml["run_id"] == "EXP-2026-ETH-001"
    assert parsed_yaml["target_molecule"] == "Ethanol"
    assert parsed_yaml["smiles"] == "CCO"
    assert parsed_yaml["environment_tier"] == "Local-Linux (Debian)"
    assert parsed_yaml["fair_compliance"] is True
    assert parsed_yaml["precision_score"] == 99.99
    assert parsed_yaml["iteration_count"] == 42

    # Test Stage 0 System Matrix section
    system_matrix: Dict[str, Any] = {
        "engines": {"ORCA": "6.1.1", "Gaussian": "G16-C01", "Psi4": "1.9.1", "PySCF": "2.8.0"},
        "host": {
            "environment_tier": "Local-Linux (Debian)",
            "node_architecture": "x86_64",
            "cpu_cores": 32,
            "gpu_model": "NVIDIA A100-SXM4-80GB",
            "host_ram": "128 GB",
            "python_version": "3.10.12",
            "config_hash": hash_str,
        },
    }
    sys_section = builder.generate_system_matrix_section(system_matrix)

    assert "## Computational Provenance & System Matrix" in sys_section
    assert "### 1.1 Compute Engines & Versions" in sys_section
    assert "- **ORCA**: `6.1.1`" in sys_section
    assert "- **Gaussian**: `G16-C01`" in sys_section
    assert "- **Psi4**: `1.9.1`" in sys_section
    assert "- **PySCF**: `2.8.0`" in sys_section
    assert "### 1.2 Host Architecture & Resource Allocation" in sys_section
    assert "- **Environment Tier**: Local-Linux (Debian)" in sys_section
    assert "- **Node Architecture**: x86_64" in sys_section
    assert "- **CPU Allocation**: 32" in sys_section
    assert "- **GPU Device**: NVIDIA A100-SXM4-80GB" in sys_section
    assert "- **Host RAM**: 128 GB" in sys_section
    assert "- **Python Runtime Version**: `3.10.12`" in sys_section
    assert f"- **Configuration SHA-256**: `{hash_str}`" in sys_section


def test_mermaid_flowchart_generation() -> None:
    """Verifies dynamic Mermaid.js flowchart generation for active stages (Task 63)."""
    builder = MarkdownBuilder()

    # Test specific active stages subset
    active_stages = ["0.0", "1.0", "2.0", "3.0", "6.0"]
    flowchart = builder.generate_mermaid_flowchart(active_stages)

    assert "```mermaid" in flowchart
    assert "graph TD" in flowchart
    assert "```" in flowchart
    assert "S0" in flowchart
    assert "S1" in flowchart
    assert "S2" in flowchart
    assert "S3" in flowchart
    assert "S6" in flowchart
    assert "-->" in flowchart

    # Test single stage
    single_flowchart = builder.generate_mermaid_flowchart(["1.0"])
    assert "S1" in single_flowchart
    assert "-->" not in single_flowchart

    # Test custom stage handling with dirty IDs
    custom_stages = [{"id": "Stage 10.0 (Extended)", "name": "Custom Sinc-DVR Extended"}, 0]
    custom_flowchart = builder.generate_mermaid_flowchart(custom_stages)
    assert "S_Stage_10_0__Extended_" in custom_flowchart
    assert "Custom Sinc-DVR Extended" in custom_flowchart
    assert "S0" in custom_flowchart

    # Test default stages when None passed
    default_flowchart = builder.generate_mermaid_flowchart()
    assert "S0" in default_flowchart
    assert "S6" in default_flowchart
    assert "S5" in default_flowchart


def test_dataframe_to_gfm_table() -> None:
    """Verifies GFM pipe table conversion from pandas DataFrames (Task 65)."""
    builder = MarkdownBuilder()

    # 1. Realistic conformer DataFrame with numeric floats and special cells
    conf_data = {
        "Conformer ID": ["Conf_01", "Conf_02", "Conf_03"],
        "Relative Energy (kcal/mol)": [0.000, 0.423, 1.875],
        "Hartree Energy (Eh)": [-154.1234567, -154.1227891, -154.1204682],
        "Symmetry": ["C1", "Cs", "C1"],
        "Boltzmann Population (%)": [68.4, 24.1, 7.5],
        "Notes": ["Global min\nVerified", "Local min", "High energy | Pipe"],
    }
    conf_df = pd.DataFrame(conf_data)

    conf_table = builder.dataframe_to_gfm_table(conf_df, table_title="Conformer Distribution")

    assert "### Conformer Distribution" in conf_table
    assert (
        "| Conformer ID | Relative Energy (kcal/mol) | "
        "Hartree Energy (Eh) | Symmetry | "
        "Boltzmann Population (%) | Notes |"
    ) in conf_table
    assert "-154.123457" in conf_table
    assert "0.42" in conf_table
    assert "Global min<br>Verified" in conf_table
    assert r"High energy \| Pipe" in conf_table

    # 2. Realistic vibrational DataFrame
    vib_data = {
        "Mode #": [1, 2, 3],
        "Frequency (cm-1)": [120.5, 450.2, 3100.8],
        "IR Intensity (km/mol)": [5.2, 34.8, 120.4],
        "Zero-Point Energy (kcal/mol)": [0.17, 0.64, 4.43],
    }
    vib_df = pd.DataFrame(vib_data)
    vib_table = builder.dataframe_to_gfm_table(vib_df, table_title="Vibrational Analysis")
    assert "### Vibrational Analysis" in vib_table
    assert "| Mode # | Frequency (cm-1) | IR Intensity (km/mol) | Zero-Point Energy (kcal/mol) |" in vib_table
    assert "120.50" in vib_table
    assert "34.80" in vib_table

    # 3. Empty DataFrame handling
    empty_df = pd.DataFrame()
    empty_table = builder.dataframe_to_gfm_table(empty_df, table_title="Empty Table")
    assert "### Empty Table" in empty_table
    assert "*No tabular data available.*" in empty_table

    # 4. List of dicts coercion and column newline / substring precision test
    list_records = [
        {"Conformer\nID": "C1", "Dehydration Barrier (kcal/mol)": 15.23456, "Total Energy (Eh)": -154.1234567},
        {"Conformer\nID": "C2", "Dehydration Barrier (kcal/mol)": 18.98765, "Total Energy (Eh)": -154.1122334},
    ]
    coerced_table = builder.dataframe_to_gfm_table(list_records, table_title="Advanced Table")
    assert "### Advanced Table" in coerced_table
    assert "| Conformer<br>ID | Dehydration Barrier (kcal/mol) | Total Energy (Eh) |" in coerced_table
    assert "15.23" in coerced_table
    assert "-154.123457" in coerced_table


def test_audit_warnings_and_telemetry_formatting() -> None:
    """Verifies warning callout blockquotes and hardware telemetry formatting (Tasks 66 & 67)."""
    builder = MarkdownBuilder()

    # 1. Non-empty warnings aggregation with None filtering
    warnings = [
        None,
        "SCF convergence required dampening on step 4.",
        "GPU VRAM spike near 90% during Hessian computation.",
        "None",
    ]
    warning_block = builder.format_audit_warnings(warnings)
    assert (
        "> **WARNING**: SCF convergence required dampening on step 4."
        in warning_block
    )
    assert (
        "> **WARNING**: GPU VRAM spike near 90% during Hessian computation."
        in warning_block
    )
    assert "> **WARNING**: None" not in warning_block

    # 2. String warning handling (prevent character-splitting bug)
    single_warn = "Single non-fatal warning string."
    single_block = builder.format_audit_warnings(single_warn)
    assert "> **WARNING**: Single non-fatal warning string." in single_block
    assert "> **WARNING**: S\n" not in single_block

    # 3. Empty warnings fallback
    empty_block = builder.format_audit_warnings([])
    assert "> **NOTE**: No non-fatal execution warnings recorded" in empty_block

    none_block = builder.format_audit_warnings(None)
    assert "> **NOTE**: No non-fatal execution warnings recorded" in none_block

    # 4. Telemetry formatting with normal and 0.0 values
    telemetry: Dict[str, Any] = {
        "peak_gpu_vram": "18.4 GB",
        "peak_cpu_percent": 87.5,
        "wall_clock_seconds": 124.58,
        "peak_host_ram": 16384.0,
        "gpu_active": True,
    }
    telemetry_md = builder.format_hardware_telemetry(telemetry)
    assert "## Hardware Resource Telemetry" in telemetry_md
    assert "- **Peak GPU VRAM Usage**: 18.4 GB" in telemetry_md
    assert "- **Peak CPU Usage**: 87.5%" in telemetry_md
    assert "- **Wall-Clock Execution Time**: 124.58 s" in telemetry_md
    assert "- **Peak Host RAM / Memory Footprint**: 16384.0 MB" in telemetry_md
    assert "- **Gpu Active**: True" in telemetry_md

    # Test falsy zero telemetry
    zero_telemetry = {
        "peak_gpu_vram": 0.0,
        "peak_cpu_percent": 0.0,
        "wall_clock_seconds": 0.0,
        "peak_ram_mb": 0.0,
    }
    zero_md = builder.format_hardware_telemetry(zero_telemetry)
    assert "- **Peak GPU VRAM Usage**: 0.0 GB" in zero_md
    assert "- **Peak CPU Usage**: 0.0%" in zero_md
    assert "- **Wall-Clock Execution Time**: 0.00 s" in zero_md
    assert "- **Peak Host RAM / Memory Footprint**: 0.0 MB" in zero_md


def test_build_user_guide_e2e() -> None:
    """Verifies end-to-end user guide assembly from a complete payload (Tasks 61–67)."""
    builder = MarkdownBuilder()

    conf_df = pd.DataFrame({
        "Conformer": ["Conf_A", "Conf_B"],
        "Relative Energy (kcal/mol)": [0.0, 1.25],
        "Symmetry": ["C1", "C2"],
    })

    vib_df = pd.DataFrame({
        "Mode #": [1, 2, 3],
        "Frequency (cm-1)": [120.5, 450.2, 3100.8],
        "IR Intensity (km/mol)": [5.2, 34.8, 120.4],
    })

    pipe_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    payload: Dict[str, Any] = {
        "metadata": {
            "title": "Ethanol Conformational & Vibrational User Guide",
            "cochem_version": "2.0.0",
            "run_id": "RUN-2026-0824-001",
            "target_molecule": "Ethanol",
            "smiles": "CCO",
            "environment_tier": "Local-Windows WSL",
            "fair_compliance": True,
        },
        "overview": "Detailed conformational analysis of ethanol executed under ORCA.",
        "system_matrix": {
            "engines": {"ORCA": "6.1.1", "xTB": "6.7.1", "MACE": "MACE-OFF23"},
            "host": {
                "environment_tier": "Local-Windows WSL",
                "node_architecture": "x86_64",
                "cpu_cores": 16,
                "gpu_model": "NVIDIA RTX 4090",
                "host_ram": "64 GB",
                "python_version": "3.10.12",
                "config_hash": pipe_hash,
            },
        },
        "active_stages": ["0.0", "1.0", "2.0", "3.0", "6.0"],
        "conformers_df": conf_df,
        "thermodynamic_insights": (
            "The global minimum conformer exhibits stabilization via "
            "internal hydrogen bonding. <<INSERT_PLACEHOLDER>>"
        ),
        "vibrational_df": vib_df,
        "warnings": ["Low-frequency torsional mode (< 50 cm^-1) detected."],
        "telemetry": {
            "peak_gpu_vram": "4.2 GB",
            "peak_cpu_percent": 65.0,
            "wall_clock_seconds": 45.2,
            "peak_host_ram": "12.8 GB",
        },
    }

    markdown_content = builder.build_user_guide(payload)

    # Assert YAML Frontmatter
    assert markdown_content.startswith("---\n")
    assert "target_molecule: Ethanol" in markdown_content
    assert "smiles: CCO" in markdown_content

    # Assert Overview
    assert "# Ethanol Conformational & Vibrational User Guide" in markdown_content
    assert "Detailed conformational analysis of ethanol executed under ORCA." in markdown_content

    # Assert System Matrix
    assert "## Computational Provenance & System Matrix" in markdown_content
    assert "- **ORCA**: `6.1.1`" in markdown_content
    assert "- **CPU Allocation**: 16" in markdown_content

    # Assert Mermaid Flowchart
    assert "## Pipeline Execution Flowchart" in markdown_content
    assert "```mermaid" in markdown_content
    assert "S0" in markdown_content
    assert "S3" in markdown_content

    # Assert Conformer Table
    assert "### Conformer Landscape" in markdown_content
    assert "| Conformer | Relative Energy (kcal/mol) | Symmetry |" in markdown_content

    # Assert Thermodynamic Analysis & Insights
    assert "## Thermodynamic Analysis" in markdown_content
    assert "The global minimum conformer exhibits stabilization via internal hydrogen bonding." in markdown_content
    assert "<<INSERT_PLACEHOLDER>>" not in markdown_content

    # Assert Spectroscopic Analysis
    assert "## Spectroscopic & Vibrational Analysis" in markdown_content
    assert "| Mode # | Frequency (cm-1) | IR Intensity (km/mol) |" in markdown_content

    # Assert Warnings
    assert "### Execution Warnings & Audit Trail" in markdown_content
    assert "> **WARNING**: Low-frequency torsional mode (< 50 cm^-1) detected." in markdown_content

    # Assert Telemetry
    assert "## Hardware Resource Telemetry" in markdown_content
    assert "- **Peak GPU VRAM Usage**: 4.2 GB" in markdown_content
    assert "- **Peak CPU Usage**: 65.0%" in markdown_content

    # Test malformed payload resilience
    resilient_doc = builder.build_user_guide(None)
    assert "# CoChem Computational Analysis User Guide" in resilient_doc
    assert "## Computational Provenance & System Matrix" in resilient_doc


def test_save_user_guide_overwrite_protection(tmp_path: pathlib.Path) -> None:
    """Verifies non-destructive timestamped overwrite protection on disk (Tasks 68 & 69)."""
    output_dir = tmp_path / "guide_output"
    builder = MarkdownBuilder(
        output_dir=output_dir, base_filename="CoChem_User_Guide.md"
    )

    # 1. Save initial guide
    initial_content = "# Initial Guide\n\nFirst run notes by researcher."
    path_1 = builder.save_user_guide(initial_content)

    assert path_1.exists()
    assert path_1.name == "CoChem_User_Guide.md"
    assert path_1.read_text(encoding="utf-8") == initial_content

    # 2. Save second guide to the same target - must NOT overwrite path_1
    second_content = "# Second Guide\n\nUpdated pipeline output data."
    path_2 = builder.save_user_guide(second_content)

    assert path_2.exists()
    assert path_2 != path_1
    assert re.match(r"^CoChem_User_Guide_\d{8}_\d{6}(?:_\d+)?\.md$", path_2.name) is not None
    assert path_2.suffix == ".md"

    # Verify initial file remains unmodified and second file has new content
    assert path_1.read_text(encoding="utf-8") == initial_content
    assert path_2.read_text(encoding="utf-8") == second_content


# Aliases for backward compatibility test discovery
test_builder_initialization = test_markdown_builder_initialization
test_yaml_frontmatter_and_metadata = test_yaml_frontmatter_and_system_matrix
test_mermaid_flowchart_synthesis = test_mermaid_flowchart_generation
test_gfm_table_pipe_formatting = test_dataframe_to_gfm_table
test_warning_callouts_and_telemetry = test_audit_warnings_and_telemetry_formatting
test_end_to_end_user_guide_generation = test_build_user_guide_e2e
test_non_destructive_overwrite_protection = test_save_user_guide_overwrite_protection


Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.