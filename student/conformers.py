"""Generalized student workflow: XYZ -> CREST 3.0.2 -> AIMNet2 / MACE-OFF24 -> CPU PySCF -> v2 Handoff.

Supports all 11 CoChem v2 elements (H, B, C, N, O, F, Si, P, S, Cl, Br),
charges in {-2..+2}, multiplicities in {1..3}, 1..64 atoms, and up to 256 frames.

Scientific routing invariants:
- CREST 3.0.2 invokes external xTB via `--gfn2 --legacy --xnam <xtb> --nocross --chrg <Q> --uhf <mult-1>`.
- Neutral-only MACE-OFF24 is strictly forbidden for charged (Q != 0), open-shell
  (multiplicity != 1), or heteroatom (F/S/Cl/Br/P/Si/B) systems; those route
  exclusively to charge-aware AIMNet2.
- CPU PySCF supports RHF/UHF, B3LYP-D3BJ, and (DF-)wB97X-D3 with STO-3G,
  def2-SVP, def2-TZVP, or def2-TZVPP, optional PCM/ddCOSMO solvation, and
  optional harmonic frequency calculation (`hessian_calculated`, `n_imaginary_modes`).
- Emits a sealed, self-verified `cochem.student-handoff/2` ZIP + `.sha256` sidecar.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as md
import json
import math
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Mapping, Sequence
import urllib.request

try:
    from .handoff import (
        DEFAULT_COLLABORATOR_INSTITUTION,
        V2_ALLOWED_CHARGES,
        V2_ALLOWED_COURSE_IDS,
        V2_ALLOWED_ELEMENTS,
        V2_ALLOWED_MULTIPLICITIES,
        V2_ALLOWED_SOLVATIONS,
        V2_ALLOWED_TARGET_CONTINUATIONS,
        V2_ALLOWED_WORKFLOW_TYPES,
        V2_MAX_FRAMES,
        frames,
        get_allowed_course_ids,
        read_input,
        seal,
    )
    from .starter_inputs import is_known_starter_input, resolve_or_materialize_input
except ImportError:
    from handoff import (  # type: ignore[no-redef]
        DEFAULT_COLLABORATOR_INSTITUTION,
        V2_ALLOWED_CHARGES,
        V2_ALLOWED_COURSE_IDS,
        V2_ALLOWED_ELEMENTS,
        V2_ALLOWED_MULTIPLICITIES,
        V2_ALLOWED_SOLVATIONS,
        V2_ALLOWED_TARGET_CONTINUATIONS,
        V2_ALLOWED_WORKFLOW_TYPES,
        V2_MAX_FRAMES,
        frames,
        get_allowed_course_ids,
        read_input,
        seal,
    )
    from starter_inputs import is_known_starter_input, resolve_or_materialize_input  # type: ignore[no-redef]

ROOT = Path(__file__).resolve().parents[1]

MACE_MODEL_URL = (
    "https://raw.githubusercontent.com/ACEsuit/mace-off/"
    "91a78c5a9c300d1104700d9352c8bfe449227737/mace_off24/MACE-OFF24_medium.model"
)
MACE_MODEL_SHA = "e5ccf5837f685899811a68754e7c994393bfd1a81720393b03c643b46c70bc69"

MACE_NEUTRAL_ONLY_ELEMENTS: frozenset[str] = frozenset({"H", "C", "N", "O"})
AIMNET2_REQUIRED_ELEMENTS: frozenset[str] = frozenset({"B", "F", "Si", "P", "S", "Cl", "Br"})

SUPPORTED_METHODS: dict[str, dict[str, Any]] = {
    "rhf": {"label": "RHF", "kind": "hf", "xc": None, "dispersion": None},
    "uhf": {"label": "UHF", "kind": "hf", "xc": None, "dispersion": None},
    "b3lyp-d3bj": {"label": "B3LYP-D3BJ", "kind": "dft", "xc": "b3lypg", "dispersion": "d3bj"},
    "wb97x-d3": {"label": "wB97X-D3", "kind": "dft", "xc": "wb97x", "dispersion": "d3zero"},
    "df-wb97x-d3": {"label": "DF-wB97X-D3", "kind": "dft", "xc": "wb97x", "dispersion": "d3zero"},
}

SUPPORTED_BASIS_SETS: dict[str, str] = {
    "sto-3g": "STO-3G",
    "def2-svp": "def2-SVP",
    "def2-tzvp": "def2-TZVP",
    "def2-tzvpp": "def2-TZVPP",
}

SOLVENT_DIELECTRICS: dict[str, float] = {
    "water": 78.3553,
    "acetonitrile": 35.688,
    "dmso": 46.826,
    "methanol": 32.613,
    "ethanol": 24.852,
    "dichloromethane": 8.93,
    "chloroform": 4.7113,
    "thf": 7.4257,
    "toluene": 2.3741,
}

HARTREE_TO_EV = 27.211386245988
BOHR_TO_ANGSTROM = 0.529177210903


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def requires_charge_aware_aimnet2(
    elements: Sequence[str],
    charge: int = 0,
    multiplicity: int = 1,
) -> bool:
    """Return True when neutral-only MACE-OFF24 is scientifically invalid and AIMNet2 is mandatory."""
    if not isinstance(charge, int) or isinstance(charge, bool) or charge not in V2_ALLOWED_CHARGES:
        raise ValueError(f"Unsupported charge {charge!r}; expected one of {V2_ALLOWED_CHARGES}")
    if (
        not isinstance(multiplicity, int)
        or isinstance(multiplicity, bool)
        or multiplicity not in V2_ALLOWED_MULTIPLICITIES
    ):
        raise ValueError(f"Unsupported multiplicity {multiplicity!r}; expected one of {V2_ALLOWED_MULTIPLICITIES}")
    elem_set = set(elements)
    disallowed = elem_set - set(V2_ALLOWED_ELEMENTS)
    if disallowed:
        raise ValueError(f"Unsupported element(s) {sorted(disallowed)}; allowed: {sorted(V2_ALLOWED_ELEMENTS)}")
    if charge != 0 or multiplicity != 1:
        return True
    if elem_set & AIMNET2_REQUIRED_ELEMENTS:
        return True
    return not elem_set.issubset(MACE_NEUTRAL_ONLY_ELEMENTS)


def select_mlff_backend(
    elements: Sequence[str],
    charge: int = 0,
    multiplicity: int = 1,
    requested: str = "auto",
) -> str:
    """Resolve and validate the MLFF scoring engine (`aimnet2` or `mace`).

    Strictly rejects `requested="mace"` for charged (Q != 0), open-shell
    (multiplicity != 1), or F/S/Cl/Br/P/Si/B molecules, routing them exclusively
    to charge-aware `aimnet2`.
    """
    choice = (requested or "auto").strip().lower()
    if choice not in {"auto", "aimnet2", "mace"}:
        raise ValueError(f"Unsupported MLFF backend {requested!r}; expected 'auto', 'aimnet2', or 'mace'")
    needs_aimnet2 = requires_charge_aware_aimnet2(elements, charge=charge, multiplicity=multiplicity)
    if needs_aimnet2:
        if choice == "mace":
            raise ValueError(
                "Neutral-only MACE-OFF24 is forbidden for charged (Q != 0), open-shell, "
                "or heteroatom (F/S/Cl/Br/P/Si/B) species; use charge-aware AIMNet2."
            )
        return "aimnet2"
    if choice == "mace":
        return "mace"
    return "aimnet2"


def normalize_method_and_basis(method: str, basis: str) -> tuple[dict[str, Any], str]:
    method_key = (method or "").strip().lower()
    if method_key not in SUPPORTED_METHODS:
        raise ValueError(
            f"Unsupported PySCF method {method!r}; supported: {[v['label'] for v in SUPPORTED_METHODS.values()]}"
        )
    basis_key = (basis or "").strip().lower()
    if basis_key not in SUPPORTED_BASIS_SETS:
        raise ValueError(f"Unsupported basis set {basis!r}; supported: {list(SUPPORTED_BASIS_SETS.values())}")
    return SUPPORTED_METHODS[method_key], SUPPORTED_BASIS_SETS[basis_key]


def build_crest_argv(
    crest_exe: str | Path,
    xtb_exe: str | Path,
    *,
    input_xyz: str = "input.xyz",
    charge: int = 0,
    multiplicity: int = 1,
    cores: int = 1,
    nci: bool = False,
    quick: bool = True,
) -> list[str]:
    """Construct the CREST 3.0.2 command preserving the verified `--legacy --xnam --nocross` fix."""
    if charge not in V2_ALLOWED_CHARGES:
        raise ValueError(f"Unsupported charge {charge!r}")
    if multiplicity not in V2_ALLOWED_MULTIPLICITIES:
        raise ValueError(f"Unsupported multiplicity {multiplicity!r}")
    uhf = multiplicity - 1
    argv = [
        str(crest_exe),
        input_xyz,
        "--gfn2",
        "--legacy",
        "--xnam",
        str(xtb_exe),
    ]
    if nci:
        argv.append("--nci")
    if quick:
        argv.append("--quick")
    argv.extend(
        [
            "--nocross",
            "--chrg",
            str(charge),
            "--uhf",
            str(uhf),
            "--T",
            str(max(1, int(cores))),
        ]
    )
    return argv


def input_file(filename: str, *, materialize_dir: Path | None = None) -> Path:
    """Resolve an input XYZ file from disk, `examples/student_inputs/`, or built-in starter inputs."""
    candidate = Path(filename)
    if candidate.is_file() and not candidate.is_symlink() and candidate.suffix.lower() == ".xyz":
        return candidate.resolve()
    if is_known_starter_input(filename):
        return resolve_or_materialize_input(filename, materialize_dir=materialize_dir)
    if not re.fullmatch(r"[a-zA-Z0-9._-]{1,96}\.xyz", filename):
        raise ValueError("Select a valid .xyz filename from examples/student_inputs or an existing .xyz file path")
    source = ROOT / "examples" / "student_inputs" / filename
    if source.is_symlink() or not source.is_file() or source.resolve().parent != (ROOT / "examples" / "student_inputs").resolve():
        raise ValueError("XYZ must be an ordinary file in examples/student_inputs")
    return source


def resolve_xtb_crest_binaries(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Resolve `xtb` and `crest` executables without requiring `COCHEM_FREE_ROOT`.

    Priority order:
      1. Explicit `COCHEM_XTB_BIN` / `COCHEM_CREST_BIN` environment variables.
      2. `COCHEM_FREE_ROOT` silo binaries (when set).
      3. `shutil.which("xtb")` / `shutil.which("crest")` on `PATH`.
    """
    env_map = dict(os.environ if env is None else env)
    free_root_raw = str(env_map.get("COCHEM_FREE_ROOT") or "").strip()
    free_root = Path(free_root_raw) if free_root_raw else None

    def _pick_binary(env_var: str, free_rel: str, cmd_name: str) -> str:
        explicit = str(env_map.get(env_var) or "").strip()
        if explicit:
            explicit_path = Path(explicit)
            if explicit_path.is_file():
                return str(explicit_path)
            raise RuntimeError(f"{env_var} points to missing executable: {explicit}")
        if free_root is not None:
            candidate = free_root / free_rel
            if candidate.is_file():
                return str(candidate)
        found = shutil.which(cmd_name, path=env_map.get("PATH"))
        if found:
            return found
        raise RuntimeError(
            f"Unable to locate `{cmd_name}` executable. Set {env_var}, COCHEM_FREE_ROOT, "
            f"or activate the WSL2 environment so `{cmd_name}` is on PATH."
        )

    xtb_bin = _pick_binary("COCHEM_XTB_BIN", "xtb/xtb-dist/bin/xtb", "xtb")
    crest_bin = _pick_binary("COCHEM_CREST_BIN", "crest/crest/crest", "crest")

    sub_env = dict(env_map)
    path_entries = [str(Path(xtb_bin).parent), str(Path(crest_bin).parent)]
    existing_path = sub_env.get("PATH", "")
    prefix_parts = [p for p in path_entries if p and p not in existing_path.split(os.pathsep)]
    if prefix_parts:
        sub_env["PATH"] = os.pathsep.join(prefix_parts + ([existing_path] if existing_path else []))

    if free_root is not None:
        xtb_share = free_root / "xtb/xtb-dist/share/xtb"
        if xtb_share.is_dir():
            sub_env["XTBPATH"] = str(xtb_share)

    engines_json_path: Path | None = None
    if free_root is not None and (free_root / "engines.json").is_file():
        engines_json_path = free_root / "engines.json"

    return {
        "xtb": xtb_bin,
        "crest": crest_bin,
        "env": sub_env,
        "engines_json_path": engines_json_path,
        "free_root": str(free_root) if free_root is not None else None,
    }


