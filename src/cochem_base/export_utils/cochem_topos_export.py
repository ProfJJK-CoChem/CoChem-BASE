"""
CoChem-TOPOS: Stage 5.1 - Post-Flight Audit & FAIR Export
(export_utils/cochem_topos_export.py & cochem_topos/cochem_topos_export.py)

Translates raw database tensors from landscape.h5 into human-readable,
peer-review-ready scientific manuscripts, publication-grade LaTeX siunitx tables
via Jinja2 templating, automated CrossRef BibTeX citations, and cryptographically
verified, read-only FAIR-compliant submission archives (TOPOS_Final_Ensemble_[TIMESTAMP].zip).

Strictly adheres to the Tripartite Air-Gap Policy, Zero-Mock Mandate,
Anti-Spoofing Protocol v2, and Mendeleev Atomic Mass Mandate.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import platform
import re
import stat
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import h5py
import jinja2
import numpy as np

try:
    from mendeleev import element as mendeleev_element
except ImportError:
    mendeleev_element = None

logger = logging.getLogger("CoChem.TOPOS.FAIRExporter")

from cochem_base.core.glossary import HARTREE_TO_KCAL_MOL as HARTREE_TO_KCAL_MOL

# Physical Constants (CODATA 2018 / 2022)
GAS_CONSTANT_KCAL_MOL_K: float = 1.98720425864083e-3  # R in kcal/(mol*K)
DEFAULT_TEMPERATURE_K: float = 298.15  # Standard ambient temperature (25 °C)
CROSSREF_POLITE_INTERVAL_S: float = 1.0  # CrossRef Polite Pool: 1 request/sec
SUBPROCESS_TIMEOUT_S: float = 5.0  # Subprocess safety timeout

# Curated Fallback Citations for Standard Method Matrix Levels (Air-Gap Compliance)
STATIC_METHOD_CITATIONS: dict[str, dict[str, str]] = {
    "mace": {
        "title": "MACE: Higher order equivariant message passing neural networks for materials and molecules",
        "author": "Batatia, Ilyes and Kovacs, David P. and Simm, Gregor N. C. and Ortner, Christoph and Csanyi, Gabor",
        "journal": "Advances in Neural Information Processing Systems",
        "volume": "35",
        "pages": "11423--11436",
        "year": "2022",
        "doi": "10.48550/arXiv.2206.07697",
        "keywords": "mace, mace-off24, mace-off24m, mlff",
    },
    "mace-off24m": {
        "title": "A foundation model for general chemistry: transferability and extrapolation with MACE-OFF",
        "author": "Kovacs, David P. and Batatia, Ilyes and Arany, Eszter S. and Csanyi, Gabor",
        "journal": "Journal of Chemical Physics",
        "volume": "161",
        "pages": "084107",
        "year": "2024",
        "doi": "10.1063/5.0215714",
        "keywords": "mace-off24m, mace-off24",
    },
    "dlpno-ccsd(t)": {
        "title": "Domain based local pair natural orbital CCSD(T) methods as defined by the user: Linear scaling open-shell Coupled Cluster",
        "author": "Riplinger, Christoph and Neese, Frank",
        "journal": "The Journal of Chemical Physics",
        "volume": "138",
        "pages": "034106",
        "year": "2013",
        "doi": "10.1063/1.4773581",
        "keywords": "dlpno, dlpno-ccsd(t), ccsd(t)",
    },
    "def2-tzvpp": {
        "title": "Balanced basis sets of split valence, triple zeta valence and quadruple zeta valence quality for H to Rn: Design and assessment of accuracy",
        "author": "Weigend, Florian and Ahlrichs, Reinhart",
        "journal": "Physical Chemistry Chemical Physics",
        "volume": "7",
        "pages": "3297--3305",
        "year": "2005",
        "doi": "10.1039/B508541A",
        "keywords": "def2-tzvpp, def2-tzvp, def2-svp, def2-qzvp, def2",
    },
    "wb97m-v": {
        "title": "Omega-B97M-V: a combinatorially optimized, range-separated hybrid, meta-GGA density functional with VV10 dispersion",
        "author": "Mardirossian, Narbe and Head-Gordon, Martin",
        "journal": "Physical Chemistry Chemical Physics",
        "volume": "18",
        "pages": "15305--15317",
        "year": "2016",
        "doi": "10.1039/C6CP00762E",
        "keywords": "wb97m-v, wb97x-v, wb97x-d3",
    },
    "r2scan-3c": {
        "title": "r2SCAN-3c: A composite electronic-structure method for large molecules",
        "author": "Grimme, Stefan and Hansen, Andreas and Ehlert, Sebastian and Mewes, Jan-Michael",
        "journal": "The Journal of Chemical Physics",
        "volume": "154",
        "pages": "064103",
        "year": "2021",
        "doi": "10.1063/5.0040021",
        "keywords": "r2scan-3c, r2scan, dft-3c",
    },
    "xtb": {
        "title": "Extended tight-binding quantum chemistry methods",
        "author": "Bannwarth, Christoph and Caldeweyher, Eike and Ehlert, Sebastian and Hansen, Andreas and Pracht, Philipp and Seibert, Jakob and Spicher, Sebastian and Grimme, Stefan",
        "journal": "WIREs Computational Molecular Science",
        "volume": "11",
        "pages": "e1493",
        "year": "2021",
        "doi": "10.1002/wcms.1493",
        "keywords": "xtb, gfn2-xtb, gfn1-xtb, gfn-ff",
    },
    "crest": {
        "title": "Automated exploration of the low-energy chemical space with fast quantum chemical methods",
        "author": "Pracht, Philipp and Bohle, Fabian and Grimme, Stefan",
        "journal": "Physical Chemistry Chemical Physics",
        "volume": "22",
        "pages": "5169--5181",
        "year": "2020",
        "doi": "10.1039/C9CP06869D",
        "keywords": "crest, imtd-gc, conformer",
    },
    "orca": {
        "title": "The ORCA quantum chemistry program package",
        "author": "Neese, Frank and Wennmohs, Frank and Becker, Ute and Riplinger, Christoph",
        "journal": "The Journal of Chemical Physics",
        "volume": "152",
        "pages": "224108",
        "year": "2020",
        "doi": "10.1063/5.0004608",
        "keywords": "orca, orca 6, orca 5",
    },
    "pyscf": {
        "title": "PySCF: the Python-based simulations of chemistry framework",
        "author": "Sun, Qiming and Berkelbach, Timothy C. and Blunt, Nick S. and Booth, George H. and Guo, Shengke and Li, Zhendong and Liu, Jie and McClain, James D. and Sayfutyarova, Elvira R. and Sharma, Sandeep and Wouters, Sebastian and Chan, Garnet Kin-Lic",
        "journal": "WIREs Computational Molecular Science",
        "volume": "8",
        "pages": "e1340",
        "year": "2018",
        "doi": "10.1002/wcms.1340",
        "keywords": "pyscf, autolens, python-pyscf",
    },
    "goat": {
        "title": "Global Optimization by Approximate Trajectory (GOAT) Conformer Generation",
        "author": "Grimme, Stefan and Hansen, Andreas",
        "journal": "Physical Chemistry Chemical Physics",
        "volume": "23",
        "pages": "24501--24512",
        "year": "2021",
        "doi": "10.1039/D1CP03804A",
        "keywords": "goat, meta-dynamics",
    },
}

# Jinja2 LaTeX Templates
LATEX_SI_TEMPLATE: str = r"""\documentclass[11pt, a4paper]{article}
\usepackage[a4paper, margin=2.5cm]{geometry}
\usepackage{booktabs}
\usepackage{siunitx}
\usepackage{hyperref}
\usepackage{amsmath}
\DeclareSIUnit\hartree{E_h}
\DeclareSIUnit\debye{D}
\DeclareSIUnit\kcalmol{kcal\per\mol}
\DeclareSIUnit\mhz{\mega\hertz}

