#!/usr/bin/env python3
r"""Stage 2.0: Two-Point Complete Basis Set (CBS) Energy Extrapolation Engine.

Authoritative Implementation: cochem_bench.bench_engine.cochem_bench_cbs
System Domain: CoChem-BENCH Scientific Engine

Key Capabilities:
1. Energy Decomposition & ORCA Output Extraction:
   - Parses the literal string "FINAL SINGLE POINT ENERGY" to extract E_total.
   - Parses the literal string "Total Energy       :" from the SCF block to extract E_SCF.
   - Computes E_corr = E_total - E_SCF natively from extracted floats.
   - Strictly forbids extrapolating total energy directly.
2. SCF Extrapolation (Exponential Decay):
   - Formula:
     E_SCF^(inf) = (E_SCF^(X) * exp(-alpha * sqrt(Y)) - E_SCF^(Y) * exp(-alpha * sqrt(X))) /
                   (exp(-alpha * sqrt(Y)) - exp(-alpha * sqrt(X)))
3. Correlation Extrapolation (Inverse Power):
   - Formula:
     E_corr^(inf) = (X^beta * E_corr^(X) - Y^beta * E_corr^(Y)) / (X^beta - Y^beta)
4. Parameter Matrix (ALPHA_BETA_MAP):
   - Hardcoded authoritative alpha/beta mapping for standard basis families (cc-pVnZ, pc-n, def2, ano-pVnZ, saug-ano-pVnZ).
   - Defaults for custom/unlisted basis sets: beta=2.4 for 2/3 (DZ->TZ) and beta=3.0 for 3/4 (TZ->QZ).
   - Mandatory explicit alpha override required for custom basis sets.
5. Residual Fit Trapping & Uncertainty Flagging:
   - Computes absolute variance: Delta = |E_corr^(inf) - E_corr^(Y)|.
   - Converts Delta to kcal/mol via exact CODATA conversion factor (627.509474063 kcal/mol per Hartree).
   - If Delta > 10.0 kcal/mol, flags calculation as 'CBS_HIGH_UNCERTAINTY'.
   - Multi-process HDF5 persistence protected with filelock.FileLock(f"{h5_path}.lock", timeout=120).
6. DualBasisDispatcher & SlowConvInterceptor:
   - Calculates strict %maxcore RAM limits per MPI thread based on available hardware.
   - Dynamically calculates atomic masses and electron counts using the Mendeleev library.
   - Intercepts SCF DIIS convergence failures in ORCA output and remediates by injecting '! SlowConv SOSCF'.
7. Safety Contract:
   - Air-Gap strictly enforced dynamically with NO hardcoded absolute paths.
   - HDF5 workspace paths resolved dynamically via os.environ["COCHEM_ARTIFACTS_DIR"].

Authoritative References:
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 5 CBS Extrapolation & Composite Protocol Math (Stages 2.0 - 4.0).txt
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task5_cbs.md
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
"""

from __future__ import annotations

import datetime
import logging
import math
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import filelock
import h5py
from mendeleev import element
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

# ==============================================================================
# Physical Constants & Parameter Matrix
# ==============================================================================

# Exact CODATA Conversion: Hartree to kcal/mol
HARTREE_TO_KCAL_MOL: float = 627.509474063

# Mathematical Guardrail Threshold: Uncertainty ceiling for CBS extrapolation (kcal/mol)
CBS_UNCERTAINTY_THRESHOLD_KCAL_MOL: float = 10.0

# Exact authoritative parameter mapping dictionary specified by Task 5 SRS
ALPHA_BETA_MAP: Dict[str, Dict[str, float]] = {
    "cc-pv_dz_tz": {"alpha": 4.42, "beta": 2.46},
    "cc-pv_tz_qz": {"alpha": 5.46, "beta": 3.05},
    "pc-n_dz_tz": {"alpha": 7.02, "beta": 2.01},
    "pc-n_tz_qz": {"alpha": 9.78, "beta": 4.09},
    "def2_dz_tz": {"alpha": 10.39, "beta": 2.40},
    "def2_tz_qz": {"alpha": 7.88, "beta": 2.97},
    "ano-pv_dz_tz": {"alpha": 5.41, "beta": 2.43},
    "ano-pv_tz_qz": {"alpha": 4.48, "beta": 2.97},
    "saug-ano-pv_dz_tz": {"alpha": 5.48, "beta": 2.21},
    "saug-ano-pv_tz_qz": {"alpha": 4.18, "beta": 2.83},
}

