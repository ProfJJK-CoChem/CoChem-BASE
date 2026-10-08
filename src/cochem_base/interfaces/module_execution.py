"""Execute reviewed module operations in their independently verified environments.

An installed distribution is not a scientific acceptance result. Every execution
revalidates the pinned installation and the immutable handoff, and only explicitly
reviewed operations are dispatchable.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .artifact_handoff import load_module_handoff

_ADAPTERS = {
    "topos_geometry": "module_adapter_topos.py",
    "torq_geometry": "module_adapter_torq.py",
}


def _environment() -> dict[str, str]:
    """Do not pass source/binary credentials or Python/Git injection to providers."""
    excluded = {"PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE", "VIRTUAL_ENV",
                "GIT_ASKPASS", "SSH_ASKPASS", "LD_PRELOAD", "LD_LIBRARY_PATH"}
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
                verify_installation(name, spec, destination)
            except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
                item.update(status="installation_invalid", reason=str(exc))
            else:
                item.update(status="installed", operations=spec["operations"])
        observed.append(item)
    return observed


def execute_module_handoff(handoff_path: str | Path, output: str | Path, *,
                           root: Path | None = None, manifest: Path | None = None,
                           timeout: float = 180, cancellation_event=None,
                           hosted_budget: Path | None = None) -> dict:
    """Run one bounded, reviewed geometry operation; preserve its exact provenance."""
    import scripts
    from cochem.core.context import assert_writable_path
    from scripts.manage_modules import (
        DEFAULT_MANIFEST,
        default_root,
        load_manifest,
        verify_installation,
    )

    path = Path(handoff_path).expanduser().resolve(strict=True)
    handoff = load_module_handoff(path)
    spec = load_manifest(manifest or DEFAULT_MANIFEST)["modules"].get(handoff.module_id)
    if spec is None or handoff.operation not in spec["operations"]:
        raise ValueError("This module operation has no reviewed execution adapter")
    if handoff.module_id == "topos" and spec["adapter"] == "topos_handoff":
        from scripts.mandatory_ecosystem import execute
        return execute(path, Path(output).expanduser().resolve(), spec,
                       Path(root) if root is not None else default_root(), timeout=timeout,
                       cancellation_event=cancellation_event, hosted_budget=hosted_budget)
    if hosted_budget is not None:
        raise ValueError("Hosted budget controls belong only to the exact mandatory TOPOS receiver")
    if spec["adapter"] not in _ADAPTERS or handoff.operation != "geometry_analysis":
        raise ValueError("This operation is not supported by BASE's installed adapters")
    if handoff.artifact.kind != "geometry_xyz":
        raise ValueError("Geometry analysis requires a single XYZ geometry handoff")
    if handoff.options:
        raise ValueError("Geometry analysis currently accepts no options; remove unsupported options")
    if handoff.artifact.metadata["atom_count"] > 2000:
        raise ValueError("The bounded geometry operation supports at most 2000 atoms")
    installation_root = Path(root) if root is not None else default_root()
    receipt = verify_installation(handoff.module_id, spec, installation_root)
    adapter = Path(scripts.__file__).resolve().parent / _ADAPTERS[spec["adapter"]]
    adapter_hash = hashlib.sha256(adapter.read_bytes()).hexdigest()
    target = Path(output).expanduser().resolve()
    assert_writable_path(target)
    target.mkdir(parents=True, exist_ok=False)
    artifact = path.parent / handoff.artifact.filename
    native_output = target / "operation.json"
    command = [receipt["python_path"], "-I", "-B", str(adapter), "--artifact", str(artifact),
               "--output", str(native_output)]
    identity = {"schema_version": "cochem.module-execution/1", "execution_id": uuid.uuid4().hex,
                "created_at": datetime.now(timezone.utc).isoformat(), "module_id": handoff.module_id,
                "operation": handoff.operation, "handoff_id": handoff.handoff_id,
                "input_sha256": handoff.artifact.sha256, "repository": spec["repository"],
                "revision": spec["revision"], "distribution": receipt["distribution_metadata"],
                "adapter_sha256": adapter_hash, "scientific_accuracy_established": False}
    try:
        with (target / "execution.log").open("w", encoding="utf-8") as log:
            completed = subprocess.run(command, cwd=target, env=_environment(), stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT, timeout=timeout, check=False)
        if completed.returncode:
            raise RuntimeError(f"Module operation exited {completed.returncode}; inspect {target / 'execution.log'}")
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
        result = {**identity, "status": "completed", "operation_performed": True,
                  "scope": native["scope"], "result": native["result"], "provider_file": str(provider),
                  "provider_sha256": hashlib.sha256(provider.read_bytes()).hexdigest(),
                  "operation_report_sha256": hashlib.sha256(native_output.read_bytes()).hexdigest(),
                  "operation_report": native}
        (target / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        return result
    except Exception as exc:
        failure = {**identity, "status": "failed", "error": str(exc)}
        (target / "failure.json").write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8")
        raise
