"""Install and invoke the reviewed mandatory TOPOS ecosystem, without another installer.

Kit checksums are integrity records, not trust anchors. TOPOS/TORQ wheel digests
come from BASE's reviewed catalog; the BASE wheel must match the running installed
BASE distribution. The existing pinned TOPOS setup helper owns provisioning.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import importlib.metadata as metadata
import json
import math
import os
import re
import shutil
import stat
import sys
import tarfile
import tempfile
import time
import tomllib
import zipfile
from pathlib import Path, PurePosixPath

SCHEMA = "cochem.mandatory-ecosystem-installation/1"
ADAPTER = "topos_handoff"
PROVIDER = "topos.base_provider:provider"
CONTRACT = "cochem.module-handoff/1"
PACKAGES = {"base": "CoChem-BASE", "topos": "cochem-topos", "torq": "CoChem-TORQ"}
VERSIONS = {"base": "1.0.1", "topos": "0.1.0", "torq": "0.1.0"}
OPERATIONS = ("energy", "gradient", "optimize", "search", "frequency", "thermochemistry", "association", "matrix")


def _manager():
    from scripts import manage_modules
    return manage_modules


def _hash(path: Path, checkpoint=None) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            if checkpoint is not None:
                checkpoint()
            digest.update(block)
    return digest.hexdigest()


class _Budget:
    def __init__(self, timeout: float, cancellation_event=None):
        self.deadline = time.monotonic() + timeout
        self.cancellation_event = cancellation_event

    def check(self) -> float:
        from cochem_base.core_engine.cochem_core_subprocess_broker import SubprocessCancelledError
        if self.cancellation_event is not None and self.cancellation_event.is_set():
            raise SubprocessCancelledError("Module receiver cancelled before further verification or execution")
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Total module receiver deadline exhausted")
        return remaining

    def run(self, command, *, env, label, cwd=None):
        from cochem_base.core_engine.cochem_core_subprocess_broker import safe_subprocess_run
        with tempfile.TemporaryDirectory(prefix="cochem-module-verification-") as temporary:
            result = safe_subprocess_run(command, cwd=cwd or temporary, env=_sanitize_loaders(env),
                timeout=self.check(), cancellation_event=self.cancellation_event, required_disk_gb=0.01,
                load_full_stdout=True)
        self.check()
        return result.stdout.rstrip("\r\n")


def _json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 * 1024**2:
        raise ValueError("Ecosystem metadata requires a bounded regular JSON file")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Ecosystem metadata must be an object")
    return value


def _relative(value: str) -> str:
    path = PurePosixPath(value)
    if (not value or "\\" in value or path.is_absolute() or ".." in path.parts
            or path.as_posix() != value or any(c in value for c in "\r\n\x00")):
        raise ValueError("Unsafe ecosystem member path")
    return value


def _sha(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise ValueError("A reviewed SHA-256 identity is required")
    return value


def _pin(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{40}", value):
        raise ValueError("An immutable source commit is required")
    return value


def validate_spec(spec: dict) -> dict:
    authority = spec.get("mandatory_ecosystem", {})
    if (spec.get("adapter") != ADAPTER or spec.get("repository") != "ProfJJK-CoChem/CoChem-TOPOS"
            or authority.get("schema_version") != "cochem.mandatory-ecosystem-catalog/2"
            or spec.get("distribution") != "cochem-topos"
            or tuple(spec.get("operations", ())) != OPERATIONS):
        raise ValueError("TOPOS requires its reviewed typed mandatory-ecosystem catalog")
    _pin(spec["revision"])
    _pin(authority.get("torq_revision"))
    for key in ("topos_wheel_sha256", "torq_wheel_sha256", "setup_helper_sha256", "base_source_content_sha256"):
        _sha(authority.get(key))
    bootstrap = authority.get("base_bootstrap_sha256", {})
    if set(bootstrap) != {"cli.py", "pyproject.toml", "MANIFEST.in", "requirements.txt", "requirements-ui.txt"}:
        raise ValueError("Reviewed BASE source bootstrap identities are required")
    for digest in bootstrap.values():
        _sha(digest)
    return authority


def verify_kit_checksums(kit: Path, checkpoint=None) -> dict[str, str]:
    """Reject unrecorded or redirected kit files before interpreting any payload."""
    if kit.is_symlink() or not kit.is_dir():
        raise ValueError("Supply an extracted complete kit directory, without redirected paths")
    sums = kit / "SHA256SUMS"
    if sums.is_symlink() or not sums.is_file() or sums.stat().st_size > 8 * 1024**2:
        raise ValueError("Complete kit SHA256SUMS is required")
    inventory = {}
    for line in sums.read_text().splitlines():
        match = re.fullmatch(r"([a-f0-9]{64})  (.+)", line)
        if not match:
            raise ValueError("Malformed kit checksum record")
        name = _relative(match[2])
        if name in inventory or name == "SHA256SUMS":
            raise ValueError("Duplicate or recursive kit checksum record")
        inventory[name] = match[1]
    actual = set()
    for path in kit.rglob("*"):
        if checkpoint is not None:
            checkpoint()
        if path.is_symlink():
            raise ValueError("Kit files may not be symlinks")
        if path.is_file() and path != sums:
            name = path.relative_to(kit).as_posix()
            actual.add(name)
            if path.stat().st_size > 512 * 1024**2 or inventory.get(name) != _hash(path, checkpoint):
                raise ValueError("Kit payload differs from its checksum inventory")
        elif not path.is_dir() and path != sums:
            raise ValueError("Unsupported kit filesystem member")
    if actual != set(inventory):
        raise ValueError("Kit inventory has missing or unrecorded files")
    return inventory


def verify_current_base_wheel(wheel: Path, checkpoint=None) -> None:
    """A self-hashed kit cannot replace the currently executing BASE code."""
    distribution = metadata.distribution("CoChem-BASE")
    if not Path(__file__).resolve().is_relative_to(Path(sys.prefix).resolve()):
        raise ValueError("Mandatory installation must be called by installed BASE code, not a source override")
    direct = json.loads(distribution.read_text("direct_url.json") or "null") or {}
    if direct.get("dir_info", {}).get("editable") or distribution.version != VERSIONS["base"]:
        raise ValueError("Mandatory-kit installation requires the reviewed noneditable BASE distribution")
    files = {str(entry): entry for entry in distribution.files or ()}
    if not files:
        raise ValueError("Running BASE lacks installed file provenance")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        if len(set(names)) != len(names):
            raise ValueError("Duplicate BASE wheel member")
        wheel_payload = set()
        for name in names:
            if checkpoint is not None:
                checkpoint()
            _relative(name)
            if name.endswith("/"):
                continue
            if ".dist-info/" in name:
                suffix = name.split(".dist-info/", 1)[1]
                if suffix in {"METADATA", "WHEEL", "entry_points.txt", "top_level.txt"}:
                    installed = distribution.read_text(suffix)
                    if installed is None or installed.encode() != archive.read(name):
                        raise ValueError("BASE wheel metadata differs from the running distribution")
                continue
            wheel_payload.add(name)
            entry = files.get(name)
            if entry is None:
                raise ValueError("BASE kit contains code absent from the running distribution")
            installed_path = Path(distribution.locate_file(entry))
            path = installed_path.resolve(strict=True)
            if (not path.is_relative_to(Path(sys.prefix).resolve()) or installed_path.is_symlink()
                    or path.read_bytes() != archive.read(name)):
                raise ValueError("BASE kit payload differs from the currently executing BASE code")
        installed_payload = {name for name in files if ".dist-info/" not in name
                             and not name.startswith("../") and not name.endswith((".pyc", ".pyo"))}
        if wheel_payload != installed_payload:
            raise ValueError("BASE kit omits installed BASE payload")


def base_source_content_identity(source: Path) -> dict:
    """Hash every source member except Git control data and the self catalog.

    This is a content identity, never an execution or Git provenance receipt.
    Runtime callers separately require a clean, complete tracked checkout.
    """
    source = source.expanduser().absolute()
    if any(path.is_symlink() for path in (source, *source.parents)):
        raise ValueError("BASE source content paths may not be redirected")
    source = source.resolve(strict=True)
    if not source.is_dir():
        raise ValueError("BASE source content requires a directory")
    tracked = None
    if (source / ".git").exists() or (source / ".git").is_symlink():
        if (source / ".git").is_symlink() or not (source / ".git").is_dir():
            raise ValueError("BASE Git control directory may not be redirected")
        if _manager()._git(source, "status", "--porcelain", "--untracked-files=all", "--ignored"):
            raise ValueError("BASE source content requires a clean tracked checkout without ignored inputs")
        tracked = set(filter(None, _manager()._git(source, "ls-files", "-z").split("\0")))
    files = {}
    for directory, folders, names in os.walk(source, followlinks=False):
        parent = Path(directory)
        if parent == source and ".git" in folders:
            git_control = parent / ".git"
            if git_control.is_symlink():
                raise ValueError("BASE Git control directory may not be redirected")
            folders.remove(".git")
        for name in folders:
            if (parent / name).is_symlink():
                raise ValueError("BASE source content paths may not be redirected")
        for name in names:
            path = parent / name
            relative = path.relative_to(source).as_posix()
            _relative(relative)
            mode = path.lstat().st_mode
            if not stat.S_ISREG(mode) or relative == ".git":
                raise ValueError("BASE source content requires regular, unredirected files")
            # O_NOFOLLOW closes file-link replacement on hosts that provide it;
            # compare inode/stat identity as well, including portable platforms.
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(descriptor, "rb") as stream:
                before = os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode):
                    raise ValueError("BASE source content requires regular files")
                content = hashlib.file_digest(stream, "sha256").hexdigest()
                after = os.fstat(stream.fileno())
            current = path.lstat()
            observed = [(value.st_dev, value.st_ino, value.st_mode, value.st_size, value.st_mtime_ns)
                        for value in (before, after, current)]
            if len(set(observed)) != 1:
                raise ValueError("BASE source content changed while hashing")
            files[relative] = {"kind": "executable" if before.st_mode & 0o111 else "file",
                               "mode": stat.S_IMODE(before.st_mode),
                               "sha256": content, "size_bytes": before.st_size}
    catalog = "scripts/module-distribution.json"
    if catalog not in files:
        raise ValueError("BASE source content requires its independently owned catalog")
    if tracked is not None and set(files) != tracked:
        raise ValueError("BASE source contains untracked, ignored or missing members")
    digest = hashlib.sha256()
    for name, item in sorted(files.items()):
        if name != catalog:
            digest.update(name.encode() + b"\0" + item["kind"].encode() + b"\0" + bytes.fromhex(item["sha256"]))
    return {"schema_version": "cochem.base-source-content/1", "sha256": digest.hexdigest(),
            "excluded_catalog_path": catalog, "files": files}


def _base_executable_sources(source: Path, bootstrap: dict) -> set[Path]:
    """Resolve the already hash-anchored setuptools source layout without imports."""
    source = source.resolve(strict=True)
    configured = tomllib.loads((source / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["setuptools"]
    package_dirs = configured.get("package-dir", {})
    discovery = configured.get("packages", {}).get("find", {})
    if not package_dirs or not isinstance(package_dirs, dict) or not isinstance(discovery, dict):
        raise ValueError("Reviewed BASE package source layout is required")

    def confined(relative: str) -> Path:
        path = source if relative == "." else source / _relative(relative)
        if (any(part.is_symlink() for part in (path, *path.parents) if part.is_relative_to(source))
                or not path.resolve().is_relative_to(source)):
            raise ValueError("BASE package source paths may not be redirected")
        return path

    executable_suffixes = {".py", ".pyw", ".pyc", ".pyo", ".so", ".pyd", ".pth"}
    selected = {confined(name) for name in bootstrap if Path(name).suffix in executable_suffixes}
    for directory in package_dirs.values():
        folder = confined(directory)
        for path in folder.rglob("*"):
            if path.is_symlink():
                raise ValueError("BASE package source paths may not be redirected")
            if path.is_file() and path.suffix in executable_suffixes:
                selected.add(path)

    def package_folder(name: str, fallback: Path) -> Path:
        # Setuptools maps the longest dotted package prefix. In particular,
        # cochem -> src/cochem supersedes legacy cochem files found under '.'.
        prefixes = [key for key in package_dirs if not key or name == key or name.startswith(key + ".")]
        if not prefixes:
            return fallback
        prefix = max(prefixes, key=len)
        remainder = name[len(prefix):].lstrip(".")
        folder = confined(package_dirs[prefix])
        return folder.joinpath(*remainder.split(".")) if remainder else folder

    include = discovery.get("include", ["*"])
    exclude = discovery.get("exclude", [])
    for directory in discovery.get("where", ["."]):
        root = confined(directory)
        for path in root.rglob("*"):
            package = ".".join(path.relative_to(root).parts if path.is_dir() else path.parent.relative_to(root).parts)
            if (not any(fnmatch.fnmatchcase(package, pattern) for pattern in include)
                    or any(fnmatch.fnmatchcase(package, pattern) for pattern in exclude)):
                continue
            folder = package_folder(package, path if path.is_dir() else path.parent)
            candidate = folder if path.is_dir() else folder / path.name
            candidate = confined(candidate.relative_to(source).as_posix())
            if candidate.is_file() and candidate.suffix in executable_suffixes:
                selected.add(candidate)
    for name in configured.get("py-modules", []):
        package, _, module = name.rpartition(".")
        folder = package_folder(package, source)
        selected.add(confined((folder / (module + ".py")).relative_to(source).as_posix()))
    return selected


def verify_base_source(source: Path, wheel: Path, authority: dict) -> None:
    """Bind bootstrap source to installed BASE; do not trust a kit's chosen SHA alone."""
    source = source.expanduser().absolute()
    if any(path.is_symlink() for path in (source, *source.parents)):
        raise ValueError("BASE package source paths may not be redirected")
    source = source.resolve(strict=True)
    expected_source = _sha(authority.get("base_source_content_sha256"))
    identity = base_source_content_identity(source)
    if identity["sha256"] != expected_source:
        raise ValueError("Complete BASE source content differs from the reviewed catalog")
    for name, expected in authority["base_bootstrap_sha256"].items():
        path = source / _relative(name)
        if path.is_symlink() or not path.is_file() or _hash(path) != expected:
            raise ValueError("BASE source bootstrap differs from the reviewed catalog")
    if any((source / name).exists() for name in ("setup.py", "setup.cfg", "sitecustomize.py", "usercustomize.py")):
        raise ValueError("Unexpected executable BASE build customization")
    matched = set()
    with zipfile.ZipFile(wheel) as archive:
        catalog = identity["excluded_catalog_path"]
        if (archive.namelist().count(catalog) != 1
                or archive.read(catalog) != (source / catalog).read_bytes()):
            raise ValueError("BASE source catalog differs from the independently owned wheel")
        for name in archive.namelist():
            if name.endswith("/") or ".dist-info/" in name:
                continue
            choices = [source / name, source / "src" / name]
            content = archive.read(name)
            matching = [path for path in choices if path.is_file() and path.read_bytes() == content]
            if not matching:
                raise ValueError("BASE Git source differs from the currently installed wheel payload")
            matched.update(path.resolve() for path in matching)
    for path in _base_executable_sources(source, authority["base_bootstrap_sha256"]):
        if path.resolve() not in matched:
            raise ValueError("BASE bootstrap source contains unowned executable code")
    if base_source_content_identity(source) != identity:
        raise ValueError("BASE source content changed during source verification")


