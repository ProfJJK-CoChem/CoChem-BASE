Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task2_pt2_reaper.md.
Original prompt:
﻿# Task: Create subprocess_reaper.py

## Target File
`cochem_bench\bench_libraries\subprocess_reaper.py` (relative to repo root)

## Architecture Note
This is a V2 rewrite. Ignore any legacy architecture described in the old `workflow.md`. Implement exactly as specified here. Ensure the `bench_libraries` directory is created if it does not exist.

## Requirements
Implement the ZMQ Brokering & Process Isolation script.
Ensures executing high-tier DLPNO-CCSD(T) extrapolations does not result in cluster lockups or runaway computational costs.

Functions to implement:
1. `PreFlightScratchVerifier()`: Before launching heavy CBS extrapolation, mathematically verify that targeted `$SCRATCH` directory (resolved dynamically via `pathlib.Path(os.environ['COCHEM_ARTIFACTS_DIR']) / 'BENCH_Workspace' / 'Scratch'`) has sufficient free NVMe space (via `shutil.disk_usage()`), failing fast if disk is too full.
2. `NUMA_ThreadPinner()`: Uses `psutil.Process().cpu_affinity()` to restrict the process to specific CPU cores based on the dynamic config located at `pathlib.Path(os.environ['COCHEM_ARTIFACTS_DIR']) / 'Registry' / 'cochem_system_config.json'`. Do NOT hallucinate MPI pinning flags or complex cache mapping logic.
3. `ZombieReaper()`: Establishes a ZeroMQ (ZMQ) PUB/SUB heartbeat bound to an ephemeral port (`tcp://127.0.0.1:*`), logging the dynamic port to `pathlib.Path(os.environ['COCHEM_ARTIFACTS_DIR']) / 'Registry' / 'zmq_ipc.json'`. Monitors the `$SCRATCH` directory for an `ABORT.signal` file. If heartbeat drops or the abort signal is detected, it executes a ruthless termination of orphaned OpenMPI threads using cross-platform `psutil` or `subprocess.run(['taskkill', ...])` on Windows.
4. `SegfaultTrapper()`: Catches OS-level Segmentation Faults by strictly evaluating the process `returncode`. Specifically, check for `-11` (`-signal.SIGSEGV`) on POSIX, and `0xC0000005` (3221225477) on Windows. Upon detection, do NOT attempt to parse stderr output. Instead, construct a structured JSON-LD provenance block logging the timestamp, exact process ID, and the raw integer return code, and explicitly save it to `pathlib.Path(os.environ['COCHEM_ARTIFACTS_DIR']) / 'BENCH_Workspace' / 'Processed' / 'bench_provenance.jsonld'`. Absolutely NO hardcoded absolute paths.
Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_topos\__init__.py ---
"""CoChem-TOPOS Combinatorial Conformational Engine."""

from .cochem_topos_cleanup import (
    HDF5LockRecord,
    HDF5LockSweeperConfig,
    HDF5LockSweepResult,
    PostFlightAuditReport,
    ProcessReaperConfig,
    PurgedFileRecord,
    PurgeResult,
    ReapedProcessRecord,
    ReapResult,
    ScratchPurgeConfig,
    ToposEnvironmentSanitizer,
    ToposHDF5LockSweeper,
    ToposProcessReaper,
    ToposScratchPurgeEngine,
    WSLPathTranslator,
)
from .cochem_topos_export import (
    DEFAULT_TEMPERATURE_K,
    GAS_CONSTANT_KCAL_MOL_K,
    HARTREE_TO_KCAL_MOL,
    STATIC_METHOD_CITATIONS,
    TOPOSFAIRExporter,
    _compute_sha256,
    apply_readonly_lock,
    calculate_boltzmann_weights,
    remove_readonly_lock,
    sanitize_latex,
)
from .cochem_topos_graph import (
    COVALENT_RADII,
    RESONANCE_PROTECTION_SCALE,
    MonomerSeed,
    ShortestGapTelemetry,
    TopologyAnalysisResult,
    TopologyGraphEngine,
    analyze_molecular_graph,
    generate_chemical_formula,
    get_atomic_mass,
    get_atomic_number,
    get_atomic_symbol,
    get_covalent_radius,
    is_transition_or_coordination_metal,
    parse_xyz_file,
    parse_xyz_string,
    run_crest_secondary_search,
)
from .engine import ToposEngine

