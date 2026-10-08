#!/usr/bin/env python3
"""Provision CFOUR only from an explicit, authentic private distribution record.

No CFOUR version, archive checksum, layout, or banner format is assumed. The
reviewed record must describe the actual distribution and metadata invocation.
Archive/native/version checks are installation evidence, not quantum acceptance.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from scripts.provision_orca import (
    REPOSITORY_ROOT,
    archive_space_preflight,
    extract_verified_archive,
    native_executable,
    require_platform,
    sha256_file,
)

SHA256 = re.compile(r"[0-9a-f]{64}")


def _relative(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or any(character in value for character in "\r\n\x00")
    ):
        raise ValueError("CFOUR distribution paths must be single-line relative paths.")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in (".", "..") for part in value.split("/")):
        raise ValueError("CFOUR distribution paths must not contain traversal segments.")
    return value


def load_distribution_manifest(path: Path) -> dict[str, Any]:
    """Require a privately supplied authentic distribution; there is no default."""
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate CFOUR manifest fields are forbidden.")
            result[key] = value
        return result

    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise ValueError("Supply a bounded regular private CFOUR distribution manifest.")
    manifest = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON.")),
    )
    required = {
        "schema_version", "repository", "release_tag", "archive_name", "sha256",
        "cfour_version", "platform", "architecture", "entrypoint", "native_executables",
        "runtime_path_directories", "runtime_library_directories", "metadata_probe",
        "source",
    }
    if (
        not isinstance(manifest, dict)
        or set(manifest) != required
        or manifest["schema_version"] != 1
    ):
        raise ValueError("The explicit CFOUR distribution schema is incomplete.")
    strings = {
        "repository", "release_tag", "archive_name", "sha256", "cfour_version",
        "platform", "architecture", "entrypoint", "source",
    }
    if any(
        not isinstance(manifest[key], str) or not manifest[key]
        or any(character in manifest[key] for character in "\r\n\x00")
        for key in strings
    ):
        raise ValueError("CFOUR distribution identity must use nonempty single-line strings.")
    if (
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9._-]*", manifest["repository"]) is None
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", manifest["release_tag"]) is None
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", manifest["archive_name"]) is None
        or SHA256.fullmatch(manifest["sha256"]) is None
        or manifest["platform"] != "Linux"
        or manifest["architecture"] != "x86_64"
    ):
        raise ValueError("This Actions installer requires an approved Linux x86_64 identity.")
    _relative(manifest["entrypoint"])
    native = manifest["native_executables"]
    if (
        not isinstance(native, dict) or not native
        or any(
            _relative(key) != key
            or not isinstance(value, str) or SHA256.fullmatch(value) is None
            for key, value in native.items()
        )
    ):
        raise ValueError("Pin every required genuine native executable by path and SHA-256.")
    # The driver may be an authentic script in a real distribution; its archive
    # hash is bound independently, while named computational executables must
    # pass actual ELF readback. There is no substitute script/native fallback.
    for key in ("runtime_path_directories", "runtime_library_directories"):
        if not isinstance(manifest[key], list) or (
            key == "runtime_path_directories" and not manifest[key]
        ):
            raise ValueError("Declare the actual CFOUR runtime directories.")
        if any(_relative(value) != value for value in manifest[key]):
            raise ValueError("Invalid runtime directory.")
        if len(set(manifest[key])) != len(manifest[key]):
            raise ValueError("Runtime directories must be distinct.")
    probe = manifest["metadata_probe"]
    if (
        not isinstance(probe, dict)
        or set(probe) != {"arguments", "expected_returncode", "version_pattern"}
        or not isinstance(probe["arguments"], list)
        or any(
            not isinstance(argument, str)
            or not argument
            or any(character in argument for character in "\r\n\x00")
            for argument in probe["arguments"]
        )
        or type(probe["expected_returncode"]) is not int
        or not -255 <= probe["expected_returncode"] <= 255
        or not isinstance(probe["version_pattern"], str)
        or len(probe["version_pattern"]) > 1024
    ):
        raise ValueError("Supply the genuine CFOUR metadata invocation and observed banner rule.")
    pattern = re.compile(probe["version_pattern"], re.MULTILINE)
    if "version" not in pattern.groupindex:
        raise ValueError("The reviewed banner rule requires a named version capture.")
    return manifest


def observed_version(output: str, manifest: dict[str, Any], returncode: int) -> str:
    probe = manifest["metadata_probe"]
    pattern = re.compile(probe["version_pattern"], re.MULTILINE)
    versions = {match.group("version") for match in pattern.finditer(output)}
    if returncode != probe["expected_returncode"] or versions != {manifest["cfour_version"]}:
        raise ValueError("The native CFOUR metadata response differs from the reviewed record.")
    return manifest["cfour_version"]


def _contained(root: Path, relative: str) -> Path:
    path = root / relative
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise ValueError("A CFOUR distribution member escapes the installation.")
    return resolved


def provision(archive: Path, install_root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = load_distribution_manifest(manifest_path)
    require_platform(platform.system(), platform.machine(), manifest)
    if archive.name != manifest["archive_name"]:
        raise ValueError("The CFOUR archive name differs from its authentic descriptor.")
    root = install_root.expanduser().resolve()
    if root.is_relative_to(REPOSITORY_ROOT) or root.exists():
        raise ValueError("Use a new CFOUR installation outside the source checkout.")
    disk = archive_space_preflight(archive, root, manifest["sha256"])
    root.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix=".cochem-cfour-install-", dir=root.parent) as temporary:
            staging = Path(temporary) / "distribution"
            extract_verified_archive(archive, staging, manifest["sha256"])
            for relative, expected in manifest["native_executables"].items():
                native = _contained(staging, relative)
                native_executable(native)
                if sha256_file(native) != expected:
                    raise ValueError("A native CFOUR executable differs from the reviewed SHA-256.")
            entry = _contained(staging, manifest["entrypoint"])
            if not entry.is_file() or not os.access(entry, os.X_OK):
                raise ValueError("The authentic CFOUR entry point is not executable.")
            for relative in manifest["runtime_path_directories"] + manifest["runtime_library_directories"]:
                if not _contained(staging, relative).is_dir():
                    raise ValueError("A required CFOUR runtime directory is absent.")
            staging.rename(root)
        entry = _contained(root, manifest["entrypoint"])
        environment = os.environ.copy()
        paths = [str(_contained(root, value)) for value in manifest["runtime_path_directories"]]
        libraries = [str(_contained(root, value)) for value in manifest["runtime_library_directories"]]
        environment["PATH"] = os.pathsep.join([*paths, environment.get("PATH", "")])
        environment["LD_LIBRARY_PATH"] = os.pathsep.join(
            [*libraries, environment.get("LD_LIBRARY_PATH", "")]
        ).rstrip(os.pathsep)
        with tempfile.TemporaryDirectory(prefix="cochem-cfour-metadata-") as temporary:
            command = [str(entry), *manifest["metadata_probe"]["arguments"]]
            completed = subprocess.run(
                command, cwd=temporary, env=environment, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                timeout=30, check=False,
            )
        version = observed_version(completed.stdout, manifest, completed.returncode)
        inventory = {
            str(path.relative_to(root)): {
                "sha256": sha256_file(path), "bytes": path.stat().st_size,
            }
            for path in sorted(root.rglob("*")) if path.is_file() and not path.is_symlink()
        }
        record = {
            "schema_version": "cochem.cfour-installation/1",
            "scope": "approved archive, native executable readback, metadata only",
            "distribution": manifest, "manifest_sha256": sha256_file(manifest_path),
            "archive_sha256": manifest["sha256"], "version": version,
            "executable": str(entry), "native_executables": manifest["native_executables"],
            "metadata_command": command, "metadata_returncode": completed.returncode,
            "metadata_output": completed.stdout, "files": inventory,
            "disk_preflight": disk, "path_entries": paths,
            "ld_library_path": environment["LD_LIBRARY_PATH"],
            "scientific_calculation_executed": False,
            "scientific_profile_qualified": False,
        }
        (root / "cochem-cfour-provenance.json").write_text(
            json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        return record
    except BaseException:
        if root.exists():
            shutil.rmtree(root)
        raise


def github_environment(record: dict[str, Any], environment_file: Path, path_file: Path) -> None:
    values = {
        "CFOUR_CMD": record["executable"],
        "COCHEM_CFOUR_BIN": record["executable"],
        "COCHEM_CFOUR_LIBRARY_PATH": record["ld_library_path"],
    }
    with environment_file.open("a", encoding="utf-8") as stream:
        for key, value in values.items():
            if any(character in value for character in "\r\n\x00"):
                raise ValueError("Invalid multiline CFOUR runtime setting.")
            stream.write(f"{key}={value}\n")
    with path_file.open("a", encoding="utf-8") as stream:
        for value in record["path_entries"]:
            if any(character in value for character in "\r\n\x00"):
                raise ValueError("Invalid multiline CFOUR runtime path.")
            stream.write(value + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--github-env", type=Path)
    parser.add_argument("--github-path", type=Path)
    args = parser.parse_args()
    record = provision(args.archive, args.install_root, args.manifest)
    if (args.github_env is None) != (args.github_path is None):
        parser.error("--github-env and --github-path must be supplied together.")
    if args.github_env is not None and args.github_path is not None:
        github_environment(record, args.github_env, args.github_path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