def inspect_kit(kit: Path, spec: dict, checkpoint=None) -> dict:
    authority = validate_spec(spec)
    inventory = verify_kit_checksums(kit, checkpoint)
    manifest = _json(kit / "candidate-manifest.json")
    if (manifest.get("schema_version") != "cochem-unsigned-download/0.1.0"
            or manifest.get("engines_included") is not False
            or manifest.get("model_weights_included") is not False):
        raise ValueError("Unsupported complete ecosystem kit")
    pins = manifest.get("source_pins", {})
    base_pin, torq_pin = _pin(pins.get("BASE")), _pin(pins.get("TORQ"))
    if torq_pin != authority["torq_revision"]:
        raise ValueError("TORQ kit revision differs from the reviewed catalog")
    wheels = {}
    owned = set()
    manager = _manager()
    for path in (kit / "wheels").glob("*.whl"):
        if checkpoint is not None:
            checkpoint()
        name, version = manager._wheel_identity(path)
        project = next((key for key, package in PACKAGES.items()
                        if manager._canonical_name(name) == manager._canonical_name(package)), None)
        if project is None or project in wheels or version != VERSIONS[project]:
            raise ValueError("Kit must contain exactly the reviewed mandatory distribution versions")
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(set(names)) != len(names):
                raise ValueError("Duplicate wheel member")
            payload = set()
            for member in names:
                _relative(member)
                if not member.endswith("/") and ".dist-info/" not in member:
                    payload.add(member)
            if payload & owned:
                raise ValueError("Mandatory distributions have overlapping installed ownership")
            owned.update(payload)
        wheels[project] = path
    if set(wheels) != set(PACKAGES):
        raise ValueError("Complete kit requires all three mandatory wheels")
    for project in ("topos", "torq"):
        if _hash(wheels[project], checkpoint) != authority[project + "_wheel_sha256"]:
            raise ValueError("Module wheel differs from its independently reviewed catalog digest")
    verify_current_base_wheel(wheels["base"], checkpoint)
    builds = _json(kit / "evidence/companion-build-manifest.json")
    if builds.get("schema_version") != "cochem-companion-build/0.1.0":
        raise ValueError("Companion source build identity is required")
    sources = {}
    for project, pin in (("base", base_pin), ("torq", torq_pin)):
        identity = builds.get("companions", {}).get(project, {})
        wheel_sha = _hash(wheels[project], checkpoint)
        if (identity.get("source_commit") != pin or identity.get("wheel_sha256") != wheel_sha
                or identity.get("repeated_wheel_sha256") != [wheel_sha, wheel_sha]):
            raise ValueError("Companion source/wheel identities disagree")
        source = kit / "sources" / Path(_relative(identity["source_archive"])).name
        if _hash(source, checkpoint) != _sha(identity["source_archive_sha256"]):
            raise ValueError("Companion source archive differs from its recorded build")
        sources[project] = source
    distribution = _json(kit / "evidence/distribution-manifest.json")
    if manifest.get("topos_source_sha256") != distribution.get("source_sha256"):
        raise ValueError("TOPOS executable source inventories disagree")
    candidates = [path for path in (kit / "sources").glob("*.tar.gz") if path not in sources.values()]
    if len(candidates) != 1:
        raise ValueError("One TOPOS source archive is required")
    sources["topos"] = candidates[0]
    return {"inventory": inventory, "pins": {"base": base_pin, "topos": spec["revision"], "torq": torq_pin},
            "wheels": wheels, "sources": sources, "distribution": distribution}


