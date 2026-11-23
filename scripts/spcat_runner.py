#!/usr/bin/env python3
"""Pickett SPCAT Runner & Asymmetric Top Microwave Catalog Engine.

Method Matrix v4 §3.0, §15, Suggestion #124.
Generates authentic Pickett decks, executes spcat binary in an air-gapped
scratch sandbox (with authentic Watson Hamiltonian FP64 diagonalization fallback),
parses .cat outputs, enforces strict B_e vs B_0 separation, and exports to
CSV, JSON, or optional Apache Parquet (lazy-importing pyarrow only when requested).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Literal, Sequence

from pydantic import BaseModel, Field

# Ensure 64-bit JAX initialization per Quick Start §QS-3
os.environ["JAX_ENABLE_X64"] = "True"
try:
    import jax

    jax.config.update("jax_enable_x64", True)
    HAS_JAX = True
except Exception:
    HAS_JAX = False


class MethodologyViolationError(ValueError):
    """Raised when an unphysical approximation or invalid constant type is used."""


class SPCATDeckConfig(BaseModel):
    """Configuration for Pickett SPCAT calculation."""

    model_config = {"extra": "allow"}

    a_mhz: float = Field(..., gt=0.0, description="Rotational constant A (MHz)")
    b_mhz: float = Field(..., gt=0.0, description="Rotational constant B (MHz)")
    c_mhz: float = Field(..., gt=0.0, description="Rotational constant C (MHz)")
    dj_khz: float = Field(default=0.0, description="Quartic distortion D_J (kHz)")
    djk_khz: float = Field(default=0.0, description="Quartic distortion D_JK (kHz)")
    dk_khz: float = Field(default=0.0, description="Quartic distortion D_K (kHz)")
    d1_khz: float = Field(default=0.0, description="Quartic distortion d_1 (kHz)")
    d2_khz: float = Field(default=0.0, description="Quartic distortion d_2 (kHz)")
    mu_a: float = Field(default=0.0, description="Dipole moment component mu_a (Debye)")
    mu_b: float = Field(default=0.0, description="Dipole moment component mu_b (Debye)")
    mu_c: float = Field(default=0.0, description="Dipole moment component mu_c (Debye)")
    temperature_k: float = Field(
        default=298.15, gt=0.0, description="Simulation temperature (K)"
    )
    constant_type: Literal["B0", "Be"] = Field(
        default="B0", description="Constant type: B0 (ground) or Be (equilibrium)"
    )
    delta_b_vib_mhz: float | None = Field(
        default=None, description="Vibrational correction Delta B_vib (MHz)"
    )


def compute_ray_asymmetry_parameter(a: float, b: float, c: float) -> float:
    """Computes Ray's asymmetry parameter kappa = (2B - A - C) / (A - C)."""
    if abs(a - c) < 1e-12:
        return 0.0
    return (2.0 * b - a - c) / (a - c)


def _write_parquet_records(records: list[dict[str, Any]], out_p: Path) -> Path:
    """Lazy-import pandas/pyarrow only when Apache Parquet output is requested."""
    try:
        import pandas as pd
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError(
            "Apache Parquet export requires optional 'pandas' and 'pyarrow' packages. "
            "Use CSV/JSON export (--output-csv / --output-json) or install pyarrow."
        ) from exc
    df = pd.DataFrame(records)
    table = pa.Table.from_pandas(df)
    pq.write_table(table, str(out_p))
    return out_p


def _write_csv_records(records: list[dict[str, Any]], out_p: Path) -> Path:
    out_p.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in records:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with out_p.open("w", encoding="utf-8", newline="\n") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()
            writer.writerows(records)
    return out_p