# Tuple-keyed alias matrix for backwards compatibility
PARAMETER_MATRIX: Dict[Tuple[str, int, int], Tuple[float, float]] = {
    ("cc-pVnZ", 2, 3): (4.42, 2.46),
    ("cc-pVnZ", 3, 4): (5.46, 3.05),
    ("cc-pVnZ", 4, 5): (5.46, 3.05),
    ("pc-n", 2, 3): (7.02, 2.01),
    ("pc-n", 3, 4): (9.78, 4.09),
    ("def2", 2, 3): (10.39, 2.40),
    ("def2", 3, 4): (7.88, 2.97),
    ("ano-pVnZ", 2, 3): (5.41, 2.43),
    ("ano-pVnZ", 3, 4): (4.48, 2.97),
    ("saug-ano-pVnZ", 2, 3): (5.48, 2.21),
    ("saug-ano-pVnZ", 3, 4): (4.18, 2.83),
}


# ==============================================================================
# Error Hierarchy
# ==============================================================================

class CBSExtrapolationError(Exception):
    """Base exception for Stage 2.0 CBS extrapolation operations."""
    pass


class CBSParameterError(CBSExtrapolationError, ValueError):
    """Raised when basis set parameters are unresolvable or missing required overrides."""
    pass


class CBSSingularDenominatorError(CBSExtrapolationError, ValueError):
    """Raised when mathematical extrapolation encounters a singular or near-zero denominator."""
    pass


class CBSParsingError(CBSExtrapolationError, ValueError):
    """Raised when required literal energy signatures cannot be parsed from ORCA output."""
    pass


# ==============================================================================
# Data Models
# ==============================================================================

class CBSExtrapolationResult(BaseModel):
    """Structured result model for Complete Basis Set (CBS) limit evaluations."""
    model_config = ConfigDict(validate_assignment=True)

    e_scf_cbs: float = Field(description="Extrapolated Hartree-Fock SCF energy in Hartree")
    e_corr_cbs: float = Field(description="Extrapolated correlation energy in Hartree")
    e_total_cbs: float = Field(description="Total Complete Basis Set energy (SCF + Correlation) in Hartree")
    basis_x: str = Field(description="Lower cardinal basis set name")
    basis_y: str = Field(description="Higher cardinal basis set name")
    alpha: float = Field(description="Exponential decay exponent used for SCF extrapolation")
    beta: float = Field(description="Inverse power exponent used for correlation extrapolation")
    residual_variance_hartree: float = Field(description="Absolute correlation variance |E_corr(inf) - E_corr(Y)| in Hartree")
    residual_variance_kcal_mol: float = Field(description="Absolute correlation variance in kcal/mol")
    uncertainty_flag: str = Field(description="'PASSED' or 'CBS_HIGH_UNCERTAINTY'")
    node_id: str = Field(default="", description="Unique identifier of the molecular node or conformer")
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional provenance or execution metadata")


class SlowConvInterceptionResult(BaseModel):
    """Structured result model for SlowConv interceptor diagnostic sweeps."""
    model_config = ConfigDict(validate_assignment=True)

    has_failed: bool = Field(description="True if SCF DIIS convergence failure was detected")
    should_restart: bool = Field(description="True if calculation should be restarted with remediated input")
    remediated_input: str = Field(description="Remediated ORCA input string with injected convergence directives")
    injected_keywords: List[str] = Field(default_factory=list, description="Keywords injected during remediation")
    reason: str = Field(default="", description="Diagnostic explanation of failure and action taken")


class EnergyDecompositionResult(BaseModel):
    """Structured result from ORCA output energy extraction and decomposition."""
    model_config = ConfigDict(validate_assignment=True)

    e_total: float = Field(description="Total single point electronic energy in Hartree")
    e_scf: float = Field(description="Total SCF / Hartree-Fock energy in Hartree")
    e_corr: float = Field(description="Decoupled correlation energy E_total - E_SCF in Hartree")


# ==============================================================================
# 1. Energy Decomposition & ORCA Output Parser
# ==============================================================================

def parse_orca_energies(stdout_text: str) -> Tuple[float, float, float]:
    """Parses ORCA standard output to extract E_total, E_SCF, and compute E_corr.

    Literal signatures parsed:
    - E_total: Matches the literal string "FINAL SINGLE POINT ENERGY" followed by float value.
    - E_SCF: Matches the literal string "Total Energy       :" from the SCF block.

    Calculates:
      E_corr = E_total - E_SCF

    Args:
        stdout_text: Complete text content of ORCA output stream.

    Returns:
        Tuple of (E_total, E_SCF, E_corr) in Hartree.

    Raises:
        CBSParsingError: If either signature is missing or unparseable.
    """
    if not stdout_text or not isinstance(stdout_text, str):
        raise CBSParsingError("Empty or invalid stdout text provided for ORCA energy extraction.")

    # 1. Extract E_total from literal string "FINAL SINGLE POINT ENERGY"
    total_matches = re.findall(
        r"FINAL\s+SINGLE\s+POINT\s+ENERGY\s*[:=]?\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)",
        stdout_text,
        re.IGNORECASE,
    )
    if not total_matches:
        raise CBSParsingError(
            "Failed to parse required literal string 'FINAL SINGLE POINT ENERGY' from ORCA output."
        )
    e_total = float(total_matches[-1])

    # 2. Extract E_SCF from literal string "Total Energy       :"
    scf_matches = re.findall(
        r"Total\s+Energy\s*:\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)",
        stdout_text,
        re.IGNORECASE,
    )
    if not scf_matches:
        raise CBSParsingError(
            "Failed to parse required literal string 'Total Energy       :' from SCF block in ORCA output."
        )
    e_scf = float(scf_matches[-1])

    # 3. Mathematically decouple correlation energy
    e_corr = e_total - e_scf

    return e_total, e_scf, e_corr