def verify_source_archive(archive: Path, source: Path, *, allow_sdist_metadata: bool = False) -> None:
    """Compare archive source bytes with the actual independently fetched commit."""
    manager = _manager()
    tracked = set(manager._git(source, "ls-files").splitlines())
    observed = set()
    with tarfile.open(archive, "r:gz") as stream:
        for member in stream:
            name = _relative(member.name.rstrip("/"))
            parts = PurePosixPath(name).parts
            if len(parts) == 1 and member.isdir():
                continue
            relative = PurePosixPath(*parts[1:]).as_posix()
            if member.isdir():
                continue
            if relative in observed:
                raise ValueError("Duplicate source archive member")
            observed.add(relative)
            if relative not in tracked:
                if allow_sdist_metadata and (relative in {"PKG-INFO", "setup.cfg"} or ".egg-info/" in relative):
                    continue
                raise ValueError("Source archive contains a file absent from the pinned Git commit")
            original = source / relative
            if member.issym():
                if not original.is_symlink() or os.readlink(original) != member.linkname:
                    raise ValueError("Source archive symlink differs from pinned Git")
            elif member.isfile():
                file = stream.extractfile(member)
                if original.is_symlink() or file is None or file.read() != original.read_bytes():
                    raise ValueError("Source archive bytes differ from pinned Git")
            else:
                raise ValueError("Unsupported source archive member")
    if not allow_sdist_metadata and observed != tracked:
        raise ValueError("Companion archive is not the complete pinned Git source")


