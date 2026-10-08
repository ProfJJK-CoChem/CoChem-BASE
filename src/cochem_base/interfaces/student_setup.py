"""No-command student setup and reviewed, reversible ecosystem updates.

Only BASE is a student checkout. Providers live in independently verified
runtime directories. The canonical maintained BASE manifest carries reviewed provider pins. The
maintained branch, stable release or instructor approval is resolved to an exact
Git SHA before code is downloaded; moving module branches are never executed.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from scripts import manage_modules as installer

SETUP_SCHEMA = "cochem.student-setup/1"
RUNTIME_SCHEMA = "cochem.student-runtime/1"
PLAN_SCHEMA = "cochem.student-update-plan/1"
UPSTREAM = "ProfJJK-CoChem/CoChem-BASE"
DEFAULT_MODULES = ("topos", "torq")
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_RELEASE = re.compile(r"v(\d+)\.(\d+)\.(\d+)\Z")


class StudentSetupError(RuntimeError):
    """A setup/update must retain the previous usable configuration."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise StudentSetupError("GitHub release discovery redirected unexpectedly; no credentials were forwarded.")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read(path: Path, default=None):
    if not path.is_file():
        return default
    if path.is_symlink() or path.stat().st_size > 4 * 1024 * 1024:
        raise StudentSetupError("Setup receipt is redirected or exceeds its size limit.")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise StudentSetupError(f"Setup record {path.name} is unreadable; the previous runtime has been retained.") from error


def _checkout_revision(source: Path) -> str | None:
    result = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"],
                            env=installer._build_env(), capture_output=True, text=True, timeout=15)
    value = result.stdout.strip()
    return value if result.returncode == 0 and _SHA.fullmatch(value) else None


