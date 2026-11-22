#!/usr/bin/env python3
"""Kramers-Kronig ATR-FTIR Phase Correction & Complex Refractive Index Inversion.

CHEM 312 Module 2 (Tennessee Tech University) — Single-bounce diamond ATR-FTIR
optical distortion correction:
  - Diamond crystal refractive index default: n_1 = 2.417
  - Angle of incidence default: theta = 45.0 deg
  - Unpolarized reflectance: R = 0.5 * (R_s + R_p)
  - Exact 45 deg Fresnel relation: r_p = r_s^2 => R_p = R_s^2, solved
    analytically for R_s = (-1 + sqrt(1 + 8*R)) / 2 (with Bertie-Eysel
    iterative Fresnel refinement for arbitrary theta != 45 deg).
  - Causal Kramers-Kronig phase retrieval phi_s(nu) via O(N log N) even-extended
    FFT Hilbert transform (default) or direct Maclaurin odd/even principal-value
    quadrature, anchored by the high-frequency transparent limit n_inf.
  - Closed-form Fresnel inversion of r_s = sqrt(R_s) * exp(i * phi_s) to
    complex refractive index n_hat(nu) = n(nu) + i * kappa(nu).

Zero hardcoded frequency shifts: blue-shifts of strong carbonyl bands
(typically +8 to +13 cm^-1 for neat esters/carbonates) emerge directly from
Maxwell/Fresnel boundary physics and Kramers-Kronig causality.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from scipy.signal import find_peaks, hilbert


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fresnel_atr_forward(
    n_complex: np.ndarray,
    *,
    n_crystal: float = 2.417,
    angle_deg: float = 45.0,
) -> dict[str, np.ndarray]:
    """Compute exact Fresnel s/p/unpolarized ATR reflectance for n_hat(nu) = n + i*kappa."""
    n_hat = np.asarray(n_complex, dtype=np.complex128)
    theta = math.radians(float(angle_deg))
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    n1 = float(n_crystal)

    eps2 = n_hat * n_hat
    xi = np.sqrt(eps2 - (n1 * sin_t) ** 2)
    # Physical decaying branch into absorbing/evanescent sample: Im(xi) >= 0
    xi = np.where(xi.imag < 0.0, -xi, xi)

    r_s = (n1 * cos_t - xi) / (n1 * cos_t + xi)
    r_p = (eps2 * cos_t - n1 * xi) / (eps2 * cos_t + n1 * xi)

    R_s = np.abs(r_s) ** 2
    R_p = np.abs(r_p) ** 2
    R_unpol = 0.5 * (R_s + R_p)
    R_clipped = np.clip(R_unpol, 1e-12, 1.0)
    atr_abs = -np.log10(R_clipped)

    return {
        "r_s": r_s,
        "r_p": r_p,
        "R_s": R_s,
        "R_p": R_p,
        "R_unpolarized": R_unpol,
        "atr_absorbance": atr_abs,
    }


def damped_lorentzian_refractive_index(
    wavenumber_cm1: np.ndarray,
    *,
    oscillators: Sequence[tuple[float, float, float]],
    n_inf: float = 1.40,
) -> np.ndarray:
    """Build causal complex refractive index n_hat(nu) = sqrt(n_inf^2 + sum S_j / (nu_j^2 - nu^2 - i*gamma_j*nu)).

    Each oscillator tuple is (nu0_cm1, gamma_cm1, strength_cm2).
    """
    nu = np.asarray(wavenumber_cm1, dtype=np.float64)
    eps = np.full(nu.shape, float(n_inf) ** 2, dtype=np.complex128)
    for nu0, gamma, strength in oscillators:
        eps = eps + float(strength) / (float(nu0) ** 2 - nu * nu - 1j * float(gamma) * nu)
    n_hat = np.sqrt(eps)
    return np.where(n_hat.imag < 0.0, np.conj(n_hat), n_hat)


def _anchor_phase_s(n_crystal: float, angle_deg: float, n_inf: float) -> float:
    """High-frequency transparent TIR phase of r_s for n_sample = n_inf, kappa = 0."""
    theta = math.radians(float(angle_deg))
    n1_sin = float(n_crystal) * math.sin(theta)
    n1_cos = float(n_crystal) * math.cos(theta)
    if n_inf >= n1_sin:
        return 0.0
    evanescent = math.sqrt(max(n1_sin * n1_sin - n_inf * n_inf, 0.0))
    return -2.0 * math.atan2(evanescent, n1_cos)


def kk_phase_fft(wavenumber_cm1: np.ndarray, ln_r_s: np.ndarray) -> np.ndarray:
    """Causal KK phase shift -(2*nu/pi) P int_0^inf ln|r_s(u)| / (u^2 - nu^2) du via FFT Hilbert."""
    nu = np.asarray(wavenumber_cm1, dtype=np.float64)
    f_in = np.asarray(ln_r_s, dtype=np.float64)
    if nu.size < 4:
        raise ValueError("At least 4 wavenumber points are required for Kramers-Kronig transform.")

    diffs = np.diff(nu)
    dnu = float(np.median(diffs))
    if dnu <= 0.0:
        raise ValueError("Wavenumber axis must be strictly increasing after sorting.")

    n_grid = int(round(float(nu[-1]) / dnu)) + 1
    full_nu = np.arange(n_grid, dtype=np.float64) * dnu
    f_pos = np.interp(full_nu, nu, f_in, left=0.0, right=0.0)

    # Even extension f(-u) = f(u) with zero padding eliminates circular wrap-around
    pad_len = 2 * n_grid
    f_sym = np.concatenate([f_pos, np.zeros(pad_len, dtype=np.float64), f_pos[n_grid - 1 : 0 : -1]])
    hilb_imag = np.imag(hilbert(f_sym))
    phi_full = hilb_imag[:n_grid]
    return np.interp(nu, full_nu, phi_full)


def kk_phase_maclaurin(wavenumber_cm1: np.ndarray, ln_r_s: np.ndarray) -> np.ndarray:
    """Direct Ohta-Ishida Maclaurin odd/even principal-value quadrature for KK phase shift."""
    nu = np.asarray(wavenumber_cm1, dtype=np.float64)
    f_in = np.asarray(ln_r_s, dtype=np.float64)
    if nu.size < 4:
        raise ValueError("At least 4 wavenumber points are required for Maclaurin KK quadrature.")

    diffs = np.diff(nu)
    if not np.allclose(diffs, diffs[0], rtol=1e-3, atol=1e-6):
        # Resample onto a uniform grid if non-uniform
        dnu = float(np.median(diffs))
        n_pts = int(round((nu[-1] - nu[0]) / dnu)) + 1
        nu_u = nu[0] + np.arange(n_pts, dtype=np.float64) * dnu
        f_u = np.interp(nu_u, nu, f_in)
        phi_u = kk_phase_maclaurin(nu_u, f_u)
        return np.interp(nu, nu_u, phi_u)

    dnu = float(diffs[0])
    n_pts = nu.size
    nu_sq = nu * nu
    even_idx = np.arange(0, n_pts, 2)
    odd_idx = np.arange(1, n_pts, 2)

    phi = np.empty(n_pts, dtype=np.float64)
    # Odd output indices sum over even quadrature nodes, and vice versa
    factor = -4.0 * dnu / math.pi
    for idx_out, idx_quad in ((even_idx, odd_idx), (odd_idx, even_idx)):
        denom = nu_sq[idx_quad][None, :] - nu_sq[idx_out][:, None]
        phi[idx_out] = factor * nu[idx_out] * np.sum(f_in[idx_quad][None, :] / denom, axis=1)
    return phi


def invert_fresnel_rs(
    R_s: np.ndarray,
    phi_s: np.ndarray,
    *,
    n_crystal: float = 2.417,
    angle_deg: float = 45.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Closed-form Fresnel inversion from r_s = sqrt(R_s) * exp(i*phi_s) to (n, kappa)."""
    theta = math.radians(float(angle_deg))
    n1_cos = float(n_crystal) * math.cos(theta)
    n1_sin_sq = (float(n_crystal) * math.sin(theta)) ** 2

    r_s = np.sqrt(np.clip(R_s, 1e-12, 1.0)) * np.exp(1j * phi_s)
    xi = n1_cos * (1.0 - r_s) / (1.0 + r_s)
    eps2 = xi * xi + n1_sin_sq
    n_hat = np.sqrt(eps2)
    n_hat = np.where(n_hat.real < 0.0, -n_hat, n_hat)
    n_real = np.maximum(n_hat.real, 0.0)
    kappa = np.maximum(n_hat.imag, 0.0)
    return n_real, kappa