def _sanitize_loaders(environment: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in environment.items()
            if not key.startswith(("LD_", "DYLD_"))
            and key not in {"PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE", "VIRTUAL_ENV", "GIT_ASKPASS", "SSH_ASKPASS"}}


def _setup_environment() -> dict[str, str]:
    environment = _manager()._build_env()
    # Fresh installation must not select or modify another controller's silos.
    for key in list(environment):
        if (key in {"COCHEM_MODULES", "COCHEM_CONFIG", "COCHEM_MANIFEST_PATH", "COCH_SRC", "COCH_DATA", "COCHEM_REPO_DIR", "COCHEM_ROOT", "TOPOS_CONFIG", "COCHEM_ARTIFACTS", "COCHEM_ARTIFACT_DIR"}
                or key.endswith("_SILO") or key in {"COCHEM_BASE_ROOT", "COCHEM_TOPOS_ROOT", "COCHEM_TORQ_ROOT"}):
            environment.pop(key, None)
    # Keep the configured primary package index and CA/proxy settings, but never
    # inherit installer redirection, additional package sources or pip config.
    for key in ("PIP_TARGET", "PIP_PREFIX", "PIP_ROOT", "PIP_USER", "PIP_FIND_LINKS",
                "PIP_EXTRA_INDEX_URL", "PIP_CONSTRAINT", "PIP_REQUIREMENT"):
        environment.pop(key, None)
    environment.update(PYTHONDONTWRITEBYTECODE="1", COCHEM_MODULES="",
                       PIP_CONFIG_FILE=os.devnull, PIP_NO_INPUT="1")
    return _sanitize_loaders(environment)