def _release_metadata(token: str | None = None) -> dict:
    """Read only the official stable release, using this user's GitHub identity."""
    request = urllib.request.Request(f"https://api.github.com/repos/{UPSTREAM}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "CoChem-BASE-student-setup"})
    token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or os.environ.get("COCHEM_SOURCE_CREDENTIAL")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.build_opener(_NoRedirect()).open(request, timeout=30) as response:
            data = response.read(1024 * 1024 + 1)
    except urllib.error.HTTPError as error:
        raise StudentSetupError(f"The approved BASE release could not be read (GitHub HTTP {error.code}). Check repository access and retry.") from error
    if len(data) > 1024 * 1024:
        raise StudentSetupError("GitHub release metadata exceeds its size limit.")
    release = json.loads(data)
    if (not isinstance(release, dict) or release.get("draft") is not False
            or release.get("prerelease") is not False or not _RELEASE.fullmatch(str(release.get("tag_name", "")))
            or not isinstance(release.get("id"), int)):
        raise StudentSetupError("Only a published stable versioned BASE release can be offered as an update.")
    return release


def _resolve_release(tag: str, token: str | None = None) -> str:
    if not _RELEASE.fullmatch(tag):
        raise StudentSetupError("The update tag is not a stable semantic version.")
    with installer._git_auth(token_override=token) as (env, options):
        output = installer._run(["git", *options, "ls-remote", f"https://github.com/{UPSTREAM}.git",
            f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}"], env=env, label="Resolve approved BASE release", timeout=60)
    values = {}
    for line in output.splitlines():
        fields = line.split("\t")
        if len(fields) == 2 and _SHA.fullmatch(fields[0]):
            values[fields[1]] = fields[0]
    revision = values.get(f"refs/tags/{tag}^{{}}", values.get(f"refs/tags/{tag}"))
    if revision is None:
        raise StudentSetupError("The published release has no immutable Git source identity.")
    return revision


def _resolve_default_branch(token: str | None = None) -> dict:
    """Pin the canonical maintained default branch before fetching any code."""
    with installer._git_auth(token_override=token) as (env, options):
        output = installer._run(["git", *options, "ls-remote", "--symref", f"https://github.com/{UPSTREAM}.git", "HEAD"],
            env=env, label="Resolve maintained BASE default branch", timeout=60)
    branch = None
    revision = None
    for line in output.splitlines():
        fields = line.split("\t")
        if len(fields) != 2 or fields[1] != "HEAD":
            continue
        if fields[0].startswith("ref: refs/heads/"):
            branch = fields[0][len("ref: refs/heads/"):]
        elif _SHA.fullmatch(fields[0]):
            revision = fields[0]
    if not revision or not branch or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./-]*", branch):
        raise StudentSetupError("The canonical BASE repository has no verifiable maintained default branch.")
    return {"revision": revision, "branch": branch}


def _base_spec(revision: str, requirements: list[str] | None = None) -> dict:
    return {"repository": UPSTREAM, "revision": revision, "distribution": "CoChem-BASE",
            "adapter": None, "adapter_requirements": requirements or [], "operations": []}


class StudentSetupService:
    """JSON-friendly service called by GUI buttons and automatic Codespace setup.

    Long-running methods belong on a GUI worker thread. ``status`` reads bounded
    records without importing providers. Provider execution performs its full
    integrity verification again before every scientific operation.
    """

    def __init__(self, artifact_dir: str | Path | None = None, repository_root: str | Path | None = None,
                 *, idle_check: Callable[[], bool] | None = None):
        self.repository_root = Path(repository_root or installer.REPOSITORY_ROOT).expanduser().resolve()
        self.artifact_dir = Path(artifact_dir or os.environ.get("COCHEM_ARTIFACT_DIR", "~/CoChem_Artifacts")).expanduser().resolve()
        if self.artifact_dir == self.repository_root or self.repository_root in self.artifact_dir.parents:
            raise StudentSetupError("Student runtime and update files must be outside the assignment repository.")
        from cochem_base.core_engine.cochem_core_workspace_manager import scaffold_core_directories
        scaffold_core_directories(self.artifact_dir)
        self.state_dir = self.artifact_dir / "StudentSetup"
        for path in (self.state_dir, self.artifact_dir / "Modules", self.artifact_dir / "BaseRuntime"):
            if path.is_symlink():
                raise StudentSetupError("Student runtime directories may not be redirected with symbolic links.")
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
        assignment_record = self.state_dir / "assignment-runtime.json"
        if not assignment_record.exists() and not self.repository_root.is_relative_to(self.artifact_dir / "BaseRuntime"):
            installer._atomic_json(assignment_record, {"schema_version": RUNTIME_SCHEMA, "kind": "assignment",
                "source_path": str(self.repository_root), "python_path": sys.executable,
                "revision": _checkout_revision(self.repository_root), "manifest_path": str(self.repository_root / "scripts/module-distribution.json")})
        self.idle_check = idle_check
        from filelock import FileLock
        self._lock = FileLock(str(self.state_dir / "setup.lock"))

    @property
    def manifest_path(self) -> Path:
        return self.repository_root / "scripts" / "module-distribution.json"

    def _write(self, filename: str, value: dict) -> None:
        installer._atomic_json(self.state_dir / filename, value)

    def _progress(self, action: str, message: str, status: str = "running", **extra) -> None:
        self._write("operation.json", {"status": status, "action": action, "message": installer._redact(message),
                                       "updated_at": _now(), **extra})

    def _assert_idle(self) -> None:
        if self.idle_check is not None and not self.idle_check():
            raise StudentSetupError("A calculation or import is active. Wait for it to finish before changing the runtime.")
        runtime = self._active_runtime()
        authority = Path(runtime.get("authority_path", str(self.artifact_dir)))
        registry = authority / "Registry" / "cochem_system_config.json"
        record = _read(registry, {})
        if not isinstance(record, dict) or record.get("active_jobs"):
            raise StudentSetupError("The execution registry contains active jobs; finish or cancel them before updating.")

    @contextmanager
    def _operation(self, action: str, *, require_idle: bool = True):
        from filelock import Timeout
        try:
            with self._lock.acquire(timeout=0):
                if require_idle:
                    self._assert_idle()
                self._progress(action, "Preparing the requested setup operation.")
                try:
                    yield
                except Exception as error:
                    message = installer._redact(str(error))
                    self._progress(action, message, "failed")
                    if isinstance(error, StudentSetupError):
                        raise
                    raise StudentSetupError(message) from error
                else:
                    completed_message = "Complete. Your input files and results have been preserved."
                    if action == "install":
                        completed_message = _read(self.state_dir / "initial-setup.json", {}).get("message", completed_message)
                    self._progress(action, completed_message, "complete")
        except Timeout as error:
            raise StudentSetupError("Another setup or update is already running. Its progress is shown below.") from error

    def _active_runtime(self) -> dict:
        record = _read(self.state_dir / "active-runtime.json")
        if record is None:
            return _read(self.state_dir / "assignment-runtime.json", {"schema_version": RUNTIME_SCHEMA, "source_path": str(self.repository_root), "python_path": sys.executable, "revision": _checkout_revision(self.repository_root), "kind": "assignment", "manifest_path": str(self.manifest_path)})
        validate_runtime_record(record, self.artifact_dir, self.repository_root)
        return record

    def status(self) -> dict:
        catalog = installer.load_manifest(self.manifest_path)["modules"]
        previous = _read(self.state_dir / "initial-setup.json", {})
        observed = {}
        for module_id in DEFAULT_MODULES:
            spec = catalog.get(module_id)
            receipt = _read(self.artifact_dir / "Modules" / module_id / "installation.json", {})
            installed = (spec is not None and isinstance(receipt, dict) and receipt.get("status") == "installed"
                         and receipt.get("revision") == spec["revision"]
                         and receipt.get("manifest_spec_sha256") == installer._digest_json(spec))
            detail = previous.get("modules", {}).get(module_id, {}) if isinstance(previous, dict) else {}
            observed[module_id] = {"status": "installed" if installed else ("failed" if detail.get("status") == "failed" else "missing"),
                "revision": spec["revision"] if spec else None,
                "message": "Installed; integrity is verified again before execution." if installed else detail.get("message", "Not installed yet; BASE remains available."),
                "operations": list(spec["operations"]) if installed else [],
                "scientific_execution_verified": False}
        runtime = self._active_runtime()
        restart = Path(runtime["source_path"]).resolve() != self.repository_root
        last_update = _read(self.state_dir / "last-update.json", {})
        rollback = (isinstance(last_update, dict) and last_update.get("status") == "applied"
                    and re.fullmatch(r"[0-9a-f]{32}", str(last_update.get("plan_id", ""))) is not None
                    and (self.state_dir / "history" / f"{last_update['plan_id']}.json").is_file())
        free_engines = _read(self.artifact_dir / "free-engines/setup-status.json", {"status": "unchecked", "engines": {},
            "message": "Free-engine installation is checked by BASE's native setup."})
        return {"schema_version": SETUP_SCHEMA, "rollback_available": rollback, "ready": all(item["status"] == "installed" for item in observed.values()) and free_engines.get("status") != "failed",
            "base": {"status": "ready", "revision": runtime.get("revision"), "restart_required": restart},
            "modules": observed, "initial_setup": previous, "free_engines": free_engines,
            "operation": _read(self.state_dir / "operation.json", {"status": "idle", "action": None, "message": "Ready."}),
            "update_plan": _read(self.state_dir / "update-plan.json")}

    def _retry_owned_failure(self, module_id: str, spec: dict, root: Path) -> None:
        """Retain interrupted attempts; never discard a user or runtime file."""
        parent, location, _source, environment = installer._paths(module_id, spec, root)
        if not location.exists() or (location / "installation.json").exists():
            return
        current = _read(parent / "installation.json", {})
        if (isinstance(current, dict) and current.get("revision") == spec["revision"]
                and current.get("manifest_spec_sha256") == installer._digest_json(spec)):
            return  # A valid existing installation is verified, never replaced.
        source_receipt = _read(location / "source.json")
        if source_receipt is not None:
            installer._source_integrity(location / "source", spec)
            if environment.exists():
                environment.rename(location / f"env.failed-{uuid.uuid4().hex}")
            return
        location.rename(parent / f"failed-{spec['revision']}-{uuid.uuid4().hex}")
        source_pointer = _read(parent / "source.json", {})
        if (isinstance(source_pointer, dict) and source_pointer.get("revision") == spec["revision"]
                and source_pointer.get("source_path") == str(location / "source")):
            (parent / "source.json").rename(parent / f"source.failed-{uuid.uuid4().hex}.json")

    def install_default_modules(self) -> dict:
        """Install TOPOS/TORQ independently; either failure leaves BASE usable."""
        free = _read(self.artifact_dir / "free-engines/setup-status.json", {})
        if free.get("status") == "failed":
            self.retry_free_engines()
        return self.install_modules(DEFAULT_MODULES)

    def retry_free_engines(self) -> dict:
        """Retry actual downloads and republish all eleven authority phases."""
        with self._operation("retry_free_engines"):
            from scripts.hosted_dashboard import prepare_free_engines, refresh_stage0_authority
            runtime = self._active_runtime()
            python = Path(runtime["python_path"])
            self._progress("retry_free_engines", "Retrying pinned free-engine downloads; BASE inputs and results remain intact.")
            result = prepare_free_engines(python, self.artifact_dir)
            self._progress("retry_free_engines", "Refreshing all eleven setup phases using actually available engines.")
            evidence = refresh_stage0_authority(python, self.artifact_dir)
            self._write("free-engine-retry.json", {"schema_version": "cochem.free-engine-retry/1",
                "free_engines": result, "authority": evidence, "created_at": _now()})
        return result

    def install_modules(self, module_ids=DEFAULT_MODULES) -> dict:
        """Install a selected reviewed set, including its actual private dependencies."""
        selected = tuple(dict.fromkeys(module_ids))
        if not selected or any(not isinstance(name, str) or not installer.ID_PATTERN.fullmatch(name) for name in selected):
            raise StudentSetupError("Choose at least one module from the reviewed catalog.")
        result = {"schema_version": SETUP_SCHEMA, "created_at": _now(), "modules": {}}
        with self._operation("install"):
            catalog = installer.load_manifest(self.manifest_path)["modules"]
            if any(name not in catalog for name in selected):
                raise StudentSetupError("A selected module is absent from the reviewed catalog.")
            ordered = sorted(selected, key=lambda name: (name == "topos", name != "torq", name))
            for module_id in ordered:
                self._progress("install", f"Installing and verifying {module_id.upper()} in its own environment.")
                try:
                    spec = catalog[module_id]
                    self._retry_owned_failure(module_id, spec, self.artifact_dir / "Modules")
                    dependencies = self._private_dependencies(module_id, spec, catalog)
                    receipt = installer.install_module(module_id, spec, self.artifact_dir / "Modules", dependency_wheels=dependencies)
                    result["modules"][module_id] = {"status": "installed", "revision": spec["revision"],
                        "message": "Installation and dependencies verified.", "operations": receipt["operations"]}
                except Exception as error:
                    result["modules"][module_id] = {"status": "failed", "operations": [],
                        "message": installer._redact(str(error)) + " BASE remains usable. Check module access, then click Retry setup."}
                self._write("initial-setup.json", result)
            free = _read(self.artifact_dir / "free-engines/setup-status.json", {})
            result["free_engines"] = free
            result["ready"] = all(item["status"] == "installed" for item in result["modules"].values()) and free.get("status") != "failed"
            result["message"] = "The selected modules are installed and verified." if result["ready"] else "BASE is ready. Unavailable modules remain disabled; correct access and click Retry setup."
            self._write("initial-setup.json", result)
        return result

    def _private_base_wheel(self, version: str, revision: str | None = None) -> Path:
        if not re.fullmatch(r"\d+\.\d+\.\d+", version):
            raise StudentSetupError("A private BASE dependency must declare an exact stable version.")
        if revision is not None and not _SHA.fullmatch(revision):
            raise StudentSetupError("The reviewed private BASE science source must name an exact Git revision.")
        # A reviewed catalog may bind an immutable candidate before its release
        # is published. Never substitute a branch or mutate a released wheel.
        revision = revision or _resolve_release("v" + version)
        spec = _base_spec(revision)
        root = self.artifact_dir / "DependencyRuntime"
        self._retry_owned_failure("base", spec, root)
        source_receipt = installer.fetch_module("base", spec, root, activate=False)
        source = Path(source_receipt["source_path"])
        location = source.parent
        import tomllib
        project = tomllib.loads((source / "pyproject.toml").read_text(encoding="utf-8")).get("project", {})
        if installer._canonical_name(str(project.get("name", ""))) != "cochem-base" or project.get("version") != version:
            raise StudentSetupError("The reviewed private BASE science source differs from its declared distribution or version.")
        previous = _read(location / "wheel.json")
        if isinstance(previous, dict):
            wheel = Path(previous["wheel_path"])
            if (wheel.parent != location / "wheels" or wheel.is_symlink() or not wheel.is_file()
                    or hashlib.sha256(wheel.read_bytes()).hexdigest() != previous.get("wheel_sha256")
                    or previous.get("source_sha256") != source_receipt["source_sha256"]
                    or previous.get("revision") != revision or previous.get("version") != version):
                raise StudentSetupError("The retained private BASE dependency wheel changed; no provider was installed.")
            name, actual_version = installer._wheel_identity(wheel)
            if installer._canonical_name(name) != "cochem-base" or actual_version != version:
                raise StudentSetupError("The retained private BASE dependency wheel has incompatible metadata.")
            return wheel
        wheels = location / "wheels"
        wheels.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".wheel-build-", dir=location) as temporary:
            copied = Path(temporary) / "source"
            shutil.copytree(source, copied, ignore=shutil.ignore_patterns(".git"), symlinks=True)
            installer._run([sys.executable, "-I", "-B", "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(wheels), str(copied)],
                env=installer._build_env(), label="Build verified private BASE dependency wheel")
        candidates = list(wheels.glob("*.whl"))
        if len(candidates) != 1:
            raise StudentSetupError("The private BASE dependency build did not produce exactly one wheel.")
        wheel = candidates[0]
        name, actual_version = installer._wheel_identity(wheel)
        if installer._canonical_name(name) != "cochem-base" or actual_version != version:
            raise StudentSetupError("The private BASE dependency wheel differs from its declared compatible version.")
        installer._source_integrity(source, spec)
        installer._atomic_json(location / "wheel.json", {"wheel_path": str(wheel), "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
            "source_sha256": source_receipt["source_sha256"], "revision": revision, "version": version})
        return wheel

    def _private_dependencies(self, module_id: str, spec: dict, catalog: dict) -> list[Path]:
        """Supply actual private wheels, rather than pretending they are on PyPI."""
        source_receipt = installer.fetch_module(module_id, spec, self.artifact_dir / "Modules", activate=False)
        source = Path(source_receipt["source_path"])
        project_file = source / "pyproject.toml"
        if not project_file.is_file():
            return []
        import tomllib
        dependencies = tomllib.loads(project_file.read_text(encoding="utf-8")).get("project", {}).get("dependencies", [])
        wheels = []
        for requirement in dependencies:
            name = re.match(r"[A-Za-z0-9_.-]+", requirement)
            if name is None:
                raise StudentSetupError("The provider has an invalid package requirement.")
            normalized = installer._canonical_name(name.group()) + requirement[name.end():]
            if normalized.startswith("cochem-base"):
                try:
                    from packaging.requirements import Requirement
                except ImportError:
                    from pip._vendor.packaging.requirements import Requirement
                requested = Requirement(requirement)
                if requested.url or requested.extras:
                    raise StudentSetupError("Private BASE dependencies must use the reviewed stable science wheel.")
                exact = re.fullmatch(r"cochem-base\s*==\s*(\d+\.\d+\.\d+)", normalized)
                science_version = exact.group(1) if exact else str(spec.get("science_base_version", "1.0.1"))
                if science_version not in requested.specifier:
                    raise StudentSetupError("The reviewed private BASE science version does not satisfy this provider's declared dependency.")
                wheels.append(self._private_base_wheel(science_version, spec.get("science_base_revision")))
            elif normalized.startswith("cochem-torq") and module_id != "torq":
                receipt = installer.install_module("torq", catalog["torq"], self.artifact_dir / "Modules", activate=False,
                    dependency_wheels=self._private_dependencies("torq", catalog["torq"], catalog))
                wheel_path = receipt.get("built_wheel_path")
                if wheel_path is None:
                    raise StudentSetupError("The reviewed TORQ dependency has no retained verified wheel; retry its setup.")
                wheels.append(Path(wheel_path))
        return wheels

    def _course_channel(self, token: str | None = None) -> dict | None:
        origin = _read(self.state_dir / "assignment-runtime.json", {})
        assignment = Path(origin.get("source_path", str(self.repository_root)))
        config = _read(assignment / ".cochem" / "course-runtime.json")
        if config is None:
            return None
        if isinstance(config, dict) and config.get("channel") in {"stable-release", "canonical-default-branch"}:
            if config.get("schema_version") != "cochem.course-channel/1" or config.get("repository", UPSTREAM) != UPSTREAM:
                raise StudentSetupError("The instructor update channel has an invalid canonical repository identity.")
            return None
        if (not isinstance(config, dict) or config.get("schema_version") != "cochem.course-channel/1"
                or config.get("repository", UPSTREAM) != UPSTREAM
                or not re.fullmatch(r"\.cochem/course-channels/[a-z0-9][a-z0-9_-]*\.json", str(config.get("path", "")))):
            raise StudentSetupError("The instructor course channel must name a data file in the canonical BASE repository.")
        path = config["path"]
        request = urllib.request.Request(f"https://api.github.com/repos/{UPSTREAM}/contents/{path}?ref=main",
            headers={"Accept": "application/vnd.github+json", "User-Agent": "CoChem-BASE-student-updater"})
        token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or os.environ.get("COCHEM_SOURCE_CREDENTIAL")
        if token:
            request.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.build_opener(_NoRedirect()).open(request, timeout=30) as response:
                raw = response.read(1024 * 1024 + 1)
        except urllib.error.HTTPError as error:
            raise StudentSetupError(f"The instructor-approved course channel could not be read (GitHub HTTP {error.code}).") from error
        if len(raw) > 1024 * 1024:
            raise StudentSetupError("The instructor channel exceeds its size limit.")
        content = json.loads(raw)
        if content.get("type") != "file" or content.get("encoding") != "base64":
            raise StudentSetupError("The course approval channel is not a bounded JSON data file.")
        data = base64.b64decode(content["content"])
        approval = json.loads(data)
        if (not isinstance(approval, dict) or approval.get("schema_version") != "cochem.course-approval/1"
                or approval.get("repository", UPSTREAM) != UPSTREAM
                or not _SHA.fullmatch(str(approval.get("approved_base_revision", "")))
                or not isinstance(approval.get("label"), str) or not approval["label"].strip()
                or len(approval["label"]) > 120 or any(char in approval["label"] for char in "\r\n\0")):
            raise StudentSetupError("The instructor approval must bind an exact compatible BASE Git revision.")
        return {"path": path, "sha256": hashlib.sha256(data).hexdigest(), **approval}

    def _update_channel(self) -> str:
        origin = _read(self.state_dir / "assignment-runtime.json", {})
        assignment = Path(origin.get("source_path", str(self.repository_root)))
        config = _read(assignment / ".cochem" / "course-runtime.json", {})
        configured = config.get("channel") if isinstance(config, dict) else None
        if configured in {"stable-release", "canonical-default-branch"}:
            return configured
        return os.environ.get("COCHEM_UPDATE_CHANNEL", "canonical-default-branch")

    def check_updates(self) -> dict:
        """Offer exact revisions from the instructor-selected maintained channel."""
        with self._operation("check_updates", require_idle=False):
            self._progress("check_updates", "Checking the maintained BASE channel and its reviewed module versions.")
            course = self._course_channel()
            channel = "course-approved" if course else self._update_channel()
            if channel == "stable-release":
                release = _release_metadata()
                revision = _resolve_release(release["tag_name"])
            elif channel == "canonical-default-branch":
                default = _resolve_default_branch()
                revision = default["revision"]
                release = {"id": None, "tag_name": "Maintained BASE " + default["branch"]}
            elif course is not None:
                revision = course["approved_base_revision"]
                release = {"id": None, "tag_name": course["label"]}
            else:
                raise StudentSetupError("The instructor update channel is unsupported.")
            current = self._active_runtime()
            base_root = self.artifact_dir / "BaseRuntime"
            self._retry_owned_failure("base", _base_spec(revision), base_root)
            source = installer.fetch_module("base", _base_spec(revision), base_root, activate=False)
            source_path = Path(source["source_path"])
            reviewed_manifest = source_path / "scripts" / "module-distribution.json"
            catalog = installer.load_manifest(reviewed_manifest)
            if not all(name in catalog["modules"] for name in DEFAULT_MODULES):
                raise StudentSetupError("The new release does not provide the required reviewed TOPOS/TORQ manifest.")
            modules = {}
            for name in DEFAULT_MODULES:
                spec = catalog["modules"][name]
                current_receipt = _read(self.artifact_dir / "Modules" / name / "installation.json", {})
                modules[name] = {"revision": spec["revision"], "current_revision": current_receipt.get("revision"),
                    "update_available": current_receipt.get("manifest_spec_sha256") != installer._digest_json(spec)}
            import tomllib
            incoming_project = tomllib.loads((source_path / "pyproject.toml").read_text(encoding="utf-8"))["project"]
            current_project = tomllib.loads((self.repository_root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
            def version(value):
                match = _RELEASE.fullmatch("v" + str(value))
                if match is None:
                    raise StudentSetupError("Only stable semantic BASE versions can be applied to a student runtime.")
                return tuple(map(int, match.groups()))
            compatible = version(incoming_project["version"]) >= version(current_project["version"])
            required = ["src/cochem_base/interfaces/student_setup.py", "src/cochem_base/interfaces/student_actions.py",
                        "scripts/run_student_research.py", ".github/workflows/student_research.yml"]
            compatible = compatible and all((source_path / name).is_file() for name in required)
            for name in DEFAULT_MODULES:
                active_receipt = _read(self.artifact_dir / "Modules" / name / "installation.json", {})
                if not set(active_receipt.get("operations", [])).issubset(catalog["modules"][name]["operations"]):
                    compatible = False
            base_update = current.get("revision") != revision
            available = base_update or any(item["update_available"] for item in modules.values())
            plan = {"schema_version": PLAN_SCHEMA, "plan_id": uuid.uuid4().hex, "created_at": _now(),
                "status": "updates_available" if available and compatible else "current", "compatible": compatible, "release_id": release["id"],
                "channel": channel, "course_approval": course,
                "base": {"repository": UPSTREAM, "tag": release["tag_name"], "revision": revision,
                    "current_revision": current.get("revision"), "update_available": base_update,
                    "source_path": str(source_path), "source_sha256": source["source_sha256"]},
                "manifest": catalog, "manifest_sha256": hashlib.sha256(reviewed_manifest.read_bytes()).hexdigest(),
                "modules": modules, "restart_required": base_update,
                "scope": "Exact maintainer-approved BASE and provider pins; student files remain in the assignment repository.",
                "message": "Compatible updates are available." if available and compatible else ("This channel has no compatible newer student runtime; the current version is retained." if not compatible else "The current reviewed versions are up to date.") }
            self._write("update-plan.json", plan)
        return plan

    def _plan(self) -> dict:
        plan = _read(self.state_dir / "update-plan.json")
        if not isinstance(plan, dict) or plan.get("schema_version") != PLAN_SCHEMA or plan.get("status") != "updates_available":
            raise StudentSetupError("Click Check updates first. There is no reviewed compatible update ready to apply.")
        if not re.fullmatch(r"[0-9a-f]{32}", str(plan.get("plan_id", ""))):
            raise StudentSetupError("The reviewed update has an invalid receipt identity.")
        base = plan.get("base", {})
        if base.get("repository") != UPSTREAM or not _SHA.fullmatch(str(base.get("revision", ""))):
            raise StudentSetupError("The recorded update has an invalid upstream identity.")
        if plan.get("channel") == "course-approved":
            if self._course_channel() != plan.get("course_approval"):
                raise StudentSetupError("The instructor approval changed after checking. Check updates again.")
        elif plan.get("channel") == "canonical-default-branch":
            if _resolve_default_branch()["revision"] != base["revision"]:
                raise StudentSetupError("The maintained BASE revision changed after checking. Check updates again.")
        elif _resolve_release(base["tag"]) != base["revision"]:
            raise StudentSetupError("The release tag changed after checking. Check updates again; no runtime was changed.")
        expected = installer._paths("base", _base_spec(base["revision"]), self.artifact_dir / "BaseRuntime")[2]
        if Path(base.get("source_path", "")).resolve() != expected.resolve():
            raise StudentSetupError("The recorded update source is outside its pinned runtime directory.")
        integrity = installer._source_integrity(expected, _base_spec(base["revision"]))
        path = expected / "scripts" / "module-distribution.json"
        if (integrity["source_sha256"] != base.get("source_sha256")
                or hashlib.sha256(path.read_bytes()).hexdigest() != plan.get("manifest_sha256")
                or installer.load_manifest(path) != plan.get("manifest")):
            raise StudentSetupError("The reviewed update changed after checking; no runtime was changed.")
        return plan

    def _prepare_base(self, plan: dict) -> dict:
        source = Path(plan["base"]["source_path"])
        import tomllib
        project = tomllib.loads((source / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        requirements = list(project.get("optional-dependencies", {}).get("ui", []))
        requirements += list(project.get("optional-dependencies", {}).get("symmetry", []))
        spec = _base_spec(plan["base"]["revision"], requirements)
        self._retry_owned_failure("base", spec, self.artifact_dir / "BaseRuntime")
        # Source inspection and UI installation can have different dependency
        # policies at the same Git revision. Obtain the exact immutable source
        # in the installation generation, leaving the inspected source intact.
        source_receipt = installer.fetch_module("base", spec, self.artifact_dir / "BaseRuntime", activate=False)
        source = Path(source_receipt["source_path"])
        _parent, location, _, _ = installer._paths("base", spec, self.artifact_dir / "BaseRuntime")
        receipt = installer.install_module("base", spec, self.artifact_dir / "BaseRuntime", activate=False)
        authority = location / "authority"
        authority.mkdir(exist_ok=True, mode=0o700)
        dashboard = authority / "dashboard"
        dashboard.mkdir(exist_ok=True, mode=0o700)
        from scripts.hosted_dashboard import (
            requested_silos,
            runtime_environment,
            setup_build_environment,
        )
        installer._atomic_json(dashboard / "deployment_manifest.json", {
            "selected_repositories": ["CoChem-BASE", "CoChem-TOPOS", "CoChem-TORQ"],
            "requested_silos": requested_silos(self.artifact_dir)})
        env = setup_build_environment(runtime_environment(self.artifact_dir))
        env.update(COCHEM_ARTIFACT_DIR=str(authority), COCHEM_CONFIG=str(authority / "Registry/cochem_system_config.json"),
                   COCHEM_MANIFEST_PATH=str(dashboard / "deployment_manifest.json"),
                   QT_QPA_PLATFORM="offscreen", COCHEM_HEADLESS="1", PYTHONDONTWRITEBYTECODE="1")
        for variable, name in {"COCHEM_CORE_SILO": "cochem_core_silo", "COCHEM_UI_SILO": "cochem_ui_silo",
                               "COCHEM_CALC_SILO": "cochem_calc_silo", "COCHEM_ML_SILO": "cochem_mace_silo"}.items():
            env[variable] = str(authority / "Silos" / name)
        # Authority is prepared under the candidate revision. Failed setup and
        # rollback leave the previous registry, engine seals and silos untouched.
        installer._run([receipt["python_path"], "-B", str(source / "cli.py"), "setup", "--all",
            "--artifact-dir", str(authority), "--min-disk-space-gb", "1", "--json"],
            env=env, label="Validate new BASE runtime through complete Stage 0", cwd=source)
        installer.verify_installation("base", spec, self.artifact_dir / "BaseRuntime", active=False)
        return {"schema_version": RUNTIME_SCHEMA, "kind": "reviewed-release", "source_path": str(source),
            "python_path": receipt["python_path"], "revision": spec["revision"], "tag": plan["base"]["tag"],
            "base_spec": spec, "manifest_path": str(source / "scripts/module-distribution.json"), "authority_path": str(authority),
            "activated_at": _now()}

    def _snapshot(self) -> dict:
        modules = {}
        catalog = installer.load_manifest(self.manifest_path)["modules"]
        for name in DEFAULT_MODULES:
            parent = self.artifact_dir / "Modules" / name
            receipt = _read(parent / "installation.json")
            if receipt is not None:
                # Migrate pre-update installations into retained revision receipts.
                spec = catalog.get(name)
                if spec is None or spec["revision"] != receipt.get("revision"):
                    raise StudentSetupError("An active module differs from this interface's reviewed manifest. Restart the interface before updating.")
                installer.install_module(name, spec, self.artifact_dir / "Modules")
            modules[name] = {"installation": receipt, "source": _read(parent / "source.json"), "spec": catalog.get(name)}
        return {"schema_version": RUNTIME_SCHEMA, "runtime": self._active_runtime(), "modules": modules}

    def _restore(self, snapshot: dict) -> None:
        for name, record in snapshot["modules"].items():
            parent = self.artifact_dir / "Modules" / name
            parent.mkdir(parents=True, exist_ok=True)
            for filename, key in (("installation.json", "installation"), ("source.json", "source")):
                if record[key] is None:
                    (parent / filename).unlink(missing_ok=True)
                else:
                    installer._atomic_json(parent / filename, record[key])
        self._write("active-runtime.json", snapshot["runtime"])

    def apply_updates(self) -> dict:
        with self._operation("apply_updates"):
            plan = self._plan()
            current = self._active_runtime()
            if current.get("revision") != plan["base"]["current_revision"]:
                raise StudentSetupError("The active version changed after checking. Click Check updates again.")
            snapshot = self._snapshot()
            for name in ("torq", "topos"):
                spec = plan["manifest"]["modules"][name]
                self._progress("apply_updates", f"Preparing and verifying the reviewed {name.upper()} version. The previous version remains active.")
                self._retry_owned_failure(name, spec, self.artifact_dir / "Modules")
                dependencies = self._private_dependencies(name, spec, plan["manifest"]["modules"])
                installer.install_module(name, spec, self.artifact_dir / "Modules", activate=False, dependency_wheels=dependencies)
            runtime = self._prepare_base(plan) if plan["base"]["update_available"] else current
            self._assert_idle()
            history = self.state_dir / "history"
            history.mkdir(exist_ok=True, mode=0o700)
            installer._atomic_json(history / f"{plan['plan_id']}.json", snapshot)
            try:
                for name in DEFAULT_MODULES:
                    installer.activate_installation(name, plan["manifest"]["modules"][name], self.artifact_dir / "Modules")
                self._write("active-runtime.json", runtime)
            except Exception:
                self._restore(snapshot)
                raise
            receipt = {"status": "applied", "plan_id": plan["plan_id"], "restart_required": bool(plan["base"]["update_available"]),
                "created_at": _now(), "previous_runtime": snapshot["runtime"], "runtime": runtime,
                "modules": plan["modules"], "message": "Updated versions are verified. Click Restart interface, then refresh your browser. Your structures and results are unchanged."}
            self._write("last-update.json", receipt)
            self._write("update-plan.json", dict(plan, status="applied"))
        return receipt

    def rollback(self) -> dict:
        with self._operation("rollback"):
            last = _read(self.state_dir / "last-update.json")
            if not isinstance(last, dict) or last.get("status") != "applied":
                raise StudentSetupError("There is no applied update available to roll back.")
            if not re.fullmatch(r"[0-9a-f]{32}", str(last.get("plan_id", ""))):
                raise StudentSetupError("The retained update receipt has an invalid identity.")
            snapshot = _read(self.state_dir / "history" / f"{last['plan_id']}.json")
            if not isinstance(snapshot, dict) or snapshot.get("schema_version") != RUNTIME_SCHEMA:
                raise StudentSetupError("The retained rollback receipt is missing or invalid.")
            if not isinstance(snapshot.get("modules"), dict) or set(snapshot["modules"]) != set(DEFAULT_MODULES):
                raise StudentSetupError("The retained module rollback manifest is incomplete or invalid.")
            validate_runtime_record(snapshot["runtime"], self.artifact_dir, self.repository_root)
            if snapshot["runtime"].get("base_spec"):
                installer.verify_installation("base", snapshot["runtime"]["base_spec"], self.artifact_dir / "BaseRuntime", active=False)
            for name, record in snapshot["modules"].items():
                if record["installation"] is not None:
                    checked = installer.verify_installation(name, record["spec"], self.artifact_dir / "Modules", active=False)
                    if checked != record["installation"]:
                        raise StudentSetupError("A retained module differs from the verified rollback receipt.")
            self._restore(snapshot)
            result = {"status": "rolled_back", "restart_required": True, "runtime": snapshot["runtime"],
                "message": "Previous verified versions restored. Restart the interface and refresh the browser."}
            self._write("last-update.json", dict(last, status="rolled_back"))
        return result

    def restart_dashboard(self) -> dict:
        """Ask the owned launcher to restart after the widget reply is delivered."""
        with self._operation("restart"):
            runtime = self._active_runtime()
            validate_runtime_record(runtime, self.artifact_dir, self.repository_root)
            launcher = self.repository_root / "scripts" / "hosted_dashboard.py"
            # Retain the user's own Codespaces identity and the instructor's
            # scoped source reader for personal-project updates after restart.
            # Package builds still receive installer._build_env(), never credentials.
            env = os.environ.copy()
            for name in ("base_source_credential", "COCHEM_ORCA_ASSET_CREDENTIAL", "COCHEM_CFOUR_ASSET_CREDENTIAL"):
                env.pop(name, None)
            env.update(COCHEM_ARTIFACT_DIR=str(self.artifact_dir), COCHEM_STUDENT_AUTO_SETUP="true")
            log_path = self.state_dir / "restart.log"
            with log_path.open("ab") as log:
                child = subprocess.Popen([sys.executable, "-B", str(launcher), "restart", "--artifacts", str(self.artifact_dir), "--restart-delay", "2"],
                    cwd=self.repository_root, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                    start_new_session=os.name != "nt")
            self._write("restart-request.json", {"requested_at": _now(), "pid": child.pid, "runtime": runtime})
        return {"status": "restart_requested", "message": "The interface is restarting. Refresh this browser tab in about ten seconds; startup may take longer."}


def validate_runtime_record(record: dict, artifact_dir: Path, repository_root: Path) -> None:
    if not isinstance(record, dict) or record.get("schema_version") != RUNTIME_SCHEMA:
        raise StudentSetupError("The selected runtime has no valid versioned receipt.")
    source = Path(record.get("source_path", "")).expanduser().resolve()
    python = Path(record.get("python_path", "")).expanduser().absolute()
    if record.get("kind") == "assignment":
        # Assignment rollback may be requested from a newer external runtime.
        origin = _read(artifact_dir / "StudentSetup" / "assignment-runtime.json")
        expected = Path(origin["source_path"]).resolve() if isinstance(origin, dict) else repository_root
        if source != expected or not (source / "Start_Here.ipynb").is_file() or not python.is_file():
            raise StudentSetupError("The assignment runtime is unavailable; retain the current version.")
    elif record.get("kind") == "reviewed-release":
        revision = record.get("revision", "")
        if not _SHA.fullmatch(str(revision)):
            raise StudentSetupError("The selected runtime lacks its immutable source revision.")
        spec = record.get("base_spec")
        if not isinstance(spec, dict) or spec.get("repository") != UPSTREAM or spec.get("revision") != revision:
            raise StudentSetupError("The selected runtime has an invalid source identity.")
        expected = installer._paths("base", spec, artifact_dir / "BaseRuntime")[1]
        if source != expected / "source" or python != installer._python_path(expected / "env"):
            raise StudentSetupError("The selected runtime is outside its verified revision directory.")
        if Path(record.get("authority_path", "")).resolve() != expected / "authority":
            raise StudentSetupError("The selected execution authority is outside its verified revision directory.")
    else:
        raise StudentSetupError("The selected runtime kind is unsupported.")


def resolve_worker_source(repository_root: str | Path | None = None, artifact_dir: str | Path | None = None, *, token: str | None = None) -> dict:
    """Resolve a trusted worker independently of a student's assignment Git HEAD.

    This small resolver uses stdlib and the stdlib-only source installer, so the
    Actions dispatcher can determine its pinned worker before installing BASE.
    ``main`` is read only for an explicitly configured instructor approval data
    file; executable source is always fetched at the returned immutable SHA.
    """
    source = Path(repository_root or installer.REPOSITORY_ROOT).expanduser().resolve()
    artifacts = Path(artifact_dir or os.environ.get("COCHEM_ARTIFACT_DIR", "~/CoChem_Artifacts")).expanduser().resolve()
    resolver = object.__new__(StudentSetupService)
    resolver.repository_root = source
    resolver.artifact_dir = artifacts
    resolver.state_dir = artifacts / "StudentSetup"
    course = resolver._course_channel(token=token)
    if course is not None:
        return {"revision": course["approved_base_revision"], "approval": "course-approved", "label": course["label"],
                "repository": UPSTREAM, "course_approval": course}
    if resolver._update_channel() == "canonical-default-branch":
        default = _resolve_default_branch(token=token)
        return {"revision": default["revision"], "approval": "canonical-default-branch", "label": "Maintained BASE " + default["branch"], "repository": UPSTREAM}
    release = _release_metadata(token=token)
    return {"revision": _resolve_release(release["tag_name"], token=token), "approval": "stable-release",
            "label": release["tag_name"], "repository": UPSTREAM, "release_id": release["id"]}
