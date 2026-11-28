"""Pure-stdlib CoChem student handoff builder & verifier (v1 & v2).

Matches `cochem_workstation_job_runner/src/cochem_runner/student_handoff_intake.py`
byte-for-byte on schema constants, geometry/spin physics invariants, security
firewall checks, and `.zip` + `.zip.sha256` packaging:

1. Backward-compatible verification & staging for `cochem.student-conformer-handoff/1`.
2. Generalized creation, sealing, self-verification, and staging for
   `cochem.student-handoff/2`:
   - Elements (11): H, B, C, N, O, F, Si, P, S, Cl, Br
   - Charge in {-2, -1, 0, +1, +2}, multiplicity in {1, 2, 3}
   - 1..64 atoms/frame, 1..256 frames/trajectory
   - workflow_type in {conformer, rxn_profile, nci_dimer, geom_comparison, vpt2_anharmonic}
   - solvation in {gas, pcm, ddcosmo}
   - course_id in {CHEM311, CHEM312, CHEM490, CHEM410, CHEM411}
   - collaborator_institution locked strictly to "Tennessee Tech University"
   - target_continuation in {workstation, colab_gpu, gcp_spot}
   - hessian_calculated (bool) & n_imaginary_modes (int >= 0 or null)
   - full files_sha256 manifest + `<archive>.sha256` sidecar
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
from typing import Any, Mapping, Sequence
import zipfile

SCHEMA_V1 = "cochem.student-conformer-handoff/1"
SCHEMA_V2 = "cochem.student-handoff/2"
SCHEMA = SCHEMA_V2
SUPPORTED_SCHEMAS: tuple[str, ...] = (SCHEMA_V1, SCHEMA_V2)

V1_ALLOWED_ELEMENTS: dict[str, int] = {
    "H": 1,
    "C": 6,
    "N": 7,
    "O": 8,
}

V2_ALLOWED_ELEMENTS: dict[str, int] = {
    "H": 1,
    "B": 5,
    "C": 6,
    "N": 7,
    "O": 8,
    "F": 9,
    "Si": 14,
    "P": 15,
    "S": 16,
    "Cl": 17,
    "Br": 35,
}
ALLOWED = V2_ALLOWED_ELEMENTS

V1_CORE_FILES: frozenset[str] = frozenset(
    {
        "input.xyz",
        "crest_conformers.xyz",
        "crest.log",
        "engines.json",
        "ranking.json",
        "pyscf.json",
        "pyscf.log",
        "refined.xyz",
    }
)

V1_MAX_ATOMS = 16
V1_MIN_ATOMS = 2
V1_MAX_FRAMES = 32
V1_MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
V1_MAX_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
V1_MAX_MEMBERS = 41

V2_MAX_ATOMS = 64
V2_MIN_ATOMS = 1
V2_MAX_FRAMES = 256
V2_MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
V2_MAX_UNCOMPRESSED_BYTES = 128 * 1024 * 1024
V2_MAX_MEMBERS = 512

V2_ALLOWED_WORKFLOW_TYPES: tuple[str, ...] = (
    "conformer",
    "rxn_profile",
    "nci_dimer",
    "geom_comparison",
    "vpt2_anharmonic",
)
V2_ALLOWED_CHARGES: tuple[int, ...] = (-2, -1, 0, 1, 2)
V2_ALLOWED_MULTIPLICITIES: tuple[int, ...] = (1, 2, 3)
V2_ALLOWED_SOLVATIONS: tuple[str, ...] = ("gas", "pcm", "ddcosmo")
V2_ALLOWED_COURSE_IDS: tuple[str, ...] = ("CHEM311", "CHEM312", "CHEM490", "CHEM410", "CHEM411")
V2_ALLOWED_TARGET_CONTINUATIONS: tuple[str, ...] = ("workstation", "colab_gpu", "gcp_spot")


def get_allowed_course_ids() -> tuple[str, ...]:
    """Return allowed course IDs dynamically from CoChem-CURE when available, else the standalone fallback."""
    try:
        from cochem_base.course_loader import get_allowed_course_ids as _loader_allowed_course_ids
    except ImportError:
        return V2_ALLOWED_COURSE_IDS
    try:
        loaded = tuple(str(cid).strip() for cid in _loader_allowed_course_ids() if str(cid).strip())
        return loaded if loaded else V2_ALLOWED_COURSE_IDS
    except Exception:
        return V2_ALLOWED_COURSE_IDS

DEFAULT_COLLABORATOR_INSTITUTION = "Tennessee Tech University"
ALLOWED_COLLABORATOR_INSTITUTIONS: tuple[str, ...] = (DEFAULT_COLLABORATOR_INSTITUTION,)

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")
_CONFLICT_NAME_RE = re.compile(r" \(\d+\)(\.[^.]+)?$")
_SAFE_SLUG_RE = re.compile(r"[^A-Za-z0-9._-]+")
_DLPNO_TOKEN_RE = re.compile(r"dlpno", re.IGNORECASE)
_DLPNO_CONTENT_RE = re.compile(
    r"(?<![A-Za-z])dlpno(?!(?:exclusionfirewall|_allowed|_firewall|_excluded))",
    re.IGNORECASE,
)

# Canonical Pipeline 5.0.0 continuation calculation kinds & aliases,
# kept in lockstep with `cochem_workstation_job_runner` (zero DLPNO).
V2_CANONICAL_CONTINUATION_CALC_KINDS: tuple[str, ...] = (
    "sp",
    "opt",
    "freq",
    "opt_freq",
    "ts_opt",
    "irc",
    "scan",
    "vpt2",
    "revdsd",
    "ccsd",
    "ccsd_t",
    "cbs_extrapolation",
    "led_decomposition",
    "oniom",
    "nmr",
    "td_dft",
    "nbo",
    "aim_qtaim",
    "md_nve_nvt",
    "mlff_mace",
    "xtb_crest",
    "xtb_opt_freq",
)

V2_CONTINUATION_CALC_KIND_ALIASES: dict[str, str] = {
    "single_point": "sp",
    "dft_sp": "sp",
    "orca_sp": "sp",
    "geometry_optimization": "opt",
    "dft_opt": "opt",
    "orca_opt": "opt",
    "frequency": "freq",
    "dft_freq": "freq",
    "orca_freq": "freq",
    "dft_opt_freq": "opt_freq",
    "orca_opt_freq": "opt_freq",
    "ts": "ts_opt",
    "dft_ts_opt": "ts_opt",
    "orca_ts_opt": "ts_opt",
    "orca_irc": "irc",
    "relaxed_scan": "scan",
    "orca_scan": "scan",
    "anharmonic": "vpt2",
    "cfour_vpt2": "vpt2",
    "orca_vpt2": "vpt2",
    "revdsd_opt_freq": "revdsd",
    "revdsd_opt": "revdsd",
    "orca_revdsd": "revdsd",
    "orca_ccsd": "ccsd",
    "cfour_ccsd": "ccsd",
    "ccsdt": "ccsd_t",
    "ccsd(t)": "ccsd_t",
    "orca_ccsdt": "ccsd_t",
    "orca_ccsd_t": "ccsd_t",
    "cfour_ccsdt": "ccsd_t",
    "cfour_ccsd_t": "ccsd_t",
    "cbs": "cbs_extrapolation",
    "led": "led_decomposition",
    "orca_led": "led_decomposition",
    "orca_oniom": "oniom",
    "orca_nmr": "nmr",
    "tddft": "td_dft",
    "orca_tddft": "td_dft",
    "nbo7": "nbo",
    "qtaim": "aim_qtaim",
    "multiwfn_qtaim": "aim_qtaim",
    "md": "md_nve_nvt",
    "mace": "mlff_mace",
    "mlff": "mlff_mace",
    "xtb": "xtb_crest",
    "crest": "xtb_crest",
}

_DLPNO_SCAN_TEXT_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".inp",
        ".orca",
        ".xyz",
        ".json",
        ".yaml",
        ".yml",
        ".txt",
        ".log",
        ".out",
        ".dat",
        ".csv",
        ".md",
        ".cfg",
        ".ini",
    }
)


class HandoffValidationError(ValueError):
    """Raised when a student handoff archive fails schema, physics, or integrity validation."""

    def __init__(self, message: str, *, code: str = "VALIDATION_ERROR") -> None:
        super().__init__(message)
        self.code = code


class HandoffSecurityError(HandoffValidationError):
    """Raised when a student handoff archive violates path/symlink/zip-bomb security checks."""

    def __init__(self, message: str, *, code: str = "SECURITY_ERROR") -> None:
        super().__init__(message, code=code)


@dataclass
class XYZFrame:
    symbols: list[str]
    coords: list[list[float]]
    comment: str
    energy_hartree: float | None
    text: str
    formula: str

    @property
    def n_atoms(self) -> int:
        return len(self.symbols)

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_atoms": self.n_atoms,
            "formula": self.formula,
            "symbols": list(self.symbols),
            "coords": [list(row) for row in self.coords],
            "comment": self.comment,
            "energy_hartree": self.energy_hartree,
            "energy": self.energy_hartree,
            "text": self.text,
        }


@dataclass
class StudentHandoffV2Manifest:
    """Canonical `cochem.student-handoff/2` manifest contract shared with `cochem_workstation_job_runner`."""

    workflow_type: str
    input_name: str
    charge: int
    multiplicity: int
    method: str
    basis: str
    solvation: str
    hessian_calculated: bool
    n_imaginary_modes: int | None
    course_id: str
    target_continuation: str
    primary_xyz: str
    repository: str
    commit: str
    run_id: str
    attempt: str = "1"
    starting_xyz: str = "input.xyz"
    ensemble_xyz: str | None = None
    candidate_count: int = 1
    selected: str | None = None
    student_id: str = "student_unknown"
    collaborator_institution: str = DEFAULT_COLLABORATOR_INSTITUTION
    length_unit: str = "angstrom"
    solvent_name: str | None = None
    continuation_calc_kind: str | None = None
    created_at_utc: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    files_sha256: dict[str, str] = field(default_factory=dict)
    schema: str = SCHEMA_V2

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema"] = SCHEMA_V2
        if not payload["created_at_utc"]:
            payload["created_at_utc"] = _utc_now()
        return payload


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_strict_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _sanitize_slug(raw: str, *, fallback: str = "item", max_len: int = 40) -> str:
    cleaned = _SAFE_SLUG_RE.sub("_", str(raw or "").strip()).strip("._-")
    if not cleaned:
        return fallback
    return cleaned[:max_len]


def compute_hill_formula(symbols: Sequence[str], *, charge: int = 0) -> str:
    counts = Counter(symbols)
    parts: list[str] = []
    if "C" in counts:
        c_n = counts.pop("C")
        parts.append(f"C{c_n if c_n > 1 else ''}")
        if "H" in counts:
            h_n = counts.pop("H")
            parts.append(f"H{h_n if h_n > 1 else ''}")
    for sym in sorted(counts):
        cnt = counts[sym]
        parts.append(f"{sym}{cnt if cnt > 1 else ''}")
    formula = "".join(parts)
    if charge > 0:
        formula += "+" if charge == 1 else f"{charge}+"
    elif charge < 0:
        formula += "-" if charge == -1 else f"{abs(charge)}-"
    return formula


def _assert_no_dlpno(value: str | None, *, field_name: str) -> None:
    """Enforce Pipeline 5.0.0 DLPNOExclusionFirewall locally on student handoffs."""
    if value is not None and _DLPNO_TOKEN_RE.search(str(value)):
        raise HandoffValidationError(
            f"{field_name} {value!r} is forbidden under Pipeline 5.0.0 DLPNOExclusionFirewall; "
            "use canonical CCSD or CCSD(T) instead",
            code="DLPNO_EXCLUDED",
        )


def _assert_no_dlpno_in_metadata(metadata: Any, *, prefix: str = "metadata") -> None:
    if isinstance(metadata, Mapping):
        for key, val in metadata.items():
            key_str = str(key)
            if key_str.lower() in {"dlpno_allowed", "dlpno_firewall", "dlpno_excluded"}:
                continue
            _assert_no_dlpno_in_metadata(val, prefix=f"{prefix}.{key_str}")
    elif isinstance(metadata, (list, tuple)):
        for idx, item in enumerate(metadata):
            _assert_no_dlpno_in_metadata(item, prefix=f"{prefix}[{idx}]")
    elif isinstance(metadata, str):
        if _DLPNO_CONTENT_RE.search(metadata):
            raise HandoffValidationError(
                f"{prefix} contains forbidden DLPNO directive under Pipeline 5.0.0 DLPNOExclusionFirewall; "
                "use canonical CCSD or CCSD(T) instead",
                code="DLPNO_EXCLUDED",
            )


def _assert_no_dlpno_in_file_bytes(member_name: str, data: bytes) -> None:
    suffix = PurePosixPath(member_name).suffix.lower()
    if suffix and suffix not in _DLPNO_SCAN_TEXT_EXTENSIONS:
        return
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return
    if _DLPNO_CONTENT_RE.search(text):
        raise HandoffValidationError(
            f"Archive member {member_name!r} contains forbidden DLPNO directive under Pipeline 5.0.0 "
            "DLPNOExclusionFirewall; use canonical CCSD or CCSD(T) instead",
            code="DLPNO_EXCLUDED",
        )


def normalize_continuation_calc_kind(kind: str) -> str:
    """Validate and normalize `continuation_calc_kind` in lockstep with `cochem_workstation_job_runner`."""
    if not isinstance(kind, str) or not kind.strip():
        raise HandoffValidationError(
            "continuation_calc_kind must be null or a non-empty string",
            code="SCHEMA_INVALID",
        )
    _assert_no_dlpno(kind, field_name="continuation_calc_kind")
    cleaned = kind.strip().lower().replace("-", "_").replace(" ", "_")
    resolved = V2_CONTINUATION_CALC_KIND_ALIASES.get(cleaned, cleaned)
    _assert_no_dlpno(resolved, field_name="continuation_calc_kind")
    if resolved not in V2_CANONICAL_CONTINUATION_CALC_KINDS:
        raise HandoffValidationError(
            f"Unsupported continuation_calc_kind {kind!r}; expected one of "
            f"{V2_CANONICAL_CONTINUATION_CALC_KINDS} (or aliases such as dft_opt_freq, single_point, dft_sp, revdsd)",
            code="SCHEMA_INVALID",
        )
    return resolved


def validate_collaborator_institution(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HandoffValidationError(
            "collaborator_institution must be a non-empty string",
            code="INSTITUTION_INVALID",
        )
    cleaned = value.strip()
    if cleaned not in ALLOWED_COLLABORATOR_INSTITUTIONS:
        raise HandoffValidationError(
            f"Unsupported collaborator_institution {cleaned!r}; must be {DEFAULT_COLLABORATOR_INSTITUTION!r}",
            code="INSTITUTION_INVALID",
        )
    return cleaned


def _validate_member_relpath(name: str, *, allow_dir: bool = False) -> str:
    if not isinstance(name, str) or not name:
        raise HandoffSecurityError("Empty archive member path is forbidden", code="ZIP_SLIP")
    if "\x00" in name:
        raise HandoffSecurityError(f"NUL byte in archive member path: {name!r}", code="ZIP_SLIP")
    if "\\" in name:
        raise HandoffSecurityError(f"Backslash path separator forbidden in archive member: {name!r}", code="ZIP_SLIP")
    if name.startswith("/") or _WINDOWS_DRIVE_RE.match(name):
        raise HandoffSecurityError(f"Absolute or drive-qualified path forbidden in archive: {name!r}", code="ZIP_SLIP")
    is_dir = name.endswith("/")
    if is_dir and not allow_dir:
        raise HandoffSecurityError(f"Directory entry not allowed where file expected: {name!r}", code="ZIP_SLIP")
    trimmed = name[:-1] if is_dir else name
    parts = trimmed.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise HandoffSecurityError(
            f"Path traversal or empty path segment forbidden in archive: {name!r}",
            code="ZIP_SLIP",
        )
    norm = PurePosixPath(*parts).as_posix()
    leaf = parts[-1]
    if " (1)" in leaf or "(1)." in leaf or _CONFLICT_NAME_RE.search(leaf):
        raise HandoffSecurityError(
            f"HC-4 conflict filename forbidden in handoff archive: {name!r}",
            code="HC4_CONFLICT_NAME",
        )
    return norm + ("/" if is_dir else "")


def _inspect_zip_safety(
    archive: zipfile.ZipFile,
    *,
    max_members: int,
    max_uncompressed_bytes: int,
) -> tuple[list[zipfile.ZipInfo], set[str]]:
    infos = archive.infolist()
    if len(infos) == 0 or len(infos) > max_members:
        raise HandoffSecurityError(
            f"Archive member count {len(infos)} outside allowed range 1..{max_members}",
            code="ARCHIVE_LIMIT_EXCEEDED",
        )
    seen_names: set[str] = set()
    file_names: set[str] = set()
    total_uncompressed = 0

    for info in infos:
        raw_name = info.filename
        if raw_name in seen_names:
            raise HandoffSecurityError(f"Duplicate ZIP member name: {raw_name!r}", code="DUPLICATE_MEMBER")
        seen_names.add(raw_name)

        unix_mode = (info.external_attr >> 16) & 0o170000
        if unix_mode == stat.S_IFLNK:
            raise HandoffSecurityError(
                f"Symlink entry forbidden in ZIP archive: {raw_name!r}",
                code="SYMLINK_FORBIDDEN",
            )

        safe_name = _validate_member_relpath(raw_name, allow_dir=True)
        if safe_name != raw_name:
            raise HandoffSecurityError(
                f"Non-canonical ZIP member path {raw_name!r} (normalized {safe_name!r})",
                code="ZIP_SLIP",
            )
        if info.file_size < 0:
            raise HandoffSecurityError(f"Negative file size for member {raw_name!r}", code="ARCHIVE_LIMIT_EXCEEDED")
        total_uncompressed += int(info.file_size)
        if total_uncompressed > max_uncompressed_bytes:
            raise HandoffSecurityError(
                f"Uncompressed archive size exceeds limit ({max_uncompressed_bytes} bytes)",
                code="ARCHIVE_LIMIT_EXCEEDED",
            )
        if not info.is_dir():
            file_names.add(raw_name)

    return infos, file_names


def parse_xyz_frames(
    text: str,
    *,
    allowed_elements: Mapping[str, int] = V2_ALLOWED_ELEMENTS,
    min_atoms: int = V2_MIN_ATOMS,
    max_atoms: int = V2_MAX_ATOMS,
    max_frames: int = V2_MAX_FRAMES,
    charge: int = 0,
    multiplicity: int = 1,
    require_energy: bool = False,
    check_electron_parity: bool = True,
) -> list[XYZFrame]:
    """Parse one or more XYZ frames and verify stoichiometry, finite coords, and spin parity."""
    lines = text.strip().splitlines()
    offset = 0
    parsed: list[XYZFrame] = []

    while offset < len(lines):
        try:
            n_atoms = int(lines[offset].strip())
        except ValueError as exc:
            raise HandoffValidationError(
                f"Invalid XYZ atom count line at offset {offset}: {lines[offset]!r}",
                code="XYZ_INVALID",
            ) from exc

        end = offset + n_atoms + 2
        if not (min_atoms <= n_atoms <= max_atoms):
            raise HandoffValidationError(
                f"Atom count {n_atoms} outside allowed range {min_atoms}..{max_atoms}",
                code="XYZ_ATOM_LIMIT",
            )
        if end > len(lines):
            raise HandoffValidationError(
                f"Truncated XYZ frame at offset {offset}: expected {n_atoms} atoms",
                code="XYZ_TRUNCATED",
            )
        if len(parsed) >= max_frames:
            raise HandoffValidationError(
                f"XYZ trajectory exceeds maximum frame limit of {max_frames}",
                code="XYZ_FRAME_LIMIT",
            )

        comment = lines[offset + 1]
        symbols: list[str] = []
        coords: list[list[float]] = []
        for row in lines[offset + 2 : end]:
            tokens = row.split()
            if len(tokens) != 4:
                raise HandoffValidationError(
                    f"Expected 4 tokens (symbol x y z) in XYZ row, got: {row!r}",
                    code="XYZ_INVALID",
                )
            sym = tokens[0]
            if sym not in allowed_elements:
                raise HandoffValidationError(
                    f"Disallowed element symbol {sym!r}; allowed: {sorted(allowed_elements)}",
                    code="ELEMENT_NOT_ALLOWED",
                )
            try:
                xyz = [float(v) for v in tokens[1:4]]
            except ValueError as exc:
                raise HandoffValidationError(f"Non-numeric XYZ coordinate in row: {row!r}", code="XYZ_INVALID") from exc
            if not all(math.isfinite(v) for v in xyz):
                raise HandoffValidationError(f"Non-finite XYZ coordinate in row: {row!r}", code="XYZ_INVALID")
            symbols.append(sym)
            coords.append(xyz)

        if check_electron_parity:
            n_electrons = sum(allowed_elements[s] for s in symbols) - charge
            unpaired = multiplicity - 1
            if n_electrons < 1 or n_electrons < unpaired:
                raise HandoffValidationError(
                    f"Unphysical electron count {n_electrons} for charge={charge}, multiplicity={multiplicity}",
                    code="ELECTRON_PARITY_MISMATCH",
                )
            if (n_electrons % 2) != (unpaired % 2):
                raise HandoffValidationError(
                    f"Electron count {n_electrons} incompatible with charge={charge}, multiplicity={multiplicity}",
                    code="ELECTRON_PARITY_MISMATCH",
                )

        energy_val: float | None = None
        comment_tokens = comment.split()
        if require_energy:
            if not comment_tokens:
                raise HandoffValidationError(
                    "Missing required energy value on XYZ comment line",
                    code="XYZ_ENERGY_MISSING",
                )
            try:
                energy_val = float(comment_tokens[0])
            except ValueError as exc:
                raise HandoffValidationError(
                    f"Invalid numeric energy on XYZ comment line: {comment!r}",
                    code="XYZ_ENERGY_INVALID",
                ) from exc
            if not math.isfinite(energy_val):
                raise HandoffValidationError("Non-finite energy on XYZ comment line", code="XYZ_ENERGY_INVALID")
        elif comment_tokens:
            try:
                maybe_e = float(comment_tokens[0])
                if math.isfinite(maybe_e):
                    energy_val = maybe_e
            except ValueError:
                energy_val = None

        frame_text = "\n".join(lines[offset:end]) + "\n"
        parsed.append(
            XYZFrame(
                symbols=symbols,
                coords=coords,
                comment=comment,
                energy_hartree=energy_val,
                text=frame_text,
                formula=compute_hill_formula(symbols, charge=charge),
            )
        )
        offset = end

    if not parsed:
        raise HandoffValidationError("Empty XYZ content", code="XYZ_EMPTY")
    return parsed


def frames(
    text: str,
    *,
    energy: bool = False,
    charge: int = 0,
    multiplicity: int = 1,
    allowed_elements: Mapping[str, int] = V2_ALLOWED_ELEMENTS,
) -> list[dict[str, Any]]:
    """Parse XYZ trajectory frames as dictionaries (generalized v2 bounds by default)."""
    parsed = parse_xyz_frames(
        text,
        allowed_elements=allowed_elements,
        min_atoms=V2_MIN_ATOMS,
        max_atoms=V2_MAX_ATOMS,
        max_frames=V2_MAX_FRAMES,
        charge=charge,
        multiplicity=multiplicity,
        require_energy=energy,
    )
    return [f.to_dict() for f in parsed]


def read_input(path: Path | str, *, charge: int = 0, multiplicity: int = 1) -> dict[str, Any]:
    """Read and validate a single-frame starting XYZ file under v2 bounds."""
    p = Path(path)
    if not p.is_file() or p.is_symlink():
        raise HandoffValidationError(f"Starting XYZ must be a regular file: {p}", code="XYZ_INVALID")
    if p.stat().st_size > 256 * 1024:
        raise HandoffValidationError("Starting XYZ exceeds 256 KiB limit", code="XYZ_INVALID")
    rows = frames(p.read_text(encoding="utf-8"), charge=charge, multiplicity=multiplicity)
    if len(rows) != 1:
        raise HandoffValidationError("Supply exactly one starting geometry", code="XYZ_INVALID")
    return rows[0]


def _check_gradient(gradient: Any, n_atoms: int) -> None:
    if not isinstance(gradient, list) or len(gradient) != n_atoms:
        raise HandoffValidationError("Invalid gradient dimensions", code="GRADIENT_INVALID")
    for row in gradient:
        if (
            not isinstance(row, list)
            or len(row) != 3
            or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v)) for v in row)
        ):
            raise HandoffValidationError("Invalid or non-finite gradient row", code="GRADIENT_INVALID")


def parse_sha256_sidecar(sidecar_path: Path | str, *, expected_filename: str | None = None) -> str:
    """Strictly parse a `.zip.sha256` sidecar file (`<64-hex>  <filename>` or `<64-hex>`)."""
    p = Path(sidecar_path)
    try:
        raw = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise HandoffValidationError(f"Unreadable SHA-256 sidecar {p}: {exc}", code="SIDECAR_MALFORMED") from exc

    non_empty = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if len(non_empty) != 1:
        raise HandoffValidationError(
            f"Expected exactly one non-empty line in SHA-256 sidecar {p.name}, got {len(non_empty)}",
            code="SIDECAR_MALFORMED",
        )
    line = non_empty[0]
    parts = line.split(None, 1)
    digest_hex = parts[0].lower()
    if not _HEX64_RE.fullmatch(digest_hex):
        raise HandoffValidationError(
            f"Corrupted SHA-256 digest in sidecar {p.name}: {parts[0]!r}",
            code="SIDECAR_MALFORMED",
        )
    if len(parts) == 2 and expected_filename is not None:
        recorded_name = parts[1].strip()
        if recorded_name.startswith("*"):
            recorded_name = recorded_name[1:]
        if Path(recorded_name).name != expected_filename:
            raise HandoffValidationError(
                f"Sidecar {p.name} filename {recorded_name!r} does not match archive {expected_filename!r}",
                code="SIDECAR_FILENAME_MISMATCH",
            )
    return digest_hex


def _stage_verified_archive(
    archive: zipfile.ZipFile,
    destination: Path,
    archive_hash: str,
    file_names: set[str],
    member_checksums: Mapping[str, str],
) -> Path:
    """Atomically stage verified archive members into `<destination>/<archive_hash>` without zip-slip."""
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / archive_hash

    with tempfile.TemporaryDirectory(dir=destination) as tmp:
        stage = Path(tmp) / "contents"
        stage.mkdir(parents=True, exist_ok=True)
        stage_resolved = stage.resolve()

        for name in sorted(file_names):
            _validate_member_relpath(name, allow_dir=False)
            out = (stage / name).resolve()
            try:
                out.relative_to(stage_resolved)
            except ValueError as exc:
                raise HandoffSecurityError(f"Staged path escaped staging root: {name!r}", code="ZIP_SLIP") from exc
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(archive.read(name))

        if not target.exists() and not target.is_symlink():
            try:
                stage.rename(target)
            except OSError:
                if not target.exists():
                    raise

    if target.is_symlink() or not target.is_dir():
        raise HandoffSecurityError("Expected a regular staging directory", code="STAGE_SYMLINK")

    for name, expected_sha in member_checksums.items():
        staged_file = target / name
        if not staged_file.is_file() or staged_file.is_symlink():
            raise HandoffValidationError(
                f"Existing staged directory missing or symlinked member {name!r}",
                code="EXISTING_STAGE_MISMATCH",
            )
        if sha256_bytes(staged_file.read_bytes()) != expected_sha:
            raise HandoffValidationError(
                f"Existing staged directory member {name!r} differs on disk",
                code="EXISTING_STAGE_MISMATCH",
            )
    staged_manifest = target / "handoff.json"
    if (
        not staged_manifest.is_file()
        or staged_manifest.is_symlink()
        or staged_manifest.read_bytes() != archive.read("handoff.json")
    ):
        raise HandoffValidationError(
            "Existing staged handoff.json differs on disk",
            code="EXISTING_STAGE_MISMATCH",
        )
    return target


def validate_v2_manifest_fields(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Validate all schema-level fields of a `cochem.student-handoff/2` manifest."""
    if receipt.get("schema") != SCHEMA_V2:
        raise HandoffValidationError(
            f"Expected schema {SCHEMA_V2!r}, got {receipt.get('schema')!r}",
            code="SCHEMA_INVALID",
        )

    workflow_type = receipt.get("workflow_type")
    if workflow_type not in V2_ALLOWED_WORKFLOW_TYPES:
        raise HandoffValidationError(
            f"Invalid workflow_type {workflow_type!r}; expected one of {V2_ALLOWED_WORKFLOW_TYPES}",
            code="SCHEMA_INVALID",
        )

    charge = receipt.get("charge")
    if not _is_strict_int(charge) or charge not in V2_ALLOWED_CHARGES:
        raise HandoffValidationError(
            f"Invalid charge {charge!r}; expected one of {V2_ALLOWED_CHARGES}",
            code="SCHEMA_INVALID",
        )

    multiplicity = receipt.get("multiplicity")
    if not _is_strict_int(multiplicity) or multiplicity not in V2_ALLOWED_MULTIPLICITIES:
        raise HandoffValidationError(
            f"Invalid multiplicity {multiplicity!r}; expected one of {V2_ALLOWED_MULTIPLICITIES}",
            code="SCHEMA_INVALID",
        )

    if receipt.get("length_unit") != "angstrom":
        raise HandoffValidationError("length_unit must be 'angstrom'", code="SCHEMA_INVALID")

    method = receipt.get("method")
    basis = receipt.get("basis")
    if not isinstance(method, str) or not method.strip():
        raise HandoffValidationError("method must be a non-empty string", code="SCHEMA_INVALID")
    if not isinstance(basis, str) or not basis.strip():
        raise HandoffValidationError("basis must be a non-empty string", code="SCHEMA_INVALID")
    _assert_no_dlpno(method, field_name="method")
    _assert_no_dlpno(basis, field_name="basis")

    solvation = receipt.get("solvation")
    if solvation not in V2_ALLOWED_SOLVATIONS:
        raise HandoffValidationError(
            f"Invalid solvation {solvation!r}; expected one of {V2_ALLOWED_SOLVATIONS}",
            code="SCHEMA_INVALID",
        )

    solvent_name = receipt.get("solvent_name")
    if solvent_name is not None and (not isinstance(solvent_name, str) or not solvent_name.strip()):
        raise HandoffValidationError("solvent_name must be null or a non-empty string", code="SCHEMA_INVALID")

    hessian_calculated = receipt.get("hessian_calculated")
    if not isinstance(hessian_calculated, bool):
        raise HandoffValidationError("hessian_calculated must be a boolean", code="SCHEMA_INVALID")

    n_imag = receipt.get("n_imaginary_modes")
    if hessian_calculated:
        if not _is_strict_int(n_imag) or n_imag < 0:
            raise HandoffValidationError(
                "n_imaginary_modes must be a non-negative integer when hessian_calculated is True",
                code="SCHEMA_INVALID",
            )
    else:
        if n_imag is not None:
            raise HandoffValidationError(
                "n_imaginary_modes must be null when hessian_calculated is False",
                code="SCHEMA_INVALID",
            )

    allowed_course_ids = get_allowed_course_ids()
    course_id = receipt.get("course_id")
    if course_id not in allowed_course_ids:
        raise HandoffValidationError(
            f"Invalid course_id {course_id!r}; expected one of {allowed_course_ids}",
            code="SCHEMA_INVALID",
        )

    institution = validate_collaborator_institution(
        receipt.get("collaborator_institution", DEFAULT_COLLABORATOR_INSTITUTION)
    )

    target_continuation = receipt.get("target_continuation")
    if target_continuation not in V2_ALLOWED_TARGET_CONTINUATIONS:
        raise HandoffValidationError(
            f"Invalid target_continuation {target_continuation!r}; expected one of {V2_ALLOWED_TARGET_CONTINUATIONS}",
            code="SCHEMA_INVALID",
        )

    candidate_count = receipt.get("candidate_count", 1)
    if not _is_strict_int(candidate_count) or not (1 <= candidate_count <= V2_MAX_FRAMES):
        raise HandoffValidationError(
            f"candidate_count must be an integer in 1..{V2_MAX_FRAMES}, got {candidate_count!r}",
            code="SCHEMA_INVALID",
        )

    commit = str(receipt.get("commit") or "")
    if not _HEX40_RE.fullmatch(commit):
        raise HandoffValidationError(
            f"commit must be a 40-char lowercase hex SHA, got {commit!r}",
            code="SCHEMA_INVALID",
        )

    for req_str_key in ("input_name", "primary_xyz", "starting_xyz", "repository", "run_id", "attempt"):
        val = receipt.get(req_str_key)
        if not isinstance(val, str) or not val.strip():
            raise HandoffValidationError(f"{req_str_key} must be a non-empty string", code="SCHEMA_INVALID")

    starting_xyz = _validate_member_relpath(str(receipt["starting_xyz"]), allow_dir=False)
    primary_xyz = _validate_member_relpath(str(receipt["primary_xyz"]), allow_dir=False)

    ensemble_xyz_raw = receipt.get("ensemble_xyz")
    ensemble_xyz = None
    if ensemble_xyz_raw is not None:
        ensemble_xyz = _validate_member_relpath(str(ensemble_xyz_raw), allow_dir=False)

    selected_raw = receipt.get("selected")
    selected = None
    if selected_raw is not None:
        selected = _validate_member_relpath(str(selected_raw), allow_dir=False)

    cont_kind = receipt.get("continuation_calc_kind")
    if cont_kind is not None:
        cont_kind = normalize_continuation_calc_kind(cont_kind)

    metadata = receipt.get("metadata")
    if metadata is not None:
        _assert_no_dlpno_in_metadata(metadata)

    return {
        "workflow_type": workflow_type,
        "charge": charge,
        "multiplicity": multiplicity,
        "method": method.strip(),
        "basis": basis.strip(),
        "solvation": solvation,
        "solvent_name": solvent_name.strip() if isinstance(solvent_name, str) else None,
        "hessian_calculated": hessian_calculated,
        "n_imaginary_modes": n_imag,
        "course_id": course_id,
        "collaborator_institution": institution,
        "target_continuation": target_continuation,
        "candidate_count": candidate_count,
        "commit": commit,
        "starting_xyz": starting_xyz,
        "primary_xyz": primary_xyz,
        "ensemble_xyz": ensemble_xyz,
        "selected": selected,
        "continuation_calc_kind": cont_kind,
    }