def _companion_spec(project: str, pin: str) -> dict:
    if project not in {"base", "torq"}:
        raise ValueError("Only mandatory BASE and TORQ companion sources are accepted")
    return {"repository": "ProfJJK-CoChem/CoChem-" + project.upper(), "revision": _pin(pin),
            "distribution": PACKAGES[project], "adapter": None, "adapter_requirements": [], "operations": []}


def install(spec: dict, root: Path, kit: Path) -> dict:
    manager = _manager()
    parent, location, source, _ = manager._paths("topos", spec, root)
    if (parent / "installation.json").exists():
        previous = manager._read_receipt(parent / "installation.json")
        if previous.get("revision") == spec["revision"]:
            return verify(spec, root)
    inspected = inspect_kit(kit, spec)
    manager.fetch_module("topos", spec, root)
    sources = {"topos": source}
    for project in ("base", "torq"):
        dependency = _companion_spec(project, inspected["pins"][project])
        receipt = manager.fetch_module(project, dependency, location / "dependencies")
        sources[project] = Path(receipt["source_path"])
    for project, path in sources.items():
        verify_source_archive(inspected["sources"][project], path, allow_sdist_metadata=project == "topos")
    authority = validate_spec(spec)
    verify_base_source(sources["base"], inspected["wheels"]["base"], authority)
    helper = source / "scripts/setup_ecosystem.py"
    if _hash(helper) != authority["setup_helper_sha256"]:
        raise ValueError("Pinned setup helper differs from the reviewed catalog")
    for relative, digest in inspected["distribution"].get("source_sha256", {}).items():
        if _hash(source / _relative(relative)) != _sha(digest):
            raise ValueError("Kit executable inventory differs from the pinned TOPOS commit")
    retained = location / "complete-kit"
    shutil.copytree(kit, retained)
    inspect_kit(retained, spec)
    # BASE's bootstrap creates build metadata. Keep immutable Git sources intact.
    copies = {}
    for project, path in sources.items():
        destination = location / "setup-sources" / project
        shutil.copytree(path, destination, symlinks=True, ignore=shutil.ignore_patterns(".git"))
        copies[project] = destination
    runtime = location / "runtime"
    if runtime.exists():
        raise ValueError("Mandatory setup requires fresh runtime artifacts")
    from cochem_base.core_engine.cochem_core_subprocess_broker import safe_subprocess_run
    command = [sys.executable, "-B", str(copies["topos"] / "scripts/setup_ecosystem.py"),
               "--base-root", str(copies["base"]), "--torq-root", str(copies["torq"]),
               "--wheelhouse", str(retained / "wheels"), "--artifacts", str(runtime)]
    safe_subprocess_run(command, cwd=location, env=_setup_environment(), timeout=3600,
                        stream_to_disk=True, required_disk_gb=1)
    python = manager._python_path(runtime / "ui-env")
    setup = _json(runtime / "setup-receipt.json")
    if setup.get("status") != "completed" or setup.get("distribution_mode") != "noneditable-reviewed-wheels":
        raise ValueError("Mandatory setup did not complete the reviewed wheel installation")
    state = _inspect_runtime(python, runtime)
    probe = manager._probe(python, "cochem-topos")
    source_provenance = {
        project: manager._source_integrity(path, {
            "revision": inspected["pins"][project],
            "repository": "ProfJJK-CoChem/CoChem-" + project.upper(),
        }) for project, path in sources.items()
    }
    receipt = {"schema_version": SCHEMA, "status": "installed", "module_id": "topos", "repository": spec["repository"],
               "revision": spec["revision"], "manifest_spec_sha256": manager._digest_json(spec),
               "source_path": str(source), "python_path": str(python), "runtime_path": str(runtime),
               "kit_path": str(retained), "adapter": ADAPTER, "operations": list(OPERATIONS),
               "source_pins": inspected["pins"], "setup_helper_sha256": _hash(helper),
               "source_provenance": source_provenance,
               "kit_inventory": verify_kit_checksums(retained), "runtime_identity": state,
               "environment_sha256": manager._environment_integrity(runtime / "ui-env"),
               "setup_receipt_sha256": _hash(runtime / "setup-receipt.json"),
               "mandatory_validation_sha256": _hash(runtime / "mandatory-validation.json"),
               "pip_check": {"passed": True}, **manager._source_integrity(source, spec), **probe}
    # A failed upgrade keeps the previous working receipt; a failed first setup
    # publishes no installed status. Verify the prospective receipt in full.
    _verify_receipt(spec, root, receipt)
    manager._atomic_json(parent / "installation.json", receipt)
    return receipt