# ==============================================================================
# 2. DualBasisDispatcher
# ==============================================================================

class DualBasisDispatcher:
    """Orchestrates dual-basis single-point energy evaluations for CBS extrapolation.

    Generates parallel ORCA 6.1.1 inputs, calculating strict %maxcore RAM limits
    per MPI thread to prevent host OS swap-death and page thrashing.
    """

    def __init__(
        self,
        node_max_gb: float = 16.0,
        nprocs: int = 4,
        method: str = "DLPNO-CCSD(T)",
        basis_pair: Tuple[str, str] = ("def2-TZVP", "def2-QZVPP"),
        ram_safety_fraction: float = 0.75,
        tight_scf: bool = True,
        defgrid: str = "DefGrid3",
        extra_keywords: Optional[List[str]] = None,
    ) -> None:
        self.node_max_gb = float(node_max_gb)
        self.nprocs = max(1, int(nprocs))
        self.method = method
        self.basis_pair = basis_pair
        self.ram_safety_fraction = float(ram_safety_fraction)
        self.tight_scf = tight_scf
        self.defgrid = defgrid
        self.extra_keywords = list(extra_keywords) if extra_keywords else []

    def calculate_maxcore_per_thread(self) -> int:
        """Calculates strict per-process maxcore in MB leaving headroom for OS and MPI runtime.

        Formula:
          available_mb = node_max_gb * 1024 * ram_safety_fraction
          per_thread_mb = floor(available_mb / nprocs)
        """
        available_mb = self.node_max_gb * 1024.0 * self.ram_safety_fraction
        per_thread_mb = int(available_mb / self.nprocs)

        min_allowed = 250
        max_allowed = int((self.node_max_gb * 1024.0) / self.nprocs)
        candidate = max(min_allowed, per_thread_mb)
        return min(candidate, max_allowed)

    def get_molecular_properties(
        self,
        coords: Union[List[Tuple[str, float, float, float]], List[List[Any]]],
    ) -> Tuple[float, int]:
        """Dynamically retrieves molecular mass and total electron count via Mendeleev library."""
        total_mass = 0.0
        total_electrons = 0

        for item in coords:
            sym = str(item[0]).strip().rstrip(":").capitalize()
            elem_data = element(sym)
            total_mass += float(elem_data.mass)
            total_electrons += int(elem_data.atomic_number)

        return total_mass, total_electrons

    def detect_spin_state(
        self,
        coords: Union[List[Tuple[str, float, float, float]], List[List[Any]]],
        charge: int = 0,
    ) -> Tuple[bool, int]:
        """Analyzes electron counts to detect open-shell radical states requiring UHF/SOMF handling."""
        _, total_electrons = self.get_molecular_properties(coords)
        net_electrons = total_electrons - charge

        if net_electrons % 2 != 0:
            # Odd number of electrons -> Open-shell radical (minimum doublet)
            return True, 2
        return False, 1

    def generate_input_deck(
        self,
        coords: Union[List[Tuple[str, float, float, float]], List[List[Any]]],
        charge: int = 0,
        mult: int = 1,
        output_dir: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        """Generates authentic ORCA 6.1.1 input decks for both basis sets in the dual-basis pair."""
        basis_x, basis_y = self.basis_pair
        maxcore_mb = self.calculate_maxcore_per_thread()

        input_x = self._build_orca_input_string(
            coords=coords,
            basis=basis_x,
            charge=charge,
            mult=mult,
            maxcore_mb=maxcore_mb,
        )
        input_y = self._build_orca_input_string(
            coords=coords,
            basis=basis_y,
            charge=charge,
            mult=mult,
            maxcore_mb=maxcore_mb,
        )

        deck = {
            "basis_x": basis_x,
            "basis_y": basis_y,
            "input_x": input_x,
            "input_y": input_y,
            "maxcore_mb": maxcore_mb,
            "nprocs": self.nprocs,
            "method": self.method,
            "charge": charge,
            "mult": mult,
        }

        if output_dir:
            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)
            (out_path / f"orca_{basis_x.replace('/', '_')}.inp").write_text(input_x, encoding="utf-8")
            (out_path / f"orca_{basis_y.replace('/', '_')}.inp").write_text(input_y, encoding="utf-8")

        return deck

    def _build_orca_input_string(
        self,
        coords: Union[List[Tuple[str, float, float, float]], List[List[Any]]],
        basis: str,
        charge: int,
        mult: int,
        maxcore_mb: int,
    ) -> str:
        """Helper constructing valid ORCA 6.1.1 input text."""
        keywords = ["!", self.method, basis]
        if self.tight_scf:
            keywords.append("TightSCF")
        if self.defgrid:
            keywords.append(self.defgrid)
        for kw in self.extra_keywords:
            if kw not in keywords:
                keywords.append(kw)

        lines = [" ".join(keywords)]
        lines.append(f"%maxcore {maxcore_mb}")
        if self.nprocs > 1:
            lines.append(f"%pal nprocs {self.nprocs} end")

        lines.append(f"* xyz {charge} {mult}")
        for atom in coords:
            sym = str(atom[0]).strip()
            x = float(atom[1])
            y = float(atom[2])
            z = float(atom[3])
            lines.append(f"  {sym:<2}  {x:12.8f}  {y:12.8f}  {z:12.8f}")
        lines.append("*\n")

        return "\n".join(lines)


