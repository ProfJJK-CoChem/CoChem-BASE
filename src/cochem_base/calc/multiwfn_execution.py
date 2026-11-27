"""Authentic Multiwfn execution adapter (QTAIM topology, NCI/RDG, Mayer BO, ELF).

Resolves real `Multiwfn_noGUI` and `orca_2mkl` binaries, enforces Fortran <80-char
working-path safety, converts `.gbw` wavefunctions via `orca_2mkl <base> -molden`
or ingests `.molden`/`.molden.input`/`.fchk`/`.wfx` directly, verifies the real
`Multiwfn` banner, and emits SHA-256 provenance of all outputs.
"""
from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any, Mapping, Sequence
import uuid

import numpy as np

from cochem_base.core_engine.engine_environment import engine_runtime_environment
from cochem_base.core_engine.scientific_writer import scientific_producer

_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?"
_SUPPORTED_WAVEFUNCTION_SUFFIXES = (".molden.input", ".molden", ".fchk", ".wfx", ".wfn", ".gbw")
_MAX_FORTRAN_PATH_LEN = 79
_DEFAULT_ORCA_2MKL_CANDIDATES = (
    "/home/ansac/.local/share/cochem-topos/workstation-20261008/engines/"
    "orca-native-v1/orca_6_1_1_linux_x86-64_shared_openmpi418/orca_2mkl",
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_float(token: str) -> float:
    value = float(token.replace("D", "E").replace("d", "e"))
    if not math.isfinite(value):
        raise ValueError(f"Nonfinite numeric token in Multiwfn output: {token!r}")
    return value


def _candidate_file(candidate: str | Path | None, *, search_path: str | None = None) -> Path | None:
    if not candidate:
        return None
    raw = str(candidate).strip()
    if not raw:
        return None
    expanded = Path(os.path.expandvars(raw)).expanduser()
    if expanded.is_file():
        # Preserve short symlinks (e.g. engines/mw) because Multiwfn Fortran truncates paths >=80 chars.
        return Path(os.path.abspath(str(expanded)))
    found = shutil.which(raw, path=search_path)
    if found:
        located = Path(os.path.abspath(found))
        if located.is_file():
            return located
    return None


def resolve_multiwfn_executable(
    executable: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> tuple[Path, Path]:
    """Resolve `(Multiwfn_noGUI, Multiwfnpath)` and enforce <80-char Fortran path safety."""
    active_env = os.environ if env is None else env
    search_path = active_env.get("PATH")
    resolved: Path | None = None

    if executable is not None:
        resolved = _candidate_file(executable, search_path=search_path)
        if resolved is None:
            raise FileNotFoundError(f"Requested Multiwfn executable not found: {executable}")
    else:
        candidates: list[str | Path] = []
        mw_dir_env = active_env.get("Multiwfnpath") or active_env.get("MULTIWFNPATH")
        if mw_dir_env:
            mw_dir = Path(os.path.expandvars(mw_dir_env)).expanduser()
            candidates.extend([mw_dir / "Multiwfn_noGUI", mw_dir / "Multiwfn"])
        candidates.append(
            Path.home() / "CoChem_Workstation_Direct" / "engines" / "mw" / "Multiwfn_noGUI"
        )
        for var in ("COCHEM_MULTIWFN_BIN", "MULTIWFN_BIN"):
            if active_env.get(var):
                candidates.append(active_env[var])
        candidates.extend(["Multiwfn_noGUI", "Multiwfn"])
        for cand in candidates:
            resolved = _candidate_file(cand, search_path=search_path)
            if resolved is not None:
                break

    if resolved is None:
        raise FileNotFoundError(
            "Authentic Multiwfn_noGUI executable not found. Configure Multiwfnpath, "
            "~/CoChem_Workstation_Direct/engines/mw/Multiwfn_noGUI, or PATH."
        )
    mw_dir = resolved.parent
    if len(str(mw_dir)) > _MAX_FORTRAN_PATH_LEN:
        raise ValueError(
            f"Multiwfnpath exceeds Fortran 79-char limit ({len(str(mw_dir))} chars): {mw_dir}"
        )
    return resolved, mw_dir


def resolve_orca_2mkl_executable(
    executable: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    """Resolve real `orca_2mkl` executable for `.gbw` -> `.molden.input` conversion."""
    active_env = os.environ if env is None else env
    search_path = active_env.get("PATH")
    if executable is not None:
        resolved = _candidate_file(executable, search_path=search_path)
        if resolved is None:
            raise FileNotFoundError(f"Requested orca_2mkl executable not found: {executable}")
        return resolved

    candidates: list[str | Path] = []
    for var in ("COCHEM_ORCA_2MKL_BIN", "ORCA_2MKL_BIN"):
        if active_env.get(var):
            candidates.append(active_env[var])
    for var in ("ORCA_DIR", "ORCA_PATH"):
        if active_env.get(var):
            candidates.append(Path(os.path.expandvars(active_env[var])).expanduser() / "orca_2mkl")
    for var in ("ORCA_CMD", "COCHEM_ORCA_BIN"):
        if active_env.get(var):
            candidates.append(Path(os.path.expandvars(active_env[var])).expanduser().parent / "orca_2mkl")
    candidates.extend(_DEFAULT_ORCA_2MKL_CANDIDATES)
    candidates.append("orca_2mkl")
    for cand in candidates:
        resolved = _candidate_file(cand, search_path=search_path)
        if resolved is not None:
            return resolved
    raise FileNotFoundError(
        "Authentic orca_2mkl executable not found. Configure ORCA_DIR, ORCA_CMD, or PATH."
    )


def convert_gbw_to_molden(
    gbw_path: str | Path,
    *,
    output_dir: str | Path | None = None,
    orca_2mkl_executable: str | Path | None = None,
    timeout_seconds: float = 120.0,
    env: Mapping[str, str] | None = None,
) -> Path:
    """Convert an ORCA `.gbw` file to `.molden.input` via real `orca_2mkl <base> -molden`."""
    source = Path(gbw_path).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() != ".gbw":
        raise FileNotFoundError(f"Valid ORCA .gbw file required: {gbw_path}")
    mkl_bin = resolve_orca_2mkl_executable(orca_2mkl_executable, env=env)

    work = Path(output_dir).expanduser().resolve() if output_dir else source.parent
    work.mkdir(parents=True, exist_ok=True)
    staged_gbw = work / source.name
    if staged_gbw != source:
        shutil.copy2(source, staged_gbw)

    base = staged_gbw.stem
    child_env = engine_runtime_environment("orca_2mkl", env, executable=mkl_bin)
    completed = subprocess.run(
        [str(mkl_bin), base, "-molden"],
        cwd=work,
        env=child_env,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    molden_path = work / f"{base}.molden.input"
    if completed.returncode != 0 or not molden_path.is_file() or molden_path.stat().st_size == 0:
        raise RuntimeError(
            f"orca_2mkl conversion failed (exit={completed.returncode}): {completed.stderr or completed.stdout}"
        )
    return molden_path


def _extract_multiwfn_banner(text: str) -> dict[str, Any]:
    """Verify authentic Multiwfn banner and version."""
    banner_match = re.search(r"Multiwfn\s*--\s*A Multifunctional Wavefunction Analyzer", text)
    if banner_match is None:
        raise ValueError(
            "Authentic Multiwfn banner was not found in output; refusing unverified data."
        )
    version_match = re.search(r"Version\s+([0-9][^\r\n(]*)", text)
    version = version_match.group(1).strip() if version_match else "unknown"
    return {
        "banner_verified": True,
        "multiwfn_version": version,
        "banner": banner_match.group(0).strip(),
    }


def _short_stage_dir(preferred_dir: Path) -> tuple[Path, bool]:
    """Ensure Multiwfn cwd stays well under Fortran's 80-char path limit."""
    preferred_dir.mkdir(parents=True, exist_ok=True)
    if len(str(preferred_dir)) <= 60:
        return preferred_dir, False
    tmp_root = Path("/tmp") if os.name != "nt" and Path("/tmp").is_dir() else Path(tempfile.gettempdir())
    stage = tmp_root / f"mw_{uuid.uuid4().hex[:8]}"
    stage.mkdir(parents=True, exist_ok=True)
    return stage, True


def _short_wavefunction_name(wavefunction: Path) -> str:
    lower = wavefunction.name.lower()
    if lower.endswith(".molden.input"):
        return "wf.molden.input"
    return f"wf{wavefunction.suffix.lower()}"


def _run_multiwfn_batch(
    wavefunction_path: Path,
    stdin_commands: str,
    *,
    workdir: Path,
    multiwfn_executable: str | Path | None = None,
    timeout_seconds: float = 300.0,
    env: Mapping[str, str] | None = None,
    collect_files: Sequence[str] = (),
) -> dict[str, Any]:
    """Run Multiwfn_noGUI in batch mode inside a Fortran-safe short working path."""
    mw_bin, mw_dir = resolve_multiwfn_executable(multiwfn_executable, env=env)
    stage_dir, is_temp = _short_stage_dir(workdir)
    short_name = _short_wavefunction_name(wavefunction_path)
    staged_wf = stage_dir / short_name
    if staged_wf.resolve() != wavefunction_path.resolve():
        shutil.copy2(wavefunction_path, staged_wf)

    # Clear prior outputs in stage_dir so stale artifacts can never leak across runs
    for artifact_name in ("CPprop.txt", "CPs.txt", "output.txt", *collect_files):
        prior = stage_dir / artifact_name
        if prior.exists():
            prior.unlink()

    child_env = engine_runtime_environment("multiwfn", env, executable=mw_bin)
    child_env["Multiwfnpath"] = str(mw_dir)
    child_env.setdefault("OMP_STACKSIZE", "200M")
    child_env.setdefault("OMP_NUM_THREADS", "2")

    started = time.monotonic()
    try:
        completed = subprocess.run(
            [str(mw_bin), short_name],
            input=stdin_commands,
            cwd=stage_dir,
            env=child_env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        wall_time = time.monotonic() - started
        stdout_text = completed.stdout or ""
        stderr_text = completed.stderr or ""
        banner = _extract_multiwfn_banner(stdout_text)
        if completed.returncode != 0:
            raise RuntimeError(
                f"Multiwfn_noGUI failed (exit={completed.returncode}): {stderr_text[-400:]}"
            )
        collected: dict[str, Path] = {}
        for name in collect_files:
            candidate = stage_dir / name
            if candidate.is_file():
                if is_temp:
                    dest = workdir / name
                    shutil.copy2(candidate, dest)
                    collected[name] = dest
                else:
                    collected[name] = candidate
        return {
            "stdout": stdout_text,
            "stderr": stderr_text,
            "stdout_sha256": _sha256_bytes(stdout_text.encode("utf-8")),
            "wall_time_seconds": round(wall_time, 4),
            "multiwfn_executable": str(mw_bin),
            "multiwfn_path": str(mw_dir),
            "collected_files": collected,
            **banner,
        }
    finally:
        if is_temp and stage_dir.exists():
            shutil.rmtree(stage_dir, ignore_errors=True)


def parse_multiwfn_qtaim(
    stdout_text: str,
    cpprop_text: str | None = None,
    *,
    expected_atoms: int | None = None,
) -> dict[str, Any]:
    """Parse Multiwfn QTAIM critical point counts, Poincare-Hopf invariant, and BCP properties.

    Raises:
        ValueError: If the authentic Multiwfn banner or critical-point summary block is
            missing from `stdout_text`, or if `expected_atoms` is not a positive integer.
    """
    banner = _extract_multiwfn_banner(stdout_text)

    if expected_atoms is not None:
        if isinstance(expected_atoms, bool) or not isinstance(expected_atoms, int) or expected_atoms <= 0:
            raise ValueError(f"expected_atoms must be a positive integer, got {expected_atoms!r}")

    counts_match = re.findall(
        r"\(3,-3\):\s*(\d+),\s*\(3,-1\):\s*(\d+),\s*\(3,\+1\):\s*(\d+),\s*\(3,\+3\):\s*(\d+)",
        stdout_text,
    )
    if not counts_match:
        raise ValueError("Multiwfn QTAIM output missing critical-point summary")
    n_ncp, n_bcp, n_rcp, n_ccp = (int(x) for x in counts_match[-1])

    atom_count: int | None = expected_atoms
    if atom_count is None:
        atom_match = (
            re.search(r"\bAtoms\s*:\s*(\d+)\b", stdout_text)
            or re.search(r"Number\s+of\s+atoms\s*[:=]\s*(\d+)", stdout_text, re.IGNORECASE)
        )
        if atom_match:
            parsed_atoms = int(atom_match.group(1))
            if parsed_atoms > 0:
                atom_count = parsed_atoms

    bcps: list[dict[str, Any]] = []
    all_cps: list[dict[str, Any]] = []

    if cpprop_text:
        blocks = re.split(
            r"-{4,}\s*CP\s+(\d+),\s*Type\s+\(([+-]?\d+,[+-]?\d+)\)\s*-{4,}",
            cpprop_text,
        )
        # blocks layout: [preamble, cp_idx_1, cp_type_1, body_1, ...]
        for pos in range(1, len(blocks) - 2, 3):
            cp_idx = int(blocks[pos])
            cp_type = blocks[pos + 1].replace(" ", "")
            body = blocks[pos + 2]

            def _field(pattern: str) -> float | None:
                m = re.search(pattern, body)
                return _parse_float(m.group(1)) if m else None

            pos_bohr_m = re.search(
                rf"Position\s*\(Bohr\):\s*({_NUMBER})\s+({_NUMBER})\s+({_NUMBER})", body
            )
            pos_ang_m = re.search(
                rf"Position\s*\(Angstrom\):\s*({_NUMBER})\s+({_NUMBER})\s+({_NUMBER})", body
            )
            conn_m = re.search(
                r"Connected atoms:\s*(\d+)\(([A-Za-z]+)\s*\)\s*--\s*(\d+)\(([A-Za-z]+)\s*\)",
                body,
            )
            bonded_atoms = (
                [
                    {"atom_index": int(conn_m.group(1)), "element": conn_m.group(2).strip()},
                    {"atom_index": int(conn_m.group(3)), "element": conn_m.group(4).strip()},
                ]
                if conn_m
                else []
            )
            record = {
                "cp_index": cp_idx,
                "type": f"({cp_type})",
                "position_bohr": (
                    [_parse_float(pos_bohr_m.group(i)) for i in (1, 2, 3)] if pos_bohr_m else None
                ),
                "position_angstrom": (
                    [_parse_float(pos_ang_m.group(i)) for i in (1, 2, 3)] if pos_ang_m else None
                ),
                "bonded_atoms": bonded_atoms,
                "rho": _field(rf"Density of all electrons:\s*({_NUMBER})"),
                "laplacian": _field(rf"Laplacian of electron density:\s*({_NUMBER})"),
                "G": _field(rf"Lagrangian kinetic energy G\(r\):\s*({_NUMBER})"),
                "V": _field(rf"Potential energy density V\(r\):\s*({_NUMBER})"),
                "H": _field(rf"Energy density E\(r\) or H\(r\):\s*({_NUMBER})"),
                "ellipticity": _field(rf"Ellipticity of electron density:\s*({_NUMBER})"),
                "elf": _field(rf"Electron localization function \(ELF\):\s*({_NUMBER})"),
                "sign_lambda2_rho": _field(rf"Sign\(lambda2\)\*rho:\s*({_NUMBER})"),
            }
            all_cps.append(record)
            if cp_type == "3,-1":
                bcps.append(record)

    chi = n_ncp - n_bcp + n_rcp - n_ccp
    ncp_matches_atoms: bool | None = (n_ncp == atom_count) if atom_count is not None else None
    return {
        **banner,
        "n_ncp": n_ncp,
        "n_bcp": n_bcp,
        "n_rcp": n_rcp,
        "n_ccp": n_ccp,
        "atom_count": atom_count,
        "ncp_matches_atoms": ncp_matches_atoms,
        "poincare_hopf_chi": chi,
        "poincare_hopf_satisfied": chi == 1,
        "bcps": bcps,
        "critical_points": all_cps,
        "raw_output_sha256": _sha256_bytes(stdout_text.encode("utf-8")),
        "cpprop_sha256": _sha256_bytes(cpprop_text.encode("utf-8")) if cpprop_text else None,
    }


def parse_multiwfn_nci_output_txt(
    output_txt_path: str | Path,
    *,
    rdg_cutoff: float = 0.5,
    strong_threshold: float = -0.01,
    steric_threshold: float = 0.01,
) -> dict[str, Any]:
    """Parse Multiwfn NCI scatter `output.txt` (`x y z sign(lambda2)*rho RDG`)."""
    path = Path(output_txt_path)
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError(f"Multiwfn NCI scatter output.txt missing or empty: {path}")
    data = np.loadtxt(path, dtype=np.float64)
    if data.ndim == 1:
        data = data.reshape(1, -1)
    if data.shape[1] < 5:
        raise ValueError(f"Unexpected Multiwfn NCI output.txt column count: {data.shape}")

    sign_l2_rho = data[:, 3]
    rdg = data[:, 4]
    finite_mask = np.isfinite(sign_l2_rho) & np.isfinite(rdg)
    sign_l2_rho = sign_l2_rho[finite_mask]
    rdg = rdg[finite_mask]
    total_points = int(sign_l2_rho.size)
    if total_points == 0:
        raise ValueError("Multiwfn NCI output.txt contains zero finite grid points")

    nci_mask = rdg <= rdg_cutoff
    nci_vals = sign_l2_rho[nci_mask]
    strong_count = int(np.count_nonzero(nci_vals < strong_threshold))
    vdw_count = int(np.count_nonzero((nci_vals >= strong_threshold) & (nci_vals <= steric_threshold)))
    steric_count = int(np.count_nonzero(nci_vals > steric_threshold))

    return {
        "rdg_cutoff": float(rdg_cutoff),
        "strong_threshold": float(strong_threshold),
        "steric_threshold": float(steric_threshold),
        "total_grid_points": total_points,
        "nci_grid_points": int(nci_vals.size),
        "strong_attraction_count": strong_count,
        "vdw_count": vdw_count,
        "steric_count": steric_count,
        "min_sign_lambda2_rho": float(np.min(sign_l2_rho)),
        "max_sign_lambda2_rho": float(np.max(sign_l2_rho)),
        "min_rdg": float(np.min(rdg)),
        "mean_nci_sign_lambda2_rho": float(np.mean(nci_vals)) if nci_vals.size else None,
        "output_txt_sha256": _sha256_file(path),
    }


def parse_multiwfn_mayer_bond_orders(stdout_text: str) -> dict[str, Any]:
    """Parse Multiwfn Mayer bond orders and atomic valences (`menu 9 -> 1`)."""
    banner = _extract_multiwfn_banner(stdout_text)
    bond_re = re.compile(
        rf"^\s*#\s*(\d+):\s*(\d+)\(([A-Za-z]+)\s*\)\s+(\d+)\(([A-Za-z]+)\s*\)\s+({_NUMBER})\s*$"
    )
    valence_re = re.compile(
        rf"^\s*Atom\s+(\d+)\(([A-Za-z]+)\s*\)\s*:\s*({_NUMBER})\s+({_NUMBER})\s*$"
    )
    bonds: list[dict[str, Any]] = []
    valences: list[dict[str, Any]] = []
    for line in stdout_text.splitlines():
        bm = bond_re.match(line)
        if bm:
            bonds.append({
                "index": int(bm.group(1)),
                "atom_i": int(bm.group(2)),
                "element_i": bm.group(3).strip(),
                "atom_j": int(bm.group(4)),
                "element_j": bm.group(5).strip(),
                "mayer_bond_order": _parse_float(bm.group(6)),
            })
            continue
        vm = valence_re.match(line)
        if vm:
            valences.append({
                "atom_index": int(vm.group(1)),
                "element": vm.group(2).strip(),
                "total_valence": _parse_float(vm.group(3)),
                "free_valence": _parse_float(vm.group(4)),
            })
    return {
        **banner,
        "mayer_bonds": bonds,
        "mayer_valences": valences,
        "raw_output_sha256": _sha256_bytes(stdout_text.encode("utf-8")),
    }


def _prepare_wavefunction(
    wavefunction_path: str | Path,
    workdir: Path,
    *,
    orca_2mkl_executable: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[Path, str | None]:
    source = Path(wavefunction_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Wavefunction file not found: {wavefunction_path}")
    lower = source.name.lower()
    if not any(lower.endswith(ext) for ext in _SUPPORTED_WAVEFUNCTION_SUFFIXES):
        raise ValueError(
            f"Unsupported wavefunction format {source.name!r}; expected one of {_SUPPORTED_WAVEFUNCTION_SUFFIXES}"
        )
    if lower.endswith(".gbw"):
        converted = convert_gbw_to_molden(
            source, output_dir=workdir, orca_2mkl_executable=orca_2mkl_executable, env=env
        )
        return converted, _sha256_file(source)
    return source, None


def build_multiwfn_qtaim_commands(*, sphere_points: int = 200) -> str:
    """Build Multiwfn QTAIM topology batch stdin commands.

    When ``sphere_points > 0``, runs Multiwfn's nuclear-centered sphere critical-point
    search (``6 -> 11 -> <sphere_points> -> -1 -> -9``) after nuclear/midpoint/triangle/
    pyramid searches so polar and asymmetric covalent bond critical points are located
    reliably and Poincare-Hopf topology closes cleanly.
    """
    if isinstance(sphere_points, bool) or not isinstance(sphere_points, int) or sphere_points < 0:
        raise ValueError(f"sphere_points must be a non-negative integer, got {sphere_points!r}")
    # 2: Topology -> 2 (NCP), 3 (BCP), 4 (RCP), 5 (CCP)
    # [optional 6 (sphere search) -> 11 (<sphere_points>) -> -1 (each nucleus) -> -9 (return)]
    # -> 8 (bond paths), 7->0 (CPprop.txt), 0 (summary/Poincare-Hopf), -10, q
    if sphere_points > 0:
        return f"2\n2\n3\n4\n5\n6\n11\n{int(sphere_points)}\n-1\n-9\n8\n7\n0\n0\n-10\nq\n"
    return "2\n2\n3\n4\n5\n8\n7\n0\n0\n-10\nq\n"


@scientific_producer
def run_multiwfn_qtaim(
    wavefunction_path: str | Path,
    *,
    workdir: str | Path,
    multiwfn_executable: str | Path | None = None,
    orca_2mkl_executable: str | Path | None = None,
    expected_atoms: int | None = None,
    sphere_points: int = 200,
    timeout_seconds: float = 300.0,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Run real Multiwfn QTAIM topology analysis (CPs, Poincare-Hopf, BCP properties)."""
    commands = build_multiwfn_qtaim_commands(sphere_points=sphere_points)
    work = Path(workdir).expanduser().resolve()
    work.mkdir(parents=True, exist_ok=True)
    wf_path, gbw_sha = _prepare_wavefunction(
        wavefunction_path, work, orca_2mkl_executable=orca_2mkl_executable, env=env
    )
    run_info = _run_multiwfn_batch(
        wf_path,
        commands,
        workdir=work,
        multiwfn_executable=multiwfn_executable,
        timeout_seconds=timeout_seconds,
        env=env,
        collect_files=("CPprop.txt",),
    )
    log_path = work / "multiwfn_qtaim.out"
    log_path.write_text(run_info["stdout"], encoding="utf-8")
    cpprop_path = run_info["collected_files"].get("CPprop.txt")
    cpprop_text = cpprop_path.read_text(encoding="utf-8", errors="replace") if cpprop_path else None
    parsed = parse_multiwfn_qtaim(run_info["stdout"], cpprop_text, expected_atoms=expected_atoms)
    parsed.update({
        "engine": "multiwfn",
        "analysis": "qtaim",
        "sphere_points": int(sphere_points),
        "wavefunction_file": str(wf_path),
        "wavefunction_sha256": _sha256_file(wf_path),
        "source_gbw_sha256": gbw_sha,
        "output_file": str(log_path),
        "cpprop_file": str(cpprop_path) if cpprop_path else None,
        "multiwfn_executable": run_info["multiwfn_executable"],
        "wall_time_seconds": run_info["wall_time_seconds"],
    })
    return parsed


@scientific_producer
def run_multiwfn_nci(
    wavefunction_path: str | Path,
    *,
    workdir: str | Path,
    grid_quality: int = 1,
    rdg_cutoff: float = 0.5,
    multiwfn_executable: str | Path | None = None,
    orca_2mkl_executable: str | Path | None = None,
    timeout_seconds: float = 300.0,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Run real Multiwfn NCI/RDG grid analysis and return region counts + statistics."""
    if isinstance(grid_quality, bool) or grid_quality not in (1, 2, 3):
        raise ValueError("Multiwfn NCI grid_quality must be 1 (low), 2 (medium), or 3 (high)")
    work = Path(workdir).expanduser().resolve()
    work.mkdir(parents=True, exist_ok=True)
    wf_path, gbw_sha = _prepare_wavefunction(
        wavefunction_path, work, orca_2mkl_executable=orca_2mkl_executable, env=env
    )
    # 20: Weak interaction -> 1: NCI -> grid_quality -> 2: Output scatter points to output.txt -> 0 -> 0 -> q
    commands = f"20\n1\n{grid_quality}\n2\n0\n0\nq\n"
    run_info = _run_multiwfn_batch(
        wf_path,
        commands,
        workdir=work,
        multiwfn_executable=multiwfn_executable,
        timeout_seconds=timeout_seconds,
        env=env,
        collect_files=("output.txt",),
    )
    log_path = work / "multiwfn_nci.out"
    log_path.write_text(run_info["stdout"], encoding="utf-8")
    scatter_path = run_info["collected_files"].get("output.txt")
    if scatter_path is None:
        raise RuntimeError(f"Multiwfn NCI analysis did not emit output.txt in {work}")
    nci_stats = parse_multiwfn_nci_output_txt(scatter_path, rdg_cutoff=rdg_cutoff)
    return {
        "engine": "multiwfn",
        "analysis": "nci",
        "banner_verified": run_info["banner_verified"],
        "multiwfn_version": run_info["multiwfn_version"],
        "banner": run_info["banner"],
        "grid_quality": grid_quality,
        **nci_stats,
        "wavefunction_file": str(wf_path),
        "wavefunction_sha256": _sha256_file(wf_path),
        "source_gbw_sha256": gbw_sha,
        "output_file": str(log_path),
        "raw_output_sha256": run_info["stdout_sha256"],
        "scatter_file": str(scatter_path),
        "multiwfn_executable": run_info["multiwfn_executable"],
        "wall_time_seconds": run_info["wall_time_seconds"],
    }


@scientific_producer
def run_multiwfn_mayer_bond_orders(
    wavefunction_path: str | Path,
    *,
    workdir: str | Path,
    multiwfn_executable: str | Path | None = None,
    orca_2mkl_executable: str | Path | None = None,
    timeout_seconds: float = 300.0,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Run real Multiwfn Mayer bond order analysis (`menu 9 -> 1`)."""
    work = Path(workdir).expanduser().resolve()
    work.mkdir(parents=True, exist_ok=True)
    wf_path, gbw_sha = _prepare_wavefunction(
        wavefunction_path, work, orca_2mkl_executable=orca_2mkl_executable, env=env
    )
    run_info = _run_multiwfn_batch(
        wf_path,
        "9\n1\nn\n0\nq\n",
        workdir=work,
        multiwfn_executable=multiwfn_executable,
        timeout_seconds=timeout_seconds,
        env=env,
    )
    log_path = work / "multiwfn_mayer.out"
    log_path.write_text(run_info["stdout"], encoding="utf-8")
    parsed = parse_multiwfn_mayer_bond_orders(run_info["stdout"])
    parsed.update({
        "engine": "multiwfn",
        "analysis": "mayer_bond_order",
        "wavefunction_file": str(wf_path),
        "wavefunction_sha256": _sha256_file(wf_path),
        "source_gbw_sha256": gbw_sha,
        "output_file": str(log_path),
        "multiwfn_executable": run_info["multiwfn_executable"],
        "wall_time_seconds": run_info["wall_time_seconds"],
    })
    return parsed


@scientific_producer
def run_multiwfn_analysis(
    wavefunction_path: str | Path,
    *,
    workdir: str | Path,
    analyses: Sequence[str] = ("qtaim", "nci", "mayer_bond_order"),
    nci_grid_quality: int = 1,
    qtaim_sphere_points: int = 200,
    rdg_cutoff: float = 0.5,
    multiwfn_executable: str | Path | None = None,
    orca_2mkl_executable: str | Path | None = None,
    timeout_seconds: float = 300.0,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Unified Multiwfn analysis entrypoint supporting QTAIM, NCI/RDG, Mayer BO, and ELF."""
    work = Path(workdir).expanduser().resolve()
    work.mkdir(parents=True, exist_ok=True)
    wf_path, gbw_sha = _prepare_wavefunction(
        wavefunction_path, work, orca_2mkl_executable=orca_2mkl_executable, env=env
    )
    requested = tuple(dict.fromkeys(item.strip().lower() for item in analyses if item.strip()))
    unknown = set(requested) - {"qtaim", "nci", "mayer_bond_order", "elf"}
    if unknown:
        raise ValueError(f"Unsupported Multiwfn analyses requested: {sorted(unknown)}")
    if not requested:
        raise ValueError("At least one Multiwfn analysis ('qtaim', 'nci', 'mayer_bond_order', 'elf') is required")

    results: dict[str, Any] = {}
    banner_meta: dict[str, Any] = {}
    if "qtaim" in requested or "elf" in requested:
        qtaim = run_multiwfn_qtaim(
            wf_path,
            workdir=work / "qtaim",
            multiwfn_executable=multiwfn_executable,
            sphere_points=qtaim_sphere_points,
            timeout_seconds=timeout_seconds,
            env=env,
        )
        results["qtaim"] = qtaim
        banner_meta = {
            "banner_verified": qtaim["banner_verified"],
            "multiwfn_version": qtaim["multiwfn_version"],
            "banner": qtaim["banner"],
            "multiwfn_executable": qtaim["multiwfn_executable"],
        }
        if "elf" in requested:
            results["elf"] = {
                "bcp_elf_values": [
                    {
                        "cp_index": bcp["cp_index"],
                        "bonded_atoms": bcp["bonded_atoms"],
                        "elf": bcp["elf"],
                    }
                    for bcp in qtaim["bcps"]
                ],
                "source_cpprop_sha256": qtaim["cpprop_sha256"],
            }
    if "nci" in requested:
        nci = run_multiwfn_nci(
            wf_path,
            workdir=work / "nci",
            grid_quality=nci_grid_quality,
            rdg_cutoff=rdg_cutoff,
            multiwfn_executable=multiwfn_executable,
            timeout_seconds=timeout_seconds,
            env=env,
        )
        results["nci"] = nci
        if not banner_meta:
            banner_meta = {
                "banner_verified": nci["banner_verified"],
                "multiwfn_version": nci["multiwfn_version"],
                "banner": nci["banner"],
                "multiwfn_executable": nci["multiwfn_executable"],
            }
    if "mayer_bond_order" in requested:
        mayer = run_multiwfn_mayer_bond_orders(
            wf_path,
            workdir=work / "mayer",
            multiwfn_executable=multiwfn_executable,
            timeout_seconds=timeout_seconds,
            env=env,
        )
        results["mayer_bond_order"] = mayer
        if not banner_meta:
            banner_meta = {
                "banner_verified": mayer["banner_verified"],
                "multiwfn_version": mayer["multiwfn_version"],
                "banner": mayer["banner"],
                "multiwfn_executable": mayer["multiwfn_executable"],
            }

    return {
        "engine": "multiwfn",
        **banner_meta,
        "wavefunction_file": str(wf_path),
        "wavefunction_sha256": _sha256_file(wf_path),
        "source_gbw_sha256": gbw_sha,
        "analyses": list(requested),
        "results": results,
    }


__all__ = [
    "build_multiwfn_qtaim_commands",
    "convert_gbw_to_molden",
    "parse_multiwfn_mayer_bond_orders",
    "parse_multiwfn_nci_output_txt",
    "parse_multiwfn_qtaim",
    "resolve_multiwfn_executable",
    "resolve_orca_2mkl_executable",
    "run_multiwfn_analysis",
    "run_multiwfn_mayer_bond_orders",
    "run_multiwfn_nci",
    "run_multiwfn_qtaim",
]
