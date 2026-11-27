"""Authentic FP64 CUDA GPU4PySCF execution adapter (RKS/UKS single-point, gradient, opt).

Executes real GPU4PySCF via `cochem-gpu4pyscf-python` / `/home/ansac/.venvs/gpu4pyscf/bin/python`
(or in-process when CUDA + `gpu4pyscf` are present in the active interpreter),
using explicit FP64 density fitting (`def2-universal-jkfit`), `(99, 590)` XC grid,
and `(50, 194)` NLC grid for VV10 functionals (`wb97x_v`, `wb97m_v`).

Fails closed when no CUDA GPU or `gpu4pyscf` runtime is available; NEVER silently
downgrades to CPU PySCF.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence

import numpy as np

from cochem_base.core_engine.scientific_writer import scientific_producer

DEFAULT_AUXBASIS = "def2-universal-jkfit"
DEFAULT_XC_GRID = (99, 590)
DEFAULT_VV10_NLC_GRID = (50, 194)
VV10_FUNCTIONALS = frozenset({
    "wb97x_v",
    "wb97m_v",
    "rev_wb97m_v",
    "b97m_v",
    "vv10",
    "rvv10",
})


class GPU4PySCFUnavailableError(RuntimeError):
    """Raised fail-closed when CUDA GPU or GPU4PySCF runtime is unavailable."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_gpu4pyscf_method(method: str) -> tuple[str, bool, bool]:
    """Normalize a method name to `(xc_or_hf, is_hf, uses_vv10)`.

    Examples:
        'wB97M-V' -> ('wb97m_v', False, True)
        'wB97X-V' -> ('wb97x_v', False, True)
        'HF'      -> ('HF', True, False)
        'PBE0'    -> ('pbe0', False, False)
    """
    cleaned = method.strip()
    if not cleaned:
        raise ValueError("GPU4PySCF requires a nonempty method or functional name")
    upper = cleaned.upper()
    if upper in {"HF", "RHF", "UHF"}:
        return upper, True, False
    norm = cleaned.lower().replace("-", "_").replace(" ", "_")
    # Strip leading restricted/unrestricted prefix only when explicitly rks_/uks_
    for prefix in ("rks_", "uks_"):
        if norm.startswith(prefix):
            norm = norm[len(prefix):]
    aliases = {
        "m06_2x": "m062x",
        "m06_l": "m06l",
        "b3lyp_g": "b3lypg",
    }
    norm = aliases.get(norm, norm)
    uses_vv10 = norm in VV10_FUNCTIONALS or norm.endswith("_v") or "vv10" in norm
    return norm, False, uses_vv10


def _candidate_executable(candidate: str | Path | None, *, search_path: str | None = None) -> Path | None:
    if not candidate:
        return None
    raw = str(candidate).strip()
    if not raw:
        return None
    expanded = Path(os.path.expandvars(raw)).expanduser()
    if expanded.is_file():
        # Preserve venv bin/python symlinks so Python loads pyvenv.cfg instead of system python.
        return Path(os.path.abspath(str(expanded)))
    found = shutil.which(raw, path=search_path)
    if found:
        located = Path(os.path.abspath(found))
        if located.is_file():
            return located
    return None


def _in_process_gpu4pyscf_ready(env: Mapping[str, str] | None = None) -> bool:
    active_env = os.environ if env is None else env
    if active_env.get("CUDA_VISIBLE_DEVICES", "0").strip() in {"", "-1"}:
        return False
    try:
        import cupy  # type: ignore[import-not-found]
        import gpu4pyscf  # type: ignore[import-not-found]
        import pyscf  # type: ignore[import-not-found]
    except Exception:
        return False
    try:
        return bool(pyscf and gpu4pyscf and cupy.cuda.runtime.getDeviceCount() > 0)
    except Exception:
        return False


