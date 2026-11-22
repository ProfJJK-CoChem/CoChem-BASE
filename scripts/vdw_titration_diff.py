#!/usr/bin/env python3
"""Week 10/11 1:1 Non-Covalent Complexation & Counterpoise BSSE Difference Analyzer.

CHEM 312 Module 3 (Tennessee Tech University) — Analyzes 1:1 van der Waals /
hydrogen-bonded complexes (e.g., monomer...H2O, monomer...CO2) by combining:
  1. Computed monomer and 1:1 dimer harmonic/IR JSON artifacts (extracting the
     diagnostic carbonyl C=O stretch shift Delta_nu(C=O) = nu_dimer - nu_monomer).
  2. Boys-Bernardi counterpoise BSSE JSON (compatible with
     `.github/workflows/04_crest_nci_dimer_bsse.yml` `bsse_counterpoise.json`),
     computing exact raw binding energy Delta E_raw, counterpoise-corrected
     binding energy Delta E_CP = E_AB(AB) - E_A(AB) - E_B(AB), and BSSE magnitude.
  3. Optional experimental ATR-FTIR titration CSV spectra (optionally KK-corrected).
     Whenever experimental spectra are not supplied, experimental slots are
     explicitly marked "PENDING" — never fabricated or interpolated.

Exports CSV summary, Markdown report, and SHA-256 provenance JSON.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

HARTREE_TO_KCAL_MOL = 627.5094740631
HARTREE_TO_KJ_MOL = 2625.4996394799


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_counterpoise_bsse(bsse_data: Mapping[str, Any]) -> dict[str, Any]:
    """Compute exact Boys-Bernardi counterpoise BSSE energetics from Hartree totals.

    Accepts field names produced by `.github/workflows/04_crest_nci_dimer_bsse.yml`:
      e_dimer_hartree, e_monomer_a_hartree, e_monomer_b_hartree,
      e_monomer_a_dcbs_hartree, e_monomer_b_dcbs_hartree
    as well as compact aliases (E_AB, E_A, E_B, E_A_AB, E_B_AB).
    """
    def _pick(keys: Sequence[str], label: str) -> float:
        for key in keys:
            if key in bsse_data and bsse_data[key] is not None:
                val = float(bsse_data[key])
                if not math.isfinite(val):
                    raise ValueError(f"Non-finite energy for {label} ({key})")
                return val
        raise KeyError(f"Missing required energy key for {label}: expected one of {keys}")

    e_ab = _pick(("e_dimer_hartree", "E_AB", "e_ab_hartree"), "E_AB(AB)")
    e_a_mon = _pick(("e_monomer_a_hartree", "E_A", "e_a_hartree"), "E_A(A)")
    e_b_mon = _pick(("e_monomer_b_hartree", "E_B", "e_b_hartree"), "E_B(B)")
    e_a_dcbs = _pick(("e_monomer_a_dcbs_hartree", "E_A_AB", "e_a_ab_hartree"), "E_A(AB)")
    e_b_dcbs = _pick(("e_monomer_b_dcbs_hartree", "E_B_AB", "e_b_ab_hartree"), "E_B(AB)")

    delta_e_raw_eh = e_ab - (e_a_mon + e_b_mon)
    delta_e_cp_eh = e_ab - (e_a_dcbs + e_b_dcbs)
    bsse_eh = delta_e_cp_eh - delta_e_raw_eh

    return {
        "status": "COMPUTED",
        "method": bsse_data.get("method"),
        "basis": bsse_data.get("basis"),
        "solvation": bsse_data.get("solvation"),
        "solvent_name": bsse_data.get("solvent_name"),
        "e_dimer_hartree": e_ab,
        "e_monomer_a_hartree": e_a_mon,
        "e_monomer_b_hartree": e_b_mon,
        "e_monomer_a_dcbs_hartree": e_a_dcbs,
        "e_monomer_b_dcbs_hartree": e_b_dcbs,
        "delta_e_raw_hartree": delta_e_raw_eh,
        "delta_e_cp_hartree": delta_e_cp_eh,
        "bsse_hartree": bsse_eh,
        "delta_e_raw_kcal_mol": delta_e_raw_eh * HARTREE_TO_KCAL_MOL,
        "delta_e_cp_kcal_mol": delta_e_cp_eh * HARTREE_TO_KCAL_MOL,
        "bsse_kcal_mol": bsse_eh * HARTREE_TO_KCAL_MOL,
        "delta_e_raw_kj_mol": delta_e_raw_eh * HARTREE_TO_KJ_MOL,
        "delta_e_cp_kj_mol": delta_e_cp_eh * HARTREE_TO_KJ_MOL,
        "bsse_kj_mol": bsse_eh * HARTREE_TO_KJ_MOL,
    }


def _extract_ir_modes(payload: Mapping[str, Any]) -> list[dict[str, float]]:
    """Extract (wavenumber_cm1, intensity_km_mol) pairs from harmonic/IR JSON."""
    modes: list[dict[str, float]] = []
    if isinstance(payload.get("ir_modes"), list):
        for item in payload["ir_modes"]:
            if isinstance(item, Mapping) and "wavenumber_cm1" in item:
                modes.append(
                    {
                        "wavenumber_cm1": float(item["wavenumber_cm1"]),
                        "intensity": float(item.get("intensity_km_mol", item.get("intensity", 1.0))),
                    }
                )
    elif isinstance(payload.get("modes"), list):
        for item in payload["modes"]:
            if isinstance(item, Mapping):
                nu = item.get("wavenumber_cm1", item.get("freq_cm1", item.get("frequency_cm1")))
                if nu is not None:
                    modes.append(
                        {
                            "wavenumber_cm1": float(nu),
                            "intensity": float(item.get("intensity_km_mol", item.get("intensity", 1.0))),
                        }
                    )
    else:
        freqs = payload.get("frequencies_cm1", payload.get("harmonic_cm1"))
        ints = payload.get("ir_intensities_km_mol", payload.get("intensities"))
        if isinstance(freqs, list):
            for idx, val in enumerate(freqs):
                nu = float(val)
                inten = float(ints[idx]) if isinstance(ints, list) and idx < len(ints) else 1.0
                modes.append({"wavenumber_cm1": nu, "intensity": inten})
    return modes


def select_co_band(
    modes: Sequence[Mapping[str, float]],
    *,
    window: tuple[float, float] = (1650.0, 1850.0),
) -> dict[str, float] | None:
    """Identify the strongest IR-active mode inside the diagnostic C=O stretch window."""
    lo, hi = float(min(window)), float(max(window))
    candidates = [m for m in modes if lo <= float(m["wavenumber_cm1"]) <= hi]
    if not candidates:
        return None
    best = max(candidates, key=lambda item: float(item.get("intensity", 0.0)))
    return {
        "wavenumber_cm1": float(best["wavenumber_cm1"]),
        "intensity": float(best.get("intensity", 0.0)),
    }


def _extract_exp_peak_in_window(
    csv_path: Path,
    *,
    window: tuple[float, float],
    apply_kk: bool = False,
    n_crystal: float = 2.417,
    angle_deg: float = 45.0,
    n_inf: float = 1.40,
) -> dict[str, Any]:
    """Load an experimental ATR CSV and find its peak wavenumber inside the C=O window."""
    from scripts.kk_atr_correct import kk_atr_correct, load_spectrum_file

    nu, sig, hint = load_spectrum_file(csv_path)
    lo, hi = float(min(window)), float(max(window))
    if apply_kk:
        res = kk_atr_correct(
            nu,
            sig,
            input_mode=hint,
            n_crystal=n_crystal,
            angle_deg=angle_deg,
            n_inf=n_inf,
        )
        nu_axis = res["arrays"]["wavenumber_cm1"]
        y_axis = res["arrays"]["kappa"]
        quantity = "kk_kappa"
    else:
        order = np.argsort(nu)
        nu_axis = nu[order]
        y_axis = sig[order]
        quantity = "raw_atr_signal"

    mask = (nu_axis >= lo) & (nu_axis <= hi)
    if not np.any(mask):
        raise ValueError(f"Experimental file {csv_path} has no points inside C=O window [{lo}, {hi}] cm^-1.")
    sub_nu = nu_axis[mask]
    sub_y = y_axis[mask]
    idx = int(np.argmax(sub_y))
    return {
        "path": str(csv_path.resolve()),
        "sha256": sha256_file(csv_path),
        "quantity": quantity,
        "nu_co_cm1": float(sub_nu[idx]),
        "peak_value": float(sub_y[idx]),
    }


def analyze_vdw_complexation(
    *,
    complex_label: str = "monomer...H2O",
    monomer_json_path: Path | None = None,
    dimer_json_path: Path | None = None,
    bsse_json_path: Path | None = None,
    exp_monomer_csv: Path | None = None,
    exp_complex_csv: Path | None = None,
    co_window: tuple[float, float] = (1650.0, 1850.0),
    apply_kk: bool = False,
) -> dict[str, Any]:
    """Combine computed IR shifts, counterpoise BSSE energies, and optional experimental ATR data."""
    input_provenance: dict[str, dict[str, str]] = {}

    def _register_input(role: str, path: Path) -> dict[str, Any]:
        resolved = path.resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"Input file for {role} not found: {resolved}")
        input_provenance[role] = {
            "path": str(resolved),
            "sha256": sha256_file(resolved),
        }
        return json.loads(resolved.read_text(encoding="utf-8"))

    # 1. Counterpoise BSSE
    bsse_summary: dict[str, Any]
    if bsse_json_path is not None:
        bsse_raw = _register_input("bsse_json", bsse_json_path)
        bsse_summary = compute_counterpoise_bsse(bsse_raw)
    else:
        bsse_summary = {
            "status": "PENDING",
            "delta_e_raw_kcal_mol": None,
            "delta_e_cp_kcal_mol": None,
            "bsse_kcal_mol": None,
            "delta_e_raw_kj_mol": None,
            "delta_e_cp_kj_mol": None,
            "bsse_kj_mol": None,
        }

    # 2. Computed monomer vs 1:1 dimer C=O shift
    computed_shift: dict[str, Any]
    if monomer_json_path is not None and dimer_json_path is not None:
        mon_data = _register_input("monomer_json", monomer_json_path)
        dim_data = _register_input("dimer_json", dimer_json_path)
        mon_co = select_co_band(_extract_ir_modes(mon_data), window=co_window)
        dim_co = select_co_band(_extract_ir_modes(dim_data), window=co_window)
        if mon_co is None or dim_co is None:
            computed_shift = {
                "status": "PENDING",
                "reason": f"No harmonic mode found in C=O window {list(co_window)} cm^-1",
                "nu_co_monomer_cm1": mon_co["wavenumber_cm1"] if mon_co else None,
                "nu_co_dimer_cm1": dim_co["wavenumber_cm1"] if dim_co else None,
                "delta_nu_co_cm1": None,
            }
        else:
            delta_nu = dim_co["wavenumber_cm1"] - mon_co["wavenumber_cm1"]
            computed_shift = {
                "status": "COMPUTED",
                "co_window_cm1": [float(co_window[0]), float(co_window[1])],
                "nu_co_monomer_cm1": mon_co["wavenumber_cm1"],
                "intensity_monomer": mon_co["intensity"],
                "nu_co_dimer_cm1": dim_co["wavenumber_cm1"],
                "intensity_dimer": dim_co["intensity"],
                "delta_nu_co_cm1": delta_nu,
                "shift_direction": "red_shift" if delta_nu < 0.0 else ("blue_shift" if delta_nu > 0.0 else "unshifted"),
            }
    else:
        computed_shift = {
            "status": "PENDING",
            "co_window_cm1": [float(co_window[0]), float(co_window[1])],
            "nu_co_monomer_cm1": None,
            "nu_co_dimer_cm1": None,
            "delta_nu_co_cm1": None,
        }

    # 3. Experimental ATR titration comparison (strictly PENDING when unmeasured)
    experimental_shift: dict[str, Any]
    if exp_monomer_csv is not None and exp_complex_csv is not None:
        mon_exp = _extract_exp_peak_in_window(exp_monomer_csv, window=co_window, apply_kk=apply_kk)
        cmp_exp = _extract_exp_peak_in_window(exp_complex_csv, window=co_window, apply_kk=apply_kk)
        input_provenance["exp_monomer_csv"] = {"path": mon_exp["path"], "sha256": mon_exp["sha256"]}
        input_provenance["exp_complex_csv"] = {"path": cmp_exp["path"], "sha256": cmp_exp["sha256"]}
        exp_delta = cmp_exp["nu_co_cm1"] - mon_exp["nu_co_cm1"]
        exp_vs_calc_err = (
            exp_delta - computed_shift["delta_nu_co_cm1"]
            if computed_shift.get("delta_nu_co_cm1") is not None
            else None
        )
        experimental_shift = {
            "status": "MEASURED",
            "kk_corrected": bool(apply_kk),
            "nu_co_monomer_cm1": mon_exp["nu_co_cm1"],
            "nu_co_complex_cm1": cmp_exp["nu_co_cm1"],
            "delta_nu_co_cm1": exp_delta,
            "exp_minus_calc_delta_nu_cm1": exp_vs_calc_err,
        }
    else:
        experimental_shift = {
            "status": "PENDING",
            "kk_corrected": bool(apply_kk),
            "nu_co_monomer_cm1": "PENDING",
            "nu_co_complex_cm1": "PENDING",
            "delta_nu_co_cm1": "PENDING",
            "exp_minus_calc_delta_nu_cm1": "PENDING",
        }

    return {
        "schema": "cochem.vdw-titration-diff/1",
        "collaborator_institution": "Tennessee Tech University",
        "course_id": "CHEM312",
        "created_at_utc": _utc_now(),
        "complex_label": complex_label,
        "counterpoise_bsse": bsse_summary,
        "computed_ir_shift": computed_shift,
        "experimental_atr_shift": experimental_shift,
        "inputs_sha256": input_provenance,
    }


def write_summary_csv(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bsse = report["counterpoise_bsse"]
    comp = report["computed_ir_shift"]
    exp = report["experimental_atr_shift"]

    rows = [
        ("complex_label", report["complex_label"], "", "METADATA"),
        ("delta_e_raw_kcal_mol", bsse.get("delta_e_raw_kcal_mol", "PENDING"), "kcal/mol", bsse["status"]),
        ("delta_e_cp_kcal_mol", bsse.get("delta_e_cp_kcal_mol", "PENDING"), "kcal/mol", bsse["status"]),
        ("bsse_kcal_mol", bsse.get("bsse_kcal_mol", "PENDING"), "kcal/mol", bsse["status"]),
        ("computed_nu_co_monomer_cm1", comp.get("nu_co_monomer_cm1", "PENDING"), "cm^-1", comp["status"]),
        ("computed_nu_co_dimer_cm1", comp.get("nu_co_dimer_cm1", "PENDING"), "cm^-1", comp["status"]),
        ("computed_delta_nu_co_cm1", comp.get("delta_nu_co_cm1", "PENDING"), "cm^-1", comp["status"]),
        ("experimental_nu_co_monomer_cm1", exp.get("nu_co_monomer_cm1", "PENDING"), "cm^-1", exp["status"]),
        ("experimental_nu_co_complex_cm1", exp.get("nu_co_complex_cm1", "PENDING"), "cm^-1", exp["status"]),
        ("experimental_delta_nu_co_cm1", exp.get("delta_nu_co_cm1", "PENDING"), "cm^-1", exp["status"]),
    ]
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        writer = csv.writer(fh)
        writer.writerow(["metric", "value", "unit", "status"])
        for metric, val, unit, status in rows:
            val_str = "PENDING" if val is None else (f"{val:.6f}" if isinstance(val, float) else str(val))
            writer.writerow([metric, val_str, unit, status])


def render_markdown(report: Mapping[str, Any]) -> str:
    bsse = report["counterpoise_bsse"]
    comp = report["computed_ir_shift"]
    exp = report["experimental_atr_shift"]

    def _fmt(val: Any, decimals: int = 3) -> str:
        if val is None or val == "PENDING":
            return "PENDING"
        if isinstance(val, (int, float)):
            return f"{val:.{decimals}f}"
        return str(val)

    lines = [
        f"# CHEM 312 M3 Non-Covalent Complexation & BSSE Report — `{report['complex_label']}`",
        "",
        f"- **Institution:** {report['collaborator_institution']}",
        f"- **Timestamp (UTC):** {report['created_at_utc']}",
        "",
        "## Counterpoise BSSE Binding Energy",
        "",
        "| Quantity | Value | Unit | Status |",
        "| --- | ---: | --- | --- |",
        f"| Raw Binding Energy ($\\Delta E_{{\\text{{raw}}}}$) | {_fmt(bsse.get('delta_e_raw_kcal_mol'))} | kcal/mol | {bsse['status']} |",
        f"| Counterpoise Binding Energy ($\\Delta E_{{\\text{{CP}}}}$) | {_fmt(bsse.get('delta_e_cp_kcal_mol'))} | kcal/mol | {bsse['status']} |",
        f"| BSSE Magnitude ($\\Delta E_{{\\text{{CP}}}} - \\Delta E_{{\\text{{raw}}}}$) | {_fmt(bsse.get('bsse_kcal_mol'))} | kcal/mol | {bsse['status']} |",
        "",
        "## Diagnostic Carbonyl Stretch Shift ($\\Delta\\tilde{\\nu}(\\text{C=O})$)",
        "",
        "| Channel | Monomer ($\\text{cm}^{-1}$) | 1:1 Complex ($\\text{cm}^{-1}$) | $\\Delta\\tilde{\\nu}$ ($\\text{cm}^{-1}$) | Status |",
        "| --- | ---: | ---: | ---: | --- |",
        f"| Computed Harmonic/IR | {_fmt(comp.get('nu_co_monomer_cm1'), 2)} | {_fmt(comp.get('nu_co_dimer_cm1'), 2)} | {_fmt(comp.get('delta_nu_co_cm1'), 2)} | {comp['status']} |",
        f"| Experimental ATR-FTIR | {_fmt(exp.get('nu_co_monomer_cm1'), 2)} | {_fmt(exp.get('nu_co_complex_cm1'), 2)} | {_fmt(exp.get('delta_nu_co_cm1'), 2)} | {exp['status']} |",
        "",
        "## Input SHA-256 Provenance",
        "",
        "| Role | SHA-256 |",
        "| --- | --- |",
    ]
    for role, meta in sorted(report["inputs_sha256"].items()):
        lines.append(f"| `{role}` | `{meta['sha256']}` |")
    if not report["inputs_sha256"]:
        lines.append("| *(none supplied)* | `PENDING` |")
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Analyze 1:1 monomer...H2O/CO2 vibrational shifts and counterpoise BSSE (CHEM 312 M3)."
    )
    p.add_argument("--complex-label", default="monomer...H2O", help="Descriptive complex name.")
    p.add_argument("--monomer-json", type=Path, default=None, help="Computed monomer harmonic/IR JSON.")
    p.add_argument("--dimer-json", type=Path, default=None, help="Computed 1:1 dimer harmonic/IR JSON.")
    p.add_argument("--bsse-json", type=Path, default=None, help="Counterpoise BSSE JSON from 04_crest_nci_dimer_bsse.yml.")
    p.add_argument("--exp-monomer-csv", type=Path, default=None, help="Optional experimental monomer ATR CSV.")
    p.add_argument("--exp-complex-csv", type=Path, default=None, help="Optional experimental 1:1 complex ATR CSV.")
    p.add_argument("--co-window", default="1650,1850", help="Carbonyl wavenumber window min,max in cm^-1 (default: 1650,1850).")
    p.add_argument("--kk-correct", action="store_true", help="Apply Kramers-Kronig correction to experimental ATR CSVs.")
    p.add_argument("--output-csv", type=Path, default=None, help="Output summary CSV path.")
    p.add_argument("--output-md", type=Path, default=None, help="Output Markdown report path.")
    p.add_argument("--output-json", type=Path, default=None, help="Output SHA-256 provenance JSON path.")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    lo_s, hi_s = [part.strip() for part in args.co_window.split(",")]
    window = (float(lo_s), float(hi_s))

    report = analyze_vdw_complexation(
        complex_label=args.complex_label,
        monomer_json_path=args.monomer_json,
        dimer_json_path=args.dimer_json,
        bsse_json_path=args.bsse_json,
        exp_monomer_csv=args.exp_monomer_csv,
        exp_complex_csv=args.exp_complex_csv,
        co_window=window,
        apply_kk=args.kk_correct,
    )

    outputs_sha256: dict[str, str] = {}
    if args.output_csv is not None:
        write_summary_csv(args.output_csv, report)
        outputs_sha256["output_csv"] = sha256_file(args.output_csv)

    if args.output_md is not None:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_markdown(report), encoding="utf-8")
        outputs_sha256["output_md"] = sha256_file(args.output_md)

    report["outputs_sha256"] = outputs_sha256
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