def _inspect_runtime(python: Path, runtime: Path, *, runner=None) -> dict:
    command = [str(python), "-I", "-B", str(Path(__file__).resolve()), "inspect", "--runtime", str(runtime)]
    output = (runner or _manager()._run)(command, env=_setup_environment(), label="Mandatory Stage 0/provider inspection")
    return json.loads(output)


def verify(spec: dict, root: Path, *, budget=None) -> dict:
    manager = _manager()
    budget = budget or _Budget(180)
    parent = manager._paths("topos", spec, root, budget=budget)[0]
    return _verify_receipt(spec, root, manager._read_receipt(parent / "installation.json"), budget=budget)


def _verify_receipt(spec: dict, root: Path, receipt: dict, *, budget=None, legacy_location: Path | None = None) -> dict:
    manager = _manager()
    budget = budget or _Budget(180)
    budget.check()
    if legacy_location is None:
        parent, location, source, _ = manager._paths("topos", spec, root, budget=budget)
    else:
        manager._validate_spec("topos", spec)
        parent = Path(root).expanduser().resolve() / "topos"
        location = parent / spec["revision"]
        if legacy_location != location:
            raise ValueError("Historical kit location differs from its exact legacy revision")
        source = location / "source"
        for path in (parent, location, source, location / "runtime", location / "runtime/ui-env", location / "complete-kit"):
            if path.is_symlink() or not path.resolve().is_relative_to(parent.parent):
                raise ValueError("Historical kit location was redirected")
    validate_spec(spec)
    resolved_legacy = location == Path(root).expanduser().resolve() / "topos" / spec["revision"]
    runtime, kit = location / "runtime", location / "complete-kit"
    python = manager._python_path(runtime / "ui-env")
    expected = {"schema_version": SCHEMA, "status": "installed", "module_id": "topos", "repository": spec["repository"],
                "revision": spec["revision"], "manifest_spec_sha256": manager._digest_json(spec), "source_path": str(source),
                "python_path": str(python), "runtime_path": str(runtime), "kit_path": str(kit),
                "adapter": ADAPTER, "operations": list(OPERATIONS)}
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise ValueError("Mandatory installation receipt differs from reviewed paths or specification")
    for path in (runtime, runtime / "ui-env", kit):
        if path.is_symlink() or not path.resolve().is_relative_to(location.resolve()):
            raise ValueError("Mandatory installation path was redirected")
    if receipt.get("kit_inventory") != verify_kit_checksums(kit, budget.check):
        raise ValueError("Retained complete kit changed after installation")
    inspected = inspect_kit(kit, spec, budget.check)
    if (receipt.get("source_pins") != inspected["pins"]
            or receipt.get("setup_helper_sha256") != validate_spec(spec)["setup_helper_sha256"]):
        raise ValueError("Mandatory source identities differ from the reviewed kit")
    for project, pin in inspected["pins"].items():
        project_spec = spec if project == "topos" else _companion_spec(project, pin)
        if project == "topos":
            project_source = source
        elif resolved_legacy:
            project_source = location / "dependencies" / project / pin / "source"
            for path in (location / "dependencies", project_source.parent.parent, project_source.parent, project_source):
                if path.is_symlink() or not path.resolve().is_relative_to(location):
                    raise ValueError("Historical companion source was redirected")
        else:
            project_source = manager._paths(project, project_spec, location / "dependencies")[2]
        current_source = manager._source_integrity(
            project_source, project_spec, runner=budget.run, checkpoint=budget.check)
        if current_source != receipt.get("source_provenance", {}).get(project):
            raise ValueError("Mandatory source checkout changed after installation")
    if any(receipt.get(key) != value for key, value in manager._source_integrity(
            source, spec, runner=budget.run, checkpoint=budget.check).items()):
        raise ValueError("Pinned TOPOS source changed after installation")
    for filename, key in (("setup-receipt.json", "setup_receipt_sha256"), ("mandatory-validation.json", "mandatory_validation_sha256")):
        _json(runtime / filename)
        if _hash(runtime / filename) != receipt.get(key):
            raise ValueError("Mandatory setup evidence changed after installation")
    if manager._environment_integrity(runtime / "ui-env", checkpoint=budget.check) != receipt.get("environment_sha256"):
        raise ValueError("Mandatory installed environment changed; no provider was executed")
    if _inspect_runtime(python, runtime, runner=budget.run) != receipt.get("runtime_identity"):
        raise ValueError("Mandatory registry/provider identity changed; repeat reviewed setup")
    if any(receipt.get(key) != value for key, value in manager._probe(python, "cochem-topos", runner=budget.run).items()):
        raise ValueError("Mandatory installed distribution inventory changed")
    budget.run([str(python), "-I", "-B", "-m", "pip", "check"], env=manager._build_env(), label="Historical dependency check")
    return receipt