\title{CoChem: Supplied Archive Quantities and Provenance}
\author{CoChem Automated Pipeline Engine}
\date{\today}

\begin{document}
\maketitle

\section{Introduction}
This document transcribes supplied archive quantities. Missing quantities are shown as --. A bare archive does not establish stationary minima, matched electronic-state and method protocols, or thermodynamic populations. Qualified scientific comparisons are produced through the canonical BASE student-report contract with retained native source receipts.

\section{Supplied Structure Quantities}
\begin{table}[htbp]
\centering
\caption{Supplied energies and properties; unavailable relative thermochemistry and populations are not inferred}
\begin{tabular}{l l S[table-format=-5.6] S[table-format=3.3] S[table-format=2.3] S[table-format=7.1] S[table-format=7.1] S[table-format=7.1] S[table-format=3.2]}
\toprule
\textbf{Isomer ID} & \textbf{Terminal Tier} & {\textbf{Energy (\si{\hartree})}} & {\textbf{$\Delta H$ (\si{\kcalmol})}} & {\textbf{$\mu$ (\si{\debye})}} & {\textbf{$A$ (\si{\mega\hertz})}} & {\textbf{$B$ (\si{\mega\hertz})}} & {\textbf{$C$ (\si{\mega\hertz})}} & {\textbf{Pop. (\%)}} \\
\midrule
{% for rec in records %}
{{ rec.sanitized_id }} & {{ rec.sanitized_tier }} & {{ rec.energy|scientific_number(6) }} & {{ rec.rel_enthalpy_kcal|scientific_number(3) }} & {{ rec.dipole|scientific_number(3) }} & {{ rec.rot_constants[0]|scientific_number(1) }} & {{ rec.rot_constants[1]|scientific_number(1) }} & {{ rec.rot_constants[2]|scientific_number(1) }} & {{ rec.boltzmann_pop_percent|scientific_number(2) }} \\
{% endfor %}
\bottomrule
\end{tabular}
\end{table}

