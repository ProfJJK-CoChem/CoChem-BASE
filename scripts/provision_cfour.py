#!/usr/bin/env python3
"""Verify and provision the approved optional CFOUR Linux runtime.

The complete private runtime is retained outside the checkout. Its checksum and
embedded inventory establish build identity; native ELF dependency and launcher
probes establish startup availability. Scientific acceptance uses real jobs and
is deliberately separate from provisioning. No downloaded installer is executed.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

try:
    from .provision_orca import (
        archive_space_preflight, extract_verified_archive, native_executable,
        sha256_file, verified_digest,
    )
except ImportError:
    from provision_orca import (
        archive_space_preflight, extract_verified_archive, native_executable,
        sha256_file, verified_digest,
    )

DEFAULT_MANIFEST = Path(__file__).with_name("cfour-distribution.json")
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROVENANCE_NAME = "cochem-cfour-provenance.json"


def load_distribution_manifest(path: Path = DEFAULT_MANIFEST) -> dict:
    manifest = json.loads(path.read_text())
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("CFOUR distribution manifest requires schema_version 1.")
    required = ("repository", "release_tag", "archive_name", "sha256",
                "runtime_manifest_sha256", "source_sha256", "cfour_version",
                "platform", "architecture", "minimum_glibc", "archive_root", "blas")
    if any(not isinstance(manifest.get(key), str) or not manifest[key]
           or any(char in manifest[key] for char in "\r\n\x00") for key in required):
        raise ValueError("CFOUR distribution fields require nonempty single-line strings.")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9._-]*", manifest["repository"]):
        raise ValueError("CFOUR asset repository must be OWNER/REPOSITORY.")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", manifest["release_tag"]):
        raise ValueError("CFOUR release tag is invalid.")
    for field in ("sha256", "runtime_manifest_sha256", "source_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", manifest[field]):
            raise ValueError(f"CFOUR {field} must be a lowercase SHA-256.")
    supported = {
        "archive_name": "cfour_2_1_linux_x86-64_gcc11_openmp_ilp64.tar.xz",
        "cfour_version": "2.1", "platform": "Linux", "architecture": "x86_64",
        "minimum_glibc": "2.35", "archive_root": "cfour-2.1",
        "blas": "ILP64 OpenBLAS pthread", "fortran_integer_bits": 64,
    }
    for key, expected in supported.items():
        if manifest.get(key) != expected:
            raise ValueError(f"This CFOUR installer requires {key}={expected!r}.")
    if manifest.get("mpi") is not False or manifest.get("openmp") is not True:
        raise ValueError("The reviewed CFOUR build enables OpenMP and disables MPI.")
    return manifest


def require_platform(system: str, machine: str, glibc: str, manifest: dict) -> None:
    if system != manifest["platform"] or machine != manifest["architecture"]:
        raise ValueError("This CFOUR runtime requires Linux x86_64; use WSL2 or a matching local/HPC build.")
    match = re.fullmatch(r"(?:glibc\s+)?([0-9]+)\.([0-9]+)(?:\.[0-9]+)?", glibc)
    if not match or tuple(map(int, match.groups())) < tuple(map(int, manifest["minimum_glibc"].split("."))):
        raise ValueError(f"CFOUR requires glibc {manifest['minimum_glibc']} or newer; observed {glibc!r}.")


def _inventory_path(name: str) -> PurePosixPath:
    if not isinstance(name, str) or not name or any(char in name for char in "\\\x00\r\n"):
        raise ValueError("Invalid CFOUR inventory path.")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "." == name or str(path) != name:
        raise ValueError(f"Unsafe CFOUR inventory path: {name!r}")
    return path


def verify_inventory(prefix: Path, distribution: dict, *, allow_provenance: bool = False) -> dict:
    """Verify every runtime file against the checksum-pinned embedded inventory."""
    inventory_path = prefix / "manifest.json"
    if inventory_path.is_symlink() or not inventory_path.is_file():
        raise ValueError("CFOUR embedded inventory must be a regular file.")
    verified_digest(inventory_path, distribution["runtime_manifest_sha256"])
    manifest = json.loads(inventory_path.read_text())
    identities = {
        "schema_version": 1, "software": "CFOUR", "version": distribution["cfour_version"],
        "source_sha256": distribution["source_sha256"], "platform": "linux-x86_64",
        "minimum_glibc": distribution["minimum_glibc"],
        "fortran_integer_bits": distribution["fortran_integer_bits"], "blas": distribution["blas"],
    }
    if not isinstance(manifest, dict) or any(manifest.get(k) != v for k, v in identities.items()):
        raise ValueError("Embedded CFOUR build identity does not match the reviewed distribution.")
    if manifest.get("mpi") is not False or manifest.get("openmp") is not True:
        raise ValueError("Embedded CFOUR threading identity does not match the reviewed build.")
    if not isinstance(manifest.get("files"), list) or not manifest["files"]:
        raise ValueError("CFOUR inventory must contain runtime files.")
    seen = {"manifest.json"}
    for record in manifest["files"]:
        if not isinstance(record, dict):
            raise ValueError("Invalid CFOUR inventory record.")
        name = str(_inventory_path(record.get("path")))
        if name in seen:
            raise ValueError(f"Duplicate CFOUR inventory entry: {name}")
        seen.add(name)
        path = prefix / name
        if not path.resolve().is_relative_to(prefix.resolve()):
            raise ValueError(f"CFOUR inventory link escapes installation: {name}")
        if "symlink" in record:
            if not isinstance(record["symlink"], str) or not path.is_symlink() or os.readlink(path) != record["symlink"]:
                raise ValueError(f"CFOUR inventory link mismatch: {name}")
            if not path.exists():
                raise ValueError(f"CFOUR inventory link is broken: {name}")
        else:
            expected_size = record.get("size")
            if not isinstance(expected_size, int) or isinstance(expected_size, bool) or expected_size < 0:
                raise ValueError(f"Invalid CFOUR inventory size: {name}")
            if path.is_symlink() or not path.is_file() or path.stat().st_size != expected_size:
                raise ValueError(f"CFOUR inventory file mismatch: {name}")
            checksum = record.get("sha256")
            if not isinstance(checksum, str):
                raise ValueError(f"Invalid CFOUR inventory SHA-256: {name}")
            verified_digest(path, checksum)
    actual = {str(path.relative_to(prefix)) for path in prefix.rglob("*")
              if path.is_file() or path.is_symlink()}
    if allow_provenance and PROVENANCE_NAME in actual:
        actual.remove(PROVENANCE_NAME)
    if actual != seen:
        raise ValueError(f"CFOUR inventory differs from extracted files: missing={sorted(seen-actual)}, unexpected={sorted(actual-seen)}")
    return manifest


def verify_runtime(prefix: Path | str, manifest_path: Path = DEFAULT_MANIFEST) -> dict:
    """Seal the approved packaged runtime before/after a native calculation.

