#!/usr/bin/env python3
"""CoChem-CORE: Stage 2.0 - Legacy Conformer Pre-Filtering & Ingestion Script.

Module: intake/stage2_ingestor.py
Ecosystem Role: Legacy Pre-Filtering & Stage 2 Ingestion Engine.
                Referenced in SRS Document 2 Rectification Matrix; superseded by
                intake/cochem_stage2_ingestor.py for Hungarian SVD alignment.
                Maintains full backward compatibility for legacy geometry pre-filtering
                invocations, direct CLI execution, and re-exports canonical symbols
                from intake.cochem_stage2_ingestor.

Authoritative Standards:
- D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\Method_Matrix.md (v4 Sections 9B, 10.6, 12-14)
- D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\CoChem_User_Manual.md (Section 3.3)
- D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\SRS\\Perfected_Document 2 File Inventory & Deliverable Capabilities Manifest (Part 2).md
"""

from __future__ import annotations

import argparse
import enum
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

# Ensure parent directory and module path resolution
_current_dir = Path(__file__).resolve().parent
_repo_dir = _current_dir.parent
if str(_repo_dir) not in sys.path:
    sys.path.insert(0, str(_repo_dir))
if str(_current_dir) not in sys.path:
    sys.path.insert(0, str(_current_dir))

# Canonical imports from superseded Stage 2 Ingestor
try:
    from intake.cochem_stage2_ingestor import (
        COVALENT_RADII_FALLBACK,
        MAX_PHYSICAL_VALENCY,
        VDW_RADII_FALLBACK,
        AtomNode,
        ChemicalSystemResult,
        ConformerClusterResult,
        CovalentGraphBuilder,
        DualGraphResult,
        HungarianKabschAligner,
        IngestionEngine,
        JiggleQuenchDeduplicator,
        KabschAlignmentResult,
        MonomerSubgraph,
        Stage2Ingestor,
        XYZ_LINE_PATTERN,
        get_atomic_mass,
        get_covalent_radius,
        get_vdw_radius,
        is_ghost_symbol,
        normalize_symbol,
        parse_sdf_text,
        parse_xyz_text,
    )
except ImportError:
    from cochem_stage2_ingestor import (  # type: ignore[no-redef]
        COVALENT_RADII_FALLBACK,
        MAX_PHYSICAL_VALENCY,
        VDW_RADII_FALLBACK,
        AtomNode,
        ChemicalSystemResult,
        ConformerClusterResult,
        CovalentGraphBuilder,
        DualGraphResult,
        HungarianKabschAligner,
        IngestionEngine,
        JiggleQuenchDeduplicator,
        KabschAlignmentResult,
        MonomerSubgraph,
        Stage2Ingestor,
        XYZ_LINE_PATTERN,
        get_atomic_mass,
        get_covalent_radius,
        get_vdw_radius,
        is_ghost_symbol,
        normalize_symbol,
        parse_sdf_text,
        parse_xyz_text,
    )

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CoChem-Stage2PreFilter")


# ==============================================================================
# 1. Pre-Filtering Configuration & Result Models
# ==============================================================================

class PreFilterVerdict(str, enum.Enum):
    """Enumeration of pre-filter classification outcomes."""
    PASSED = "PASSED"
    CLASH_DETECTED = "CLASH_DETECTED"
    VALENCY_VIOLATION = "VALENCY_VIOLATION"
    DISSOCIATION_ERROR = "DISSOCIATION_ERROR"
    ENERGY_OUT_OF_BOUNDS = "ENERGY_OUT_OF_BOUNDS"
    DUPLICATE_FILTERED = "DUPLICATE_FILTERED"


