"""
electronic_sanitizer.py - Electronic Structure Keyword Sanitizer & Spin Contamination Gatekeeper.
Method Matrix v4.1: §2.8, §2.9, Verification Requirement VR-05.
Standard Compliance: IEEE 830-1998 / Method Matrix v4.1 Zero-Trust Directive.
"""
from __future__ import annotations

import logging
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
        fn_clean = functional.strip().upper()
        disp_clean = dispersion.strip().upper() if dispersion else ""

        # Check for non-local VV10 double-counting
        is_vv10 = any(nl in fn_clean for nl in NON_LOCAL_VV10_FUNCTIONALS)
        has_empirical = any(d in disp_clean for d in ["D3", "D4", "D3BJ", "D3ZERO"]) or any(
            d in fn_clean for d in ["-D3", "-D4", "-D3BJ"]
        )

        if is_vv10 and has_empirical:
            raise RedundantDispersionError(
                f"[REDUNDANT_DISPERSION] Functional '{functional}' has native non-local VV10 dispersion; "
                f"pairing with explicit empirical dispersion '{dispersion or fn_clean}' produces unphysical "
                f"double-counting of dispersive energy [M]."
            )

        # Check for missing dispersion on intermolecular complexes
        if is_complex and not is_vv10 and not has_empirical:
            is_req_hybrid = any(h in fn_clean for h in HYBRID_DISPERSION_REQUIRING)
            if is_req_hybrid or not has_empirical:
                raise MissingDispersionError(
                    f"[DISPERSION_MISSING] Standard functional '{functional}' lacks required empirical "
                    f"dispersion (D3BJ/D4) for non-covalent complex calculation [M]."
                )

        # Axilrod-Teller-Muto (ATM) 3-body dispersion for trimers and higher clusters
        requires_atm = (num_monomers >= 3) and (has_empirical or is_vv10)

        return {
            "functional": functional,
            "dispersion": "VV10" if is_vv10 else (dispersion or "None"),
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
        if multiplicity < 1:
            raise ValueError(f"Multiplicity must be >= 1, got {multiplicity}.")

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
            is_pure = rel_pct < relative_threshold_pct
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


__all__ = [
    "NON_LOCAL_VV10_FUNCTIONALS",
    "HYBRID_DISPERSION_REQUIRING",
    "ElectronicSanitizer",
]