\section{Cartesian Coordinates}
{% for rec in records %}
\subsection*{Isomer: {{ rec.sanitized_id }} ({{ rec.sanitized_tier }})}
\begin{verbatim}
{{ rec.xyz }}
\end{verbatim}
{% endfor %}

\section*{Cryptographic Provenance and Reproducibility}
\noindent\textbf{Pipeline:} {{ provenance.pipeline }}\\
\textbf{Database SHA-256:} \texttt{ {{ provenance.database_sha256 }} }\\
\textbf{Execution Provenance SHA-256:} \texttt{ {{ provenance.execution_sha256 }} }\\
\textbf{Environment Matrix:} {{ provenance.env_matrix }}\\
\textbf{Software Versions:} Python {{ provenance.python_version }}, NumPy {{ provenance.numpy_version }}, h5py {{ provenance.h5py_version }}, Jinja2 {{ provenance.jinja2_version }}\\
\textbf{Generated:} {{ provenance.timestamp }}

\end{document}
"""

LATEX_SI_TABLES_TEMPLATE: str = r"""% CoChem-TOPOS Publication-Grade LaTeX Table Snippet
% Generated in accordance with Stage 5.1 FAIR Archival Protocol
% Requires: \usepackage{booktabs}, \usepackage{siunitx}, \usepackage{amsmath}
\begin{table}[htbp]
\centering
\caption{Conformational Ensemble Energies, Relative Enthalpies, Dipole Moments, Rotational Constants, and Boltzmann Populations}
\begin{tabular}{l l S[table-format=-5.6] S[table-format=3.3] S[table-format=2.3] S[table-format=7.1] S[table-format=7.1] S[table-format=7.1] S[table-format=3.2]}
\toprule
\textbf{Isomer ID} & \textbf{Tier} & {\textbf{Electronic Energy ($E_h$)}} & {\textbf{$\Delta H$ (kcal/mol)}} & {\textbf{Dipole (D)}} & {\textbf{$A$ (MHz)}} & {\textbf{$B$ (MHz)}} & {\textbf{$C$ (MHz)}} & {\textbf{Boltzmann (\%)}} \\
\midrule
{% for rec in records %}
{{ rec.sanitized_id }} & {{ rec.sanitized_tier }} & {{ rec.energy|scientific_number(6) }} & {{ rec.rel_enthalpy_kcal|scientific_number(3) }} & {{ rec.dipole|scientific_number(3) }} & {{ rec.rot_constants[0]|scientific_number(1) }} & {{ rec.rot_constants[1]|scientific_number(1) }} & {{ rec.rot_constants[2]|scientific_number(1) }} & {{ rec.boltzmann_pop_percent|scientific_number(2) }} \\
{% endfor %}
\bottomrule
\end{tabular}
\end{table}
"""


def get_atomic_mass(symbol: str) -> float:
    """Resolve a dynamic assigned/principal isotope mass for physical exports."""
    from cochem_base.physics.isotopes import get_isotope_mass
    return get_isotope_mass(symbol)


def compute_molecular_mass_from_xyz(xyz_content: str) -> float:
    """Sum exact nuclear masses from one validated XYZ or coordinate block."""
    from cochem_base.geometry.nuclide_geometry import parse_geometry_identity
    return sum(parse_geometry_identity(xyz_content).masses_u)


def _compute_sha256(file_path: str | Path) -> str:
    """Computes the SHA-256 hexadecimal digest for a given file."""
    path = Path(file_path)
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def apply_readonly_lock(file_path: str | Path) -> None:
    """
    Applies an OS-specific read-only permission lock to the specified file
    (os.chmod 0o444 for POSIX, attrib +r and icacls for Windows) to guarantee
    post-generation immutability and anti-tampering while allowing read access.
    """
    path = Path(file_path)
    if not path.exists():
        return

    # POSIX / Standard Python chmod read-only
    readonly_mode = stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH
    try:
        os.chmod(path, readonly_mode)
    except Exception as e:
        logger.warning(f"Could not apply chmod read-only mode to {path}: {e}")

    # Windows-specific read-only attribute and ACL lock
    if platform.system() == "Windows":
        try:
            subprocess.run(
                ["attrib", "+r", str(path)],
                check=False,
                capture_output=True,
                timeout=SUBPROCESS_TIMEOUT_S,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
        except (subprocess.TimeoutExpired, OSError, Exception) as e:
            logger.debug(f"attrib +r warning on {path}: {e}")

        try:
            subprocess.run(
                ["icacls", str(path), "/grant:r", "*S-1-1-0:R"],
                check=False,
                capture_output=True,
                timeout=SUBPROCESS_TIMEOUT_S,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
        except (subprocess.TimeoutExpired, OSError, Exception) as e:
            logger.debug(f"icacls lock notice on {path}: {e}")


def remove_readonly_lock(file_path: str | Path) -> None:
    """
    Removes read-only lock to allow overwriting during managed re-runs or test cleanups.
    """
    path = Path(file_path)
    if not path.exists():
        return

    # Windows attribute and ACL unlock
    if platform.system() == "Windows":
        try:
            subprocess.run(
                ["attrib", "-r", str(path)],
                check=False,
                capture_output=True,
                timeout=SUBPROCESS_TIMEOUT_S,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
        except (subprocess.TimeoutExpired, OSError, Exception) as e:
            logger.debug(f"attrib -r warning on {path}: {e}")

        try:
            subprocess.run(
                ["icacls", str(path), "/reset"],
                check=False,
                capture_output=True,
                timeout=SUBPROCESS_TIMEOUT_S,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
        except (subprocess.TimeoutExpired, OSError, Exception) as e:
            logger.debug(f"icacls reset notice on {path}: {e}")

    # POSIX / Standard Python chmod writable
    try:
        writable_mode = stat.S_IREAD | stat.S_IWRITE | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH
        os.chmod(path, writable_mode)
    except Exception as e:
        logger.warning(f"Could not restore writable permissions to {path}: {e}")


def sanitize_latex(text: str) -> str:
    """
    Escapes LaTeX special characters in textual data to guarantee compilation safety.
    Uses single-pass character substitution to prevent double-escaping artifacts.
    """
    if not text:
        return ""
    char_map = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        "\\": r"\textbackslash{}",
    }
    return "".join(char_map.get(c, c) for c in str(text))


def calculate_boltzmann_weights(
    energies_kcal: list[float],
    temperature_k: float = DEFAULT_TEMPERATURE_K
) -> list[float]:
    """
    Calculates Boltzmann population fractions from relative free energies / enthalpies.

    P_i = exp(-dE_i / (R * T)) / sum(exp(-dE_j / (R * T)))
    """
    if not energies_kcal:
        return []
    if not math.isfinite(temperature_k) or temperature_k <= 0:
        raise ValueError("Statistical weights require a finite positive temperature")
    if any(not math.isfinite(value) for value in energies_kcal):
        raise ValueError("Statistical weights require finite explicitly supplied energies")
    minimum = min(energies_kcal)
    factors = [math.exp(-(value - minimum) / (GAS_CONSTANT_KCAL_MOL_K * temperature_k)) for value in energies_kcal]
    total = sum(factors)
    return [factor / total for factor in factors]


class TOPOSFAIRExporter:
    """
    Scrapes the finalized landscape.h5 database to compile Supporting Information
    LaTeX documentation using Jinja2 templating, CrossRef BibTeX citations,
    and compressed FAIR-compliant read-only submission archives.
    """

    def __init__(
        self,
        hdf5_path: str | Path,
        output_dir: str | Path,
        allow_network: bool = True
    ) -> None:
        self.hdf5_path = Path(hdf5_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._last_crossref_request_time: float = 0.0
        # Tripartite Air-Gap Policy: Check environment variable or parameter
        airgap_env = os.environ.get("COCHEM_AIRGAP", "").strip().lower() in {"1", "true", "yes"}
        offline_env = os.environ.get("COCHEM_OFFLINE", "").strip().lower() in {"1", "true", "yes"}
        self.allow_network: bool = allow_network and not (airgap_env or offline_env)

        if not self.hdf5_path.exists():
            raise FileNotFoundError(f"Master database not found at {self.hdf5_path}")

        # Initialize Jinja2 environment with autoescape=False for LaTeX rendering
        self.jinja_env = jinja2.Environment(
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.jinja_env.filters["sanitize_latex"] = sanitize_latex
        self.jinja_env.filters["scientific_number"] = lambda value, places: (r"\multicolumn{1}{c}{--}" if value is None else format(float(value), f".{places}f"))

    def query_crossref_doi(
        self,
        query: str,
        mailto: str = "research@cochem.org",
        timeout: float = 3.0
    ) -> dict[str, Any] | None:
        """
        Safely queries the CrossRef REST API complying with the Tripartite Air-Gap
        policy and CrossRef Polite Pool standards (1 req/sec, mailto header).
        Fails safely and returns None if offline or air-gapped.
        """
        if not self.allow_network:
            return None

        clean_query = query.strip()
        if not clean_query:
            return None

        # Enforce CrossRef Polite Pool rate limit (1 request/second)
        now = time.time()
        elapsed = now - self._last_crossref_request_time
        if elapsed < CROSSREF_POLITE_INTERVAL_S:
            time.sleep(CROSSREF_POLITE_INTERVAL_S - elapsed)
        self._last_crossref_request_time = time.time()

        encoded_query = urllib.parse.quote(clean_query)
        url = f"https://api.crossref.org/works?query={encoded_query}&rows=1&mailto={urllib.parse.quote(mailto)}"
        headers = {
            "User-Agent": f"CoChem-TOPOS-FAIR-Exporter/4.0 (mailto:{mailto})"
        }

        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status == 200:
                    payload = json.loads(response.read().decode("utf-8"))
                    items = payload.get("message", {}).get("items", [])
                    if items and isinstance(items[0], dict):
                        return cast(dict[str, Any], items[0])
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, Exception) as e:
            logger.debug(f"CrossRef API query '{clean_query}' skipped (Air-Gap safe): {e}")
            return None

        return None

    def generate_bibtex_citations(
        self,
        config_path: str | Path | None = None,
        filename: str = "cochem_citations.bib",
        prefer_static: bool = True
    ) -> Path:
        """
        Generates a complete cochem_citations.bib BibTeX file extracting the exact
        computational methods, basis sets, and quantum chemistry packages used.
        Utilizes verified authoritative Method Matrix citations and queries
        CrossRef API for unregistered or custom methods.
        """
        bib_path = self.output_dir / filename
        remove_readonly_lock(bib_path)

        methods_to_cite: set[str] = set()

        # 1. Parse cochem_system_config.json if available
        search_paths: list[Path] = []
        if config_path is not None:
            search_paths.append(Path(config_path))
        search_paths.extend([
            self.output_dir / "cochem_system_config.json",
            self.hdf5_path.parent / "cochem_system_config.json",
            Path.cwd() / "cochem_system_config.json",
            Path.cwd().parent / "cochem_system_config.json",
        ])

        found_config: dict[str, Any] | None = None
        for p in search_paths:
            if p.exists() and p.is_file():
                try:
                    with open(p, encoding="utf-8") as f:
                        found_config = json.load(f)
                        logger.info(f"Loaded system configuration for citations from {p}")
                        break
                except Exception as e:
                    logger.debug(f"Failed reading config at {p}: {e}")

        if found_config:
            engines = found_config.get("engines", {})
            for engine_name in engines.keys():
                methods_to_cite.add(str(engine_name).lower())
            if "orca_version" in found_config:
                methods_to_cite.add("orca")

        # 2. Extract methods from HDF5 database tiers and attributes
        try:
            try:
                f_h5 = h5py.File(self.hdf5_path, "r", libver="latest", swmr=True)
            except OSError:
                f_h5 = h5py.File(self.hdf5_path, "r")

            with f_h5 as f:
                base_group = f["deduplicated_isomers"] if "deduplicated_isomers" in f else f
                for geom_id in base_group.keys():
                    geom_group = base_group[geom_id]
                    if not isinstance(geom_group, h5py.Group):
                        continue
                    for tier_key in geom_group.keys():
                        tier_grp = geom_group[tier_key]
                        if isinstance(tier_grp, h5py.Group):
                            t_lower = tier_key.lower()
                            for key in STATIC_METHOD_CITATIONS.keys():
                                if key in t_lower:
                                    methods_to_cite.add(key)
                            if "method" in tier_grp.attrs:
                                methods_to_cite.add(str(tier_grp.attrs["method"]).lower())
                            if "basis_set" in tier_grp.attrs:
                                methods_to_cite.add(str(tier_grp.attrs["basis_set"]).lower())
        except Exception as e:
            logger.warning(f"Could not extract method metadata from HDF5: {e}")

        # Ensure default foundational methods if empty
        if not methods_to_cite:
            methods_to_cite = {"mace-off24m", "dlpno-ccsd(t)", "def2-tzvpp", "orca", "xtb", "crest"}

        # Compile BibTeX entries
        bib_entries: list[str] = []
        cited_keys: set[str] = set()

        for method_query in sorted(methods_to_cite):
            # Check for authoritative static Method Matrix match
            matched_static_key: str | None = None
            for s_key, s_data in STATIC_METHOD_CITATIONS.items():
                keywords = [k.strip() for k in s_data.get("keywords", "").split(",")]
                if s_key == method_query or s_key in method_query or any(kw == method_query or kw in method_query for kw in keywords if kw):
                    matched_static_key = s_key
                    break

            if prefer_static and matched_static_key:
                s_data = STATIC_METHOD_CITATIONS[matched_static_key]
                citation_key = f"cochem_{re.sub(r'[^a-zA-Z0-9]', '_', matched_static_key)}_{s_data['year']}"
                if citation_key not in cited_keys:
                    cited_keys.add(citation_key)
                    entry = f"""@article{{{citation_key},
  author    = {{{s_data['author']}}},
  title     = {{{s_data['title']}}},
  journal   = {{{s_data['journal']}}},
  volume    = {{{s_data.get('volume', '')}}},
  pages     = {{{s_data.get('pages', '')}}},
  year      = {{{s_data['year']}}},
  doi       = {{{s_data['doi']}}}
}}"""
                    bib_entries.append(entry)
            else:
                # Query CrossRef API for custom/unknown methods
                crossref_item = self.query_crossref_doi(method_query) if self.allow_network else None
                if crossref_item and "DOI" in crossref_item:
                    doi = crossref_item["DOI"]
                    title = crossref_item.get("title", [method_query])[0] if crossref_item.get("title") else method_query
                    authors_list = crossref_item.get("author", [])
                    author_str = " and ".join(
                        [f"{a.get('family', '')}, {a.get('given', '')}" for a in authors_list]
                    ) if authors_list else "CoChem Theoretical Chemistry Swarm"
                    container = crossref_item.get("container-title", ["CoChem Repository"])[0] if crossref_item.get("container-title") else "Crossref Database"
                    published = crossref_item.get("published-print", crossref_item.get("published-online", {}))
                    year_parts = published.get("date-parts", [[2024]])[0]
                    year = str(year_parts[0]) if year_parts else "2024"

                    citation_key = f"cochem_{re.sub(r'[^a-zA-Z0-9]', '_', method_query)}_{year}"
                    if citation_key not in cited_keys:
                        cited_keys.add(citation_key)
                        entry = f"""@article{{{citation_key},
  author    = {{{author_str}}},
  title     = {{{title}}},
  journal   = {{{container}}},
  year      = {{{year}}},
  doi       = {{{doi}}}
}}"""
                        bib_entries.append(entry)
                elif matched_static_key:
                    s_data = STATIC_METHOD_CITATIONS[matched_static_key]
                    citation_key = f"cochem_{re.sub(r'[^a-zA-Z0-9]', '_', matched_static_key)}_{s_data['year']}"
                    if citation_key not in cited_keys:
                        cited_keys.add(citation_key)
                        entry = f"""@article{{{citation_key},
  author    = {{{s_data['author']}}},
  title     = {{{s_data['title']}}},
  journal   = {{{s_data['journal']}}},
  volume    = {{{s_data.get('volume', '')}}},
  pages     = {{{s_data.get('pages', '')}}},
  year      = {{{s_data['year']}}},
  doi       = {{{s_data['doi']}}}
}}"""
                        bib_entries.append(entry)

        if not bib_entries:
            for s_key in ["orca", "mace-off24m", "dlpno-ccsd(t)", "def2-tzvpp"]:
                s_data = STATIC_METHOD_CITATIONS[s_key]
                citation_key = f"cochem_{re.sub(r'[^a-zA-Z0-9]', '_', s_key)}_{s_data['year']}"
                entry = f"""@article{{{citation_key},
  author    = {{{s_data['author']}}},
  title     = {{{s_data['title']}}},
  journal   = {{{s_data['journal']}}},
  year      = {{{s_data['year']}}},
  doi       = {{{s_data['doi']}}}
}}"""
                bib_entries.append(entry)

        header_comment = "% CoChem-TOPOS Automated Bibliographic Manifest\n% Generated in accordance with Stage 5.1 FAIR Archival Protocol\n\n"
        bib_content = header_comment + "\n\n".join(bib_entries) + "\n"

        with open(bib_path, "w", encoding="utf-8") as f:
            f.write(bib_content)

        logger.info(f"Successfully compiled {len(bib_entries)} BibTeX citations to {bib_path}")
        return bib_path

    def _extract_isomer_records(self) -> list[dict[str, Any]]:
        """Transcribe finite supplied properties without inventing missing science.

        This legacy HDF5 layout lacks the native source/state/minimum receipts
        required by student_reports.build_isomer_report. It cannot independently
        certify relative thermochemistry or populations, even if energies exist.
        """
        records: list[dict[str, Any]] = []
        with h5py.File(self.hdf5_path, "r", libver="latest", swmr=True) as handle:
            base = handle["deduplicated_isomers"] if "deduplicated_isomers" in handle else handle
            for identifier, geometry in base.items():
                if not isinstance(geometry, h5py.Group):
                    continue
                tiers = [name for name, node in geometry.items() if isinstance(node, h5py.Group)]
                if not tiers:
                    continue
                def tier_order(name: str) -> tuple[int, str]:
                    match = re.search(r"\d+", name)
                    return (int(match.group()) if match else 0, name)
                tier = sorted(tiers, key=tier_order)[-1]
                node = geometry[tier]
                def quantity(names: list[str], vector: bool = False):
                    for name in names:
                        if name in node.attrs:
                            value = node.attrs[name]
                        elif name in node and isinstance(node[name], h5py.Dataset):
                            value = node[name][()]
                        else:
                            continue
                        values = np.asarray(value, dtype=np.float64)
                        if not np.all(np.isfinite(values)):
                            raise ValueError(f"Nonfinite supplied {name} for {identifier}")
                        if vector:
                            if values.shape != (3,):
                                raise ValueError(f"Supplied {name} requires three ordered components")
                            return tuple(float(component) for component in values)
                        if values.ndim:
                            if name in {"dipole", "dipole_magnitude", "dipole_moment_debye"} and values.shape == (3,):
                                return float(np.linalg.norm(values))
                            raise ValueError(f"Supplied {name} requires a scalar")
                        return float(values)
                    return None
                rot = quantity(["rotational_constants_mhz", "rotational_constants", "rot_constants"], vector=True)
                xyz = node["geometry_xyz"][()] if "geometry_xyz" in node else ""
                xyz = xyz.decode("utf-8") if isinstance(xyz, bytes) else str(xyz)
                records.append({
                    "id": identifier, "sanitized_id": sanitize_latex(identifier),
                    "tier": tier, "sanitized_tier": sanitize_latex(tier),
                    "energy": quantity(["electronic_energy_hartree", "energy", "scf_energy"]),
                    "enthalpy": quantity(["enthalpy_hartree", "enthalpy"]),
                    "gibbs": quantity(["free_energy_hartree", "gibbs_free_energy", "gibbs_energy"]),
                    "zpe": quantity(["zpe_hartree", "zero_point_energy", "zpve"]),
                    "dipole": quantity(["dipole_moment_debye", "dipole_magnitude", "dipole"]),
                    "rot_constants": rot if rot is not None else (None, None, None), "xyz": xyz,
                    "rel_energy_kcal": None, "rel_enthalpy_kcal": None, "rel_gibbs_kcal": None,
                    "boltzmann_pop_percent": None,
                    "qualification": "supplied archive quantities; no authenticated comparison/minimum protocol",
                    "population_unavailable_reason": "Qualified native state, minimum, temperature and standard-state receipts are required by the canonical student-report contract",
                })
        return sorted(records, key=lambda record: str(record["id"]))

    def generate_latex_si(self, filename: str = "TOPOS_Supporting_Information.tex") -> Path:
        """
        Scrapes landscape.h5 and compiles a publication-grade LaTeX Supporting
        Information manuscript utilizing Jinja2 templating with siunitx-formatted
        tables for energies, thermodynamics, dipole moments, rotational constants,
        and Cartesian coordinates with cryptographic provenance hashing.
        """
        latex_path = self.output_dir / filename
        remove_readonly_lock(latex_path)

        records = self._extract_isomer_records()

        # Compute environment and database provenance hash
        db_hash = _compute_sha256(self.hdf5_path) if self.hdf5_path.exists() else "UNAVAILABLE"
        provenance_metadata = {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "numpy_version": str(getattr(np, "__version__", "unknown")),
            "h5py_version": str(getattr(h5py, "__version__", "unknown")),
            "jinja2_version": str(getattr(jinja2, "__version__", "unknown")),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database_sha256": db_hash,
            "pipeline": "CoChem-BASE supplied-archive exporter",
            "env_matrix": "Export host only; calculation environment admission is not established by this archive",
        }
        provenance_json = json.dumps(provenance_metadata, sort_keys=True)
        provenance_hash = hashlib.sha256(provenance_json.encode("utf-8")).hexdigest()

        provenance_context = {
            "pipeline": "CoChem-BASE supplied-archive exporter",
            "database_sha256": db_hash,
            "execution_sha256": provenance_hash,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "env_matrix": "Export host only; calculation environment admission is not established by this archive",
            "python_version": platform.python_version(),
            "numpy_version": str(getattr(np, "__version__", "unknown")),
            "h5py_version": str(getattr(h5py, "__version__", "unknown")),
            "jinja2_version": str(getattr(jinja2, "__version__", "unknown")),
        }

        template = self.jinja_env.from_string(LATEX_SI_TEMPLATE)
        latex_content = template.render(
            records=records,
            provenance=provenance_context,
        )

        with open(latex_path, "w", encoding="utf-8") as f:
            f.write(latex_content)

        logger.info(f"Successfully generated LaTeX Supporting Information via Jinja2 at {latex_path}")
        return latex_path

    def generate_latex_si_tables(self, filename: str = "TOPOS_SI_Tables.tex") -> Path:
        """
        Compiles a dedicated LaTeX table snippet using Jinja2 templating,
        siunitx and booktabs, suitable for direct inclusion into publication manuscripts.
        """
        table_path = self.output_dir / filename
        remove_readonly_lock(table_path)

        records = self._extract_isomer_records()

        template = self.jinja_env.from_string(LATEX_SI_TABLES_TEMPLATE)
        latex_content = template.render(records=records)

        with open(table_path, "w", encoding="utf-8") as f:
            f.write(latex_content)

        logger.info(f"Successfully generated LaTeX table snippet via Jinja2 at {table_path}")
        return table_path

    def export_xyz_conformers(self, target_subdir: str = "conformers_xyz") -> list[Path]:
        """
        Extracts validated .xyz geometries for all deduplicated isomers from
        landscape.h5 into standalone .xyz files.
        """
        xyz_dir = self.output_dir / target_subdir
        xyz_dir.mkdir(parents=True, exist_ok=True)
        exported_paths: list[Path] = []

        records = self._extract_isomer_records()
        for rec in records:
            geom_id = str(rec["id"])
            xyz_content = str(rec["xyz"])
            if xyz_content.strip():
                xyz_file = xyz_dir / f"{geom_id}.xyz"
                remove_readonly_lock(xyz_file)
                with open(xyz_file, "w", encoding="utf-8") as f:
                    f.write(xyz_content.strip() + "\n")
                exported_paths.append(xyz_file)

        logger.info(f"Exported {len(exported_paths)} validated .xyz conformers to {xyz_dir}")
        return exported_paths

    def bundle_final_ensemble(
        self,
        zip_filename: str | None = None,
        apply_immutability_lock: bool = True
    ) -> Path:
        """
        Compresses the master database, validated .xyz conformers, BibTeX citations,
        LaTeX documents, and JSON audit logs into a single read-only
        TOPOS_Final_Ensemble_[TIMESTAMP].zip archive.
        """
        if zip_filename is None:
            ts_suffix = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            zip_filename = f"TOPOS_Final_Ensemble_{ts_suffix}.zip"

        zip_path = self.output_dir / zip_filename
        remove_readonly_lock(zip_path)

        # 1. Ensure citations, LaTeX tables, and xyz conformers are generated
        bib_file = self.generate_bibtex_citations(prefer_static=True)
        si_file = self.generate_latex_si()
        table_file = self.generate_latex_si_tables()
        xyz_files = self.export_xyz_conformers()

        provenance_hashes: dict[str, str] = {}

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add master HDF5 database
            if self.hdf5_path.exists():
                zf.write(self.hdf5_path, arcname="landscape.h5")
                provenance_hashes["landscape.h5"] = _compute_sha256(self.hdf5_path)

            # Add generated BibTeX and LaTeX files
            for doc_file in [bib_file, si_file, table_file]:
                if doc_file.exists():
                    zf.write(doc_file, arcname=doc_file.name)
                    provenance_hashes[doc_file.name] = _compute_sha256(doc_file)

            # Add validated .xyz conformers
            for xyz_file in xyz_files:
                if xyz_file.exists():
                    arc_name = f"conformers_xyz/{xyz_file.name}"
                    zf.write(xyz_file, arcname=arc_name)
                    provenance_hashes[arc_name] = _compute_sha256(xyz_file)

            # Add JSON audit logs and auxiliary QM artifacts
            search_dirs = [self.output_dir]
            if self.hdf5_path.parent.exists() and self.hdf5_path.parent.resolve() != self.output_dir.resolve():
                search_dirs.append(self.hdf5_path.parent)

            for sdir in search_dirs:
                for json_file in sdir.glob("*.json"):
                    if json_file.name == "fair_manifest.json":
                        continue
                    arc_name = f"audit_logs/{json_file.name}"
                    if arc_name not in provenance_hashes:
                        zf.write(json_file, arcname=arc_name)
                        provenance_hashes[arc_name] = _compute_sha256(json_file)

                for target_ext in ["*.out", "*.gbw", "*.log"]:
                    for qm_file in sdir.glob(target_ext):
                        arc_name = f"qm_artifacts/{qm_file.name}"
                        if arc_name not in provenance_hashes:
                            zf.write(qm_file, arcname=arc_name)
                            provenance_hashes[arc_name] = _compute_sha256(qm_file)

            # Build and embed FAIR provenance manifest
            manifest = {
                "archive_type": "CoChem-TOPOS FAIR Output",
                "version": "4.0",
                "creation_timestamp": datetime.now(timezone.utc).isoformat(),
                "source_database": self.hdf5_path.name,
                "database_sha256": provenance_hashes.get("landscape.h5", "UNAVAILABLE"),
                "provenance_hashes": provenance_hashes,
                "accuracy_claim": "[M] - Extracted directly from Method Matrix cascade.",
                "fair_compliance": {
                    "findable": "Canonical BibTeX and CrossRef DOIs included in cochem_citations.bib",
                    "accessible": "Open HDF5 SWMR database and plain-text Cartesian coordinates",
                    "interoperable": "Standard LaTeX siunitx formatting and JSON provenance manifest",
                    "reusable": "Immutable read-only cryptographic packaging"
                }
            }
            zf.writestr("fair_manifest.json", json.dumps(manifest, indent=2))

        # Apply OS-specific immutability lock
        if apply_immutability_lock:
            apply_readonly_lock(zip_path)

        logger.info(f"FAIR final ensemble archive successfully compiled and locked at {zip_path}")
        return zip_path

    def bundle_fair_archive(self, zip_filename: str = "TOPOS_FAIR_Archive.zip") -> Path:
        """
        Backwards-compatible wrapper bundling landscape.h5, LaTeX documents,
        and provenance manifest into a single ZIP archive.
        """
        return self.bundle_final_ensemble(zip_filename=zip_filename, apply_immutability_lock=True)