class PreFilterConfig(BaseModel):
    """Configuration parameters for Stage 2 geometry pre-filtering."""
    model_config = ConfigDict(extra="ignore")

    min_atomic_distance: float = Field(0.55, description="Absolute minimum physical distance between any two atoms (A)")
    clash_factor: float = Field(0.55, description="Fraction of sum of covalent radii indicating unphysical atom overlap")
    max_interatomic_distance: float = Field(20.0, description="Maximum allowable coordinate span / bounding radius (A)")
    breathing_tolerance: float = Field(1.15, description="Method Matrix covalent bond breathing multiplier")
    vdw_contact_buffer: float = Field(0.8, description="Buffer added to sum of vdW radii for non-covalent contacts (A)")
    rmsd_threshold: float = Field(0.08, description="RMSD threshold for conformer duplicate rejection (A)")
    energy_window_kcal: float = Field(12.0, description="Thermodynamic energy window for conformer retention (kcal/mol)")
    enforce_valency: bool = Field(True, description="Whether to actively evaluate and prune unphysical valencies")
    max_workers: int = Field(4, description="Maximum concurrent worker threads for file scanning")


class PreFilterRecord(BaseModel):
    """Audit record for an individual geometry pre-filtering evaluation."""
    model_config = ConfigDict(extra="ignore")

    conformer_index: int
    conformer_name: str
    verdict: PreFilterVerdict
    details: str
    min_observed_distance: float
    num_clashes: int = 0
    passed: bool


class PreFilterSummary(BaseModel):
    """Summary report of a batch pre-filtering campaign."""
    model_config = ConfigDict(extra="ignore")

    total_candidates: int
    passed_count: int
    clash_rejected_count: int
    valency_rejected_count: int
    dissociation_rejected_count: int
    energy_rejected_count: int
    duplicate_rejected_count: int
    records: List[PreFilterRecord] = Field(default_factory=list)


# ==============================================================================
# 2. Legacy Pre-Filter Engine
# ==============================================================================

