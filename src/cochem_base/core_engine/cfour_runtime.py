"""Verify native CFOUR basis, companions and the approved packaged runtime.

Packaged installations receive a complete independently pinned inventory seal.
Local/HPC installations remain supported and explicitly carry an unsealed local
identity made from the actual launcher, required helpers and basis-file hashes.
Stage 0 requests an ELF dependency audit; calculations compare the returned
runtime_seal_sha256 before and after every native process.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path, PurePosixPath
from typing import Mapping

from .cfour_basis_profile import BASIS_PROFILE, DERIVED_INVENTORY_SHA256

APPROVED_ARCHIVE_SHA256 = "19ea269fcc7a13eb059bf43d34f0ef32e07cc9bb98f4ce84bdc4d0d7b20ccd63"
APPROVED_INVENTORY_SHA256 = "e9a59cfcaeed3df210d8276b7d3055aed68ba082b2dbc31e826b8eafebd4e286"
APPROVED_SOURCE_SHA256 = "3c596dcdb866d500d3c37e602d8e5491deea6cfad9e4595c50dfc08b4088944a"
PROVENANCE_NAME = "cochem-cfour-provenance.json"
REQUIRED_HELPERS = (
    "xjoda", "xvmol", "xvmol2ja", "xvscf", "xintprc", "xvtran",
    "xncc", "xcphf", "xvdint", "xvprop", "xprops", "xrun", "xclean", "xvcc",
)
KNOWN_HELPERS = (
    "xanhdriv", "xanti", "xbcktrn", "xclean", "xcphf", "xcubic", "xdens", "xecc",
    "xextrap", "xfillfc", "xguinea", "xint", "xintprc", "xja2fja", "xjoda", "xlambda",
    "xlcc", "xncc", "xpolyreg", "xprepfc2f", "xprops", "xqcscf", "xrun", "xscrewdriver",
    "xsdcc", "xsim", "xsymcor", "xvcc", "xvdint", "xvea", "xvee", "xvip", "xvmol",
    "xvmol2ja", "xvprop", "xvpropx2c", "xvscf", "xvtran", "xwipeout", "tcsh",
)


def _sha256(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def _field(value: str) -> str:
    if any(char in value for char in "\r\n\x00"):
        raise ValueError("CFOUR runtime paths and environment settings must be single-line strings.")
    return value


def _file(path: Path, *, executable: bool = False, native: bool = False) -> dict:
    resolved = path.expanduser().resolve(strict=True)
    if not resolved.is_file() or resolved.stat().st_size == 0:
        raise ValueError(f"CFOUR runtime file must be nonempty and regular: {path}")
    if executable and not os.access(resolved, os.X_OK):
        raise ValueError(f"CFOUR runtime executable is not executable: {path}")
    if native:
        with resolved.open("rb") as stream:
            header = stream.read(20)
        system, machine = platform.system(), platform.machine().lower()
        if system == "Linux":
            architectures = {"x86_64": 62, "amd64": 62, "aarch64": 183, "arm64": 183,
                             "ppc64le": 21, "ppc64": 21, "riscv64": 243}
            byte_order = "little" if header[5:6] == b"\x01" else "big"
            valid = (header[:5] == b"\x7fELF\x02" and header[5:6] in (b"\x01", b"\x02")
                     and int.from_bytes(header[18:20], byte_order) == architectures.get(machine))
        elif system == "Darwin":
            # Thin and universal Mach-O binaries are interrogated by Stage 0
            # on the actual native host, which confirms executable compatibility.
            valid = header[:4] in (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf",
                                   b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",
                                   b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca")
        else:
            valid = False
        if not valid:
            raise ValueError(f"CFOUR helper must be native to this {system} {machine} host: {path}")
    return {"path": str(resolved), "sha256": _sha256(resolved), "bytes": resolved.stat().st_size}


def _relative(name: str) -> str:
    if not isinstance(name, str) or not name or any(char in name for char in "\\\x00\r\n"):
        raise ValueError("Invalid packaged CFOUR inventory path.")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or name == "." or str(path) != name:
        raise ValueError(f"Unsafe packaged CFOUR inventory path: {name!r}")
    return name


def _packaged_inventory(root: Path) -> dict:
    metadata = root / "manifest.json"
    if metadata.is_symlink() or not metadata.is_file():
        raise ValueError("Packaged CFOUR inventory checksum does not match the approved runtime.")
    inventory_sha256 = _sha256(metadata)
    if inventory_sha256 not in (APPROVED_INVENTORY_SHA256, DERIVED_INVENTORY_SHA256):
        raise ValueError("Packaged CFOUR inventory checksum does not match the approved runtime.")
    inventory = json.loads(metadata.read_text())
    if inventory_sha256 == DERIVED_INVENTORY_SHA256 and inventory.get("basis_derivation") != BASIS_PROFILE:
        raise ValueError("Derived CFOUR basis provenance does not match its reviewed profile.")
    expected = {
        "schema_version": 1, "software": "CFOUR", "version": "2.1",
        "source_sha256": APPROVED_SOURCE_SHA256, "platform": "linux-x86_64",
        "minimum_glibc": "2.35", "fortran_integer_bits": 64, "blas": "ILP64 OpenBLAS pthread",
    }
    if (not isinstance(inventory, dict) or any(inventory.get(k) != v for k, v in expected.items())
            or inventory.get("mpi") is not False or inventory.get("openmp") is not True
            or not isinstance(inventory.get("files"), list) or not inventory["files"]):
        raise ValueError("Packaged CFOUR build identity does not match the approved runtime.")
    seen = {"manifest.json"}
    for record in inventory["files"]:
        if not isinstance(record, dict):
            raise ValueError("Invalid packaged CFOUR inventory record.")
        name = _relative(record.get("path"))
        if name in seen:
            raise ValueError(f"Duplicate packaged CFOUR inventory entry: {name}")
        seen.add(name)
        path = root / name
        try:
            resolved = path.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ValueError(f"Packaged CFOUR inventory file is missing or cyclic: {name}") from exc
        if not resolved.is_relative_to(root):
            raise ValueError(f"Packaged CFOUR inventory path escapes its installation: {name}")
        if "symlink" in record:
            if not path.is_symlink() or os.readlink(path) != record["symlink"]:
                raise ValueError(f"Packaged CFOUR inventory link changed: {name}")
        elif (path.is_symlink() or not path.is_file() or path.stat().st_size != record.get("size")
              or _sha256(path) != record.get("sha256")):
            raise ValueError(f"Packaged CFOUR inventory bytes changed: {name}")
    actual = {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file() or path.is_symlink()}
    if PROVENANCE_NAME in actual:
        actual.remove(PROVENANCE_NAME)
        receipt_path = root / PROVENANCE_NAME
        if receipt_path.is_symlink() or not receipt_path.is_file():
            raise ValueError("CFOUR installation provenance must be a regular file.")
        receipt = json.loads(receipt_path.read_text())
        if (not isinstance(receipt, dict) or receipt.get("software") != "CFOUR"
                or receipt.get("status") != "available"
                or receipt.get("archive_sha256") != APPROVED_ARCHIVE_SHA256
                or receipt.get("runtime_manifest_sha256") != inventory_sha256
                or receipt.get("native_cfour_version") != "2.1"):
            raise ValueError("CFOUR installation provenance does not match its approved inventory.")
    if actual != seen:
        raise ValueError(f"Packaged CFOUR inventory differs from runtime files: missing={sorted(seen-actual)}, unexpected={sorted(actual-seen)}")
    return inventory


def _basis(name: str, root: Path, environment: Mapping[str, str], *, packaged: bool) -> dict:
    explicit = next((environment[key] for key in (f"COCHEM_CFOUR_{name}", f"CFOUR_{name}")
                     if environment.get(key)), None)
    canonical = root / "basis" / name
    if packaged:
        if explicit and Path(_field(explicit)).expanduser().resolve() != canonical.resolve():
            raise ValueError(f"A packaged CFOUR {name} override would invalidate its pinned runtime identity.")
        if canonical.is_symlink():
            raise ValueError(f"Packaged CFOUR {name} must be a regular basis file.")
        return _file(canonical)
    if explicit:
        return _file(Path(_field(explicit)))
    homes = [root]
    for key in ("CFOUR_HOME", "CFOUR_ROOT"):
        if environment.get(key):
            home = Path(_field(environment[key])).expanduser().resolve()
            if home not in homes:
                homes.append(home)
    for home in homes:
        for candidate in (home / "basis" / name, home / name, home / "share" / name):
            if candidate.is_file():
                return _file(candidate)
    raise ValueError(f"CFOUR {name} is missing; set COCHEM_CFOUR_{name} to the actual basis file.")


def _helpers(binary: Path, root: Path, environment: Mapping[str, str], *, packaged: bool) -> dict:
    parents = [binary.parent]
    if not packaged and environment.get("CFOUR_BIN"):
        configured = Path(_field(environment["CFOUR_BIN"])).expanduser().resolve()
        parents.append(configured if configured.is_dir() else configured.parent)
    if root / "bin" not in parents:
        parents.append(root / "bin")
    helpers = {}
    for name in REQUIRED_HELPERS:
        candidate = next((parent / name for parent in parents if (parent / name).is_file()), None)
        if candidate is None and not packaged:
            found = shutil.which(name, path=environment.get("PATH", os.defpath))
            candidate = Path(found) if found else None
        if candidate is None:
            raise ValueError(f"CFOUR required companion executable is missing: {name}")
        helpers[name] = _file(candidate, executable=True, native=True)
    # Bind the remaining known native CFOUR companions in its own directories.
    # Unrelated engine executables and broad system PATH contents are excluded.
    for name in KNOWN_HELPERS:
        if name in helpers:
            continue
        candidate = next((parent / name for parent in parents if (parent / name).is_file()), None)
        if candidate is not None:
            helpers[name] = _file(candidate, executable=True, native=True)
    return helpers


def _dependencies(files: list[Path], paths: list[str], libraries: str) -> dict:
    system = platform.system()
    tool_name = "otool" if system == "Darwin" else "ldd"
    tool = shutil.which(tool_name, path="/usr/bin:/bin")
    if not tool:
        raise ValueError(f"Stage 0 requires {tool_name} to audit CFOUR native dependencies.")
    child = {"PATH": os.pathsep.join([*paths, "/usr/bin", "/bin"]), "LANG": "C", "LC_ALL": "C"}
    if libraries:
        child["DYLD_LIBRARY_PATH" if system == "Darwin" else "LD_LIBRARY_PATH"] = libraries
    observed = {}
    for path in files:
        with path.open("rb") as stream:
            magic = stream.read(4)
            if magic != b"\x7fELF" and system != "Darwin":
                continue
            if system == "Darwin" and magic not in (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf",
                                                    b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",
                                                    b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca"):
                continue
        argv = [tool, "-L", str(path)] if system == "Darwin" else [tool, str(path)]
        result = subprocess.run(argv, capture_output=True, text=True,
                                env=child, timeout=30, check=False)
        if result.returncode != 0 or "not found" in result.stdout + result.stderr:
            raise ValueError(f"CFOUR native dependency audit failed: {path}")
        observed[str(path)] = result.stdout
    if not observed:
        raise ValueError("No CFOUR native dependencies were audited.")
    return observed


def verify_cfour_runtime(executable: Path | str, *, environment: Mapping[str, str] | None = None,
                         audit_dependencies: bool = False) -> dict:
    """Return actual readiness and a stable seal; raise on any missing/changed file.

