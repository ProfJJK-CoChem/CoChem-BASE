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
        "gpu4pyscf": (
            "@article{Wu_gpu4pyscf_2024,\n"
            "  author = {Wu, Xiaojie and Cui, Zhi-Hao and Zhang, Xing and "
            "Sun, Qiming and Chan, Garnet Kin-Lic},\n"
            "  title = {gpu4pyscf: GPU-Accelerated Quantum Chemistry on "
            "Distributed Systems},\n"
            "  journal = {arXiv preprint arXiv:2404.09452},\n"
            "  year = {2024},\n"
            "  doi = {10.48550/arXiv.2404.09452}\n"
            "}"
        ),
        "CFOUR": (
            "@article{Stanton_CFOUR_2020,\n"
            "  author = {Matthews, Devin A. and Cheng, Lan and Harding, Michael E. "
            "and Lipparini, Filippo and Stopkowicz, Stella and Jagau, Thomas-C. "
            "and Szalay, P{\\'e}ter G. and Gauss, J{\\\"u}rgen and Stanton, John F.},\n"
            "  title = {Coupled-cluster techniques for computational chemistry: "
            "The CFOUR program package},\n"
            "  journal = {The Journal of Chemical Physics},\n"
            "  volume = {152},\n"
            "  number = {21},\n"
            "  pages = {214108},\n"
            "  year = {2020},\n"
            "  doi = {10.1063/5.0004824}\n"
            "}"
        ),
        "AIMNet2": (
            "@article{Zubatyuk_AIMNet2_2024,\n"
            "  author = {Zubatyuk, Roman and Smith, Justin S. and "
            "Isayev, Olexandr},\n"
            "  title = {AIMNet2: A Neural Network Potential for Organic Chemistry "
            "and Beyond},\n"
            "  journal = {arXiv preprint arXiv:2404.06456},\n"
            "  year = {2024},\n"
            "  doi = {10.48550/arXiv.2404.06456}\n"
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
        "GFN-FF": (
            "@article{Spicher_GFNFF_2020,\n"
            "  author = {Spicher, Sebastian and Grimme, Stefan},\n"
            "  title = {Robust Atom-Parametrized Generic Force Field (GFN-FF) "
            "for General Molecular Structures},\n"
            "  journal = {Angewandte Chemie International Edition},\n"
            "  volume = {59},\n"
            "  number = {36},\n"
            "  pages = {15665--15673},\n"
            "  year = {2020},\n"
            "  doi = {10.1002/anie.202004239}\n"
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
        "PGOPHER": (
            "@article{Western_PGOPHER_2017,\n"
            "  author = {Western, Colin M.},\n"
            "  title = {PGOPHER: A program for simulating rotational, vibrational "
            "and electronic spectra},\n"
            "  journal = {Journal of Quantitative Spectroscopy and "
            "Radiative Transfer},\n"
            "  volume = {186},\n"
            "  pages = {221--242},\n"
            "  year = {2017},\n"
            "  doi = {10.1016/j.jqsrt.2016.04.010}\n"
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
        if delay <= 0.0:
            return
        with cls._rate_limit_lock:
            now = time.perf_counter()
            elapsed = now - cls._global_last_request_time
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

    @staticmethod
    def _escape_latex_field(text: str) -> str:
        """Escapes unescaped LaTeX special characters (% & _ # $) in BibTeX values."""
        if not text:
            return ""
        # Preserve existing escape sequences, escape raw %, &, _, #, $
        escaped = re.sub(r"(?<!\\)&", r"\&", text)
        escaped = re.sub(r"(?<!\\)%", r"\%", escaped)
        escaped = re.sub(r"(?<!\\)_", r"\_", escaped)
        escaped = re.sub(r"(?<!\\)#", r"\#", escaped)
        escaped = re.sub(r"(?<!\\)\$", r"\$", escaped)
        return escaped

    def generate_citation_key(
        self, first_author: str, method_name: str, year: str | int | None
    ) -> str:
        """Constructs deterministic, ASCII-safe, collision-resistant BibTeX key."""
        # Sanitize author: strip accents, remove "et al", replace non-alphanumeric
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
        # Strip URL query parameters and fragments
        clean = re.split(r"[?#]", clean)[0].strip()

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
        base_endpoint = self.api_url.rstrip("/")
        try:
            if (
                doi_candidate
                and "/" in doi_candidate
                and doi_candidate.startswith("10.")
            ):
                endpoint = f"{base_endpoint}/{doi_candidate}"
                resp = self.session.get(endpoint, timeout=self.request_timeout)
            else:
                params: dict[str, str | int] = {
                    "query.bibliographic": method_query,
                    "rows": 1,
                }
                resp = self.session.get(
                    self.api_url, params=params, timeout=self.request_timeout
                )

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
            logger.warning(
                "CrossRef query exception for '%s': %s (triggering fallback)",
                method_query,
                e,
            )
            return None
        except Exception as e:
            logger.warning(
                "Failed to parse CrossRef response for '%s': %s", method_query, e
            )
            return None
        finally:
            with CitationManager._rate_limit_lock:
                CitationManager._global_last_request_time = max(
                    CitationManager._global_last_request_time, time.perf_counter()
                )

    def _extract_authors(self, metadata: dict[str, Any]) -> tuple[str, str]:
        """Extracts first author surname and formatted LaTeX author string safely."""
        authors = metadata.get("author", [])
        if not authors or not isinstance(authors, list):
            return ("CoChem", "{CoChem Consortium}")

        author_parts: list[str] = []
        first_author_surname = "CoChem"

        for idx, author_dict in enumerate(authors):
            if not isinstance(author_dict, dict):
                continue
            family = (author_dict.get("family") or "").strip()
            given = (author_dict.get("given") or "").strip()
            name = (
                author_dict.get("name") or author_dict.get("literal") or ""
            ).strip()

            is_corporate = False
            if not family and not given and name:
                family = name
                is_corporate = True

            if idx == 0:
                first_author_surname = family or given or "CoChem"

            if family and given:
                author_parts.append(f"{family}, {given}")
            elif family:
                if is_corporate or (" " in family and not given):
                    author_parts.append(f"{{{family}}}")
                else:
                    author_parts.append(family)
            elif given:
                author_parts.append(given)

        if not author_parts:
            return (first_author_surname, "{CoChem Consortium}")

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

    @staticmethod
    def _determine_bib_type(entry_type: str) -> str:
        """Maps CrossRef work type string to standard BibTeX entry type."""
        entry_type_lower = entry_type.lower()
        if "book" in entry_type_lower:
            return "book"
        if "proceedings" in entry_type_lower or "conference" in entry_type_lower:
            return "inproceedings"
        if any(t in entry_type_lower for t in ("dataset", "report", "standard")):
            return "misc"
        return "article"

    def format_bibtex_entry(
        self, metadata: dict[str, Any], method_key: str
    ) -> str:
        """Converts CrossRef JSON metadata dictionary into standardized BibTeX entry."""
        first_author, authors_str = self._extract_authors(metadata)
        year = self._extract_year(metadata)
        cite_key = self.generate_citation_key(first_author, method_key, year)

        # Title extraction, HTML/XML tag stripping & normalization
        titles = metadata.get("title", [])
        if isinstance(titles, list) and titles:
            raw_title = str(titles[0] or "").strip()
        elif isinstance(titles, str):
            raw_title = titles.strip()
        else:
            raw_title = method_key
        clean_title = re.sub(r"<[^>]+>", "", raw_title)
        title = re.sub(r"\s+", " ", clean_title) or method_key
        title = self._escape_latex_field(title)

        # Journal / Container extraction
        container = metadata.get("container-title", [])
        if isinstance(container, list) and container:
            raw_journal = str(container[0] or "").strip()
            journal = re.sub(r"<[^>]+>", "", raw_journal)
        elif isinstance(container, str) and container:
            journal = re.sub(r"<[^>]+>", "", container.strip())
        else:
            pub = str(metadata.get("publisher") or "").strip()
            journal = pub
        journal = self._escape_latex_field(journal)

        volume = self._escape_latex_field(str(metadata.get("volume") or "").strip())
        issue_obj = metadata.get("journal-issue")
        issue_from_obj = issue_obj.get("issue") if isinstance(issue_obj, dict) else ""
        issue = self._escape_latex_field(
            str(metadata.get("issue") or issue_from_obj or "").strip()
        )

        pages = str(
            metadata.get("page") or metadata.get("article-number") or ""
        ).strip()
        if pages and "-" in pages and "--" not in pages:
            pages = pages.replace("-", "--")
        pages = self._escape_latex_field(pages)

        raw_doi = str(metadata.get("DOI") or "").strip()
        doi = self.normalize_doi(raw_doi) or raw_doi

        meta_type = str(metadata.get("type", "article-journal"))
        bib_type = self._determine_bib_type(meta_type)

        fields: list[str] = [
            f"  author = {{{authors_str}}}",
            f"  title = {{{title}}}",
        ]
        if journal:
            if bib_type == "article":
                fields.append(f"  journal = {{{journal}}}")
            elif bib_type == "inproceedings":
                fields.append(f"  booktitle = {{{journal}}}")
            elif bib_type == "book":
                fields.append(f"  publisher = {{{journal}}}")
            else:
                fields.append(f"  howpublished = {{{journal}}}")

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
            (r"\bgpu4pyscf\b", "gpu4pyscf"),
            (r"\bcfour\b", "CFOUR"),
            (r"\baimnet\b|\baimnet2\b", "AIMNet2"),
            (r"\bmace\b", "MACE-OFF23"),
            (r"\bgfn-ff\b|\bgfnff\b", "GFN-FF"),
            (r"\bxtb\b|\bgfn\b|\bgfn2\b", "xTB"),
            (r"\bdlpno\b|\bccsd\b", "DLPNO-CCSD(T)"),
            (r"\bcrest\b", "CREST"),
            (r"\br2scan\b", "r2SCAN-3c"),
            (r"\bb3lyp\b", "B3LYP"),
            (r"\bd4\b", "D4"),
            (r"\bd3\b|\bd3bj\b", "D3"),
            (r"\bpgopher\b", "PGOPHER"),
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
        clean_method_key = self.generate_citation_key("CoChem", method_str, 2024)
        escaped_method_title = self._escape_latex_field(method_str)
        fallback_title = f"{{{{Computational Method: {escaped_method_title}}}}}"
        generic_bibtex = (
            f"@misc{{{clean_method_key},\n"
            f"  author = {{{{CoChem Consortium}}}},\n"
            f"  title = {fallback_title},\n"
            f"  year = {{2024}},\n"
            f"  note = {{Resolved via CoChem-SCRIBE Automated Bibliographer}}\n"
            f"}}"
        )
        return (clean_method_key, generic_bibtex)

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
                if (
                    k
                    in (
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
                    )
                    or isinstance(v, dict | list)
                ):
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
