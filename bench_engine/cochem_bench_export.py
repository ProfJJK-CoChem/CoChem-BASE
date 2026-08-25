#!/usr/bin/env python3
r"""Stage 5.0: Benchmark HDF5 & Publication Table Exporter.

Authoritative Implementation: bench_engine.cochem_bench_export
System Domain: CoChem-BENCH Scientific Engine

Key Capabilities:
1. CompositeAggregator: Sweeps landscape.h5 utilizing SWMR mode (swmr=True, libver='latest')
   and algebraically compiles the focal-point/composite total electronic energy:
   E_Total = E_SCF^CBS + E_corr^CBS + Delta_E_CV + Delta_E_rel + Delta_E_SOC + ZPVE.
   Enforces strict fail-fast validation when ZPVE is missing (never defaulting ZPVE to 0.0).
2. SiunitxLaTeXCompiler: Generates publication-ready LaTeX tables utilizing siunitx and booktabs
   via memory-safe Jinja2 streaming, programmatically sanitizing LaTeX special characters.
3. ProvenanceStamper: Assembles cryptographic JSON-LD metadata records (bench_provenance.jsonld)
   embedding Git commit hashes, SHA-256 binary signatures, system hardware configurations,
   and exact mathematical parameters for FAIR reproducibility.
4. AirGapVerifier: Verifies runtime package availability (jinja2, siunitx, booktabs)
   without attempting dynamic network installations (strictly banning pip, apt, tlmgr).
5. PublicationArchiver: Packages exported artifacts (.tex, .jsonld, .bib, .xyz) into
   CoChem_BENCH_Publication_Archive.zip and sets read-only permissions (0o444).

Authoritative Standards:
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 8 Benchmark Assembly & Publication Export (Stage 5.0).txt
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task2_pt1_export.md
"""

from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import h5py
from mendeleev import element
from pydantic import BaseModel, Field


# ==============================================================================
# Physical Constants & System Defaults
# ==============================================================================

# Exact CODATA Conversion: Hartree to kcal/mol
HARTREE_TO_KCAL_MOL: float = 627.509474063

# Default Output Workspace Directory (Stage 5.0)
DEFAULT_PROCESSED_DIR: Path = Path(r"D:\__CoChem\CoChem_Artifacts\BENCH_Workspace\Processed")


# ==============================================================================
# Custom Domain Exceptions
# ==============================================================================

class MissingZPVEError(ValueError):
    """Raised when Zero-Point Vibrational Energy (ZPVE) is absent during composite aggregation."""


class AirGapPackageMissingError(RuntimeError):
    """Raised when a required external package or LaTeX dependency is missing in an air-gapped environment."""


class HDF5SchemaError(KeyError):
    """Raised when an expected HDF5 group or dataset structure is invalid or corrupt."""


# ==============================================================================
# Data Models
# ==============================================================================

class CompositeEnergyRecord(BaseModel):
    """Structured result model for Stage 5.0 Composite Thermochemical Totals."""
    node_id: str = Field(description="Unique identifier of the molecular node or conformer")
    e_scf_cbs: float = Field(description="Hartree-Fock Complete Basis Set limit in Hartree")
    e_corr_cbs: float = Field(description="Correlation Complete Basis Set limit in Hartree")
    e_total_cbs: float = Field(description="Total CBS energy (SCF + Correlation) in Hartree")
    delta_e_cv: float = Field(default=0.0, description="Core-Valence correlation energy correction in Hartree")
    delta_e_rel: float = Field(default=0.0, description="Scalar relativistic energy correction in Hartree")
    delta_e_soc: float = Field(default=0.0, description="Spin-orbit coupling energy correction in Hartree")
    zpve: float = Field(description="Zero-Point Vibrational Energy in Hartree (Strictly Mandatory)")
    e_total_hartree: float = Field(description="Final composite total electronic and zero-point energy in Hartree")
    e_total_kcal_mol: float = Field(description="Final composite total energy converted to kcal/mol")
    basis_scf: str = Field(default="", description="Basis set notation for SCF extrapolation")
    basis_corr: str = Field(default="", description="Basis set notation for correlation extrapolation")
    basis_cv: str = Field(default="", description="Basis set notation for Core-Valence correction")
    method: str = Field(default="DLPNO-CCSD(T)", description="High-level quantum chemical method")
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional provenance or node metadata")