def resolve_aimnet_python(env: Mapping[str, str] | None = None) -> str | None:
    """Resolve an external Python interpreter hosting `aimnet` via `$COCHEM_AIMNET_PYTHON`."""
    env_map = os.environ if env is None else env
    candidates: list[str] = []
    for var in ("COCHEM_AIMNET_PYTHON", "COCHEM_AIMNET_SILO_PYTHON"):
        raw = str(env_map.get(var) or "").strip()
        if raw:
            candidates.append(raw)
    for cand in candidates:
        p = Path(cand)
        if p.is_file():
            return str(p)
    return None


_AIMNET2_SUBPROCESS_SCRIPT = r"""
import json, math, sys
from pathlib import Path
import numpy as np

HARTREE_TO_EV = 27.211386245988
BOHR_TO_ANGSTROM = 0.529177210903
Z_MAP = {"H": 1, "B": 5, "C": 6, "N": 7, "O": 8, "F": 9, "Si": 14, "P": 15, "S": 16, "Cl": 17, "Br": 35}

req = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
out_path = Path(sys.argv[2])
charge = int(req["charge"])
mult = int(req["multiplicity"])
model_name = str(req.get("model_name", "aimnet2"))
frames_in = req["frames"]

results = []
try:
    from ase import Atoms
    from aimnet.calculators import AIMNet2ASE

    calc = AIMNet2ASE(model_name, charge=charge, mult=mult)
    for item in frames_in:
        symbols = list(item["symbols"])
        coords = list(item["coords"])
        atoms = Atoms(symbols, positions=coords)
        atoms.info["charge"] = charge
        atoms.info["spin"] = mult
        atoms.calc = calc
        e_ev = float(atoms.get_potential_energy())
        forces_ev_ang = np.asarray(atoms.get_forces(), dtype=float)
        if not math.isfinite(e_ev) or forces_ev_ang.shape != (len(symbols), 3) or not np.isfinite(forces_ev_ang).all():
            raise RuntimeError("AIMNet2 returned non-finite energy or forces")
        results.append({
            "status": "SUCCESS",
            "backend": "aimnet2",
            "model": model_name,
            "charge": charge,
            "multiplicity": mult,
            "energy_hartree": e_ev / HARTREE_TO_EV,
            "gradient_hartree_per_bohr": (-forces_ev_ang * BOHR_TO_ANGSTROM / HARTREE_TO_EV).tolist(),
        })
except ImportError:
    from aimnet.calculators import AIMNet2Calculator

    calc = AIMNet2Calculator(model_name)
    for item in frames_in:
        symbols = list(item["symbols"])
        coords = np.asarray(item["coords"], dtype=np.float64)
        numbers = np.asarray([Z_MAP[s] for s in symbols], dtype=np.int64)
        out = calc({"coord": coords, "numbers": numbers, "charge": float(charge), "mult": float(mult)}, forces=True)
        e_ev = float(np.asarray(out["energy"]).reshape(-1)[0])
        forces_ev_ang = np.asarray(out["forces"], dtype=float).reshape(len(symbols), 3)
        if not math.isfinite(e_ev) or not np.isfinite(forces_ev_ang).all():
            raise RuntimeError("AIMNet2 returned non-finite energy or forces")
        results.append({
            "status": "SUCCESS",
            "backend": "aimnet2",
            "model": model_name,
            "charge": charge,
            "multiplicity": mult,
            "energy_hartree": e_ev / HARTREE_TO_EV,
            "gradient_hartree_per_bohr": (-forces_ev_ang * BOHR_TO_ANGSTROM / HARTREE_TO_EV).tolist(),
        })

out_path.write_text(json.dumps({"results": results}, indent=2, allow_nan=False) + "\n", encoding="utf-8")
"""


