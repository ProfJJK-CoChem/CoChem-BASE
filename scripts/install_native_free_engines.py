"""Provision frozen native macOS xTB/CREST packages outside the source tree.

The reviewed lock contains every conda-forge dependency URL and SHA-256. The
installer verifies those archives before an explicit, offline prefix install;
there is no runtime dependency solver or floating package version. Readiness
requires actual host-native engine execution and a retained full-file seal.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import uuid

try:
    from scripts.manage_modules import _atomic_json, _build_env, _redact
except ModuleNotFoundError:
    from manage_modules import _atomic_json, _build_env, _redact

REPOSITORY = Path(__file__).resolve().parents[1]
LOCK_SCHEMA = "cochem.native-free-engine-lock/1"
RECEIPT_SCHEMA = "cochem.native-free-engines/1"
LOCK_DIRECTORY = Path(__file__).with_name("native_free_engine_locks")


def native_subdir() -> str:
    if platform.system() != "Darwin":
        raise RuntimeError("Native macOS provisioning must run on a real macOS host.")
    machine = platform.machine()
    if machine in {"arm64", "aarch64"}:
        return "osx-arm64"
    if machine in {"x86_64", "AMD64"}:
        return "osx-64"
    raise RuntimeError(f"No reviewed native engine lock exists for macOS architecture {machine!r}.")


def load_lock(subdir: str) -> dict:
    if subdir not in {"osx-64", "osx-arm64"}:
        raise ValueError("Only reviewed macOS architecture locks are supported.")
    path = LOCK_DIRECTORY / f"{subdir}.json"
    lock = json.loads(path.read_text(encoding="utf-8"))
    if (lock.get("schema_version") != LOCK_SCHEMA or lock.get("platform") != subdir
            or lock.get("engines") != {"xtb": "6.7.1", "crest": "3.0.2"}
            or not isinstance(lock.get("packages"), list) or not lock["packages"]):
        raise ValueError("The reviewed native engine lock has an invalid contract.")
    names = set()
    for package in lock["packages"]:
        url = urllib.parse.urlsplit(package.get("url", ""))
        if (url.scheme != "https" or url.hostname != "conda.anaconda.org"
                or not url.path.startswith(f"/conda-forge/{package.get('subdir')}/")
                or package.get("subdir") not in {subdir, "noarch"} or url.query or url.fragment
                or not re.fullmatch(r"[0-9a-f]{64}", str(package.get("sha256", "")))
                or not re.fullmatch(r"[0-9a-f]{32}", str(package.get("md5", "")))
                or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", str(package.get("name", "")))
                or package["name"] in names):
            raise ValueError("A native package differs from its reviewed channel, architecture or integrity contract.")
        names.add(package["name"])
    for engine, version in lock["engines"].items():
        records = [p for p in lock["packages"] if p["name"] == engine]
        if len(records) != 1 or records[0]["version"] != version:
            raise ValueError("A native engine differs from the approved scientific version.")
    manager = lock.get("manager", {})
    expected_url = f"https://github.com/mamba-org/micromamba-releases/releases/download/2.9.0-0/micromamba-{subdir}"
    if (manager.get("url") != expected_url or manager.get("version") != "2.9.0"
            or not re.fullmatch(r"[0-9a-f]{64}", str(manager.get("sha256", "")))):
        raise ValueError("The native package manager is not an approved immutable release.")
    return lock


def lock_sha256(subdir: str) -> str:
    return hashlib.sha256((LOCK_DIRECTORY / f"{subdir}.json").read_bytes()).hexdigest()


def owned_path(root: Path, relative: str) -> Path:
    path = root / relative
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError("Native engine artifacts must not redirect outside their owned directory.")
    return path


def download_verified(url: str, digest: str, destination: Path) -> Path:
    if destination.is_symlink():
        raise ValueError("A cached native package must not be a symbolic link.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        temporary = destination.with_name(destination.name + ".partial")
        if temporary.is_symlink():
            raise ValueError("A native package download path was redirected.")
        with urllib.request.urlopen(url, timeout=60) as response, temporary.open("wb") as output:
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > 512 * 1024 * 1024:
                    raise RuntimeError("A native package exceeds its download size budget.")
                output.write(chunk)
        temporary.replace(destination)
    with destination.open("rb") as source:
        actual = hashlib.file_digest(source, "sha256").hexdigest()
    if actual != digest:
        raise RuntimeError("A native package differs from its published SHA-256; it was not executed or installed.")
    return destination


def inventory(prefix: Path) -> dict:
    records = {}
    for path in sorted(prefix.rglob("*")):
        if path.is_symlink():
            if not path.resolve().is_relative_to(prefix):
                raise RuntimeError("A native engine runtime link escapes its isolated prefix.")
            records[path.relative_to(prefix).as_posix()] = {"symlink": os.readlink(path)}
        elif path.is_file():
            with path.open("rb") as source:
                records[path.relative_to(prefix).as_posix()] = {"sha256": hashlib.file_digest(source, "sha256").hexdigest(),
                    "size": path.stat().st_size, "mode": path.stat().st_mode & 0o777}
    if not records:
        raise RuntimeError("The native engine runtime is empty.")
    return records


def retain_interrupted_prefix(root: Path, prefix: Path) -> Path | None:
    """Keep an unaccepted attempt intact so the GUI can retry without a terminal."""
    if prefix != owned_path(root, f"prefixes/{prefix.name}"):
        raise ValueError("Only an owned native engine prefix may be retained for retry.")
    if owned_path(root, "installation.json").exists():
        raise RuntimeError("An accepted native runtime must be verified rather than replaced.")
    if not prefix.exists() or not any(prefix.iterdir()):
        return None
    retained = owned_path(root, f"interrupted/{prefix.name}-{uuid.uuid4().hex}")
    retained.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    prefix.rename(retained)
    _atomic_json(retained.parent / f"{retained.name}.json", {
        "schema_version": "cochem.native-engine-interruption/1", "status": "retained",
        "original_path": str(prefix), "retained_path": str(retained),
        "native_execution_verified": False,
    })
    return retained


def verify_native_runtime(root: Path) -> dict:
    root = root.expanduser().resolve()
    path = owned_path(root, "installation.json")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    subdir = receipt.get("platform")
    load_lock(subdir)
    if (receipt.get("schema_version") != RECEIPT_SCHEMA or receipt.get("native_execution_verified") is not True
            or receipt.get("lock_sha256") != lock_sha256(subdir)):
        raise RuntimeError("The native engine runtime has no current reviewed execution receipt.")
    prefix = owned_path(root, f"prefixes/{subdir}-{receipt['lock_sha256'][:16]}")
    if receipt.get("prefix") != str(prefix) or inventory(prefix) != receipt.get("files"):
        raise RuntimeError("The native engine runtime changed after its accepted installation.")
    for name, record in receipt.get("engines", {}).items():
        expected = prefix / "bin" / name
        if record.get("path") != str(expected) or record.get("version") != load_lock(subdir)["engines"].get(name):
            raise RuntimeError("The native engine executable differs from its reviewed runtime.")
        with expected.open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != record.get("binary_sha256"):
                raise RuntimeError("The native engine binary changed after its accepted installation.")
    if set(receipt.get("engines", {})) != {"xtb", "crest"}:
        raise RuntimeError("The native free-engine receipt is incomplete.")
    return receipt


def install(root: Path) -> dict:
    root = root.expanduser().resolve()
    if root == REPOSITORY or REPOSITORY in root.parents:
        raise ValueError("Native engine installation must remain outside SOURCE.")
    subdir = native_subdir()
    lock = load_lock(subdir)
    release = tuple(map(int, platform.mac_ver()[0].split(".")[:2]))
    if release < tuple(map(int, lock["minimum_macos"].split("."))):
        raise RuntimeError("The frozen native chemistry runtime requires macOS 11 or newer.")
    root.mkdir(parents=True, exist_ok=True, mode=0o750)
    from filelock import FileLock
    with FileLock(str(owned_path(root, "installation.lock")), timeout=10):
        if owned_path(root, "installation.json").is_file():
            return verify_native_runtime(root)
        manager = download_verified(lock["manager"]["url"], lock["manager"]["sha256"],
            owned_path(root, f"manager/{subdir}/micromamba"))
        manager.chmod(0o700)
        env = _build_env()
        version = subprocess.check_output([str(manager), "--version"], env=env, text=True, timeout=30).strip()
        if version != lock["manager"]["version"]:
            raise RuntimeError("The verified native package manager reports a different version.")
        explicit = ["@EXPLICIT"]
        for package in lock["packages"]:
            archive = download_verified(package["url"], package["sha256"],
                owned_path(root, f"packages/{package['sha256']}/{Path(urllib.parse.urlsplit(package['url']).path).name}"))
            explicit.append(archive.as_uri() + "#" + package["md5"])
        specification = owned_path(root, f"explicit-{subdir}.txt")
        specification.write_text("\n".join(explicit) + "\n", encoding="utf-8")
        digest = lock_sha256(subdir)
        prefix = owned_path(root, f"prefixes/{subdir}-{digest[:16]}")
        retain_interrupted_prefix(root, prefix)
        env["MAMBA_ROOT_PREFIX"] = str(owned_path(root, "manager-runtime"))
        subprocess.run([str(manager), "create", "--yes", "--offline", "--prefix", str(prefix), "--file", str(specification)],
            env=env, check=True, capture_output=True, text=True, timeout=600)
        env["PATH"] = str(prefix / "bin") + os.pathsep + env.get("PATH", "")
        env["XTBPATH"] = str(prefix / "share/xtb")
        engines = {}
        for name, expected in lock["engines"].items():
            executable = prefix / "bin" / name
            output = subprocess.check_output([str(executable), "--version"], env=env, text=True, timeout=30)
            if not re.search(r"(?<!\d)" + re.escape(expected) + r"(?![\d.])", output):
                raise RuntimeError(f"The actual native {name} executable reports a different scientific version.")
            with executable.open("rb") as source:
                engines[name] = {"path": str(executable), "version": expected,
                    "version_output": output.strip(), "binary_sha256": hashlib.file_digest(source, "sha256").hexdigest()}
        receipt = {"schema_version": RECEIPT_SCHEMA, "platform": subdir, "prefix": str(prefix),
            "lock_sha256": digest, "manager_sha256": lock["manager"]["sha256"], "engines": engines,
            "files": inventory(prefix), "native_execution_verified": True}
        _atomic_json(owned_path(root, "installation.json"), receipt)
        return verify_native_runtime(root)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        receipt = install(args.root)
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(_redact(str(error)), file=sys.stderr)
        return 1
    print(json.dumps({"status": "installed", "platform": receipt["platform"], "engines": receipt["engines"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