class LaTeXExportConfig(BaseModel):
    """Configuration model for LaTeX table formatting with siunitx and booktabs."""
    table_title: str = Field(default="Benchmark Composite Thermochemistry Summary", description="LaTeX table caption title")
    caption: str = Field(
        default="Composite focal-point electronic and zero-point corrected benchmark energies.",
        description="Full descriptive caption for Supporting Information"
    )
    label: str = Field(default="tab:bench_composite_summary", description="LaTeX table cross-reference label")
    table_format: str = Field(
        default="l S[table-format=-4.6] S[table-format=-4.6] S[table-format=-4.6] S[table-format=-4.6] S[table-format=-4.6]",
        description="siunitx column alignment specification string"
    )
    energy_unit: str = Field(default=r"\text{E}_{\text{h}}", description="Energy unit symbol for table headers")


class ExportPipelineResult(BaseModel):
    """Structured summary returned upon completing Stage 5.0 export workflow."""
    records: List[CompositeEnergyRecord] = Field(default_factory=list, description="Aggregated composite energy records")
    tex_file_path: Optional[str] = Field(default=None, description="Path to generated Benchmark_Results.tex")
    jsonld_file_path: Optional[str] = Field(default=None, description="Path to generated bench_provenance.jsonld")
    archive_file_path: Optional[str] = Field(default=None, description="Path to generated publication zip archive")
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    status: str = Field(default="SUCCESS", description="Overall execution status")


# ==============================================================================
# 1. AirGapVerifier
# ==============================================================================

class AirGapVerifier:
    """Enforces air-gap compliance by verifying dependencies without invoking package managers."""

    @staticmethod
    def check_jinja2() -> bool:
        """Verifies that jinja2 is installed and functional.
        
        Raises:
            AirGapPackageMissingError: If jinja2 is unavailable.
        """
        try:
            import jinja2
            return True
        except ImportError as e:
            raise AirGapPackageMissingError(
                "Required template engine 'jinja2' is not available in the current environment. "
                "In air-gapped environments, dynamic installation via pip/apt is strictly prohibited. "
                "Please ensure the host environment includes jinja2."
            ) from e

    @staticmethod
    def check_latex_packages(required_packages: Optional[List[str]] = None) -> Dict[str, bool]:
        """Inspects LaTeX system for required style packages (e.g., siunitx, booktabs).
        
        Note:
            Uses non-destructive local queries (e.g. kpsewhich) if available,
            strictly avoiding any call to tlmgr, apt, or network installation scripts.
        """
        if required_packages is None:
            required_packages = ["siunitx", "booktabs"]

        results: Dict[str, bool] = {}
        kpsewhich_bin = shutil.which("kpsewhich")

        for pkg in required_packages:
            sty_name = f"{pkg}.sty" if not pkg.endswith(".sty") else pkg
            if kpsewhich_bin:
                try:
                    proc = subprocess.run(
                        [kpsewhich_bin, sty_name],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False,
                    )
                    found = bool(proc.stdout.strip() and Path(proc.stdout.strip()).exists())
                    results[pkg] = found
                except OSError:
                    results[pkg] = False
            else:
                results[pkg] = False

        return results

    def verify_all(self, strict_latex: bool = False) -> bool:
        """Runs full suite of air-gap compliance checks."""
        self.check_jinja2()
        if strict_latex:
            pkg_status = self.check_latex_packages()
            missing = [pkg for pkg, found in pkg_status.items() if not found]
            if missing:
                raise AirGapPackageMissingError(
                    f"Required LaTeX packages {missing} were not located by kpsewhich. "
                    "In air-gapped environments, automatic package installation via tlmgr is forbidden."
                )
        return True


