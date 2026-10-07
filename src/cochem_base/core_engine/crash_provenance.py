"""Durable, exact crash evidence shared by execution brokers."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid
from typing import Mapping, Sequence

import psutil

from cochem.core.context import assert_writable_path


def _source_git_identity() -> tuple[str | None, str | None, dict]:
    """Collect optional source identity without replacing the original failure.

    Installed wheels need not have Git metadata or a Git executable. A broken
    repository or a blocked Git command must likewise leave an honest omission
    in the durable crash record, not interrupt recording the process crash.
    """
    metadata = {"status": "no_repository", "repository": None}
    try:
        source = Path(__file__).resolve()
        repository = next((parent for parent in source.parents if (parent / ".git").exists()), None)
        if repository is None:
            return None, None, metadata
        metadata["repository"] = str(repository)
        # Source identity belongs to this module's checkout, regardless of an
        # enclosing Git command or user's selected repository. Keep ordinary
        # config inputs (and their bounded timeout), but isolate repository,
        # object-store and ref selectors. cwd discovery supports .git files in
        # linked worktrees as well as ordinary .git directories.
        git_environment = dict(os.environ)
        for name in (
            "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_INDEX_FILE", "GIT_GRAFT_FILE",
            "GIT_SHALLOW_FILE", "GIT_NAMESPACE", "GIT_REPLACE_REF_BASE",
            "GIT_PREFIX", "GIT_IMPLICIT_WORK_TREE", "GIT_CEILING_DIRECTORIES",
            "GIT_DISCOVERY_ACROSS_FILESYSTEM", "GIT_CONFIG", "GIT_CONFIG_COUNT",
            "GIT_CONFIG_PARAMETERS",
        ):
            git_environment.pop(name, None)
        git_environment["GIT_NO_REPLACE_OBJECTS"] = "1"
        commit_id = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD^{commit}"], cwd=repository,
            env=git_environment, capture_output=True, timeout=2, check=True,
        )
        commit = commit_id.stdout.decode("ascii").strip()
        if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit) is None:
            raise ValueError("Git did not return a full hexadecimal commit object identity")
        # Pin the resolved object: HEAD can move between these two commands.
        commit_object = subprocess.run(
            ["git", "cat-file", "commit", commit], cwd=repository,
            env=git_environment, capture_output=True, timeout=2, check=True,
        )
        metadata["status"] = "available"
        return commit, hashlib.sha256(commit_object.stdout).hexdigest(), metadata
    except subprocess.TimeoutExpired as error:
        metadata.update(status="timeout", error_type=type(error).__name__, timeout_seconds=error.timeout)
    except subprocess.CalledProcessError as error:
        metadata.update(status="failed", error_type=type(error).__name__, exit_code=error.returncode,
                        stderr_tail=(error.stderr or b"")[-1024:].decode("utf-8", errors="replace"))
    except OSError as error:
        metadata.update(status="unavailable", error_type=type(error).__name__, error=str(error))
    except (UnicodeError, ValueError) as error:
        metadata.update(status="invalid_output", error_type=type(error).__name__, error=str(error))
    return None, None, metadata


def snapshot_process_context(
    command: Sequence[str], *, cwd: Path | str | None = None,
    environment: Mapping[str, str] | None = None,
    resources: Mapping | None = None,
) -> dict:
    """Bind executable and input hashes before launch, using the child's paths.

    Only resource controls are retained from the child environment. Credentials,
    other environment values, and licensed basis contents never enter the record.
    Native drivers such as CFOUR consume ``ZMAT`` without a command-line input.
    """
    work = Path(cwd or Path.cwd()).resolve()
    child_environment = dict(os.environ if environment is None else environment)
    binary = None
    if command:
        executable = Path(command[0])
        if executable.is_absolute() or any(separator in command[0] for separator in ("/", "\\")):
            candidate = executable if executable.is_absolute() else work / executable
            binary = str(candidate.resolve()) if candidate.is_file() else None
        else:
            binary = shutil.which(str(executable), path=child_environment.get("PATH", os.defpath))
            binary = str(Path(binary).resolve()) if binary else None
    binary_hash = None
    binary_status = "unresolved"
    if binary is not None:
        try:
            with open(binary, "rb") as stream:
                binary_hash = hashlib.file_digest(stream, "sha256").hexdigest()
            binary_status = "hashed_before_launch"
        except OSError as error:
            binary_status = f"unreadable:{type(error).__name__}"
    inputs = []
    candidates = [str(argument) for argument in command[1:]]
    candidates.extend(["ZMAT", "GENBAS", "ECPDATA"])
    seen: set[Path] = set()
    for argument in candidates:
        if "\x00" in argument or "\n" in argument:
            continue
        candidate = Path(argument)
        if not candidate.is_absolute():
            candidate = work / candidate
        try:
            candidate = candidate.resolve()
            if candidate in seen or not candidate.is_file():
                continue
            seen.add(candidate)
            with candidate.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            inputs.append({"path": str(candidate), "sha256": digest,
                           "size_bytes": candidate.stat().st_size})
        except OSError as error:
            inputs.append({"path": str(candidate), "status": f"unreadable:{type(error).__name__}"})
    resource_names = ("OMP_NUM_THREADS", "OMP_THREAD_LIMIT", "MKL_NUM_THREADS",
                      "OPENBLAS_NUM_THREADS", "BLIS_NUM_THREADS", "SLURM_CPUS_PER_TASK",
                      "SLURM_NTASKS", "PBS_NP")
    return {
        "working_directory": str(work), "binary_path": binary,
        "binary_sha256": binary_hash, "binary_identity_status": binary_status,
        "input_files": inputs, "input_identity_observed": "before_launch",
        "requested_resources": {**dict(resources or {}), "thread_environment": {
            name: child_environment[name] for name in resource_names if name in child_environment}},
    }


def record_process_crash(
    command: list[str], exit_code: int, stderr: bytes, log_directory: Path, *,
    execution_context: Mapping | None = None,
) -> dict:
    """Persist an exclusive, read-only JSON-LD crash record with exact tail bytes.

    Git object identity and its SHA-256 digest are distinct fields: Git may use
    SHA-1 object IDs, which must never be mislabeled as SHA-256.
    """
    context = dict(execution_context) if execution_context is not None else snapshot_process_context(command)
    recorder_module = Path(__file__).resolve()
    source_identity = {"package_version": None, "recorder_module_path": str(recorder_module),
                       "recorder_module_sha256": None}
    try:
        from cochem_base._version import get_version
        source_identity["package_version"] = get_version()
    except (ImportError, OSError, ValueError, KeyError) as error:
        source_identity["package_version_status"] = f"unavailable:{type(error).__name__}"
    try:
        with recorder_module.open("rb") as stream:
            source_identity["recorder_module_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
    except OSError as error:
        source_identity["recorder_module_status"] = f"unavailable:{type(error).__name__}"
    commit, commit_hash, git_provenance = _source_git_identity()
    memory = psutil.virtual_memory()
    record = {
        "@context": "https://schema.org/",
        "@type": "Event",
        "event": "process_crash",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "exit_code": exit_code,
        "stderr_tail_hex": stderr[-256:].hex(),
        "stderr_tail_bytes": len(stderr[-256:]),
        **context,
        "git_commit": commit,
        "git_commit_object_sha256": commit_hash,
        "git_provenance": git_provenance,
        "source_identity": source_identity,
        "inputs": command,
        "cpu_utilization_percent": psutil.cpu_percent(interval=None),
        "ram_used_bytes": memory.used,
        "ram_available_bytes": memory.available,
        "resource_observation": "system_at_crash_recording",
    }
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    record["sha256"] = hashlib.sha256(canonical).hexdigest()
    assert_writable_path(log_directory)
    log_directory.mkdir(parents=True, exist_ok=True)
    target = log_directory / f"crash-{uuid.uuid4().hex}.json"
    with target.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    target.chmod(0o444)
    return {**record, "record_path": str(target)}