def kk_atr_correct(
    wavenumber_cm1: np.ndarray,
    signal: np.ndarray,
    *,
    input_mode: str = "auto",
    n_crystal: float = 2.417,
    angle_deg: float = 45.0,
    n_inf: float = 1.40,
    kk_method: str = "fft",
    max_iter: int = 8,
    tol: float = 1e-7,
) -> dict[str, Any]:
    """Perform Kramers-Kronig ATR-FTIR phase correction and optical constant inversion."""
    nu_raw = np.asarray(wavenumber_cm1, dtype=np.float64)
    y_raw = np.asarray(signal, dtype=np.float64)
    if nu_raw.ndim != 1 or y_raw.ndim != 1 or nu_raw.size != y_raw.size:
        raise ValueError("Wavenumber and signal must be 1D arrays of identical length.")
    if nu_raw.size < 8:
        raise ValueError("Spectrum must contain at least 8 wavenumber points.")
    if not (np.all(np.isfinite(nu_raw)) and np.all(np.isfinite(y_raw))):
        raise ValueError("Spectrum contains non-finite values.")
    if n_crystal <= 1.0 or not (0.0 < angle_deg < 90.0) or n_inf <= 0.0:
        raise ValueError("Invalid optical parameters (require n_crystal > 1, 0 < angle_deg < 90, n_inf > 0).")

    # Sort strictly ascending by wavenumber
    order = np.argsort(nu_raw)
    nu = nu_raw[order]
    y = y_raw[order]
    if np.any(np.diff(nu) <= 0.0):
        # Deduplicate repeated wavenumber rows cleanly
        nu, uniq_idx = np.unique(nu, return_index=True)
        y = y[uniq_idx]

    resolved_mode = input_mode.lower().strip()
    if resolved_mode == "auto":
        p90 = float(np.percentile(y, 90))
        if float(np.min(y)) > 0.0 and float(np.max(y)) <= 1.005 and p90 > 0.80:
            resolved_mode = "reflectance"
        else:
            resolved_mode = "absorbance"

    if resolved_mode == "reflectance":
        R_unpol = np.clip(y, 1e-12, 1.0)
        atr_abs = -np.log10(R_unpol)
    elif resolved_mode == "absorbance":
        atr_abs = np.maximum(y, 0.0)
        R_unpol = np.clip(np.power(10.0, -atr_abs), 1e-12, 1.0)
    else:
        raise ValueError(f"Unsupported input_mode {input_mode!r}; expected auto, absorbance, or reflectance.")

    if kk_method not in ("fft", "maclaurin"):
        raise ValueError(f"Unsupported kk_method {kk_method!r}; expected 'fft' or 'maclaurin'.")

    kk_fn = kk_phase_fft if kk_method == "fft" else kk_phase_maclaurin
    phi_inf = _anchor_phase_s(n_crystal, angle_deg, n_inf)

    # Exact initial R_s from 45-degree identity R = 0.5 * (R_s + R_s^2)
    R_s = np.clip(0.5 * (-1.0 + np.sqrt(1.0 + 8.0 * R_unpol)), 1e-12, 1.0)
    is_exact_45 = abs(float(angle_deg) - 45.0) < 1e-6

    iterations = 0
    max_r_residual = 0.0
    n_real = np.full_like(nu, float(n_inf))
    kappa = np.zeros_like(nu)
    phi_s = np.full_like(nu, phi_inf)

    n_steps = 1 if is_exact_45 else max(1, int(max_iter))
    for it in range(1, n_steps + 1):
        iterations = it
        ln_r_s = 0.5 * np.log(np.clip(R_s, 1e-12, 1.0))
        phi_s = phi_inf + kk_fn(nu, ln_r_s)
        n_real, kappa = invert_fresnel_rs(R_s, phi_s, n_crystal=n_crystal, angle_deg=angle_deg)
        fwd = fresnel_atr_forward(n_real + 1j * kappa, n_crystal=n_crystal, angle_deg=angle_deg)
        max_r_residual = float(np.max(np.abs(fwd["R_unpolarized"] - R_unpol)))
        if is_exact_45 or max_r_residual < tol:
            break
        ratio = np.clip(fwd["R_p"] / np.maximum(fwd["R_s"], 1e-12), 1e-6, 10.0)
        R_s = np.clip(2.0 * R_unpol / (1.0 + ratio), 1e-12, 1.0)

    # Identify global maximum and prominent peaks in ATR absorbance and corrected kappa(nu)
    idx_atr_max = int(np.argmax(atr_abs))
    idx_kappa_max = int(np.argmax(kappa))
    nu_max_atr = float(nu[idx_atr_max])
    nu_max_kappa = float(nu[idx_kappa_max])
    delta_nu_cm1 = nu_max_kappa - nu_max_atr

    prom_kappa = max(float(np.max(kappa)) * 0.05, 1e-6)
    prom_atr = max(float(np.max(atr_abs)) * 0.05, 1e-6)
    kappa_peaks_idx, _ = find_peaks(kappa, prominence=prom_kappa)
    atr_peaks_idx, _ = find_peaks(atr_abs, prominence=prom_atr)
    if kappa_peaks_idx.size == 0:
        kappa_peaks_idx = np.array([idx_kappa_max], dtype=int)
    if atr_peaks_idx.size == 0:
        atr_peaks_idx = np.array([idx_atr_max], dtype=int)

    peak_table: list[dict[str, float]] = []
    for kp in kappa_peaks_idx:
        nu_k = float(nu[kp])
        # Match nearest ATR peak within 80 cm^-1
        nearest_idx = int(atr_peaks_idx[int(np.argmin(np.abs(nu[atr_peaks_idx] - nu_k)))])
        nu_a = float(nu[nearest_idx])
        peak_table.append(
            {
                "nu_kappa_cm1": round(nu_k, 4),
                "kappa_peak": round(float(kappa[kp]), 6),
                "n_at_kappa_peak": round(float(n_real[kp]), 6),
                "nu_atr_cm1": round(nu_a, 4),
                "atr_absorbance_peak": round(float(atr_abs[nearest_idx]), 6),
                "delta_nu_cm1": round(nu_k - nu_a, 4),
            }
        )
    peak_table.sort(key=lambda row: row["kappa_peak"], reverse=True)

    return {
        "schema": "cochem.kk-atr-correction/1",
        "collaborator_institution": "Tennessee Tech University",
        "input_mode": resolved_mode,
        "kk_method": kk_method,
        "n_crystal": float(n_crystal),
        "angle_deg": float(angle_deg),
        "n_inf": float(n_inf),
        "phi_inf_rad": float(phi_inf),
        "iterations": iterations,
        "max_reflectance_residual": max_r_residual,
        "n_points": int(nu.size),
        "wavenumber_min_cm1": float(nu[0]),
        "wavenumber_max_cm1": float(nu[-1]),
        "nu_max_atr_cm1": nu_max_atr,
        "nu_max_kappa_cm1": nu_max_kappa,
        "delta_nu_cm1": delta_nu_cm1,
        "peak_table": peak_table,
        "arrays": {
            "wavenumber_cm1": nu,
            "reflectance": R_unpol,
            "atr_absorbance": atr_abs,
            "phi_s_rad": phi_s,
            "n_real": n_real,
            "kappa": kappa,
        },
    }