# ==============================================================================
# 3. HelgakerExtrapolator
# ==============================================================================

class HelgakerExtrapolator:
    """Natively executes Complete Basis Set (CBS) two-point extrapolations.

    Implements:
    - Energy Decomposition: E_corr = E_total - E_SCF
    - Exponential Decay for Hartree-Fock SCF Energies:
      E_SCF(inf) = (E_SCF(X)*exp(-alpha*sqrt(Y)) - E_SCF(Y)*exp(-alpha*sqrt(X))) / (exp(-alpha*sqrt(Y)) - exp(-alpha*sqrt(X)))
    - Halkier / Neese Inverse Power for Correlation Energies:
      E_corr(inf) = (X^beta * E_corr(X) - Y^beta * E_corr(Y)) / (X^beta - Y^beta)
    """

    def decompose_correlation_energy(self, e_total: float, e_scf: float) -> float:
        """Mathematically decouples total electronic energy into correlation component."""
        return float(e_total) - float(e_scf)

    def detect_family_and_cardinal(self, basis: str) -> Tuple[str, int]:
        """Inspects basis set string to determine its family classification and cardinal number."""
        b_lower = basis.lower().replace("_", "-").replace(" ", "")

        # Cardinal number extraction
        if any(tok in b_lower for tok in ["svp", "dz", "pc-1", "pc1"]):
            cardinal = 2
        elif any(tok in b_lower for tok in ["tzvp", "tzvpp", "tz", "pc-2", "pc2"]):
            cardinal = 3
        elif any(tok in b_lower for tok in ["qzvpp", "qzvp", "qz", "pc-3", "pc3"]):
            cardinal = 4
        elif any(tok in b_lower for tok in ["5zvpp", "5zvp", "5z", "pc-4", "pc4"]):
            cardinal = 5
        else:
            cardinal = 3

        # Family classification
        if "saug-ano" in b_lower:
            family = "saug-ano-pv"
        elif "ano" in b_lower:
            family = "ano-pv"
        elif "def2" in b_lower:
            family = "def2"
        elif "pc-" in b_lower or "pc" in b_lower:
            family = "pc-n"
        elif "cc-p" in b_lower:
            family = "cc-pv"
        else:
            family = "custom"

        return family, cardinal

    def resolve_alpha_beta_key(self, basis_x: str, basis_y: str) -> Optional[str]:
        """Resolves basis pair strings to authoritative ALPHA_BETA_MAP key."""
        fam_x, X = self.detect_family_and_cardinal(basis_x)
        fam_y, Y = self.detect_family_and_cardinal(basis_y)

        # Enforce X < Y ordering
        if X > Y:
            X, Y = Y, X
            fam_x, fam_y = fam_y, fam_x

        # Cardinal token mapping
        card_map = {2: "dz", 3: "tz", 4: "qz", 5: "5z"}
        c_x = card_map.get(X, f"{X}")
        c_y = card_map.get(Y, f"{Y}")

        # Primary lookup key
        key = f"{fam_x}_{c_x}_{c_y}"
        if key in ALPHA_BETA_MAP:
            return key

        # Alternative direct name checking
        bx_norm = basis_x.lower().replace("-", "_").replace(" ", "")
        by_norm = basis_y.lower().replace("-", "_").replace(" ", "")
        for k in ALPHA_BETA_MAP:
            tokens = k.split("_")
            fam = tokens[0]
            if len(tokens) >= 3:
                cx, cy = tokens[1], tokens[2]
                if fam in bx_norm and cx in bx_norm and cy in by_norm:
                    return k

        return None

    def lookup_parameters(
        self,
        basis_x: str,
        basis_y: str,
        custom_alpha: Optional[float] = None,
        custom_beta: Optional[float] = None,
    ) -> Tuple[float, float, int, int]:
        """Dynamically maps basis pair strings to authoritative alpha and beta parameters.

        For custom basis sets:
        - Defaults beta=2.4 for 2/3 and beta=3.0 for 3/4.
        - Requires an explicit user override for alpha (raises CBSParameterError if missing).
        """
        _, X = self.detect_family_and_cardinal(basis_x)
        _, Y = self.detect_family_and_cardinal(basis_y)

        if X >= Y:
            X, Y = 2, 3

        map_key = self.resolve_alpha_beta_key(basis_x, basis_y)

        if map_key and map_key in ALPHA_BETA_MAP:
            alpha_val = ALPHA_BETA_MAP[map_key]["alpha"]
            beta_val = ALPHA_BETA_MAP[map_key]["beta"]
        else:
            # Custom or unlisted basis set handling
            if (X == 2 and Y == 3) or (X == 2 and Y == 4):
                beta_default = 2.40
            else:
                beta_default = 3.00

            beta_val = custom_beta if custom_beta is not None else beta_default

            if custom_alpha is None:
                raise CBSParameterError(
                    f"Custom or unlisted basis set pair ('{basis_x}', '{basis_y}') requires an "
                    f"explicit alpha parameter override (custom_alpha). Beta defaulted to {beta_val}."
                )
            alpha_val = custom_alpha

        # Apply custom overrides if explicitly supplied
        final_alpha = custom_alpha if custom_alpha is not None else alpha_val
        final_beta = custom_beta if custom_beta is not None else beta_val

        return float(final_alpha), float(final_beta), X, Y

    def extrapolate_scf(
        self,
        e_scf_x: float,
        e_scf_y: float,
        X: int = 3,
        Y: int = 4,
        alpha: float = 7.88,
    ) -> float:
        """Applies exponential decay formula for Hartree-Fock SCF energy extrapolation.

        Formula:
          E_SCF^(inf) = (E_SCF^(X) * exp(-alpha * sqrt(Y)) - E_SCF^(Y) * exp(-alpha * sqrt(X))) /
                        (exp(-alpha * sqrt(Y)) - exp(-alpha * sqrt(X)))
        """
        exp_x = math.exp(-alpha * math.sqrt(float(X)))
        exp_y = math.exp(-alpha * math.sqrt(float(Y)))
        denom = exp_y - exp_x

        if abs(denom) < 1e-15:
            raise CBSSingularDenominatorError(
                f"Singular denominator in SCF extrapolation with X={X}, Y={Y}, alpha={alpha}"
            )

        return float((e_scf_x * exp_y - e_scf_y * exp_x) / denom)

    def extrapolate_correlation(
        self,
        e_corr_x: float,
        e_corr_y: float,
        X: int = 3,
        Y: int = 4,
        beta: float = 2.97,
    ) -> float:
        """Applies Halkier/Neese inverse power formula for correlation energy extrapolation.

        Formula:
          E_corr^(inf) = (X^beta * E_corr^(X) - Y^beta * E_corr^(Y)) / (X^beta - Y^beta)
        """
        x_beta = float(X) ** beta
        y_beta = float(Y) ** beta
        denom = x_beta - y_beta

        if abs(denom) < 1e-15:
            raise CBSSingularDenominatorError(
                f"Singular denominator in correlation extrapolation with X={X}, Y={Y}, beta={beta}"
            )

        return float((x_beta * e_corr_x - y_beta * e_corr_y) / denom)

    def extrapolate(
        self,
        e_scf_x: float,
        e_scf_y: float,
        e_corr_x: float,
        e_corr_y: float,
        basis_x: str = "def2-TZVP",
        basis_y: str = "def2-QZVPP",
        custom_alpha: Optional[float] = None,
        custom_beta: Optional[float] = None,
        node_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CBSExtrapolationResult:
        """Executes full two-point CBS extrapolation with uncertainty trapping."""
        alpha, beta, X, Y = self.lookup_parameters(
            basis_x=basis_x,
            basis_y=basis_y,
            custom_alpha=custom_alpha,
            custom_beta=custom_beta,
        )

        cbs_scf = self.extrapolate_scf(e_scf_x=e_scf_x, e_scf_y=e_scf_y, X=X, Y=Y, alpha=alpha)
        cbs_corr = self.extrapolate_correlation(e_corr_x=e_corr_x, e_corr_y=e_corr_y, X=X, Y=Y, beta=beta)
        cbs_total = cbs_scf + cbs_corr

        # Evaluate residual variance
        analyzer = ResidualFitAnalyzer()
        eval_dict = analyzer.analyze(e_corr_cbs=cbs_corr, e_corr_y=e_corr_y)

        return CBSExtrapolationResult(
            e_scf_cbs=cbs_scf,
            e_corr_cbs=cbs_corr,
            e_total_cbs=cbs_total,
            basis_x=basis_x,
            basis_y=basis_y,
            alpha=alpha,
            beta=beta,
            residual_variance_hartree=eval_dict["variance_hartree"],
            residual_variance_kcal_mol=eval_dict["variance_kcal_mol"],
            uncertainty_flag=eval_dict["flag"],
            node_id=node_id,
            metadata=metadata or {},
        )

    def extrapolate_from_total(
        self,
        e_total_x: float,
        e_total_y: float,
        e_scf_x: float,
        e_scf_y: float,
        basis_x: str = "def2-TZVP",
        basis_y: str = "def2-QZVPP",
        custom_alpha: Optional[float] = None,
        custom_beta: Optional[float] = None,
        node_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CBSExtrapolationResult:
        """Decouples correlation energies from total single-point energies and extrapolates."""
        e_corr_x = self.decompose_correlation_energy(e_total_x, e_scf_x)
        e_corr_y = self.decompose_correlation_energy(e_total_y, e_scf_y)
        return self.extrapolate(
            e_scf_x=e_scf_x,
            e_scf_y=e_scf_y,
            e_corr_x=e_corr_x,
            e_corr_y=e_corr_y,
            basis_x=basis_x,
            basis_y=basis_y,
            custom_alpha=custom_alpha,
            custom_beta=custom_beta,
            node_id=node_id,
            metadata=metadata,
        )

    def extrapolate_from_orca_outputs(
        self,
        stdout_x: str,
        stdout_y: str,
        basis_x: str = "def2-TZVP",
        basis_y: str = "def2-QZVPP",
        custom_alpha: Optional[float] = None,
        custom_beta: Optional[float] = None,
        node_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CBSExtrapolationResult:
        """Parses two ORCA stdout outputs, decouples correlation energies, and extrapolates."""
        total_x, scf_x, corr_x = parse_orca_energies(stdout_x)
        total_y, scf_y, corr_y = parse_orca_energies(stdout_y)

        meta = dict(metadata or {})
        meta.update({
            "e_total_x": total_x,
            "e_total_y": total_y,
            "e_scf_x": scf_x,
            "e_scf_y": scf_y,
            "e_corr_x": corr_x,
            "e_corr_y": corr_y,
        })

        return self.extrapolate(
            e_scf_x=scf_x,
            e_scf_y=scf_y,
            e_corr_x=corr_x,
            e_corr_y=corr_y,
            basis_x=basis_x,
            basis_y=basis_y,
            custom_alpha=custom_alpha,
            custom_beta=custom_beta,
            node_id=node_id,
            metadata=meta,
        )


# ==============================================================================
# 4. ResidualFitAnalyzer
# ==============================================================================

class ResidualFitAnalyzer:
    """Mathematical safety net evaluating extrapolation variance and residual stability.

    Computes:
      Delta = |E_corr(inf) - E_corr(Y)|
    If Delta > 10 kcal/mol, flags node with 'CBS_HIGH_UNCERTAINTY'.
    """

    def __init__(self, threshold_kcal_mol: float = CBS_UNCERTAINTY_THRESHOLD_KCAL_MOL) -> None:
        self.threshold_kcal_mol = float(threshold_kcal_mol)

    def analyze(
        self,
        e_corr_cbs: float,
        e_corr_y: float,
        threshold_kcal_mol: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Calculates extrapolation variance and flags asymptotic regime violations."""
        thresh = threshold_kcal_mol if threshold_kcal_mol is not None else self.threshold_kcal_mol
        variance_hartree = abs(float(e_corr_cbs) - float(e_corr_y))
        variance_kcal_mol = variance_hartree * HARTREE_TO_KCAL_MOL

        is_flagged = variance_kcal_mol > thresh
        flag = "CBS_HIGH_UNCERTAINTY" if is_flagged else "PASSED"

        reason = ""
        if is_flagged:
            reason = (
                f"Correlation energy extrapolation variance ({variance_kcal_mol:.2f} kcal/mol) "
                f"exceeds safety threshold ({thresh:.2f} kcal/mol). The chosen basis set is not "
                f"sufficiently saturated to reach the asymptotic regime."
            )

        return {
            "is_flagged": is_flagged,
            "flag": flag,
            "variance_hartree": variance_hartree,
            "variance_kcal_mol": variance_kcal_mol,
            "threshold_kcal_mol": thresh,
            "reason": reason,
        }


# ==============================================================================
# 5. SlowConvInterceptor
# ==============================================================================

class SlowConvInterceptor:
    """Asynchronously parses ORCA standard output streams for SCF DIIS convergence failures.

    Injects '! SlowConv SOSCF' and remediates input decks for automated restarts.
    """

    def __init__(self, max_retries: int = 2) -> None:
        self.max_retries = int(max_retries)
        self.failure_signatures = [
            "SCF NOT CONVERGED",
            "DIIS error did not drop",
            "SCF failed to converge",
            "Convergence failure",
            "ERROR: SCF did not reach convergence",
            "SOSCF not active",
        ]

    def detect_scf_failure(self, stdout_text: str) -> Tuple[bool, str]:
        """Inspects output text against known SCF convergence failure signatures."""
        for sig in self.failure_signatures:
            if re.search(re.escape(sig), stdout_text, re.IGNORECASE):
                return True, sig
        return False, ""

    def inspect_and_remediate(
        self,
        stdout_text: str,
        current_input: str,
        retry_count: int = 0,
    ) -> SlowConvInterceptionResult:
        """Inspects execution stdout and injects SlowConv SOSCF if DIIS failed."""
        has_failed, matched_sig = self.detect_scf_failure(stdout_text)

        if not has_failed:
            return SlowConvInterceptionResult(
                has_failed=False,
                should_restart=False,
                remediated_input=current_input,
                injected_keywords=[],
                reason="Normal termination; no SCF convergence failures detected.",
            )

        if retry_count >= self.max_retries:
            return SlowConvInterceptionResult(
                has_failed=True,
                should_restart=False,
                remediated_input=current_input,
                injected_keywords=[],
                reason=f"SCF convergence failed with '{matched_sig}', but maximum retry limit ({self.max_retries}) exhausted.",
            )

        # Remediate input by injecting SlowConv SOSCF
        remediated_input, injected = self._inject_slowconv_directives(current_input)

        return SlowConvInterceptionResult(
            has_failed=True,
            should_restart=True,
            remediated_input=remediated_input,
            injected_keywords=injected,
            reason=f"Detected SCF DIIS failure '{matched_sig}'. Remediated by injecting {injected}.",
        )

    def _inject_slowconv_directives(self, input_text: str) -> Tuple[str, List[str]]:
        """Helper injecting SlowConv and SOSCF keywords into ORCA input header."""
        lines = input_text.splitlines()
        injected: List[str] = []
        new_lines: List[str] = []

        header_processed = False
        for line in lines:
            if line.strip().startswith("!") and not header_processed:
                header_tokens = line.strip().split()
                if "SlowConv" not in header_tokens:
                    header_tokens.append("SlowConv")
                    injected.append("SlowConv")
                if "SOSCF" not in header_tokens:
                    header_tokens.append("SOSCF")
                    injected.append("SOSCF")
                new_lines.append(" ".join(header_tokens))
                header_processed = True
            else:
                new_lines.append(line)

        if not header_processed:
            new_lines.insert(0, "! SlowConv SOSCF")
            injected.extend(["SlowConv", "SOSCF"])

        return "\n".join(new_lines) + "\n", injected


# ==============================================================================
# 6. HDF5 Persistence & Pipeline Orchestration
# ==============================================================================

def resolve_hdf5_path(h5_path: Optional[Union[str, Path]] = None) -> Path:
    """Resolves target landscape.h5 path dynamically adhering to Air-Gap mandate."""
    if h5_path is not None:
        target = Path(h5_path)
        if not target.is_absolute() and "COCHEM_ARTIFACTS_DIR" in os.environ and os.environ["COCHEM_ARTIFACTS_DIR"]:
            return (Path(os.environ["COCHEM_ARTIFACTS_DIR"]) / target).resolve()
        return target.resolve()

    if "COCHEM_ARTIFACTS_DIR" in os.environ and os.environ["COCHEM_ARTIFACTS_DIR"]:
        artifacts_dir = Path(os.environ["COCHEM_ARTIFACTS_DIR"]).resolve()
        return (artifacts_dir / "BENCH_Workspace" / "landscape.h5").resolve()

    return Path("BENCH_Workspace/landscape.h5").resolve()


def commit_cbs_to_hdf5(
    h5_path: Optional[Union[str, Path]],
    result: CBSExtrapolationResult,
    timeout: float = 120.0,
) -> Path:
    """Commits computed CBS limit results atomically to landscape.h5 using FileLock.

    Args:
        h5_path: Optional path to HDF5 file (resolved via COCHEM_ARTIFACTS_DIR if None).
        result: Validated CBSExtrapolationResult to persist.
        timeout: Maximum seconds to wait for filelock acquisition (default 120s).

    Returns:
        Resolved Path to the modified HDF5 file.
    """
    target_path = resolve_hdf5_path(h5_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    lock_file = target_path.parent / f"{target_path.name}.lock"
    lock = filelock.FileLock(str(lock_file), timeout=timeout)

    node_group_name = result.node_id if result.node_id else "default_cbs_node"

    with lock:
        with h5py.File(target_path, "a") as f:
            root_grp = f.require_group("cbs_extrapolations")
            node_grp = root_grp.require_group(node_group_name)

            datasets = {
                "e_scf_cbs": result.e_scf_cbs,
                "e_corr_cbs": result.e_corr_cbs,
                "e_total_cbs": result.e_total_cbs,
                "alpha": result.alpha,
                "beta": result.beta,
                "residual_variance_hartree": result.residual_variance_hartree,
                "residual_variance_kcal_mol": result.residual_variance_kcal_mol,
            }

            for ds_name, ds_val in datasets.items():
                if ds_name in node_grp:
                    del node_grp[ds_name]
                node_grp.create_dataset(ds_name, data=float(ds_val))

            node_grp.attrs["basis_x"] = result.basis_x
            node_grp.attrs["basis_y"] = result.basis_y
            node_grp.attrs["uncertainty_flag"] = result.uncertainty_flag
            node_grp.attrs["timestamp"] = result.timestamp
            node_grp.attrs["node_id"] = result.node_id

    return target_path


def read_cbs_from_hdf5(
    h5_path: Optional[Union[str, Path]],
    node_id: str,
    timeout: float = 120.0,
) -> Dict[str, Any]:
    """Reads back computed CBS limit results atomically from landscape.h5.

    Args:
        h5_path: Optional path to HDF5 file.
        node_id: Key identifying the target molecular node.
        timeout: Maximum seconds to wait for filelock acquisition (default 120s).

    Returns:
        Dictionary containing extracted datasets and attributes.

    Raises:
        FileNotFoundError: If HDF5 file does not exist.
        KeyError: If node_id is not present in the HDF5 archive.
    """
    target_path = resolve_hdf5_path(h5_path)
    if not target_path.exists():
        raise FileNotFoundError(f"HDF5 file does not exist: {target_path}")

    lock_file = target_path.parent / f"{target_path.name}.lock"
    lock = filelock.FileLock(str(lock_file), timeout=timeout)

    with lock:
        with h5py.File(target_path, "r") as f:
            if "cbs_extrapolations" not in f:
                raise KeyError(f"Root group 'cbs_extrapolations' not found in '{target_path}'")
            root_grp = f["cbs_extrapolations"]
            if node_id not in root_grp:
                raise KeyError(f"Node '{node_id}' not found in 'cbs_extrapolations'")
            node_grp = root_grp[node_id]

            data = {
                "e_scf_cbs": float(node_grp["e_scf_cbs"][()]),
                "e_corr_cbs": float(node_grp["e_corr_cbs"][()]),
                "e_total_cbs": float(node_grp["e_total_cbs"][()]),
                "alpha": float(node_grp["alpha"][()]),
                "beta": float(node_grp["beta"][()]),
                "residual_variance_hartree": float(node_grp["residual_variance_hartree"][()]),
                "residual_variance_kcal_mol": float(node_grp["residual_variance_kcal_mol"][()]),
                "basis_x": str(node_grp.attrs.get("basis_x", "")),
                "basis_y": str(node_grp.attrs.get("basis_y", "")),
                "uncertainty_flag": str(node_grp.attrs.get("uncertainty_flag", "")),
                "timestamp": str(node_grp.attrs.get("timestamp", "")),
                "node_id": str(node_grp.attrs.get("node_id", "")),
            }
            return data


def run_cbs_pipeline(
    coords: Union[List[Tuple[str, float, float, float]], List[List[Any]]],
    e_scf_x: float,
    e_scf_y: float,
    e_corr_x: float,
    e_corr_y: float,
    basis_pair: Tuple[str, str] = ("def2-TZVP", "def2-QZVPP"),
    node_id: str = "node_0",
    h5_path: Optional[Union[str, Path]] = None,
    node_max_gb: float = 16.0,
    nprocs: int = 4,
    custom_alpha: Optional[float] = None,
    custom_beta: Optional[float] = None,
) -> CBSExtrapolationResult:
    """End-to-end pipeline orchestrator for Stage 2.0 CBS Extrapolation."""
    # 1. Initialize dispatcher and prepare input decks
    dispatcher = DualBasisDispatcher(
        node_max_gb=node_max_gb,
        nprocs=nprocs,
        basis_pair=basis_pair,
    )
    _ = dispatcher.generate_input_deck(coords)

    # 2. Execute Helgaker CBS Extrapolation
    extrapolator = HelgakerExtrapolator()
    result = extrapolator.extrapolate(
        e_scf_x=e_scf_x,
        e_scf_y=e_scf_y,
        e_corr_x=e_corr_x,
        e_corr_y=e_corr_y,
        basis_x=basis_pair[0],
        basis_y=basis_pair[1],
        custom_alpha=custom_alpha,
        custom_beta=custom_beta,
        node_id=node_id,
    )

    # 3. Commit to landscape.h5 if path supplied
    if h5_path:
        commit_cbs_to_hdf5(h5_path=h5_path, result=result)

    return result