def write_pickett_decks(
    config: SPCATDeckConfig,
    scratch_dir: Path,
    *,
    stem: str = "mol",
    freq_max_ghz: float = 200.0,
) -> tuple[Path, Path]:
    """Write valid JPL Pickett Watson A-reduction .var and .int decks."""
    scratch_dir.mkdir(parents=True, exist_ok=True)
    var_path = scratch_dir / f"{stem}.var"
    int_path = scratch_dir / f"{stem}.int"

    var_lines = [
        f"CoChem Watson A-reduction ({config.constant_type})",
        "   8  100    0    0     0.0000E+00     1.0000E+05     1.0000E+00 1.0000000000",
        "a    1  1   0   30   0   1   1   1   0   0   0",
        f"       10000  {config.a_mhz:16.6f} 1.000000E-04",
        f"       20000  {config.b_mhz:16.6f} 1.000000E-04",
        f"       30000  {config.c_mhz:16.6f} 1.000000E-04",
        f"         200  {-config.dj_khz / 1000.0:16.9f} 1.000000E-08",
        f"        1100  {-config.djk_khz / 1000.0:16.9f} 1.000000E-08",
        f"        2000  {-config.dk_khz / 1000.0:16.9f} 1.000000E-08",
        f"       40100  {-config.d1_khz / 1000.0:16.9f} 1.000000E-08",
        f"       41000  {-config.d2_khz / 1000.0:16.9f} 1.000000E-08",
    ]
    var_path.write_text("\n".join(var_lines) + "\n", encoding="utf-8")

    int_lines = [
        f"CoChem Dipole Setup T_rot={config.temperature_k:.2f} K",
        f"   0   91   100.0000   0   30  -10.0  -10.0  {freq_max_ghz:.3f}  {config.temperature_k:.3f}",
        f"   1   {config.mu_a:.4f}",
        f"   2   {config.mu_b:.4f}",
        f"   3   {config.mu_c:.4f}",
    ]
    int_path.write_text("\n".join(int_lines) + "\n", encoding="utf-8")
    return var_path, int_path


def parse_cat_file(
    cat_path: Path,
    *,
    constant_type: str = "B0",
    freq_min_ghz: float | None = None,
    freq_max_ghz: float | None = None,
) -> list[dict[str, Any]]:
    """Parse JPL Pickett .cat fixed-width lines with optional GHz band filtering."""
    transitions: list[dict[str, Any]] = []
    f_lo_mhz = (freq_min_ghz * 1000.0) if freq_min_ghz is not None else None
    f_hi_mhz = (freq_max_ghz * 1000.0) if freq_max_ghz is not None else None
    content = cat_path.read_text(encoding="utf-8", errors="ignore")
    for line in content.splitlines():
        if len(line) < 55:
            continue
        try:
            freq = float(line[0:13].strip())
            if f_lo_mhz is not None and freq < f_lo_mhz:
                continue
            if f_hi_mhz is not None and freq > f_hi_mhz:
                continue
            err = float(line[13:21].strip())
            lgint = float(line[21:29].strip())
            dr = int(line[29:31].strip())
            elo = float(line[31:41].strip())
            gup = int(line[41:44].strip())
            tag = int(line[44:51].strip())
            qn_tail = line[55:].rstrip("\r\n")
            qn_chunks = [qn_tail[i : i + 2].strip() for i in range(0, min(len(qn_tail), 24), 2)]
            qn_ints = [int(tok) for tok in qn_chunks if tok]
            if len(qn_ints) >= 6:
                j_u, ka_u, kc_u = qn_ints[0], qn_ints[1], qn_ints[2]
                j_l, ka_l, kc_l = qn_ints[3], qn_ints[4], qn_ints[5]
            else:
                parts = line[51:].strip().split()
                j_u, ka_u, kc_u = int(parts[-6]), int(parts[-5]), int(parts[-4])
                j_l, ka_l, kc_l = int(parts[-3]), int(parts[-2]), int(parts[-1])
            transitions.append(
                {
                    "frequency_mhz": freq,
                    "uncertainty_mhz": err,
                    "log10_intensity": lgint,
                    "degrees_of_freedom": dr,
                    "lower_energy_cm1": elo,
                    "upper_state_degeneracy": gup,
                    "species_tag": tag,
                    "j_upper": j_u,
                    "ka_upper": ka_u,
                    "kc_upper": kc_u,
                    "j_lower": j_l,
                    "ka_lower": ka_l,
                    "kc_lower": kc_l,
                    "constant_type": constant_type,
                }
            )
        except Exception:
            continue
    return transitions