The helper never treats a missing packaged manifest as an approved archive. Such
an installation is explicitly local_unsealed and requires Stage 0's successful
native version check. audit_dependencies is intended for Stage 0, while default
checks are pure file verification suitable before and after every calculation.
"""
    binary = Path(_field(str(executable))).expanduser().resolve(strict=True)
    from .engine_environment import engine_runtime_environment
    selected = engine_runtime_environment(
        "cfour", dict(os.environ if environment is None else environment), executable=binary
    )
    binary_record = _file(binary, executable=True)
    root = binary.parent.parent if binary.parent.name == "bin" else binary.parent
    packaged = (root / "manifest.json").exists() or (root / "manifest.json").is_symlink()
    known_packaged_layout = ((root / PROVENANCE_NAME).exists() or (root / PROVENANCE_NAME).is_symlink()
                             or ((root / "libexec/xcfour.native").exists() and (root / "lib/runtime").is_dir()))
    if known_packaged_layout and not packaged:
        raise ValueError("The packaged CFOUR runtime lost its embedded inventory; refusing an unsealed downgrade.")
    inventory = _packaged_inventory(root) if packaged else None
    if packaged and binary != root / "bin/xcfour":
        raise ValueError("Packaged CFOUR execution must use its approved xcfour launcher.")
    basis = {name: _basis(name, root, selected, packaged=packaged) for name in ("GENBAS", "ECPDATA")}
    helpers = _helpers(binary, root, selected, packaged=packaged)
    files = [binary, *(Path(record["path"]) for record in helpers.values())]
    native = root / "libexec/xcfour.native"
    if packaged:
        _file(native, executable=True, native=True)
        files = [root / entry["path"] for entry in inventory["files"]
                 if "symlink" not in entry and entry["path"].startswith(("bin/", "libexec/", "lib/runtime/"))]
    generic_libraries = selected.get("DYLD_LIBRARY_PATH" if platform.system() == "Darwin" else "LD_LIBRARY_PATH", "")
    libraries = str(root / "lib/runtime") if packaged else _field(selected.get("COCHEM_CFOUR_LD_LIBRARY_PATH", generic_libraries))
    paths = list(dict.fromkeys([str(binary.parent), *(str(Path(record["path"]).parent) for record in helpers.values())]))
    bindings = {
        "mode": "packaged" if packaged else "local_unsealed", "executable": binary_record,
        "basis": basis, "helpers": helpers,
        "runtime_inventory_sha256": _sha256(root / "manifest.json") if packaged else None,
        "path_entries": paths, "ld_library_path": libraries,
    }
    if packaged and "basis_derivation" in inventory:
        bindings["basis_derivation"] = inventory["basis_derivation"]
    seal = hashlib.sha256(json.dumps(bindings, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    observed = _dependencies(files, paths, libraries) if audit_dependencies else None
    return {
        **bindings, "available": True, "sealed": packaged, "software": "CFOUR", "prefix": str(root),
        "executable": str(binary), "executable_record": binary_record,
        "genbas": basis["GENBAS"]["path"], "ecpdata": basis["ECPDATA"]["path"],
        "runtime_seal_sha256": seal, "files_verified": len(inventory["files"]) if inventory else
                              len({binary_record["path"], *(record["path"] for record in helpers.values()),
                                   *(record["path"] for record in basis.values())}),
        "version": "2.1" if packaged else None, "mpi": False if packaged else None,
        "openmp": True if packaged else None, "dependency_audit": observed,
        "identity_scope": ("Approved complete derived runtime inventory; unchanged licensed binaries and explicit reviewed H/O basis addon"
                           if inventory and "basis_derivation" in inventory else "Approved complete runtime inventory") if packaged else
                          "Unsealed local/HPC installation; actual launcher, required helper and basis hashes; Stage 0 version authority required",
    }
