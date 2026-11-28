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
from typing import Any, Sequence
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
        read_input,
        seal,
    )
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
        read_input,
        seal,
    )

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
    quick: bool = False,
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


def input_file(filename: str) -> Path:
    """Resolve an input XYZ file either from `examples/student_inputs/` or a direct regular file path."""
    candidate = Path(filename)
    if candidate.is_file() and not candidate.is_symlink() and candidate.suffix.lower() == ".xyz":
        return candidate.resolve()
    if not re.fullmatch(r"[a-zA-Z0-9._-]{1,96}\.xyz", filename):
        raise ValueError("Select a valid .xyz filename from examples/student_inputs or an existing .xyz file path")
    source = ROOT / "examples" / "student_inputs" / filename
    if source.is_symlink() or not source.is_file() or source.resolve().parent != (ROOT / "examples" / "student_inputs").resolve():
        raise ValueError("XYZ must be an ordinary file in examples/student_inputs")
    return source


def _probe_binary_version(exe_path: str) -> str | None:
    """Capture the first non-empty version line from an authentic local binary."""
    try:
        proc = subprocess.run(
            [exe_path, "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except OSError:
        return None
    combined = "\n".join(part for part in (proc.stdout, proc.stderr) if part)
    for line in combined.splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned[:200]
    return None


def _resolve_free_engines(payload_dir: Path) -> tuple[str, str, dict[str, str]]:
    """Resolve authentic local xTB and CREST binaries and bind SHA-256 + version provenance."""
    env = dict(os.environ)
    free_root_raw = env.get("COCHEM_FREE_ROOT", "").strip()
    source_kind = "local_workstation_env"
    xtb_path: str | None = None
    crest_path: str | None = None
    upstream_manifest: dict[str, Any] | None = None

    if free_root_raw:
        engine_root = Path(free_root_raw)
        xtb_candidate = engine_root / "xtb/xtb-dist/bin/xtb"
        crest_candidate = engine_root / "crest/crest/crest"
        if xtb_candidate.is_file() and crest_candidate.is_file():
            xtb_path = str(xtb_candidate.resolve())
            crest_path = str(crest_candidate.resolve())
            source_kind = "cochem_free_root"
            xtb_share = engine_root / "xtb/xtb-dist/share/xtb"
            if xtb_share.is_dir():
                env["XTBPATH"] = str(xtb_share)
            env["PATH"] = str(xtb_candidate.parent) + os.pathsep + env.get("PATH", "")
            engines_json = engine_root / "engines.json"
            if engines_json.is_file():
                try:
                    loaded = json.loads(engines_json.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        upstream_manifest = loaded
                except Exception as exc:
                    raise RuntimeError(f"Unreadable engines.json in COCHEM_FREE_ROOT: {exc}") from exc

    if not xtb_path:
        xtb_path = next(
            (
                str(Path(candidate).resolve())
                for candidate in (env.get("COCHEM_XTB_BIN"), env.get("XTB_CMD"), shutil.which("xtb"))
                if candidate and Path(candidate).is_file()
            ),
            None,
        )
    if not crest_path:
        crest_path = next(
            (
                str(Path(candidate).resolve())
                for candidate in (env.get("COCHEM_CREST_BIN"), env.get("CREST_CMD"), shutil.which("crest"))
                if candidate and Path(candidate).is_file()
            ),
            None,
        )
    if not xtb_path or not crest_path:
        raise RuntimeError(
            "Unable to locate authentic xTB and CREST binaries. "
            "Activate WSL2 (`source ~/CoChem_Workstation_Direct/activate_cochem_wsl.sh`) "
            "or set COCHEM_FREE_ROOT / COCHEM_XTB_BIN / COCHEM_CREST_BIN."
        )

    def _sha256_path(path_str: str) -> str:
        with Path(path_str).open("rb") as handle:
            return hashlib.file_digest(handle, "sha256").hexdigest()

    xtb_sha = _sha256_path(xtb_path)
    crest_sha = _sha256_path(crest_path)

    # If COCHEM_FREE_ROOT provided a manifest with binary SHA-256 entries, verify them against disk.
    if isinstance(upstream_manifest, dict):
        for key, actual_sha in (("xtb", xtb_sha), ("crest", crest_sha)):
            entry = upstream_manifest.get(key)
            if isinstance(entry, dict):
                expected = entry.get("binary_sha256") or entry.get("executable_sha256") or entry.get("sha256")
                if isinstance(expected, str) and len(expected) == 64 and expected.lower() != actual_sha.lower():
                    raise RuntimeError(
                        f"COCHEM_FREE_ROOT manifest SHA-256 mismatch for {key}: "
                        f"expected {expected}, observed {actual_sha}"
                    )

    provenance: dict[str, Any] = {
        "schema": "cochem.local-free-engines/1",
        "source": source_kind,
        "xtb": {
            "path": xtb_path,
            "sha256": xtb_sha,
            "observed_version": _probe_binary_version(xtb_path),
        },
        "crest": {
            "path": crest_path,
            "sha256": crest_sha,
            "observed_version": _probe_binary_version(crest_path),
        },
        "xtbpath": env.get("XTBPATH"),
    }
    if upstream_manifest is not None:
        provenance["upstream_manifest"] = upstream_manifest
    save_json(payload_dir / "engines.json", provenance)
    return xtb_path, crest_path, env


def _evaluate_aimnet2_via_subprocess(
    python_exe: str,
    symbols: Sequence[str],
    coords: Sequence[Sequence[float]],
    *,
    charge: int,
    multiplicity: int,
    model_name: str,
) -> dict[str, Any]:
    """Run authentic AIMNet2ASE in the host's isolated COCHEM_AIMNET_PYTHON venv."""
    helper = (
        "import json, math, sys\n"
        "import numpy as np\n"
        "from ase import Atoms\n"
        "from aimnet.calculators import AIMNet2ASE\n"
        "req = json.loads(sys.stdin.read())\n"
        "atoms = Atoms(list(req['symbols']), positions=list(req['coords']))\n"
        "atoms.info['charge'] = int(req['charge'])\n"
        "atoms.info['spin'] = int(req['multiplicity'])\n"
        "atoms.calc = AIMNet2ASE(req['model_name'], charge=int(req['charge']), mult=int(req['multiplicity']))\n"
        "e_ev = float(atoms.get_potential_energy())\n"
        "f_ev_ang = np.asarray(atoms.get_forces(), dtype=float)\n"
        "if not math.isfinite(e_ev) or f_ev_ang.shape != (len(req['symbols']), 3) or not np.isfinite(f_ev_ang).all():\n"
        "    raise RuntimeError('AIMNet2 returned non-finite energy or forces')\n"
        "print(json.dumps({'energy_ev': e_ev, 'forces_ev_ang': f_ev_ang.tolist()}))\n"
    )
    req_json = json.dumps(
        {
            "symbols": list(symbols),
            "coords": [list(map(float, row)) for row in coords],
            "charge": int(charge),
            "multiplicity": int(multiplicity),
            "model_name": model_name,
        }
    )
    proc = subprocess.run(
        [python_exe, "-c", helper],
        input=req_json,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Isolated COCHEM_AIMNET_PYTHON ({python_exe}) failed (exit {proc.returncode}): "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    import numpy as np

    out = json.loads(proc.stdout.strip().splitlines()[-1])
    energy_ev = float(out["energy_ev"])
    forces_ev_ang = np.asarray(out["forces_ev_ang"], dtype=float)
    energy_hartree = energy_ev / HARTREE_TO_EV
    gradient_eh_bohr = (-forces_ev_ang * BOHR_TO_ANGSTROM / HARTREE_TO_EV).tolist()
    return {
        "status": "SUCCESS",
        "backend": "aimnet2",
        "model": model_name,
        "charge": int(charge),
        "multiplicity": int(multiplicity),
        "energy_hartree": energy_hartree,
        "gradient_hartree_per_bohr": gradient_eh_bohr,
        "runtime_python": python_exe,
    }


def _evaluate_aimnet2_frame(
    symbols: Sequence[str],
    coords: Sequence[Sequence[float]],
    *,
    charge: int,
    multiplicity: int,
    model_name: str = "aimnet2",
) -> dict[str, Any]:
    """Evaluate single-point energy & gradient using charge-aware AIMNet2 on CPU."""
    import numpy as np
    from ase import Atoms

    try:
        from aimnet.calculators import AIMNet2ASE  # type: ignore[import-not-found]
    except ImportError as exc:
        aimnet_py = os.environ.get("COCHEM_AIMNET_PYTHON", "").strip()
        if aimnet_py and Path(aimnet_py).is_file():
            return _evaluate_aimnet2_via_subprocess(
                aimnet_py,
                symbols,
                coords,
                charge=charge,
                multiplicity=multiplicity,
                model_name=model_name,
            )
        raise RuntimeError(
            "Charge-aware AIMNet2 package (`aimnet`) is required for this system but is not installed "
            "in the current interpreter and COCHEM_AIMNET_PYTHON is not configured."
        ) from exc

    atoms = Atoms(list(symbols), positions=list(coords))
    atoms.info["charge"] = int(charge)
    atoms.info["spin"] = int(multiplicity)
    calc = AIMNet2ASE(model_name, charge=int(charge), mult=int(multiplicity))
    atoms.calc = calc
    energy_ev = float(atoms.get_potential_energy())
    forces_ev_ang = np.asarray(atoms.get_forces(), dtype=float)
    if not math.isfinite(energy_ev) or forces_ev_ang.shape != (len(symbols), 3) or not np.isfinite(forces_ev_ang).all():
        raise RuntimeError("AIMNet2 returned non-finite energy or forces")
    energy_hartree = energy_ev / HARTREE_TO_EV
    gradient_eh_bohr = (-forces_ev_ang * BOHR_TO_ANGSTROM / HARTREE_TO_EV).tolist()
    return {
        "status": "SUCCESS",
        "backend": "aimnet2",
        "model": model_name,
        "charge": int(charge),
        "multiplicity": int(multiplicity),
        "energy_hartree": energy_hartree,
        "gradient_hartree_per_bohr": gradient_eh_bohr,
    }


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
    quick: bool = False,
) -> tuple[Path, Path, str, dict[str, Any]]:
    """Run XYZ -> CREST 3.0.2 -> AIMNet2/MACE -> CPU PySCF and seal a v2 handoff ZIP."""
    if workflow_type not in V2_ALLOWED_WORKFLOW_TYPES:
        raise ValueError(f"Unsupported workflow_type {workflow_type!r}")
    if course_id not in V2_ALLOWED_COURSE_IDS:
        raise ValueError(f"Unsupported course_id {course_id!r}")
    if target_continuation not in V2_ALLOWED_TARGET_CONTINUATIONS:
        raise ValueError(f"Unsupported target_continuation {target_continuation!r}")

    source = input_file(filename)
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

    xtb, crest, env = _resolve_free_engines(payload)

    argv = build_crest_argv(
        crest,
        xtb,
        charge=charge,
        multiplicity=multiplicity,
        cores=cores,
        nci=(workflow_type == "nci_dimer"),
        quick=quick,
    )
    log = execute(argv, native, "crest.log", env, timeout=900)
    if "CREST terminated normally" not in log or xtb not in log or "Use of GFN2-xTB requested" not in log:
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
            calc = _evaluate_aimnet2_frame(
                frame["symbols"],
                frame["coords"],
                charge=charge,
                multiplicity=multiplicity,
            )
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
    parser.add_argument("filename", nargs="?", default=None, help="XYZ filename inside examples/student_inputs/ or path to .xyz")
    parser.add_argument("work", nargs="?", type=Path, default=None, help="Scratch working directory")
    parser.add_argument("output", nargs="?", type=Path, default=None, help="Output directory for sealed v2 ZIP + .sha256")
    parser.add_argument("--xyz", dest="xyz_opt", default=None, help="Optional named alias for input .xyz path")
    parser.add_argument("--work-dir", dest="work_opt", type=Path, default=None, help="Optional named alias for scratch working directory")
    parser.add_argument("--output-dir", dest="output_opt", type=Path, default=None, help="Optional named alias for output directory")
    parser.add_argument("--charge", type=int, default=0, choices=list(V2_ALLOWED_CHARGES))
    parser.add_argument("--multiplicity", type=int, default=1, choices=list(V2_ALLOWED_MULTIPLICITIES))
    parser.add_argument("--mlff", default="auto", choices=["auto", "aimnet2", "mace"])
    parser.add_argument("--method", default="B3LYP-D3BJ", help="PySCF method: RHF, UHF, B3LYP-D3BJ, wB97X-D3")
    parser.add_argument("--basis", default="def2-SVP", help="PySCF basis: STO-3G, def2-SVP, def2-TZVP, def2-TZVPP")
    parser.add_argument("--solvation", default="gas", choices=list(V2_ALLOWED_SOLVATIONS))
    parser.add_argument("--solvent-name", default=None, help="Solvent name when solvation is pcm/ddcosmo")
    parser.add_argument("--frequencies", action="store_true", help="Compute harmonic Hessian and imaginary mode count")
    parser.add_argument("--quick", action="store_true", help="Pass --quick to CREST 3.0.2 (off by default for full conformer search)")
    parser.add_argument("--workflow-type", default="conformer", choices=list(V2_ALLOWED_WORKFLOW_TYPES))
    parser.add_argument("--course-id", default="CHEM312", choices=list(V2_ALLOWED_COURSE_IDS))
    parser.add_argument("--target-continuation", default="workstation", choices=list(V2_ALLOWED_TARGET_CONTINUATIONS))
    parser.add_argument("--student-id", default=None)
    parser.add_argument("--cores", type=int, default=1)
    return parser


def resolve_cli_paths(args: argparse.Namespace) -> tuple[str, Path, Path]:
    """Accept either positional `(filename, work, output)` or named `--xyz`/`--output-dir` flags."""
    filename = args.xyz_opt if args.xyz_opt is not None else args.filename
    output = args.output_opt if args.output_opt is not None else args.output
    work = args.work_opt if args.work_opt is not None else args.work
    if not filename:
        raise ValueError("Provide an input .xyz file via positional `filename` or `--xyz <path>`.")
    if output is None:
        raise ValueError("Provide an output directory via positional `output` or `--output-dir <dir>`.")
    if work is None:
        work = output / "_work"
    return filename, work, output


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        filename, work, output = resolve_cli_paths(args)
    except ValueError as exc:
        parser.error(str(exc))
    zip_path, sha_path, archive_sha, _ = calculate(
        filename,
        work,
        output,
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
        quick=bool(args.quick),
    )
    print(json.dumps({"zip_path": str(zip_path), "sha256_path": str(sha_path), "archive_sha256": archive_sha}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