def resolve_gpu4pyscf_python(
    executable: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    """Resolve an authentic GPU4PySCF Python interpreter; fail closed if unavailable."""
    active_env = os.environ if env is None else env
    if active_env.get("CUDA_VISIBLE_DEVICES", "0").strip() in {"", "-1"}:
        raise GPU4PySCFUnavailableError(
            "CUDA_VISIBLE_DEVICES disables CUDA GPUs; GPU4PySCF fails closed and never downgrades to CPU."
        )
    search_path = active_env.get("PATH")
    if executable is not None:
        resolved = _candidate_executable(executable, search_path=search_path)
        if resolved is None:
            raise GPU4PySCFUnavailableError(f"Requested GPU4PySCF interpreter not found: {executable}")
        return resolved

    candidates: list[str | Path] = []
    for var in ("COCHEM_GPU4PYSCF_PYTHON", "GPU4PYSCF_PYTHON"):
        if active_env.get(var):
            candidates.append(active_env[var])
    candidates.extend([
        Path.home() / "CoChem_Workstation_Direct" / "bin" / "cochem-gpu4pyscf-python",
        Path.home() / ".venvs" / "gpu4pyscf" / "bin" / "python",
        "cochem-gpu4pyscf-python",
    ])
    for cand in candidates:
        resolved = _candidate_executable(cand, search_path=search_path)
        if resolved is not None:
            return resolved

    if _in_process_gpu4pyscf_ready(active_env):
        return Path(sys.executable).resolve()

    raise GPU4PySCFUnavailableError(
        "No CUDA GPU4PySCF Python runtime found (checked COCHEM_GPU4PYSCF_PYTHON, "
        "~/CoChem_Workstation_Direct/bin/cochem-gpu4pyscf-python, ~/.venvs/gpu4pyscf/bin/python, "
        "and current interpreter). Refusing silent CPU fallback."
    )


def build_gpu4pyscf_script(
    elements: Sequence[str],
    coordinates_angstrom: Sequence[Sequence[float]],
    *,
    method: str = "wB97M-V",
    basis_set: str = "def2-SVP",
    charge: int = 0,
    multiplicity: int = 1,
    is_opt: bool = False,
    compute_gradient: bool = True,
    auxbasis: str = DEFAULT_AUXBASIS,
    xc_grid: tuple[int, int] = DEFAULT_XC_GRID,
    nlc_grid: tuple[int, int] = DEFAULT_VV10_NLC_GRID,
    conv_tol: float = 1e-10,
    max_cycle: int = 200,
    opt_gtol: float = 1e-4,
    opt_maxiter: int = 100,
    max_memory_mb: int = 8192,
    device_index: int = 0,
) -> tuple[str, dict[str, Any]]:
    """Build an explicit FP64 CUDA GPU4PySCF worker script and its spec dict."""
    if not elements or len(elements) != len(coordinates_angstrom):
        raise ValueError("Nonempty matching elements and Cartesian coordinates are required")
    if isinstance(multiplicity, bool) or multiplicity < 1:
        raise ValueError("multiplicity must be an integer >= 1")
    if not basis_set or not basis_set.strip():
        raise ValueError("GPU4PySCF requires an explicit Gaussian orbital basis set")
    xyz = np.asarray(coordinates_angstrom, dtype=np.float64)
    if xyz.shape != (len(elements), 3) or not np.isfinite(xyz).all():
        raise ValueError("GPU4PySCF requires finite N x 3 Cartesian coordinates")

    xc_or_hf, is_hf, uses_vv10 = normalize_gpu4pyscf_method(method)
    spin = int(multiplicity) - 1
    unrestricted = spin > 0 or method.strip().upper().startswith(("UHF", "UKS"))

    from cochem_base.calc.regime_guards import apply_chemical_regime_guards

    regime = apply_chemical_regime_guards(
        elements,
        charge=int(charge),
        method_or_theory=method.strip(),
        basis=basis_set.strip(),
        engine="gpu4pyscf",
    )
    effective_basis = regime.effective_basis or basis_set.strip()
    effective_xc_grid = (
        (max(int(xc_grid[0]), DEFAULT_XC_GRID[0]), max(int(xc_grid[1]), DEFAULT_XC_GRID[1]))
        if regime.require_defgrid3
        else (int(xc_grid[0]), int(xc_grid[1]))
    )

    spec: dict[str, Any] = {
        "atom": [[str(sym), [float(v) for v in row]] for sym, row in zip(elements, xyz, strict=True)],
        "basis": effective_basis,
        "requested_basis": basis_set.strip(),
        "ecp": dict(regime.pyscf_ecp) if regime.pyscf_ecp else None,
        "use_sfx2c1e": bool(regime.pyscf_sfx2c1e),
        "regime_guards": regime.to_provenance_dict(),
        "charge": int(charge),
        "spin": spin,
        "multiplicity": int(multiplicity),
        "requested_method": method.strip(),
        "xc_or_hf": xc_or_hf,
        "is_hf": is_hf,
        "uses_vv10": uses_vv10,
        "unrestricted": unrestricted,
        "auxbasis": auxbasis,
        "xc_grid": [effective_xc_grid[0], effective_xc_grid[1]],
        "nlc_grid": [int(nlc_grid[0]), int(nlc_grid[1])] if uses_vv10 else None,
        "conv_tol": float(conv_tol),
        "max_cycle": int(max_cycle),
        "is_opt": bool(is_opt),
        "compute_gradient": bool(compute_gradient or is_opt),
        "opt_gtol": float(opt_gtol),
        "opt_maxiter": int(opt_maxiter),
        "max_memory_mb": int(max_memory_mb),
        "device_index": int(device_index),
    }

    worker_source = """# Authentic FP64 CUDA GPU4PySCF calculation (never downgrades to CPU).
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

if os.environ.get("CUDA_VISIBLE_DEVICES", "0").strip() in {"", "-1"}:
    raise RuntimeError("CUDA GPU disabled by CUDA_VISIBLE_DEVICES; refusing CPU fallback")

import cupy
import pyscf
from pyscf import gto
import gpu4pyscf
from gpu4pyscf.dft import rks as gpu_rks, uks as gpu_uks
from gpu4pyscf.scf import hf as gpu_hf, uhf as gpu_uhf

BOHR_TO_ANGSTROM = 0.529177210903
spec = json.loads(SPEC_JSON)
n_gpus = cupy.cuda.runtime.getDeviceCount()
if n_gpus < 1:
    raise RuntimeError("No CUDA GPU detected by CuPy; GPU4PySCF refuses CPU downgrade")

dev_idx = int(spec["device_index"])
if dev_idx < 0 or dev_idx >= n_gpus:
    raise RuntimeError(f"Requested CUDA device index {dev_idx} out of range (found {n_gpus})")
cupy.cuda.Device(dev_idx).use()
props = cupy.cuda.runtime.getDeviceProperties(dev_idx)
raw_name = props.get("name", b"unknown")
cuda_device_name = raw_name.decode("utf-8", errors="replace") if isinstance(raw_name, bytes) else str(raw_name)
banner = (
    f"GPU4PySCF {gpu4pyscf.__version__} | PySCF {pyscf.__version__} | "
    f"CuPy {cupy.__version__} | CUDA Device {dev_idx}: {cuda_device_name} | FP64"
)
print(banner, flush=True)

elements = [item[0] for item in spec["atom"]]
init_coords = np.asarray([item[1] for item in spec["atom"]], dtype=np.float64)


def _build_mf(coords_ang):
    atom_spec = [[sym, coords_ang[i].tolist()] for i, sym in enumerate(elements)]
    mol_kwargs = {
        "atom": atom_spec,
        "unit": "Angstrom",
        "basis": spec["basis"],
        "charge": spec["charge"],
        "spin": spec["spin"],
        "max_memory": spec["max_memory_mb"],
        "verbose": 3,
    }
    if spec.get("ecp"):
        mol_kwargs["ecp"] = spec["ecp"]
    mol = gto.M(**mol_kwargs)
    if spec["is_hf"]:
        mf = gpu_uhf.UHF(mol) if spec["unrestricted"] else gpu_hf.RHF(mol)
        mf = mf.density_fit(auxbasis=spec["auxbasis"])
    else:
        mf = (
            gpu_uks.UKS(mol, xc=spec["xc_or_hf"])
            if spec["unrestricted"]
            else gpu_rks.RKS(mol, xc=spec["xc_or_hf"])
        )
        mf = mf.density_fit(auxbasis=spec["auxbasis"])
        mf.grids.atom_grid = tuple(spec["xc_grid"])
        if spec["nlc_grid"] is not None:
            mf.nlcgrids.atom_grid = tuple(spec["nlc_grid"])
    if spec.get("use_sfx2c1e"):
        mf = mf.sfx2c1e()
    mf.conv_tol = float(spec["conv_tol"])
    mf.max_cycle = int(spec["max_cycle"])
    return mol, mf


def _evaluate(coords_ang, need_grad):
    mol, mf = _build_mf(coords_ang)
    energy = float(mf.kernel())
    if not mf.converged or not math.isfinite(energy):
        raise RuntimeError("GPU4PySCF SCF did not converge to a finite FP64 energy")
    s_squared = None
    if spec["unrestricted"]:
        ss, _ = mf.spin_square()
        s_squared = float(ss)
    grad = None
    if need_grad:
        g_raw = mf.nuc_grad_method().kernel()
        grad = np.asarray(cupy.asnumpy(g_raw) if hasattr(g_raw, "device") else g_raw, dtype=np.float64)
        if grad.shape != (mol.natm, 3) or not np.isfinite(grad).all():
            raise RuntimeError("GPU4PySCF returned invalid or nonfinite nuclear gradients")
    return energy, grad, s_squared


started = time.monotonic()
trajectory = []
optimization_evidence = None
final_coords = init_coords.copy()
final_energy = None
final_grad = None
final_s2 = None

if spec["is_opt"]:
    from scipy.optimize import minimize

    def _obj(flat_ang):
        pos = flat_ang.reshape(len(elements), 3)
        e_val, g_val, s2_val = _evaluate(pos, True)
        trajectory.append({
            "coordinates_angstrom": pos.tolist(),
            "energy_hartree": e_val,
            "max_gradient_hartree_per_bohr": float(np.max(np.linalg.norm(g_val, axis=1))),
        })
        return e_val, (g_val / BOHR_TO_ANGSTROM).ravel()

    opt = minimize(
        _obj,
        final_coords.ravel(),
        method="BFGS",
        jac=True,
        options={
            "gtol": float(spec["opt_gtol"]) / (BOHR_TO_ANGSTROM * math.sqrt(3.0)),
            "maxiter": int(spec["opt_maxiter"]),
        },
    )
    final_coords = opt.x.reshape(len(elements), 3)
    final_energy, final_grad, final_s2 = _evaluate(final_coords, True)
    max_force = float(np.max(np.linalg.norm(final_grad, axis=1)))
    if not opt.success or max_force > float(spec["opt_gtol"]):
        raise RuntimeError(
            f"GPU4PySCF BFGS optimization did not converge (success={opt.success}, max_force={max_force:.3e})"
        )
    optimization_evidence = {
        "optimizer": "SciPy BFGS with GPU4PySCF FP64 analytic gradients",
        "converged": True,
        "evaluations": len(trajectory),
        "maximum_atomic_gradient_hartree_per_bohr": max_force,
        "tolerance_hartree_per_bohr": float(spec["opt_gtol"]),
        "optimizer_message": str(opt.message),
    }
else:
    final_energy, final_grad, final_s2 = _evaluate(final_coords, bool(spec["compute_gradient"]))

wall_time = time.monotonic() - started
reference_kind = (
    ("UHF" if spec["unrestricted"] else "RHF")
    if spec["is_hf"]
    else ("UKS" if spec["unrestricted"] else "RKS")
)
payload = {
    "engine": "gpu4pyscf",
    "pyscf_version": str(pyscf.__version__),
    "gpu4pyscf_version": str(gpu4pyscf.__version__),
    "cupy_version": str(cupy.__version__),
    "cuda_device_index": dev_idx,
    "cuda_device_name": cuda_device_name,
    "precision": "FP64",
    "banner": banner,
    "method": spec["requested_method"],
    "functional": spec["xc_or_hf"],
    "reference": reference_kind,
    "basis": spec["basis"],
    "requested_basis": spec.get("requested_basis", spec["basis"]),
    "ecp": spec.get("ecp"),
    "use_sfx2c1e": bool(spec.get("use_sfx2c1e", False)),
    "regime_guards": spec.get("regime_guards"),
    "auxbasis": spec["auxbasis"],
    "xc_grid": spec["xc_grid"] if not spec["is_hf"] else None,
    "nlc_grid": spec["nlc_grid"] if not spec["is_hf"] else None,
    "charge": spec["charge"],
    "multiplicity": spec["multiplicity"],
    "operation": "optimization" if spec["is_opt"] else "single_point",
    "scf_converged": True,
    "converged": True,
    "energy_hartree": float(final_energy),
    "elements": elements,
    "coordinates_angstrom": final_coords.tolist(),
    "gradients_hartree_per_bohr": final_grad.tolist() if final_grad is not None else None,
    "s_squared": final_s2,
    "optimization_performed": bool(spec["is_opt"]),
    "optimization_evidence": optimization_evidence,
    "trajectory": trajectory if spec["is_opt"] else None,
    "wall_time_seconds": round(wall_time, 4),
    "input_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
}
Path(__file__).with_suffix(".result.json").write_text(
    json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8"
)
""".replace("SPEC_JSON", repr(json.dumps(spec)))
    return worker_source, spec


def write_gpu4pyscf_input(
    directory: str | Path,
    elements: Sequence[str],
    coordinates_angstrom: Sequence[Sequence[float]],
    *,
    basin_id: str = "gpu4pyscf_job",
    method: str = "wB97M-V",
    basis_set: str = "def2-SVP",
    charge: int = 0,
    multiplicity: int = 1,
    is_opt: bool = False,
    compute_gradient: bool = True,
    auxbasis: str = DEFAULT_AUXBASIS,
    xc_grid: tuple[int, int] = DEFAULT_XC_GRID,
    nlc_grid: tuple[int, int] = DEFAULT_VV10_NLC_GRID,
    max_memory_mb: int = 8192,
    device_index: int = 0,
) -> Path:
    """Write the GPU4PySCF execution script into `directory` and return its Path."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", basin_id):
        raise ValueError("basin_id must be a safe filename component")
    out_dir = Path(directory).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    script_text, _ = build_gpu4pyscf_script(
        elements,
        coordinates_angstrom,
        method=method,
        basis_set=basis_set,
        charge=charge,
        multiplicity=multiplicity,
        is_opt=is_opt,
        compute_gradient=compute_gradient,
        auxbasis=auxbasis,
        xc_grid=xc_grid,
        nlc_grid=nlc_grid,
        max_memory_mb=max_memory_mb,
        device_index=device_index,
    )
    deck_path = out_dir / f"{basin_id}_gpu4pyscf.py"
    deck_path.write_text(script_text, encoding="utf-8")
    return deck_path


def parse_cuda_device_index(device: str) -> int:
    """Parse `--device cuda` or `--device cuda:N` into a non-negative CUDA ordinal."""
    cleaned = device.strip().lower()
    if cleaned == "cuda":
        return 0
    match = re.fullmatch(r"cuda:(\d+)", cleaned)
    if match is None:
        raise ValueError(f"Unsupported CUDA device specification: {device!r}")
    return int(match.group(1))


@scientific_producer
def execute_gpu4pyscf(
    elements: Sequence[str],
    coordinates_angstrom: Sequence[Sequence[float]],
    *,
    directory: str | Path,
    basin_id: str = "gpu4pyscf_job",
    method: str = "wB97M-V",
    basis_set: str = "def2-SVP",
    charge: int = 0,
    multiplicity: int = 1,
    is_opt: bool = False,
    compute_gradient: bool = True,
    auxbasis: str = DEFAULT_AUXBASIS,
    xc_grid: tuple[int, int] = DEFAULT_XC_GRID,
    nlc_grid: tuple[int, int] = DEFAULT_VV10_NLC_GRID,
    max_memory_mb: int = 8192,
    device: str = "cuda",
    timeout_seconds: float = 1800.0,
    python_executable: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Execute authentic FP64 GPU4PySCF on a real CUDA GPU; fail closed if unavailable."""
    device_index = parse_cuda_device_index(device)
    interpreter = resolve_gpu4pyscf_python(python_executable, env=env)

    work = Path(directory).expanduser().resolve()
    work.mkdir(parents=True, exist_ok=True)
    deck = write_gpu4pyscf_input(
        work,
        elements,
        coordinates_angstrom,
        basin_id=basin_id,
        method=method,
        basis_set=basis_set,
        charge=charge,
        multiplicity=multiplicity,
        is_opt=is_opt,
        compute_gradient=compute_gradient,
        auxbasis=auxbasis,
        xc_grid=xc_grid,
        nlc_grid=nlc_grid,
        max_memory_mb=max_memory_mb,
        device_index=device_index,
    )

    child_env = dict(os.environ if env is None else env)
    child_env.setdefault("OMP_NUM_THREADS", "2")
    child_env.setdefault("PYTHONDONTWRITEBYTECODE", "1")

    completed = subprocess.run(
        [str(interpreter), str(deck)],
        cwd=work,
        env=child_env,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    stdout_path = work / "gpu4pyscf.out"
    stderr_path = work / "stderr.log"
    stdout_path.write_text(completed.stdout or "", encoding="utf-8")
    stderr_path.write_text(completed.stderr or "", encoding="utf-8")

    if completed.returncode != 0:
        err_detail = (completed.stderr or completed.stdout or "").strip()
        if any(
            token in err_detail
            for token in (
                "No CUDA GPU",
                "CUDA GPU disabled",
                "No module named 'gpu4pyscf'",
                "No module named 'cupy'",
                "cudaErrorNoDevice",
                "cudaErrorInsufficientDriver",
            )
        ):
            raise GPU4PySCFUnavailableError(
                f"GPU4PySCF CUDA runtime unavailable (refusing CPU fallback): {err_detail[-500:]}"
            )
        raise RuntimeError(
            f"GPU4PySCF failed with exit code {completed.returncode}; diagnostics in {work}: {err_detail[-500:]}"
        )

    result_path = deck.with_suffix(".result.json")
    if not result_path.is_file():
        raise RuntimeError(f"GPU4PySCF did not produce expected result file: {result_path}")
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    expected_input_sha = _sha256_file(deck)
    if payload.get("input_sha256") != expected_input_sha:
        raise RuntimeError("GPU4PySCF result input_sha256 does not match submitted script")
    if payload.get("scf_converged") is not True or payload.get("converged") is not True:
        raise RuntimeError("GPU4PySCF result lacks explicit SCF convergence verification")
    energy = payload.get("energy_hartree")
    if isinstance(energy, bool) or not isinstance(energy, (int, float)) or not math.isfinite(energy):
        raise RuntimeError("GPU4PySCF returned a nonfinite electronic energy")
    if not payload.get("cuda_device_name") or "GPU4PySCF" not in str(payload.get("banner", "")):
        raise RuntimeError("GPU4PySCF result lacks authentic CUDA device name or banner")

    payload.update({
        "python_executable": str(interpreter),
        "python_executable_sha256": _sha256_file(interpreter),
        "output_file": str(stdout_path),
        "output_sha256": _sha256_file(stdout_path),
        "result_file": str(result_path),
        "result_sha256": _sha256_file(result_path),
        "device": device,
    })
    return payload


__all__ = [
    "DEFAULT_AUXBASIS",
    "DEFAULT_VV10_NLC_GRID",
    "DEFAULT_XC_GRID",
    "GPU4PySCFUnavailableError",
    "VV10_FUNCTIONALS",
    "build_gpu4pyscf_script",
    "execute_gpu4pyscf",
    "normalize_gpu4pyscf_method",
    "parse_cuda_device_index",
    "resolve_gpu4pyscf_python",
    "write_gpu4pyscf_input",
]