This hashes all inventoried helpers, scripts, libraries and basis data without
executing a program. A missing embedded inventory is an error: manual local/HPC
installations must be classified as unsealed and authorized through Stage 0.
The optional generated installation receipt is checked separately and never
allows an additional runtime file to escape the pinned inventory.
"""
    root = Path(prefix).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("CFOUR runtime prefix must be a directory.")
    distribution = load_distribution_manifest(manifest_path)
    inventory = verify_inventory(root, distribution, allow_provenance=True)
    executable = root / "bin/xcfour"
    if executable.is_symlink() or not executable.is_file() or not os.access(executable, os.X_OK):
        raise ValueError("CFOUR packaged launcher must be an executable regular file.")
    native_executable(root / "libexec/xcfour.native")
    for path in (root / "bin").iterdir():
        if path.is_symlink() or not path.is_file():
            continue
        with path.open("rb") as stream:
            if stream.read(4) == b"\x7fELF":
                native_executable(path)
    basis = {}
    for name in ("GENBAS", "ECPDATA"):
        path = root / "basis" / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"CFOUR packaged {name} must be a nonempty regular basis file.")
        basis[name] = {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}
    receipt = root / PROVENANCE_NAME
    receipt_sha = None
    if receipt.exists() or receipt.is_symlink():
        if receipt.is_symlink() or not receipt.is_file():
            raise ValueError("CFOUR provisioning receipt must be a regular file.")
        recorded = json.loads(receipt.read_text())
        if (not isinstance(recorded, dict) or recorded.get("schema_version") != 1
                or recorded.get("software") != "CFOUR" or recorded.get("status") != "available"
                or recorded.get("distribution") != distribution
                or recorded.get("archive_sha256") != distribution["sha256"]
                or recorded.get("runtime_manifest_sha256") != distribution["runtime_manifest_sha256"]
                or recorded.get("manifest_sha256") != sha256_file(manifest_path)
                or recorded.get("native_cfour_version") != distribution["cfour_version"]):
            raise ValueError("CFOUR provisioning receipt does not match the approved runtime identity.")
        receipt_sha = sha256_file(receipt)
    return {
        "sealed": True, "seal_scope": "Complete checksum-pinned packaged runtime inventory; no scientific accuracy claim",
        "software": "CFOUR", "version": distribution["cfour_version"], "prefix": str(root),
        "executable": str(executable), "genbas": basis["GENBAS"]["path"],
        "ecpdata": basis["ECPDATA"]["path"], "basis": basis,
        "runtime_inventory_sha256": distribution["runtime_manifest_sha256"],
        "manifest_sha256": sha256_file(manifest_path), "source_sha256": distribution["source_sha256"],
        "files_verified": len(inventory["files"]),
        "provisioning_receipt_sha256": receipt_sha,
        "mpi": False, "openmp": True,
    }


def _runtime_environment(prefix: Path) -> dict[str, str]:
    # No source/asset token or other inherited credentials reach native programs.
    return {
        "PATH": os.pathsep.join([str(prefix / "bin"), "/usr/bin", "/bin"]),
        "LD_LIBRARY_PATH": str(prefix / "lib/runtime"), "LANG": "C", "LC_ALL": "C",
        "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
        "CFOUR_ROOT": str(prefix),
    }


def cfour_version(output: str, expected: str) -> str:
    """Read the actual CFOUR-qualified native banner, never arbitrary numbers."""
    sections = re.findall(
        r"CFOUR\s+Coupled-Cluster\s+techniques\s+for\s+Computational\s+Chemistry(.{0,4000}?)\bVersion\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?)(?![\w.])",
        output, re.IGNORECASE | re.DOTALL,
    )
    if len(sections) != 1 or sections[0][1] != expected:
        raise ValueError(f"Expected native CFOUR version {expected}; observed {[section[1] for section in sections]}.")
    return expected


def interrogate_runtime(prefix: Path) -> dict:
    executable = prefix / "bin/xcfour"
    native = prefix / "libexec/xcfour.native"
    if executable.is_symlink() or not executable.is_file() or not os.access(executable, os.X_OK):
        raise ValueError("The approved CFOUR launcher is missing or not executable.")
    native_executable(native)
    for name in ("basis/GENBAS", "basis/ECPDATA"):
        path = prefix / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"Required CFOUR basis data is missing: {name}")
    ldd = shutil.which("ldd")
    if not ldd:
        raise ValueError("ldd is required to verify CFOUR native runtime dependencies.")
    environment = _runtime_environment(prefix)
    dependencies = {}
    with tempfile.TemporaryDirectory(prefix="cochem-cfour-probe-") as temporary:
        directory = Path(temporary)
        for parent in (prefix / "bin", prefix / "libexec", prefix / "lib/runtime"):
            for path in sorted(parent.iterdir()):
                if path.is_symlink() or not path.is_file():
                    continue
                with path.open("rb") as stream:
                    if stream.read(4) != b"\x7fELF":
                        continue
                if parent == prefix / "lib/runtime":
                    with path.open("rb") as stream:
                        header = stream.read(20)
                    if header[:6] != b"\x7fELF\x02\x01" or header[18:20] != b"\x3e\x00":
                        raise ValueError(f"Expected Linux x86-64 CFOUR shared library: {path.name}")
                else:
                    native_executable(path)
                result = subprocess.run([ldd, str(path)], cwd=directory, env=environment,
                                        capture_output=True, text=True, timeout=30, check=False)
                if result.returncode != 0 or "not found" in result.stdout + result.stderr:
                    raise ValueError(f"Unresolved CFOUR native dependencies: {path.name}")
                dependencies[str(path.relative_to(prefix))] = result.stdout
        # Bare xcfour prints nothing. A deliberately invalid geometry reveals
        # the native xjoda banner and stops during input/basis validation.
        # This error response establishes metadata, never scientific success.
        (directory / "ZMAT").write_text(
            "CoChem CFOUR version audit\nNOT_AN_ATOM\n\n*CFOUR(CALC=SCF,BASIS=STO-3G)\n"
        )
        result = subprocess.run([str(executable)], cwd=directory, env=environment,
                                capture_output=True, text=True, timeout=30, check=False)
        output = result.stdout + result.stderr
        version = cfour_version(output, "2.1")
        if (result.returncode != 0 or "@RDBAS-F, Basis set NOT_A:STO-3G not found on GENBAS." not in output
                or "Job has terminated with error flag" not in output
                or not re.search(r"--executable xjoda finished with status\s+256\b", output)):
            raise ValueError("CFOUR version probe did not produce its expected native input-error response.")
        if re.search(r"--executable\s+(?:xvscf|xqcscf|xncc|xvcc)\b", output):
            raise ValueError("The metadata probe unexpectedly reached an electronic calculation.")
        for name in ("GENBAS", "ECPDATA"):
            link = directory / name
            if not link.is_symlink() or link.resolve() != (prefix / "basis" / name).resolve():
                raise ValueError(f"CFOUR launcher did not supply its verified {name} basis link.")
    if not dependencies:
        raise ValueError("No CFOUR native dependencies were interrogated.")
    return {"native_dependencies": dependencies, "version_probe_returncode": result.returncode,
            "version_probe_mode": "controlled_invalid_input_metadata_no_calculation",
            "version_probe_expected_error": "@RDBAS-F, Basis set NOT_A:STO-3G not found on GENBAS.",
            "version_probe_output": output, "native_cfour_version": version}


def provision(archive: Path, install_root: Path, manifest_path: Path = DEFAULT_MANIFEST) -> dict:
    distribution = load_distribution_manifest(manifest_path)
    try:
        glibc = os.confstr("CS_GNU_LIBC_VERSION") or ""
    except (AttributeError, OSError, ValueError):
        glibc = ""
    require_platform(platform.system(), platform.machine(), glibc, distribution)
    if archive.name != distribution["archive_name"]:
        raise ValueError(f"Expected CFOUR archive filename {distribution['archive_name']!r}.")
    install_root = install_root.expanduser().absolute()
    if install_root.exists() or install_root.is_symlink():
        raise ValueError("CFOUR install root already exists; select a fresh installation directory.")
    install_root = install_root.resolve()
    if install_root.is_relative_to(REPOSITORY_ROOT):
        raise ValueError("Licensed CFOUR installation must be outside the source checkout.")
    disk_preflight = archive_space_preflight(archive, install_root, distribution["sha256"])
    install_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".cochem-cfour-install-", dir=install_root.parent) as temporary:
        staging = Path(temporary) / "distribution"
        archive_digest = extract_verified_archive(archive, staging, distribution["sha256"])
        children = list(staging.iterdir())
        if len(children) != 1 or children[0].name != distribution["archive_root"] or not children[0].is_dir():
            raise ValueError("CFOUR archive must contain exactly its reviewed runtime directory.")
        prefix = children[0]
        inventory = verify_inventory(prefix, distribution)
        if install_root.exists() or install_root.is_symlink():
            raise ValueError("CFOUR installation destination appeared during extraction.")
        prefix.rename(install_root)
    try:
        probes = interrogate_runtime(install_root)
        # Probes are isolated; every inventoried byte must remain unchanged.
        verify_inventory(install_root, distribution)
        provenance_path = install_root / PROVENANCE_NAME
        provenance = {
            "schema_version": 1, "software": "CFOUR", "version": distribution["cfour_version"],
            "status": "available", "recorded_at": datetime.now(timezone.utc).isoformat(),
            "scope": "pinned runtime identity, inventory, ELF dependencies and launcher startup; no calculation acceptance",
            "distribution": distribution, "archive_sha256": archive_digest,
            "manifest_sha256": sha256_file(manifest_path),
            "runtime_manifest_sha256": distribution["runtime_manifest_sha256"],
            "files_verified": len(inventory["files"]), "disk_preflight": disk_preflight,
            "host_glibc": glibc, "mpi": False, "openmp": True,
            "runtime_environment_scope": "CFOUR child processes only; global LD_LIBRARY_PATH is unchanged",
            **probes,
        }
        provenance_path.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
        return {
            "available": True, "executable": str(install_root / "bin/xcfour"),
            "cfour_home": str(install_root), "cfour_bin": str(install_root / "bin"),
            "genbas": str(install_root / "basis/GENBAS"),
            "ecpdata": str(install_root / "basis/ECPDATA"),
            "ld_library_path": str(install_root / "lib/runtime"),
            "cfour_version": distribution["cfour_version"], "mpi": False, "openmp": True,
            "archive_sha256": archive_digest, "files_verified": len(inventory["files"]),
            "provenance": str(provenance_path), "path_entries": [str(install_root / "bin")],
        }
    except BaseException:
        shutil.rmtree(install_root)
        raise


def github_environment(result: dict, env_path: Path, path_path: Path) -> None:
    values = {
        "COCHEM_CFOUR_AVAILABLE": "true", "COCHEM_CFOUR_BIN": result["executable"],
        "COCHEM_XCFOUR_BIN": result["executable"], "CFOUR_CMD": result["executable"],
        "CFOUR_EXE": result["executable"], "CFOUR_HOME": result["cfour_home"],
        "CFOUR_ROOT": result["cfour_home"], "CFOUR_BIN": result["cfour_bin"],
        "COCHEM_CFOUR_GENBAS": result["genbas"], "CFOUR_GENBAS": result["genbas"],
        "COCHEM_CFOUR_ECPDATA": result["ecpdata"], "CFOUR_ECPDATA": result["ecpdata"],
        "COCHEM_CFOUR_LD_LIBRARY_PATH": result["ld_library_path"],
        "COCHEM_CFOUR_PROVENANCE": result["provenance"],
        "COCHEM_CFOUR_MPI_AVAILABLE": "false", "COCHEM_CFOUR_OPENMP_AVAILABLE": "true",
    }
    if any(any(char in value for char in "\r\n\x00")
           for value in [*values.values(), *result["path_entries"]]):
        raise ValueError("Multiline or NUL-containing paths cannot be exported to Actions.")
    with env_path.open("a") as stream:
        stream.writelines(f"{key}={value}\n" for key, value in values.items())
    with path_path.open("a") as stream:
        stream.writelines(f"{path}\n" for path in result["path_entries"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--github-env", type=Path)
    parser.add_argument("--github-path", type=Path)
    args = parser.parse_args()
    if bool(args.github_env) != bool(args.github_path):
        parser.error("--github-env and --github-path must be supplied together")
    try:
        result = provision(args.archive, args.install_root, args.manifest)
        if args.github_env:
            github_environment(result, args.github_env, args.github_path)
    except (ValueError, OSError, subprocess.SubprocessError, tarfile.TarError) as exc:
        parser.exit(1, f"CFOUR provisioning failed: {exc}\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