def _evaluate_aimnet2_via_subprocess(
    frames_in: Sequence[Mapping[str, Any]],
    *,
    charge: int,
    multiplicity: int,
    model_name: str = "aimnet2",
    aimnet_python: str,
    timeout: int = 600,
) -> list[dict[str, Any]]:
    """Run AIMNet2 evaluation in an isolated `$COCHEM_AIMNET_PYTHON` interpreter."""
    with tempfile.TemporaryDirectory(prefix="cochem_aimnet2_") as tmp_dir:
        tmp = Path(tmp_dir)
        in_json = tmp / "request.json"
        out_json = tmp / "response.json"
        in_json.write_text(
            json.dumps(
                {
                    "charge": int(charge),
                    "multiplicity": int(multiplicity),
                    "model_name": model_name,
                    "frames": [
                        {"symbols": list(f["symbols"]), "coords": [list(row) for row in f["coords"]]}
                        for f in frames_in
                    ],
                },
                allow_nan=False,
            ),
            encoding="utf-8",
        )
        proc = subprocess.run(
            [aimnet_python, "-B", "-c", _AIMNET2_SUBPROCESS_SCRIPT, str(in_json), str(out_json)],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if proc.returncode != 0 or not out_json.is_file():
            detail = (proc.stderr or proc.stdout).strip()
            raise RuntimeError(
                f"AIMNet2 subprocess ({aimnet_python}) failed with exit code {proc.returncode}: {detail}"
            )
        payload = json.loads(out_json.read_text(encoding="utf-8"))
        results = payload.get("results")
        if not isinstance(results, list) or len(results) != len(frames_in):
            raise RuntimeError("AIMNet2 subprocess returned unexpected result count")
        for rec in results:
            rec["interpreter"] = aimnet_python
        return results


def _evaluate_aimnet2_frames(
    frames_in: Sequence[Mapping[str, Any]],
    *,
    charge: int,
    multiplicity: int,
    model_name: str = "aimnet2",
) -> list[dict[str, Any]]:
    """Evaluate one or more geometries using in-process AIMNet2 or `$COCHEM_AIMNET_PYTHON` fallback."""
    try:
        import numpy as np
        from ase import Atoms
        from aimnet.calculators import AIMNet2ASE  # type: ignore[import-not-found]
    except ImportError as exc:
        aimnet_py = resolve_aimnet_python()
        if aimnet_py is not None:
            return _evaluate_aimnet2_via_subprocess(
                frames_in,
                charge=charge,
                multiplicity=multiplicity,
                model_name=model_name,
                aimnet_python=aimnet_py,
            )
        raise RuntimeError(
            "Charge-aware AIMNet2 package (`aimnet`) is required for this system but is not installed "
            "in the current interpreter and COCHEM_AIMNET_PYTHON is not set"
        ) from exc

    calc = AIMNet2ASE(model_name, charge=int(charge), mult=int(multiplicity))
    out: list[dict[str, Any]] = []
    for item in frames_in:
        symbols = list(item["symbols"])
        coords = list(item["coords"])
        atoms = Atoms(symbols, positions=coords)
        atoms.info["charge"] = int(charge)
        atoms.info["spin"] = int(multiplicity)
        atoms.calc = calc
        energy_ev = float(atoms.get_potential_energy())
        forces_ev_ang = np.asarray(atoms.get_forces(), dtype=float)
        if not math.isfinite(energy_ev) or forces_ev_ang.shape != (len(symbols), 3) or not np.isfinite(forces_ev_ang).all():
            raise RuntimeError("AIMNet2 returned non-finite energy or forces")
        energy_hartree = energy_ev / HARTREE_TO_EV
        gradient_eh_bohr = (-forces_ev_ang * BOHR_TO_ANGSTROM / HARTREE_TO_EV).tolist()
        out.append(
            {
                "status": "SUCCESS",
                "backend": "aimnet2",
                "model": model_name,
                "charge": int(charge),
                "multiplicity": int(multiplicity),
                "energy_hartree": energy_hartree,
                "gradient_hartree_per_bohr": gradient_eh_bohr,
            }
        )
    return out


def _evaluate_aimnet2_frame(
    symbols: Sequence[str],
    coords: Sequence[Sequence[float]],
    *,
    charge: int,
    multiplicity: int,
    model_name: str = "aimnet2",
) -> dict[str, Any]:
    """Evaluate single-point energy & gradient using charge-aware AIMNet2 on CPU."""
    return _evaluate_aimnet2_frames(
        [{"symbols": list(symbols), "coords": [list(row) for row in coords]}],
        charge=charge,
        multiplicity=multiplicity,
        model_name=model_name,
    )[0]


def _download_verified_mace_model(work: Path) -> Path:
    model = work / "MACE-OFF24_medium.model"
    if not model.is_file():
        with urllib.request.urlopen(MACE_MODEL_URL, timeout=90) as src, model.open("wb") as dst:
            shutil.copyfileobj(src, dst)
    with model.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != MACE_MODEL_SHA:
            raise ValueError("MACE-OFF24 checkpoint SHA-256 mismatch")
    return model


def _apply_solvation(mf: Any, solvation: str, solvent_name: str | None) -> Any:
    if solvation == "gas":
        return mf
    eps_key = (solvent_name or "water").strip().lower()
    if eps_key not in SOLVENT_DIELECTRICS:
        raise ValueError(
            f"Unsupported solvent_name {solvent_name!r}; supported: {sorted(SOLVENT_DIELECTRICS)}"
        )
    eps = SOLVENT_DIELECTRICS[eps_key]
    if solvation == "pcm":
        mf = mf.PCM()
        mf.with_solvent.method = "IEF-PCM"
        mf.with_solvent.eps = eps
        return mf
    if solvation == "ddcosmo":
        mf = mf.DDCOSMO()
        mf.with_solvent.eps = eps
        return mf
    raise ValueError(f"Unsupported solvation {solvation!r}")


def _build_pyscf_mf(
    mol: Any,
    method_spec: dict[str, Any],
    *,
    solvation: str,
    solvent_name: str | None,
) -> Any:
    from pyscf import dft, scf

    unrestricted = mol.spin != 0 or method_spec["label"] == "UHF"
    if method_spec["kind"] == "hf":
        mf = scf.UHF(mol) if unrestricted else scf.RHF(mol)
    else:
        mf = (dft.UKS(mol) if unrestricted else dft.RKS(mol)).density_fit()
        mf.xc = method_spec["xc"]
        if method_spec["dispersion"]:
            mf.disp = method_spec["dispersion"]
    mf = _apply_solvation(mf, solvation, solvent_name)
    mf.conv_tol = 1e-9
    return mf


def refine_with_pyscf(
    frame: dict[str, Any],
    destination: Path,
    *,
    charge: int = 0,
    multiplicity: int = 1,
    method: str = "B3LYP-D3BJ",
    basis: str = "def2-SVP",
    solvation: str = "gas",
    solvent_name: str | None = None,
    run_frequencies: bool = False,
    cores: int = 1,
) -> dict[str, Any]:
    """Optimize geometry with CPU PySCF + geomeTRIC and optionally compute harmonic frequencies."""
    import numpy as np
    from pyscf import gto, lib
    from pyscf.geomopt import geometric_solver

    method_spec, basis_label = normalize_method_and_basis(method, basis)
    if solvation not in V2_ALLOWED_SOLVATIONS:
        raise ValueError(f"Unsupported solvation {solvation!r}")

    lib.num_threads(max(1, int(cores)))
    spin = multiplicity - 1
    mol = gto.M(
        atom=list(zip(frame["symbols"], frame["coords"])),
        unit="Angstrom",
        basis=basis_label,
        spin=spin,
        charge=charge,
        verbose=4,
        output=str(destination / "pyscf.log"),
    )
    mf = _build_pyscf_mf(mol, method_spec, solvation=solvation, solvent_name=solvent_name)
    converged, optimized = geometric_solver.kernel(mf, maxsteps=80, assert_convergence=True)
    if not converged:
        raise RuntimeError("geomeTRIC geometry optimization did not converge")

    final_mf = _build_pyscf_mf(optimized, method_spec, solvation=solvation, solvent_name=solvent_name)
    energy = float(final_mf.kernel())
    if not final_mf.converged or not math.isfinite(energy):
        raise RuntimeError(f"Final PySCF {method_spec['label']}/{basis_label} SCF did not converge")
    gradient = final_mf.nuc_grad_method().kernel()
    coords = optimized.atom_coords(unit="Angstrom")
    if gradient.shape != coords.shape or not np.isfinite(gradient).all() or not np.isfinite(coords).all():
        raise ValueError("Invalid final PySCF gradient or geometry")

    n_imaginary_modes: int | None = None
    freq_cm1: list[float] | None = None
    if run_frequencies:
        from pyscf.hessian import thermo

        hess = final_mf.Hessian().kernel()
        h_info = thermo.harmonic_analysis(optimized, hess)
        raw_freqs = h_info["freq_wavenumber"]
        parsed_freqs: list[float] = []
        imag_count = 0
        for val in raw_freqs:
            if isinstance(val, complex):
                if abs(val.imag) > 10.0:
                    imag_count += 1
                    parsed_freqs.append(-abs(val.imag))
                else:
                    parsed_freqs.append(float(val.real))
            else:
                fval = float(val)
                if fval < -10.0:
                    imag_count += 1
                parsed_freqs.append(fval)
        n_imaginary_modes = imag_count
        freq_cm1 = parsed_freqs

    symbols = list(frame["symbols"])
    method_label = method_spec["label"]
    if method_label == "RHF" and spin != 0:
        method_label = "UHF"
    lines = [
        str(len(symbols)),
        f"{energy:.14f} {method_label}/{basis_label} ({solvation}) hartree; coordinates in angstrom",
    ]
    lines.extend(f"{s} {x:.12f} {y:.12f} {z:.12f}" for s, (x, y, z) in zip(symbols, coords))
    (destination / "refined.xyz").write_text("\n".join(lines) + "\n", encoding="utf-8")

    summary: dict[str, Any] = {
        "energy_hartree": energy,
        "gradient_hartree_per_bohr": gradient.tolist(),
        "optimizer_converged": True,
        "scf_converged": True,
        "method": method_label,
        "basis": basis_label,
        "charge": int(charge),
        "multiplicity": int(multiplicity),
        "solvation": solvation,
        "solvent_name": solvent_name if solvation != "gas" else None,
        "hessian_calculated": bool(run_frequencies),
        "n_imaginary_modes": n_imaginary_modes,
    }
    if freq_cm1 is not None:
        summary["frequencies_cm1"] = freq_cm1
    save_json(destination / "pyscf.json", summary)
    return summary


def calculate(
    filename: str,
    work: Path,
    out: Path,
    *,
    charge: int = 0,
    multiplicity: int = 1,
    mlff: str = "auto",
    method: str = "B3LYP-D3BJ",
    basis: str = "def2-SVP",
    solvation: str = "gas",
    solvent_name: str | None = None,
    run_frequencies: bool = False,
    workflow_type: str = "conformer",
    course_id: str = "CHEM312",
    target_continuation: str = "workstation",
    student_id: str | None = None,
    cores: int = 1,
) -> tuple[Path, Path, str, dict[str, Any]]:
    """Run XYZ -> CREST 3.0.2 -> AIMNet2/MACE -> CPU PySCF and seal a v2 handoff ZIP."""
    if workflow_type not in V2_ALLOWED_WORKFLOW_TYPES:
        raise ValueError(f"Unsupported workflow_type {workflow_type!r}")
    allowed_courses = get_allowed_course_ids()
    if course_id not in allowed_courses:
        raise ValueError(f"Unsupported course_id {course_id!r}; expected one of {allowed_courses}")
    if target_continuation not in V2_ALLOWED_TARGET_CONTINUATIONS:
        raise ValueError(f"Unsupported target_continuation {target_continuation!r}")

    work = Path(work)
    out = Path(out)
    starter_stage = work / "_starter_inputs"
    source = input_file(filename, materialize_dir=starter_stage)
    original = read_input(source, charge=charge, multiplicity=multiplicity)
    chosen_mlff = select_mlff_backend(
        original["symbols"],
        charge=charge,
        multiplicity=multiplicity,
        requested=mlff,
    )
    normalize_method_and_basis(method, basis)

    payload = work / "bundle"
    payload.mkdir(parents=True, exist_ok=True)
    conformers_dir = payload / "isomers"
    conformers_dir.mkdir(exist_ok=True)
    shutil.copyfile(source, payload / "input.xyz")

    native = work / "native"
    native.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, native / "input.xyz")

    sys.path.insert(0, str(ROOT / "scripts"))
    from verify_free_engines import execute

    bins = resolve_xtb_crest_binaries()
    xtb = bins["xtb"]
    crest = bins["crest"]
    env = bins["env"]
    if bins["engines_json_path"] is not None:
        shutil.copyfile(bins["engines_json_path"], payload / "engines.json")
    else:
        save_json(
            payload / "engines.json",
            {
                "source": "wsl2_or_path_discovery",
                "xtb_executable": xtb,
                "crest_executable": crest,
                "aimnet_python": resolve_aimnet_python(),
            },
        )

    argv = build_crest_argv(
        crest,
        xtb,
        charge=charge,
        multiplicity=multiplicity,
        cores=cores,
        nci=(workflow_type == "nci_dimer"),
        quick=True,
    )
    log = execute(argv, native, "crest.log", env, timeout=900)
    if (
        "CREST terminated normally" not in log
        or (xtb not in log and Path(xtb).name not in log)
        or "Use of GFN2-xTB requested" not in log
    ):
        raise RuntimeError("CREST did not confirm external GFN2-xTB and normal termination")
    for name in ("crest.log", "crest_conformers.xyz"):
        shutil.copyfile(native / name, payload / name)

    ensemble = frames(
        (payload / "crest_conformers.xyz").read_text(encoding="utf-8"),
        energy=True,
        charge=charge,
        multiplicity=multiplicity,
    )
    if len(ensemble) > V2_MAX_FRAMES:
        raise ValueError(f"Ensemble ({len(ensemble)}) exceeds the {V2_MAX_FRAMES}-conformer v2 budget")

    results: list[dict[str, Any]] = []
    if chosen_mlff == "mace":
        model_path = _download_verified_mace_model(work)
        evaluate_mace = runpy.run_path(str(ROOT / "src/cochem_base/core_engine/mlff_worker.py"))["evaluate"]
        for index, frame in enumerate(ensemble, start=1):
            if frame["symbols"] != original["symbols"]:
                raise ValueError("CREST changed the atom sequence")
            relative = f"isomers/crest-{index:03}.xyz"
            (payload / relative).write_text(frame["text"], encoding="utf-8")
            calc = evaluate_mace(
                {
                    "elements": frame["symbols"],
                    "coordinates_angstrom": frame["coords"],
                    "cores": max(1, int(cores)),
                    "checkpoint": str(model_path),
                    "checkpoint_sha256": MACE_MODEL_SHA,
                }
            )
            if calc["status"] != "SUCCESS":
                raise RuntimeError(f"MACE evaluation {index}: {calc['status']}")
            results.append(
                {
                    "xyz": relative,
                    "crest_energy_hartree": frame["energy_hartree"],
                    "mlff": calc,
                }
            )
        ranking_model = "MACE-OFF24-medium"
        ranking_sha = MACE_MODEL_SHA
    else:
        for index, frame in enumerate(ensemble, start=1):
            if frame["symbols"] != original["symbols"]:
                raise ValueError("CREST changed the atom sequence")
            relative = f"isomers/crest-{index:03}.xyz"
            (payload / relative).write_text(frame["text"], encoding="utf-8")
        aimnet_calcs = _evaluate_aimnet2_frames(
            ensemble,
            charge=charge,
            multiplicity=multiplicity,
        )
        for index, (frame, calc) in enumerate(zip(ensemble, aimnet_calcs), start=1):
            relative = f"isomers/crest-{index:03}.xyz"
            results.append(
                {
                    "xyz": relative,
                    "crest_energy_hartree": frame["energy_hartree"],
                    "mlff": calc,
                }
            )
        ranking_model = "AIMNet2"
        ranking_sha = None

    winner = min(range(len(results)), key=lambda i: results[i]["mlff"]["energy_hartree"])
    save_json(
        payload / "ranking.json",
        {
            "backend": chosen_mlff,
            "model": ranking_model,
            "model_sha256": ranking_sha,
            "selection": f"lowest {ranking_model} single-point energy; first CREST index breaks exact ties",
            "selected": results[winner]["xyz"],
            "candidates": results,
        },
    )

    pyscf_summary = refine_with_pyscf(
        ensemble[winner],
        payload,
        charge=charge,
        multiplicity=multiplicity,
        method=method,
        basis=basis,
        solvation=solvation,
        solvent_name=solvent_name,
        run_frequencies=run_frequencies,
        cores=cores,
    )

    pkg_versions: dict[str, str] = {}
    for pkg in ("torch", "aimnet", "mace-torch", "ase", "pyscf", "geometric"):
        try:
            pkg_versions[pkg] = md.version(pkg)
        except md.PackageNotFoundError:
            continue

    commit_sha = os.environ.get("GITHUB_SHA", "0" * 40).strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
        commit_sha = "0" * 40

    manifest: dict[str, Any] = {
        "workflow_type": workflow_type,
        "input_name": Path(filename).name,
        "charge": int(charge),
        "multiplicity": int(multiplicity),
        "length_unit": "angstrom",
        "method": f"{ranking_model} + {pyscf_summary['method']}",
        "basis": pyscf_summary["basis"],
        "solvation": solvation,
        "solvent_name": solvent_name if solvation != "gas" else None,
        "hessian_calculated": bool(pyscf_summary["hessian_calculated"]),
        "n_imaginary_modes": pyscf_summary["n_imaginary_modes"],
        "course_id": course_id,
        "collaborator_institution": DEFAULT_COLLABORATOR_INSTITUTION,
        "target_continuation": target_continuation,
        "starting_xyz": "input.xyz",
        "primary_xyz": "refined.xyz",
        "ensemble_xyz": "crest_conformers.xyz",
        "candidate_count": len(results),
        "selected": results[winner]["xyz"],
        "student_id": student_id or f"{course_id.lower()}_student",
        "repository": os.environ.get("GITHUB_REPOSITORY", "ProfJJK-CoChem/CoChem-BASE"),
        "commit": commit_sha,
        "run_id": os.environ.get("GITHUB_RUN_ID", "local-run"),
        "attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
        "metadata": {
            "energy_hartree": pyscf_summary["energy_hartree"],
            "mlff_backend": chosen_mlff,
            "crest_options": argv[1:],
            "packages": pkg_versions,
        },
    }
    return seal(payload, out, manifest)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "filename",
        nargs="?",
        default=None,
        help="XYZ filename inside examples/student_inputs/ or path to .xyz (or use --xyz)",
    )
    parser.add_argument(
        "work",
        nargs="?",
        type=Path,
        default=None,
        help="Scratch working directory (or use --work-dir; defaults to <output-dir>/_work)",
    )
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=None,
        help="Output directory for sealed v2 ZIP + .sha256 (or use --output-dir)",
    )
    parser.add_argument(
        "--xyz",
        dest="xyz_flag",
        default=None,
        help="Input .xyz path or starter filename (alternative to positional filename)",
    )
    parser.add_argument(
        "--work-dir",
        dest="work_dir",
        type=Path,
        default=None,
        help="Scratch working directory (alternative to positional work; defaults to <output-dir>/_work)",
    )
    parser.add_argument(
        "--output-dir",
        dest="output_dir",
        type=Path,
        default=None,
        help="Output directory for sealed v2 ZIP + .sha256 (alternative to positional output)",
    )
    parser.add_argument("--charge", type=int, default=0, choices=list(V2_ALLOWED_CHARGES))
    parser.add_argument("--multiplicity", type=int, default=1, choices=list(V2_ALLOWED_MULTIPLICITIES))
    parser.add_argument("--mlff", default="auto", choices=["auto", "aimnet2", "mace"])
    parser.add_argument("--method", default="B3LYP-D3BJ", help="PySCF method: RHF, UHF, B3LYP-D3BJ, wB97X-D3")
    parser.add_argument("--basis", default="def2-SVP", help="PySCF basis: STO-3G, def2-SVP, def2-TZVP, def2-TZVPP")
    parser.add_argument("--solvation", default="gas", choices=list(V2_ALLOWED_SOLVATIONS))
    parser.add_argument("--solvent-name", default=None, help="Solvent name when solvation is pcm/ddcosmo")
    parser.add_argument("--frequencies", action="store_true", help="Compute harmonic Hessian and imaginary mode count")
    parser.add_argument("--workflow-type", default="conformer", choices=list(V2_ALLOWED_WORKFLOW_TYPES))
    parser.add_argument("--course-id", default="CHEM312", choices=list(get_allowed_course_ids()))
    parser.add_argument("--target-continuation", default="workstation", choices=list(V2_ALLOWED_TARGET_CONTINUATIONS))
    parser.add_argument("--student-id", default=None)
    parser.add_argument("--cores", type=int, default=1)
    return parser