class Stage2PreFilter:
    """Legacy Stage 2 Pre-Filtering Engine.
    
    Provides rapid geometric and topological pre-filtering of raw candidate ensembles
    prior to expensive high-level quantum chemical optimization and SVD alignment.
    Evaluates:
    - Minimum distance clash violations: D_ij < clash_factor * (r_cov,i + r_cov,j)
    - Unphysical coordinate span / dissociation bounds
    - Hypercoordination and unphysical valency violations
    - Energy window filtering
    - Rapid pairwise RMSD pre-sifting
    """

    def __init__(self, config: Optional[PreFilterConfig] = None) -> None:
        self.config = config or PreFilterConfig()
        self.graph_builder = CovalentGraphBuilder(
            breathing_tolerance=self.config.breathing_tolerance,
            vdw_contact_buffer=self.config.vdw_contact_buffer,
        )
        self.aligner = HungarianKabschAligner()

    def check_atomic_clashes(
        self,
        coords: np.ndarray,
        symbols: Sequence[str],
    ) -> Tuple[bool, float, List[Tuple[int, int, float, float]]]:
        """Evaluates pairwise interatomic distances for unphysical atomic clashes.
        
        Returns:
            Tuple of:
            - is_clashing (bool): True if any atomic pair is within unphysical proximity.
            - min_dist (float): Minimum observed interatomic distance in Angstroms.
            - clash_list (List): List of (atom_i, atom_j, distance, threshold) tuples.
        """
        coords_arr = np.asarray(coords, dtype=np.float64)
        n_atoms = len(coords_arr)
        if n_atoms < 2:
            return False, float("inf"), []

        cov_radii = [get_covalent_radius(s) for s in symbols]
        min_dist = float("inf")
        clashes: List[Tuple[int, int, float, float]] = []

        for i in range(n_atoms):
            if is_ghost_symbol(symbols[i]):
                continue
            for j in range(i + 1, n_atoms):
                if is_ghost_symbol(symbols[j]):
                    continue
                d = float(np.linalg.norm(coords_arr[i] - coords_arr[j]))
                if d < min_dist:
                    min_dist = d

                thresh = max(
                    self.config.min_atomic_distance,
                    self.config.clash_factor * (cov_radii[i] + cov_radii[j]),
                )

                if d < thresh:
                    clashes.append((i, j, d, thresh))

        is_clashing = len(clashes) > 0 or (min_dist < self.config.min_atomic_distance)
        return is_clashing, min_dist, clashes

    def check_spatial_extent(
        self,
        coords: np.ndarray,
    ) -> Tuple[bool, float]:
        """Evaluates bounding sphere radius to reject dissociated unphysical fragments."""
        coords_arr = np.asarray(coords, dtype=np.float64)
        if len(coords_arr) == 0:
            return True, 0.0
        com = np.mean(coords_arr, axis=0)
        radii = np.linalg.norm(coords_arr - com, axis=1)
        max_r = float(np.max(radii))
        is_valid = max_r <= self.config.max_interatomic_distance
        return is_valid, max_r

    def evaluate_candidate(
        self,
        coords: np.ndarray,
        symbols: Sequence[str],
        name: str = "candidate",
        energy_kcal: Optional[float] = None,
        min_energy_kcal: Optional[float] = None,
    ) -> PreFilterRecord:
        """Runs the full battery of pre-filtering evaluations on a single geometry."""
        coords_arr = np.asarray(coords, dtype=np.float64)

        # 1. Clash check
        is_clashing, min_d, clashes = self.check_atomic_clashes(coords_arr, symbols)
        if is_clashing:
            clash_desc = ", ".join([f"{symbols[i]}[{i}]-{symbols[j]}[{j}]: {d:.3f}A<{th:.3f}A" for i, j, d, th in clashes[:3]])
            return PreFilterRecord(
                conformer_index=0,
                conformer_name=name,
                verdict=PreFilterVerdict.CLASH_DETECTED,
                details=f"Unphysical atomic clash detected. Min dist={min_d:.3f} A ({clash_desc})",
                min_observed_distance=min_d,
                num_clashes=len(clashes),
                passed=False,
            )

        # 2. Spatial extent / dissociation check
        is_extent_valid, max_r = self.check_spatial_extent(coords_arr)
        if not is_extent_valid:
            return PreFilterRecord(
                conformer_index=0,
                conformer_name=name,
                verdict=PreFilterVerdict.DISSOCIATION_ERROR,
                details=f"System exceeded spatial bounding radius: {max_r:.2f} A > {self.config.max_interatomic_distance:.2f} A",
                min_observed_distance=min_d,
                num_clashes=0,
                passed=False,
            )

        # 3. Valency violation check
        if self.config.enforce_valency and len(coords_arr) >= 2:
            g_raw = self.graph_builder.build_covalent_graph(coords_arr, symbols, enforce_valency=False)
            valency_violations = []
            for node in g_raw.nodes():
                sym = normalize_symbol(symbols[node])
                max_v = MAX_PHYSICAL_VALENCY.get(sym, 6)
                deg = g_raw.degree(node)
                if deg > max_v:
                    valency_violations.append((node, sym, deg, max_v))
            if valency_violations:
                v_desc = ", ".join([f"{s}[{idx}] degree={deg}>{max_v}" for idx, s, deg, max_v in valency_violations[:3]])
                return PreFilterRecord(
                    conformer_index=0,
                    conformer_name=name,
                    verdict=PreFilterVerdict.VALENCY_VIOLATION,
                    details=f"Unphysical valency violation detected ({v_desc})",
                    min_observed_distance=min_d,
                    num_clashes=0,
                    passed=False,
                )

        # 4. Energy window check
        if energy_kcal is not None and min_energy_kcal is not None:
            delta_e = energy_kcal - min_energy_kcal
            if delta_e > self.config.energy_window_kcal:
                return PreFilterRecord(
                    conformer_index=0,
                    conformer_name=name,
                    verdict=PreFilterVerdict.ENERGY_OUT_OF_BOUNDS,
                    details=f"Relative energy {delta_e:.2f} kcal/mol exceeds window {self.config.energy_window_kcal:.2f} kcal/mol",
                    min_observed_distance=min_d,
                    num_clashes=0,
                    passed=False,
                )

        return PreFilterRecord(
            conformer_index=0,
            conformer_name=name,
            verdict=PreFilterVerdict.PASSED,
            details="Passed geometric, topological, and physical clash pre-filtering.",
            min_observed_distance=min_d,
            num_clashes=0,
            passed=True,
        )

    def filter_ensemble(
        self,
        conformers: Sequence[np.ndarray],
        symbols: Sequence[str] | Sequence[Sequence[str]],
        names: Optional[Sequence[str]] = None,
        energies_kcal: Optional[Sequence[float]] = None,
    ) -> Tuple[List[np.ndarray], List[str], PreFilterSummary]:
        """Pre-filters an ensemble of candidate conformers, sifting out invalid geometries."""
        n_confs = len(conformers)
        if n_confs == 0:
            return [], [], PreFilterSummary(
                total_candidates=0,
                passed_count=0,
                clash_rejected_count=0,
                valency_rejected_count=0,
                dissociation_rejected_count=0,
                energy_rejected_count=0,
                duplicate_rejected_count=0,
                records=[],
            )

        conf_names = list(names) if names is not None else [f"conf_{i}" for i in range(n_confs)]

        if len(symbols) > 0 and isinstance(symbols[0], (list, tuple)):
            symbols_list: Sequence[Sequence[str]] = symbols  # type: ignore
        else:
            symbols_list = [symbols] * n_confs  # type: ignore

        min_e = float(np.min(energies_kcal)) if (energies_kcal is not None and len(energies_kcal) > 0) else None

        passed_coords: List[np.ndarray] = []
        passed_names: List[str] = []
        passed_symbols: List[Sequence[str]] = []
        records: List[PreFilterRecord] = []

        clash_rej = 0
        val_rej = 0
        dissoc_rej = 0
        energy_rej = 0
        dup_rej = 0

        for i in range(n_confs):
            c_coords = np.asarray(conformers[i], dtype=np.float64)
            c_syms = symbols_list[i]
            c_name = conf_names[i]
            c_energy = energies_kcal[i] if energies_kcal is not None else None

            rec = self.evaluate_candidate(
                coords=c_coords,
                symbols=c_syms,
                name=c_name,
                energy_kcal=c_energy,
                min_energy_kcal=min_e,
            )
            rec.conformer_index = i

            if not rec.passed:
                if rec.verdict == PreFilterVerdict.CLASH_DETECTED:
                    clash_rej += 1
                elif rec.verdict == PreFilterVerdict.VALENCY_VIOLATION:
                    val_rej += 1
                elif rec.verdict == PreFilterVerdict.DISSOCIATION_ERROR:
                    dissoc_rej += 1
                elif rec.verdict == PreFilterVerdict.ENERGY_OUT_OF_BOUNDS:
                    energy_rej += 1
                records.append(rec)
                continue

            # Pairwise rapid RMSD duplicate pre-sieve against already accepted geometries
            is_dup = False
            for prev_idx, prev_coords in enumerate(passed_coords):
                align_res = self.aligner.align(
                    target_coords=c_coords,
                    ref_coords=prev_coords,
                    symbols=c_syms,
                    ref_symbols=passed_symbols[prev_idx],
                    allow_permutation=True,
                )
                if align_res.rmsd < self.config.rmsd_threshold:
                    is_dup = True
                    dup_rec = PreFilterRecord(
                        conformer_index=i,
                        conformer_name=c_name,
                        verdict=PreFilterVerdict.DUPLICATE_FILTERED,
                        details=f"Conformer redundant with accepted {passed_names[prev_idx]} (RMSD={align_res.rmsd:.4f} A < {self.config.rmsd_threshold:.4f} A)",
                        min_observed_distance=rec.min_observed_distance,
                        num_clashes=0,
                        passed=False,
                    )
                    records.append(dup_rec)
                    dup_rej += 1
                    break

            if not is_dup:
                passed_coords.append(c_coords)
                passed_names.append(c_name)
                passed_symbols.append(c_syms)
                records.append(rec)

        summary = PreFilterSummary(
            total_candidates=n_confs,
            passed_count=len(passed_coords),
            clash_rejected_count=clash_rej,
            valency_rejected_count=val_rej,
            dissociation_rejected_count=dissoc_rej,
            energy_rejected_count=energy_rej,
            duplicate_rejected_count=dup_rej,
            records=records,
        )

        return passed_coords, passed_names, summary