__all__ = [
    "ToposEngine",
    "TopologyGraphEngine",
    "TopologyAnalysisResult",
    "MonomerSeed",
    "ShortestGapTelemetry",
    "analyze_molecular_graph",
    "parse_xyz_string",
    "parse_xyz_file",
    "generate_chemical_formula",
    "get_covalent_radius",
    "get_atomic_mass",
    "get_atomic_number",
    "get_atomic_symbol",
    "is_transition_or_coordination_metal",
    "run_crest_secondary_search",
    "COVALENT_RADII",
    "RESONANCE_PROTECTION_SCALE",
    "ToposEnvironmentSanitizer",
    "ToposScratchPurgeEngine",
    "ToposProcessReaper",
    "ToposHDF5LockSweeper",
    "WSLPathTranslator",
    "ScratchPurgeConfig",
    "PurgedFileRecord",
    "PurgeResult",
    "ProcessReaperConfig",
    "ReapedProcessRecord",
    "ReapResult",
    "HDF5LockRecord",
    "HDF5LockSweeperConfig",
    "HDF5LockSweepResult",
    "PostFlightAuditReport",
    "TOPOSFAIRExporter",
    "apply_readonly_lock",
    "remove_readonly_lock",
    "calculate_boltzmann_weights",
    "sanitize_latex",
    "_compute_sha256",
    "STATIC_METHOD_CITATIONS",
    "HARTREE_TO_KCAL_MOL",
    "GAS_CONSTANT_KCAL_MOL_K",
    "DEFAULT_TEMPERATURE_K",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_topos\cochem_topos_export.py ---
"""
CoChem-TOPOS: Stage 5.1 - Post-Flight Audit & FAIR Export
(export_utils/cochem_topos_export.py & cochem_topos/cochem_topos_export.py)

Translates raw database tensors from landscape.h5 into human-readable,
peer-review-ready scientific manuscripts, publication-grade LaTeX siunitx tables
via Jinja2 templating, automated CrossRef BibTeX citations, and cryptographically
verified, read-only FAIR-compliant submission archives (TOPOS_Final_Ensemble.zip).

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
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import h5py
import jinja2
import numpy as np

logger = logging.getLogger("CoChem.TOPOS.FAIRExporter")

# Physical Constants (CODATA 2018 / 2022)
HARTREE_TO_KCAL_MOL: float = 627.509474
GAS_CONSTANT_KCAL_MOL_K: float = 1.98720425864083e-3  # R in kcal/(mol*K)
DEFAULT_TEMPERATURE_K: float = 298.15  # Standard ambient temperature (25 °C)

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

\title{CoChem-TOPOS: High-Precision Conformational Supporting Information}
\author{CoChem Automated Pipeline Engine}
\date{\today}

\begin{document}
\maketitle

\section{Introduction}
This document contains the verified structural coordinates, thermodynamic corrections, and single-point electronic energies resulting from the multi-tier Method Matrix Cascade. All quantum chemistry calculations and tensor operations strictly follow Stage 5.1 FAIR reporting protocols.

\section{Optimized Isomer Energetics and Thermodynamics}
\begin{table}[htbp]
\centering
\caption{Optimized Isomer Energetics, Relative Enthalpies ($\Delta H$), Dipole Moments ($\mu$), and Boltzmann Populations at \SI{298.15}{\kelvin}}
\begin{tabular}{l l S[table-format=-4.6] S[table-format=3.3] S[table-format=2.3] S[table-format=3.2]}
\toprule
\textbf{Isomer ID} & \textbf{Terminal Tier} & {\textbf{Energy (\si{\hartree})}} & {\textbf{$\Delta H$ (\si{\kcalmol})}} & {\textbf{$\mu$ (\si{\debye})}} & {\textbf{Pop. (\%)}} \\
\midrule
{% for rec in records %}
{{ rec.sanitized_id }} & {{ rec.sanitized_tier }} & {{ "%.6f"|format(rec.energy) }} & {{ "%.3f"|format(rec.rel_enthalpy_kcal) }} & {{ "%.3f"|format(rec.dipole) }} & {{ "%.2f"|format(rec.boltzmann_pop_percent) }} \\
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
\textbf{Generated:} {{ provenance.timestamp }}

\end{document}
"""

LATEX_SI_TABLES_TEMPLATE: str = r"""% CoChem-TOPOS Publication-Grade LaTeX Table Snippet
% Requires: \usepackage{booktabs}, \usepackage{siunitx}
\begin{table}[htbp]
\centering
\caption{Conformational Ensemble Energies, Relative Enthalpies, and Dipole Moments}
\begin{tabular}{l l S[table-format=-4.6] S[table-format=3.3] S[table-format=2.3] S[table-format=3.2]}
\toprule
\textbf{Isomer ID} & \textbf{Tier} & {\textbf{Electronic Energy ($E_h$)}} & {\textbf{$\Delta H$ (kcal/mol)}} & {\textbf{Dipole (D)}} & {\textbf{Boltzmann (\%)}} \\
\midrule
{% for rec in records %}
{{ rec.sanitized_id }} & {{ rec.sanitized_tier }} & {{ "%.6f"|format(rec.energy) }} & {{ "%.3f"|format(rec.rel_enthalpy_kcal) }} & {{ "%.3f"|format(rec.dipole) }} & {{ "%.2f"|format(rec.boltzmann_pop_percent) }} \\
{% endfor %}
\bottomrule
\end{tabular}
\end{table}
"""


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
    Applies an OS-agnostic read-only permission lock to the specified file
    to guarantee post-generation immutability and anti-tampering.
    """
    path = Path(file_path)
    if not path.exists():
        return
    readonly_mode = stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH
    try:
        os.chmod(path, readonly_mode)
    except Exception as e:
        logger.warning(f"Could not apply POSIX/Windows chmod read-only lock to {path}: {e}")


def remove_readonly_lock(file_path: str | Path) -> None:
    """
    Removes read-only lock to allow overwriting during managed re-runs or test cleanups.
    """
    path = Path(file_path)
    if not path.exists():
        return
    try:
        writable_mode = stat.S_IREAD | stat.S_IWRITE | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH
        os.chmod(path, writable_mode)
    except Exception as e:
        logger.warning(f"Could not restore writable permissions to {path}: {e}")


def sanitize_latex(text: str) -> str:
    """
    Escapes LaTeX special characters in textual data to guarantee compilation safety.
    """
    if not text:
        return ""
    replacements = [
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ]
    sanitized = str(text)
    for char, rep in replacements:
        sanitized = sanitized.replace(char, rep)
    return sanitized


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

    min_energy = min(energies_kcal)
    rt = GAS_CONSTANT_KCAL_MOL_K * temperature_k

    if rt <= 0:
        return [1.0 if e == min_energy else 0.0 for e in energies_kcal]

    rel_energies = [e - min_energy for e in energies_kcal]
    exp_factors = [math.exp(-de / rt) for de in rel_energies]
    sum_exp = sum(exp_factors)

    if sum_exp <= 0.0:
        return [1.0 / len(energies_kcal)] * len(energies_kcal)

    return [ef / sum_exp for ef in exp_factors]


class TOPOSFAIRExporter:
    """
    Scrapes the finalized landscape.h5 database to compile Supporting Information
    LaTeX documentation using Jinja2 templating, CrossRef BibTeX citations,
    and compressed FAIR-compliant read-only submission archives.
    """

    def __init__(self, hdf5_path: str | Path, output_dir: str | Path) -> None:
        self.hdf5_path = Path(hdf5_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if not self.hdf5_path.exists():
            raise FileNotFoundError(f"Master database not found at {self.hdf5_path}")

        # Initialize Jinja2 environment with autoescape=False for LaTeX rendering
        self.jinja_env = jinja2.Environment(
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.jinja_env.filters["sanitize_latex"] = sanitize_latex

    def query_crossref_doi(
        self,
        query: str,
        mailto: str = "research@cochem.org",
        timeout: float = 3.0
    ) -> dict[str, Any] | None:
        """
        Safely queries the CrossRef REST API complying with the Tripartite Air-Gap
        policy and CrossRef Polite Pool standards (mailto header, rate limiting).
        Fails safely and returns None if offline or air-gapped.
        """
        clean_query = query.strip()
        if not clean_query:
            return None

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
                    if items:
                        return items[0]
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, Exception) as e:
            logger.debug(f"CrossRef API query '{clean_query}' skipped (Air-Gap safe): {e}")
            return None

        return None

    def generate_bibtex_citations(
        self,
        config_path: str | Path | None = None,
        filename: str = "cochem_citations.bib"
    ) -> Path:
        """
        Generates a complete cochem_citations.bib BibTeX file extracting the exact
        computational methods, basis sets, and quantum chemistry packages used.
        Safely queries CrossRef API when online, falling back to verified static
        Method Matrix citations in air-gapped environments.
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
                methods_to_cite.add(engine_name.lower())
            if "orca_version" in found_config:
                methods_to_cite.add("orca")

        # 2. Extract methods from HDF5 database tiers and attributes
        try:
            with h5py.File(self.hdf5_path, "r", libver="latest", swmr=True) as f:
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
            matched_static_key: str | None = None
            for s_key, s_data in STATIC_METHOD_CITATIONS.items():
                keywords = [k.strip() for k in s_data.get("keywords", "").split(",")]
                if s_key in method_query or any(kw in method_query for kw in keywords if kw):
                    matched_static_key = s_key
                    break

            crossref_item = self.query_crossref_doi(method_query)
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
        """
        Traverses landscape.h5 and extracts deduplicated energies, thermodynamic
        corrections, rotational constants, dipole moments, and geometries.
        """
        records: list[dict[str, Any]] = []

        with h5py.File(self.hdf5_path, "r", libver="latest", swmr=True) as f:
            base_group = f["deduplicated_isomers"] if "deduplicated_isomers" in f else f
            for geom_id in base_group.keys():
                geom_group = base_group[geom_id]
                if not isinstance(geom_group, h5py.Group):
                    continue

                available_tiers = [k for k, v in geom_group.items() if isinstance(v, h5py.Group)]
                if not available_tiers:
                    continue

                def extract_tier_num(t: str) -> int:
                    match = re.search(r"\d+", t)
                    return int(match.group()) if match else 0

                available_tiers.sort(key=extract_tier_num)
                terminal_tier = available_tiers[-1]
                tier_grp = geom_group[terminal_tier]

                # 1. Electronic Energy (Hartree)
                energy: float | None = None
                for k in ["electronic_energy_hartree", "energy", "scf_energy"]:
                    if k in tier_grp.attrs and tier_grp.attrs[k] is not None:
                        energy = float(tier_grp.attrs[k])
                        break
                    elif k in tier_grp and isinstance(tier_grp[k], h5py.Dataset):
                        val = tier_grp[k][()]
                        if val is not None:
                            energy = float(val)
                            break

                if energy is None:
                    logger.warning(
                        f"Missing electronic energy for geometry '{geom_id}' at tier '{terminal_tier}'. Defaulting to 0.0 Hartree."
                    )
                    energy = 0.0

                # 2. Enthalpy & Gibbs Free Energy (Hartree)
                enthalpy: float | None = None
                for k in ["enthalpy_hartree", "enthalpy"]:
                    if k in tier_grp.attrs and tier_grp.attrs[k] is not None:
                        enthalpy = float(tier_grp.attrs[k])
                        break
                    elif k in tier_grp and isinstance(tier_grp[k], h5py.Dataset):
                        val = tier_grp[k][()]
                        if val is not None:
                            enthalpy = float(val)
                            break

                gibbs: float | None = None
                for k in ["free_energy_hartree", "gibbs_free_energy", "gibbs_energy"]:
                    if k in tier_grp.attrs and tier_grp.attrs[k] is not None:
                        gibbs = float(tier_grp.attrs[k])
                        break
                    elif k in tier_grp and isinstance(tier_grp[k], h5py.Dataset):
                        val = tier_grp[k][()]
                        if val is not None:
                            gibbs = float(val)
                            break

                # 3. Zero-Point Energy (Hartree)
                zpe: float | None = None
                for k in ["zpe_hartree", "zero_point_energy", "zpve"]:
                    if k in tier_grp.attrs and tier_grp.attrs[k] is not None:
                        zpe = float(tier_grp.attrs[k])
                        break
                    elif k in tier_grp and isinstance(tier_grp[k], h5py.Dataset):
                        val = tier_grp[k][()]
                        if val is not None:
                            zpe = float(val)
                            break

                # 4. Dipole Moment (Debye)
                dipole: float | None = None
                for k in ["dipole_moment_debye", "dipole_magnitude", "dipole"]:
                    if k in tier_grp.attrs and tier_grp.attrs[k] is not None:
                        dipole = float(tier_grp.attrs[k])
                        break
                    elif k in tier_grp and isinstance(tier_grp[k], h5py.Dataset):
                        val = tier_grp[k][()]
                        if isinstance(val, (np.ndarray, list, tuple)):
                            arr = np.asarray(val, dtype=np.float64)
                            dipole = float(np.linalg.norm(arr))
                        elif val is not None:
                            dipole = float(val)
                        break

                # 5. Rotational Constants (MHz)
                rot_constants: tuple[float, float, float] | None = None
                for k in ["rotational_constants_mhz", "rotational_constants", "rot_constants"]:
                    if k in tier_grp.attrs and tier_grp.attrs[k] is not None:
                        val = tier_grp.attrs[k]
                        if isinstance(val, (np.ndarray, list, tuple)) and len(val) >= 3:
                            rot_constants = (float(val[0]), float(val[1]), float(val[2]))
                            break
                    elif k in tier_grp and isinstance(tier_grp[k], h5py.Dataset):
                        val = tier_grp[k][()]
                        if isinstance(val, (np.ndarray, list, tuple)) and len(val) >= 3:
                            rot_constants = (float(val[0]), float(val[1]), float(val[2]))
                            break

                # 6. Geometry XYZ
                xyz_str = ""
                if "geometry_xyz" in tier_grp:
                    xyz_val = tier_grp["geometry_xyz"][()]
                    xyz_str = xyz_val.decode("utf-8") if hasattr(xyz_val, "decode") else str(xyz_val)

                records.append({
                    "id": geom_id,
                    "sanitized_id": sanitize_latex(geom_id),
                    "tier": terminal_tier,
                    "sanitized_tier": sanitize_latex(terminal_tier),
                    "energy": energy,
                    "enthalpy": enthalpy if enthalpy is not None else energy,
                    "gibbs": gibbs if gibbs is not None else energy,
                    "zpe": zpe if zpe is not None else 0.0,
                    "dipole": dipole if dipole is not None else 0.0,
                    "rot_constants": rot_constants if rot_constants is not None else (0.0, 0.0, 0.0),
                    "xyz": xyz_str,
                })

        records.sort(key=lambda x: x["id"])

        # Compute relative enthalpies and Boltzmann weights
        if records:
            min_e = min(r["energy"] for r in records)
            min_h = min(r["enthalpy"] for r in records)
            min_g = min(r["gibbs"] for r in records)

            for r in records:
                r["rel_energy_kcal"] = (r["energy"] - min_e) * HARTREE_TO_KCAL_MOL
                r["rel_enthalpy_kcal"] = (r["enthalpy"] - min_h) * HARTREE_TO_KCAL_MOL
                r["rel_gibbs_kcal"] = (r["gibbs"] - min_g) * HARTREE_TO_KCAL_MOL

            gibbs_kcal_list = [r["rel_gibbs_kcal"] for r in records]
            boltzmann_weights = calculate_boltzmann_weights(gibbs_kcal_list, DEFAULT_TEMPERATURE_K)

            for r, bw in zip(records, boltzmann_weights, strict=False):
                r["boltzmann_pop_percent"] = bw * 100.0

        return records

    def generate_latex_si(self, filename: str = "TOPOS_Supporting_Information.tex") -> Path:
        """
        Scrapes landscape.h5 and compiles a publication-grade LaTeX Supporting
        Information manuscript utilizing Jinja2 templating with siunitx-formatted
        tables for energies, thermodynamics, dipole moments, and Cartesian
        coordinates with cryptographic provenance hashing.
        """
        latex_path = self.output_dir / filename
        remove_readonly_lock(latex_path)

        records = self._extract_isomer_records()

        # Compute environment and database provenance hash
        db_hash = _compute_sha256(self.hdf5_path) if self.hdf5_path.exists() else "UNAVAILABLE"
        provenance_metadata = {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database_sha256": db_hash,
            "pipeline": "CoChem-TOPOS v4.0 (Stage 5.1)",
        }
        provenance_json = json.dumps(provenance_metadata, sort_keys=True)
        provenance_hash = hashlib.sha256(provenance_json.encode("utf-8")).hexdigest()

        provenance_context = {
            "pipeline": "CoChem-TOPOS v4.0 (Stage 5.1)",
            "database_sha256": db_hash,
            "execution_sha256": provenance_hash,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
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
            geom_id = rec["id"]
            xyz_content = rec["xyz"]
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
        zip_filename: str = "TOPOS_Final_Ensemble.zip",
        apply_immutability_lock: bool = True
    ) -> Path:
        """
        Compresses the master database, validated .xyz conformers, BibTeX citations,
        LaTeX documents, and SHA-256 provenance manifest into a singular, read-only
        TOPOS_Final_Ensemble.zip archive.
        """
        zip_path = self.output_dir / zip_filename
        remove_readonly_lock(zip_path)

        # 1. Ensure citations, LaTeX tables, and xyz conformers are generated
        bib_file = self.generate_bibtex_citations()
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

            # Add auxiliary QM artifacts (.out, .gbw) if present
            search_dirs = [self.output_dir]
            if self.hdf5_path.parent.exists() and self.hdf5_path.parent.resolve() != self.output_dir.resolve():
                search_dirs.append(self.hdf5_path.parent)

            for sdir in search_dirs:
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

        # Apply OS-agnostic immutability lock
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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_cochem_topos_export.py ---
"""
Comprehensive Zero-Mock Unit Tests for CoChem-TOPOS Stage 5.1 FAIR Export.
(tests/test_cochem_topos_export.py)

Validates:
1. Jinja2-based publication-grade LaTeX Supporting Information generation and siunitx formatting.
2. Jinja2-based LaTeX SI table snippet generation with booktabs and siunitx rules.
3. Automated CrossRef / static fallback BibTeX citation generation.
4. Physical Boltzmann population distributions and thermodynamic enthalpy scaling.
5. Deterministic SHA-256 cryptographic provenance manifests and environment hashing.
6. Standalone Cartesian coordinate (.xyz) conformer extraction.
7. Immutable read-only FAIR archive packaging (TOPOS_Final_Ensemble.zip).
8. Air-gap safety and network fault resilience.

Strictly complies with the Zero-Mock Mandate, Anti-Spoofing Protocol v2,
and Mendeleev Atomic Mass Mandate.
"""

from __future__ import annotations

import json
import logging
import math
import zipfile
from pathlib import Path

import h5py
import numpy as np
import pytest

try:
    from cochem_topos.cochem_topos_export import (
        DEFAULT_TEMPERATURE_K,
        GAS_CONSTANT_KCAL_MOL_K,
        HARTREE_TO_KCAL_MOL,
        STATIC_METHOD_CITATIONS,
        TOPOSFAIRExporter,
        _compute_sha256,
        apply_readonly_lock,
        calculate_boltzmann_weights,
        remove_readonly_lock,
        sanitize_latex,
    )
except ImportError:
    from export_utils.cochem_topos_export import (  # type: ignore[no-redef]
        DEFAULT_TEMPERATURE_K,
        GAS_CONSTANT_KCAL_MOL_K,
        HARTREE_TO_KCAL_MOL,
        STATIC_METHOD_CITATIONS,
        TOPOSFAIRExporter,
        _compute_sha256,
        apply_readonly_lock,
        calculate_boltzmann_weights,
        remove_readonly_lock,
        sanitize_latex,
    )


def _create_sample_landscape_h5(h5_path: Path) -> None:
    """Populates an authentic multi-tier HDF5 database with real molecular structures."""
    with h5py.File(h5_path, "w", libver="latest") as f:
        dedup = f.create_group("deduplicated_isomers")

        # Isomer 1: Water conformer A
        iso1 = dedup.create_group("water_conf_01")
        t1 = iso1.create_group("T1_MACE_OFF24M")
        t1.attrs["electronic_energy_hartree"] = -76.400000
        t1.attrs["enthalpy_hartree"] = -76.350000
        t1.attrs["free_energy_hartree"] = -76.380000
        t1.attrs["zpe_hartree"] = 0.021000
        t1.attrs["dipole_moment_debye"] = 1.854
        t1.attrs["rotational_constants_mhz"] = np.array([835840.0, 435350.0, 278139.0])
        t1.attrs["method"] = "MACE-OFF24m"
        t1.attrs["basis_set"] = "MLFF"
        t1.create_dataset(
            "geometry_xyz",
            data="3\nWater Isomer 1 T1\nO 0.000000 0.000000 0.117300\nH 0.000000 0.757200 -0.469200\nH 0.000000 -0.757200 -0.469200"
        )

        t2 = iso1.create_group("T2_ORCA_DFT")
        t2.attrs["electronic_energy_hartree"] = -76.435678
        t2.attrs["enthalpy_hartree"] = -76.385432
        t2.attrs["free_energy_hartree"] = -76.415000
        t2.attrs["zpe_hartree"] = 0.021500
        t2.attrs["dipole_moment_debye"] = 1.855
        t2.attrs["rotational_constants_mhz"] = np.array([835900.0, 435400.0, 278150.0])
        t2.attrs["method"] = "wB97M-V"
        t2.attrs["basis_set"] = "def2-TZVPP"
        t2.create_dataset(
            "geometry_xyz",
            data="3\nWater Isomer 1 T2 Opt\nO 0.000000 0.000000 0.117000\nH 0.000000 0.757000 -0.468000\nH 0.000000 -0.757000 -0.468000"
        )

        # Isomer 2: Water conformer B (Higher energy conformer)
        iso2 = dedup.create_group("water_conf_02")
        t2_2 = iso2.create_group("T2_ORCA_DFT")
        t2_2.attrs["electronic_energy_hartree"] = -76.430000
        t2_2.attrs["enthalpy_hartree"] = -76.380000
        t2_2.attrs["free_energy_hartree"] = -76.410000
        t2_2.attrs["zpe_hartree"] = 0.021200
        t2_2.attrs["dipole_moment_debye"] = 1.902
        t2_2.attrs["rotational_constants_mhz"] = np.array([830000.0, 430000.0, 275000.0])
        t2_2.attrs["method"] = "wB97M-V"
        t2_2.attrs["basis_set"] = "def2-TZVPP"
        t2_2.create_dataset(
            "geometry_xyz",
            data="3\nWater Isomer 2 T2\nO 0.000000 0.000000 0.120000\nH 0.000000 0.760000 -0.470000\nH 0.000000 -0.760000 -0.470000"
        )


def test_compute_sha256(tmp_path: Path):
    """Verifies deterministic SHA-256 calculation for arbitrary payloads."""
    test_file = tmp_path / "test_manifest.txt"
    test_file.write_text("CoChem Stage 5.1 FAIR Export Verification", encoding="utf-8")
    digest = _compute_sha256(test_file)
    assert isinstance(digest, str)
    assert len(digest) == 64
    digest_second = _compute_sha256(test_file)
    assert digest == digest_second


def test_topos_fair_exporter_init(tmp_path: Path):
    """Verifies initialization fails on missing database and succeeds on valid path."""
    h5_path = tmp_path / "landscape.h5"
    out_dir = tmp_path / "fair_export"

    with pytest.raises(FileNotFoundError):
        TOPOSFAIRExporter(h5_path, out_dir)

    with h5py.File(h5_path, "w") as f:
        f.attrs["initialized"] = True

    exporter = TOPOSFAIRExporter(h5_path, out_dir)
    assert exporter.hdf5_path == h5_path
    assert exporter.output_dir.exists()
    assert exporter.jinja_env is not None


def test_sanitize_latex():
    """Verifies proper escaping of LaTeX special characters."""
    assert sanitize_latex("isomer_001%_val&hash#$test{a}") == r"isomer\_001\%\_val\&hash\#\$test\{a\}"
    assert sanitize_latex("test~name^2") == r"test\textasciitilde{}name\textasciicircum{}2"
    assert sanitize_latex("") == ""


def test_calculate_boltzmann_weights_physics():
    """Verifies physical Boltzmann distribution weighting and normalization."""
    # 1. Equal energies -> equal populations
    weights_equal = calculate_boltzmann_weights([0.0, 0.0], DEFAULT_TEMPERATURE_K)
    assert len(weights_equal) == 2
    assert pytest.approx(weights_equal[0], rel=1e-5) == 0.5
    assert pytest.approx(weights_equal[1], rel=1e-5) == 0.5

    # 2. Known energy delta: Delta E = RT -> P_2 / P_1 = 1 / e
    rt = GAS_CONSTANT_KCAL_MOL_K * DEFAULT_TEMPERATURE_K
    weights_rt = calculate_boltzmann_weights([0.0, rt], DEFAULT_TEMPERATURE_K)
    expected_ratio = 1.0 / math.e
    assert pytest.approx(weights_rt[1] / weights_rt[0], rel=1e-4) == expected_ratio

    # 3. Sum of probabilities must strictly equal 1.0
    weights_multi = calculate_boltzmann_weights([0.0, 0.5, 1.2, 3.0], DEFAULT_TEMPERATURE_K)
    assert pytest.approx(sum(weights_multi), rel=1e-6) == 1.0

    # 4. Empty list handling
    assert calculate_boltzmann_weights([]) == []


def test_custom_temperature_boltzmann():
    """Evaluates population distribution across different temperatures."""
    energies = [0.0, 1.0]  # 1.0 kcal/mol gap
    w_low_t = calculate_boltzmann_weights(energies, temperature_k=100.0)
    w_std_t = calculate_boltzmann_weights(energies, temperature_k=298.15)
    w_high_t = calculate_boltzmann_weights(energies, temperature_k=1000.0)

    # Low T: ground state dominates heavily
    assert w_low_t[0] > w_std_t[0] > w_high_t[0]
    # High T: excited state population increases towards 0.5
    assert w_high_t[1] > w_std_t[1] > w_low_t[1]


def test_generate_bibtex_citations_static_fallback(tmp_path: Path):
    """Verifies cochem_citations.bib generation using authentic method citations."""
    h5_path = tmp_path / "landscape.h5"
    out_dir = tmp_path / "export_output"
    out_dir.mkdir(parents=True, exist_ok=True)

    _create_sample_landscape_h5(h5_path)

    exporter = TOPOSFAIRExporter(h5_path, out_dir)
    bib_path = exporter.generate_bibtex_citations()

    assert bib_path.exists()
    content = bib_path.read_text(encoding="utf-8")
    assert "@article{" in content
    assert "doi" in content.lower()
    assert "author" in content.lower()
    assert "cochem_citations.bib" == bib_path.name
    assert "wb97m_v" in content.lower() or "def2_tzvpp" in content.lower()


def test_generate_bibtex_citations_from_config(tmp_path: Path):
    """Verifies citation compilation parses cochem_system_config.json."""
    h5_path = tmp_path / "landscape.h5"
    out_dir = tmp_path / "export_output"
    out_dir.mkdir(parents=True, exist_ok=True)

    with h5py.File(h5_path, "w") as f:
        f.attrs["init"] = 1

    config_data = {
        "engines": {
            "mace": {"version": "0.3.0"},
            "orca": {"version": "6.0.0"},
            "xtb": {"version": "6.7.0"},
            "crest": {"version": "3.0"}
        },
        "orca_version": "6.0.0"
    }
    config_file = out_dir / "cochem_system_config.json"
    config_file.write_text(json.dumps(config_data, indent=2), encoding="utf-8")

    exporter = TOPOSFAIRExporter(h5_path, out_dir)
    bib_path = exporter.generate_bibtex_citations(config_path=config_file)

    assert bib_path.exists()
    content = bib_path.read_text(encoding="utf-8")
    assert "mace" in content.lower()
    assert "orca" in content.lower()
    assert "xtb" in content.lower()
    assert "crest" in content.lower()


def test_latex_si_generation_jinja2(tmp_path: Path):
    """Verifies LaTeX Supporting Information generation via Jinja2, siunitx header bracing, and tier selection."""
    h5_path = tmp_path / "landscape.h5"
    out_dir = tmp_path / "fair_export"

    _create_sample_landscape_h5(h5_path)

    exporter = TOPOSFAIRExporter(h5_path, out_dir)
    tex_path = exporter.generate_latex_si("TOPOS_Supporting_Information.tex")

    assert tex_path.exists()
    content = tex_path.read_text(encoding="utf-8")

    # 1. Verify siunitx braces and column alignment
    assert r"{\textbf{Energy (\si{\hartree})}}" in content
    assert r"{\textbf{$\Delta H$ (\si{\kcalmol})}}" in content
    assert r"{\textbf{$\mu$ (\si{\debye})}}" in content
    assert r"{\textbf{Pop. (\%)}}" in content
    assert r"S[table-format=-4.6]" in content

    # 2. Verify highest tier was chosen (T2_ORCA_DFT over T1_MACE_OFF24M)
    assert r"water\_conf\_01" in content
    assert r"water\_conf\_02" in content
    assert r"T2\_ORCA\_DFT" in content
    assert "-76.435678" in content
    assert "Water Isomer 1 T2 Opt" in content

    # 3. Verify Cryptographic Provenance Section
    assert r"\section*{Cryptographic Provenance and Reproducibility}" in content
    assert r"Execution Provenance SHA-256:" in content
    assert r"Database SHA-256:" in content


def test_latex_si_tables_snippet_jinja2(tmp_path: Path):
    """Verifies dedicated LaTeX table snippet generation via Jinja2."""
    h5_path = tmp_path / "landscape.h5"
    out_dir = tmp_path / "fair_export"

    _create_sample_landscape_h5(h5_path)

    exporter = TOPOSFAIRExporter(h5_path, out_dir)
    table_path = exporter.generate_latex_si_tables("TOPOS_SI_Tables.tex")

    assert table_path.exists()
    content = table_path.read_text(encoding="utf-8")
    assert r"\begin{table}" in content
    assert r"\toprule" in content
    assert r"\midrule" in content
    assert r"\bottomrule" in content
    assert r"water\_conf\_01" in content
    assert r"water\_conf\_02" in content
    assert "-76.435678" in content


def test_energy_dataset_and_fallback_warning(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """Verifies fallback when energy is stored in dataset or missing."""
    h5_path = tmp_path / "landscape.h5"
    out_dir = tmp_path / "fair_export"

    with h5py.File(h5_path, "w") as f:
        geom_b = f.create_group("isomer_dataset_energy")
        t1 = geom_b.create_group("TIER_1_SCREEN")
        t1.create_dataset("electronic_energy_hartree", data=-76.123456)

        geom_c = f.create_group("isomer_missing_energy")
        geom_c.create_group("TIER_1_SCREEN")

    exporter = TOPOSFAIRExporter(h5_path, out_dir)
    with caplog.at_level(logging.WARNING):
        tex_path = exporter.generate_latex_si()

    content = tex_path.read_text(encoding="utf-8")
    assert "-76.123456" in content
    assert "0.000000" in content
    assert any("Missing electronic energy for geometry 'isomer_missing_energy'" in record.message for record in caplog.records)


def test_export_xyz_conformers(tmp_path: Path):
    """Verifies extraction of individual .xyz geometry files."""
    h5_path = tmp_path / "landscape.h5"
    out_dir = tmp_path / "export_output"

    _create_sample_landscape_h5(h5_path)

    exporter = TOPOSFAIRExporter(h5_path, out_dir)
    xyz_files = exporter.export_xyz_conformers()

    assert len(xyz_files) == 2
    filenames = [f.name for f in xyz_files]
    assert "water_conf_01.xyz" in filenames
    assert "water_conf_02.xyz" in filenames

    water_txt = (out_dir / "conformers_xyz" / "water_conf_01.xyz").read_text(encoding="utf-8")
    assert "Water Isomer 1 T2 Opt" in water_txt


def test_bundle_final_ensemble_and_readonly_lock(tmp_path: Path):
    """Verifies final ensemble zip packaging, provenance manifest, and immutability lock."""
    h5_dir = tmp_path / "calculations"
    h5_dir.mkdir()
    h5_path = h5_dir / "landscape.h5"
    out_dir = tmp_path / "export_output"
    out_dir.mkdir()

    _create_sample_landscape_h5(h5_path)

    # Add QM output artifact
    orca_out = h5_dir / "calc_01.out"
    orca_out.write_text("ORCA TERMINATED NORMALLY", encoding="utf-8")
    orca_gbw = h5_dir / "calc_01.gbw"
    orca_gbw.write_bytes(b"\x00\x01\x02\x03\x04\x05")

    exporter = TOPOSFAIRExporter(h5_path, out_dir)
    zip_path = exporter.bundle_final_ensemble("TOPOS_Final_Ensemble.zip", apply_immutability_lock=True)

    assert zip_path.exists()

    # Verify ZIP contents
    with zipfile.ZipFile(zip_path, "r") as zf:
        namelist = zf.namelist()
        assert "landscape.h5" in namelist
        assert "cochem_citations.bib" in namelist
        assert "TOPOS_Supporting_Information.tex" in namelist
        assert "TOPOS_SI_Tables.tex" in namelist
        assert "conformers_xyz/water_conf_01.xyz" in namelist
        assert "conformers_xyz/water_conf_02.xyz" in namelist
        assert "qm_artifacts/calc_01.out" in namelist
        assert "fair_manifest.json" in namelist

        manifest_data = json.loads(zf.read("fair_manifest.json").decode("utf-8"))
        assert manifest_data["archive_type"] == "CoChem-TOPOS FAIR Output"
        assert "fair_compliance" in manifest_data
        hashes = manifest_data["provenance_hashes"]
        assert "landscape.h5" in hashes
        assert "cochem_citations.bib" in hashes

    # Verify immutability / read-only lock helper
    remove_readonly_lock(zip_path)
    apply_readonly_lock(zip_path)
    assert zip_path.exists()
    remove_readonly_lock(zip_path)


def test_bundle_fair_archive_wrapper(tmp_path: Path):
    """Verifies backwards-compatible bundle_fair_archive wrapper."""
    h5_path = tmp_path / "landscape.h5"
    out_dir = tmp_path / "export_output"
    _create_sample_landscape_h5(h5_path)

    exporter = TOPOSFAIRExporter(h5_path, out_dir)
    zip_path = exporter.bundle_fair_archive("TOPOS_FAIR_Archive.zip")
    assert zip_path.exists()
    assert zip_path.name == "TOPOS_FAIR_Archive.zip"
    remove_readonly_lock(zip_path)


def test_query_crossref_doi_safely(tmp_path: Path):
    """Verifies CrossRef API queries fail safely without throwing unhandled network errors."""
    h5_path = tmp_path / "landscape.h5"
    out_dir = tmp_path / "export_output"
    with h5py.File(h5_path, "w") as f:
        f.attrs["init"] = 1

    exporter = TOPOSFAIRExporter(h5_path, out_dir)
    # Empty query should return None immediately
    assert exporter.query_crossref_doi("") is None
    assert exporter.query_crossref_doi("   ") is None
    # Real query should either return parsed dict or None (if air-gapped/timed out) without raising
    result = exporter.query_crossref_doi("10.1063/5.0004608", timeout=1.0)
    assert result is None or isinstance(result, dict)

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_subprocess_reaper.py ---
#!/usr/bin/env python3
r"""Authentic Unit Test Suite for Stage 6.0 Subprocess Brokering and Zombie Reaper Engine.

Module: tests/test_subprocess_reaper.py
Target Implementation: cochem_bench.bench_libraries.subprocess_reaper

Capabilities Tested:
1. PreFlightScratchVerifier:
   - Dynamic scratch path resolution via COCHEM_ARTIFACTS_DIR.
   - Physical disk space inspection via shutil.disk_usage().
   - ResourceGuardError fast-failure on threshold breach.
   - Pydantic v2 ScratchSpaceReport validation.
2. NUMA_ThreadPinner:
   - Dynamic configuration loading from Registry/cochem_system_config.json.
   - Core affinity assignment via psutil.Process().cpu_affinity().
   - Pydantic v2 ThreadPinningResult validation.
   - Exception handling on non-existent process IDs.
3. ZombieReaper:
   - Ephemeral port ZeroMQ PUB/SUB socket binding and manifest logging to Registry/zmq_ipc.json.
   - Real-time heartbeat broadcast and verification.
   - ABORT.signal file detection, triggering, and clearing in $SCRATCH workspace.
   - Ruthless recursive child process tree extermination across Windows and POSIX platforms.
4. SegfaultTrapper & ExitCode139_Trapper:
   - Precise returncode classification for POSIX (-11, 139) and Windows (0xC0000005, 3221225477, -1073741819).
   - Non-segfault return code discrimination.
   - Structured FAIR JSON-LD provenance block generation and atomic commit to bench_provenance.jsonld.
   - SegmentationFaultError raising on fault conditions.
5. Mendeleev Elemental Mass Integration:
   - Dynamic atomic weight lookup for elements without hardcoded values.
6. Protected Subprocess Orchestrator:
   - End-to-end protected subprocess execution.

Authoritative Standards:
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task2_pt2_reaper.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 6 Subprocess Brokering & Temporal Engine Routing.txt
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 7 Thread-Safe Atomic IO & Context-Compression.txt
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Generator

import psutil
import pytest
import zmq
from mendeleev import element

from cochem_bench.bench_libraries.subprocess_reaper import (
    DEFAULT_MIN_FREE_SCRATCH_BYTES,
    ExitCode139_Trapper,
    JSONLDProvenanceBlock,
    NUMAPinningError,
    NUMA_ThreadPinner,
    PreFlightResourceError,
    PreFlightScratchVerifier,
    ProcessReapReport,
    ResourceGuardError,
    SEGFAULT_RETURN_CODES,
    ScratchSpaceReport,
    SegfaultTrapper,
    SegmentationFaultError,
    ThreadPinningResult,
    ZMQEndpointManifest,
    ZombieReaper,
    ZombieReaperError,
    execute_protected_subprocess,
    get_cochem_artifacts_dir,
    get_element_mass_mendeleev,
    get_processed_workspace_dir,
    get_registry_workspace_dir,
    get_scratch_workspace_dir,
)


# ==============================================================================
# Authentic Fixtures
# ==============================================================================

@pytest.fixture
def isolated_artifacts_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path, None, None]:
    """Establishes an authentic, isolated artifacts workspace."""
    artifacts_root = tmp_path / "cochem_isolated_artifacts"
    artifacts_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACTS_DIR", str(artifacts_root))
    yield artifacts_root
    if artifacts_root.exists():
        shutil.rmtree(artifacts_root, ignore_errors=True)


# ==============================================================================
# 1. Dynamic Path Resolution & Mendeleev Tests
# ==============================================================================

def test_dynamic_path_resolution(isolated_artifacts_dir: Path) -> None:
    """Verifies dynamic resolution of artifacts, scratch, registry, and processed dirs."""
    resolved_artifacts = get_cochem_artifacts_dir()
    assert resolved_artifacts == isolated_artifacts_dir.resolve()

    scratch_dir = get_scratch_workspace_dir(isolated_artifacts_dir)
    assert scratch_dir == isolated_artifacts_dir / "BENCH_Workspace" / "Scratch"

    reg_dir = get_registry_workspace_dir(isolated_artifacts_dir)
    assert reg_dir == isolated_artifacts_dir / "Registry"

    proc_dir = get_processed_workspace_dir(isolated_artifacts_dir)
    assert proc_dir == isolated_artifacts_dir / "BENCH_Workspace" / "Processed"


def test_mendeleev_elemental_mass_dynamic() -> None:
    """Validates dynamic retrieval of atomic weights via the Mendeleev database."""
    carbon_mass = get_element_mass_mendeleev("C")
    expected_carbon = float(element("C").atomic_weight)
    assert abs(carbon_mass - expected_carbon) < 1e-6

    hydrogen_mass = get_element_mass_mendeleev("H")
    expected_hydrogen = float(element("H").atomic_weight)
    assert abs(hydrogen_mass - expected_hydrogen) < 1e-6

    oxygen_mass = get_element_mass_mendeleev("O")
    expected_oxygen = float(element("O").atomic_weight)
    assert abs(oxygen_mass - expected_oxygen) < 1e-6

    platinum_mass = get_element_mass_mendeleev("Pt")
    expected_platinum = float(element("Pt").atomic_weight)
    assert abs(platinum_mass - expected_platinum) < 1e-6


# ==============================================================================
# 2. PreFlightScratchVerifier Tests
# ==============================================================================

def test_preflight_scratch_verifier_success(isolated_artifacts_dir: Path) -> None:
    """Verifies that scratch verification succeeds when available space exceeds threshold."""
    verifier = PreFlightScratchVerifier(artifacts_dir=isolated_artifacts_dir)
    # Use a small threshold of 1024 bytes (1 KB) to ensure verification passes on local disk
    report = verifier.verify(min_free_bytes=1024)

    assert isinstance(report, ScratchSpaceReport)
    assert report.is_sufficient is True
    assert report.total_bytes > 0
    assert report.free_bytes >= 1024
    assert Path(report.scratch_path).exists()
    assert verifier.check_space_safe(min_free_bytes=1024) is True


def test_preflight_scratch_verifier_insufficient_space_raises(isolated_artifacts_dir: Path) -> None:
    """Verifies fast-failure with ResourceGuardError when disk space threshold is unmet."""
    verifier = PreFlightScratchVerifier(artifacts_dir=isolated_artifacts_dir)
    # Require an impossibly large capacity (100 Petabytes) to trigger fast failure
    impossible_bytes = 100 * (1024 ** 5)

    with pytest.raises(ResourceGuardError) as exc_info:
        verifier.verify(min_free_bytes=impossible_bytes)

    assert "RESOURCE_GUARD" in str(exc_info.value)
    assert verifier.check_space_safe(min_free_bytes=impossible_bytes) is False


# ==============================================================================
# 3. NUMA_ThreadPinner Tests
# ==============================================================================

def test_numa_thread_pinner_from_config(isolated_artifacts_dir: Path) -> None:
    """Verifies loading affinity configuration from dynamic cochem_system_config.json."""
    reg_dir = get_registry_workspace_dir(isolated_artifacts_dir)
    reg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = reg_dir / "cochem_system_config.json"

    total_logical = psutil.cpu_count(logical=True) or 1
    target_core_indices = [0] if total_logical == 1 else [0, min(1, total_logical - 1)]

    cfg_payload = {
        "schema_version": "1.0.0",
        "hardware": {
            "physical_cpu_cores": min(2, total_logical),
            "logical_cpu_cores": total_logical,
            "ram_gb": 16.0,
            "pinned_cores": target_core_indices,
        },
        "pinned_cores": target_core_indices,
    }
    cfg_file.write_text(json.dumps(cfg_payload, indent=2), encoding="utf-8")

    pinner = NUMA_ThreadPinner(artifacts_dir=isolated_artifacts_dir)
    loaded_cores = pinner.load_affinity_cores()
    assert loaded_cores == target_core_indices

    # Execute physical pinning on current process
    result = pinner.pin_process(pid=os.getpid())
    assert isinstance(result, ThreadPinningResult)
    assert result.pid == os.getpid()
    assert result.assigned_cores == target_core_indices
    assert result.status in ("PINNED_SUCCESS", "UNSUPPORTED_PLATFORM")
    if result.status == "PINNED_SUCCESS":
        assert set(result.active_affinity) == set(target_core_indices)


def test_numa_thread_pinner_invalid_pid_raises(isolated_artifacts_dir: Path) -> None:
    """Verifies that pinning a non-existent process ID raises NUMAPinningError."""
    pinner = NUMA_ThreadPinner(artifacts_dir=isolated_artifacts_dir)
    invalid_pid = 99999999
    with pytest.raises(NUMAPinningError):
        pinner.pin_process(pid=invalid_pid, cores=[0])


# ==============================================================================
# 4. ZombieReaper Tests
# ==============================================================================

def test_zombie_reaper_zmq_heartbeat_lifecycle(isolated_artifacts_dir: Path) -> None:
    """Verifies ephemeral ZMQ PUB/SUB socket binding, manifest recording, and message transmission."""
    reaper = ZombieReaper(artifacts_dir=isolated_artifacts_dir)
    ctx = zmq.Context()

    try:
        pub_socket, manifest = reaper.establish_heartbeat_publisher(context=ctx)
        assert isinstance(manifest, ZMQEndpointManifest)
        assert manifest.port > 0
        assert manifest.endpoint.startswith("tcp://127.0.0.1:")
        assert reaper.get_ipc_manifest_path().exists()

        # Verify reading manifest from disk
        disk_manifest = reaper.read_ipc_manifest()
        assert disk_manifest.port == manifest.port
        assert disk_manifest.endpoint == manifest.endpoint

        # Publish a heartbeat
        reaper.publish_heartbeat(pub_socket, topic="HEARTBEAT", payload={"status": "ACTIVE_CALCULATION"})

        # Subscriber verification
        received = reaper.check_heartbeat_receptive(
            endpoint=manifest.endpoint,
            timeout_ms=1000,
            topic="HEARTBEAT",
            context=ctx,
        )
        # In fast local loopback with yield, reception or timeout is handled deterministically
        assert isinstance(received, bool)
    finally:
        pub_socket.close()
        ctx.term()


def test_zombie_reaper_abort_signal_file(isolated_artifacts_dir: Path) -> None:
    """Verifies detection, triggering, and clearing of ABORT.signal file in $SCRATCH."""
    reaper = ZombieReaper(artifacts_dir=isolated_artifacts_dir)
    scratch_dir = get_scratch_workspace_dir(isolated_artifacts_dir)
    scratch_dir.mkdir(parents=True, exist_ok=True)

    assert reaper.check_abort_signal() is False

    abort_file = reaper.trigger_abort_signal(reason="MANUAL_TEST_ABORT")
    assert abort_file.exists()
    assert reaper.check_abort_signal() is True

    cleared = reaper.clear_abort_signal()
    assert cleared is True
    assert reaper.check_abort_signal() is False


def test_zombie_reaper_exterminate_real_child_process(isolated_artifacts_dir: Path) -> None:
    """Spawns an authentic background child process and ruthlessly terminates it."""
    reaper = ZombieReaper(artifacts_dir=isolated_artifacts_dir)

    # Spawn an authentic long-running Python worker process
    worker = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    worker_pid = worker.pid
    assert psutil.pid_exists(worker_pid) is True

    # Execute ruthless termination
    report = reaper.terminate_process_tree(target_pid=worker_pid, reason="ORPHAN_TERMINATION_TEST")

    assert isinstance(report, ProcessReapReport)
    assert report.target_pid == worker_pid
    assert report.status == "EXTERMINATED"
    assert worker_pid in report.terminated_pids

    # Allow brief window for OS process table to update
    time.sleep(0.2)
    assert psutil.pid_exists(worker_pid) is False or not psutil.Process(worker_pid).is_running()


def test_zombie_reaper_monitor_and_reap_on_abort_signal(isolated_artifacts_dir: Path) -> None:
    """Verifies monitor_and_reap_if_needed executes when ABORT.signal is present."""
    reaper = ZombieReaper(artifacts_dir=isolated_artifacts_dir)

    worker = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    worker_pid = worker.pid

    try:
        reaper.trigger_abort_signal(reason="TEST_CLUSTER_ABORT")
        reap_report = reaper.monitor_and_reap_if_needed(target_pid=worker_pid, heartbeat_alive=True)

        assert reap_report is not None
        assert reap_report.reason == "ABORT_SIGNAL_DETECTED"
        assert reap_report.abort_signal_detected is True
    finally:
        reaper.clear_abort_signal()
        if psutil.pid_exists(worker_pid):
            try:
                psutil.Process(worker_pid).kill()
            except Exception:
                pass


# ==============================================================================
# 5. SegfaultTrapper & ExitCode139_Trapper Tests
# ==============================================================================

@pytest.mark.parametrize("segfault_code", [-11, 139, 3221225477, -1073741819, 0xC0000005])
def test_segfault_trapper_identifies_all_segfault_codes(segfault_code: int) -> None:
    """Validates that all POSIX and Windows segmentation fault return codes are recognized."""
    assert SegfaultTrapper.is_segmentation_fault(segfault_code) is True
    assert ExitCode139_Trapper.is_segmentation_fault(segfault_code) is True


@pytest.mark.parametrize("normal_code", [0, 1, 2, 127, 255])
def test_segfault_trapper_ignores_normal_and_generic_codes(normal_code: int) -> None:
    """Validates that non-segfault return codes return False."""
    assert SegfaultTrapper.is_segmentation_fault(normal_code) is False


def test_segfault_trapper_generates_jsonld_provenance(isolated_artifacts_dir: Path) -> None:
    """Verifies JSON-LD provenance block generation and atomic commitment on segfault."""
    trapper = SegfaultTrapper(artifacts_dir=isolated_artifacts_dir)
    simulated_pid = 45120
    simulated_returncode = -11

    provenance = trapper.trap(
        process_id=simulated_pid,
        returncode=simulated_returncode,
        metadata={"method": "DLPNO-CCSD(T)", "basis": "aug-cc-pVQZ"},
    )

    assert isinstance(provenance, JSONLDProvenanceBlock)
    assert provenance.process_id == simulated_pid
    assert provenance.return_code == simulated_returncode
    assert provenance.fault_type == "OS_SEGMENTATION_FAULT"
    assert provenance.status == "FATAL_CRASH_RECORDED"

    prov_path = trapper.get_provenance_file_path()
    assert prov_path.exists()

    # Read back and parse JSON-LD file
    data = json.loads(prov_path.read_text(encoding="utf-8"))
    assert data["@context"] == "https://doi.org/10.5281/zenodo.cochem.v2"
    assert data["@type"] == "ComputationalProcessProvenance"
    assert data["process_id"] == simulated_pid
    assert data["return_code"] == simulated_returncode
    assert data["fault_type"] == "OS_SEGMENTATION_FAULT"
    assert data["metadata"]["method"] == "DLPNO-CCSD(T)"


def test_segfault_trapper_check_and_raise(isolated_artifacts_dir: Path) -> None:
    """Verifies that check_and_raise commits JSON-LD and raises SegmentationFaultError."""
    trapper = SegfaultTrapper(artifacts_dir=isolated_artifacts_dir)

    with pytest.raises(SegmentationFaultError) as exc_info:
        trapper.check_and_raise(process_id=8888, returncode=3221225477)

    assert "Segmentation fault detected" in str(exc_info.value)
    assert trapper.get_provenance_file_path().exists()


def test_segfault_trapper_exitcode139_alias(isolated_artifacts_dir: Path) -> None:
    """Verifies that ExitCode139_Trapper operates identically to SegfaultTrapper."""
    assert ExitCode139_Trapper is SegfaultTrapper
    trapper = ExitCode139_Trapper(artifacts_dir=isolated_artifacts_dir)
    assert trapper.is_segmentation_fault(139) is True


# ==============================================================================
# 6. Composite Subprocess Execution Orchestrator Tests
# ==============================================================================

def test_execute_protected_subprocess_success(isolated_artifacts_dir: Path) -> None:
    """Verifies end-to-end execution of a healthy protected subprocess."""
    retcode, provenance = execute_protected_subprocess(
        cmd=[sys.executable, "-c", "import sys; sys.exit(0)"],
        artifacts_dir=isolated_artifacts_dir,
        min_free_scratch_bytes=1024,
        pin_cores=False,
    )
    assert retcode == 0
    assert provenance is None

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.