def _provider():
    entries = [entry for entry in metadata.entry_points(group="cochem.modules") if entry.name == "topos"]
    if len(entries) != 1 or entries[0].value != PROVIDER or entries[0].dist.name.lower().replace("_", "-") != "cochem-topos":
        raise ValueError("Exactly the reviewed TOPOS provider entry point is required")
    provider = entries[0].load()
    details = provider.metadata()
    if details.get("integration_contract") != CONTRACT or tuple(details.get("operations", ())) != OPERATIONS:
        raise ValueError("Installed TOPOS provider contract differs from the reviewed receiver")
    return provider


def child_inspect(runtime: Path) -> dict:
    from topos.base_integration import BaseRuntime

    from cochem_base.core.cochem_core_registry_manager import load_system_config
    registry = runtime / "Registry/cochem_system_config.json"
    if registry.is_symlink() or not registry.resolve().is_relative_to(runtime.resolve()):
        raise ValueError("Mandatory registry must remain confined to its runtime")
    config = load_system_config(registry, verify_integrity=True)
    if not config.verify_checksum() or config.stage0 is None or sorted(p.phase_number for p in config.stage0.phases) != list(range(1, 12)):
        raise ValueError("Mandatory installation lacks all eleven current authenticated setup phases")
    expected = ["CoChem-BASE", "CoChem-TOPOS", "CoChem-TORQ"]
    if sorted(_json(runtime / "mandatory-deployment.json").get("selected_repositories", [])) != sorted(expected):
        raise ValueError("Mandatory deployment must select all three repositories")
    selected = BaseRuntime(registry)
    provider = _provider()
    versions = {name: metadata.version(package) for name, package in PACKAGES.items()}
    if versions != VERSIONS:
        raise ValueError("Installed mandatory package versions differ from the reviewed kit")
    return {"registry_sha256": _hash(registry), "registry_checksum": config.registry_checksum,
            "phases": list(range(1, 12)), "versions": versions,
            "provider": PROVIDER, "provider_metadata": provider.metadata(),
            "xtb_executable": selected.resolve_executable("xtb"), "crest_executable": selected.resolve_executable("crest")}


