"""CoChem-TORQ Decoupled Trajectory Quench Broker & IPC Infrastructure.

Authoritative Standards:
- Tripartite Air-Gap Architecture: Strictly zero imports of cochem_base.
- QCSchema / AtomicResult standard serialization contracts.
- Thread-safe & process-safe active learning manifest updates via filelock.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, NoReturn, Optional, Tuple, Union

import numpy as np
from pydantic import BaseModel, Field
import filelock
from cochem.core.cochem_constants import ANGSTROM_TO_BOHR, HARTREE_TO_EV
from cochem.core.mendeleev_invariants import get_element


class QuenchMethodology(str, Enum):
    """Supported semiempirical quench methodologies for air-gapped workers. [M]"""
    GFN2_XTB = "gfn2-xtb"
    GFN_FF = "gfn-ff"


class QuenchRequest(BaseModel):
    """Validated Pydantic contract for trajectory quench dispatch. [M]"""
    trajectory_id: str = Field(..., description="Unique trajectory identifier")
    frame_index: int = Field(..., ge=0, description="Breach trajectory frame index")
    atomic_numbers: List[int] = Field(..., description="Atomic numbers of system atoms")
    geometry_angstrom: List[List[float]] = Field(..., description="Cartesian coordinates in Angstroms")
    nonconformity_score: float = Field(..., description="Calculated conformal nonconformity score")
    calibration_threshold: float = Field(..., description="Active calibration boundary (1 - alpha)")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of breach event"
    )
    methodology: QuenchMethodology = Field(
        default=QuenchMethodology.GFN2_XTB,
        description="Selected semiempirical relaxation engine"
    )

    def to_qcschema(self) -> Dict[str, Any]:
        """Serializes geometry into standardized QCSchema AtomicResult input structure. [D]"""
        # QCSchema is a shared interchange conversion. Native xTB dispatch below
        # supplies Angstrom XYZ and does not consume this Bohr representation.
        flat_bohr: List[float] = []
        for atom in self.geometry_angstrom:
            flat_bohr.extend([coord * ANGSTROM_TO_BOHR for coord in atom])

        return {
            "schema_name": "qcschema_input",
            "schema_version": 1,
            "molecule": {
                "geometry": flat_bohr,
                "atomic_numbers": self.atomic_numbers,
            },
            "driver": "gradient",
            "model": {
                "method": self.methodology.value,
                "basis": None,
            },
            "keywords": {
                "opt": True,
                "gfn_version": 2 if self.methodology == QuenchMethodology.GFN2_XTB else "ff",
            },
            "provenance": {
                "creator": "CoChem-TORQ",
                "version": "0.1.0",
                "routine": "quench_broker.dispatch_quench",
            },
        }


class QuenchResponse(BaseModel):
    """Validated Pydantic response contract for completed quench jobs. [M]"""
    trajectory_id: str
    frame_index: int
    quenched_geometry: List[List[float]]
    quenched_energy_hartree: float
    converged: bool
    walltime_ms: float
    methodology: str
    provenance_tag: str = "[M]"


class QuenchExecutionError(RuntimeError):
    """Rejected quench with retained process diagnostics, never a physical result."""

    def __init__(self, message: str, *, diagnostics_dir: Path,
                 command: List[str], returncode: Optional[int] = None) -> None:
        self.diagnostics_dir = diagnostics_dir
        self.command = tuple(command)
        self.returncode = returncode
        super().__init__(f"{message}; diagnostics retained in {diagnostics_dir}")


class BinaryNotFoundError(QuenchExecutionError):
    """The explicitly selected xTB binary could not be resolved."""

class IPCTrajectoryQuenchBroker:
    """Decoupled IPC Broker dispatching trajectory quenches to isolated workers. [M]"""

    def __init__(self, manifest_path: Optional[Union[str, Path]] = None) -> None:
        self.manifest_path = Path(manifest_path) if manifest_path else Path("active_learning_manifest.json")

    def append_to_manifest(self, request: QuenchRequest) -> None:
        """Thread-safe, process-safe append of outlier configuration to Active Learning manifest. [M]"""
        lock_path = self.manifest_path.with_suffix(".lock")
        with filelock.FileLock(str(lock_path), timeout=15.0):
            entries: List[Dict[str, Any]] = []
            if self.manifest_path.exists():
                try:
                    with open(self.manifest_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            entries = data
                except Exception:
                    entries = []

            entries.append(request.model_dump())
            with open(self.manifest_path, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2)

    def dispatch_quench(
        self,
        request: QuenchRequest,
        timeout: float = 30.0,
    ) -> QuenchResponse:
        """Run the requested native xTB screening quench or retain a typed failure.

        This legacy TORQ worker does not certify BASE execution authority or
        spectroscopic accuracy. It never substitutes a different calculator.
        """
        start_time = time.perf_counter()
        self.append_to_manifest(request)

        coords = np.array(request.geometry_angstrom, dtype=np.float64)
        if not request.atomic_numbers or coords.shape != (len(request.atomic_numbers), 3) or not np.isfinite(coords).all():
            raise ValueError("Quench requires a finite Cartesian triplet for each input atom")
        symbols = [get_element(number).symbol for number in request.atomic_numbers]
        diagnostics_root = self.manifest_path.parent / "quench_runs"
        diagnostics_root.mkdir(parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix="quench-", dir=diagnostics_root))
        configured = os.environ.get("XTB_CMD") or os.environ.get("COCHEM_XTB_BIN") or "xtb"
        xtb_bin = shutil.which(configured)
        arguments = ["--gfn", "2"] if request.methodology == QuenchMethodology.GFN2_XTB else ["--gfnff"]
        cmd = [xtb_bin or configured, "outlier.xyz", "--opt", *arguments]
        (directory / "request.json").write_text(request.model_dump_json(indent=2), encoding="utf-8")

        def reject(message: str, *, returncode: Optional[int] = None,
                   error_type: type[QuenchExecutionError] = QuenchExecutionError) -> NoReturn:
            (directory / "execution.json").write_text(json.dumps({
                "status": "rejected", "scope": "screening", "method": request.methodology.value,
                "command": cmd, "returncode": returncode, "reason": message,
            }, indent=2), encoding="utf-8")
            raise error_type(message, diagnostics_dir=directory, command=cmd, returncode=returncode)

        if xtb_bin is None:
            (directory / "stderr.log").write_text(f"Cannot resolve selected xTB binary: {configured}\n", encoding="utf-8")
            reject("Selected xTB executable was not found", error_type=BinaryNotFoundError)
        lines = [str(len(symbols)), f"Quench frame {request.frame_index}"]
        lines.extend(f"{symbol} " + " ".join(format(value, ".17g") for value in atom)
                     for symbol, atom in zip(symbols, coords, strict=True))
        (directory / "outlier.xyz").write_text("\n".join(lines) + "\n", encoding="utf-8")
        try:
            result = subprocess.run(cmd, cwd=directory, capture_output=True, text=True,
                                    encoding="utf-8", errors="replace", timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            for name, content in (("stdout.log", exc.stdout), ("stderr.log", exc.stderr)):
                text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else content or ""
                (directory / name).write_text(text, encoding="utf-8")
            reject(f"xTB quench exceeded timeout {timeout} seconds")
        except OSError as exc:
            (directory / "stderr.log").write_text(str(exc), encoding="utf-8")
            reject(f"Could not launch selected xTB executable: {exc}")
        (directory / "stdout.log").write_text(result.stdout, encoding="utf-8")
        (directory / "stderr.log").write_text(result.stderr, encoding="utf-8")
        if result.returncode != 0:
            reject("xTB process failed", returncode=result.returncode)
        if "normal termination of xtb" not in (result.stdout + result.stderr).lower():
            reject("xTB normal-termination evidence is missing", returncode=result.returncode)
        energies = re.findall(r"\|\s*TOTAL ENERGY\s+([^\s]+)\s+Eh\s*\|", result.stdout)
        try:
            energy = float(energies[-1].replace("D", "E").replace("d", "e"))
            if not math.isfinite(energy):
                raise ValueError("nonfinite energy")
        except (IndexError, ValueError):
            reject("xTB final finite energy in Hartree is missing", returncode=result.returncode)
        if request.methodology == QuenchMethodology.GFN2_XTB and not re.search(
                r"convergence criteria satisfied after \d+ iterations", result.stdout, re.I):
            reject("xTB SCC convergence evidence is missing", returncode=result.returncode)
        if not re.search(r"GEOMETRY OPTIMIZATION CONVERGED AFTER \d+ ITERATIONS", result.stdout):
            reject("xTB optimization convergence evidence is missing", returncode=result.returncode)
        try:
            opt_lines = (directory / "xtbopt.xyz").read_text(encoding="utf-8").splitlines()
            rows = [line.split() for line in opt_lines[2:] if line.strip()]
            if int(opt_lines[0]) != len(symbols) or [row[0] for row in rows] != symbols:
                raise ValueError("optimized atom identities/order differ from input")
            if any(len(row) != 4 for row in rows):
                raise ValueError("optimized geometry requires Cartesian triplets")
            new_coords = [[float(value) for value in row[1:]] for row in rows]
            if not np.isfinite(new_coords).all():
                raise ValueError("nonfinite optimized geometry")
        except (OSError, IndexError, ValueError) as exc:
            reject(f"xTB optimized geometry is invalid: {exc}", returncode=result.returncode)
        response = QuenchResponse(
            trajectory_id=request.trajectory_id, frame_index=request.frame_index,
            quenched_geometry=new_coords, quenched_energy_hartree=energy, converged=True,
            walltime_ms=(time.perf_counter() - start_time) * 1000.0,
            methodology=request.methodology.value,
        )
        (directory / "result.json").write_text(response.model_dump_json(indent=2), encoding="utf-8")
        (directory / "execution.json").write_text(json.dumps({
            "status": "accepted", "scope": "screening", "method": request.methodology.value,
            "command": cmd, "returncode": result.returncode,
        }, indent=2), encoding="utf-8")
        return response

