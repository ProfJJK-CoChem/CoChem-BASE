"""Execute Recipe R2 with supplied CCSD(T)/CBS references and five CP legs.

Reference geometries are external scientific inputs. Their source claims are
retained alongside verified file digests; this module never invents benchmarks
or infers CCSD(T)/CBS quality from an arbitrary submitted XYZ geometry.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from contextlib import nullcontext
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable, Literal, Sequence
import uuid
import warnings

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator
from scipy.constants import physical_constants

from cochem_base.analysis.electronic_sanitizer import SpinContaminationStreamValidator
from cochem_base.calc.cochem_calc_output_parser import QuantumParser
from cochem_base.core_engine.execution_authority import authorize_engine_execution
from cochem_base.core_engine.cochem_core_subprocess_broker import safe_subprocess_run, sanitize_mpi_environment
from cochem_base.core_engine.engine_environment import engine_runtime_environment
from cochem_base.geometry.constraints import (
    build_wilson_b_matrix,
    generate_frozen_monomer_constraints,
    format_orca_frozen_monomer_constraints_block,
    validate_trajectory_monomer_drift,
)
from cochem_base.physics.isotopes import get_element_mass_and_abundance


class R2ReferenceError(ValueError):
    """A production reference is missing, inconsistent, or has changed."""


class ResidualGradientWarning(UserWarning):
    """The frozen CCSD(T)/CBS geometry has significant strain on the R2 surface."""


class ReferenceArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: Path
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    def verify(self, base: Path) -> Path:
        path = self.path if self.path.is_absolute() else base / self.path
        path = path.resolve(strict=True)
        if not path.is_file() or path.stat().st_size == 0:
            raise R2ReferenceError(f"Reference artifact is absent or empty: {path}")
        with path.open("rb") as handle:
            actual = hashlib.file_digest(handle, "sha256").hexdigest()
        if actual != self.sha256:
            raise R2ReferenceError(f"Reference artifact digest mismatch: {path}")
        return path


class MonomerReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    atom_indices: list[StrictInt] = Field(min_length=1)
    charge: StrictInt = 0
    multiplicity: StrictInt = Field(default=1, ge=1)
    method: Literal["CCSD(T)/CBS"]
    basis_cardinal_pair: tuple[StrictInt, StrictInt]
    basis_family: Literal["cc-pVXZ", "cc-pCVXZ", "aug-cc-pVXZ", "aug-cc-pCVXZ"]
    source_uri: str = Field(min_length=1)
    geometry: ReferenceArtifact
    # Retain the two actual benchmark outputs supporting the CBS provenance.
    lower_cardinal_output: ReferenceArtifact
    upper_cardinal_output: ReferenceArtifact

    @field_validator("basis_cardinal_pair")
    @classmethod
    def cbs_pair(cls, value: tuple[int, int]) -> tuple[int, int]:
        if value not in {(3, 4), (4, 5)}:
            raise ValueError("CCSD(T)/CBS references require cardinal pairs (3,4) or (4,5)")
        return value

    @field_validator("source_uri")
    @classmethod
    def source_identity(cls, value: str) -> str:
        if not re.match(r"^(?:https?://|doi:|urn:)", value):
            raise ValueError("A traceable URL, DOI, or URN is required for each benchmark")
        return value

    @field_validator("atom_indices")
    @classmethod
    def unique_indices(cls, value: list[int]) -> list[int]:
        if min(value) < 0 or len(value) != len(set(value)):
            raise ValueError("Monomer atom indices must be distinct and nonnegative")
        return value


class R2ReferenceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["cochem.r2-reference/1"]
    monomers: tuple[MonomerReference, MonomerReference]

    @model_validator(mode="after")
    def disjoint_monomers(self) -> "R2ReferenceManifest":
        if set(self.monomers[0].atom_indices) & set(self.monomers[1].atom_indices):
            raise ValueError("Reference monomers must be disjoint")
        return self


def _geometry(text: str) -> tuple[list[str], np.ndarray]:
    # The native service owns the single strict XYZ grammar.
    from cochem_base.calc.calculation_service import parse_run_geometry

    symbols, coordinates = parse_run_geometry(text)
    return symbols, np.asarray(coordinates, dtype=float)


def _state(symbols: Sequence[str], charge: int, multiplicity: int) -> None:
    electrons = sum(get_element_mass_and_abundance(s)[2] for s in symbols) - charge
    if electrons < 0 or multiplicity < 1 or multiplicity > electrons + 1 or (electrons + multiplicity) % 2 != 1:
        raise R2ReferenceError("Reference charge/multiplicity is incompatible with its nuclei")


def parse_reference_geometry_state(text: str) -> dict[str, Any]:
    """Read the final ORCA printed geometry and electronic-state declarations.

    This parser alone does not establish a completed scientific calculation.
    The enclosing benchmark validator supplies method and completion checks.
    """
    states = {}
    for label, key in (("Total Charge", "charge"), ("Multiplicity", "multiplicity")):
        values = re.findall(r"^\s*" + label + r"[^\n]*?(-?\d+)\s*$", text, re.I | re.M)
        if not values or len(set(values)) != 1:
            raise R2ReferenceError(f"Benchmark output omits or contradicts its {label}")
        states[key] = int(values[-1])
    sections = re.split(r"CARTESIAN COORDINATES\s*\(ANGSTROEM\)", text, flags=re.I)
    if len(sections) < 2:
        raise R2ReferenceError("Benchmark output omits its Cartesian coordinates in Angstrom")
    symbols, coordinates = [], []
    for line in sections[-1].splitlines():
        stripped = line.strip()
        if not symbols and (not stripped or set(stripped) <= {"-"}):
            continue
        fields = stripped.split()
        if len(fields) == 5 and fields[0].isdigit():
            fields = fields[1:]
        if len(fields) != 4 or not re.fullmatch(r"[A-Z][a-z]?", fields[0]):
            break
        try:
            position = [float(item.replace("D", "E").replace("d", "e")) for item in fields[1:]]
        except ValueError as error:
            raise R2ReferenceError("Invalid benchmark Cartesian coordinate") from error
        if not np.isfinite(position).all():
            raise R2ReferenceError("Nonfinite benchmark Cartesian coordinate")
        symbols.append(fields[0])
        coordinates.append(position)
    if not symbols:
        raise R2ReferenceError("Benchmark output has an empty or unsupported Cartesian block")
    _state(symbols, states["charge"], states["multiplicity"])
    return {"elements": symbols, "coordinates_angstrom": coordinates, **states}


def validate_reference_output(path: Path, basis_name: str) -> dict[str, Any]:
    """Accept explicit ORCA canonical CCSD(T) benchmark completion evidence.

    Supported text must contain ORCA normal termination, explicit CCSD(T) and
    SCF total energies, SCF convergence, and the requested correlation-consistent
    basis. Unknown/CFOUR formats require a dedicated parser before acceptance.
    """
    text = path.read_text(encoding="utf-8")
    if text.count("ORCA TERMINATED NORMALLY") != 1 or not re.search(r"\bORCA\b", text):
        raise R2ReferenceError(
            f"Unsupported or incomplete benchmark output {path}: currently accepted format is "
            "normally completed ORCA canonical CCSD(T), with E(CCSD(T)), E(SCF), and explicit basis"
        )
    if re.search(
        r"DLPNO|PNO-LCCSD|SCF NOT CONVERGED|SCF DID NOT CONVERGE|ERROR TERMINATION", text, re.I
    ):
        raise R2ReferenceError(
            "Benchmark must be converged canonical CCSD(T), not a local approximation"
        )
    if not re.search(r"(?<![A-Za-z0-9_-])" + re.escape(basis_name) + r"(?![A-Za-z0-9_-])", text, re.I):
        raise R2ReferenceError(f"Benchmark output does not establish requested basis {basis_name}")
    if not re.search(r"SCF CONVERGED AFTER\s+\d+\s+CYCLES", text, re.I):
        raise R2ReferenceError("Benchmark output omits explicit successful SCF convergence")
    number = r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eEdD][-+]?\d+)?)"
    cc = re.findall(r"E\s*\(\s*CCSD\(T\)\s*\)\s*(?:=|:|\.{2,})?\s*" + number, text, re.I)
    hf = re.findall(r"E\s*\(\s*SCF\s*\)\s*(?:=|:|\.{2,})?\s*" + number, text, re.I)
    if not cc or not hf:
        raise R2ReferenceError(
            "Benchmark output requires explicit E(CCSD(T)) and E(SCF), not a generic final energy"
        )
    values = [float(value.replace("D", "E").replace("d", "e")) for value in (cc[-1], hf[-1])]
    if not all(math.isfinite(value) for value in values):
        raise R2ReferenceError("Benchmark energies must be finite")
    return {
        **parse_reference_geometry_state(text),
        "engine": "ORCA",
        "method": "canonical CCSD(T)",
        "basis": basis_name,
        "normal_completion": True,
        "ccsdt_energy_hartree": values[0],
        "scf_energy_hartree": values[1],
        "correlation_energy_hartree": values[0] - values[1],
    }


def load_r2_references(
    path: str | Path,
    symbols: Sequence[str],
    coordinates: Sequence[Sequence[float]],
    *,
    charge: int,
    multiplicity: int,
) -> tuple[R2ReferenceManifest, dict[str, Any]]:
    """Verify input identity, full artifact provenance and internal geometry.

    CCSD(T)/CBS is the reference supplier's scientific provenance assertion;
    source artifacts and their digests are required for independent review.
    """
    source = Path(path).resolve(strict=True)
    manifest = R2ReferenceManifest.model_validate_json(source.read_text(encoding="utf-8"))
    xyz = np.asarray(coordinates, dtype=float)
    if xyz.shape != (len(symbols), 3) or not np.isfinite(xyz).all():
        raise R2ReferenceError("A finite N x 3 input geometry is required")
    indices = [index for monomer in manifest.monomers for index in monomer.atom_indices]
    if sorted(indices) != list(range(len(symbols))):
        raise R2ReferenceError("Monomer references must cover every submitted atom exactly once")
    if sum(m.charge for m in manifest.monomers) != charge:
        raise R2ReferenceError("Monomer charges do not add to the dimer charge")
    _state(symbols, charge, multiplicity)
    spins = [m.multiplicity - 1 for m in manifest.monomers]
    if not abs(spins[0] - spins[1]) <= multiplicity - 1 <= sum(spins):
        raise R2ReferenceError("Dimer spin cannot couple the supplied monomer states")
    evidence = []
    for monomer in manifest.monomers:
        paths = {
            name: getattr(monomer, name).verify(source.parent)
            for name in ("geometry", "lower_cardinal_output", "upper_cardinal_output")
        }
        reference_symbols, reference_xyz = _geometry(paths["geometry"].read_text(encoding="utf-8"))
        selected_symbols = [symbols[index] for index in monomer.atom_indices]
        if selected_symbols != reference_symbols:
            raise R2ReferenceError("Reference atom identities/order differ from the dimer mapping")
        _state(reference_symbols, monomer.charge, monomer.multiplicity)
        benchmarks = []
        for cardinal, key in zip(
            monomer.basis_cardinal_pair, ("lower_cardinal_output", "upper_cardinal_output")
        ):
            cardinal_name = {3: "T", 4: "Q", 5: "5"}[cardinal]
            basis_name = monomer.basis_family.replace("X", cardinal_name)
            benchmark = validate_reference_output(paths[key], basis_name)
            if benchmark["elements"] != reference_symbols:
                raise R2ReferenceError("Benchmark output atom identities/order do not match its reference XYZ")
            if (benchmark["charge"], benchmark["multiplicity"]) != (monomer.charge, monomer.multiplicity):
                raise R2ReferenceError("Benchmark output charge/multiplicity does not match the reference manifest")
            benchmark_xyz = np.asarray(benchmark["coordinates_angstrom"])
            reference_distances = np.linalg.norm(reference_xyz[:, None, :] - reference_xyz[None, :, :], axis=2)
            benchmark_distances = np.linalg.norm(benchmark_xyz[:, None, :] - benchmark_xyz[None, :, :], axis=2)
            maximum_difference = float(np.max(np.abs(reference_distances - benchmark_distances)))
            # Standard ORCA text coordinates have six decimal places. This is
            # linkage tolerance for rounded source text, not the 1e-6 A drift gate.
            if maximum_difference > 2e-6:
                raise R2ReferenceError("Benchmark output geometry does not match the supplied reference XYZ")
            benchmark["reference_geometry_maximum_distance_difference_angstrom"] = maximum_difference
            benchmark["reference_geometry_linkage_tolerance_angstrom"] = 2e-6
            benchmarks.append(benchmark)
        lower, upper = monomer.basis_cardinal_pair
        cbs_correlation = (
            upper**3 * benchmarks[1]["correlation_energy_hartree"]
            - lower**3 * benchmarks[0]["correlation_energy_hartree"]
        ) / (upper**3 - lower**3)
        selected_xyz = xyz[monomer.atom_indices]
        _, drift = validate_trajectory_monomer_drift(
            [reference_xyz, selected_xyz],
            list(range(len(reference_symbols))),
            raise_on_violation=True,
        )
        evidence.append(
            {
                **monomer.model_dump(mode="json"),
                "verified_paths": {name: str(value) for name, value in paths.items()},
                "initial_internal_drift_angstrom": drift,
                "benchmark_output_checks": benchmarks,
                "helgaker_cbs_correlation_energy_hartree": cbs_correlation,
            }
        )
    return manifest, {
        "manifest": str(source),
        "manifest_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "monomers": evidence,
        "reference_method": "CCSD(T)/CBS",
        "reference_scientific_provenance": "UNVERIFIED",
        "verified_reference_evidence": "source hashes, canonical method, basis pair, normal completion, coordinates, charge and multiplicity",
        "unverified_reference_claim": "The external supplier's assertion that the monomer geometry is optimized at the CCSD(T)/CBS limit requires independent benchmark review; two single-point energies alone do not establish it.",
    }


def build_r2_leg_deck(
    leg: Literal["dimer", "monomer_a", "monomer_b", "ghost_a", "ghost_b"],
    symbols: Sequence[str],
    coordinates: Sequence[Sequence[float]],
    references: R2ReferenceManifest,
    *,
    charge: int,
    multiplicity: int,
    cores: int,
    maxcore_mb: int,
) -> tuple[str, list[str], np.ndarray, int]:
    """Serialize one of the five physical calculations, with correct ghost states."""
    if leg not in {"dimer", "monomer_a", "monomer_b", "ghost_a", "ghost_b"}:
        raise ValueError("Unknown R2 counterpoise leg")
    xyz = np.asarray(coordinates, dtype=float)
    if xyz.shape != (len(symbols), 3) or not np.isfinite(xyz).all():
        raise ValueError("Finite geometry is required")
    if cores < 1 or maxcore_mb < 1:
        raise ValueError("Positive audited resources are required")
    all_symbols = list(symbols)
    for symbol in all_symbols:
        if not re.fullmatch(r"[A-Z][a-z]?", symbol):
            raise ValueError("Only real element symbols may define reference nuclei")
        get_element_mass_and_abundance(symbol)
    current_symbols, current_xyz = all_symbols, xyz
    geom = ""
    if leg == "dimer":
        constraints = generate_frozen_monomer_constraints(
            references.monomers[0].atom_indices,
            references.monomers[1].atom_indices,
            symbols=symbols,
            coordinates=xyz,
        )
        geom = format_orca_frozen_monomer_constraints_block(constraints) + "\n"
    else:
        reference = references.monomers[0 if leg.endswith("a") else 1]
        charge, multiplicity = reference.charge, reference.multiplicity
        active = set(reference.atom_indices)
        if leg.startswith("ghost"):
            current_symbols = [
                symbol if i in active else symbol + ":" for i, symbol in enumerate(symbols)
            ]
        else:
            current_symbols = [symbols[i] for i in reference.atom_indices]
            current_xyz = xyz[reference.atom_indices]
    _state([s for s in current_symbols if not s.endswith(":")], charge, multiplicity)
    deck = (
        "! wB97M-V def2-QZVPP def2/J RIJCOSX TightSCF DEFGRID3"
        + (" TightOpt" if leg == "dimer" else "")
        + "\n"
        + f"%pal nprocs {cores} end\n%maxcore {maxcore_mb}\n"
        + "%scf\n TolE 1.0e-8\n Thresh 1.0e-11\n MaxIter 150\nend\n"
        + geom
        + f"* xyz {charge} {multiplicity}\n"
        + "\n".join(
            f"{s} {x:.17g} {y:.17g} {z:.17g}" for s, (x, y, z) in zip(current_symbols, current_xyz)
        )
        + "\n*\n"
    )
    return deck, current_symbols, current_xyz, multiplicity


def counterpoise_bracket(energies: dict[str, float], tolerance: float = 1e-7) -> dict[str, float]:
    names = {"dimer", "monomer_a", "monomer_b", "ghost_a", "ghost_b"}
    if set(energies) != names or any(
        isinstance(v, bool) or not math.isfinite(v) for v in energies.values()
    ):
        raise ValueError("All five measured finite leg energies are required")
    raw = energies["dimer"] - energies["monomer_a"] - energies["monomer_b"]
    cp = energies["dimer"] - energies["ghost_a"] - energies["ghost_b"]
    correction = cp - raw
    if correction < -tolerance:
        raise ValueError("Counterpoise correction reverses the variational BSSE bracket")
    return {
        "uncorrected_interaction_hartree": raw,
        "counterpoise_interaction_hartree": cp,
        "bsse_correction_hartree": correction,
        "bracket_lower_hartree": min(raw, cp),
        "bracket_upper_hartree": max(raw, cp),
    }


def read_dimer_gradient(
    path: Path, symbols: list[str], coordinates: np.ndarray
) -> tuple[float, np.ndarray]:
    fields = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    n = len(symbols)
    if not fields or int(fields[0]) != n or len(fields) != 2 + 4 * n:
        raise ValueError("ORCA engrad is incomplete or has the wrong atom count")
    numeric = lambda value: float(value.replace("D", "E").replace("d", "e"))
    energy = numeric(fields[1])
    gradient = np.asarray([numeric(v) for v in fields[2 : 2 + 3 * n]]).reshape(n, 3)
    nuclei = [row.split() for row in fields[2 + 3 * n :]]
    if any(len(row) != 4 for row in nuclei):
        raise ValueError("Invalid engrad nuclear coordinates")
    expected_z = [get_element_mass_and_abundance(symbol)[2] for symbol in symbols]
    if [int(float(row[0])) for row in nuclei] != expected_z:
        raise ValueError("ORCA engrad atom identities/order differ from the final geometry")
    bohr_angstrom = physical_constants["Bohr radius"][0] * 1e10
    observed_xyz = np.asarray([[numeric(v) for v in row[1:]] for row in nuclei]) * bohr_angstrom
    if (
        not math.isfinite(energy)
        or not np.isfinite(gradient).all()
        or not np.allclose(observed_xyz, coordinates, atol=1e-7, rtol=0)
    ):
        raise ValueError("ORCA gradient is nonfinite or does not belong to the final geometry")
    return energy, gradient


def execute_recipe_r2(
    symbols: Sequence[str],
    coordinates: Sequence[Sequence[float]],
    reference_manifest: str | Path,
    *,
    work_dir: str | Path,
    registry_path: str | Path | None = None,
    charge: int = 0,
    multiplicity: int = 1,
    cores: int | None = None,
    maxcore_mb: int | None = None,
    timeout_seconds: float = 3600.0,
    cancellation_event: Any = None,
    on_event: Callable[[dict], None] | None = None,
    is_freq: bool = False,
    is_vpt2: bool = False,
) -> dict[str, Any]:
    """Optimize the frozen dimer, run four SP legs, then publish actual evidence."""
    if (
        isinstance(timeout_seconds, bool)
        or not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0
    ):
        raise ValueError("R2 requires a finite positive overall timeout")
    started = time.monotonic()
    deadline = started + timeout_seconds
    if is_freq or is_vpt2:
        raise ValueError("R2 counterpoise optimization does not certify frequency/VPT2 properties")
    manifest, reference_evidence = load_r2_references(
        reference_manifest,
        symbols,
        coordinates,
        charge=charge,
        multiplicity=multiplicity,
    )
    authorization = authorize_engine_execution(
        "orca", registry_path=registry_path, cores=cores, maxcore_mb=maxcore_mb
    )
    root = Path(work_dir).resolve()
    from cochem.core.context import assert_writable_path

    assert_writable_path(root)
    checkout = Path(__file__).resolve().parents[3]
    if (checkout / "pyproject.toml").is_file() and root.is_relative_to(checkout):
        raise ValueError("R2 runtime artifacts must be outside the source checkout")
    root.mkdir(parents=True, exist_ok=False)
    (root / "reference_evidence.json").write_text(
        json.dumps(reference_evidence, indent=2), encoding="utf-8"
    )
    original = np.asarray(coordinates, dtype=float)
    final_xyz = original.copy()
    energies, legs = {}, {}
    dimer_gradient = None
    identity = "r2_" + uuid.uuid4().hex
    telemetry_cancel = threading.Event()

    class CancellationScope:
        def is_set(self) -> bool:
            return telemetry_cancel.is_set() or (
                cancellation_event is not None and cancellation_event.is_set()
            )

    for leg in ["dimer", "monomer_a", "monomer_b", "ghost_a", "ghost_b"]:
        directory = root / leg
        directory.mkdir()
        deck, leg_symbols, leg_xyz, leg_spin = build_r2_leg_deck(
            leg,
            symbols,
            final_xyz,
            manifest,
            charge=charge,
            multiplicity=multiplicity,
            cores=authorization.cores,
            maxcore_mb=authorization.maxcore_mb,
        )
        input_path = directory / "calculation.inp"
        input_path.write_text(deck, encoding="utf-8")
        validator = SpinContaminationStreamValidator(leg_spin)

        def stream(line: str) -> None:
            validator(line)
            if on_event:
                on_event({"kind": "log", "leg": leg, "stream": "stdout", "message": line})

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Overall R2 five-leg execution budget expired")
        leg_started = time.monotonic()
        follower = None
        if leg == "dimer":
            from cochem_base.core_engine.trajectory_telemetry import XYZTrajectoryFollower

            follower = XYZTrajectoryFollower(
                directory / "calculation_trj.xyz",
                f"{identity}_{leg}",
                symbols,
                source_format="orca",
                required=True,
                metadata={
                    "engine": "orca",
                    "recipe": "R2",
                    "counterpoise_leg": leg,
                    "record_kind": "optimization_trajectory",
                },
                on_error=lambda error: telemetry_cancel.set(),
            )
        try:
            with follower if follower is not None else nullcontext():
                result = safe_subprocess_run(
                    authorization.command([input_path.name]),
                    cwd=directory,
                    timeout=remaining,
                    env=sanitize_mpi_environment(
                        engine_runtime_environment("orca", executable=authorization.executable),
                        force_single_thread=True,
                    ),
                    capture_output=True,
                    text=True,
                    check=False,
                    required_disk_gb=0.1,
                    on_stdout_line=stream,
                    load_full_stdout=True,
                    cancellation_event=CancellationScope(),
                    cpu_affinity=list(authorization.cpu_affinity) or None,
                )
        finally:
            if follower is not None:
                (directory / "trajectory_telemetry.json").write_text(
                    json.dumps(follower.status, indent=2), encoding="utf-8"
                )
        log = directory / "calculation.out"
        log.write_text(result.stdout or "", encoding="utf-8")
        (directory / "stderr.log").write_text(result.stderr or "", encoding="utf-8")
        if result.returncode:
            raise RuntimeError(f"ORCA R2 leg {leg} failed; diagnostics retained at {directory}")
        parser = QuantumParser(str(directory))
        parser.scf_threshold = 1e-8
        if not parser.verify_scf_convergence(log):
            raise RuntimeError(f"R2 leg {leg} lacks accepted SCF convergence")
        parser.check_spin_contamination(log, multiplicity=leg_spin)
        digest = hashlib.sha256(log.read_bytes()).hexdigest()
        schema = parser.parse_to_qcschema(log, f"{identity}_{leg}", digest)
        energies[leg] = schema.properties.return_energy
        if leg == "dimer":
            parser.verify_geometry_convergence(log)
            final_symbols, final_xyz = _geometry(
                (directory / "calculation.xyz").read_text(encoding="utf-8")
            )
            if list(symbols) != final_symbols:
                raise R2ReferenceError("Optimized dimer atom identities/order changed")
            from cochem_base.calc.calculation_service import validate_frozen_monomer_trajectory

            drift = validate_frozen_monomer_trajectory(
                directory / "calculation_trj.xyz",
                list(symbols),
                original.tolist(),
                final_xyz.tolist(),
            )
            # Check the explicit reference partition too, independent of graph perception.
            for monomer in manifest.monomers:
                validate_trajectory_monomer_drift(
                    [original, final_xyz], monomer.atom_indices, raise_on_violation=True
                )
            gradient_energy, dimer_gradient = read_dimer_gradient(
                directory / "calculation.engrad", list(symbols), final_xyz
            )
            if abs(gradient_energy - energies[leg]) > 1e-7:
                raise ValueError("Final dimer energy and gradient checkpoint disagree")
        legs[leg] = {
            "energy_hartree": energies[leg],
            "output_sha256": digest,
            "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
            "directory": str(directory),
            "charge": charge
            if leg == "dimer"
            else manifest.monomers[0 if leg.endswith("a") else 1].charge,
            "multiplicity": leg_spin,
            "scf_converged": True,
            "wall_time_seconds": time.monotonic() - leg_started,
        }
        if follower is not None:
            legs[leg]["trajectory_telemetry"] = follower.status
    constraints = generate_frozen_monomer_constraints(
        manifest.monomers[0].atom_indices,
        manifest.monomers[1].atom_indices,
        symbols=symbols,
        coordinates=final_xyz,
    )
    bmatrix = build_wilson_b_matrix(constraints, final_xyz)
    _, singular, vt = np.linalg.svd(bmatrix, full_matrices=False)
    basis = vt[singular > 1e-10]
    frozen_gradient = basis.T @ (basis @ dimer_gradient.reshape(-1))
    norm = float(np.linalg.norm(frozen_gradient))
    strained = norm > 1e-4
    if strained:
        warnings.warn(
            f"Frozen-coordinate residual gradient {norm:.6g} Eh/bohr exceeds 1e-4",
            ResidualGradientWarning,
        )
    evidence = {
        "engine": "orca",
        "method": "wB97M-V",
        "basis_set": "def2-QZVPP",
        "recipe": "R2",
        "wall_time_seconds": time.monotonic() - started,
        "operation": "frozen_monomer_optimization_with_counterpoise",
        "converged": True,
        "energy_hartree": energies["dimer"],
        "elements": list(symbols),
        "coordinates_angstrom": final_xyz.tolist(),
        "gradients_hartree_per_bohr": dimer_gradient.tolist(),
        "counterpoise": counterpoise_bracket(energies),
        "legs": legs,
        "reference_evidence": reference_evidence,
        "frozen_monomer_integrity": drift,
        "residual_gradient_norm_hartree_per_bohr": norm,
        "residual_gradient_warning": strained,
        "residual_gradient_threshold": 1e-4,
        "scientific_acceptance": (
            "strain_warning_reference_geometry_quality_unverified"
            if strained else "execution_checks_passed_reference_geometry_quality_unverified"
        ),
    }
    from cochem_base.core_engine.scientific_telemetry import append_scientific_result

    for leg, details in legs.items():
        # Ghost basis functions are metadata; only real nuclei enter mass telemetry.
        active = (
            list(range(len(symbols)))
            if leg == "dimer"
            else manifest.monomers[0 if leg.endswith("a") else 1].atom_indices
        )
        append_scientific_result(
            f"{identity}_{leg}",
            [symbols[i] for i in active],
            final_xyz[active],
            energies[leg],
            dimer_gradient if leg == "dimer" else None,
            metadata={
                "recipe": "R2",
                "counterpoise_leg": leg,
                "converged": True,
                "output_sha256": details["output_sha256"],
                "reference_manifest_sha256": reference_evidence["manifest_sha256"],
            },
        )
    (root / "r2_result.json").write_text(
        json.dumps(evidence, indent=2, allow_nan=False), encoding="utf-8"
    )
    return evidence
