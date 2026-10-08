#!/usr/bin/env python3
"""
CoChem-CORE Stage 2.4: Quantum Parser
Enforces strict SCF convergence checks (ΔE < 10^-7), QCSchema JSON-LD exports,
cryptographic SHA-256 artifact verification, and applies immutable POSIX read-only locks (chmod 0o444).
"""

import hashlib
import json
import logging
import math
import os
import re
from pathlib import Path
from typing import Optional, Tuple, Union

from pydantic import BaseModel, Field

from cochem_base.analysis.electronic_sanitizer import ElectronicSanitizer
from cochem_base.exceptions import GeometryConvergenceError, MissingDataError

_NUMBER = r"(?:[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eEdD][-+]?\d+)?|[-+]?(?:nan|inf(?:inity)?))"


def _number(value: str) -> float:
    return float(value.replace("D", "E").replace("d", "e"))


def _stationary_trah_energy_change(content: str) -> Optional[float]:
    """Read ORCA 6.1.1's measured one-cycle stationary restart evidence.

    Native 6.1.1 TRAH can converge immediately from its initial orbitals. Its
    summary then prints the total SCF energy in ``Last Energy change``. The
    iteration-zero energy and final SCF total still independently establish the
    actual change. Accept this narrowly identified case only when every native
    residual and tolerance is present and no SCF iteration was omitted.
    """
    if not re.search(r"Program Version\s+6\.1\.1\b", content) or "ORCA TERMINATED NORMALLY" not in content:
        return None
    sections = re.split(r"ORCA LEAN-SCF", content)
    if len(sections) < 2:
        return None
    final = sections[-1]
    cycles = re.findall(r"SCF CONVERGED AFTER\s+(\d+)\s+CYCLES", final)
    if cycles != ["1"]:
        return None
    rows = re.findall(rf"^[ \t]*(\d+)[ \t]+({_NUMBER})[ \t]+({_NUMBER})[^\n]*\(TRAH MAcro\)[ \t]+No[ \t]*$",
                      final, re.I | re.M)
    totals = re.findall(rf"^[ \t]*Total Energy[ \t]*:[ \t]*({_NUMBER})[ \t]+Eh\b", final, re.M)
    if len(rows) != 1 or rows[0][0] != "0" or len(totals) != 1:
        return None
    initial, orbital_residual = _number(rows[0][1]), abs(_number(rows[0][2]))
    total = _number(totals[0])
    if not all(math.isfinite(value) for value in (initial, total, orbital_residual)):
        return None
    thresholds = {
        "Energy change": 1e-7, "MAX-Density change": 1e-7, "RMS-Density change": 5e-9,
        "DIIS Error": 5e-7, "Orbital Gradient": 1e-5, "Orbital Rotation": 1e-5,
    }
    observed: dict[str, tuple[float, float, str]] = {}
    for label, ceiling in thresholds.items():
        values = re.findall(rf"^[ \t]*Last {re.escape(label)}[ \t]*\.{{2,}}[ \t]*({_NUMBER})"
                            rf"[ \t]+Tolerance[ \t]*:[ \t]*({_NUMBER})[ \t]*$", final, re.M)
        if len(values) != 1:
            return None
        value, tolerance = _number(values[0][0]), _number(values[0][1])
        if not math.isfinite(value) or not math.isfinite(tolerance) or not 0 < tolerance <= ceiling:
            return None
        if label != "Energy change" and abs(value) > tolerance:
            return None
        observed[label] = value, tolerance, values[0][0]
    # Match the known sentinel at its native printed precision. This is only an
    # identity check; the independent measured difference below stays strict.
    sentinel, energy_tolerance, token = observed["Energy change"]
    mantissa, _, exponent = token.lower().replace("d", "e").partition("e")
    fraction_digits = len(mantissa.partition(".")[2])
    print_resolution = 10.0 ** (int(exponent or "0") - fraction_digits)
    if not math.isclose(sentinel, total, rel_tol=0, abs_tol=0.51 * print_resolution):
        return None
    delta = abs(total - initial)
    if delta >= min(1e-7, energy_tolerance) or orbital_residual > observed["Orbital Gradient"][1]:
        return None
    return delta


class QCSchemaProperties(BaseModel):
    return_energy: float = Field(allow_inf_nan=False)
    scf_iterations: int

class QCSchemaProvenance(BaseModel):
    creator: str
    engine: str
    log_sha256: str
    gbw_sha256: Optional[str] = None

class QCSchemaMolecule(BaseModel):
    context: str = Field(alias="@context")
    schema_name: str
    schema_version: str
    basin_id: str
    properties: QCSchemaProperties
    provenance: QCSchemaProvenance

