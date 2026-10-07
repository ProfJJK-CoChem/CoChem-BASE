"""Durable, exact crash evidence shared by execution brokers."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid

import psutil

from cochem.core.context import assert_writable_path


def record_process_crash(command: list[str], exit_code: int, stderr: bytes, log_directory: Path) -> dict:
    """Persist an exclusive, read-only JSON-LD crash record with exact tail bytes.

    Git object identity and its SHA-256 digest are distinct fields: Git may use
    SHA-1 object IDs, which must never be mislabeled as SHA-256.
    """
    binary = shutil.which(command[0]) if command else None
    binary_hash = None
    if binary is not None:
        with open(binary, "rb") as stream:
            binary_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    source = Path(__file__).resolve()
    repository = next((parent for parent in source.parents if (parent / ".git").exists()), None)
    commit = None
    commit_hash = None
    if repository is not None:
        commit_id = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repository, capture_output=True, timeout=2, check=True)
        commit_object = subprocess.run(["git", "cat-file", "commit", "HEAD"], cwd=repository, capture_output=True, timeout=2, check=True)
        commit = commit_id.stdout.decode("ascii").strip()
        commit_hash = hashlib.sha256(commit_object.stdout).hexdigest()
    memory = psutil.virtual_memory()
    record = {
        "@context": "https://schema.org/",
        "@type": "Event",
        "event": "process_crash",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "exit_code": exit_code,
        "stderr_tail_hex": stderr[-256:].hex(),
        "stderr_tail_bytes": len(stderr[-256:]),
        "binary_path": binary,
        "binary_sha256": binary_hash,
        "git_commit": commit,
        "git_commit_object_sha256": commit_hash,
        "inputs": command,
        "cpu_utilization_percent": psutil.cpu_percent(interval=None),
        "ram_used_bytes": memory.used,
        "ram_available_bytes": memory.available,
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