def resolve_cli_paths(args: argparse.Namespace) -> tuple[str, Path, Path]:
    """Resolve dual positional (`filename work output`) and flag (`--xyz --work-dir --output-dir`) paths."""
    if args.filename is not None and args.xyz_flag is not None and args.filename != args.xyz_flag:
        raise ValueError("Provide either positional filename or --xyz, not conflicting values")
    filename = args.xyz_flag if args.xyz_flag is not None else args.filename
    if not filename:
        raise ValueError("Missing input XYZ: supply positional `filename` or `--xyz <path>`")

    if args.output is not None and args.output_dir is not None and args.output != args.output_dir:
        raise ValueError("Provide either positional output or --output-dir, not conflicting values")
    output = args.output_dir if args.output_dir is not None else args.output
    if output is None:
        raise ValueError("Missing output directory: supply positional `output` or `--output-dir <dir>`")

    if args.work is not None and args.work_dir is not None and args.work != args.work_dir:
        raise ValueError("Provide either positional work or --work-dir, not conflicting values")
    work = args.work_dir if args.work_dir is not None else args.work
    if work is None:
        work = output / "_work"

    return str(filename), Path(work), Path(output)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        filename, work_dir, output_dir = resolve_cli_paths(args)
    except ValueError as exc:
        parser.error(str(exc))
    zip_path, sha_path, archive_sha, _ = calculate(
        filename,
        work_dir,
        output_dir,
        charge=args.charge,
        multiplicity=args.multiplicity,
        mlff=args.mlff,
        method=args.method,
        basis=args.basis,
        solvation=args.solvation,
        solvent_name=args.solvent_name,
        run_frequencies=bool(args.frequencies),
        workflow_type=args.workflow_type,
        course_id=args.course_id,
        target_continuation=args.target_continuation,
        student_id=args.student_id,
        cores=args.cores,
    )
    print(json.dumps({"zip_path": str(zip_path), "sha256_path": str(sha_path), "archive_sha256": archive_sha}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
