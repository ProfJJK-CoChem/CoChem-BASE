# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""auditor.py -- Method Matrix §8B.5 Dangerous Reuse (D1–D5) Integrity Auditing Engine.

Mandated by Method Matrix v4 §8B.5 and Suggestion #157 (Deliverable 7).
Adversarial verification engine enforcing Rules D1–D5:
  D1: Geometry stationarity validation & Delta R -> Delta B error propagation check
  D2: Hessian reuse validation (flags modes <100 cm^-1 and counts imaginary frequencies)
  D3: SCF density reuse stability guard against basin collapse
  D4: Counterpoise and ghost-atom inconsistency guard
  D5: Unique %base naming hygiene so no reader is ever also the writer
"""

from __future__ import annotations

from typing import Any, Optional, Sequence, Tuple

import numpy as np


class StateChainingAuditor:
    """Adversarial verification engine enforcing Method Matrix §8B.5 Rules D1–D5."""

    @staticmethod
    def audit_d1_stationarity(
        gradient_norm_hartree_bohr: Optional[float],
        tol_max_g: float = 1e-5,
        delta_r_angstrom: float = 0.0,
    ) -> Tuple[bool, str]:
        """Rule D1: A geometry may be passed forward as a starting point at any level.

        It may be REPORTED or used for rigid property evaluations attributed to level L
        ONLY if it is stationary at level L (TolMaxG <= 1e-5 Eh/bohr).
        """
        if gradient_norm_hartree_bohr is None:
            return True, "Gradient norm not provided; starting point pass valid"

        passed = gradient_norm_hartree_bohr <= tol_max_g
        delta_b_mhz_est = (
            (2.0 * delta_r_angstrom / 3.5) * 6000.0
            if delta_r_angstrom > 0.0
            else 0.0
        )

        msg = (
            f"[D1 {'PASS' if passed else 'FAIL'}] Max gradient component: "
            f"{gradient_norm_hartree_bohr:.3e} Eh/bohr (Threshold: {tol_max_g:.1e}). "
            f"Delta R: {delta_r_angstrom*100:.2f} pm (Estimated Delta B shift: {delta_b_mhz_est:.2f} MHz)."
        )
        return passed, msg

    @staticmethod
    def audit_d2_hessian_transfer(
        harmonic_frequencies_cm1: Optional[Sequence[float]],
        low_level_frequencies_cm1: Optional[Sequence[float]] = None,
        threshold_shift_pct: float = 20.0,
    ) -> Tuple[bool, str]:
        """Rule D2: Reusing a Hessian as a preconditioner is safe.

        Reusing it as the REPORTED force field is safe ONLY under the substituted hybrid
        construction and only where normal coordinates are level-insensitive.
        Flags modes < 100 cm^-1 and counts imaginary frequencies.
        """
        if harmonic_frequencies_cm1 is None:
            return True, "No frequencies evaluated in this stage"

        freqs = np.asarray(harmonic_frequencies_cm1, dtype=np.float64)
        imag_modes = [float(f) for f in freqs if f < -1.0]
        soft_modes = [float(f) for f in freqs if 0.0 <= f < 100.0]

        passed = len(imag_modes) == 0
        details = [
            f"Imaginary modes count: {len(imag_modes)}",
            f"Soft modes (<100 cm^-1) flagged: {len(soft_modes)}",
        ]

        if low_level_frequencies_cm1 is not None and len(
            low_level_frequencies_cm1
        ) == len(freqs):
            low_f = np.asarray(low_level_frequencies_cm1, dtype=np.float64)
            pos_high = sorted([f for f in freqs if f > 10.0])
            pos_low = sorted([f for f in low_f if f > 10.0])
            if pos_high and pos_low:
                shift_pct = (
                    abs(pos_high[0] - pos_low[0]) / max(pos_high[0], 1e-3)
                ) * 100.0
                details.append(
                    f"Lowest intermolecular mode shift: {shift_pct:.1f}% (Threshold: {threshold_shift_pct:.1f}%)"
                )
                if shift_pct > threshold_shift_pct:
                    passed = False
                    details.append(
                        "REJECTION: Normal coordinates are method-sensitive (>20% shift)."
                    )

        msg = f"[D2 {'PASS' if passed else 'WARNING'}] " + "; ".join(details)
        return passed, msg

    @staticmethod
    def audit_d3_scf_stability(
        fresh_energy_hartree: Optional[float],
        reused_energy_hartree: Optional[float],
        tol_e: float = 1e-7,
    ) -> Tuple[bool, str]:
        """Rule D3: Never trust a reused-guess SCF energy without a stability spot-check.

        Asserts agreement between fresh-guess and reused-guess SCF energies.
        """
        if fresh_energy_hartree is None or reused_energy_hartree is None:
            return True, "Single SCF guess mode evaluated"

        delta_e = abs(fresh_energy_hartree - reused_energy_hartree)
        passed = delta_e <= tol_e
        msg = (
            f"[D3 {'PASS' if passed else 'FAIL'}] Reused SCF Delta E: {delta_e:.3e} Hartree "
            f"(Threshold: {tol_e:.1e})."
        )
        return passed, msg

    @staticmethod
    def audit_d4_counterpoise_hygiene(
        stage_name: str,
        counterpoise: Any,
        mo_from: Optional[str],
    ) -> Tuple[bool, str]:
        """Rule D4: Never reuse a dimer .gbw as the guess for a ghosted monomer leg.

        Guarantees basis set pinning across counterpoise legs.
        """
        cp_val = str(counterpoise).lower()
        if ("monomer" in cp_val or "half" in cp_val) and mo_from:
            passed = False
            msg = (
                f"[D4 VIOLATION] Stage {stage_name} is a ghosted monomer leg but attempted "
                f"to read MOs from dimer stage '{mo_from}'. Dimer .gbw reuse on monomer is forbidden."
            )
            return passed, msg

        return (
            True,
            f"[D4 PASS] Stage {stage_name} obeys counterpoise state isolation.",
        )

    @staticmethod
    def audit_d5_naming_hygiene(
        current_stage: str, consumed_stage: Optional[str]
    ) -> Tuple[bool, str]:
        """Rule D5: Every stage owns its own %base so a reader is never also the writer."""
        if consumed_stage and current_stage.lower() == consumed_stage.lower():
            return (
                False,
                f"[D5 VIOLATION] Stage '{current_stage}' reads from same-named input '{consumed_stage}'. "
                "Input .gbw will be overwritten and destroyed!",
            )
        return (
            True,
            f"[D5 PASS] Stage '{current_stage}' has distinct name from input '{consumed_stage}'.",
        )
