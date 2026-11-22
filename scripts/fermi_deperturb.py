#!/usr/bin/env python3
"""Exact 2x2 Secular Matrix Martin Fermi Resonance Dyad Deperturbation.

CHEM 312 Module 3 (Tennessee Tech University) — Recovers the unperturbed bright
fundamental frequency nu_1^0, unperturbed dark overtone/combination frequency
2*nu_2^0, cubic Fermi coupling constant |W|, and mixing angle theta from an
observed Fermi doublet (nu_+, nu_-) and intensity ratio R = I_- / I_+.

Secular Hamiltonian (bright fundamental |1>, dark overtone |2>):
    H = [[nu_1^0,   W   ],
         [  W,    2*nu_2^0]]

Exact algebraic inversion (intensity borrowing: I_+ = I_1^0 cos^2(theta),
I_- = I_1^0 sin^2(theta), so R = I_- / I_+ = tan^2(theta)):
    cos^2(theta) = 1 / (1 + R),   sin^2(theta) = R / (1 + R)
    nu_1^0       = (nu_+ + R * nu_-) / (1 + R)
    2*nu_2^0     = (R * nu_+ + nu_-) / (1 + R)
    |W|          = (nu_+ - nu_-) * sqrt(R) / (1 + R)
    theta        = arctan(sqrt(R))

Verified on CHEM 312 Team 4 ethylene carbonate (1774 / 1803 cm^-1 doublet) and
Team 6 d4-ethylene carbonate (1792 cm^-1 collapsed unperturbed C=O fundamental).
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def deperturb_fermi_dyad(
    nu_plus_cm1: float,
    nu_minus_cm1: float,
    intensity_ratio_minus_over_plus: float,
    *,
    label: str = "fermi_dyad",
    isotopologue_unperturbed_cm1: float | None = None,
) -> dict[str, Any]:
    """Invert a 2x2 Fermi resonance doublet and verify eigenvalue round-trip."""
    nu_p = float(nu_plus_cm1)
    nu_m = float(nu_minus_cm1)
    ratio = float(intensity_ratio_minus_over_plus)

    if not (math.isfinite(nu_p) and math.isfinite(nu_m) and math.isfinite(ratio)):
        raise ValueError("Input frequencies and intensity ratio must be finite.")
    if ratio < 0.0:
        raise ValueError(f"Intensity ratio R = I_-/I_+ must be >= 0, got {ratio}.")
    if nu_p < nu_m:
        raise ValueError(f"Expected nu_plus >= nu_minus, got nu_plus={nu_p}, nu_minus={nu_m}.")

    delta_obs = nu_p - nu_m
    denom = 1.0 + ratio
    cos2_theta = 1.0 / denom
    sin2_theta = ratio / denom
    theta_rad = math.atan(math.sqrt(ratio))
    theta_deg = math.degrees(theta_rad)

    nu1_unperturbed = (nu_p + ratio * nu_m) / denom
    nu2_overtone_unperturbed = (ratio * nu_p + nu_m) / denom
    delta_unperturbed = nu1_unperturbed - nu2_overtone_unperturbed
    w_coupling = delta_obs * math.sqrt(ratio) / denom

    # Exact 2x2 secular matrix round-trip reconstruction
    secular = np.array(
        [
            [nu1_unperturbed, w_coupling],
            [w_coupling, nu2_overtone_unperturbed],
        ],
        dtype=np.float64,
    )
    eigvals, eigvecs = np.linalg.eigh(secular)
    rec_minus = float(eigvals[0])
    rec_plus = float(eigvals[1])
    max_eig_residual = max(abs(rec_plus - nu_p), abs(rec_minus - nu_m))

    # Reconstructed intensity ratio from bright-state component |<1|psi_->|^2 / |<1|psi_+>|^2
    c1_minus_sq = float(eigvecs[0, 0] ** 2)
    c1_plus_sq = float(eigvecs[0, 1] ** 2)
    rec_ratio = (c1_minus_sq / c1_plus_sq) if c1_plus_sq > 0.0 else float("inf")
    ratio_residual = abs(rec_ratio - ratio) if math.isfinite(rec_ratio) else 0.0

    iso_block: dict[str, Any]
    if isotopologue_unperturbed_cm1 is not None:
        iso_nu = float(isotopologue_unperturbed_cm1)
        iso_block = {
            "status": "COMPARED",
            "isotopologue_unperturbed_cm1": iso_nu,
            "nu1_minus_isotopologue_cm1": nu1_unperturbed - iso_nu,
        }
    else:
        iso_block = {
            "status": "PENDING",
            "isotopologue_unperturbed_cm1": None,
            "nu1_minus_isotopologue_cm1": None,
        }

    return {
        "schema": "cochem.fermi-deperturbation/1",
        "collaborator_institution": "Tennessee Tech University",
        "course_id": "CHEM312",
        "created_at_utc": _utc_now(),
        "label": label,
        "collapsed_uncoupled_limit": bool(ratio == 0.0 or delta_obs == 0.0),
        "observed": {
            "nu_plus_cm1": nu_p,
            "nu_minus_cm1": nu_m,
            "observed_splitting_cm1": delta_obs,
            "intensity_ratio_r_minus_over_plus": ratio,
        },
        "deperturbed": {
            "nu_1_unperturbed_cm1": nu1_unperturbed,
            "two_nu_2_unperturbed_cm1": nu2_overtone_unperturbed,
            "unperturbed_splitting_delta_cm1": delta_unperturbed,
            "coupling_W_cm1": w_coupling,
            "mixing_angle_rad": theta_rad,
            "mixing_angle_deg": theta_deg,
            "bright_weight_plus_cos2": cos2_theta,
            "bright_weight_minus_sin2": sin2_theta,
            "trace_sum_cm1": nu1_unperturbed + nu2_overtone_unperturbed,
        },
        "roundtrip_verification": {
            "secular_matrix_cm1": [
                [nu1_unperturbed, w_coupling],
                [w_coupling, nu2_overtone_unperturbed],
            ],
            "reconstructed_nu_plus_cm1": rec_plus,
            "reconstructed_nu_minus_cm1": rec_minus,
            "max_eigenvalue_residual_cm1": max_eig_residual,
            "reconstructed_intensity_ratio": rec_ratio,
            "intensity_ratio_residual": ratio_residual,
        },
        "isotopologue_collapse_check": iso_block,
    }


def render_markdown(res: Mapping[str, Any]) -> str:
    obs = res["observed"]
    dep = res["deperturbed"]
    ver = res["roundtrip_verification"]
    iso = res["isotopologue_collapse_check"]
    lines = [
        f"# CHEM 312 M3 Fermi Resonance Deperturbation — `{res['label']}`",
        "",
        f"- **Institution:** {res['collaborator_institution']}",
        f"- **Timestamp (UTC):** {res['created_at_utc']}",
        "",
        "## Observed Doublet vs Deperturbed Uncoupled States",
        "",
        "| Parameter | Value | Unit |",
        "| --- | ---: | --- |",
        f"| $\\nu_+$ (upper observed peak) | {obs['nu_plus_cm1']:.4f} | cm^-1 |",
        f"| $\\nu_-$ (lower observed peak) | {obs['nu_minus_cm1']:.4f} | cm^-1 |",
        f"| Observed splitting $\\Delta = \\nu_+ - \\nu_-$ | {obs['observed_splitting_cm1']:.4f} | cm^-1 |",
        f"| Intensity ratio $R = I_- / I_+$ | {obs['intensity_ratio_r_minus_over_plus']:.6f} | — |",
        f"| Unperturbed bright fundamental $\\nu_1^0$ | {dep['nu_1_unperturbed_cm1']:.4f} | cm^-1 |",
        f"| Unperturbed dark overtone $2\\nu_2^0$ | {dep['two_nu_2_unperturbed_cm1']:.4f} | cm^-1 |",
        f"| Coupling constant $|W|$ | {dep['coupling_W_cm1']:.4f} | cm^-1 |",
        f"| Mixing angle $\\theta$ | {dep['mixing_angle_deg']:.3f} | deg |",
        f"| Eigenvalue round-trip residual | {ver['max_eigenvalue_residual_cm1']:.3e} | cm^-1 |",
    ]
    if iso["status"] == "COMPARED":
        lines.append(
            f"| Isotopologue collapsed $\\nu$ (residual $\\nu_1^0 - \\nu_{{\\text{{iso}}}}$) | "
            f"{iso['isotopologue_unperturbed_cm1']:.2f} ({iso['nu1_minus_isotopologue_cm1']:+.2f}) | cm^-1 |"
        )
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Exact 2x2 Martin Fermi resonance dyad deperturbation (CHEM 312 M3)."
    )
    p.add_argument("--nu-plus", required=True, type=float, help="Upper observed doublet frequency nu_+ (cm^-1).")
    p.add_argument("--nu-minus", required=True, type=float, help="Lower observed doublet frequency nu_- (cm^-1).")
    ratio_group = p.add_mutually_exclusive_group(required=True)
    ratio_group.add_argument("--intensity-ratio", type=float, help="Observed intensity ratio R = I_- / I_+.")
    ratio_group.add_argument("--i-minus-plus", nargs=2, type=float, metavar=("I_MINUS", "I_PLUS"), help="Observed intensities I_- and I_+.")
    p.add_argument("--label", default="fermi_dyad", help="System/dyad label (e.g., Team4_EC_CO_dyad).")
    p.add_argument("--isotopologue-nu", type=float, default=None, help="Optional collapsed isotopologue frequency (e.g., 1792.0 for d4-EC).")
    p.add_argument("--output-json", type=Path, default=None, help="Optional output JSON path.")
    p.add_argument("--output-md", type=Path, default=None, help="Optional output Markdown path.")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.intensity_ratio is not None:
        ratio = float(args.intensity_ratio)
    else:
        i_minus, i_plus = args.i_minus_plus
        if i_plus <= 0.0:
            raise ValueError(f"Upper-band intensity I_+ must be > 0, got {i_plus}.")
        ratio = float(i_minus) / float(i_plus)

    result = deperturb_fermi_dyad(
        args.nu_plus,
        args.nu_minus,
        ratio,
        label=args.label,
        isotopologue_unperturbed_cm1=args.isotopologue_nu,
    )
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if args.output_md is not None:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_markdown(result), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
