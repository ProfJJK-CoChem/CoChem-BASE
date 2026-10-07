#!/usr/bin/env python3
"""Verify and install an already downloaded, approved ORCA distribution.

This helper provisions the selected Linux Actions artifact only. Workstation and
HPC installations continue to use BASE's existing discovery/configuration paths.
It does not download credentials or claim that a version probe is a calculation.
"""

from __future__ import annotations

import argparse
import hashlib
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

DEFAULT_MANIFEST = Path(__file__).with_name("orca-distribution.json")
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verified_digest(archive: Path, expected: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
        raise ValueError("The approved archive checksum must be a 64-character SHA-256.")
    actual = sha256_file(archive)
    if actual != expected.lower():
        raise ValueError(f"Archive SHA-256 mismatch: expected {expected.lower()}, got {actual}")
    return actual


def _member_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name or "\x00" in name:
        raise ValueError(f"Unsafe archive path: {name!r}")
    return path


def _link_target(member: tarfile.TarInfo, path: PurePosixPath) -> PurePosixPath:
    target = PurePosixPath(member.linkname)
    if target.is_absolute() or "\\" in member.linkname or "\x00" in member.linkname:
        raise ValueError(f"Unsafe archive link: {member.name!r}")
    combined = (path.parent / target) if member.issym() else target
    parts: list[str] = []
    for part in combined.parts:
        if part == "..":
            if not parts:
                raise ValueError(f"Archive link escapes installation: {member.name!r}")
            parts.pop()
        elif part != ".":
            parts.append(part)
    return PurePosixPath(*parts)


def extract_verified_archive(archive: Path, destination: Path, expected: str) -> str:
    """Hash before opening the tar; reject traversal, special files and link parents.

    Test archives used to exercise this boundary contain text only; extraction
    checks are not physical engine acceptance tests.
    """
    digest = verified_digest(archive, expected)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Archive destination must be empty.")
    with tarfile.open(archive, mode="r:*") as bundle:
        entries: dict[PurePosixPath, tarfile.TarInfo] = {}
        for member in bundle.getmembers():
            path = _member_path(member.name)
            if path == PurePosixPath("."):
                if not member.isdir():
                    raise ValueError("Archive root entry must be a directory.")
                continue
            if path in entries:
                if member.isdir() and entries[path].isdir():
                    continue
                raise ValueError(f"Duplicate archive member: {member.name!r}")
            if not (member.isdir() or member.isfile() or member.issym() or member.islnk()):
                raise ValueError(f"Unsupported archive member type: {member.name!r}")
            if member.issym() or member.islnk():
                _link_target(member, path)
            entries[path] = member
        for path, member in entries.items():
            for parent in path.parents:
                if parent in entries and not entries[parent].isdir():
                    raise ValueError(f"Archive member has a non-directory parent: {member.name!r}")
            if member.islnk():
                target = entries.get(_link_target(member, path))
                if target is None or not target.isfile():
                    raise ValueError(f"Hard link must name a regular archived file: {member.name!r}")
        destination.mkdir(parents=True, exist_ok=True)
        root = destination.resolve()
        # Extract regular files before links, never following an archived link.
        for path, member in entries.items():
            output = root.joinpath(*path.parts)
            output.parent.mkdir(parents=True, exist_ok=True)
            if member.isdir():
                output.mkdir(exist_ok=True)
            elif member.isfile():
                source = bundle.extractfile(member)
                if source is None:
                    raise ValueError(f"Unreadable archive member: {member.name!r}")
                with source, output.open("xb") as stream:
                    shutil.copyfileobj(source, stream)
                output.chmod(0o644 | (member.mode & 0o111))
        for path, member in entries.items():
            output = root.joinpath(*path.parts)
            if member.issym():
                output.symlink_to(member.linkname)
            elif member.islnk():
                os.link(root.joinpath(*_link_target(member, path).parts), output)
        for path, member in entries.items():
            if member.issym():
                try:
                    resolved = root.joinpath(*path.parts).resolve(strict=True)
                except (OSError, RuntimeError) as exc:
                    raise ValueError(f"Archive symlink is broken or cyclic: {member.name!r}") from exc
                if not resolved.is_relative_to(root):
                    raise ValueError(f"Archive symlink escapes installation: {member.name!r}")
        # Source distributions include generated Autotools files whose ordering
        # relative to configure.ac/m4 inputs must survive extraction. Apply
        # timestamps after all writes and links, without following symlinks or
        # letting hard-link metadata override the regular file's timestamp.
        for path, member in entries.items():
            if member.isfile() or member.isdir():
                os.utime(root.joinpath(*path.parts), (member.mtime, member.mtime),
                         follow_symlinks=False)
    return digest


def require_platform(system: str, machine: str, manifest: dict) -> None:
    if system != manifest["platform"] or machine != manifest["architecture"]:
        raise ValueError(
            f"This archive requires {manifest['platform']} {manifest['architecture']}; "
            f"host is {system} {machine}. Use the corresponding local/HPC distribution."
        )


def native_executable(path: Path) -> None:
    if not path.is_file() or path.is_symlink() or not os.access(path, os.X_OK):
        raise ValueError(f"Expected an executable regular file: {path}")
    with path.open("rb") as stream:
        header = stream.read(20)
    if header[:6] != b"\x7fELF\x02\x01" or header[18:20] != b"\x3e\x00":
        raise ValueError(f"Expected a native Linux x86-64 ELF executable: {path}")


def probe(argv: list[str], environment: dict[str, str], directory: Path) -> subprocess.CompletedProcess:
    return subprocess.run(argv, env=environment, cwd=directory, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, timeout=30, check=False)


def exact_version(output: str, engine: str, expected: str) -> str:
    if engine == "orca":
        pattern = r"(?:Program\s+Version|ORCA[- ]Version)\s+(\d+\.\d+\.\d+)(?![\w.])"
    elif engine == "openmpi":
        pattern = r"Open\s+MPI\)?\s*:?\s+v?(\d+\.\d+\.\d+)(?![\w.])"
    else:
        raise ValueError(f"Unknown engine version format: {engine}")
    versions = set(re.findall(pattern, output, re.IGNORECASE))
    if versions != {expected}:
        raise ValueError(f"Expected {engine} version {expected}, observed {sorted(versions)}")
    return expected


def _external_path(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved.is_relative_to(REPOSITORY_ROOT):
        raise ValueError("Licensed engine installation must be outside the source checkout.")
    return resolved


def provision(archive: Path, install_root: Path, mpi_prefix: Path, manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text())
    require_platform(platform.system(), platform.machine(), manifest)
    if archive.name != manifest["archive_name"]:
        raise ValueError(f"Expected archive filename {manifest['archive_name']!r}")
    install_root = _external_path(install_root)
    if install_root.exists():
        raise ValueError("Install root already exists; choose a fresh job-local installation path.")
    mpi_prefix = mpi_prefix.expanduser().resolve()
    mpirun = mpi_prefix / "bin/mpirun"
    mpi_info = mpi_prefix / "bin/ompi_info"
    for executable in (mpirun, mpi_info):
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise ValueError(f"Required Open MPI executable is missing: {executable}")
        native_executable(executable.resolve())
    mpi_libraries = [mpi_prefix / part for part in ("lib", "lib64") if (mpi_prefix / part).is_dir()]
    if not any(list(path.glob("libmpi.so*")) for path in mpi_libraries):
        raise ValueError("The selected Open MPI prefix has no libmpi shared library.")
    environment = os.environ.copy()
    environment["PATH"] = os.pathsep.join([str(mpirun.parent), environment.get("PATH", "")])
    environment["LD_LIBRARY_PATH"] = os.pathsep.join(
        [*(str(path) for path in mpi_libraries), environment.get("LD_LIBRARY_PATH", "")]
    ).rstrip(os.pathsep)
    with tempfile.TemporaryDirectory(prefix="cochem-mpi-probe-") as temporary:
        result = probe([str(mpirun), "--version"], environment, Path(temporary))
        if result.returncode:
            raise ValueError(f"Open MPI version probe failed with exit {result.returncode}")
        mpi_version = exact_version(result.stdout, "openmpi", manifest["openmpi_version"])
        mpi_banner = result.stdout
        info = probe([str(mpi_info), "--version"], environment, Path(temporary))
        if info.returncode:
            raise ValueError(f"Open MPI installation probe failed with exit {info.returncode}")
        exact_version(info.stdout, "openmpi", manifest["openmpi_version"])
    install_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".cochem-orca-install-", dir=install_root.parent) as temporary:
        staging = Path(temporary) / "distribution"
        archive_sha = extract_verified_archive(archive, staging, manifest["sha256"])
        candidates = list(staging.rglob("orca"))
        if len(candidates) != 1:
            raise ValueError(f"Expected exactly one ORCA executable, found {len(candidates)}")
        candidate = candidates[0]
        native_executable(candidate)
        relative_binary = candidate.relative_to(staging)
        staging.rename(install_root)
    try:
        binary = install_root / relative_binary
        environment["PATH"] = os.pathsep.join([str(binary.parent), environment["PATH"]])
        environment["LD_LIBRARY_PATH"] = os.pathsep.join(
            [str(binary.parent), environment["LD_LIBRARY_PATH"]]
        )
        with tempfile.TemporaryDirectory(prefix="cochem-orca-probe-") as temporary:
            # Bare ORCA emits its banner and may return nonzero because no input
            # was supplied. Scientific success is checked by separate real jobs.
            result = probe([str(binary)], environment, Path(temporary))
        orca_version = exact_version(result.stdout, "orca", manifest["orca_version"])
        if result.returncode < 0:
            raise ValueError(f"ORCA version probe terminated by signal {-result.returncode}")
        files = {}
        for path in sorted(install_root.rglob("*")):
            if path.is_symlink():
                files[str(path.relative_to(install_root))] = {"symlink": os.readlink(path)}
            elif path.is_file():
                files[str(path.relative_to(install_root))] = {
                    "sha256": sha256_file(path), "bytes": path.stat().st_size,
                }
        provenance_path = install_root / "cochem-orca-provenance.json"
        provenance = {
            "schema_version": 1, "scope": "archive integrity and executable version; no calculation acceptance",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "distribution": manifest, "archive_sha256": archive_sha,
            "manifest_sha256": sha256_file(manifest_path),
            "executable": str(binary), "orca_version": orca_version,
            "openmpi_version": mpi_version, "mpi_prefix": str(mpi_prefix),
            "openmpi_version_output": mpi_banner, "ompi_info_version_output": info.stdout,
            "mpirun": str(mpirun), "mpirun_sha256": sha256_file(mpirun),
            "mpi_library_sha256": {
                str(path): sha256_file(path)
                for directory in mpi_libraries for path in directory.glob("libmpi.so*")
                if path.is_file() and not path.is_symlink()
            },
            "mpi_library_paths": [str(path) for path in mpi_libraries],
            "version_probe_returncode": result.returncode,
            "version_probe_output": result.stdout, "files": files,
        }
        provenance_path.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
        return {
            "executable": str(binary), "orca_version": orca_version,
            "archive_sha256": archive_sha, "openmpi_version": mpi_version,
            "mpirun": str(mpirun), "mpi_prefix": str(mpi_prefix),
            "path_entries": [str(binary.parent), str(mpirun.parent)],
            "ld_library_path": environment["LD_LIBRARY_PATH"],
            "provenance": str(provenance_path),
        }
    except BaseException:
        shutil.rmtree(install_root)
        raise


def github_environment(result: dict, env_path: Path, path_path: Path) -> None:
    values = {
        "COCHEM_ORCA_BIN": result["executable"], "ORCA_CMD": result["executable"],
        "ORCA_PATH": result["executable"], "COCHEM_MPIRUN_BIN": result["mpirun"],
        "MPI_HOME": result["mpi_prefix"], "LD_LIBRARY_PATH": result["ld_library_path"],
        "COCHEM_ORCA_PROVENANCE": result["provenance"],
    }
    for value in [*values.values(), *result["path_entries"]]:
        if "\n" in value or "\r" in value or "\x00" in value:
            raise ValueError("Multiline or NUL-containing values cannot be written to Actions environment files.")
    with env_path.open("a") as stream:
        stream.writelines(f"{key}={value}\n" for key, value in values.items())
    with path_path.open("a") as stream:
        stream.writelines(f"{value}\n" for value in result["path_entries"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--mpi-prefix", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--github-env", type=Path)
    parser.add_argument("--github-path", type=Path)
    args = parser.parse_args()
    if bool(args.github_env) != bool(args.github_path):
        parser.error("--github-env and --github-path must be supplied together")
    try:
        result = provision(args.archive, args.install_root, args.mpi_prefix, args.manifest)
        if args.github_env:
            github_environment(result, args.github_env, args.github_path)
    except (ValueError, OSError, subprocess.SubprocessError, tarfile.TarError) as exc:
        parser.exit(1, f"ORCA provisioning failed: {exc}\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