# Legacy aliases for pre-filtering engine
LegacyStage2PreFilter = Stage2PreFilter
PreFilterEngine = Stage2PreFilter
ConformerPreFilter = Stage2PreFilter
LegacyStage2Ingestor = Stage2Ingestor


# ==============================================================================
# 3. Geometry Formatting & File Serialization Utilities
# ==============================================================================

def format_xyz_string(
    coords: np.ndarray,
    symbols: Sequence[str],
    comment: str = "CoChem-Stage2 Ingestor Geometry",
) -> str:
    """Formats Cartesian coordinates and symbols into standard XYZ format."""
    coords_arr = np.asarray(coords, dtype=np.float64)
    n_atoms = len(coords_arr)
    lines = [str(n_atoms), comment]
    for sym, (x, y, z) in zip(symbols, coords_arr):
        lines.append(f"{normalize_symbol(sym):<3} {x:14.8f} {y:14.8f} {z:14.8f}")
    return "\n".join(lines) + "\n"


def write_xyz_file(
    file_path: Union[str, Path],
    coords: np.ndarray,
    symbols: Sequence[str],
    comment: str = "CoChem-Stage2 Geometry",
) -> Path:
    """Writes a molecular geometry to an XYZ file on disk."""
    p = Path(file_path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    xyz_str = format_xyz_string(coords, symbols, comment=comment)
    p.write_text(xyz_str, encoding="utf-8")
    return p


# ==============================================================================
# 4. Standalone CLI Entry Point
# ==============================================================================

def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entrypoint for Stage 2 Ingestor & Pre-Filtering Engine."""
    parser = argparse.ArgumentParser(
        description="CoChem Stage 2 Conformer Pre-Filtering & Ingestion Engine",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input-dir", "-i", type=str, default=".", help="Directory containing .xyz, .sdf, or .mol files")
    parser.add_argument("--rmsd", type=float, default=0.08, help="RMSD clustering threshold (Angstroms)")
    parser.add_argument("--clash-factor", type=float, default=0.55, help="Clash overlap factor of covalent radii sum")
    parser.add_argument("--breathing-tol", type=float, default=1.15, help="Breathing tolerance for covalent bonds")
    parser.add_argument("--workers", "-w", type=int, default=4, help="Maximum worker threads")
    parser.add_argument("--output-json", "-o", type=str, default="", help="Optional JSON output report path")

    args = parser.parse_args(argv)

    input_path = Path(args.input_dir).resolve()
    if not input_path.exists() or not input_path.is_dir():
        logger.error(f"Input directory does not exist: {input_path}")
        return 1

    ingestor = Stage2Ingestor(
        max_workers=args.workers,
        breathing_tolerance=args.breathing_tol,
        rmsd_threshold=args.rmsd,
    )

    results = ingestor.process_directory(input_path)
    logger.info(f"Successfully processed {len(results)} chemical systems.")

    if args.output_json:
        out_p = Path(args.output_json).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        import json
        payload = [res.model_dump() for res in results]
        out_p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info(f"Saved ingestion results to {out_p}")

    return 0


__all__ = [
    # Radii, Mass & Symbol Helpers
    "COVALENT_RADII_FALLBACK",
    "VDW_RADII_FALLBACK",
    "MAX_PHYSICAL_VALENCY",
    "is_ghost_symbol",
    "normalize_symbol",
    "get_covalent_radius",
    "get_vdw_radius",
    "get_atomic_mass",
    # Pydantic Models & Schemas
    "AtomNode",
    "MonomerSubgraph",
    "DualGraphResult",
    "KabschAlignmentResult",
    "ConformerClusterResult",
    "ChemicalSystemResult",
    "PreFilterVerdict",
    "PreFilterConfig",
    "PreFilterRecord",
    "PreFilterSummary",
    # Core Engines
    "CovalentGraphBuilder",
    "HungarianKabschAligner",
    "JiggleQuenchDeduplicator",
    "Stage2PreFilter",
    "LegacyStage2PreFilter",
    "PreFilterEngine",
    "ConformerPreFilter",
    "Stage2Ingestor",
    "LegacyStage2Ingestor",
    "IngestionEngine",
    # IO & Parsers
    "XYZ_LINE_PATTERN",
    "parse_xyz_text",
    "parse_sdf_text",
    "format_xyz_string",
    "write_xyz_file",
    # CLI
    "main",
]


if __name__ == "__main__":
    sys.exit(main())