def child_execute(handoff: Path, output: Path, runtime: Path) -> dict:
    from topos.config import SystemConfig
    from topos.storage import RunStore

    from cochem_base.interfaces.artifact_handoff import load_module_handoff
    original = load_module_handoff(handoff)
    before = _hash(handoff)
    provider = _provider()
    request, _ = provider.request_from_handoff(handoff)
    if request.calculation_environment != "local":
        raise ValueError("This installed receiver accepts explicit local BASE execution only")
    outcome = provider.execute_handoff(handoff, output / "runs", config=SystemConfig(
        execution_backend="base", base_registry_path=runtime / "Registry/cochem_system_config.json"))
    record, consumption = outcome["record"], outcome["receipt"]
    folder = Path(record["metadata"]["run_dir"]).resolve()
    if not folder.is_relative_to((output / "runs").resolve()):
        raise ValueError("TOPOS receiver returned a run outside its assigned output directory")
    store = RunStore(folder)
    verified = store.verify()
    if (store.load() != record or _hash(handoff) != before or load_module_handoff(handoff) != original
            or consumption.get("handoff_id") != original.handoff_id
            or consumption.get("manifest_file_sha256") != before
            or consumption.get("artifact_sha256") != original.artifact.sha256
            or record["metadata"].get("base_consumption") != consumption):
        raise ValueError("TOPOS consumption evidence differs from its immutable BASE handoff")
    return {"schema_version": "cochem.mandatory-module-operation/1", "module_id": "topos",
            "operation": original.operation, "handoff_id": original.handoff_id, "input_sha256": original.artifact.sha256,
            "status": record["status"], "validation_status": record["validation_status"], "published": False,
            "provider": PROVIDER, "consumption_receipt": consumption, "run_directory": str(folder),
            "run_snapshot_id": verified["snapshot_id"], "execution_provider": record["metadata"].get("execution_provider"),
            "scope": "Typed TOPOS calculation through mandatory BASE authority; no automatic publication or TORQ calculation"}


def execute(handoff: Path, output: Path, spec: dict, root: Path, *, timeout: float, cancellation_event=None) -> dict:
    from cochem.core.context import assert_writable_path
    from cochem_base.core_engine.cochem_core_subprocess_broker import safe_subprocess_run
    from cochem_base.interfaces.artifact_handoff import load_module_handoff
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Module timeout must be finite and positive")
    budget = _Budget(timeout, cancellation_event)
    budget.check()
    manifest = load_module_handoff(handoff)
    payload = manifest.options.get("topos_request")
    if (manifest.module_id != "topos" or manifest.operation not in OPERATIONS or set(manifest.options) != {"topos_request"}
            or not isinstance(payload, dict) or not isinstance(payload.get("budget_seconds"), (int, float))
            or isinstance(payload["budget_seconds"], bool) or not 0 < payload["budget_seconds"] <= timeout):
        raise ValueError("A typed TOPOS handoff and sufficient explicit caller timeout are required")
    receipt = verify(spec, root, budget=budget)
    assert_writable_path(output)
    output.mkdir(parents=True, exist_ok=False)
    report = output / "operation.json"
    command = [receipt["python_path"], "-I", "-B", str(Path(__file__).resolve()), "execute",
               "--runtime", receipt["runtime_path"], "--handoff", str(handoff), "--output", str(output)]
    try:
        safe_subprocess_run(command, cwd=output, env=_setup_environment(), timeout=budget.check(),
                            stream_to_disk=True, cancellation_event=cancellation_event, required_disk_gb=0.01)
        result = _json(report)
        if (result.get("schema_version") != "cochem.mandatory-module-operation/1"
                or result.get("handoff_id") != manifest.handoff_id or result.get("input_sha256") != manifest.artifact.sha256
                or result.get("operation") != manifest.operation or result.get("provider") != PROVIDER
                or result.get("published") is not False):
            raise ValueError("Module result does not match the typed handoff")
        verify(spec, root, budget=budget)
        if load_module_handoff(handoff) != manifest:
            raise ValueError("Handoff changed during calculation")
        _manager()._atomic_json(output / "result.json", result)
        return result
    except Exception as exc:
        _manager()._atomic_json(output / "failure.json", {"schema_version": "cochem.mandatory-module-operation/1",
            "module_id": "topos", "status": "failed", "published": False, "handoff_id": manifest.handoff_id,
            "error": str(exc)})
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("inspect", "execute"))
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--handoff", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.mode == "inspect":
        print(json.dumps(child_inspect(arguments.runtime), allow_nan=False))
        return 0
    if arguments.handoff is None or arguments.output is None:
        parser.error("execute requires --handoff and --output")
    result = child_execute(arguments.handoff, arguments.output, arguments.runtime)
    _manager()._atomic_json(arguments.output / "operation.json", result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