def _verify_v1_contents(
    archive: zipfile.ZipFile,
    archive_path: Path,
    archive_hash: str,
    receipt: dict[str, Any],
    destination: Path | None,
) -> dict[str, Any]:
    if archive_path.stat().st_size > V1_MAX_ARCHIVE_BYTES:
        raise HandoffSecurityError("v1 handoff archive exceeds 32 MiB", code="ARCHIVE_LIMIT_EXCEEDED")

    infos, file_names = _inspect_zip_safety(
        archive,
        max_members=V1_MAX_MEMBERS,
        max_uncompressed_bytes=V1_MAX_UNCOMPRESSED_BYTES,
    )
    if len(file_names) != len(infos):
        raise HandoffValidationError("v1 handoff archive must not contain bare directory entries", code="SCHEMA_INVALID")

    n = receipt.get("candidate_count")
    if receipt.get("schema") != SCHEMA_V1 or not _is_strict_int(n) or not (1 <= n <= V1_MAX_FRAMES):
        raise HandoffValidationError("Unrecognized v1 handoff schema or candidate_count", code="SCHEMA_INVALID")
    if (
        receipt.get("charge") != 0
        or receipt.get("multiplicity") != 1
        or receipt.get("length_unit") != "angstrom"
        or not _HEX40_RE.fullmatch(str(receipt.get("commit") or ""))
    ):
        raise HandoffValidationError("Invalid v1 molecular state, length_unit, or commit SHA", code="SCHEMA_INVALID")

    isomers = [f"isomers/crest-{i:03}.xyz" for i in range(1, n + 1)]
    expected = V1_CORE_FILES | set(isomers)
    checksums = receipt.get("files_sha256")
    if not isinstance(checksums, dict) or set(checksums) != expected or file_names != (expected | {"handoff.json"}):
        raise HandoffValidationError("Unexpected, duplicate, or missing v1 archive members", code="INVENTORY_MISMATCH")

    normalized_checksums: dict[str, str] = {}
    for name in sorted(expected):
        expected_sha = checksums[name]
        if not isinstance(expected_sha, str) or not _HEX64_RE.fullmatch(expected_sha.lower()):
            raise HandoffValidationError(f"Malformed SHA-256 in files_sha256 for {name}", code="MEMBER_SHA256_MISMATCH")
        actual_sha = sha256_bytes(archive.read(name))
        if actual_sha != expected_sha.lower():
            raise HandoffValidationError(f"SHA-256 mismatch for {name}", code="MEMBER_SHA256_MISMATCH")
        normalized_checksums[name] = expected_sha.lower()

    try:
        starting_text = archive.read("input.xyz").decode("ascii")
        native_text = archive.read("crest_conformers.xyz").decode("ascii")
        refined_text = archive.read("refined.xyz").decode("ascii")
    except UnicodeDecodeError as exc:
        raise HandoffValidationError(f"Non-ASCII XYZ file in v1 archive: {exc}", code="XYZ_INVALID") from exc

    starting = parse_xyz_frames(
        starting_text,
        allowed_elements=V1_ALLOWED_ELEMENTS,
        min_atoms=V1_MIN_ATOMS,
        max_atoms=V1_MAX_ATOMS,
        max_frames=V1_MAX_FRAMES,
        charge=0,
        multiplicity=1,
        require_energy=False,
    )
    native = parse_xyz_frames(
        native_text,
        allowed_elements=V1_ALLOWED_ELEMENTS,
        min_atoms=V1_MIN_ATOMS,
        max_atoms=V1_MAX_ATOMS,
        max_frames=V1_MAX_FRAMES,
        charge=0,
        multiplicity=1,
        require_energy=True,
    )
    ranking = json.loads(archive.read("ranking.json"))
    candidates = ranking.get("candidates")
    if (
        len(starting) != 1
        or len(native) != n
        or not isinstance(candidates, list)
        or len(candidates) != n
        or [c.get("xyz") for c in candidates] != isomers
    ):
        raise HandoffValidationError("Candidate count or order disagrees with native CREST ensemble", code="RANKING_MISMATCH")

    for name, frame, candidate in zip(isomers, native, candidates):
        result = candidate.get("mace")
        if (
            not isinstance(result, dict)
            or archive.read(name) != frame.text.encode("ascii")
            or frame.symbols != starting[0].symbols
            or frame.energy_hartree != candidate.get("crest_energy_hartree")
            or result.get("status") != "SUCCESS"
            or not isinstance(result.get("energy_hartree"), (int, float))
            or isinstance(result.get("energy_hartree"), bool)
            or not math.isfinite(float(result["energy_hartree"]))
            or result.get("checkpoint_sha256") != ranking.get("model_sha256")
        ):
            raise HandoffValidationError(f"Inconsistent science record for {name}", code="SCIENCE_MISMATCH")
        _check_gradient(result.get("gradient_hartree_per_bohr"), len(frame.symbols))

    selected = min(candidates, key=lambda c: c["mace"]["energy_hartree"])["xyz"]
    final = json.loads(archive.read("pyscf.json"))
    refined = parse_xyz_frames(
        refined_text,
        allowed_elements=V1_ALLOWED_ELEMENTS,
        min_atoms=V1_MIN_ATOMS,
        max_atoms=V1_MAX_ATOMS,
        max_frames=V1_MAX_FRAMES,
        charge=0,
        multiplicity=1,
        require_energy=True,
    )
    if (
        selected != receipt.get("selected")
        or selected != ranking.get("selected")
        or len(refined) != 1
        or refined[0].symbols != starting[0].symbols
        or receipt.get("refined_xyz") != "refined.xyz"
        or not math.isclose(refined[0].energy_hartree or 0.0, float(final["energy_hartree"]), rel_tol=0.0, abs_tol=1e-12)
        or final.get("method") != "RHF"
        or final.get("basis") != "STO-3G"
        or final.get("optimizer_converged") is not True
        or final.get("scf_converged") is not True
    ):
        raise HandoffValidationError("Final PySCF result or selection does not agree with the v1 handoff", code="FINAL_MISMATCH")
    _check_gradient(final.get("gradient_hartree_per_bohr"), len(starting[0].symbols))

    if destination is not None:
        _stage_verified_archive(archive, destination, archive_hash, file_names, normalized_checksums)

    return receipt


