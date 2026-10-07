"""
electronic_sanitizer.py - Electronic Structure Keyword Sanitizer & Spin Contamination Gatekeeper.
Method Matrix v4.1: §2.8, §2.9, Verification Requirement VR-05.
Standard Compliance: IEEE 830-1998 / Method Matrix v4.1 Zero-Trust Directive.
"""
from __future__ import annotations

import logging
import math
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from cochem_base.exceptions import (
    RedundantDispersionError,
    MissingDispersionError,
    SpinContaminationError,
)

logger = logging.getLogger(__name__)

# Native non-local dispersion functionals with VV10 integration [D]
NON_LOCAL_VV10_FUNCTIONALS: Set[str] = {
    "WB97M-V",
    "WB97X-V",
    "REV-WB97M-V",
    "B97M-V",
    "PBE-NL",
}

# Standard hybrid and pure functionals requiring explicit empirical dispersion on complexes [D]
HYBRID_DISPERSION_REQUIRING: Set[str] = {
    "B3LYP",
    "PBE0",
    "WB97X",
    "PBE",
    "BP86",
    "TPSS",
    "M06-2X",
}


class ElectronicSanitizer:
    """Sanitizes functional/dispersion combinations and guards against spin contamination."""

    @staticmethod
    def sanitize_dft_dispersion(
        functional: str,
        dispersion: Optional[str] = None,
        is_complex: bool = False,
        num_monomers: int = 1,
    ) -> Dict[str, Any]:
        """Sanitizes functional and dispersion options against Method Matrix v4.1 §2.8 rules.

        1. Non-local VV10 functionals (e.g. wB97M-V) paired with D3/D4 raise RedundantDispersionError [M].
        2. Standard hybrids lacking dispersion on non-covalent complexes raise MissingDispersionError [M].
        3. Multi-body trimers (num_monomers >= 3) append ATM 3-body dispersion [M].
        """
        fn_clean = functional.strip().upper().replace("Ω", "W").replace("Ω", "W")
        disp_clean = dispersion.strip().upper() if dispersion else ""

        if not isinstance(num_monomers, int) or isinstance(num_monomers, bool) or num_monomers < 1:
            raise ValueError("num_monomers must be a positive integer.")

        # Check for non-local VV10 double-counting
        is_vv10 = any(nl in fn_clean for nl in NON_LOCAL_VV10_FUNCTIONALS)
        empirical = re.findall(r"(?<![A-Z0-9])D(?:3(?:BJ|ZERO)?|4)(?![A-Z0-9])", f"{fn_clean} {disp_clean}")
        has_empirical = bool(empirical)
        composite = any(token in fn_clean.split() for token in ("R2SCAN-3C", "B97-3C", "HF-3C", "PBEH-3C"))
        correlated = bool(re.search(r"\b(?:MP[234]|CCSD|CC2|CC3|CASSCF|NEVPT2|CASPT2)\b", fn_clean))
        tight_binding = bool(re.search(r"\bGFN[012]-?XTB\b", fn_clean))
        # HF and its spin variants are wavefunction methods, not dispersion-free
        # density functionals. A spin-reference keyword alongside an explicit
        # DFT functional must not waive that functional's dispersion policy.
        tokens = fn_clean.split()
        explicit_dft = any(
            re.search(rf"(?<![A-Z0-9]){re.escape(name)}(?![A-Z0-9])", fn_clean)
            for name in HYBRID_DISPERSION_REQUIRING | NON_LOCAL_VV10_FUNCTIONALS
        )
        hartree_fock = bool(tokens and tokens[0] in {"HF", "RHF", "UHF", "ROHF"} and not explicit_dft)

        if is_vv10 and has_empirical:
            raise RedundantDispersionError(
                f"[METHOD_MATRIX_VIOLATION_DISPERSION] External dispersion correction: Functional '{functional}' has native non-local VV10 dispersion; "
                f"pairing with explicit empirical dispersion '{dispersion or fn_clean}' produces unphysical "
                f"double-counting of dispersive energy [M]."
            )
        if re.search(r"\b(?:B3LYP|PBE0)\b", fn_clean) and not any(d in {"D3BJ", "D4"} for d in empirical):
            raise MissingDispersionError("B3LYP/PBE0 require D3BJ or D4 dispersion; undamped D3 is insufficient.")

        # Check for missing dispersion on intermolecular complexes
        if is_complex and not any((is_vv10, has_empirical, composite, correlated, tight_binding, hartree_fock)):
            raise MissingDispersionError(
                f"[DISPERSION_MISSING] Standard functional '{functional}' lacks required empirical "
                f"dispersion (D3BJ/D4) for non-covalent complex calculation [M]."
            )

        # Axilrod-Teller-Muto (ATM) 3-body dispersion for trimers and higher clusters
        requires_atm = (num_monomers >= 3) and has_empirical

        return {
            "functional": functional,
            "dispersion": "VV10" if is_vv10 else (dispersion or (empirical[0] if empirical else "Composite" if composite else "None")),
            "has_non_local_vv10": is_vv10,
            "has_empirical_dispersion": has_empirical,
            "requires_atm_3body": requires_atm,
            "num_monomers": num_monomers,
            "provenance_tag": "[M]",
        }

    @staticmethod
    def diagnose_spin_contamination(
        s2_observed: float,
        multiplicity: int = 1,
        relative_threshold_pct: float = 10.0,
        singlet_threshold: float = 0.05,
    ) -> Dict[str, Any]:
        """Diagnoses open-shell and closed-shell spin contamination with Singularity Guard (VR-05).

        For S > 0: Delta <S^2> = |<S^2> - S(S+1)| / (S(S+1)) * 100% [D].
        For S = 0: Delta <S^2> = |<S^2>| (pure if < 0.05 a.u.) [D].
        Fails closed and triggers T9 CASSCF/NEVPT2 routing upon contamination [M].
        """
        if not isinstance(multiplicity, int) or isinstance(multiplicity, bool) or multiplicity < 1:
            raise ValueError(f"Multiplicity must be >= 1, got {multiplicity}.")
        if not math.isfinite(s2_observed) or s2_observed < 0:
            raise ValueError("Observed <S^2> must be finite and nonnegative.")
        if not math.isfinite(relative_threshold_pct) or not 0 < relative_threshold_pct <= 10:
            raise ValueError("Spin contamination threshold must be positive and no greater than 10 percent.")
        if not math.isfinite(singlet_threshold) or not 0 < singlet_threshold <= 0.05:
            raise ValueError("Singlet contamination threshold must be positive and no greater than 0.05.")

        s_quantum = (multiplicity - 1) / 2.0
        s2_ideal = s_quantum * (s_quantum + 1.0)

        # Piecewise evaluation with Singlet Singularity Guard
        if abs(s_quantum) < 1e-7:
            # Singlet state (S = 0): Evaluate absolute deviation
            deviation = abs(s2_observed)
            is_pure = deviation < singlet_threshold
            rel_pct = 0.0
            error_msg = (
                f"[SPIN_CONTAMINATION_EXCEEDED] Singlet wavefunction exhibits unacceptable spin "
                f"contamination: |<S^2>| = {s2_observed:.4f} exceeds threshold ({singlet_threshold:.4f} a.u.) [M]."
            )
        else:
            # Open-shell state (S > 0): Evaluate relative contamination percentage
            rel_pct = (abs(s2_observed - s2_ideal) / s2_ideal) * 100.0
            deviation = abs(s2_observed - s2_ideal)
            # Account for roundoff at the inclusive 10% rejection boundary.
            is_pure = rel_pct < relative_threshold_pct and not math.isclose(
                rel_pct, relative_threshold_pct, rel_tol=1e-12, abs_tol=1e-12
            )
            error_msg = (
                f"[SPIN_CONTAMINATION_EXCEEDED] Open-shell wavefunction exhibits unacceptable spin "
                f"contamination: Delta <S^2> = {rel_pct:.2f}% exceeds threshold ({relative_threshold_pct:.1f}%) [M]."
            )

        result: Dict[str, Any] = {
            "s2_observed": s2_observed,
            "s2_ideal": s2_ideal,
            "multiplicity": multiplicity,
            "s_quantum": s_quantum,
            "deviation": deviation,
            "relative_percent": rel_pct,
            "is_pure": is_pure,
            "routing_tier": "T4/T5" if is_pure else "T9",
            "routing_target": "STANDARD" if is_pure else "RO-DFT / CASSCF / NEVPT2",
            "provenance_tag": "[M]",
        }

        if not is_pure:
            logger.error(error_msg)
            raise SpinContaminationError(
                message=error_msg,
                details=result,
            )

        return result


