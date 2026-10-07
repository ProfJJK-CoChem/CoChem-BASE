"""Execute auditable Product B plane-wave PAW singlepoints with Quantum ESPRESSO.

This bounded adapter implements neutral, closed-shell PBE SCF calculations.
Numerical convergence is verified; empirical band-gap/lattice accuracy is not
inferred from the method name or from a successful SCF calculation.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
from typing import Any, Callable, Sequence
import uuid
import xml.etree.ElementTree as ET

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator, model_validator

from cochem.core.cochem_constants import BOHR_TO_ANGSTROM
from cochem_base.spectroscopy.isotopologue import get_nuclide_mass
from cochem_base.calc.periodic import (
    PeriodicStructureProvenance, periodic_structure_digest, validate_periodic_cell, validate_periodic_geometry,
)


class PAWPseudopotential(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: Path
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PeriodicCalculationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    cell_angstrom: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]
    pbc: tuple[StrictBool, StrictBool, StrictBool] = (True, True, True)
    pseudopotentials: dict[str, PAWPseudopotential]
    ecutwfc_ry: float = Field(default=45., gt=0., le=1000., allow_inf_nan=False)
    ecutrho_ry: float = Field(default=360., gt=0., le=10000., allow_inf_nan=False)
    kpoints: tuple[StrictInt, StrictInt, StrictInt] = (2, 2, 2)
    conv_thr_ry: float = Field(default=1e-8, gt=0., le=1e-6, allow_inf_nan=False)
    max_scf_steps: StrictInt = Field(default=100, ge=1, le=1000)
    structure_provenance: PeriodicStructureProvenance | None = None

    @field_validator("cell_angstrom")
    @classmethod
    def valid_cell(cls, value: Any) -> Any:
        validate_periodic_cell(value)
        return value

    @model_validator(mode="after")
    def valid_sampling(self) -> "PeriodicCalculationConfig":
        if not all(self.pbc):
            raise ValueError("This bulk PAW adapter requires three periodic boundary conditions")
        if any(n < 1 or n > 32 for n in self.kpoints) or math.prod(self.kpoints) > 4096:
            raise ValueError("Reciprocal mesh must have 1--32 points per axis and at most 4096 points")
        if self.ecutrho_ry < 4 * self.ecutwfc_ry:
            raise ValueError("PAW density cutoff must be at least four times the wavefunction cutoff")
        return self


def _sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _validate_inputs(elements: Sequence[str], coordinates: Any, periodic: PeriodicCalculationConfig,
                     charge: int, multiplicity: int) -> tuple[np.ndarray, dict[str, dict[str, Any]]]:
    if isinstance(charge, bool) or charge != 0 or isinstance(multiplicity, bool) or multiplicity != 1:
        raise ValueError("The periodic adapter currently requires a neutral closed-shell singlet")
    xyz = validate_periodic_geometry(elements, coordinates, periodic.cell_angstrom)
    if set(elements) != set(periodic.pseudopotentials):
        raise ValueError("One authenticated PAW pseudopotential is required for each atomic species")
    if periodic.structure_provenance is not None and periodic.structure_provenance.structure_sha256 != periodic_structure_digest(elements, xyz, periodic.cell_angstrom, periodic.pbc):
        raise ValueError("Periodic geometry/cell contradicts its ingested source provenance")
    metadata = {}
    for symbol, pseudo in periodic.pseudopotentials.items():
        get_nuclide_mass(symbol)
        source = pseudo.path.expanduser().resolve(strict=True)
        if source.stat().st_size > 32 * 1024 * 1024 or _sha256(source) != pseudo.sha256:
            raise ValueError(f"PAW pseudopotential digest/size validation failed for {symbol}")
        text = source.read_text(encoding="utf-8")
        # UPF 2 PP_INFO may contain unescaped Fortran '&'; parse its standalone
        # structured header, never reinterpret descriptive text as PAW evidence.
        headers = re.findall(r"<PP_HEADER\b[^>]*?/>", text, re.DOTALL)
        if len(headers) != 1 or not re.search(r"<PP_PAW\b", text):
            raise ValueError("A UPF2 PAW header and augmentation data are required")
        header = ET.fromstring(headers[0]).attrib
        if header.get("element", "").strip() != symbol or header.get("pseudo_type", "").strip().upper() != "PAW":
            raise ValueError("Pseudopotential element or PAW type contradicts the calculation")
        if header.get("is_paw", "").strip().upper() not in {"T", "TRUE", ".TRUE."}:
            raise ValueError("PAW type requires an explicitly consistent is_paw header flag")
        if header.get("has_so", "").strip().upper() not in {"F", "FALSE", ".FALSE."}:
            raise ValueError("Spin-orbit PAW requires a separately validated spinor adapter")
        functional = " ".join(header.get("functional", "").upper().split())
        if functional not in {"PBE", "SLA PW PBX PBC"}:
            raise ValueError("This PBE adapter requires a PBE PAW pseudopotential")
        valence = float(header["z_valence"])
        if not math.isfinite(valence) or valence <= 0 or not valence.is_integer():
            raise ValueError("PAW valence electron count must be a finite positive integer")
        for key, requested in (("wfc_cutoff", periodic.ecutwfc_ry), ("rho_cutoff", periodic.ecutrho_ry)):
            minimum = float(header.get(key, 0.))
            if not math.isfinite(minimum) or minimum < 0 or requested < minimum:
                raise ValueError(f"Requested {key} is below the pseudopotential recommendation")
        metadata[symbol] = {"source": str(source), "sha256": pseudo.sha256,
                            "filename": f"{symbol}.{pseudo.sha256[:16]}.UPF", "valence_electrons": int(valence),
                            "functional": functional, "pseudo_type": "PAW"}
    if sum(metadata[s]["valence_electrons"] for s in elements) % 2:
        raise ValueError("A closed-shell cell requires an even number of valence electrons")
    return xyz, metadata


def write_periodic_input(elements: Sequence[str], coordinates_angstrom: Any, periodic: PeriodicCalculationConfig,
                         *, directory: str | Path, charge: int = 0, multiplicity: int = 1) -> Path:
    """Write an executable QE input deck using only authenticated local PAW files."""
    from cochem.core.context import assert_writable_path

    xyz, pseudos = _validate_inputs(elements, coordinates_angstrom, periodic, charge, multiplicity)
    directory = Path(directory).expanduser().resolve()
    assert_writable_path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    pseudo_directory = directory / "pseudo"
    pseudo_directory.mkdir(exist_ok=True)
    for pseudo in pseudos.values():
        data = Path(pseudo["source"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != pseudo["sha256"]:
            raise ValueError("PAW pseudopotential changed while preparing execution")
        (pseudo_directory / pseudo["filename"]).write_bytes(data)
    lines = ["&CONTROL", " calculation='scf', prefix='cochem', pseudo_dir='./pseudo', outdir='./tmp',",
             " tprnfor=.true., tstress=.true., restart_mode='from_scratch'", "/", "&SYSTEM",
             f" ibrav=0, nat={len(elements)}, ntyp={len(pseudos)},",
             f" ecutwfc={periodic.ecutwfc_ry:.16g}, ecutrho={periodic.ecutrho_ry:.16g},",
             " occupations='fixed', nspin=1, input_dft='PBE'", "/", "&ELECTRONS",
             f" conv_thr={periodic.conv_thr_ry:.16g}, electron_maxstep={periodic.max_scf_steps}, mixing_beta=0.3",
             "/", "ATOMIC_SPECIES"]
    lines += [f"{symbol} {get_nuclide_mass(symbol):.14g} {pseudo['filename']}" for symbol, pseudo in pseudos.items()]
    lines += ["CELL_PARAMETERS angstrom"] + [" ".join(f"{v:.16g}" for v in row) for row in periodic.cell_angstrom]
    lines += ["ATOMIC_POSITIONS angstrom"] + [f"{s} " + " ".join(f"{v:.16g}" for v in row) for s, row in zip(elements, xyz)]
    lines += ["K_POINTS automatic", " ".join(map(str, periodic.kpoints)) + " 0 0 0"]
    path = directory / "qe.in"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (directory / "periodic-input.json").write_text(json.dumps({
        "elements": list(elements), "coordinates_angstrom": xyz.tolist(),
        "periodic": periodic.model_dump(mode="json"), "pseudopotentials": pseudos,
        "input_sha256": _sha256(path), "charge": charge, "multiplicity": multiplicity,
    }, indent=2), encoding="utf-8")
    return path


def _accept_result(directory: Path, stdout: str, elements: Sequence[str], coordinates: Any,
                   periodic: PeriodicCalculationConfig) -> dict[str, Any]:
    if "JOB DONE." not in stdout or not re.search(r"convergence has been achieved", stdout):
        raise RuntimeError("QE did not report both completed execution and converged SCF")
    if re.search(r"convergence NOT achieved|Error in routine", stdout, re.IGNORECASE):
        raise RuntimeError("QE reported an explicit calculation failure")
    xml = directory / "tmp/cochem.save/data-file-schema.xml"
    root = ET.parse(xml).getroot()
    output = root.find("output")
    if output is None or output.findtext("convergence_info/scf_conv/convergence_achieved") != "true":
        raise RuntimeError("QE structured SCF convergence evidence is absent")
    if root.findtext("status") != "0" or output.findtext("algorithmic_info/paw") != "true":
        raise RuntimeError("QE structured output does not certify a successful PAW calculation")
    if output.findtext("dft/functional", "").strip().upper() != "PBE" or output.findtext("magnetization/lsda", "false") != "false":
        raise RuntimeError("QE output method/spin treatment contradicts the PBE singlet request")
    for field, expected in (("ecutwfc", periodic.ecutwfc_ry), ("ecutrho", periodic.ecutrho_ry)):
        actual = float(output.findtext(f"basis_set/{field}")) * 2.
        if not math.isclose(actual, expected, rel_tol=1e-10):
            raise RuntimeError("QE structured plane-wave cutoff contradicts the requested basis")
    structure = output.find("atomic_structure")
    atoms = structure.findall("atomic_positions/atom") if structure is not None else []
    if [atom.attrib.get("name") for atom in atoms] != list(elements):
        raise RuntimeError("QE output atom identities/order contradict the submitted periodic structure")
    measured_xyz = np.array([[float(v) for v in atom.text.split()] for atom in atoms]) * BOHR_TO_ANGSTROM
    measured_cell = np.array([[float(v) for v in row.text.split()] for row in structure.findall("cell/*")]) * BOHR_TO_ANGSTROM
    if not np.allclose(measured_xyz, coordinates, atol=1e-7, rtol=0.) or not np.allclose(measured_cell, periodic.cell_angstrom, atol=1e-7, rtol=0.):
        raise RuntimeError("QE output geometry/cell contradict the requested singlepoint")
    energy = float(output.findtext("total_energy/etot"))
    energy_text = re.findall(r"!\s+total energy\s*=\s*([-+0-9.EeDd]+)\s+Ry", stdout)
    if not math.isfinite(energy) or not energy_text or not math.isclose(float(energy_text[-1].replace("D", "E")) / 2., energy, abs_tol=1e-7, rel_tol=0.):
        raise RuntimeError("QE structured energy and final stdout energy disagree")
    # QE schema energies and forces use Hartree atomic units, while stdout uses Ry.
    forces = np.array([float(v) for v in (output.findtext("forces") or "").split()])
    if forces.size != len(elements) * 3 or not np.isfinite(forces).all():
        raise RuntimeError("QE failed to publish finite per-atom forces")
    return {"elements": list(elements), "coordinates_angstrom": measured_xyz.tolist(),
            "cell_angstrom": measured_cell.tolist(), "pbc": [True, True, True],
            "energy_hartree": energy, "gradients_hartree_per_bohr": (-forces.reshape(-1, 3)).tolist(),
            "scf_converged": True, "xml_sha256": _sha256(xml), "stdout_sha256": _sha256(directory / "qe.out")}


def execute_periodic_singlepoint(elements: Sequence[str], coordinates_angstrom: Any, *,
        periodic: PeriodicCalculationConfig, workdir: str | Path, registry_path: str | Path | None = None,
        cores: int = 1, timeout_seconds: float = 180., charge: int = 0, multiplicity: int = 1,
        job_id: str | None = None, cancellation_event: Any = None,
        on_event: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
    """Run native pw.x under Golden Registry authority and publish measured results."""
    from cochem_base.core_engine.execution_authority import authorize_engine_execution
    from cochem_base.core_engine.cochem_core_subprocess_broker import safe_subprocess_run
    from cochem_base.core_engine.scientific_telemetry import append_scientific_result

    if isinstance(timeout_seconds, bool) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("QE timeout must be finite and positive")
    job_id = job_id or f"periodic_{uuid.uuid4().hex}"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", job_id):
        raise ValueError("Periodic job ID must be a safe component")
    authority = authorize_engine_execution("qe", registry_path=registry_path, cores=cores)
    if not authority.cpu_affinity:
        raise RuntimeError("Periodic execution requires freshly audited CPU affinity")
    directory = Path(workdir).expanduser().resolve()
    if directory.exists() and any(directory.iterdir()):
        raise ValueError("QE execution requires an empty per-job directory to exclude stale output")
    deck = write_periodic_input(elements, coordinates_angstrom, periodic, directory=directory,
                                charge=charge, multiplicity=multiplicity)
    provenance = json.loads((directory / "periodic-input.json").read_text(encoding="utf-8"))
    provenance.update(engine="qe", executable=authority.executable, binary_sha256=authority.binary_sha256,
        registry_path=authority.registry_path, cpu_affinity=list(authority.cpu_affinity), cores=authority.cores,
        memory_budget_mb=authority.total_memory_mb, method="PBE", basis="plane_wave", pseudopotential="PAW",
        accuracy_validated=False, product_class="B", job_id=job_id)
    command = authority.command(["-in", deck.name])
    provenance["command"] = command
    environment = dict(os.environ, OMP_NUM_THREADS=str(authority.cores), OPENBLAS_NUM_THREADS="1",
                       MKL_NUM_THREADS="1", OMP_PROC_BIND="true", OMP_PLACES="cores")
    from cochem_base.core_engine.engine_environment import engine_runtime_environment
    environment = engine_runtime_environment("qe", environment, executable=authority.executable)
    start = time.monotonic()
    if on_event:
        on_event({"stage": "qe_scf", "status": "RUNNING", "job_id": job_id})
    try:
        completed = safe_subprocess_run(command, cwd=directory, env=environment, timeout=timeout_seconds,
            cpu_affinity=list(authority.cpu_affinity), check=False, capture_output=True, text=True,
            required_disk_gb=0.1, load_full_stdout=True, cancellation_event=cancellation_event)
        (directory / "qe.out").write_text(completed.stdout or "", encoding="utf-8")
        (directory / "qe.err").write_text(completed.stderr or "", encoding="utf-8")
        provenance["returncode"] = completed.returncode
        if completed.returncode != 0:
            raise RuntimeError(f"QE exited {completed.returncode}; retained diagnostics: {directory}")
        result = _accept_result(directory, completed.stdout or "", elements, coordinates_angstrom, periodic)
        banner = re.search(r"Program PWSCF\s+v\.([^\s]+)", completed.stdout or "")
        if banner is None:
            raise RuntimeError("QE executable did not identify its PWSCF version")
        provenance["engine_version"] = banner.group(1)
        provenance["elapsed_seconds"] = time.monotonic() - start
        provenance["status"] = "SCF_VERIFIED"
        result["metadata"] = provenance
        archive = append_scientific_result(job_id, elements, result["coordinates_angstrom"], result["energy_hartree"],
            gradients=result["gradients_hartree_per_bohr"], metadata={**provenance, "cell_angstrom": result["cell_angstrom"], "pbc": result["pbc"]})
        result.update(status="SCF_VERIFIED", job_id=job_id, archive_path=str(archive), workdir=str(directory))
        (directory / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
        if on_event:
            on_event({"stage": "qe_scf", "status": "SCF_VERIFIED", "job_id": job_id})
        return result
    except Exception as exc:
        provenance.update(status="FAILED", error_type=type(exc).__name__, error=str(exc), elapsed_seconds=time.monotonic() - start)
        raise
    finally:
        (directory / "execution.json").write_text(json.dumps(provenance, indent=2, allow_nan=False), encoding="utf-8")
