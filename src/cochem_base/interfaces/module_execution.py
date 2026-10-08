"""Execute reviewed module operations in their independently verified environments.

An installed distribution is not a scientific acceptance result. Every execution
revalidates the pinned installation and the immutable handoff, and only explicitly
reviewed operations are dispatchable.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import tempfile
from threading import Event
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .artifact_handoff import load_module_handoff

_ADAPTERS = {
    "topos_geometry": "module_adapter_topos.py",
    "torq_geometry": "module_adapter_torq.py",
    "topos_provider": "module_adapter_topos.py",
    "torq_provider": "module_adapter_torq.py",
}


class ModuleOperationCancelled(RuntimeError):
    """The user cancelled this provider operation and its owned processes."""


def _environment() -> dict[str, str]:
    """Do not pass source/binary credentials or Python/Git injection to providers."""
    excluded = {"PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE", "VIRTUAL_ENV",
                "GIT_ASKPASS", "SSH_ASKPASS", "LD_PRELOAD", "LD_LIBRARY_PATH",
                "COCHEM_BASE_ROOT", "COCHEM_TOPOS_ROOT", "COCHEM_TORQ_ROOT",
                "COCHEM_TORQ_SIDECAR", "TOPOS_CONFIG", "TOPOS_EXECUTION_BACKEND"}
    env = {key: value for key, value in os.environ.items()
           if key not in excluded and not key.startswith("GIT_")
           and not any(word in key.upper() for word in ("TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "API_KEY"))}
    env.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="1",
               OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", PYTHONUTF8="1")
    return env


def installed_module_status(root: Path | None = None, manifest: Path | None = None) -> list[dict]:
    """Return installation observations without importing downstream namespaces."""
    from scripts.manage_modules import (
        DEFAULT_MANIFEST,
        default_root,
        load_manifest,
        verify_installation,
    )

    catalog = load_manifest(manifest or DEFAULT_MANIFEST)
    destination = (Path(root) if root is not None else default_root()).expanduser().resolve()
    observed = []
    for name, spec in catalog["modules"].items():
        item = {"module_id": name, "repository": spec["repository"], "revision": spec["revision"],
                "status": "not_installed", "operations": [], "scientific_execution_verified": False}
        if (destination / name / "installation.json").exists():
            try:
                receipt = verify_installation(name, spec, destination)
                if spec.get("adapter") in _ADAPTERS:
                    with tempfile.TemporaryDirectory(prefix="cochem-module-status-") as folder:
                        sidecar = _prepare_torq_sidecar(destination, catalog, Path(folder)) if name == "topos" else None
                        capability = probe_installed_capabilities(name, spec, receipt, sidecar=sidecar)
                else:
                    capability = None
            except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
                item.update(status="installation_invalid", reason=str(exc))
            else:
                item.update(status="installed", operations=capability["operations"] if capability else [],
                            provider_capabilities=capability)
        observed.append(item)
    return observed


def _prepare_torq_sidecar(root: Path, catalog: dict, directory: Path) -> Path | None:
    """Publish only a real reviewed isolated TORQ receipt, never a source guess."""
    from scripts.manage_modules import verify_installation

    spec = catalog["modules"].get("torq")
    if spec is None or not (Path(root) / "torq/installation.json").is_file():
        return None
    receipt = verify_installation("torq", spec, root)
    original = Path(root).expanduser().resolve() / "torq/installation.json"
    value = {"schema_version": "cochem.module-sidecar/1", "module_id": "torq",
             "root": str(Path(root).expanduser().resolve()), "spec": spec,
             "installation_receipt_sha256": hashlib.sha256(original.read_bytes()).hexdigest()}
    target = directory / "torq-sidecar.json"
    target.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    target.chmod(0o400)
    # The trusted receipt supplies the source; neither the request nor inherited
    # COCHEM_*_ROOT values can choose a provider namespace.
    if receipt["source_path"] != str(Path(root).resolve() / "torq" / spec["revision"] / "source"):
        raise ValueError("TORQ sidecar source differs from the verified installation")
    return target


def probe_installed_capabilities(module_id: str, spec: dict, receipt: dict, *, sidecar: Path | None = None) -> dict:
    """Observe callable receiver operations inside the sealed module environment."""
    import scripts

    if spec.get("adapter") not in _ADAPTERS:
        raise ValueError("This module has no reviewed capability adapter")
    adapter = Path(scripts.__file__).resolve().parent / _ADAPTERS[spec["adapter"]]
    with tempfile.TemporaryDirectory(prefix="cochem-provider-capability-") as folder:
        output = Path(folder) / "capabilities.json"
        command = [receipt["python_path"], "-I", "-B", str(adapter), "--capabilities", "--output", str(output)]
        if sidecar is not None:
            command.extend(["--torq-sidecar", str(sidecar)])
        process = subprocess.run(command, cwd=folder, env=_environment(), stdin=subprocess.DEVNULL,
                                 capture_output=True, text=True, timeout=60, check=False)
        if process.returncode or not output.is_file() or output.stat().st_size > 1_000_000:
            raise ValueError("Installed module capability discovery failed: " + process.stderr[-2000:])
        value = json.loads(output.read_text(encoding="utf-8"))
    if (value.get("schema_version") != "cochem.module-capabilities/1" or value.get("module_id") != module_id
            or not isinstance(value.get("operations"), list)
            or any(not isinstance(item, str) for item in value["operations"])):
        raise ValueError("Installed module returned an invalid capability report")
    provider = Path(value["provider_file"]).resolve(strict=True)
    environment = Path(receipt["python_path"]).parent.parent.resolve()
    if not provider.is_relative_to(environment) or hashlib.sha256(provider.read_bytes()).hexdigest() != value.get("provider_sha256"):
        raise ValueError("Capability provider is outside its verified environment or its source changed")
    value["operations"] = sorted(set(value["operations"]) & set(spec["operations"]))
    value["scientific_execution_verified"] = False
    value["adapter_sha256"] = hashlib.sha256(adapter.read_bytes()).hexdigest()
    return value


def _run_adapter(command: list[str], target: Path, log, timeout: float, *, cancel_event: Event | None = None) -> int:
    """Contain timed-out provider controllers and their owned native descendants."""
    import psutil

    if cancel_event is not None and cancel_event.is_set():
        raise ModuleOperationCancelled("Student research operation cancelled before native execution")
    process = subprocess.Popen(command, cwd=target, env=_environment(), stdin=subprocess.DEVNULL,
                               stdout=log, stderr=subprocess.STDOUT, start_new_session=os.name != "nt")
    try:
        if cancel_event is None:
            return process.wait(timeout=timeout)
        deadline = time.monotonic() + timeout
        while True:
            if cancel_event.is_set():
                raise ModuleOperationCancelled("Student research operation cancelled; owned native processes stopped")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout)
            try:
                return process.wait(timeout=min(0.25, remaining))
            except subprocess.TimeoutExpired:
                continue
    except BaseException:
        try:
            parent = psutil.Process(process.pid)
            owned = parent.children(recursive=True) + [parent]
        except psutil.NoSuchProcess:
            owned = []
        for child in reversed(owned):
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        _, remaining = psutil.wait_procs(owned, timeout=5)
        for child in remaining:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        process.wait(timeout=10)
        raise


def execute_module_handoff(handoff_path: str | Path, output: str | Path, *,
                           root: Path | None = None, manifest: Path | None = None,
                           timeout: float = 180, registry: str | Path | None = None,
                           cancel_event: Event | None = None) -> dict:
    """Run one bounded reviewed operation through an actually installed receiver."""
    import scripts
    from cochem.core.context import assert_writable_path
    from scripts.manage_modules import (
        DEFAULT_MANIFEST,
        default_root,
        load_manifest,
        verify_installation,
    )

    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("A finite positive provider execution timeout is required")

    path = Path(handoff_path).expanduser().resolve(strict=True)
    handoff = load_module_handoff(path)
    catalog = load_manifest(manifest or DEFAULT_MANIFEST)
    spec = catalog["modules"].get(handoff.module_id)
    if spec is None or handoff.operation not in spec["operations"]:
        raise ValueError("This module operation has no reviewed execution adapter")
    if handoff.module_id == "topos" and spec["adapter"] == "topos_handoff":
        from scripts.mandatory_ecosystem import execute
        return execute(path, Path(output).expanduser().resolve(), spec,
                       Path(root) if root is not None else default_root(), timeout=timeout,
                       cancellation_event=cancel_event)
    if spec["adapter"] not in _ADAPTERS:
        raise ValueError("This operation is not supported by BASE's installed adapters")
    if handoff.artifact.kind != "geometry_xyz":
        raise ValueError("Geometry analysis requires a single XYZ geometry handoff")
    if handoff.options and handoff.operation == "geometry_analysis":
        raise ValueError("Geometry analysis currently accepts no options; remove unsupported options")
    if handoff.artifact.metadata.get("atom_count", 0) > 2000:
        raise ValueError("The bounded geometry operation supports at most 2000 atoms")
    installation_root = Path(root) if root is not None else default_root()
    receipt = verify_installation(handoff.module_id, spec, installation_root)
    adapter = Path(scripts.__file__).resolve().parent / _ADAPTERS[spec["adapter"]]
    adapter_hash = hashlib.sha256(adapter.read_bytes()).hexdigest()
    target = Path(output).expanduser().resolve()
    assert_writable_path(target)
    target.mkdir(parents=True, exist_ok=False)
    sidecar = _prepare_torq_sidecar(installation_root, catalog, target) if handoff.module_id == "topos" else None
    artifact = path.parent / handoff.artifact.filename
    native_output = target / "operation.json"
    command = [receipt["python_path"], "-I", "-B", str(adapter),
               "--artifact" if handoff.operation == "geometry_analysis" else "--handoff",
               str(artifact) if handoff.operation == "geometry_analysis" else str(path),
               "--output", str(native_output)]
    if registry is not None and handoff.operation != "geometry_analysis":
        registry_path = Path(registry).expanduser().resolve(strict=True)
        command.extend(["--registry", str(registry_path)])
    if sidecar is not None:
        command.extend(["--torq-sidecar", str(sidecar)])
    identity = {"schema_version": "cochem.module-execution/1", "execution_id": uuid.uuid4().hex,
                "created_at": datetime.now(timezone.utc).isoformat(), "module_id": handoff.module_id,
                "operation": handoff.operation, "handoff_id": handoff.handoff_id,
                "input_sha256": handoff.artifact.sha256, "repository": spec["repository"],
                "revision": spec["revision"], "distribution": receipt["distribution_metadata"],
                "adapter_sha256": adapter_hash, "scientific_accuracy_established": False}
    try:
        capability = probe_installed_capabilities(handoff.module_id, spec, receipt, sidecar=sidecar)
        if handoff.operation not in capability["operations"]:
            raise ValueError("Requested operation is unavailable in the verified installed provider")
        with (target / "execution.log").open("w", encoding="utf-8") as log:
            returncode = _run_adapter(command, target, log, timeout, cancel_event=cancel_event)
        if returncode:
            raise RuntimeError(f"Module operation exited {returncode}; inspect {target / 'execution.log'}")
        if not native_output.is_file() or native_output.stat().st_size > 16 * 1024 * 1024:
            raise ValueError("Module did not publish a bounded operation report")
        native = json.loads(native_output.read_text(encoding="utf-8"))
        json.dumps(native, allow_nan=False)
        if (native.get("schema_version") != "cochem.module-operation/1"
                or native.get("module_id") != handoff.module_id
                or native.get("operation") != handoff.operation
                or native.get("input_sha256") != handoff.artifact.sha256):
            raise ValueError("Module operation report does not match the requested handoff")
        provider = Path(native["provider_file"]).resolve(strict=True)
        environment_path = Path(receipt["python_path"]).parent.parent.resolve()
        if not provider.is_relative_to(environment_path):
            raise ValueError("Module imported its provider outside the verified environment")
        if load_module_handoff(path) != handoff:
            raise ValueError("Module handoff changed during execution")
        verify_installation(handoff.module_id, spec, installation_root)
        if sidecar is not None:
            sidecar_value = json.loads(sidecar.read_text(encoding="utf-8"))
            verify_installation("torq", catalog["modules"]["torq"], installation_root)
            if hashlib.sha256((Path(installation_root) / "torq/installation.json").read_bytes()).hexdigest() != sidecar_value["installation_receipt_sha256"]:
                raise ValueError("TORQ sidecar changed during TOPOS execution")
        native_status = native.get("status", "completed") if handoff.operation == "geometry_analysis" else native.get("status")
        if handoff.operation == "geometry_analysis" and native_status == "succeeded":
            # The reviewed original TORQ file-exchange protocol used succeeded.
            native_status = "completed"
        if native_status not in {"completed", "partial", "timed-out", "cancelled", "failed", "unavailable", "unsupported"}:
            raise ValueError("Provider returned an invalid execution status")
        result = {**identity, "status": native_status, "operation_performed": native_status == "completed",
                  "scope": native["scope"], "result": native["result"], "provider_file": str(provider),
                  "provider_sha256": hashlib.sha256(provider.read_bytes()).hexdigest(),
                  "operation_report_sha256": hashlib.sha256(native_output.read_bytes()).hexdigest(),
                  "operation_report": native}
        (target / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        return result
    except Exception as exc:
        failure = {**identity, "status": "cancelled" if isinstance(exc, ModuleOperationCancelled) else "failed", "error": str(exc)}
        (target / "failure.json").write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8")
        raise