class SpinContaminationStreamValidator:
    """Reject contaminated ORCA telemetry as each complete stdout line arrives.

    The process broker owns termination; this callback raises the same typed
    escalation as artifact validation. It does not invent an active space or
    execute a multireference calculation.
    """

    _expectation = re.compile(r"Expectation value of <S(?:\*\*|\^)2>\s*:\s*(\S+)", re.I)
    _expectation_label = re.compile(r"Expectation value of <S(?:\*\*|\^)2>", re.I)
    _ideal = re.compile(r"Ideal value S\*\(S\+1\)\s*:\s*(\S+)", re.I)
    _ideal_label = re.compile(r"Ideal value S\*\(S\+1\)", re.I)

    def __init__(self, multiplicity: int, relative_threshold: float = 0.1) -> None:
        if isinstance(multiplicity, bool) or not isinstance(multiplicity, int) or multiplicity < 1:
            raise ValueError("Spin multiplicity must be a positive integer.")
        if not math.isfinite(relative_threshold) or not 0 < relative_threshold <= 0.1:
            raise ValueError("Relative spin threshold must be in (0, 0.1].")
        self.multiplicity = multiplicity
        self.relative_threshold = relative_threshold
        self.observations = 0
        self.last_result: Optional[Dict[str, Any]] = None

    def __call__(self, line: str) -> None:
        match = self._expectation.search(line)
        if match:
            try:
                observed = float(match.group(1).replace("D", "E").replace("d", "e"))
            except ValueError as exc:
                raise ValueError("Malformed spin expectation in engine telemetry.") from exc
            self.last_result = ElectronicSanitizer.diagnose_spin_contamination(
                observed, self.multiplicity, relative_threshold_pct=100 * self.relative_threshold,
            )
            self.observations += 1
        elif self._expectation_label.search(line):
            raise ValueError("Missing spin expectation value in engine telemetry.")
        ideal = self._ideal.search(line)
        if ideal:
            value = float(ideal.group(1).replace("D", "E").replace("d", "e"))
            spin = (self.multiplicity - 1) / 2
            if not math.isfinite(value) or not math.isclose(value, spin * (spin + 1), abs_tol=1e-6):
                raise ValueError("Engine ideal spin is inconsistent with the requested multiplicity.")
        elif self._ideal_label.search(line):
            raise ValueError("Missing ideal spin value in engine telemetry.")


__all__ = [
    "NON_LOCAL_VV10_FUNCTIONALS",
    "HYBRID_DISPERSION_REQUIRING",
    "ElectronicSanitizer",
    "SpinContaminationStreamValidator",
]
