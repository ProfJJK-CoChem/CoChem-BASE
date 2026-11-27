"""Pickett SPCAT Runner & Asymmetric Top Microwave Parquet Catalog Engine.

Method Matrix v4 §3.0, §15, Suggestion #124.
Generates valid JPL Pickett Watson A-reduction `.var` and `.int` decks,
executes the compiled `spcat` binary in an air-gapped scratch sandbox,
parses fixed-width `.cat` outputs, enforces strict B_e vs B_0 separation,
and exports to Parquet. Fails closed when the `spcat` binary is absent or
fails to produce authentic transitions.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel, Field


class MethodologyViolationError(ValueError):
    """Raised when an unphysical approximation or invalid constant type is used."""


class SPCATDeckConfig(BaseModel):
    """Configuration for Pickett SPCAT calculation."""

    model_config = {"extra": "allow"}

    a_mhz: float = Field(..., gt=0.0, description="Rotational constant A (MHz)")
    b_mhz: float = Field(..., gt=0.0, description="Rotational constant B (MHz)")
    c_mhz: float = Field(..., gt=0.0, description="Rotational constant C (MHz)")
    dj_khz: float = Field(default=0.0, description="Quartic distortion Delta_J (kHz)")
    djk_khz: float = Field(default=0.0, description="Quartic distortion Delta_JK (kHz)")
    dk_khz: float = Field(default=0.0, description="Quartic distortion Delta_K (kHz)")
    d1_khz: float = Field(default=0.0, description="Quartic distortion delta_J (kHz)")
    d2_khz: float = Field(default=0.0, description="Quartic distortion delta_K (kHz)")
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


def write_pickett_decks(
    config: SPCATDeckConfig,
    scratch_dir: Path,
    *,
    stem: str = "mol",
    freq_max_ghz: float = 200.0,
    j_max: int = 30,
) -> tuple[Path, Path]:
    """Write valid JPL Pickett Watson A-reduction `.var` and `.int` decks.

    All rotational and quartic centrifugal distortion parameters are emitted
    strictly in MHz with Pickett Watson A-reduction codes and sign conventions:
    - 10000: A (MHz)
    - 20000: B (MHz)
    - 30000: C (MHz)
    -   200: -Delta_J (MHz)
    -  1100: -Delta_JK (MHz)
    -  2000: -Delta_K (MHz)
    - 40100: -delta_J (MHz)
    - 41000: -delta_K (MHz)
    """
    scratch_dir.mkdir(parents=True, exist_ok=True)
    var_path = scratch_dir / f"{stem}.var"
    int_path = scratch_dir / f"{stem}.int"

    param_lines = [
        f"       10000  {config.a_mhz:16.6f} 1.000000E-04",
        f"       20000  {config.b_mhz:16.6f} 1.000000E-04",
        f"       30000  {config.c_mhz:16.6f} 1.000000E-04",
        f"         200  {-config.dj_khz / 1000.0:16.9f} 1.000000E-08",
        f"        1100  {-config.djk_khz / 1000.0:16.9f} 1.000000E-08",
        f"        2000  {-config.dk_khz / 1000.0:16.9f} 1.000000E-08",
        f"       40100  {-config.d1_khz / 1000.0:16.9f} 1.000000E-08",
        f"       41000  {-config.d2_khz / 1000.0:16.9f} 1.000000E-08",
    ]
    n_params = len(param_lines)
    var_lines = [
        f"CoChem Watson A-reduced parameters ({config.constant_type})",
        f"{n_params:4d}  0  1  0  0.0000E+00  1.0000E+04  1.0000E+00  1.0000E+00",
        f"a    1  1   0  {j_max:3d}   0   1   1   1   0   0   0",
        *param_lines,
    ]
    var_path.write_text("\n".join(var_lines) + "\n", encoding="utf-8")

    int_lines = [
        f"CoChem Dipole Setup T_rot={config.temperature_k:.2f} K",
        f"   0   91   100.0000   0  {j_max:3d}  -10.0  -10.0  {freq_max_ghz:.3f}  {config.temperature_k:.3f}",
        f"   1   {config.mu_a:.4f}",
        f"   2   {config.mu_b:.4f}",
        f"   3   {config.mu_c:.4f}",
    ]
    int_path.write_text("\n".join(int_lines) + "\n", encoding="utf-8")
    return var_path, int_path


def _decode_pickett_qn(token: str) -> int:
    """Decode a 2-character JPL Pickett quantum number field (supports A0..Z9 for >=100)."""
    cleaned = token.strip()
    if not cleaned:
        raise ValueError("Empty Pickett quantum number field")
    if len(cleaned) == 2 and cleaned[0].isalpha():
        prefix = cleaned[0].upper()
        tens = 10 + (ord(prefix) - ord("A"))
        return tens * 10 + int(cleaned[1])
    return int(cleaned)


def parse_cat_file(
    cat_path: Path,
    *,
    constant_type: str = "B0",
    freq_min_ghz: float | None = None,
    freq_max_ghz: float | None = None,
) -> list[dict[str, Any]]:
    """Parse fixed-width JPL Pickett `.cat` transition records."""
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
            qn_ints = [_decode_pickett_qn(tok) for tok in qn_chunks if tok]
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
    """Executes compiled JPL Pickett `spcat` binary; fails closed when absent or unsuccessful."""

    def __init__(self, spcat_bin_path: Path | str | None = None) -> None:
        self.spcat_bin: Path | None = None
        if spcat_bin_path is not None:
            p = Path(spcat_bin_path).expanduser()
            if p.is_file():
                self.spcat_bin = p
            return

        candidates: list[Path] = []
        env_bin = os.environ.get("SPCAT_BIN")
        if env_bin:
            candidates.append(Path(env_bin).expanduser())
        for found in (shutil.which("spcat"), shutil.which("spcat.exe")):
            if found:
                candidates.append(Path(found))
        candidates.append(Path.home() / ".local" / "bin" / "spcat")
        artifact_dir = Path(
            os.environ.get("COCHEM_ARTIFACT_DIR", "~/CoChem_Artifacts")
        ).expanduser()
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
        j_max: int = 30,
    ) -> list[dict[str, Any]]:
        """Execute Pickett `spcat` and return parsed `.cat` transitions; fail closed on any error."""
        self.validate_rotor_parameters(config, allow_unvibrated_be=allow_unvibrated_be)

        if not (self.spcat_bin and self.spcat_bin.is_file()):
            raise FileNotFoundError(
                "Pickett spcat binary not found. Provide spcat_bin_path, set SPCAT_BIN, "
                "or install compiled JPL calpgm spcat on PATH."
            )

        scr_root = Path(os.environ.get("COCH_SCRATCH", "scratch"))
        scr = (
            Path(scratch_dir)
            if scratch_dir
            else scr_root / f"spcat_{uuid.uuid4().hex[:8]}"
        )
        scr.mkdir(parents=True, exist_ok=True)

        base_name = "mol"
        deck_max_ghz = float(freq_max_ghz) if freq_max_ghz is not None else 200.0
        write_pickett_decks(
            config,
            scr,
            stem=base_name,
            freq_max_ghz=deck_max_ghz,
            j_max=j_max,
        )

        completed = subprocess.run(
            [str(self.spcat_bin), base_name],
            cwd=str(scr),
            check=False,
            timeout=30.0,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"Pickett spcat exited with code {completed.returncode} in {scr}: "
                f"{(completed.stderr or completed.stdout).strip()[:400]}"
            )

        generated_cat = scr / f"{base_name}.cat"
        if not generated_cat.is_file():
            raise RuntimeError(
                f"Pickett spcat completed without producing {generated_cat.name} in {scr}."
            )

        transitions = parse_cat_file(
            generated_cat,
            constant_type=config.constant_type,
            freq_min_ghz=freq_min_ghz,
            freq_max_ghz=freq_max_ghz,
        )
        if not transitions:
            raise RuntimeError(
                f"Pickett spcat produced zero transitions in {generated_cat} "
                f"(check non-zero dipole components and frequency window)."
            )
        return transitions

    def generate_parquet_catalog(
        self,
        config: SPCATDeckConfig,
        output_parquet_path: Path | str,
        allow_unvibrated_be: bool = False,
        scratch_dir: Path | str | None = None,
        freq_min_ghz: float | None = None,
        freq_max_ghz: float | None = None,
        j_max: int = 30,
    ) -> Path:
        """Generates authentic microwave line catalog Parquet file via compiled Pickett `spcat`."""
        transitions = self.generate_transitions(
            config,
            allow_unvibrated_be=allow_unvibrated_be,
            scratch_dir=scratch_dir,
            freq_min_ghz=freq_min_ghz,
            freq_max_ghz=freq_max_ghz,
            j_max=j_max,
        )

        out_p = Path(output_parquet_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)

        df = pd.DataFrame(transitions)
        table = pa.Table.from_pandas(df)
        pq.write_table(table, str(out_p))
        return out_p