def _verify_v2_contents(
    archive: zipfile.ZipFile,
    archive_path: Path,
    archive_hash: str,
    receipt: dict[str, Any],
    destination: Path | None,
) -> dict[str, Any]:
    if archive_path.stat().st_size > V2_MAX_ARCHIVE_BYTES:
        raise HandoffSecurityError("v2 handoff archive exceeds 64 MiB", code="ARCHIVE_LIMIT_EXCEEDED")

    _, file_names = _inspect_zip_safety(
        archive,
        max_members=V2_MAX_MEMBERS,
        max_uncompressed_bytes=V2_MAX_UNCOMPRESSED_BYTES,
    )
    validated = validate_v2_manifest_fields(receipt)

    checksums = receipt.get("files_sha256")
    if not isinstance(checksums, dict) or not checksums:
        raise HandoffValidationError("v2 handoff requires non-empty files_sha256 mapping", code="INVENTORY_MISMATCH")

    normalized_checksums: dict[str, str] = {}
    for raw_member, raw_sha in checksums.items():
        safe_member = _validate_member_relpath(str(raw_member), allow_dir=False)
        if safe_member == "handoff.json":
            raise HandoffValidationError("files_sha256 must not include handoff.json", code="INVENTORY_MISMATCH")
        if not isinstance(raw_sha, str) or not _HEX64_RE.fullmatch(raw_sha.lower()):
            raise HandoffValidationError(
                f"Malformed SHA-256 digest in files_sha256 for {safe_member}",
                code="MEMBER_SHA256_MISMATCH",
            )
        normalized_checksums[safe_member] = raw_sha.lower()

    expected_members = set(normalized_checksums.keys())
    if file_names != (expected_members | {"handoff.json"}):
        raise HandoffValidationError(
            "Archive file inventory does not match files_sha256 + handoff.json",
            code="INVENTORY_MISMATCH",
        )

    for name in sorted(expected_members):
        member_bytes = archive.read(name)
        actual_sha = sha256_bytes(member_bytes)
        if actual_sha != normalized_checksums[name]:
            raise HandoffValidationError(f"SHA-256 mismatch for {name}", code="MEMBER_SHA256_MISMATCH")
        _assert_no_dlpno_in_file_bytes(name, member_bytes)

    starting_xyz = validated["starting_xyz"]
    primary_xyz = validated["primary_xyz"]
    ensemble_xyz = validated["ensemble_xyz"]
    selected = validated["selected"]
    for req_file in (starting_xyz, primary_xyz):
        if req_file not in normalized_checksums:
            raise HandoffValidationError(f"Required XYZ member missing from archive: {req_file}", code="INVENTORY_MISMATCH")
    if ensemble_xyz is not None and ensemble_xyz not in normalized_checksums:
        raise HandoffValidationError(f"Declared ensemble_xyz missing from archive: {ensemble_xyz}", code="INVENTORY_MISMATCH")
    if selected is not None and selected not in normalized_checksums:
        raise HandoffValidationError(f"Declared selected member missing from archive: {selected}", code="INVENTORY_MISMATCH")

    charge = validated["charge"]
    multiplicity = validated["multiplicity"]

    try:
        starting_frames = parse_xyz_frames(
            archive.read(starting_xyz).decode("utf-8"),
            allowed_elements=V2_ALLOWED_ELEMENTS,
            min_atoms=V2_MIN_ATOMS,
            max_atoms=V2_MAX_ATOMS,
            max_frames=1,
            charge=charge,
            multiplicity=multiplicity,
            require_energy=False,
        )
    except UnicodeDecodeError as exc:
        raise HandoffValidationError(f"Invalid UTF-8 in {starting_xyz}: {exc}", code="XYZ_INVALID") from exc

    starting_stoich = Counter(starting_frames[0].symbols)

    try:
        primary_frames = parse_xyz_frames(
            archive.read(primary_xyz).decode("utf-8"),
            allowed_elements=V2_ALLOWED_ELEMENTS,
            min_atoms=V2_MIN_ATOMS,
            max_atoms=V2_MAX_ATOMS,
            max_frames=V2_MAX_FRAMES,
            charge=charge,
            multiplicity=multiplicity,
            require_energy=False,
        )
    except UnicodeDecodeError as exc:
        raise HandoffValidationError(f"Invalid UTF-8 in {primary_xyz}: {exc}", code="XYZ_INVALID") from exc

    for frame in primary_frames:
        if Counter(frame.symbols) != starting_stoich:
            raise HandoffValidationError(
                f"Primary XYZ {primary_xyz} stoichiometry disagrees with {starting_xyz}",
                code="STOICHIOMETRY_MISMATCH",
            )

    if ensemble_xyz is not None:
        try:
            ens_frames = parse_xyz_frames(
                archive.read(ensemble_xyz).decode("utf-8"),
                allowed_elements=V2_ALLOWED_ELEMENTS,
                min_atoms=V2_MIN_ATOMS,
                max_atoms=V2_MAX_ATOMS,
                max_frames=V2_MAX_FRAMES,
                charge=charge,
                multiplicity=multiplicity,
                require_energy=False,
            )
        except UnicodeDecodeError as exc:
            raise HandoffValidationError(f"Invalid UTF-8 in {ensemble_xyz}: {exc}", code="XYZ_INVALID") from exc
        if len(ens_frames) != validated["candidate_count"]:
            raise HandoffValidationError(
                f"Ensemble {ensemble_xyz} has {len(ens_frames)} frames, expected candidate_count={validated['candidate_count']}",
                code="CANDIDATE_COUNT_MISMATCH",
            )
        for frame in ens_frames:
            if Counter(frame.symbols) != starting_stoich:
                raise HandoffValidationError(
                    f"Ensemble {ensemble_xyz} frame stoichiometry disagrees with {starting_xyz}",
                    code="STOICHIOMETRY_MISMATCH",
                )

    for name in sorted(expected_members):
        if not name.lower().endswith(".xyz") or name in {starting_xyz, primary_xyz, ensemble_xyz}:
            continue
        is_same_system = (name == selected) or name.startswith("isomers/")
        try:
            extra_frames = parse_xyz_frames(
                archive.read(name).decode("utf-8"),
                allowed_elements=V2_ALLOWED_ELEMENTS,
                min_atoms=V2_MIN_ATOMS,
                max_atoms=V2_MAX_ATOMS,
                max_frames=V2_MAX_FRAMES,
                charge=charge if is_same_system else 0,
                multiplicity=multiplicity if is_same_system else 1,
                require_energy=False,
                check_electron_parity=is_same_system,
            )
        except UnicodeDecodeError as exc:
            raise HandoffValidationError(f"Invalid UTF-8 in {name}: {exc}", code="XYZ_INVALID") from exc
        if is_same_system:
            for frame in extra_frames:
                if Counter(frame.symbols) != starting_stoich:
                    raise HandoffValidationError(
                        f"XYZ member {name} stoichiometry disagrees with {starting_xyz}",
                        code="STOICHIOMETRY_MISMATCH",
                    )

    meta = receipt.get("metadata") if isinstance(receipt.get("metadata"), Mapping) else {}
    if "energy_hartree" in meta and meta["energy_hartree"] is not None:
        raw_e = meta["energy_hartree"]
        if not isinstance(raw_e, (int, float)) or isinstance(raw_e, bool) or not math.isfinite(float(raw_e)):
            raise HandoffValidationError("metadata.energy_hartree must be a finite number", code="SCHEMA_INVALID")

    if destination is not None:
        _stage_verified_archive(archive, destination, archive_hash, file_names, normalized_checksums)

    return receipt


