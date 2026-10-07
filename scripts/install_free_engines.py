#!/usr/bin/env python3
"""Install pinned, isolated CPU science backends without changing the BASE venv.

Linux x86_64 binaries are downloaded from their upstream GitHub releases over
verified TLS and checked against fixed SHA-256 digests. The xTB digest is also
published alongside its release. Python silos use closed exact-version locks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tarfile
import urllib.request


REPOSITORY = Path(__file__).resolve().parents[1]
BINARY_RELEASES = {
    "xtb": {
        "url": "https://github.com/grimme-lab/xtb/releases/download/v6.7.1/xtb-6.7.1-linux-x86_64.tar.xz",
        "sha256": "62a8d18778286e815292ee53d76ce447daf460a4dea3782c0f25cbac7019b5df",
        "executable": "xtb-dist/bin/xtb",
        "version": "6.7.1",
    },
    "crest": {
        "url": "https://github.com/crest-lab/crest/releases/download/v3.0.2/crest-gnu-12-ubuntu-latest.tar.xz",
        "sha256": "8e5bd18b06f99741ebd7bb71b3a996295f391b2f076aaeab739740f709e9554d",
        "executable": "crest/crest",
        "version": "3.0.2",
    },
    "gxtb": {
        "url": "https://raw.githubusercontent.com/grimme-lab/g-xtb/23f81c2db64fa4272c25b86f8776ce862aeb59e2/binaries/xtb-6.7.1-gxtb-140526-linux-x86_64.tar.xz",
        "sha256": "cdfb81164f8d3300fc451dbbf2414528b533e71f7a30ec824b564cd30d6d9e5c",
        "executable": "xtb-6.7.1/bin/xtb",
        "version": "6.7.1",
    },
    "mopac": {
        "url": "https://github.com/openmopac/mopac/releases/download/v23.2.1/mopac-23.2.1-linux.tar.gz",
        "sha256": "038388e0cafe0ed21f63f73fcc9ee96af29c6d170e1721c029b091358a373970",
        "executable": "mopac-23.2.1-linux/bin/mopac",
        "version": "23.2.1",
    },
}


def external_path(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if path == REPOSITORY or path.is_relative_to(REPOSITORY):
        raise argparse.ArgumentTypeError("Engine installations and evidence must be outside the source checkout")
    return path


def clean_environment() -> dict[str, str]:
    return {key: value for key, value in os.environ.items()
            if key not in {"PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE", "VIRTUAL_ENV"}}


def run(argv: list[str], timeout: int = 600) -> str:
    process = subprocess.run(argv, env=clean_environment(), check=True,
                             text=True, capture_output=True, timeout=timeout)
    return process.stdout


def install(root: Path, name: str) -> dict:
    target = root / name
    if name in BINARY_RELEASES:
        if platform.system() != "Linux" or platform.machine() not in {"x86_64", "AMD64"}:
            raise RuntimeError("Pinned xTB/CREST releases require Linux x86_64")
        release = BINARY_RELEASES[name]
        cache = root / "downloads"
        cache.mkdir(parents=True, exist_ok=True)
        archive = cache / release["url"].rsplit("/", 1)[-1]
        if not archive.exists():
            temporary = archive.with_suffix(archive.suffix + ".partial")
            with urllib.request.urlopen(release["url"], timeout=120) as response, temporary.open("wb") as destination:
                while chunk := response.read(1024 * 1024):
                    destination.write(chunk)
            temporary.replace(archive)
        with archive.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        if digest != release["sha256"]:
            raise RuntimeError(f"SHA-256 mismatch for {archive}")
        target.mkdir(parents=True, exist_ok=True)
        executable = target / release["executable"]
        with tarfile.open(archive) as package:
            if executable.exists():
                for member in package.getmembers():
                    installed_path = target / member.name.removeprefix("./")
                    if not installed_path.resolve().is_relative_to(target.resolve()):
                        raise RuntimeError(f"Installed package escapes its silo: {installed_path}")
                    if member.isfile():
                        if not installed_path.is_file() or installed_path.is_symlink():
                            raise RuntimeError(f"Missing installed package file: {installed_path}")
                        with package.extractfile(member) as source, installed_path.open("rb") as installed:
                            if hashlib.file_digest(source, "sha256").digest() != hashlib.file_digest(installed, "sha256").digest():
                                raise RuntimeError(f"Installed file differs from pinned release: {installed_path}")
                    elif member.issym() and (not installed_path.is_symlink() or os.readlink(installed_path) != member.linkname):
                        raise RuntimeError(f"Installed package link differs from pinned release: {installed_path}")
            else:
                package.extractall(target, filter="data")
        version_output = run([str(executable), "--version"], timeout=30)
        if release["version"] not in version_output:
            raise RuntimeError(f"Unexpected {name} version: {version_output}")
        return {**release, "path": str(executable), "version_output": version_output.strip()}

    interpreter = target / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not interpreter.exists():
        if target.exists() and any(target.iterdir()):
            raise RuntimeError(f"Refusing nonempty non-venv directory: {target}")
        run([sys.executable, "-I", "-m", "venv", str(target)], timeout=120)
    # Validate the interpreter before pip can mutate anything. An existing
    # bin/python symlink alone is not evidence of an isolated virtual environment.
    run([str(interpreter), "-I", "-c", "import pathlib,site,sys; p=pathlib.Path(sys.argv[1]).resolve(); assert pathlib.Path(sys.prefix).resolve()==p and sys.prefix!=sys.base_prefix and not site.ENABLE_USER_SITE; assert 'include-system-site-packages = false' in (p/'pyvenv.cfg').read_text().lower()", str(target)], timeout=30)
    requirements = Path(__file__).resolve().parent / "free_engine_requirements" / f"{name}.txt"
    pins = requirements.read_text().splitlines()
    run([str(interpreter), "-I", "-m", "pip", "install", "--disable-pip-version-check",
         "--no-input", "--only-binary=:all:", "--no-deps", "-r", str(requirements)])
    run([str(interpreter), "-I", "-m", "pip", "check"], timeout=60)
    probe = """