from cochem_base.config_loader import get_artifact_dir, resolve_mapped_path  # noqa: E402

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-QuantumParser")


class QuantumParser:
    def __init__(self, artifact_dir: Optional[str] = None) -> None:
        if artifact_dir:
            self.artifact_base = resolve_mapped_path(artifact_dir, get_artifact_dir())
        else:
            self.artifact_base = get_artifact_dir() / "Scratch"
        self.artifact_base.mkdir(parents=True, exist_ok=True)
        self.scf_threshold = 1e-7

    def verify_scf_convergence(self, log_path: Path) -> bool:
        delta_e_pattern = re.compile(
            rf"(?:\bdE\s*=\s*|\bLast Energy change\s*(?:\.{{2,}}|:|=)?\s*)({_NUMBER})",
            re.IGNORECASE,
        )
        last_de = None

        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()



        for line in content.splitlines():
            match = delta_e_pattern.search(line)
            if match:
                last_de = abs(_number(match.group(1)))
        if re.search(r"SCF NOT CONVERGED|SCF DID NOT CONVERGE|ERROR TERMINATION", content, re.I):
            return False
        if "TERMINATED NORMALLY" not in content or last_de is None:
            return False
        if not math.isfinite(last_de):
            return False
        if last_de >= self.scf_threshold:
            measured_restart_change = _stationary_trah_energy_change(content)
            if measured_restart_change is not None:
                logger.info("Accepted measured stationary TRAH restart SCF change %.3e Eh", measured_restart_change)
                return True
            logger.error("SCF energy change %s does not satisfy %s", last_de, self.scf_threshold)
            return False
        return True

    def verify_basis_saturation(self, log_path: Path) -> None:
        primary_pat = re.compile(r"^\s*(?:Number of basis functions|Basis Dimension|Basis Size)\s*(?:Dim\s*)?(?:\.{3,}|:)\s*(\d+)", re.IGNORECASE)
        aux_pat = re.compile(r"^\s*(?:Number of Aux.*basis functions|# of basis functions in Aux.*?|Auxiliary Basis Dimension|Auxiliary Basis Size)\s*(?:\.{3,}|:)\s*(\d+)", re.IGNORECASE)

        n_primary = None
        n_aux = None

        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                m1 = primary_pat.search(line)
                if m1:
                    val = int(m1.group(1))
                    n_primary = max(n_primary, val) if n_primary is not None else val

                m2 = aux_pat.search(line)
                if m2:
                    val = int(m2.group(1))
                    n_aux = max(n_aux, val) if n_aux is not None else val

        if n_primary is not None and n_aux is not None:
            if n_aux <= n_primary:
                logger.warning(f"[CROWN WARNING] Auxiliary Basis Under-saturation! N_aux ({n_aux}) <= N_primary ({n_primary}). Risk of severe Density Fitting accuracy loss.")

    def check_spin_contamination(
        self, log_path: Path, threshold: float = 0.1, multiplicity: Optional[int] = None
    ) -> bool:
        """Enforce the relative spin gate before accepting any trajectory result.

        ``threshold`` is a fraction (0.1 means 10%), not an absolute S-squared
        difference. Missing diagnostics cannot establish spin purity. Restricted
        closed-shell jobs may omit S-squared only when actual SCF settings report
        a restricted reference and singlet multiplicity. Credits and echoed
        input keywords do not identify the calculated wavefunction.
        """
        content = Path(log_path).read_text(encoding="utf-8", errors="replace")
        if multiplicity is not None and (isinstance(multiplicity, bool) or not isinstance(multiplicity, int) or multiplicity < 1):
            raise ValueError("Spin multiplicity must be a positive integer.")
        observed = re.findall(rf"Expectation value of <S(?:\*\*|\^)2>\s*:\s*({_NUMBER})", content, re.I)
        ideal = re.findall(rf"Ideal value S\*\(S\+1\)\s*:\s*({_NUMBER})", content, re.I)
        if not math.isfinite(threshold) or not 0 < threshold <= 0.1:
            raise ValueError("The spin-contamination threshold must be in (0, 0.1].")
        if multiplicity is None and ideal:
            ideals = [_number(item) for item in ideal]
            if any(not math.isfinite(item) or item < 0 for item in ideals):
                raise MissingDataError("Invalid ideal spin expectation value in output.")
            roots = [math.sqrt(1.0 + 4.0 * item) for item in ideals]
            multiplicity = round(roots[-1])
            if any(not math.isclose(root, multiplicity, abs_tol=1e-6) for root in roots):
                raise MissingDataError("Inconsistent or nonphysical ideal spin values in output.")
        if not observed:
            references = re.findall(
                r"^[ \t]*Hartree-Fock type[ \t]+HFTyp[ \t]+\.{2,}[ \t]+(\S+)[ \t]*$",
                content, re.I | re.M,
            )
            reported_multiplicities = re.findall(
                r"^[ \t]*Multiplicity[ \t]+Mult[ \t]+\.{2,}[ \t]+(\S+)[ \t]*$",
                content, re.I | re.M,
            )
            # ORCA credits mention UHF even in RHF output. Conversely, an RHF
            # keyword in credits/input must not exempt an unrestricted result.
            # Require every reported SCF state to be an explicit singlet with a
            # restricted reference; mixed or incomplete summaries fail closed.
            if (
                references
                and {reference.upper() for reference in references} <= {"RHF", "RKS"}
                and len(references) == len(reported_multiplicities)
                and set(reported_multiplicities) == {"1"}
                and multiplicity in (None, 1)
            ):
                return True
            raise MissingDataError("Missing spin diagnostics; unrestricted results cannot be accepted.")
        if multiplicity is None:
            raise MissingDataError("Spin multiplicity or ideal S*(S+1) is required to assess contamination.")
        for value in observed:
            ElectronicSanitizer.diagnose_spin_contamination(
                _number(value), multiplicity=multiplicity, relative_threshold_pct=100.0 * threshold
            )
        return True

    def verify_geometry_convergence(self, log_path: Path) -> dict[str, float]:
        """Check the final ORCA convergence table against all five SRS limits."""
        content = Path(log_path).read_text(encoding="utf-8", errors="replace")
        if not re.search(r"OPTIMIZATION (?:HAS )?CONVERGED", content, re.I):
            raise GeometryConvergenceError("Missing successful geometry optimization termination.")
        limits = {"Energy change": 1e-7, "RMS gradient": 3e-6, "MAX gradient": 1e-5,
                  "RMS step": 5e-5, "MAX step": 1e-4}
        final: dict[str, float] = {}
        # A new convergence table invalidates the preceding cycle's evidence.
        tables = re.split(r"Geometry convergence", content, flags=re.I)
        table = tables[-1]
        for label, limit in limits.items():
            values = re.findall(rf"^\s*{label}\s*(?::|=)?\s*({_NUMBER})\b", table, re.I | re.M)
            if not values:
                # A stationary restart can finish on its first optimization
                # cycle. ORCA then omits the table's energy-change row but
                # evaluates both the initial and final geometry. Use those two
                # actual energies only when their one-cycle ordering is clear.
                cycles = re.findall(r"GEOMETRY OPTIMIZATION CYCLE\s+(\d+)\b", content, re.I)
                energies = list(re.finditer(rf"FINAL SINGLE POINT ENERGY\s+({_NUMBER})", content, re.I))
                table_start = content.lower().rfind("geometry convergence")
                converged = re.search(r"OPTIMIZATION (?:HAS )?CONVERGED", content, re.I)
                if (label != "Energy change" or len(tables) != 2 or cycles != ["1"] or len(energies) != 2
                        or "ORCA TERMINATED NORMALLY" not in content
                        or not energies[0].start() < table_start < converged.start() < energies[1].start()):
                    raise GeometryConvergenceError(f"Missing final {label} convergence evidence.")
                value = abs(_number(energies[1][1]) - _number(energies[0][1]))
            else:
                value = abs(_number(values[-1]))
            if not math.isfinite(value) or value > limit:
                raise GeometryConvergenceError(f"Final {label} {value:g} exceeds required {limit:g}.")
            final[label] = value
        return final

    def parse_to_qcschema(self, log_path: Path, basin_id: str, log_sha256: str, gbw_sha256: Optional[str] = None) -> QCSchemaMolecule:
        final_energy = None
        scf_iterations = None
        energy_pattern = re.compile(rf"FINAL SINGLE POINT ENERGY\s+({_NUMBER})", re.I)
        iter_pattern1 = re.compile(r"Total SCF iterations\s*:\s*(\d+)")
        iter_pattern2 = re.compile(r"SCF ITERATION\s+(\d+)", re.IGNORECASE)
        iter_pattern3 = re.compile(r"SCF CONVERGED AFTER\s+(\d+)\s+CYCLES", re.IGNORECASE)

        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                match = energy_pattern.search(line)
                if match:
                    final_energy = _number(match.group(1))
                
                m1 = iter_pattern1.search(line)
                if m1:
                    scf_iterations = int(m1.group(1))
                
                m2 = iter_pattern2.search(line)
                if m2:
                    val = int(m2.group(1))
                    if scf_iterations is None or val > scf_iterations:
                        scf_iterations = val
                m3 = iter_pattern3.search(line)
                if m3:
                    scf_iterations = int(m3.group(1))

        if final_energy is None or not math.isfinite(final_energy):
            raise ValueError("[MISSING DATA] Could not extract FINAL SINGLE POINT ENERGY from log.")
        if scf_iterations is None:
            raise ValueError("[MISSING DATA] Could not extract SCF iterations from log.")

        return QCSchemaMolecule(
            **{"@context": "https://w3id.org/ro/qcschema"},
            schema_name="qcschema_molecule",
            schema_version="1.0",
            basin_id=basin_id,
            properties=QCSchemaProperties(return_energy=final_energy, scf_iterations=scf_iterations),
            provenance=QCSchemaProvenance(creator="CoChem-CORE", engine="ORCA 6.1.1", log_sha256=log_sha256, gbw_sha256=gbw_sha256)
        )

    def apply_immutable_lock(self, file_path: Path) -> None:
        if file_path.exists():
            file_path.chmod(0o444)

    def process_artifact(
        self, basin_id: str, *, is_optimization: Optional[bool] = None,
        multiplicity: Optional[int] = None,
    ) -> bool:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", basin_id):
            raise ValueError("basin_id must be a safe filename component.")
        log_path = self.artifact_base / f"{basin_id}_job.out"
        json_path = self.artifact_base / f"{basin_id}_qcschema.json"
        gbw_path = self.artifact_base / f"{basin_id}_job.gbw"

        if not log_path.exists():
            raise FileNotFoundError(f"[MISSING DATA] Job log not found: {log_path}")

        if not self.verify_scf_convergence(log_path):
            return False

        self.check_spin_contamination(log_path, multiplicity=multiplicity)
        if is_optimization is None:
            content = log_path.read_text(encoding="utf-8", errors="replace")
            is_optimization = bool(re.search(r"GEOMETRY OPTIMIZATION|OPTIMIZATION (?:HAS )?CONVERGED", content, re.I))
        if is_optimization:
            self.verify_geometry_convergence(log_path)

        self.verify_basis_saturation(log_path)

        # Compute SHA-256 for provenance
        with open(log_path, 'rb') as f:
            log_sha256 = hashlib.sha256(f.read()).hexdigest()
        
        gbw_sha256 = None
        if gbw_path.exists():
            with open(gbw_path, 'rb') as f:
                gbw_sha256 = hashlib.sha256(f.read()).hexdigest()

        schema = self.parse_to_qcschema(log_path, basin_id, log_sha256, gbw_sha256)

        # Write to a temporary file first for atomic POSIX-compliant write
        tmp_json_path = json_path.with_suffix(".json.tmp")
        schema_dict = schema.model_dump(by_alias=True) if hasattr(schema, 'model_dump') else schema.dict(by_alias=True)
        with open(tmp_json_path, 'w', encoding='utf-8') as f:
            json.dump(schema_dict, f, indent=4)

        os.replace(tmp_json_path, json_path)

        self.apply_immutable_lock(log_path)
        if gbw_path.exists():
            self.apply_immutable_lock(gbw_path)
        self.apply_immutable_lock(json_path)
        return True

    def parse_residual_gradients(
        self,
        log_path: Union[str, Path],
        strain_threshold: float = 1.0e-4,
    ) -> Tuple[float, bool]:
        """
        Parses maximum residual gradient on frozen coordinates and flags geometric strain caveat (VR-02).
        """
        path = Path(log_path)
        content = path.read_text(encoding="utf-8", errors="replace")
        if not math.isfinite(strain_threshold) or strain_threshold <= 0:
            raise ValueError("Residual gradient threshold must be finite and positive.")
        max_g_pattern = re.compile(rf"MAX GRADIENT\s*(?::|=)?\s*({_NUMBER})", re.IGNORECASE)
        last_max_g = None
        for line in content.splitlines():
            m = max_g_pattern.search(line)
            if m:
                last_max_g = abs(_number(m.group(1)))
        if last_max_g is None or not math.isfinite(last_max_g):
            raise MissingDataError("Missing finite residual gradient evidence in output.")
        has_strain = last_max_g > strain_threshold
        return last_max_g, has_strain


OutputParser = QuantumParser

__all__ = [
    "QCSchemaProperties",
    "QCSchemaProvenance",
    "QCSchemaMolecule",
    "QuantumParser",
    "OutputParser",
]