def load_spectrum_file(path: Path) -> tuple[np.ndarray, np.ndarray, str]:
    """Load 2-column CSV or whitespace-delimited XY ATR-FTIR spectrum."""
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    xs: list[float] = []
    ys: list[float] = []
    header_hint = "auto"

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",")] if "," in line else line.split()
        if len(parts) < 2:
            continue
        try:
            x_val = float(parts[0])
            y_val = float(parts[1])
        except ValueError:
            lowered = line.lower()
            if "reflect" in lowered:
                header_hint = "reflectance"
            elif "absorb" in lowered or "a_atr" in lowered:
                header_hint = "absorbance"
            continue
        xs.append(x_val)
        ys.append(y_val)

    if len(xs) < 8:
        raise ValueError(f"Spectrum file {path} contains fewer than 8 valid (wavenumber, value) rows.")
    return np.asarray(xs, dtype=np.float64), np.asarray(ys, dtype=np.float64), header_hint


def write_corrected_csv(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    arr = result["arrays"]
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        writer = csv.writer(fh)
        writer.writerow(["wavenumber_cm1", "reflectance", "atr_absorbance", "phi_s_rad", "n_real", "kappa"])
        for i in range(arr["wavenumber_cm1"].size):
            writer.writerow(
                [
                    f"{arr['wavenumber_cm1'][i]:.6f}",
                    f"{arr['reflectance'][i]:.8f}",
                    f"{arr['atr_absorbance'][i]:.8f}",
                    f"{arr['phi_s_rad'][i]:.8f}",
                    f"{arr['n_real'][i]:.8f}",
                    f"{arr['kappa'][i]:.8f}",
                ]
            )


ATR_CRYSTAL_INDICES: dict[str, float] = {
    "diamond": 2.417,
    "znse": 2.40,
    "ge": 4.00,
    "germanium": 4.00,
}


def parse_crystal_refractive_index(value: str) -> float:
    """Resolve an ATR crystal name (diamond, znse, ge) or numeric refractive index."""
    cleaned = str(value).strip()
    key = cleaned.lower()
    if key in ATR_CRYSTAL_INDICES:
        return ATR_CRYSTAL_INDICES[key]
    try:
        parsed = float(cleaned)
    except ValueError as exc:
        supported = ", ".join(sorted(ATR_CRYSTAL_INDICES))
        raise argparse.ArgumentTypeError(
            f"Invalid crystal refractive index {value!r}; expected a float or one of: {supported}."
        ) from exc
    if not math.isfinite(parsed) or parsed <= 1.0:
        raise argparse.ArgumentTypeError(
            f"Crystal refractive index must be finite and > 1.0, got {parsed}."
        )
    return parsed


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Kramers-Kronig phase correction for single-bounce diamond ATR-FTIR spectra (CHEM 312 M2)."
    )
    p.add_argument(
        "--input",
        "--csv",
        dest="input",
        required=True,
        type=Path,
        help="Input 2-column CSV or XY ATR-FTIR file (alias: --csv).",
    )
    p.add_argument(
        "--input-mode",
        choices=("auto", "absorbance", "reflectance"),
        default="auto",
        help="Input y-column interpretation (default: auto).",
    )
    p.add_argument(
        "--n-crystal",
        "--crystal",
        dest="n_crystal",
        type=parse_crystal_refractive_index,
        default=2.417,
        help="ATR crystal refractive index or name (diamond=2.417, znse=2.40, ge=4.00; default: 2.417).",
    )
    p.add_argument(
        "--angle-deg",
        "--angle",
        dest="angle_deg",
        type=float,
        default=45.0,
        help="Incidence angle in degrees (default: 45.0; alias: --angle).",
    )
    p.add_argument("--n-inf", type=float, default=1.40, help="High-frequency sample refractive index n_inf (default: 1.40).")
    p.add_argument(
        "--kk-method",
        choices=("fft", "maclaurin"),
        default="fft",
        help="Kramers-Kronig Hilbert transform method (default: fft).",
    )
    p.add_argument(
        "--output-csv",
        "--out",
        dest="output_csv",
        type=Path,
        default=None,
        help="Optional output CSV path for corrected n(nu), kappa(nu) (alias: --out).",
    )
    p.add_argument("--output-json", type=Path, default=None, help="Optional output JSON summary & peak table path.")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    in_path = args.input.resolve()
    if not in_path.is_file():
        raise FileNotFoundError(f"Input spectrum file not found: {in_path}")

    nu, sig, header_hint = load_spectrum_file(in_path)
    effective_mode = header_hint if args.input_mode == "auto" and header_hint != "auto" else args.input_mode
    result = kk_atr_correct(
        nu,
        sig,
        input_mode=effective_mode,
        n_crystal=args.n_crystal,
        angle_deg=args.angle_deg,
        n_inf=args.n_inf,
        kk_method=args.kk_method,
    )

    summary = {k: v for k, v in result.items() if k != "arrays"}
    summary["input_path"] = str(in_path)
    summary["input_sha256"] = sha256_file(in_path)

    if args.output_csv is not None:
        write_corrected_csv(args.output_csv, result)
        summary["output_csv"] = str(args.output_csv.resolve())
        summary["output_csv_sha256"] = sha256_file(args.output_csv)

    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
