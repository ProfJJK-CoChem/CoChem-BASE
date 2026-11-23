#!/usr/bin/env python3
"""Kraitchman Single-Substitution |r_s| Coordinate Calculator (Planar & Non-Planar Rigid Rotor).

CHEM 312 / 312L Organic Chemistry II Lab (Cumberland University, partnering with
Tennessee Tech University CP-FTMW rotational spectroscopy collaborators).

Computes principal-axis substitution coordinates |a|, |b|, |c| (in Angstroms)
from parent and singly-substituted isotopologue rotational constants (A, B, C in MHz),
parent molecular mass M (in amu), and isotopic mass change Delta_m (in amu) using
Kraitchman's exact rigid-rotor single-substitution equations (Kraitchman 1953,
Am. J. Phys. 21, 17; Gordy & Cook, Microwave Molecular Spectra, Ch. 13):

  - Moment of inertia conversion (CODATA 2018):
      K = h / (8 * pi^2 * u * 1e-14) = 505379.04596 MHz * u * A^2
      I_alpha = K / B_alpha   (alpha in {a, b, c})
  - Planar second moments:
      P_a = 0.5 * (-I_a + I_b + I_c)
      P_b = 0.5 * ( I_a - I_b + I_c)
      P_c = 0.5 * ( I_a + I_b - I_c)
  - Reduced substitution mass:
      mu = (M * Delta_m) / (M + Delta_m)
  - General 3D (non-planar asymmetric top):
      a^2 = (Delta_P_a / mu) * (1 + Delta_P_b / (I_a - I_b)) * (1 + Delta_P_c / (I_a - I_c))
      b^2 = (Delta_P_b / mu) * (1 + Delta_P_c / (I_b - I_c)) * (1 + Delta_P_a / (I_b - I_a))
      c^2 = (Delta_P_c / mu) * (1 + Delta_P_a / (I_c - I_a)) * (1 + Delta_P_b / (I_c - I_b))
  - Planar asymmetric top (substitution in the ab-plane, c = 0):
      a^2 = (Delta_I_b / mu) * (1 + Delta_I_a / (I_a - I_b))
      b^2 = (Delta_I_a / mu) * (1 + Delta_I_b / (I_b - I_a))
      c^2 = 0 (fixed in symmetry plane; Delta_P_c recorded honestly as inertial defect shift)

Scientific Integrity Invariants:
  - Uses ONLY Python standard library + numpy (zero hardcoded atomic mass dicts).
  - Costain imaginary coordinates (r_s^2 < 0, common for atoms near a principal
    axis or symmetry plane due to zero-point vibrational contamination) are flagged
    honestly with ``imaginary: true`` and ``abs_rs_angstrom: null``. Never
    fabricates 0.0 and never silently takes sqrt(|r_s^2|).
  - Costain empirical error estimate: delta_r_s = 0.0015 / |r_s| Angstrom for real |r_s| > 0.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

# Exact CODATA 2018 conversion constant: h / (8 * pi^2 * u * 1e-14) in MHz * amu * A^2
PLANCK_H_J_S = 6.62607015e-34
ATOMIC_MASS_U_KG = 1.66053906660e-27
ROT_CONST_CONVERSION_MHZ_AMU_A2 = PLANCK_H_J_S / (8.0 * (math.pi ** 2) * ATOMIC_MASS_U_KG * 1.0e-14)
COSTAIN_CONSTANT_A2 = 0.0015


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def moments_from_rotational_constants(a_mhz: float, b_mhz: float, c_mhz: float) -> tuple[float, float, float]:
    """Convert rotational constants (A, B, C in MHz) to principal moments (I_a, I_b, I_c in amu*A^2)."""
    vals = (float(a_mhz), float(b_mhz), float(c_mhz))
    if not all(math.isfinite(v) and v > 0.0 for v in vals):
        raise ValueError(f"Rotational constants A, B, C must be finite and > 0 MHz; got {vals}.")
    return tuple(ROT_CONST_CONVERSION_MHZ_AMU_A2 / v for v in vals)  # type: ignore[return-value]


def planar_moments_from_inertia(i_a: float, i_b: float, i_c: float) -> tuple[float, float, float]:
    """Compute second moments P_a, P_b, P_c (amu*A^2) from principal moments (I_a, I_b, I_c)."""
    p_a = 0.5 * (-i_a + i_b + i_c)
    p_b = 0.5 * (i_a - i_b + i_c)
    p_c = 0.5 * (i_a + i_b - i_c)
    return p_a, p_b, p_c


def _summarize_axis(axis: str, rs_squared: float, *, in_plane_fixed: bool = False) -> dict[str, Any]:
    """Build an honest per-axis Kraitchman coordinate entry (never masking r_s^2 < 0)."""
    val = float(rs_squared)
    if not math.isfinite(val):
        raise ValueError(f"Non-finite r_s^2 value computed for axis '{axis}': {val}")
    if in_plane_fixed:
        return {
            "axis": axis,
            "rs_squared_angstrom2": 0.0,
            "imaginary": False,
            "abs_rs_angstrom": 0.0,
            "costain_uncertainty_angstrom": None,
            "in_plane_fixed": True,
            "note": "Fixed at 0.0 A by planar-mode assumption (substitution in ab-plane).",
        }
    if val < 0.0:
        return {
            "axis": axis,
            "rs_squared_angstrom2": val,
            "imaginary": True,
            "abs_rs_angstrom": None,
            "costain_uncertainty_angstrom": None,
            "in_plane_fixed": False,
            "note": (
                "Costain imaginary coordinate (r_s^2 < 0): atom lies near a principal axis or "
                "symmetry plane where zero-point vibrational effects exceed the mass-shift term. "
                "abs_rs_angstrom is intentionally null (never fabricated as 0.0 or sqrt(|r_s^2|))."
            ),
        }
    abs_rs = math.sqrt(val)
    costain_err = (COSTAIN_CONSTANT_A2 / abs_rs) if abs_rs > 1.0e-12 else None
    return {
        "axis": axis,
        "rs_squared_angstrom2": val,
        "imaginary": False,
        "abs_rs_angstrom": abs_rs,
        "costain_uncertainty_angstrom": costain_err,
        "in_plane_fixed": False,
        "note": None,
    }


def compute_kraitchman_rs(
    *,
    parent_abc_mhz: Sequence[float],
    iso_abc_mhz: Sequence[float],
    delta_mass_amu: float,
    parent_mass_amu: float | None = None,
    reduced_mass_amu: float | None = None,
    mode: str = "nonplanar",
    label: str = "single_substitution",
    course_id: str = "CHEM312",
) -> dict[str, Any]:
    """Compute exact Kraitchman single-substitution |r_s| coordinates for planar or 3D rotors."""
    if len(parent_abc_mhz) != 3 or len(iso_abc_mhz) != 3:
        raise ValueError("Both parent_abc_mhz and iso_abc_mhz must contain exactly 3 values [A, B, C].")

    dm = float(delta_mass_amu)
    if not math.isfinite(dm) or abs(dm) < 1.0e-12:
        raise ValueError(f"delta_mass_amu must be finite and non-zero, got {delta_mass_amu}.")

    if reduced_mass_amu is not None:
        mu = float(reduced_mass_amu)
        if not math.isfinite(mu) or abs(mu) < 1.0e-12:
            raise ValueError(f"reduced_mass_amu must be finite and non-zero, got {reduced_mass_amu}.")
        m_parent_out: float | None = float(parent_mass_amu) if parent_mass_amu is not None else None
    else:
        if parent_mass_amu is None:
            raise ValueError(
                "Parent molecular mass (parent_mass_amu) is required to compute Kraitchman reduced mass "
                "mu = M * Delta_m / (M + Delta_m). Pass --parent-mass-amu (or include molecular_mass_amu "
                "in the parent JSON, or pass --reduced-mass-amu directly)."
            )
        m_parent = float(parent_mass_amu)
        if not math.isfinite(m_parent) or m_parent <= 0.0:
            raise ValueError(f"parent_mass_amu must be finite and > 0, got {parent_mass_amu}.")
        if m_parent + dm <= 0.0:
            raise ValueError(f"Isotopologue mass (M + Delta_m = {m_parent + dm}) must be > 0.")
        mu = (m_parent * dm) / (m_parent + dm)
        m_parent_out = m_parent

    a0, b0, c0 = (float(x) for x in parent_abc_mhz)
    a1, b1, c1 = (float(x) for x in iso_abc_mhz)

    i_a, i_b, i_c = moments_from_rotational_constants(a0, b0, c0)
    i_ap, i_bp, i_cp = moments_from_rotational_constants(a1, b1, c1)

    p_a, p_b, p_c = planar_moments_from_inertia(i_a, i_b, i_c)
    p_ap, p_bp, p_cp = planar_moments_from_inertia(i_ap, i_bp, i_cp)

    dp_a = p_ap - p_a
    dp_b = p_bp - p_b
    dp_c = p_cp - p_c

    di_a = i_ap - i_a
    di_b = i_bp - i_b
    di_c = i_cp - i_c

    inertial_defect_parent = i_c - i_a - i_b
    inertial_defect_iso = i_cp - i_ap - i_bp

    requested_mode = str(mode).strip().lower()
    if requested_mode not in ("auto", "nonplanar", "planar"):
        raise ValueError(f"Unsupported mode {mode!r}; expected 'auto', 'nonplanar', or 'planar'.")

    if requested_mode == "auto":
        is_planar = (
            abs(p_c) < 0.25
            and abs(p_cp) < 0.25
            and abs(dp_c) < 0.05
        )
        effective_mode = "planar" if is_planar else "nonplanar"
    else:
        effective_mode = requested_mode

    denom_ab = i_a - i_b
    if abs(denom_ab) < 1.0e-10:
        raise ValueError(
            f"Parent moments I_a ({i_a:.6f}) and I_b ({i_b:.6f}) are degenerate; "
            "asymmetric-top Kraitchman equations require distinct principal moments."
        )

    if effective_mode == "planar":
        a_sq = (di_b / mu) * (1.0 + di_a / (i_a - i_b))
        b_sq = (di_a / mu) * (1.0 + di_b / (i_b - i_a))
        coords = {
            "a": _summarize_axis("a", a_sq),
            "b": _summarize_axis("b", b_sq),
            "c": _summarize_axis("c", 0.0, in_plane_fixed=True),
        }
    else:
        denom_ac = i_a - i_c
        denom_bc = i_b - i_c
        if abs(denom_ac) < 1.0e-10 or abs(denom_bc) < 1.0e-10:
            raise ValueError(
                f"Parent moments (I_a={i_a:.6f}, I_b={i_b:.6f}, I_c={i_c:.6f}) have a degenerate pair; "
                "non-planar asymmetric-top Kraitchman equations require I_a != I_b != I_c."
            )
        a_sq = (dp_a / mu) * (1.0 + dp_b / (i_a - i_b)) * (1.0 + dp_c / (i_a - i_c))
        b_sq = (dp_b / mu) * (1.0 + dp_c / (i_b - i_c)) * (1.0 + dp_a / (i_b - i_a))
        c_sq = (dp_c / mu) * (1.0 + dp_a / (i_c - i_a)) * (1.0 + dp_b / (i_c - i_b))
        coords = {
            "a": _summarize_axis("a", a_sq),
            "b": _summarize_axis("b", b_sq),
            "c": _summarize_axis("c", c_sq),
        }

    any_imaginary = any(coords[ax]["imaginary"] for ax in ("a", "b", "c"))
    if any_imaginary:
        r_from_com: float | None = None
    else:
        r_vec = np.array(
            [
                float(coords["a"]["abs_rs_angstrom"]),
                float(coords["b"]["abs_rs_angstrom"]),
                float(coords["c"]["abs_rs_angstrom"]),
            ],
            dtype=np.float64,
        )
        r_from_com = float(np.linalg.norm(r_vec))

    return {
        "schema": "cochem.kraitchman-rs/1",
        "course_institution": "Cumberland University",
        "collaborator_institution": "Tennessee Tech University",
        "course_id": course_id,
        "created_at_utc": _utc_now(),
        "label": label,
        "requested_mode": requested_mode,
        "effective_mode": effective_mode,
        "conversion_constant_mhz_amu_a2": ROT_CONST_CONVERSION_MHZ_AMU_A2,
        "mass": {
            "parent_mass_amu": m_parent_out,
            "delta_mass_amu": dm,
            "reduced_mass_mu_amu": mu,
        },
        "parent": {
            "rotational_constants_mhz": {"A": a0, "B": b0, "C": c0},
            "moments_of_inertia_amu_a2": {"I_a": i_a, "I_b": i_b, "I_c": i_c},
            "planar_moments_amu_a2": {"P_a": p_a, "P_b": p_b, "P_c": p_c},
            "inertial_defect_amu_a2": inertial_defect_parent,
        },
        "isotopologue": {
            "rotational_constants_mhz": {"A": a1, "B": b1, "C": c1},
            "moments_of_inertia_amu_a2": {"I_a": i_ap, "I_b": i_bp, "I_c": i_cp},
            "planar_moments_amu_a2": {"P_a": p_ap, "P_b": p_bp, "P_c": p_cp},
            "inertial_defect_amu_a2": inertial_defect_iso,
        },
        "deltas_amu_a2": {
            "delta_I_a": di_a,
            "delta_I_b": di_b,
            "delta_I_c": di_c,
            "delta_P_a": dp_a,
            "delta_P_b": dp_b,
            "delta_P_c": dp_c,
        },
        "coordinates": coords,
        "any_imaginary_coordinate": any_imaginary,
        "distance_from_com_angstrom": r_from_com,
    }


def extract_rotational_record(payload: Mapping[str, Any], source_label: str) -> tuple[tuple[float, float, float], float | None]:
    """Extract (A, B, C) in MHz and optional molecular_mass_amu from a JSON object."""
    mass_val: float | None = None
    for mkey in ("molecular_mass_amu", "parent_mass_amu", "mass_amu", "M_amu", "mass"):
        if mkey in payload and payload[mkey] is not None:
            mass_val = float(payload[mkey])
            break

    # 1. Direct flat keys (a_mhz / A_MHz / A_mhz / A)
    def _find_key(mapping: Mapping[str, Any], candidates: Sequence[str]) -> float | None:
        for key in candidates:
            if key in mapping and mapping[key] is not None:
                return float(mapping[key])
        return None

    for container in (
        payload,
        payload.get("rotational_constants_mhz") if isinstance(payload.get("rotational_constants_mhz"), Mapping) else {},
        payload.get("rotational_constants") if isinstance(payload.get("rotational_constants"), Mapping) else {},
        payload.get("properties") if isinstance(payload.get("properties"), Mapping) else {},
    ):
        a = _find_key(container, ("a_mhz", "A_MHz", "A_mhz", "A_0", "A0", "A_e", "Ae", "A"))
        b = _find_key(container, ("b_mhz", "B_MHz", "B_mhz", "B_0", "B0", "B_e", "Be", "B"))
        c = _find_key(container, ("c_mhz", "C_MHz", "C_mhz", "C_0", "C0", "C_e", "Ce", "C"))
        if a is not None and b is not None and c is not None:
            return (a, b, c), mass_val

    # 2. Sequence form: rotational_constants_mhz: [A, B, C] or properties.rotational_constants: [A, B, C]
    for seq_cand in (
        payload.get("rotational_constants_mhz"),
        payload.get("rotational_constants"),
        (payload.get("properties") or {}).get("rotational_constants")
        if isinstance(payload.get("properties"), Mapping)
        else None,
    ):
        if isinstance(seq_cand, Sequence) and not isinstance(seq_cand, (str, bytes)) and len(seq_cand) == 3:
            return (float(seq_cand[0]), float(seq_cand[1]), float(seq_cand[2])), mass_val

    raise ValueError(
        f"Could not locate rotational constants (A, B, C in MHz) in {source_label}. "
        "Expected keys a_mhz/b_mhz/c_mhz, A_MHz/B_MHz/C_MHz, A/B/C, or rotational_constants_mhz: [A, B, C]."
    )


def render_markdown(result: Mapping[str, Any]) -> str:
    """Render a clean CHEM 312 M4 Markdown summary table of Kraitchman |r_s| coordinates."""
    p_rot = result["parent"]["rotational_constants_mhz"]
    i_rot = result["isotopologue"]["rotational_constants_mhz"]
    mass = result["mass"]
    coords = result["coordinates"]

    heading = (
        f"# CHEM 312 M4 Kraitchman Single-Substitution Coordinates — `{result['label']}`"
        if result.get("course_id", "CHEM312") == "CHEM312"
        else f"# {result['course_id']} Kraitchman Single-Substitution Coordinates — `{result['label']}`"
    )
    lines = [
        heading,
        "",
        f"- **Course Institution:** {result['course_institution']} (`{result['course_id']}`)",
        f"- **Spectroscopy Collaborator:** {result['collaborator_institution']}",
        f"- **Equation Mode:** `{result['effective_mode']}` (requested: `{result['requested_mode']}`)",
        f"- **Timestamp (UTC):** {result['created_at_utc']}",
        f"- **Mass Parameters:** $M = {mass['parent_mass_amu']}$ amu, $\\Delta m = {mass['delta_mass_amu']:.6f}$ amu, $\\mu = {mass['reduced_mass_mu_amu']:.6f}$ amu",
        "",
        "## Input Rotational Constants (MHz)",
        "",
        "| Species | $A$ (MHz) | $B$ (MHz) | $C$ (MHz) | Inertial Defect $\\Delta_0$ ($\\text{u}\\cdot\\text{\\AA}^2$) |",
        "| --- | ---: | ---: | ---: | ---: |",
        f"| Parent | {p_rot['A']:.4f} | {p_rot['B']:.4f} | {p_rot['C']:.4f} | {result['parent']['inertial_defect_amu_a2']:.6f} |",
        f"| Isotopologue | {i_rot['A']:.4f} | {i_rot['B']:.4f} | {i_rot['C']:.4f} | {result['isotopologue']['inertial_defect_amu_a2']:.6f} |",
        "",
        "## Kraitchman $|r_s|$ Principal-Axis Coordinates",
        "",
        "| Axis | $r_s^2$ ($\\text{\\AA}^2$) | $|r_s|$ ($\\text{\\AA}$) | Costain $\\delta r_s$ ($\\text{\\AA}$) | Status |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for ax in ("a", "b", "c"):
        entry = coords[ax]
        rs2_s = f"{entry['rs_squared_angstrom2']:+.6f}"
        if entry["imaginary"]:
            abs_s = "`IMAGINARY (null)`"
            err_s = "—"
            status = "**IMAGINARY ($r_s^2 < 0$)**"
        elif entry["in_plane_fixed"]:
            abs_s = "0.000000"
            err_s = "—"
            status = "IN-PLANE FIXED"
        else:
            abs_s = f"{entry['abs_rs_angstrom']:.6f}"
            err_s = f"{entry['costain_uncertainty_angstrom']:.6f}" if entry["costain_uncertainty_angstrom"] is not None else "—"
            status = "REAL"
        lines.append(f"| `{ax}` | {rs2_s} | {abs_s} | {err_s} | {status} |")

    r_com = result["distance_from_com_angstrom"]
    r_com_s = f"{r_com:.6f} A" if r_com is not None else "PENDING / UNDEFINED (contains imaginary axis)"
    lines.extend(
        [
            "",
            f"- **Distance from Center of Mass $|\\mathbf{{r}}_s|$:** {r_com_s}",
            "",
        ]
    )
    if result["any_imaginary_coordinate"]:
        lines.append(
            "> **Costain Imaginary-Coordinate Notice:** One or more axes returned $r_s^2 < 0$. "
            "In real ground-state ($B_0$) microwave data, atoms lying close to a principal axis or "
            "symmetry plane can exhibit slightly negative $r_s^2$ due to zero-point vibrational effects. "
            "This tool reports `abs_rs_angstrom: null` honestly rather than fabricating `0.0`."
        )
        lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Compute Kraitchman single-substitution |r_s| principal-axis coordinates "
            "from parent and isotopologue rotational constants A, B, C (CHEM 312 M4)."
        )
    )
    p.add_argument("--parent", type=Path, default=None, help="Parent species JSON containing A, B, C (MHz) and optional molecular_mass_amu.")
    p.add_argument("--iso", type=Path, default=None, help="Singly-substituted isotopologue JSON containing A, B, C (MHz) and optional molecular_mass_amu.")
    p.add_argument("--parent-abc", nargs=3, type=float, metavar=("A", "B", "C"), default=None, help="Direct parent rotational constants A B C in MHz.")
    p.add_argument("--iso-abc", nargs=3, type=float, metavar=("A", "B", "C"), default=None, help="Direct isotopologue rotational constants A B C in MHz.")
    p.add_argument("--parent-mass-amu", type=float, default=None, help="Parent molecular mass M in amu.")
    p.add_argument("--delta-mass-amu", type=float, default=None, help="Isotopic mass shift Delta_m = m_iso - m_parent in amu (e.g., 1.006277 for H->D).")
    p.add_argument("--reduced-mass-amu", type=float, default=None, help="Optional explicit Kraitchman reduced mass mu in amu.")
    p.add_argument(
        "--mode",
        choices=("nonplanar", "planar", "auto"),
        default="nonplanar",
        help="Kraitchman equation set: nonplanar (3D, default), planar (2D ab-plane), or auto.",
    )
    p.add_argument("--label", default="single_substitution", help="Substitution site label (e.g., HCOOH_H_acid_D).")
    p.add_argument(
        "--course-id",
        choices=("CHEM312", "CHEM490", "CHEM410", "CHEM411"),
        default="CHEM312",
        help="Course provenance identifier (default: CHEM312; use CHEM490 for Directed Research).",
    )
    p.add_argument("--output-json", type=Path, default=None, help="Optional output JSON path.")
    p.add_argument("--output-md", "--out", dest="output_md", type=Path, default=None, help="Optional output Markdown table path (alias: --out).")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    parent_mass_json: float | None = None
    iso_mass_json: float | None = None
    inputs_sha256: dict[str, str] = {}

    if args.parent is not None:
        p_path = args.parent.resolve()
        if not p_path.is_file():
            raise FileNotFoundError(f"Parent JSON not found: {p_path}")
        parent_abc, parent_mass_json = extract_rotational_record(
            json.loads(p_path.read_text(encoding="utf-8")), str(p_path)
        )
        inputs_sha256["parent_json"] = sha256_file(p_path)
    elif args.parent_abc is not None:
        parent_abc = (float(args.parent_abc[0]), float(args.parent_abc[1]), float(args.parent_abc[2]))
    else:
        raise ValueError("Provide either --parent <json> or --parent-abc A B C.")

    if args.iso is not None:
        i_path = args.iso.resolve()
        if not i_path.is_file():
            raise FileNotFoundError(f"Isotopologue JSON not found: {i_path}")
        iso_abc, iso_mass_json = extract_rotational_record(
            json.loads(i_path.read_text(encoding="utf-8")), str(i_path)
        )
        inputs_sha256["iso_json"] = sha256_file(i_path)
    elif args.iso_abc is not None:
        iso_abc = (float(args.iso_abc[0]), float(args.iso_abc[1]), float(args.iso_abc[2]))
    else:
        raise ValueError("Provide either --iso <json> or --iso-abc A B C.")

    parent_mass = args.parent_mass_amu if args.parent_mass_amu is not None else parent_mass_json
    delta_mass = args.delta_mass_amu
    if delta_mass is None and parent_mass is not None and iso_mass_json is not None:
        delta_mass = float(iso_mass_json) - float(parent_mass)
    if delta_mass is None:
        raise ValueError(
            "Provide --delta-mass-amu (or include molecular_mass_amu in both parent and iso JSON files)."
        )

    result = compute_kraitchman_rs(
        parent_abc_mhz=parent_abc,
        iso_abc_mhz=iso_abc,
        delta_mass_amu=delta_mass,
        parent_mass_amu=parent_mass,
        reduced_mass_amu=args.reduced_mass_amu,
        mode=args.mode,
        label=args.label,
        course_id=args.course_id,
    )
    if inputs_sha256:
        result["inputs_sha256"] = inputs_sha256

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
