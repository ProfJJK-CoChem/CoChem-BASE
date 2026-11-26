"""Authentic NBO 7.0 execution adapter (ORCA 6.1 %nbo and standalone gennbo.i8.exe).

Resolves real NBO 7 binaries, runs authentic ORCA %nbo or standalone gennbo .47
analyses, verifies the NBO 7 banner, extracts NPA charges, Wiberg bond order
matrices, and Second Order Perturbation Theory E(2) interactions, and emits
cryptographic SHA-256 provenance of raw engine outputs.
"""
from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any, Mapping, Sequence

from cochem_base.core_engine.engine_environment import engine_runtime_environment
from cochem_base.core_engine.scientific_writer import scientific_producer

_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?"
_DEFAULT_ORCA_CANDIDATES = (
    "/home/ansac/.local/share/cochem-topos/workstation-20261008/engines/"
    "orca-native-v1/orca_6_1_1_linux_x86-64_shared_openmpi418/orca",
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
        raise ValueError(f"Nonfinite numeric token in NBO 7 output: {token!r}")
    return value


def _candidate_file(candidate: str | Path | None, *, search_path: str | None = None) -> Path | None:
    if not candidate:
        return None
    raw = str(candidate).strip()
    if not raw:
        return None
    expanded = Path(os.path.expandvars(raw)).expanduser()
    if expanded.is_file():
        return expanded.resolve()
    found = shutil.which(raw, path=search_path)
    if found:
        resolved = Path(found).resolve()
        if resolved.is_file():
            return resolved
    return None


def resolve_nbo7_executable(
    executable: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    """Resolve the real NBO 7 ORCA-linked executable (`nbo7.i8.exe`).

    Fails closed with FileNotFoundError when no authentic binary is present.
    """
    active_env = os.environ if env is None else env
    search_path = active_env.get("PATH")
    if executable is not None:
        resolved = _candidate_file(executable, search_path=search_path)
        if resolved is None:
            raise FileNotFoundError(f"Requested NBO 7 executable not found: {executable}")
        return resolved

    candidates: list[str | Path] = []
    for var in ("NBOEXE", "COCHEM_NBO7_BIN", "NBO7_EXE", "NBO7_BIN"):
        if active_env.get(var):
            candidates.append(active_env[var])
    if active_env.get("NBOBIN"):
        nbobin = Path(os.path.expandvars(active_env["NBOBIN"])).expanduser()
        candidates.extend([nbobin / "nbo7.i8.exe", nbobin / "nbo7.i4.exe"])
    candidates.extend([
        Path.home() / "CoChem_Workstation_Direct" / "engines" / "nbo7" / "bin" / "nbo7.i8.exe",
        "nbo7.i8.exe",
        "nbo7",
    ])
    for candidate in candidates:
        resolved = _candidate_file(candidate, search_path=search_path)
        if resolved is not None:
            return resolved
    raise FileNotFoundError(
        "Authentic NBO 7 executable (nbo7.i8.exe) not found. Configure NBOEXE, "
        "~/CoChem_Workstation_Direct/engines/nbo7/bin/nbo7.i8.exe, or PATH."
    )


def resolve_gennbo_executable(
    executable: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    """Resolve the real standalone GENNBO 7 executable (`gennbo.i8.exe`).

    Prefers the i8 binary (matching ORCA 6.1 archive integers) and fails closed
    with FileNotFoundError when missing.
    """
    active_env = os.environ if env is None else env
    search_path = active_env.get("PATH")
    if executable is not None:
        resolved = _candidate_file(executable, search_path=search_path)
        if resolved is None:
            raise FileNotFoundError(f"Requested GENNBO executable not found: {executable}")
        return resolved

    candidates: list[str | Path] = []
    for var in ("COCHEM_GENNBO_I8_BIN", "GENNBO_I8_EXE"):
        if active_env.get(var):
            candidates.append(active_env[var])
    if active_env.get("NBOBIN"):
        nbobin = Path(os.path.expandvars(active_env["NBOBIN"])).expanduser()
        candidates.extend([nbobin / "gennbo.i8.exe", nbobin / "gennbo.i4.exe"])
    if active_env.get("NBOEXE"):
        nbo_dir = Path(os.path.expandvars(active_env["NBOEXE"])).expanduser().parent
        candidates.append(nbo_dir / "gennbo.i8.exe")
    candidates.append(
        Path.home() / "CoChem_Workstation_Direct" / "engines" / "nbo7" / "bin" / "gennbo.i8.exe"
    )
    for var in ("COCHEM_GENNBO_BIN", "GENNBO_EXE"):
        if active_env.get(var):
            candidates.append(active_env[var])
    candidates.extend(["gennbo.i8.exe", "gennbo.i4.exe", "gennbo"])
    for candidate in candidates:
        resolved = _candidate_file(candidate, search_path=search_path)
        if resolved is not None:
            return resolved
    raise FileNotFoundError(
        "Authentic standalone GENNBO 7 executable (gennbo.i8.exe) not found. Configure "
        "NBOBIN/GENNBO_EXE, ~/CoChem_Workstation_Direct/engines/nbo7/bin/gennbo.i8.exe, or PATH."
    )


def resolve_orca_executable(
    executable: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    """Resolve the real ORCA executable for ORCA %nbo runs; fail closed if absent."""
    active_env = os.environ if env is None else env
    search_path = active_env.get("PATH")
    if executable is not None:
        resolved = _candidate_file(executable, search_path=search_path)
        if resolved is None:
            raise FileNotFoundError(f"Requested ORCA executable not found: {executable}")
        return resolved

    candidates: list[str | Path] = []
    for var in ("ORCA_CMD", "COCHEM_ORCA_BIN"):
        if active_env.get(var):
            candidates.append(active_env[var])
    if active_env.get("ORCA_DIR"):
        candidates.append(Path(os.path.expandvars(active_env["ORCA_DIR"])).expanduser() / "orca")
    candidates.extend(_DEFAULT_ORCA_CANDIDATES)
    candidates.append("orca")
    for candidate in candidates:
        resolved = _candidate_file(candidate, search_path=search_path)
        if resolved is not None:
            return resolved
    raise FileNotFoundError(
        "Authentic ORCA executable not found. Configure ORCA_CMD, COCHEM_ORCA_BIN, ORCA_DIR, or PATH."
    )


def _extract_nbo7_banner(text: str) -> dict[str, Any]:
    """Verify authentic NBO 7.x banner and extract program version metadata."""
    header_match = re.search(r"\*+\s*(NBO\s+7\.\d+(?:\.\d+)?)\s*\*+", text)
    cite_match = re.search(r"Cite this program\s*\[(NBO\s+7\.[^\]]+)\]", text)
    if header_match is None and cite_match is None:
        raise ValueError(
            "Authentic NBO 7 banner ('NBO 7.x') was not found in output; refusing unverified data."
        )
    version = cite_match.group(1).strip() if cite_match else header_match.group(1).strip()
    banner = header_match.group(0).strip() if header_match else version
    return {"banner_verified": True, "nbo_version": version, "banner": banner}


def _parse_npa_charges(text: str) -> dict[str, Any]:
    """Parse Summary of Natural Population Analysis table."""
    pattern = re.compile(
        r"Summary of Natural Population Analysis:\s*\n(.*?)(?:\n\s*={10,}\s*\n\s*\*\s*Total\s*\*([^\n]*))",
        re.S,
    )
    match = pattern.search(text)
    if match is None:
        return {"atoms": [], "total_charge": None, "total_electrons": None}

    block = match.group(1)
    total_line = match.group(2)
    row_re = re.compile(
        rf"^\s*([A-Z][a-z]?)\s+(\d+)\s+({_NUMBER})\s+({_NUMBER})\s+({_NUMBER})\s+({_NUMBER})\s+({_NUMBER})\s*$"
    )
    atoms: list[dict[str, Any]] = []
    for line in block.splitlines():
        row = row_re.match(line)
        if row:
            atoms.append({
                "element": row.group(1),
                "atom_index": int(row.group(2)),
                "natural_charge": _parse_float(row.group(3)),
                "core": _parse_float(row.group(4)),
                "valence": _parse_float(row.group(5)),
                "rydberg": _parse_float(row.group(6)),
                "total": _parse_float(row.group(7)),
            })

    total_nums = re.findall(_NUMBER, total_line)
    total_charge = _parse_float(total_nums[0]) if len(total_nums) >= 1 else None
    total_electrons = _parse_float(total_nums[-1]) if len(total_nums) >= 5 else None
    return {
        "atoms": atoms,
        "total_charge": total_charge,
        "total_electrons": total_electrons,
    }


def _parse_wiberg_matrix(text: str, *, bond_threshold: float = 0.05) -> dict[str, Any]:
    """Parse multi-page Wiberg bond index matrix in the NAO basis."""
    marker = "Wiberg bond index matrix in the NAO basis:"
    start = text.find(marker)
    if start == -1:
        return {"atoms": [], "matrix": [], "bonds": [], "totals_by_atom": []}

    section = text[start + len(marker):]
    lines = section.splitlines()
    entries: dict[tuple[int, int], float] = {}
    atom_labels: dict[int, str] = {}
    col_indices: list[int] = []
    seen_header = False

    col_header_re = re.compile(r"^\s*Atom\s+((?:\d+\s*)+)$")
    row_re = re.compile(rf"^\s*(\d+)\.\s*([A-Z][a-z]?)\s+((?:{_NUMBER}\s*)+)$")

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("Wiberg bond index, Totals", "NBI:", "NATURAL BOND ORBITAL")):
            break
        col_match = col_header_re.match(line)
        if col_match:
            col_indices = [int(tok) for tok in col_match.group(1).split()]
            seen_header = True
            continue
        if set(stripped) <= {"-", " "}:
            continue
        row_match = row_re.match(line)
        if row_match and col_indices:
            row_idx = int(row_match.group(1))
            atom_labels[row_idx] = row_match.group(2)
            values = [_parse_float(tok) for tok in row_match.group(3).split()]
            for col_idx, val in zip(col_indices, values):
                entries[(row_idx, col_idx)] = val
            continue
        if seen_header:
            # Non-matching line after table body ends the matrix section.
            break

    if not atom_labels:
        return {"atoms": [], "matrix": [], "bonds": [], "totals_by_atom": []}

    n_atoms = max(atom_labels)
    atoms_ordered = [atom_labels.get(i, "") for i in range(1, n_atoms + 1)]
    matrix: list[list[float]] = [
        [entries.get((i, j), 0.0) for j in range(1, n_atoms + 1)]
        for i in range(1, n_atoms + 1)
    ]
    bonds: list[dict[str, Any]] = []
    for i in range(1, n_atoms + 1):
        for j in range(i + 1, n_atoms + 1):
            order = matrix[i - 1][j - 1]
            if order >= bond_threshold:
                bonds.append({
                    "atom_i": i,
                    "element_i": atoms_ordered[i - 1],
                    "atom_j": j,
                    "element_j": atoms_ordered[j - 1],
                    "bond_order": order,
                })

    # Optional Wiberg totals by atom
    totals: list[dict[str, Any]] = []
    totals_marker = "Wiberg bond index, Totals by atom:"
    t_start = text.find(totals_marker, start)
    if t_start != -1:
        t_lines = text[t_start + len(totals_marker):].splitlines()
        t_row_re = re.compile(rf"^\s*(\d+)\.\s*([A-Z][a-z]?)\s+({_NUMBER})\s*$")
        for line in t_lines:
            s = line.strip()
            if not s or s.startswith("Atom") or set(s) <= {"-", " "}:
                continue
            tm = t_row_re.match(line)
            if tm:
                totals.append({
                    "atom_index": int(tm.group(1)),
                    "element": tm.group(2),
                    "total_bond_index": _parse_float(tm.group(3)),
                })
            elif totals:
                break

    return {
        "atoms": atoms_ordered,
        "matrix": matrix,
        "bonds": bonds,
        "totals_by_atom": totals,
    }


def _parse_e2_perturbation(text: str) -> list[dict[str, Any]]:
    """Parse Second Order Perturbation Theory E(2) donor-acceptor interactions."""
    marker = "SECOND ORDER PERTURBATION THEORY ANALYSIS OF FOCK MATRIX IN NBO BASIS"
    interactions: list[dict[str, Any]] = []
    row_re = re.compile(
        rf"^\s*(\d+)\.\s+(.+?)\s+(\d+)\.\s+(.+?)\s+({_NUMBER})\s+({_NUMBER})\s+({_NUMBER})\s*$"
    )

    search_pos = 0
    while True:
        idx = text.find(marker, search_pos)
        if idx == -1:
            break
        prefix_window = text[max(0, idx - 400):idx].lower()
        if "alpha spin orbitals" in prefix_window:
            spin = "alpha"
        elif "beta spin orbitals" in prefix_window:
            spin = "beta"
        else:
            spin = "closed"

        section_lines = text[idx + len(marker):].splitlines()
        unit_context = ""
        in_table = False
        for line in section_lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(("NATURAL BOND ORBITALS (Summary)", "NATURAL LOCALIZED MOLECULAR ORBITALS", "*******", "$CHOOSE")):
                break
            if set(stripped) <= {"=", " "} and len(stripped) >= 10:
                in_table = True
                continue
            if not in_table:
                continue
            if stripped.lower().startswith(("within unit", "from unit")):
                unit_context = stripped
                continue
            if stripped.lower().startswith("none above threshold"):
                continue
            match = row_re.match(line)
            if match:
                donor_label = " ".join(match.group(2).split())
                acceptor_label = " ".join(match.group(4).split())
                interactions.append({
                    "donor_index": int(match.group(1)),
                    "donor_label": donor_label,
                    "acceptor_index": int(match.group(3)),
                    "acceptor_label": acceptor_label,
                    "e2_kcal_mol": _parse_float(match.group(5)),
                    "energy_diff_au": _parse_float(match.group(6)),
                    "fock_matrix_element_au": _parse_float(match.group(7)),
                    "spin": spin,
                    "unit_context": unit_context,
                })
        search_pos = idx + len(marker)

    return interactions


def parse_nbo7_output(text: str, *, bond_threshold: float = 0.05) -> dict[str, Any]:
    """Parse authentic NBO 7 output text and return structured properties + SHA-256."""
    if not text or not text.strip():
        raise ValueError("NBO 7 output text is empty")
    banner_info = _extract_nbo7_banner(text)
    npa = _parse_npa_charges(text)
    wiberg = _parse_wiberg_matrix(text, bond_threshold=bond_threshold)
    e2_interactions = _parse_e2_perturbation(text)
    if not npa["atoms"]:
        raise ValueError("NBO 7 output contains no Natural Population Analysis summary")
    return {
        "engine": "nbo7",
        **banner_info,
        "npa_charges": npa["atoms"],
        "npa_total_charge": npa["total_charge"],
        "npa_total_electrons": npa["total_electrons"],
        "wiberg_atoms": wiberg["atoms"],
        "wiberg_bond_order_matrix": wiberg["matrix"],
        "wiberg_bonds": wiberg["bonds"],
        "wiberg_totals_by_atom": wiberg["totals_by_atom"],
        "e2_interactions": e2_interactions,
        "raw_output_sha256": _sha256_bytes(text.encode("utf-8")),
    }


def build_orca_nbo7_input(
    elements: Sequence[str],
    coordinates_angstrom: Sequence[Sequence[float]],
    *,
    method: str = "HF",
    basis_set: str = "def2-SVP",
    charge: int = 0,
    multiplicity: int = 1,
    job_name: str = "nbo_job",
    nprocs: int = 1,
    maxcore_mb: int = 1024,
    nbo_keywords: Sequence[str] = ("BNDIDX", "ARCHIVE"),
) -> str:
    """Build an ORCA 6.1 input deck with explicit %nbo NBOKEYLIST directive."""
    if len(elements) != len(coordinates_angstrom) or not elements:
        raise ValueError("Nonempty matching elements and Cartesian coordinates are required")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", job_name):
        raise ValueError("job_name must be a safe filename component")
    if isinstance(nprocs, bool) or nprocs < 1:
        raise ValueError("nprocs must be a positive integer")
    if isinstance(maxcore_mb, bool) or maxcore_mb < 1:
        raise ValueError("maxcore_mb must be a positive integer")
    if isinstance(multiplicity, bool) or multiplicity < 1:
        raise ValueError("multiplicity must be >= 1")

    method_str = " ".join(part for part in (method.strip(), basis_set.strip()) if part)
    if not method_str or any(ch in method_str for ch in "\r\n%#!*"):
        raise ValueError("Invalid ORCA method/basis specification")

    kw_tokens = [kw.strip().upper() for kw in nbo_keywords if kw and kw.strip()]
    if "BNDIDX" not in kw_tokens:
        kw_tokens.insert(0, "BNDIDX")
    if not any(tok.startswith("FILE=") for tok in kw_tokens):
        kw_tokens.append(f"FILE={job_name}")
    nbokeylist = f"$NBO {' '.join(kw_tokens)} $END"

    lines = [f"! {method_str} NBO"]
    if nprocs > 1:
        lines.extend(["%pal", f"  nprocs {nprocs}", "end"])
    lines.extend([
        f"%maxcore {maxcore_mb}",
        "%nbo",
        f'  NBOKEYLIST "{nbokeylist}"',
        "end",
        f"* xyz {charge} {multiplicity}",
    ])
    for sym, xyz in zip(elements, coordinates_angstrom, strict=True):
        if len(xyz) != 3 or not all(math.isfinite(float(v)) for v in xyz):
            raise ValueError("Coordinates must be finite 3D Cartesian vectors")
        lines.append(f"  {sym:<4} {float(xyz[0]):.12f} {float(xyz[1]):.12f} {float(xyz[2]):.12f}")
    lines.append("*")
    lines.append("")
    return "\n".join(lines)


@scientific_producer
def run_orca_nbo7(
    elements: Sequence[str],
    coordinates_angstrom: Sequence[Sequence[float]],
    *,
    workdir: str | Path,
    method: str = "HF",
    basis_set: str = "def2-SVP",
    charge: int = 0,
    multiplicity: int = 1,
    job_name: str = "nbo_job",
    nprocs: int = 1,
    maxcore_mb: int = 1024,
    nbo_keywords: Sequence[str] = ("BNDIDX", "ARCHIVE"),
    timeout_seconds: float = 600.0,
    orca_executable: str | Path | None = None,
    nbo7_executable: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Execute ORCA 6.1 with real NBO 7.0 (`nbo7.i8.exe`) and parse authentic outputs."""
    orca_bin = resolve_orca_executable(orca_executable, env=env)
    nbo7_bin = resolve_nbo7_executable(nbo7_executable, env=env)

    work = Path(workdir).expanduser().resolve()
    work.mkdir(parents=True, exist_ok=True)
    inp_text = build_orca_nbo7_input(
        elements,
        coordinates_angstrom,
        method=method,
        basis_set=basis_set,
        charge=charge,
        multiplicity=multiplicity,
        job_name=job_name,
        nprocs=nprocs,
        maxcore_mb=maxcore_mb,
        nbo_keywords=nbo_keywords,
    )
    inp_path = work / f"{job_name}.inp"
    inp_path.write_text(inp_text, encoding="utf-8")

    child_env = engine_runtime_environment("orca", env, executable=orca_bin)
    child_env["NBOEXE"] = str(nbo7_bin)
    child_env["NBOBIN"] = str(nbo7_bin.parent)

    started = time.monotonic()
    completed = subprocess.run(
        [str(orca_bin), inp_path.name],
        cwd=work,
        env=child_env,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    wall_time = time.monotonic() - started
    out_path = work / f"{job_name}.out"
    err_path = work / f"{job_name}.err"
    out_text = completed.stdout or ""
    out_path.write_text(out_text, encoding="utf-8")
    err_path.write_text(completed.stderr or "", encoding="utf-8")

    if completed.returncode != 0 or "ORCA TERMINATED NORMALLY" not in out_text:
        raise RuntimeError(
            f"ORCA+NBO7 execution failed (exit={completed.returncode}); diagnostics in {work}"
        )

    parsed = parse_nbo7_output(out_text)
    archive_47 = work / f"{job_name}.47"
    gbw_path = work / f"{job_name}.gbw"
    parsed.update({
        "mode": "orca_nbo7",
        "method": method,
        "basis_set": basis_set,
        "charge": charge,
        "multiplicity": multiplicity,
        "workdir": str(work),
        "orca_executable": str(orca_bin),
        "nbo7_executable": str(nbo7_bin),
        "input_file": str(inp_path),
        "output_file": str(out_path),
        "input_sha256": _sha256_file(inp_path),
        "output_sha256": _sha256_file(out_path),
        "archive_47_file": str(archive_47) if archive_47.is_file() else None,
        "archive_47_sha256": _sha256_file(archive_47) if archive_47.is_file() else None,
        "gbw_file": str(gbw_path) if gbw_path.is_file() else None,
        "wall_time_seconds": round(wall_time, 4),
    })
    return parsed


def _ensure_47_keywords(content: str, extra_keywords: Sequence[str]) -> str:
    """Insert requested NBO keywords (e.g. BNDIDX) into a staged .47 $NBO block."""
    needed = [kw.strip().upper() for kw in extra_keywords if kw and kw.strip()]
    if not needed:
        return content

    def _inject(match: re.Match[str]) -> str:
        body = match.group(1)
        upper_tokens = set(body.upper().split())
        additions = [kw for kw in needed if kw not in upper_tokens]
        if not additions:
            return match.group(0)
        return f"$NBO {body.strip()} {' '.join(additions)} $END"

    updated, count = re.subn(r"\$NBO\b(.*?)\$END", _inject, content, count=1, flags=re.I | re.S)
    if count == 0:
        return f"$NBO {' '.join(needed)} $END\n" + content
    return updated


@scientific_producer
def run_gennbo7(
    file47_path: str | Path,
    *,
    workdir: str | Path | None = None,
    nbo_keywords: Sequence[str] = ("BNDIDX",),
    timeout_seconds: float = 300.0,
    gennbo_executable: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Execute standalone `gennbo.i8.exe` on an existing NBO `.47` archive file."""
    gennbo_bin = resolve_gennbo_executable(gennbo_executable, env=env)
    source_47 = Path(file47_path).expanduser().resolve()
    if not source_47.is_file():
        raise FileNotFoundError(f"NBO .47 archive file not found: {file47_path}")

    work = Path(workdir).expanduser().resolve() if workdir else source_47.parent
    work.mkdir(parents=True, exist_ok=True)
    staged_47 = work / (
        source_47.name if source_47.parent != work else f"{source_47.stem}_gennbo.47"
    )
    raw_47_text = source_47.read_text(encoding="utf-8", errors="replace")
    staged_text = _ensure_47_keywords(raw_47_text, nbo_keywords)
    staged_47.write_text(staged_text, encoding="utf-8")

    child_env = engine_runtime_environment("nbo7", env, executable=gennbo_bin)
    child_env["NBOBIN"] = str(gennbo_bin.parent)

    started = time.monotonic()
    completed = subprocess.run(
        [str(gennbo_bin), staged_47.name],
        cwd=work,
        env=child_env,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    wall_time = time.monotonic() - started
    out_path = work / f"{staged_47.stem}.nbo7.out"
    err_path = work / f"{staged_47.stem}.nbo7.err"
    out_text = completed.stdout or ""
    out_path.write_text(out_text, encoding="utf-8")
    err_path.write_text(completed.stderr or "", encoding="utf-8")

    if completed.returncode != 0:
        raise RuntimeError(
            f"GENNBO 7 execution failed (exit={completed.returncode}); diagnostics in {work}"
        )

    parsed = parse_nbo7_output(out_text)
    parsed.update({
        "mode": "standalone_gennbo7",
        "workdir": str(work),
        "gennbo_executable": str(gennbo_bin),
        "source_47_file": str(source_47),
        "source_47_sha256": _sha256_file(source_47),
        "staged_47_file": str(staged_47),
        "staged_47_sha256": _sha256_file(staged_47),
        "output_file": str(out_path),
        "output_sha256": _sha256_file(out_path),
        "wall_time_seconds": round(wall_time, 4),
    })
    return parsed


__all__ = [
    "build_orca_nbo7_input",
    "parse_nbo7_output",
    "resolve_gennbo_executable",
    "resolve_nbo7_executable",
    "resolve_orca_executable",
    "run_gennbo7",
    "run_orca_nbo7",
]