def verify(
    path: Path | str,
    destination: Path | str | None = None,
    expected_sha256: str | None = None,
    *,
    sidecar_path: Path | str | None = None,
) -> dict[str, Any]:
    """Verify a v1 (`cochem.student-conformer-handoff/1`) or v2 (`cochem.student-handoff/2`) ZIP archive.

    Returns the verified `handoff.json` dict (and stages verified files into
    `<destination>/<archive_sha256>` if `destination` is supplied).
    """
    archive_path = Path(path)
    if not archive_path.is_file() or archive_path.is_symlink():
        raise HandoffValidationError(f"Handoff archive must be a regular file: {archive_path}", code="ARCHIVE_MISSING")
    if archive_path.stat().st_size > V2_MAX_ARCHIVE_BYTES:
        raise HandoffSecurityError("Handoff archive exceeds 64 MiB limit", code="ARCHIVE_LIMIT_EXCEEDED")

    expected_digest: str | None = None
    if sidecar_path is not None:
        expected_digest = parse_sha256_sidecar(sidecar_path, expected_filename=archive_path.name)
    if expected_sha256 is not None:
        norm_exp = expected_sha256.strip().lower()
        if not _HEX64_RE.fullmatch(norm_exp):
            raise HandoffValidationError(f"Malformed expected_sha256: {expected_sha256!r}", code="OUTER_SHA256_MISMATCH")
        if expected_digest is not None and expected_digest != norm_exp:
            raise HandoffValidationError(
                "Supplied expected_sha256 disagrees with .sha256 sidecar digest",
                code="OUTER_SHA256_MISMATCH",
            )
        expected_digest = norm_exp

    dest_path = Path(destination) if destination is not None else None

    with archive_path.open("rb") as stream:
        archive_hash = hashlib.file_digest(stream, "sha256").hexdigest()
        if expected_digest is not None and archive_hash != expected_digest:
            raise HandoffValidationError(
                f"Outer SHA-256 mismatch for {archive_path.name}: got {archive_hash}, expected {expected_digest}",
                code="OUTER_SHA256_MISMATCH",
            )
        stream.seek(0)
        try:
            with zipfile.ZipFile(stream, "r") as archive:
                _, file_names = _inspect_zip_safety(
                    archive,
                    max_members=V2_MAX_MEMBERS,
                    max_uncompressed_bytes=V2_MAX_UNCOMPRESSED_BYTES,
                )
                if "handoff.json" not in file_names:
                    raise HandoffValidationError("Archive missing required handoff.json", code="SCHEMA_INVALID")
                try:
                    receipt = json.loads(archive.read("handoff.json").decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise HandoffValidationError(f"Malformed handoff.json: {exc}", code="SCHEMA_INVALID") from exc
                if not isinstance(receipt, dict):
                    raise HandoffValidationError("handoff.json must contain a JSON object", code="SCHEMA_INVALID")

                schema = receipt.get("schema")
                if schema == SCHEMA_V1:
                    return _verify_v1_contents(archive, archive_path, archive_hash, receipt, dest_path)
                if schema == SCHEMA_V2:
                    return _verify_v2_contents(archive, archive_path, archive_hash, receipt, dest_path)
                raise HandoffValidationError(
                    f"Unsupported handoff schema {schema!r}; expected one of {SUPPORTED_SCHEMAS}",
                    code="SCHEMA_INVALID",
                )
        except zipfile.BadZipFile as exc:
            raise HandoffValidationError(f"Corrupted ZIP archive {archive_path.name}: {exc}", code="CORRUPT_ARCHIVE") from exc


def build_student_handoff_v2_zip(
    files: Mapping[str, bytes | str],
    manifest: StudentHandoffV2Manifest | Mapping[str, Any],
    output_dir: Path | str,
    *,
    archive_name: str | None = None,
) -> tuple[Path, Path, str, dict[str, Any]]:
    """Build, seal, self-verify, and write a canonical `cochem.student-handoff/2` ZIP + `.sha256` sidecar."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest_dict = manifest.to_dict() if isinstance(manifest, StudentHandoffV2Manifest) else dict(manifest)
    manifest_dict["schema"] = SCHEMA_V2
    manifest_dict.setdefault("length_unit", "angstrom")
    manifest_dict.setdefault("collaborator_institution", DEFAULT_COLLABORATOR_INSTITUTION)
    manifest_dict.setdefault("created_at_utc", _utc_now())

    encoded_files: dict[str, bytes] = {}
    inventory: dict[str, str] = {}
    for raw_name, content in sorted(files.items()):
        safe_name = _validate_member_relpath(raw_name, allow_dir=False)
        if safe_name == "handoff.json":
            raise HandoffValidationError("Caller must not pass handoff.json inside files mapping", code="SCHEMA_INVALID")
        raw_bytes = content.encode("utf-8") if isinstance(content, str) else bytes(content)
        _assert_no_dlpno_in_file_bytes(safe_name, raw_bytes)
        encoded_files[safe_name] = raw_bytes
        inventory[safe_name] = sha256_bytes(raw_bytes)

    manifest_dict["files_sha256"] = inventory
    validated = validate_v2_manifest_fields(manifest_dict)
    if validated["continuation_calc_kind"] is not None:
        manifest_dict["continuation_calc_kind"] = validated["continuation_calc_kind"]

    stem = Path(str(manifest_dict["input_name"])).stem
    default_name = (
        f"CoChem-{_sanitize_slug(manifest_dict['course_id'].lower())}-"
        f"{_sanitize_slug(stem)}-{_sanitize_slug(str(manifest_dict['run_id']))}-"
        f"{_sanitize_slug(str(manifest_dict['attempt']))}.zip"
    )
    zip_name = archive_name or default_name
    zip_path = out_dir / zip_name
    sha_path = out_dir / f"{zip_name}.sha256"

    handoff_bytes = (json.dumps(manifest_dict, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    try:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("handoff.json", handoff_bytes)
            for name in sorted(encoded_files):
                zf.writestr(name, encoded_files[name])

        archive_sha = sha256_file(zip_path)
        sha_path.write_text(f"{archive_sha}  {zip_name}\n", encoding="ascii")

        verify(zip_path, sidecar_path=sha_path)
    except Exception:
        zip_path.unlink(missing_ok=True)
        sha_path.unlink(missing_ok=True)
        raise
    return zip_path, sha_path, archive_sha, manifest_dict


def seal(
    directory: Path | str,
    output: Path | str,
    receipt: StudentHandoffV2Manifest | Mapping[str, Any],
    *,
    archive_name: str | None = None,
) -> tuple[Path, Path, str, dict[str, Any]]:
    """Seal all regular files inside `directory` into a verified `cochem.student-handoff/2` ZIP + `.sha256`."""
    src_dir = Path(directory)
    if not src_dir.is_dir():
        raise HandoffValidationError(f"Source directory does not exist: {src_dir}", code="ARCHIVE_MISSING")
    files_map: dict[str, bytes] = {}
    for file_path in sorted(p for p in src_dir.rglob("*") if p.is_file()):
        if file_path.is_symlink():
            raise HandoffSecurityError(f"Refusing to seal symlinked file: {file_path}", code="SYMLINK_FORBIDDEN")
        rel = file_path.relative_to(src_dir).as_posix()
        if rel == "handoff.json":
            continue
        files_map[rel] = file_path.read_bytes()
    return build_student_handoff_v2_zip(files_map, receipt, output, archive_name=archive_name)


def _normalize_course_id_for_starter(raw_course_id: str) -> str:
    cleaned = str(raw_course_id or "").strip().upper().replace(" ", "").replace("-", "").replace("_", "")
    if cleaned == "CHEM312L":
        cleaned = "CHEM312"
    allowed = get_allowed_course_ids()
    if cleaned in allowed:
        return cleaned
    try:
        from cochem_base.course_loader import get_cure_course_profile

        profile = get_cure_course_profile(raw_course_id)
        cid = str(profile.get("course_id") or "").strip().upper()
        if cid in allowed:
            return cid
    except Exception:
        pass
    raise HandoffValidationError(
        f"Invalid course_id {raw_course_id!r}; expected one of {allowed}",
        code="SCHEMA_INVALID",
    )


def build_starter_manifest(
    course_id: str,
    *,
    workflow_type: str = "conformer",
    input_name: str = "input.xyz",
    charge: int = 0,
    multiplicity: int = 1,
    method: str = "B3LYP-D3BJ",
    basis: str = "def2-SVP",
    solvation: str = "gas",
    solvent_name: str | None = None,
    hessian_calculated: bool = False,
    n_imaginary_modes: int | None = None,
    starting_xyz: str = "input.xyz",
    primary_xyz: str = "refined.xyz",
    ensemble_xyz: str | None = None,
    candidate_count: int = 1,
    selected: str | None = None,
    target_continuation: str = "workstation",
    continuation_calc_kind: str | None = "opt_freq",
    student_id: str | None = None,
    repository: str = "ProfJJK-CoChem/CoChem-BASE",
    commit: str | None = None,
    run_id: str | None = None,
    attempt: str = "1",
) -> dict[str, Any]:
    """Construct and validate a starter `cochem.student-handoff/2` JSON manifest."""
    canonical_course = _normalize_course_id_for_starter(course_id)
    eff_n_imag = (0 if n_imaginary_modes is None else int(n_imaginary_modes)) if hessian_calculated else None
    eff_commit = (commit or ("0" * 40)).strip().lower()
    if not _HEX40_RE.fullmatch(eff_commit):
        raise HandoffValidationError(
            f"commit must be a 40-char lowercase hex SHA, got {eff_commit!r}",
            code="SCHEMA_INVALID",
        )
    today_slug = datetime.now(timezone.utc).strftime("%Y%m%d")
    eff_run_id = run_id or f"{canonical_course.lower()}-local-{today_slug}"
    eff_student_id = student_id or f"{canonical_course.lower()}_student"

    manifest_obj = StudentHandoffV2Manifest(
        workflow_type=workflow_type,
        input_name=input_name,
        charge=int(charge),
        multiplicity=int(multiplicity),
        method=method,
        basis=basis,
        solvation=solvation,
        solvent_name=solvent_name if solvation != "gas" else None,
        hessian_calculated=bool(hessian_calculated),
        n_imaginary_modes=eff_n_imag,
        course_id=canonical_course,
        collaborator_institution=DEFAULT_COLLABORATOR_INSTITUTION,
        target_continuation=target_continuation,
        starting_xyz=starting_xyz,
        primary_xyz=primary_xyz,
        ensemble_xyz=ensemble_xyz,
        candidate_count=int(candidate_count),
        selected=selected,
        student_id=eff_student_id,
        repository=repository,
        commit=eff_commit,
        run_id=eff_run_id,
        attempt=str(attempt),
        continuation_calc_kind=(
            normalize_continuation_calc_kind(continuation_calc_kind)
            if continuation_calc_kind is not None
            else None
        ),
    )
    payload = manifest_obj.to_dict()
    validate_v2_manifest_fields(payload)
    return payload


def _build_top_level_help_parser() -> argparse.ArgumentParser:
    epilog = (
        "Subcommands:\n"
        "  verify <archive.zip>    Verify (and optionally stage) a v1 or v2 handoff ZIP\n"
        "  seal                    Seal a directory + JSON manifest into a verified v2 ZIP + .sha256\n"
        "  init-manifest           Write a starter v2 JSON manifest for a course (--course-id)\n"
        "\n"
        "Examples:\n"
        "  python student/handoff.py init-manifest --course-id CHEM311 --output ./chem311_manifest.json\n"
        "  python student/handoff.py seal --source-dir ./work --manifest ./chem311_manifest.json --output ./handoff_out\n"
        "  python student/handoff.py verify ./handoff_out/bundle.zip --sidecar ./handoff_out/bundle.zip.sha256\n"
        "  python student/handoff.py ./handoff_out/bundle.zip --sidecar ./handoff_out/bundle.zip.sha256 --stage ./received\n"
    )
    parser = argparse.ArgumentParser(
        prog="handoff.py",
        description=(
            "Build, seal, and verify CoChem v1/v2 student handoff ZIP archives using only "
            "the Python standard library (with local Pipeline 5.0.0 DLPNOExclusionFirewall)."
        ),
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        choices=("verify", "seal", "init-manifest"),
        help="Subcommand to run (or pass a .zip archive path directly as a shorthand for verify).",
    )
    return parser


def _build_seal_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="handoff.py seal",
        description="Seal a directory and JSON manifest into a self-verified v2 handoff ZIP + .sha256.",
    )
    parser.add_argument("--source-dir", type=Path, required=True, help="Directory of files to seal")
    parser.add_argument("--manifest", type=Path, required=True, help="JSON file with v2 manifest fields")
    parser.add_argument("--output", type=Path, required=True, help="Output directory for ZIP + .sha256")
    parser.add_argument("--archive-name", default=None, help="Optional explicit archive filename")
    return parser


def _build_init_manifest_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="handoff.py init-manifest",
        description="Generate a valid starter cochem.student-handoff/2 JSON manifest for a course.",
    )
    parser.add_argument(
        "--course-id",
        required=True,
        help="Course identifier (e.g. CHEM311, CHEM312, CHEM410, CHEM411, CHEM490).",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Optional output path to write the starter manifest JSON (prints to stdout if omitted).",
    )
    parser.add_argument("--workflow-type", default="conformer", choices=list(V2_ALLOWED_WORKFLOW_TYPES))
    parser.add_argument("--input-name", default="input.xyz", help="Logical input molecule filename")
    parser.add_argument("--charge", type=int, default=0, choices=list(V2_ALLOWED_CHARGES))
    parser.add_argument("--multiplicity", type=int, default=1, choices=list(V2_ALLOWED_MULTIPLICITIES))
    parser.add_argument("--method", default="B3LYP-D3BJ", help="Electronic structure method (DLPNO forbidden)")
    parser.add_argument("--basis", default="def2-SVP", help="Basis set label")
    parser.add_argument("--solvation", default="gas", choices=list(V2_ALLOWED_SOLVATIONS))
    parser.add_argument("--solvent-name", default=None)
    parser.add_argument("--hessian-calculated", action="store_true")
    parser.add_argument("--n-imaginary-modes", type=int, default=None)
    parser.add_argument("--starting-xyz", default="input.xyz")
    parser.add_argument("--primary-xyz", default="refined.xyz")
    parser.add_argument("--ensemble-xyz", default=None)
    parser.add_argument("--candidate-count", type=int, default=1)
    parser.add_argument(
        "--selected",
        default=None,
        help="Archive member filename of the selected geometry (e.g. refined.xyz or ts_polished.xyz).",
    )
    parser.add_argument("--target-continuation", default="workstation", choices=list(V2_ALLOWED_TARGET_CONTINUATIONS))
    parser.add_argument(
        "--continuation-calc-kind",
        default="opt_freq",
        help="Continuation kind (e.g. opt_freq, dft_opt_freq, single_point, dft_sp, ts_opt, revdsd, ccsd, ccsd_t).",
    )
    parser.add_argument("--student-id", default=None)
    parser.add_argument("--repository", default="ProfJJK-CoChem/CoChem-BASE")
    parser.add_argument("--commit", default=None, help="40-char lowercase hex Git commit SHA")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--attempt", default="1")
    return parser


def _build_verify_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="handoff.py verify",
        description="Verify or stage a CoChem v1 or v2 student handoff ZIP using only the Python standard library.",
    )
    parser.add_argument("archive", type=Path, help="Path to student handoff .zip archive")
    parser.add_argument("--expected-sha256", default=None, help="Optional expected outer SHA-256 digest")
    parser.add_argument("--sidecar", type=Path, default=None, help="Optional .zip.sha256 sidecar path")
    parser.add_argument("--stage", type=Path, default=None, help="Optional staging directory")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)

    if not raw_argv or raw_argv[0] in {"-h", "--help"}:
        _build_top_level_help_parser().parse_args(["--help"])
        return 0

    if raw_argv[0] == "init-manifest":
        args = _build_init_manifest_parser().parse_args(raw_argv[1:])
        try:
            manifest = build_starter_manifest(
                args.course_id,
                workflow_type=args.workflow_type,
                input_name=args.input_name,
                charge=args.charge,
                multiplicity=args.multiplicity,
                method=args.method,
                basis=args.basis,
                solvation=args.solvation,
                solvent_name=args.solvent_name,
                hessian_calculated=bool(args.hessian_calculated),
                n_imaginary_modes=args.n_imaginary_modes,
                starting_xyz=args.starting_xyz,
                primary_xyz=args.primary_xyz,
                ensemble_xyz=args.ensemble_xyz,
                candidate_count=args.candidate_count,
                selected=args.selected,
                target_continuation=args.target_continuation,
                continuation_calc_kind=args.continuation_calc_kind,
                student_id=args.student_id,
                repository=args.repository,
                commit=args.commit,
                run_id=args.run_id,
                attempt=args.attempt,
            )
            encoded = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
            if args.output is not None:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(encoded, encoding="utf-8", newline="\n")
                print(
                    json.dumps(
                        {
                            "ok": True,
                            "manifest_path": str(args.output.resolve()),
                            "course_id": manifest["course_id"],
                            "manifest": manifest,
                        },
                        indent=2,
                        sort_keys=True,
                    )
                )
            else:
                print(encoded, end="")
            return 0
        except (HandoffValidationError, OSError, ValueError) as exc:
            code = exc.code if isinstance(exc, HandoffValidationError) else "MANIFEST_INIT_ERROR"
            print(json.dumps({"ok": False, "code": code, "reason": str(exc)}, indent=2), file=sys.stderr)
            return 2

    if raw_argv[0] == "seal":
        args = _build_seal_parser().parse_args(raw_argv[1:])
        try:
            if not args.manifest.exists() or not args.manifest.is_file():
                raise HandoffValidationError(
                    f"Manifest JSON file not found: {args.manifest}. "
                    "Create one first with: python student/handoff.py init-manifest --course-id <COURSE_ID> "
                    f"--output {args.manifest}",
                    code="MANIFEST_MISSING",
                )
            try:
                manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
                raise HandoffValidationError(
                    f"Unable to read valid JSON manifest from {args.manifest}: {exc}",
                    code="MANIFEST_INVALID",
                ) from exc
            if not isinstance(manifest, Mapping):
                raise HandoffValidationError(
                    f"Manifest {args.manifest} must contain a JSON object",
                    code="MANIFEST_INVALID",
                )
            zip_path, sha_path, archive_sha, sealed = seal(
                args.source_dir,
                args.output,
                manifest,
                archive_name=args.archive_name,
            )
            print(
                json.dumps(
                    {
                        "ok": True,
                        "zip_path": str(zip_path),
                        "sha256_path": str(sha_path),
                        "archive_sha256": archive_sha,
                        "manifest": sealed,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        except (HandoffValidationError, OSError) as exc:
            code = exc.code if isinstance(exc, HandoffValidationError) else "IO_ERROR"
            print(json.dumps({"ok": False, "code": code, "reason": str(exc)}, indent=2), file=sys.stderr)
            return 2

    verify_argv = raw_argv[1:] if raw_argv[0] == "verify" else raw_argv
    args = _build_verify_parser().parse_args(verify_argv)
    try:
        receipt = verify(
            args.archive,
            destination=args.stage,
            expected_sha256=args.expected_sha256,
            sidecar_path=args.sidecar,
        )
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0
    except (HandoffValidationError, OSError) as exc:
        code = exc.code if isinstance(exc, HandoffValidationError) else "IO_ERROR"
        print(json.dumps({"ok": False, "code": code, "reason": str(exc)}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