import importlib.metadata, json, pathlib, site, sys
root = pathlib.Path(sys.argv[1]).resolve()
assert pathlib.Path(sys.prefix).resolve() == root
assert sys.prefix != sys.base_prefix and not site.ENABLE_USER_SITE
assert 'include-system-site-packages = false' in (root/'pyvenv.cfg').read_text().lower()
for entry in sys.path:
    p = pathlib.Path(entry).resolve()
    if 'site-packages' in p.parts or 'dist-packages' in p.parts:
        assert p.is_relative_to(root), 'external package path in silo'
pins = dict(item.split('==', 1) for item in json.loads(sys.argv[2]) if item)
versions = {name: importlib.metadata.version(name) for name in pins}
assert versions == pins, 'installed versions differ from lock'
print(json.dumps(versions))
"""
    packages = json.loads(run([str(interpreter), "-I", "-c", probe, str(target), json.dumps(pins)], timeout=60))
    return {"python": str(interpreter), "packages": packages,
            "requirements_sha256": hashlib.sha256(requirements.read_bytes()).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=external_path)
    parser.add_argument("--engines", nargs="+", choices=[*BINARY_RELEASES, "pyscf", "openmm"], default=[*BINARY_RELEASES, "pyscf", "openmm"])
    parser.add_argument("--output", required=True, type=external_path)
    arguments = parser.parse_args()
    arguments.root.mkdir(parents=True, exist_ok=True)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    report = {"platform": platform.platform(), "root": str(arguments.root), "engines": {}}
    try:
        for name in arguments.engines:
            print(f"Installing and validating {name}", flush=True)
            report["engines"][name] = install(arguments.root, name)
    except Exception as error:
        report["error"] = str(error)
        raise
    finally:
        arguments.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