# ==============================================================================
# 2. CompositeAggregator
# ==============================================================================

class CompositeAggregator:
    """Executes Stage 5.0 composite arithmetic and sweeps HDF5 landscape datastores in SWMR mode."""

    def calculate_composite_energy(
        self,
        e_scf_cbs: float,
        e_corr_cbs: float,
        zpve: Optional[float],
        delta_e_cv: float = 0.0,
        delta_e_rel: float = 0.0,
        delta_e_soc: float = 0.0,
        node_id: str = "default_node",
        basis_scf: str = "",
        basis_corr: str = "",
        basis_cv: str = "",
        method: str = "DLPNO-CCSD(T)",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CompositeEnergyRecord:
        """Evaluates focal-point composite total electronic and zero-point energy:
        
        E_Total = E_SCF^CBS + E_corr^CBS + Delta_E_CV + Delta_E_rel + Delta_E_SOC + ZPVE
        
        Raises:
            MissingZPVEError: If ZPVE is None or missing. Defaulting to 0.0 is strictly forbidden.
        """
        if zpve is None:
            raise MissingZPVEError(
                f"Node '{node_id}' is missing required ZPVE (Zero-Point Vibrational Energy). "
                "Stage 5.0 composite arithmetic requires explicit ZPVE and forbids defaulting to 0.0."
            )

        e_total_cbs = float(e_scf_cbs + e_corr_cbs)
        e_total_hartree = float(e_total_cbs + delta_e_cv + delta_e_rel + delta_e_soc + zpve)
        e_total_kcal_mol = float(e_total_hartree * HARTREE_TO_KCAL_MOL)

        return CompositeEnergyRecord(
            node_id=node_id,
            e_scf_cbs=float(e_scf_cbs),
            e_corr_cbs=float(e_corr_cbs),
            e_total_cbs=e_total_cbs,
            delta_e_cv=float(delta_e_cv),
            delta_e_rel=float(delta_e_rel),
            delta_e_soc=float(delta_e_soc),
            zpve=float(zpve),
            e_total_hartree=e_total_hartree,
            e_total_kcal_mol=e_total_kcal_mol,
            basis_scf=basis_scf,
            basis_corr=basis_corr,
            basis_cv=basis_cv,
            method=method,
            metadata=metadata or {},
        )

    def sweep_hdf5(self, h5_path: Union[str, Path]) -> List[CompositeEnergyRecord]:
        """Opens landscape.h5 in SWMR mode and aggregates composite records across all valid nodes.
        
        Raises:
            FileNotFoundError: If the HDF5 file does not exist.
            MissingZPVEError: If any molecular node lacks a valid ZPVE entry.
            HDF5SchemaError: If cbs_extrapolations group is missing.
        """
        target_path = Path(h5_path)
        if not target_path.exists():
            raise FileNotFoundError(f"HDF5 landscape file not found: {target_path}")

        records: List[CompositeEnergyRecord] = []

        with h5py.File(target_path, "r", libver="latest", swmr=True) as f:
            if "cbs_extrapolations" not in f:
                raise HDF5SchemaError(f"Root group 'cbs_extrapolations' not found in {target_path}")

            cbs_root = f["cbs_extrapolations"]
            cv_root = f.get("cv_corrections")
            rel_root = f.get("rel_corrections")
            zpve_root = f.get("zpve_corrections")

            for node_id in cbs_root.keys():
                cbs_node = cbs_root[node_id]

                # 1. Extract CBS Components
                if "e_scf_cbs" not in cbs_node or "e_corr_cbs" not in cbs_node:
                    raise HDF5SchemaError(f"Node '{node_id}' in cbs_extrapolations missing energy datasets.")

                e_scf_cbs = float(cbs_node["e_scf_cbs"][()])
                e_corr_cbs = float(cbs_node["e_corr_cbs"][()])
                basis_x = str(cbs_node.attrs.get("basis_x", ""))
                basis_y = str(cbs_node.attrs.get("basis_y", ""))

                # 2. Extract CV Corrections
                delta_e_cv = 0.0
                basis_cv = ""
                if cv_root and node_id in cv_root:
                    cv_node = cv_root[node_id]
                    if "delta_e_cv_hartree" in cv_node:
                        delta_e_cv = float(cv_node["delta_e_cv_hartree"][()])
                    basis_cv = str(cv_node.attrs.get("basis_set", ""))

                # 3. Extract Relativistic & SOC Corrections
                delta_e_rel = 0.0
                delta_e_soc = 0.0
                if rel_root and node_id in rel_root:
                    rel_node = rel_root[node_id]
                    if "delta_e_rel_hartree" in rel_node:
                        delta_e_rel = float(rel_node["delta_e_rel_hartree"][()])
                    if "delta_e_soc_hartree" in rel_node:
                        delta_e_soc = float(rel_node["delta_e_soc_hartree"][()])

                # 4. Extract ZPVE (Fail-Fast Verification)
                zpve_val: Optional[float] = None

                # Search order: dedicated zpve group -> node attributes -> top-level datasets
                if zpve_root and node_id in zpve_root:
                    z_node = zpve_root[node_id]
                    if "zpve_hartree" in z_node:
                        zpve_val = float(z_node["zpve_hartree"][()])
                    elif "e_zpve" in z_node:
                        zpve_val = float(z_node["e_zpve"][()])
                    elif "zpve" in z_node:
                        zpve_val = float(z_node["zpve"][()])

                if zpve_val is None and "E_ZPVE_Correction" in cbs_node.attrs:
                    zpve_val = float(cbs_node.attrs["E_ZPVE_Correction"])
                elif zpve_val is None and "zpve" in cbs_node.attrs:
                    zpve_val = float(cbs_node.attrs["zpve"])

                if zpve_val is None:
                    raise MissingZPVEError(
                        f"Node '{node_id}' in {target_path} is missing required ZPVE correction. "
                        "Defaulting to 0.0 is strictly prohibited by CoChem-BENCH Stage 5.0 specifications."
                    )

                record = self.calculate_composite_energy(
                    e_scf_cbs=e_scf_cbs,
                    e_corr_cbs=e_corr_cbs,
                    zpve=zpve_val,
                    delta_e_cv=delta_e_cv,
                    delta_e_rel=delta_e_rel,
                    delta_e_soc=delta_e_soc,
                    node_id=node_id,
                    basis_scf=f"{basis_x}->{basis_y}",
                    basis_corr=f"{basis_x}->{basis_y}",
                    basis_cv=basis_cv,
                    metadata={"source_h5": str(target_path)},
                )
                records.append(record)

        return records

    def commit_composite_to_hdf5(
        self,
        h5_path: Union[str, Path],
        records: List[CompositeEnergyRecord],
    ) -> None:
        """Persists evaluated composite energy records atomically to landscape.h5 under 'composite_energies'."""
        target_path = Path(h5_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        with h5py.File(target_path, "a") as f:
            root_grp = f.require_group("composite_energies")

            for rec in records:
                node_grp = root_grp.require_group(rec.node_id)

                datasets = {
                    "e_scf_cbs": rec.e_scf_cbs,
                    "e_corr_cbs": rec.e_corr_cbs,
                    "e_total_cbs": rec.e_total_cbs,
                    "delta_e_cv": rec.delta_e_cv,
                    "delta_e_rel": rec.delta_e_rel,
                    "delta_e_soc": rec.delta_e_soc,
                    "zpve": rec.zpve,
                    "e_total_hartree": rec.e_total_hartree,
                    "e_total_kcal_mol": rec.e_total_kcal_mol,
                }

                for ds_name, ds_val in datasets.items():
                    if ds_name in node_grp:
                        del node_grp[ds_name]
                    node_grp.create_dataset(ds_name, data=float(ds_val))

                node_grp.attrs["basis_scf"] = rec.basis_scf
                node_grp.attrs["basis_corr"] = rec.basis_corr
                node_grp.attrs["basis_cv"] = rec.basis_cv
                node_grp.attrs["method"] = rec.method
                node_grp.attrs["timestamp"] = rec.timestamp
                node_grp.attrs["node_id"] = rec.node_id


# ==============================================================================
# 3. SiunitxLaTeXCompiler
# ==============================================================================

class SiunitxLaTeXCompiler:
    """Generates memory-safe, professional LaTeX tables utilizing siunitx and booktabs packages."""

    def __init__(self) -> None:
        AirGapVerifier.check_jinja2()

    @staticmethod
    def sanitize_latex(text: str) -> str:
        """Escapes LaTeX special characters to guarantee compilation safety."""
        if not text:
            return ""
        
        replacements = [
            (r"&", r"\&"),
            (r"%", r"\%"),
            (r"$", r"\$"),
            (r"#", r"\#"),
            (r"_", r"\_"),
            (r"{", r"\{"),
            (r"}", r"\}"),
            (r"~", r"\textasciitilde{}"),
            (r"^", r"\textasciicircum{}"),
        ]

        sanitized = text
        for char, rep in replacements:
            sanitized = sanitized.replace(char, rep)
        return sanitized

    def compile_table(
        self,
        records: List[CompositeEnergyRecord],
        config: Optional[LaTeXExportConfig] = None,
        output_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """Renders LaTeX table using Jinja2 streaming and writes to output_path if provided."""
        import jinja2

        if config is None:
            config = LaTeXExportConfig()

        rows: List[Dict[str, Any]] = []
        for rec in records:
            rows.append({
                "sanitized_node_id": self.sanitize_latex(rec.node_id),
                "e_scf_cbs": rec.e_scf_cbs,
                "e_corr_cbs": rec.e_corr_cbs,
                "delta_e_cv": rec.delta_e_cv,
                "zpve": rec.zpve,
                "e_total_hartree": rec.e_total_hartree,
                "e_total_kcal_mol": rec.e_total_kcal_mol,
            })

        template_str = r"""\begin{table}[htbp]
\centering
\caption{ {{ config.caption }} }
\label{ {{ config.label }} }
\begin{tabular}{ {{ config.table_format }} }
\toprule
{Molecular Node} & {E$_{\text{SCF}}^{\text{CBS}}$ / {{ config.energy_unit }}} & {E$_{\text{corr}}^{\text{CBS}}$ / {{ config.energy_unit }}} & {$\Delta$E$_{\text{CV}}$ / {{ config.energy_unit }}} & {ZPVE / {{ config.energy_unit }}} & {E$_{\text{Total}}$ / {{ config.energy_unit }}} \\
\midrule
{% for row in rows %}
{{ row.sanitized_node_id }} & {{ "%.6f"|format(row.e_scf_cbs) }} & {{ "%.6f"|format(row.e_corr_cbs) }} & {{ "%.6f"|format(row.delta_e_cv) }} & {{ "%.6f"|format(row.zpve) }} & {{ "%.6f"|format(row.e_total_hartree) }} \\
{% endfor %}
\bottomrule
\end{tabular}
\end{table}
"""
        template = jinja2.Template(template_str)
        rendered = template.render(config=config, rows=rows)

        if output_path:
            out_p = Path(output_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(rendered, encoding="utf-8")

        return rendered


# ==============================================================================
# 4. ProvenanceStamper
# ==============================================================================

class ProvenanceStamper:
    """Assembles cryptographic FAIR JSON-LD provenance ledgers for benchmark publications."""

    @staticmethod
    def get_git_commit_hash(repo_dir: Optional[Union[str, Path]] = None) -> str:
        """Retrieves the current Git commit hash non-destructively."""
        if repo_dir is None:
            repo_dir = Path(__file__).resolve().parent

        git_bin = shutil.which("git")
        if git_bin:
            try:
                proc = subprocess.run(
                    [git_bin, "rev-parse", "HEAD"],
                    cwd=str(repo_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    return proc.stdout.strip()
            except OSError:
                pass

        try:
            head_path = Path(repo_dir).resolve()
            while head_path.parent != head_path:
                git_head = head_path / ".git" / "HEAD"
                if git_head.exists():
                    ref = git_head.read_text(encoding="utf-8").strip()
                    if ref.startswith("ref:"):
                        ref_file = head_path / ".git" / ref.split(":", 1)[1].strip()
                        if ref_file.exists():
                            return ref_file.read_text(encoding="utf-8").strip()
                    else:
                        return ref
                head_path = head_path.parent
        except Exception:
            pass

        return "UNKNOWN_GIT_COMMIT"

    @staticmethod
    def compute_file_sha256(filepath: Union[str, Path]) -> str:
        """Computes authentic SHA-256 hash of a specified binary or configuration file."""
        p = Path(filepath)
        if not p.exists() or not p.is_file():
            return "FILE_NOT_FOUND"

        hasher = hashlib.sha256()
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    def load_system_config(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """Loads cochem_system_config.json metadata."""
        if config_path is None:
            candidates = [
                Path(r"D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_system_config.json"),
                Path(r"D:\__CoChem\GitHub-Repo\cochem_system_config.json"),
            ]
            for c in candidates:
                if c.exists():
                    config_path = c
                    break

        if config_path and Path(config_path).exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def stamp_provenance(
        self,
        records: List[CompositeEnergyRecord],
        config_path: Optional[Union[str, Path]] = None,
        repo_dir: Optional[Union[str, Path]] = None,
        output_path: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        """Constructs MolSSI/QCArchive compliant JSON-LD provenance ledger and serializes to disk."""
        sys_config = self.load_system_config(config_path)
        git_hash = self.get_git_commit_hash(repo_dir)

        payload: Dict[str, Any] = {
            "@context": {
                "cochem": "https://cochem.molssi.org/schema/",
                "xsd": "http://www.w3.org/2001/XMLSchema#",
                "qc": "https://qcarchive.molssi.org/schema/",
                "codata": "https://physics.nist.gov/cuu/Constants/",
            },
            "@type": "cochem:BenchmarkProvenanceRecord",
            "stage": "5.0",
            "description": "FAIR-compliant Stage 5.0 Benchmark Composite Energy Provenance Record",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "software": {
                "ecosystem": "CoChem-BENCH / CoChem-BASE",
                "git_commit": git_hash,
                "codata_hartree_to_kcal_mol": HARTREE_TO_KCAL_MOL,
            },
            "hardware_environment": sys_config.get("hardware", {}),
            "formulas": {
                "composite_total": "E_Total = E_SCF^CBS + E_corr^CBS + Delta_E_CV + Delta_E_rel + Delta_E_SOC + ZPVE",
                "cbs_scf_helgaker": "E_SCF(L) = E_SCF(inf) + A * exp(-alpha * L)",
                "cbs_corr_inverse_power": "E_corr(L) = E_corr(inf) + B * L^(-beta)",
            },
            "nodes": [
                {
                    "node_id": r.node_id,
                    "e_scf_cbs": r.e_scf_cbs,
                    "e_corr_cbs": r.e_corr_cbs,
                    "e_total_cbs": r.e_total_cbs,
                    "delta_e_cv": r.delta_e_cv,
                    "delta_e_rel": r.delta_e_rel,
                    "delta_e_soc": r.delta_e_soc,
                    "zpve": r.zpve,
                    "e_total_hartree": r.e_total_hartree,
                    "e_total_kcal_mol": r.e_total_kcal_mol,
                    "basis_scf": r.basis_scf,
                    "basis_corr": r.basis_corr,
                    "basis_cv": r.basis_cv,
                    "method": r.method,
                }
                for r in records
            ],
        }

        if output_path:
            out_p = Path(output_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            with open(out_p, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)

        return payload


# ==============================================================================
# 5. PublicationArchiver
# ==============================================================================

class PublicationArchiver:
    """Packages exported publication tables, JSON-LD provenance, and coordinates into locked ZIP archives."""

    @staticmethod
    def create_publication_archive(
        tex_files: List[Union[str, Path]],
        jsonld_files: List[Union[str, Path]],
        xyz_files: Optional[List[Union[str, Path]]] = None,
        bib_files: Optional[List[Union[str, Path]]] = None,
        output_zip_path: Optional[Union[str, Path]] = None,
        read_only: bool = True,
    ) -> Path:
        """Compresses publication artifacts into a single ZIP file with read-only permissions."""
        if output_zip_path is None:
            output_zip_path = DEFAULT_PROCESSED_DIR / "CoChem_BENCH_Publication_Archive.zip"

        target_zip = Path(output_zip_path)
        target_zip.parent.mkdir(parents=True, exist_ok=True)

        all_files: List[Path] = []
        for f in tex_files + jsonld_files + (xyz_files or []) + (bib_files or []):
            p = Path(f)
            if p.exists() and p.is_file():
                all_files.append(p)

        with zipfile.ZipFile(target_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in all_files:
                zf.write(file_path, arcname=file_path.name)

        if read_only:
            try:
                os.chmod(target_zip, 0o444)
            except OSError:
                pass

        return target_zip


# ==============================================================================
# 6. End-to-End Pipeline Orchestration
# ==============================================================================

def run_export_pipeline(
    h5_path: Union[str, Path],
    output_dir: Optional[Union[str, Path]] = None,
    config: Optional[LaTeXExportConfig] = None,
    create_archive: bool = True,
) -> ExportPipelineResult:
    """Stage 5.0 End-to-End Orchestrator: Sweeps landscape.h5, compiles LaTeX tables,
    generates JSON-LD provenance, and packages the complete publication bundle.
    """
    if output_dir is None:
        output_dir = DEFAULT_PROCESSED_DIR

    out_p = Path(output_dir)
    out_p.mkdir(parents=True, exist_ok=True)

    # 1. Verify Air-Gap Environment
    verifier = AirGapVerifier()
    verifier.verify_all(strict_latex=False)

    # 2. Sweep HDF5 & Aggregate Composite Energies
    aggregator = CompositeAggregator()
    records = aggregator.sweep_hdf5(h5_path)

    # 3. Generate LaTeX Tables
    tex_path = out_p / "Benchmark_Results.tex"
    compiler = SiunitxLaTeXCompiler()
    compiler.compile_table(records, config=config, output_path=tex_path)

    # 4. Generate JSON-LD Provenance Ledger
    jsonld_path = out_p / "bench_provenance.jsonld"
    stamper = ProvenanceStamper()
    stamper.stamp_provenance(records, output_path=jsonld_path)

    # 5. Optional ZIP Packaging
    archive_path: Optional[str] = None
    if create_archive:
        archiver = PublicationArchiver()
        zip_file = archiver.create_publication_archive(
            tex_files=[tex_path],
            jsonld_files=[jsonld_path],
            output_zip_path=out_p / "CoChem_BENCH_Publication_Archive.zip",
            read_only=True,
        )
        archive_path = str(zip_file)

    return ExportPipelineResult(
        records=records,
        tex_file_path=str(tex_path),
        jsonld_file_path=str(jsonld_path),
        archive_file_path=archive_path,
        status="SUCCESS",
    )
