#!/usr/bin/env python3
"""Install reviewed CoChem sources in separate environments, with verifiable receipts.

Installation and integrity verification are not scientific acceptance. Credentials
are available only to Git, never to package build/install hooks or module probes.
"""
from __future__ import annotations

import argparse
import contextlib
import email.parser
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

DEFAULT_MANIFEST = Path(__file__).with_name("module-distribution.json")
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_SCHEMA = "cochem.module-distribution/1"
RECEIPT_SCHEMA = "cochem.module-installation/1"
SOURCE_SCHEMA = "cochem.module-source/1"
ID_PATTERN = re.compile(r"[a-z][a-z0-9_-]*\Z")
REPOSITORY_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9._-]*\Z")
REQUIREMENT_PATTERN = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._-]*(?:\[[A-Za-z0-9_,.-]+\])?"
    r"(?:(?:===|==|!=|<=|>=|~=|<|>)[A-Za-z0-9.*+!_-]+"
    r"(?:,(?:===|==|!=|<=|>=|~=|<|>)[A-Za-z0-9.*+!_-]+)*)?\Z"
)


class ModuleInstallationError(RuntimeError):
    """An installation cannot be safely accepted."""


def _canonical_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _digest_json(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _validate_spec(module_id: str, spec: dict) -> None:
    if not isinstance(module_id, str) or not ID_PATTERN.fullmatch(module_id):
        raise ValueError("Module IDs must be lowercase identifiers without path components.")
    if not isinstance(spec, dict):
        raise ValueError(f"Invalid specification for {module_id}.")
    if not isinstance(spec.get("repository"), str) or not REPOSITORY_PATTERN.fullmatch(spec["repository"]):
        raise ValueError("Module repository must be a GitHub OWNER/REPOSITORY identity.")
    if not isinstance(spec.get("revision"), str) or not re.fullmatch(r"[0-9a-f]{40}", spec["revision"]):
        raise ValueError("Module revision must be an immutable 40-character lowercase Git SHA.")
    distribution = spec.get("distribution")
    if distribution is not None and (not isinstance(distribution, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", distribution)):
        raise ValueError("Invalid distribution name.")
    adapter = spec.get("adapter")
    if adapter is not None and (not isinstance(adapter, str) or not ID_PATTERN.fullmatch(adapter)):
        raise ValueError("Invalid module adapter identifier.")
    blocker = spec.get("install_blocker")
    if blocker is not None and (not isinstance(blocker, str) or not blocker.strip()
                                or any(char in blocker for char in "\r\n\x00")):
        raise ValueError("Module install_blocker must be a nonempty single-line explanation.")
    for key in ("operations", "adapter_requirements"):
        if not isinstance(spec.get(key), list) or not all(isinstance(value, str) for value in spec[key]):
            raise ValueError(f"Module {key} must be a list of strings.")
    if not all(ID_PATTERN.fullmatch(value) for value in spec["operations"]):
        raise ValueError("Invalid module operation identifier.")
    if not all(REQUIREMENT_PATTERN.fullmatch(value) for value in spec["adapter_requirements"]):
        raise ValueError("Adapter dependencies must be package-index requirements, without URLs or options.")


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict:
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != MANIFEST_SCHEMA or not isinstance(manifest.get("modules"), dict):
        raise ValueError(f"Module manifest requires schema_version {MANIFEST_SCHEMA} and modules mapping.")
    for module_id, spec in manifest["modules"].items():
        _validate_spec(module_id, spec)
    return manifest


def default_root() -> Path:
    return Path(os.environ.get("COCHEM_ARTIFACT_DIR", str(Path.home() / "CoChem_Artifacts"))) / "Modules"


def _paths(module_id: str, spec: dict, root: Path) -> tuple[Path, Path, Path, Path]:
    _validate_spec(module_id, spec)
    root = Path(root).expanduser().resolve()
    if root == REPOSITORY_ROOT or REPOSITORY_ROOT in root.parents:
        raise ValueError("Module installation root must be outside the BASE source checkout.")
    parent = root / module_id
    location = parent / spec["revision"]
    for path in (parent, location, location / "source", location / "env", parent / "installation.json", parent / "source.json"):
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("Module installation paths may not use redirected symbolic links.")
    return parent, location, location / "source", location / "env"


def _redact(message: str) -> str:
    for key in ("COCHEM_SOURCE_READ_TOKEN", "GITHUB_TOKEN", "GH_TOKEN", "BASE_SOURCE_READ_TOKEN", "ORCA_ASSET_READ_TOKEN"):
        value = os.environ.get(key)
        if value:
            message = message.replace(value, "[redacted]")
    return message


def _run(command: list[str], *, env: dict[str, str], label: str, cwd: Path | None = None) -> str:
    result = subprocess.run(command, env=env, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        # Hooks and HTTP diagnostics can contain credentials: sanitize before reporting.
        detail = _redact(result.stdout + "\n" + result.stderr)[-12000:]
        raise ModuleInstallationError(f"{label} failed (exit {result.returncode}).\n{detail}")
    return result.stdout.rstrip("\r\n")


def _build_env() -> dict[str, str]:
    blocked = {"COCHEM_SOURCE_READ_TOKEN", "BASE_SOURCE_READ_TOKEN", "ORCA_ASSET_READ_TOKEN", "GH_TOKEN", "GITHUB_TOKEN", "SSH_ASKPASS", "PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"}
    env = {key: value for key, value in os.environ.items()
           if key not in blocked and not key.startswith("GIT_")
           and not any(marker in key.upper() for marker in ("TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL", "AUTHORIZATION"))
           and not key.upper().endswith("_KEY")}
    # Prevent dependency Git commands from inheriting persisted checkout credentials.
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0", "PYTHONNOUSERSITE": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1"})
    return env


def _git_env() -> dict[str, str]:
    blocked = {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT"}
    env = {key: value for key, value in os.environ.items() if key not in blocked and not key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))}
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


@contextlib.contextmanager
def _git_auth():
    env = _git_env()
    token = env.get("COCHEM_SOURCE_READ_TOKEN")
    if not token:
        yield env, []
        return
    with tempfile.TemporaryDirectory(prefix="cochem-git-auth-") as temporary:
        helper = Path(temporary) / "askpass.sh"
        helper.write_text('#!/bin/sh\ncase "$1" in\n*sername*) printf "%s\\n" "x-access-token" ;;\n*) printf "%s\\n" "$COCHEM_SOURCE_READ_TOKEN" ;;\nesac\n', encoding="utf-8")
        helper.chmod(0o700)
        env["GIT_ASKPASS"] = str(helper)
        env["GIT_CONFIG_GLOBAL"] = os.devnull
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        # The helper reads the environment; neither its file nor Git config has a token.
        yield env, ["-c", "credential.helper=", "-c", "http.extraHeader="]


def _repository_url(spec: dict) -> str:
    """Single production transport; tests may replace this internal function."""
    return f"https://github.com/{spec['repository']}.git"


def _git(source: Path, *args: str) -> str:
    return _run(["git", "-C", str(source), *args], env=_build_env(), label="Git source verification")


def _source_integrity(source: Path, spec: dict, *, runner=None, checkpoint=None) -> dict:
    def git(*args):
        if checkpoint is not None:
            checkpoint()
        return (runner or _run)(["git", "-C", str(source), *args], env=_build_env(), label="Git source verification")
    if not (source / ".git").is_dir():
        raise ModuleInstallationError("Module checkout is missing its Git provenance.")
    if git("rev-parse", "HEAD") != spec["revision"]:
        raise ModuleInstallationError("Module checkout does not match its pinned revision.")
    # A detached HEAD has a literal SHA in .git/HEAD; never trust a moving branch.
    if (source / ".git" / "HEAD").read_text().strip() != spec["revision"]:
        raise ModuleInstallationError("Module checkout must remain detached at its pinned revision.")
    if git("status", "--porcelain", "--untracked-files=all", "--ignored"):
        raise ModuleInstallationError("Module checkout is dirty; retain it for inspection and use a clean installation root.")
    if git("config", "--get", "remote.origin.url") != _repository_url(spec):
        raise ModuleInstallationError("Module checkout origin differs from the reviewed repository.")
    files = git("ls-files", "-z").split("\0")
    digest = hashlib.sha256()
    for name in sorted(filter(None, files)):
        if checkpoint is not None:
            checkpoint()
        path = source / name
        if not path.resolve().is_relative_to(source.resolve()):
            raise ModuleInstallationError("Module source contains a symbolic link outside its checkout.")
        if path.is_symlink():
            content = os.readlink(path).encode()
            kind = b"symlink"
        elif path.is_file():
            content = path.read_bytes()
            kind = b"executable" if path.stat().st_mode & 0o111 else b"file"
        else:
            raise ModuleInstallationError("Module checkout contains an unsupported file or uninitialized submodule.")
        digest.update(name.encode() + b"\0" + kind + b"\0" + hashlib.sha256(content).digest())
    return {"source_tree_oid": git("rev-parse", "HEAD^{tree}"), "source_sha256": digest.hexdigest()}


# Executed with isolated Python. Hash every installed distribution, including
# dependencies, and cross-check wheel RECORD hashes without importing its code.
_PROBE = r'''
import base64, hashlib, importlib.metadata as metadata, json, pathlib, re, sys
prefix = pathlib.Path(sys.prefix).resolve()
normalize = lambda s: re.sub(r"[-_.]+", "-", s).lower()
requested = normalize(sys.argv[1])
packages = []
target = None
for dist in metadata.distributions():
    digest = hashlib.sha256()
    files = dist.files
    if files is None:
        raise RuntimeError("Installed distribution lacks a file inventory")
    for entry in sorted(files, key=str):
        if str(entry).endswith((".pyc", ".pyo")):
            continue
        path = pathlib.Path(dist.locate_file(entry)).resolve()
        if not path.is_relative_to(prefix) or not path.is_file():
            raise RuntimeError("Installed distribution file missing or outside isolated environment: " + str(entry))
        data = path.read_bytes()
        if entry.hash:
            actual = base64.urlsafe_b64encode(hashlib.new(entry.hash.mode, data).digest()).rstrip(b"=").decode()
            if actual != entry.hash.value:
                raise RuntimeError("Installed distribution RECORD hash mismatch: " + str(entry))
        digest.update(str(entry).encode() + b"\0" + hashlib.sha256(data).digest())
    item = {"name": dist.metadata["Name"], "version": dist.version, "files_sha256": digest.hexdigest()}
    packages.append(item)
    if normalize(item["name"]) == requested:
        if target is not None:
            raise RuntimeError("Duplicate installed target distribution")
        target = dict(item)
        target["direct_url"] = json.loads(dist.read_text("direct_url.json") or "null")
if target is None:
    raise RuntimeError("Requested distribution is not installed")
packages.sort(key=lambda item: normalize(item["name"]))
print(json.dumps({"distribution_metadata": target, "dependencies": packages,
    "installed_files_sha256": hashlib.sha256(json.dumps(packages, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}))
'''


def _probe(python: Path, distribution: str, *, runner=None) -> dict:
    return json.loads((runner or _run)([str(python), "-I", "-B", "-c", _PROBE, distribution], env=_build_env(), label="Installed distribution integrity probe"))


def _environment_integrity(environment: Path, *, checkpoint=None) -> str:
    """Hash the environment with trusted BASE Python before executing its code.

    RECORD alone misses bytecode, unowned .pth files and sitecustomize modules.
    Runtime callers must use -B so normal imports do not create new bytecode.
    """
    digest = hashlib.sha256()
    for path in sorted(environment.rglob("*")):
        if checkpoint is not None:
            checkpoint()
        relative = path.relative_to(environment).as_posix()
        if path.is_symlink():
            target = path.resolve(strict=True)
            digest.update(relative.encode() + b"\0link\0" + os.readlink(path).encode() + b"\0")
            if target.is_dir():
                if not target.is_relative_to(environment):
                    raise ModuleInstallationError("Isolated environment has an external directory link.")
                continue
        elif path.is_dir():
            digest.update(relative.encode() + b"\0directory\0")
            continue
        if not path.is_file():
            raise ModuleInstallationError("Isolated environment contains an unsupported special file.")
        content = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                if checkpoint is not None:
                    checkpoint()
                content.update(block)
        digest.update(relative.encode() + b"\0file\0" + content.digest())
    return digest.hexdigest()


def _python_path(environment: Path) -> Path:
    return environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _wheel_identity(path: Path) -> tuple[str, str]:
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(names) != 1:
            raise ModuleInstallationError("Built wheel has ambiguous distribution metadata.")
        metadata = email.parser.BytesParser().parsebytes(archive.read(names[0]))
        return metadata["Name"], metadata["Version"]


def _atomic_json(path: Path, value: dict) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".installation-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _read_receipt(path: Path) -> dict:
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ModuleInstallationError(f"Cannot read a valid module receipt at {path}.") from error
    if not isinstance(receipt, dict):
        raise ModuleInstallationError("Module receipt must be a JSON object.")
    return receipt


def verify_installation(module_id: str, spec: dict, root: Path) -> dict:
    if module_id == "topos" and spec.get("adapter") == "topos_handoff":
        from scripts.mandatory_ecosystem import verify
        return verify(spec, root)
    parent, location, source, environment = _paths(module_id, spec, root)
    receipt = _read_receipt(parent / "installation.json")
    expected = {"schema_version": RECEIPT_SCHEMA, "status": "installed", "module_id": module_id,
                "repository": spec["repository"], "revision": spec["revision"], "distribution": spec["distribution"],
                "manifest_spec_sha256": _digest_json(spec), "source_path": str(source),
                "python_path": str(_python_path(environment)), "adapter": spec.get("adapter"), "operations": spec["operations"]}
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise ModuleInstallationError("Installation receipt does not match the current reviewed module specification.")
    integrity = _source_integrity(source, spec)
    if any(receipt.get(key) != value for key, value in integrity.items()):
        raise ModuleInstallationError("Installed module source integrity differs from its receipt.")
    if receipt.get("environment_sha256") != _environment_integrity(environment):
        raise ModuleInstallationError("Isolated environment integrity differs from its receipt; no module code was executed.")
    probe = _probe(_python_path(environment), spec["distribution"])
    if any(receipt.get(key) != value for key, value in probe.items()):
        raise ModuleInstallationError("Installed distribution or dependency integrity differs from its receipt.")
    _run([str(_python_path(environment)), "-I", "-B", "-m", "pip", "check"], env=_build_env(), label="Dependency check")
    if receipt.get("pip_check") != {"passed": True}:
        raise ModuleInstallationError("Installation receipt does not record a successful dependency check.")
    return receipt


def fetch_module(module_id: str, spec: dict, root: Path) -> dict:
    """Obtain reviewed source, without representing it as an installed provider."""
    parent, location, source, _environment = _paths(module_id, spec, root)
    receipt_path = parent / "source.json"
    expected = {"schema_version": SOURCE_SCHEMA, "status": "downloaded", "module_id": module_id,
                "repository": spec["repository"], "revision": spec["revision"],
                "manifest_spec_sha256": _digest_json(spec), "source_path": str(source)}
    if receipt_path.exists():
        existing = _read_receipt(receipt_path)
        if existing.get("revision") == spec["revision"]:
            if any(existing.get(key) != value for key, value in expected.items()):
                raise ModuleInstallationError("Source receipt does not match the reviewed specification.")
            integrity = _source_integrity(source, spec)
            if any(existing.get(key) != value for key, value in integrity.items()):
                raise ModuleInstallationError("Downloaded module source integrity differs from its receipt.")
            return existing
    parent.mkdir(parents=True, exist_ok=True)
    # Atomic directory creation also excludes simultaneous installs at this pin.
    try:
        location.mkdir()
    except FileExistsError as error:
        raise ModuleInstallationError("An unreceipted installation already exists at this pin; inspect it before choosing a clean root.") from error
    _run(["git", "init", str(source)], env=_build_env(), label="Initialize module checkout")
    _run(["git", "-C", str(source), "remote", "add", "origin", _repository_url(spec)], env=_build_env(), label="Configure module origin")
    with _git_auth() as (git_env, options):
        _run(["git", *options, "-C", str(source), "fetch", "--depth", "1", "origin", spec["revision"]], env=git_env, label="Fetch pinned module source")
    _run(["git", "-C", str(source), "checkout", "--detach", spec["revision"]], env=_build_env(), label="Check out pinned module source")
    integrity = _source_integrity(source, spec)
    receipt = {**expected, **integrity}
    _atomic_json(receipt_path, receipt)
    return receipt


def install_module(module_id: str, spec: dict, root: Path, *, ecosystem_kit: Path | None = None) -> dict:
    if module_id == "topos" and spec.get("adapter") == "topos_handoff":
        from scripts.mandatory_ecosystem import install
        if ecosystem_kit is None:
            raise ModuleInstallationError(
                "Current TOPOS requires the complete reviewed BASE/TOPOS/TORQ kit; "
                "supply --ecosystem-kit with its extracted directory. No standalone module environment was created.")
        return install(spec, root, ecosystem_kit.expanduser().resolve())
    if ecosystem_kit is not None:
        raise ModuleInstallationError("The complete ecosystem kit is selected only for the reviewed TOPOS adapter.")
    parent, location, source, environment = _paths(module_id, spec, root)
    receipt_path = parent / "installation.json"
    if receipt_path.exists():
        existing = _read_receipt(receipt_path)
        if existing.get("revision") == spec["revision"]:
            return verify_installation(module_id, spec, root)
    fetch_module(module_id, spec, root)
    if spec.get("install_blocker"):
        raise ModuleInstallationError(f"{module_id} source was downloaded to {source}, but installation is blocked: {spec['install_blocker']}; no runnable installation was created.")
    if spec["distribution"] is None:
        raise ModuleInstallationError(f"{module_id} source was downloaded to {source}, but upstream Python packaging is unavailable; no runnable installation was created.")
    integrity = _source_integrity(source, spec)
    try:
        environment.mkdir()
    except FileExistsError as error:
        raise ModuleInstallationError("An unreceipted environment exists at this pin; inspect it before choosing a clean root.") from error
    _run([sys.executable, "-I", "-m", "venv", str(environment)], env=_build_env(), label="Create isolated module environment")
    python = _python_path(environment)
    # Build from a disposable copy: backend-created egg-info never dirties source.
    with tempfile.TemporaryDirectory(prefix=".build-", dir=location) as temporary:
        build_root = Path(temporary)
        build_source = build_root / "source"
        shutil.copytree(source, build_source, ignore=shutil.ignore_patterns(".git"), symlinks=True)
        wheels = build_root / "wheels"
        _run([str(python), "-I", "-B", "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(wheels), str(build_source)], env=_build_env(), label="Build pinned module wheel")
        candidates = list(wheels.glob("*.whl"))
        if len(candidates) != 1:
            raise ModuleInstallationError("Module build did not produce exactly one wheel.")
        wheel = candidates[0]
        name, version = _wheel_identity(wheel)
        if _canonical_name(name) != _canonical_name(spec["distribution"]):
            raise ModuleInstallationError("Built distribution does not match the reviewed module identity.")
        wheel_sha256 = hashlib.sha256(wheel.read_bytes()).hexdigest()
        _run([str(python), "-I", "-B", "-m", "pip", "install", str(wheel), *spec["adapter_requirements"]], env=_build_env(), label="Install module and adapter dependencies")
        _run([str(python), "-I", "-B", "-m", "pip", "check"], env=_build_env(), label="Dependency check")
        probe = _probe(python, spec["distribution"])
        if probe["distribution_metadata"]["version"] != version:
            raise ModuleInstallationError("Installed version differs from the pinned module build.")
        direct_url = probe["distribution_metadata"]["direct_url"] or {}
        if direct_url.get("archive_info", {}).get("hashes", {}).get("sha256") != wheel_sha256:
            raise ModuleInstallationError("Installed distribution lacks verified built-wheel provenance.")
    if integrity != _source_integrity(source, spec):
        raise ModuleInstallationError("Module checkout changed during installation.")
    receipt = {"schema_version": RECEIPT_SCHEMA, "status": "installed", "module_id": module_id,
               "repository": spec["repository"], "revision": spec["revision"], "distribution": spec["distribution"],
               "manifest_spec_sha256": _digest_json(spec), "source_path": str(source), "python_path": str(python),
               "adapter": spec.get("adapter"), "operations": spec["operations"], "built_wheel_sha256": wheel_sha256,
               "pip_check": {"passed": True}, "environment_sha256": _environment_integrity(environment), **integrity, **probe}
    _atomic_json(receipt_path, receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("list", "fetch", "install", "verify"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
        sub.add_argument("--root", type=Path, default=default_root())
        sub.add_argument("--json", action="store_true", help="Print machine-readable receipts (list always emits JSON)")
        if command != "list":
            sub.add_argument("--modules", nargs="+", required=command in {"fetch", "install"})
        if command == "install":
            sub.add_argument("--ecosystem-kit", type=Path, help="Extracted reviewed mandatory BASE/TOPOS/TORQ kit")
    args = parser.parse_args(argv)
    try:
        catalog = load_manifest(args.manifest)["modules"]
        if args.command == "list":
            print(json.dumps({"schema_version": MANIFEST_SCHEMA, "modules": catalog}, indent=2, sort_keys=True))
            return 0
        selected = args.modules
        if selected is None:
            selected = [key for key in catalog if (args.root / key / "installation.json").is_file()]
        if any(module_id not in catalog for module_id in selected):
            raise ValueError("Selection contains a module absent from the reviewed manifest.")
        operation = {"install": install_module, "fetch": fetch_module, "verify": verify_installation}[args.command]
        receipts = [operation(module_id, catalog[module_id], args.root,
                              **({"ecosystem_kit": args.ecosystem_kit} if args.command == "install" else {}))
                    for module_id in dict.fromkeys(selected)]
        if args.json:
            print(json.dumps({"modules": receipts}, indent=2, sort_keys=True))
        else:
            for receipt in receipts:
                print(f"{receipt['module_id']}: {args.command} complete at {receipt['revision']} (scientific acceptance is separate)")
            if not receipts:
                print("No installed modules selected.")
        return 0
    except (ValueError, OSError, ModuleInstallationError, json.JSONDecodeError) as error:
        print(_redact(f"Module {args.command} failed: {error}"), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