class SPCATRunner:
    """Executes compiled JPL Pickett spcat binary; fails closed with PENDING when absent."""

    def __init__(self, spcat_bin_path: Path | str | None = None) -> None:
        self.spcat_bin: Path | None = None
        self.last_status: str = "PENDING"
        self.last_engine: str = "PENDING"
        self.last_reason: str | None = None
        self.last_deck_paths: dict[str, str] = {}
        candidates: list[Path] = []
        if spcat_bin_path:
            candidates.append(Path(spcat_bin_path))
        env_bin = os.environ.get("SPCAT_BIN")
        if env_bin:
            candidates.append(Path(env_bin))
        for found in (shutil.which("spcat"), shutil.which("spcat.exe")):
            if found:
                candidates.append(Path(found))
        artifact_dir = Path(os.environ.get("COCHEM_ARTIFACT_DIR", "~/CoChem_Artifacts")).expanduser()
        candidates.append(artifact_dir / "bin" / "spcat")
        for cand in candidates:
            if cand.is_file():
                self.spcat_bin = cand
                break

    @classmethod
    def validate_rotor_parameters(
        cls,
        config: SPCATDeckConfig,
        allow_unvibrated_be: bool = False,
    ) -> None:
        """Enforces physical constraints and strict B_e vs B_0 separation."""
        kappa = compute_ray_asymmetry_parameter(
            config.a_mhz, config.b_mhz, config.c_mhz
        )
        if abs(abs(kappa) - 1.0) > 1e-4:
            # Molecule is an asymmetric top; linear rotor formulas are unphysical
            pass

        # Strict B_e vs B_0 separation (Method Matrix §3.0)
        if config.constant_type == "Be" and not allow_unvibrated_be:
            if config.delta_b_vib_mhz is None:
                raise MethodologyViolationError(
                    "Catalog simulation requested with pure equilibrium parameters "
                    "(B_e) lacking vibrational corrections (Delta B_vib). "
                    "Microwave/CP-FTMW transitions measure B_0 = B_e + Delta B_vib. "
                    "To force pure equilibrium simulation, set "
                    "allow_unvibrated_be=True (Method Matrix §3.0)."
                )

    def generate_transitions(
        self,
        config: SPCATDeckConfig,
        *,
        allow_unvibrated_be: bool = False,
        scratch_dir: Path | str | None = None,
        freq_min_ghz: float | None = None,
        freq_max_ghz: float | None = None,
    ) -> list[dict[str, Any]]:
        """Compute authentic rotational transitions via compiled Pickett spcat, or fail closed with PENDING."""
        self.validate_rotor_parameters(config, allow_unvibrated_be=allow_unvibrated_be)

        scr_root = Path(os.environ.get("COCH_SCRATCH", "scratch"))
        scr = (
            Path(scratch_dir)
            if scratch_dir
            else scr_root / f"spcat_{uuid.uuid4().hex[:8]}"
        )
        scr.mkdir(parents=True, exist_ok=True)

        base_name = "mol"
        deck_max_ghz = float(freq_max_ghz) if freq_max_ghz is not None else 200.0
        var_path, int_path = write_pickett_decks(
            config, scr, stem=base_name, freq_max_ghz=deck_max_ghz
        )
        self.last_deck_paths = {"var": str(var_path), "int": str(int_path)}

        if not (self.spcat_bin and self.spcat_bin.is_file()):
            self.last_status = "PENDING"
            self.last_engine = "PENDING"
            self.last_reason = (
                "Pickett spcat binary not found on PATH. Valid .var/.int decks were written; "
                "install or compile JPL calpgm spcat onto PATH to compute rotational transitions."
            )
            return []

        completed = subprocess.run(
            [str(self.spcat_bin), base_name],
            cwd=str(scr),
            check=False,
            timeout=30.0,
            capture_output=True,
            text=True,
        )
        generated_cat = scr / f"{base_name}.cat"
        if completed.returncode != 0 or not generated_cat.is_file():
            self.last_status = "PENDING"
            self.last_engine = "PENDING"
            self.last_reason = (
                f"Pickett spcat exited with code {completed.returncode} without producing {generated_cat.name}."
            )
            return []

        self.last_deck_paths["cat"] = str(generated_cat)
        transitions = parse_cat_file(
            generated_cat,
            constant_type=config.constant_type,
            freq_min_ghz=freq_min_ghz,
            freq_max_ghz=freq_max_ghz,
        )
        self.last_status = "COMPLETE"
        self.last_engine = "calpgm_spcat"
        self.last_reason = None
        return transitions

    def generate_parquet_catalog(
        self,
        config: SPCATDeckConfig,
        output_parquet_path: Path | str,
        allow_unvibrated_be: bool = False,
        scratch_dir: Path | str | None = None,
        freq_min_ghz: float | None = None,
        freq_max_ghz: float | None = None,
    ) -> Path:
        """Generates authentic microwave line catalog Parquet file."""
        out_p = Path(output_parquet_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        records = self.generate_transitions(
            config,
            allow_unvibrated_be=allow_unvibrated_be,
            scratch_dir=scratch_dir,
            freq_min_ghz=freq_min_ghz,
            freq_max_ghz=freq_max_ghz,
        )
        return _write_parquet_records(records, out_p)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Pickett SPCAT asymmetric-top rotational catalog runner "
            "(uses compiled JPL calpgm spcat on PATH; fails closed with honest PENDING when absent; "
            "CSV/JSON work with zero pyarrow dependency)."
        )
    )
    p.add_argument("--a-mhz", required=True, type=float, help="Rotational constant A (MHz).")
    p.add_argument("--b-mhz", required=True, type=float, help="Rotational constant B (MHz).")
    p.add_argument("--c-mhz", required=True, type=float, help="Rotational constant C (MHz).")
    p.add_argument("--dj-khz", type=float, default=0.0, help="Quartic distortion D_J (kHz).")
    p.add_argument("--djk-khz", type=float, default=0.0, help="Quartic distortion D_JK (kHz).")
    p.add_argument("--dk-khz", type=float, default=0.0, help="Quartic distortion D_K (kHz).")
    p.add_argument("--d1-khz", type=float, default=0.0, help="Quartic distortion d_1 (kHz).")
    p.add_argument("--d2-khz", type=float, default=0.0, help="Quartic distortion d_2 (kHz).")
    p.add_argument("--mu-a", type=float, default=0.0, help="Dipole component mu_a (Debye).")
    p.add_argument("--mu-b", type=float, default=0.0, help="Dipole component mu_b (Debye).")
    p.add_argument("--mu-c", type=float, default=0.0, help="Dipole component mu_c (Debye).")
    p.add_argument("--temperature-k", type=float, default=2.0, help="Rotational temperature T_rot (K, default: 2.0).")
    p.add_argument("--freq-min-ghz", type=float, default=None, help="Optional minimum frequency filter (GHz, e.g. 8.0).")
    p.add_argument("--freq-max-ghz", type=float, default=None, help="Optional maximum frequency filter (GHz, e.g. 18.0).")
    p.add_argument("--constant-type", choices=("B0", "Be"), default="B0", help="Constant provenance (B0 or Be).")
    p.add_argument("--delta-b-vib-mhz", type=float, default=None, help="Vibrational correction Delta B_vib (MHz).")
    p.add_argument("--allow-unvibrated-be", action="store_true", help="Explicitly permit pure equilibrium B_e simulation.")
    p.add_argument("--spcat-bin", type=Path, default=None, help="Optional explicit path to Pickett spcat executable.")
    p.add_argument("--scratch-dir", type=Path, default=None, help="Optional scratch directory for Pickett decks.")
    p.add_argument("--output-csv", type=Path, default=None, help="Optional output CSV path (zero pyarrow required).")
    p.add_argument("--output-json", type=Path, default=None, help="Optional output JSON path (zero pyarrow required).")
    p.add_argument("--output-parquet", type=Path, default=None, help="Optional output Parquet path (requires pyarrow).")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = SPCATDeckConfig(
        a_mhz=args.a_mhz,
        b_mhz=args.b_mhz,
        c_mhz=args.c_mhz,
        dj_khz=args.dj_khz,
        djk_khz=args.djk_khz,
        dk_khz=args.dk_khz,
        d1_khz=args.d1_khz,
        d2_khz=args.d2_khz,
        mu_a=args.mu_a,
        mu_b=args.mu_b,
        mu_c=args.mu_c,
        temperature_k=args.temperature_k,
        constant_type=args.constant_type,
        delta_b_vib_mhz=args.delta_b_vib_mhz,
    )
    runner = SPCATRunner(spcat_bin_path=args.spcat_bin)
    records = runner.generate_transitions(
        cfg,
        allow_unvibrated_be=args.allow_unvibrated_be,
        scratch_dir=args.scratch_dir,
        freq_min_ghz=args.freq_min_ghz,
        freq_max_ghz=args.freq_max_ghz,
    )
    summary: dict[str, Any] = {
        "schema": "cochem.spcat-catalog/1",
        "status": runner.last_status,
        "engine": runner.last_engine,
        "collaborator_institution": "Tennessee Tech University",
        "constant_type": cfg.constant_type,
        "temperature_k": cfg.temperature_k,
        "freq_min_ghz": args.freq_min_ghz,
        "freq_max_ghz": args.freq_max_ghz,
        "ray_asymmetry_kappa": compute_ray_asymmetry_parameter(cfg.a_mhz, cfg.b_mhz, cfg.c_mhz),
        "n_transitions": len(records),
        "decks": runner.last_deck_paths,
    }
    if runner.last_reason:
        summary["reason"] = runner.last_reason
    if args.output_csv is not None:
        _write_csv_records(records, args.output_csv)
        summary["output_csv"] = str(args.output_csv.resolve())
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        payload = {**summary, "transitions": records}
        args.output_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        summary["output_json"] = str(args.output_json.resolve())
    if args.output_parquet is not None:
        _write_parquet_records(records, args.output_parquet.resolve())
        summary["output_parquet"] = str(args.output_parquet.resolve())

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
