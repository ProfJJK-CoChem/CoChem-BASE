"""Pickett SPCAT runner and asymmetric-top microwave Parquet catalog writer.

Method Matrix v4 §3.0, §15, Suggestion #124.
Writes a Pickett deck, runs the SPCAT program recorded in CoChem-BASE's Pickett
receipt (schema ``cochem.pickett-installation/1``, located through
``COCHEM_PICKETT_RECEIPT`` or ``COCHEM_ARTIFACT_DIR``) in a scratch directory,
parses the ``.cat`` output, enforces the B_e versus B_0 separation and exports
the catalog to Parquet with a provenance sidecar.

A missing, unverified or failing SPCAT raises ``PickettProgramUnavailableError``.
No in-process model stands in for the program, so every catalog this module
writes is SPCAT output (CoChem-SpycFit D-SPYC-16 D; D-SPYC-26 F1, PI 2026-10-18).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel, Field

RECEIPT_SCHEMA = "cochem.pickett-installation/1"
RECEIPT_ENVIRONMENT = "COCHEM_PICKETT_RECEIPT"
_HEX64 = re.compile(r"[0-9a-f]{64}")
_CATALOG_SCHEMA = pa.schema([
    ("frequency_mhz", pa.float64()), ("uncertainty_mhz", pa.float64()), ("log10_intensity", pa.float64()),
    ("degrees_of_freedom", pa.int64()), ("lower_energy_cm1", pa.float64()), ("upper_state_degeneracy", pa.int64()),
    ("species_tag", pa.int64()), ("j_upper", pa.int64()), ("ka_upper", pa.int64()), ("kc_upper", pa.int64()),
    ("j_lower", pa.int64()), ("ka_lower", pa.int64()), ("kc_lower", pa.int64()), ("constant_type", pa.string()),
])


class MethodologyViolationError(ValueError):
    """Raised when an unphysical approximation or invalid constant type is used."""


class PickettProgramUnavailableError(RuntimeError):
    """SPCAT is missing, does not match its receipt, or failed; nothing substitutes for it."""


def _sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def locate_pickett_receipt(explicit: Path | str | None = None) -> Path:
    """The receipt path from an argument, COCHEM_PICKETT_RECEIPT or the artifact directory."""
    if explicit:
        return Path(explicit).expanduser()
    environment = os.environ.get(RECEIPT_ENVIRONMENT)
    if environment:
        return Path(environment).expanduser()
    artifacts = os.environ.get("COCHEM_ARTIFACT_DIR")
    if artifacts:
        return Path(artifacts).expanduser() / "pickett" / "install" / "pickett-installation.json"
    raise PickettProgramUnavailableError(
        f"No Pickett receipt: set {RECEIPT_ENVIRONMENT} or COCHEM_ARTIFACT_DIR, or run the BASE Pickett build.")


def verified_program(name: str, receipt_path: Path | str | None = None) -> Path:
    """The path of one Pickett program whose bytes match the receipt; raises otherwise."""
    path = locate_pickett_receipt(receipt_path)
    if path.is_symlink() or not path.is_file():
        raise PickettProgramUnavailableError(f"Pickett receipt {path} is missing; run the BASE Pickett build.")
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise PickettProgramUnavailableError(f"Pickett receipt {path} is unreadable: {error}") from error
    if not isinstance(receipt, dict) or receipt.get("schema_version") != RECEIPT_SCHEMA:
        raise PickettProgramUnavailableError(f"Pickett receipt {path} does not carry schema {RECEIPT_SCHEMA}.")
    programs = receipt.get("programs")
    entry = programs.get(name) if isinstance(programs, dict) else None
    if (not isinstance(entry, dict) or not isinstance(entry.get("path"), str)
            or not isinstance(entry.get("sha256"), str) or not _HEX64.fullmatch(entry["sha256"])):
        raise PickettProgramUnavailableError(f"Pickett receipt {path} records no verifiable {name} program.")
    program = Path(entry["path"])
    if program.is_symlink() or not program.is_file() or not os.access(program, os.X_OK):
        raise PickettProgramUnavailableError(f"Pickett program {name} at {program} is missing or not executable.")
    if _sha256_file(program) != entry["sha256"]:
        raise PickettProgramUnavailableError(f"Pickett program {name} at {program} no longer matches its receipt.")
    return program


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


class SPCATRunner:
    """Runs the receipt-verified Pickett SPCAT program; never an in-process substitute."""

    def __init__(self, spcat_bin_path: Path | str | None = None, receipt_path: Path | str | None = None) -> None:
        self.spcat_bin_path = Path(spcat_bin_path) if spcat_bin_path else None
        self.receipt_path = Path(receipt_path) if receipt_path else None
        self.spcat_bin: Path | None = None
        self.last_run: dict[str, Any] | None = None

    def resolve_spcat(self) -> Path:
        """Resolve SPCAT when a catalog is requested; an absent program raises then."""
        if self.spcat_bin_path is not None:
            program = self.spcat_bin_path
            if program.is_symlink() or not program.is_file() or not os.access(program, os.X_OK):
                raise PickettProgramUnavailableError(f"SPCAT at {program} is missing or not executable.")
        else:
            program = verified_program("spcat", self.receipt_path)
        self.spcat_bin = program
        return program

    @classmethod
    def validate_rotor_parameters(
        cls,
        config: SPCATDeckConfig,
        allow_unvibrated_be: bool = False,
    ) -> None:
        """Enforces physical constraints and strict B_e vs B_0 separation."""
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

    @staticmethod
    def parse_catalog(text: str, constant_type: str) -> list[dict[str, Any]]:
        """Parse SPCAT's fixed-width .cat lines; a malformed line is an error, never skipped."""
        transitions: list[dict[str, Any]] = []
        for number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                parts = line[55:].split()
                record = {
                    "frequency_mhz": float(line[0:13]),
                    "uncertainty_mhz": float(line[13:21]),
                    "log10_intensity": float(line[21:29]),
                    "degrees_of_freedom": int(line[29:31]),
                    "lower_energy_cm1": float(line[31:41]),
                    "upper_state_degeneracy": int(line[41:44]),
                    "species_tag": int(line[44:51]),
                    "j_upper": int(parts[-6]), "ka_upper": int(parts[-5]), "kc_upper": int(parts[-4]),
                    "j_lower": int(parts[-3]), "ka_lower": int(parts[-2]), "kc_lower": int(parts[-1]),
                    "constant_type": constant_type,
                }
            except (ValueError, IndexError) as error:
                raise ValueError(f"SPCAT catalog line {number} is not a parseable .cat record: {line!r}") from error
            transitions.append(record)
        return transitions

    def generate_parquet_catalog(
        self,
        config: SPCATDeckConfig,
        output_parquet_path: Path | str,
        allow_unvibrated_be: bool = False,
        scratch_dir: Path | str | None = None,
    ) -> Path:
        """Run SPCAT on the deck and write its catalog to Parquet with a provenance sidecar."""
        self.validate_rotor_parameters(config, allow_unvibrated_be=allow_unvibrated_be)
        program = self.resolve_spcat()

        out_p = Path(output_parquet_path).resolve()
        scr_root = Path(os.environ.get("COCH_SCRATCH", "scratch"))
        scr = (
            Path(scratch_dir)
            if scratch_dir
            else scr_root / f"spcat_{uuid.uuid4().hex[:8]}"
        )
        scr.mkdir(parents=True, exist_ok=True)

        base_name = "mol"
        var_path = scr / f"{base_name}.var"
        int_path = scr / f"{base_name}.int"

        var_lines = [
            "CoChem-TORQ Watson A-reduced parameters",
            "   5   100   0   0.0000E+000   1.0000E+000   1.0000E+000",
            f"       10000  {config.a_mhz:16.6f} 1.000000E-04",
            f"       20000  {config.b_mhz:16.6f} 1.000000E-04",
            f"       30000  {config.c_mhz:16.6f} 1.000000E-04",
            f"         200  {-config.dj_khz:16.6f} 1.000000E-06",
            f"        1100  {-config.djk_khz:16.6f} 1.000000E-06",
            f"        2000  {-config.dk_khz:16.6f} 1.000000E-06",
            f"       40100  {-config.d1_khz:16.6f} 1.000000E-06",
            f"       41000  {-config.d2_khz:16.6f} 1.000000E-06",
        ]
        var_path.write_text("\n".join(var_lines) + "\n", encoding="utf-8")

        int_lines = [
            "CoChem-TORQ Dipole Setup",
            "   0    1    0.0    0.0000    200000.0   -10.0   1.0000",
            f"   {config.temperature_k:.2f}    1000.000",
            f"   1   {config.mu_a:.4f}",
            f"   2   {config.mu_b:.4f}",
            f"   3   {config.mu_c:.4f}",
        ]
        int_path.write_text("\n".join(int_lines) + "\n", encoding="utf-8")

        try:
            completed = subprocess.run(
                [str(program), base_name],
                cwd=str(scr),
                stdin=subprocess.DEVNULL,
                check=False,
                timeout=30.0,
                capture_output=True,
            )
        except subprocess.TimeoutExpired as error:
            raise PickettProgramUnavailableError(f"SPCAT at {program} exceeded its 30 s limit.") from error
        except OSError as error:
            raise PickettProgramUnavailableError(f"SPCAT at {program} could not be started: {error}") from error
        if completed.returncode != 0:
            raise PickettProgramUnavailableError(
                f"SPCAT at {program} exited with status {completed.returncode}: "
                f"{completed.stderr.decode('utf-8', errors='replace')[-2000:]}")
        generated_cat = scr / f"{base_name}.cat"
        if not generated_cat.is_file():
            raise PickettProgramUnavailableError(f"SPCAT at {program} exited 0 but wrote no {generated_cat.name}.")

        transitions = self.parse_catalog(generated_cat.read_text(encoding="utf-8", errors="replace"), config.constant_type)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        if transitions:
            table = pa.Table.from_pandas(pd.DataFrame(transitions), schema=_CATALOG_SCHEMA, preserve_index=False)
        else:
            table = _CATALOG_SCHEMA.empty_table()
        pq.write_table(table, str(out_p))
        self.last_run = {
            "schema_version": "cochem.spcat-run/1",
            "producer": "spcat",
            "program": str(program),
            "program_sha256": _sha256_file(program),
            "receipt": str(self.receipt_path) if self.receipt_path else os.environ.get(RECEIPT_ENVIRONMENT),
            "deck_sha256": {"var": _sha256_file(var_path), "int": _sha256_file(int_path)},
            "exit_code": completed.returncode,
            "catalog_sha256": _sha256_file(generated_cat),
            "transitions": len(transitions),
            "constant_type": config.constant_type,
            "parquet": str(out_p),
        }
        out_p.with_name(out_p.name + ".provenance.json").write_text(
            json.dumps(self.last_run, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return out_p
