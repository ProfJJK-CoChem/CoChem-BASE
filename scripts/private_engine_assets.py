#!/usr/bin/env python3
"""Task-owned private-release staging through the user's existing GitHub identity.

Licensed archives stay outside Git and public artifacts. Genuine provider
permissions and byte readbacks are required; mathematical checks alone cannot
qualify a private-release staging transaction.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import re
import selectors
import shutil
import signal
import subprocess
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, BinaryIO
from urllib.parse import quote

SCHEMA = "cochem.private-engine-staging/1"
PURPOSE = "student-actions-calculation"
ROOT = Path(__file__).resolve().parents[1]
_REPOSITORY = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9._-]*")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_SHA1 = re.compile(r"[0-9a-f]{40}")
_TASK = re.compile(r"[0-9a-f]{32}")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}")
_WORKFLOW = re.compile(r"\.github/workflows/[A-Za-z0-9][A-Za-z0-9._-]*\.ya?ml")
_ZERO_SHA = "0" * 64


class PrivateAssetError(RuntimeError):
    """A provider, identity, ownership or byte-integrity prerequisite failed."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("Duplicate JSON object keys are forbidden.")
        result[name] = value
    return result


def _json(raw: bytes) -> Any:
    return json.loads(
        raw,
        object_pairs_hook=_object_pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON value.")),
    )


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _file_sha(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def _positive_id(value: Any) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError("Provider IDs and byte counts must be positive integers.")
    return value


def _digest(value: Any) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value) or value == _ZERO_SHA:
        raise ValueError("A genuine nonzero lowercase SHA-256 pin is required.")
    return value


def _text(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 300
        or any(char in value for char in "\r\n\x00")
    ):
        raise ValueError("Identity fields require bounded single-line strings.")
    return value


def _repository(value: Any) -> str:
    if not isinstance(value, str) or not _REPOSITORY.fullmatch(value):
        raise ValueError("Repository identity must be OWNER/REPOSITORY.")
    return value


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("Use an explicit UTC timestamp ending in Z.")
    return datetime.fromisoformat(value[:-1] + "+00:00")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _safe_path(path: Path) -> Path:
    result = path.absolute()
    for part in (result, *result.parents):
        if part.is_symlink():
            raise ValueError("Private asset paths cannot traverse symlinks.")
    return result


def _private_output(path: Path) -> Path:
    result = _safe_path(path)
    if result.is_relative_to(ROOT):
        raise ValueError("Private archives and receipts must stay outside the checkout.")
    for parent in result.parents:
        if (parent / ".git").exists():
            raise ValueError("Private archives and receipts cannot be written inside Git.")
    return result


def _write_private(path: Path, raw: bytes, *, exclusive: bool = False) -> None:
    path = _private_output(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if exclusive:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    else:
        fd, name = tempfile.mkstemp(prefix=".private-asset-journal-", dir=path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _codespaces() -> None:
    if os.environ.get("CODESPACES") != "true":
        raise PrivateAssetError("Staging and lifecycle repair require the Codespaces interface.")


def _gh_environment() -> dict[str, str]:
    # Use injected/native gh authentication normally. Never ask gh to reveal a
    # credential, read its auth files, or persist its environment in a receipt.
    environment = os.environ.copy()
    environment["GH_DEBUG"] = "0"
    environment["GH_PROMPT_DISABLED"] = "1"
    environment["GH_PAGER"] = "cat"
    environment["GH_FORCE_TTY"] = "0"
    return environment


def _gh(
    arguments: list[str], *, output: BinaryIO | int = subprocess.PIPE, seconds: int = 120
) -> bytes:
    executable = shutil.which("gh")
    if executable is None:
        raise PrivateAssetError("The actual authenticated GitHub CLI is required.")
    process = subprocess.Popen(
        [executable, *arguments],
        stdin=subprocess.DEVNULL,
        stdout=output,
        stderr=subprocess.PIPE,
        env=_gh_environment(),
        start_new_session=True,
    )
    try:
        stdout, _ = process.communicate(timeout=seconds)
    except subprocess.TimeoutExpired as exc:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise PrivateAssetError("Authenticated GitHub operation exceeded its time budget.") from exc
    if process.returncode:
        # gh stderr can contain signed storage URLs or private server details.
        # Preserve status, not those strings, in user-facing errors/journals.
        raise PrivateAssetError(f"Authenticated GitHub operation exited {process.returncode}.")
    if stdout is None:
        return b""
    if len(stdout) > 4 * 1024 * 1024:
        raise PrivateAssetError("GitHub metadata exceeded the bounded response size.")
    return stdout


def _api(endpoint: str, *, method: str = "GET", body: dict[str, Any] | None = None) -> Any:
    if not endpoint.startswith(("repos/", "user")) or "://" in endpoint:
        raise ValueError("Only internally constructed GitHub API routes are accepted.")
    arguments = [
        "api",
        "--hostname",
        "github.com",
        "--method",
        method,
        "-H",
        "Accept: application/vnd.github+json",
        "-H",
        "X-GitHub-Api-Version: 2022-11-28",
        endpoint,
    ]
    if body is None:
        raw = _gh(arguments)
    else:
        with tempfile.TemporaryDirectory(prefix="cochem-private-json-") as directory:
            path = Path(directory) / "request.json"
            path.write_bytes(canonical_json(body))
            path.chmod(0o600)
            raw = _gh([*arguments, "--input", str(path)])
    return _json(raw) if raw.strip() else None


def _repo_record(repository: str) -> dict[str, Any]:
    record = _api(f"repos/{_repository(repository)}")
    if not isinstance(record, dict) or record.get("full_name") != repository:
        raise PrivateAssetError("GitHub returned a different repository identity.")
    _positive_id(record.get("id"))
    return record


def _personal_private(repository: str, *, owner: bool) -> dict[str, Any]:
    record = _repo_record(repository)
    account = record.get("owner") or {}
    if record.get("private") is not True or account.get("type") != "User":
        raise PrivateAssetError("Licensed staging requires a real personal private repository.")
    _positive_id(account.get("id"))
    if owner:
        authenticated = _api("user")
        if (
            authenticated.get("type") != "User"
            or authenticated.get("id") != account["id"]
            or authenticated.get("login") != account.get("login")
        ):
            raise PrivateAssetError(
                "The authenticated Codespaces user must own the private project."
            )
    return record


def _distribution(engine: str, value: dict[str, Any]) -> dict[str, Any]:
    if engine not in {"orca", "cfour"}:
        raise ValueError("Only explicitly supported engine descriptors are accepted.")
    if not isinstance(value, dict):
        raise ValueError("An independently reviewed distribution object is required.")
    loader = importlib.import_module(f"scripts.provision_{engine}").load_distribution_manifest
    with tempfile.TemporaryDirectory(prefix="cochem-reviewed-descriptor-") as directory:
        path = Path(directory) / "distribution.json"
        path.write_bytes(canonical_json(value))
        path.chmod(0o600)
        validated = loader(path)
    if engine == "orca" and validated != loader():
        raise ValueError("ORCA staging must match the existing reviewed distribution exactly.")
    _repository(validated["repository"])
    if not _NAME.fullmatch(validated["release_tag"]) or not _NAME.fullmatch(
        validated["archive_name"]
    ):
        raise ValueError("Only literal reviewed release tags and archive names are supported.")
    _digest(validated["sha256"])
    return validated


def _receipt_shape(record: Any, *, allow_expired: bool = False) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema_version") != SCHEMA:
        raise ValueError("An exact private-engine staging receipt is required.")
    if set(record) != {
        "schema_version",
        "task_id",
        "purpose",
        "engine",
        "approved_distribution",
        "approved_distribution_sha256",
        "approved_descriptor_file_sha256",
        "source",
        "destination",
        "project",
        "created_at",
        "expires_at",
        "status",
    }:
        raise ValueError("Unexpected staging receipt fields are forbidden.")
    if (
        record.get("purpose") != PURPOSE
        or record.get("status") != "ready"
        or not isinstance(record.get("task_id"), str)
        or not _TASK.fullmatch(record["task_id"])
    ):
        raise ValueError("A completed task-owned staging receipt is required.")
    approved = _distribution(record["engine"], record["approved_distribution"])
    if _sha(canonical_json(approved)) != _digest(record["approved_distribution_sha256"]):
        raise ValueError("Approved distribution identity differs from its pinned digest.")
    _digest(record["approved_descriptor_file_sha256"])
    source, target, project = record["source"], record["destination"], record["project"]
    if (
        not isinstance(source, dict)
        or not isinstance(target, dict)
        or not isinstance(project, dict)
        or set(source)
        != {
            "repository",
            "repository_id",
            "release_tag",
            "release_id",
            "asset_id",
            "asset_name",
            "size_bytes",
            "sha256",
            "version",
            "platform",
            "architecture",
        }
        or set(target)
        != {
            "repository",
            "repository_id",
            "owner_id",
            "release_tag",
            "release_id",
            "asset_id",
            "asset_name",
            "size_bytes",
            "sha256",
        }
        or set(project) != {"ref", "source_sha", "workflow_path"}
    ):
        raise ValueError("Staging identity tuples require their exact bounded fields.")
    for field in ("repository_id", "release_id", "asset_id", "size_bytes"):
        _positive_id(source[field])
        _positive_id(target[field])
    _positive_id(target["owner_id"])
    _repository(source["repository"])
    _repository(target["repository"])
    if source["repository"] == target["repository"]:
        raise ValueError("Approved laboratory source and private student destination must differ.")
    for item in (source, target):
        if not _NAME.fullmatch(item["asset_name"]) or not _NAME.fullmatch(item["release_tag"]):
            raise ValueError("Staged release and asset identities must be literal names.")
        _digest(item["sha256"])
    version = approved[f"{record['engine']}_version"]
    if (
        any(
            source[field] != approved[key]
            for field, key in (
                ("repository", "repository"),
                ("release_tag", "release_tag"),
                ("asset_name", "archive_name"),
                ("sha256", "sha256"),
                ("version", f"{record['engine']}_version"),
                ("platform", "platform"),
                ("architecture", "architecture"),
            )
        )
        or not version
    ):
        raise ValueError("Source tuple differs from the independently approved distribution.")
    if any(target[field] != source[field] for field in ("asset_name", "sha256", "size_bytes")):
        raise ValueError("Staged bytes differ from the approved source asset.")
    if target["release_tag"] != f"cochem-private-{record['task_id']}":
        raise ValueError("A staging release must be uniquely owned by this task.")
    if (
        not isinstance(project["source_sha"], str)
        or not _SHA1.fullmatch(project["source_sha"])
        or project["source_sha"] == "0" * 40
        or not isinstance(project["ref"], str)
        or not re.fullmatch(r"refs/heads/[A-Za-z0-9][A-Za-z0-9._/-]*", project["ref"])
        or ".." in project["ref"]
        or not _WORKFLOW.fullmatch(project["workflow_path"])
    ):
        raise ValueError("A pinned project commit, branch and workflow path are required.")
    created, expires = _timestamp(record["created_at"]), _timestamp(record["expires_at"])
    now = _utc_now()
    if created > now or not timedelta(0) < expires - created <= timedelta(hours=24):
        raise ValueError("Receipt lifetime must be genuine, positive and at most 24 hours.")
    if not allow_expired and expires <= now:
        raise PrivateAssetError("The temporary staging receipt has expired.")
    return record


def load_staging_receipt(
    raw_bytes: bytes, expected_sha256: str, *, allow_expired: bool = False
) -> dict[str, Any]:
    if not isinstance(raw_bytes, bytes) or len(raw_bytes) > 256 * 1024:
        raise ValueError("A bounded immutable receipt byte string is required.")
    if _sha(raw_bytes) != _digest(expected_sha256):
        raise ValueError(
            "The private staging receipt differs from its independently retained digest."
        )
    if type(allow_expired) is not bool:
        raise ValueError("Historical expiry handling must be an explicit boolean.")
    record = _receipt_shape(_json(raw_bytes), allow_expired=allow_expired)
    if canonical_json(record) != raw_bytes:
        raise ValueError("Receipt bytes must use the exact canonical JSON representation.")
    return record


def _release_marker(record: dict[str, Any]) -> str:
    return canonical_json(
        {
            "schema_version": "cochem.private-engine-release-marker/1",
            "task_id": record["task_id"],
            "purpose": PURPOSE,
            "repository_id": record["destination"]["repository_id"],
            "owner_id": record["destination"]["owner_id"],
            "source_sha": record["project"]["source_sha"],
            "workflow_path": record["project"]["workflow_path"],
            "approved_distribution_sha256": record["approved_distribution_sha256"],
            "expires_at": record["expires_at"],
        }
    ).decode("utf-8")


def _task_release(record: dict[str, Any]) -> dict[str, Any]:
    target = record["destination"]
    release = _api(f"repos/{target['repository']}/releases/{target['release_id']}")
    if (
        release.get("id") != target["release_id"]
        or release.get("tag_name") != target["release_tag"]
        or release.get("target_commitish") != record["project"]["source_sha"]
        or release.get("body") != _release_marker(record)
        or release.get("draft") is not True
        or release.get("prerelease") is not False
    ):
        raise PrivateAssetError(
            "The provider release differs from this task's exact ownership marker."
        )
    return release


def _asset_identity(asset: dict[str, Any], expected: dict[str, Any]) -> None:
    if (
        any(
            asset.get(name) != expected[key]
            for name, key in (
                ("id", "asset_id"),
                ("name", "asset_name"),
                ("size", "size_bytes"),
            )
        )
        or asset.get("state") != "uploaded"
    ):
        raise PrivateAssetError(
            "Provider asset ID/name/size/state differs from the approved tuple."
        )
    if asset.get("digest") is not None and asset["digest"] != f"sha256:{expected['sha256']}":
        raise PrivateAssetError(
            "Provider asset digest contradicts the approved independent SHA-256."
        )


def _download(repository: str, asset: dict[str, Any], path: Path) -> None:
    path = _private_output(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    process: subprocess.Popen[bytes] | None = None
    try:
        with os.fdopen(fd, "wb") as stream:
            executable = shutil.which("gh")
            if executable is None:
                raise PrivateAssetError("The actual authenticated GitHub CLI is required.")
            process = subprocess.Popen(
                [
                    executable,
                    "api",
                    "--hostname",
                    "github.com",
                    "--method",
                    "GET",
                    "-H",
                    "Accept: application/octet-stream",
                    "-H",
                    "X-GitHub-Api-Version: 2022-11-28",
                    f"repos/{_repository(repository)}/releases/assets/{_positive_id(asset['asset_id'])}",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=_gh_environment(),
                start_new_session=True,
            )
            if process.stdout is None:
                raise PrivateAssetError("The native authenticated transfer has no byte stream.")
            import time

            deadline = time.monotonic() + 1800
            received = 0
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise PrivateAssetError(
                            "Authenticated asset transfer exceeded its time budget."
                        )
                    if not selector.select(min(1.0, remaining)):
                        continue
                    block = os.read(process.stdout.fileno(), 1024 * 1024)
                    if not block:
                        break
                    received += len(block)
                    if received > _positive_id(asset["size_bytes"]):
                        raise PrivateAssetError(
                            "Native download exceeded the approved exact byte count."
                        )
                    stream.write(block)
            process.stdout.close()
            if process.wait(timeout=max(0.001, deadline - time.monotonic())):
                raise PrivateAssetError("Authenticated native asset download failed.")
            stream.flush()
            os.fsync(stream.fileno())
        if _file_sha(path) != (asset["sha256"], asset["size_bytes"]):
            raise PrivateAssetError(
                "Authenticated asset bytes failed exact independent SHA/size readback."
            )
    except BaseException:
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        path.unlink(missing_ok=True)
        raise


def _upload(repository: str, release_id: int, name: str, path: Path) -> dict[str, Any]:
    # gh api --input opens *os.File and leaves Request.GetBody=nil. Unlike
    # gh release upload, 307/308 cannot replay these archive bytes to a new host.
    endpoint = (
        f"https://uploads.github.com/repos/{_repository(repository)}/releases/"
        f"{_positive_id(release_id)}/assets?name={quote(name, safe='')}"
    )
    raw = _gh(
        [
            "api",
            "--hostname",
            "github.com",
            "--method",
            "POST",
            "--include",
            "-H",
            "Content-Type: application/octet-stream",
            "-H",
            "X-GitHub-Api-Version: 2022-11-28",
            endpoint,
            "--input",
            str(path),
        ],
        seconds=1800,
    )
    header, separator, body = raw.partition(b"\r\n\r\n")
    if not separator:
        header, separator, body = raw.partition(b"\n\n")
    status = header.splitlines()[0].split() if header else []
    if not separator or len(status) < 2 or status[1] != b"201":
        raise PrivateAssetError(
            "The exact upload did not return an actual HTTP 201 asset creation."
        )
    value = _json(body)
    if not isinstance(value, dict):
        raise PrivateAssetError("The provider returned no exact uploaded-asset identity.")
    return value


def _journal(path: Path, record: dict[str, Any], status: str, **updates: Any) -> None:
    record.update(updates)
    record["operational_status"] = status
    record.setdefault("history", []).append({"status": status, "at": _iso(_utc_now())})
    _write_private(path, canonical_json(record))


def stage_private_asset(
    *,
    engine: str,
    descriptor: Path,
    descriptor_sha256: str,
    repository: str,
    ref: str,
    source_sha: str,
    workflow_path: str,
    receipt: Path,
    expires_hours: int = 6,
) -> dict[str, Any]:
    _codespaces()
    receipt = _private_output(receipt)
    journal_path = _private_output(Path(str(receipt) + ".journal.json"))
    if receipt.exists() or journal_path.exists():
        raise FileExistsError("A staging task's receipt/journal cannot be overwritten.")
    if type(expires_hours) is not int or not 1 <= expires_hours <= 24:
        raise ValueError("Temporary staging lifetime must be 1 through 24 hours.")
    raw_descriptor = _safe_path(descriptor).read_bytes()
    if _sha(raw_descriptor) != _digest(descriptor_sha256):
        raise ValueError("The private descriptor differs from its reviewed file digest.")
    distribution = _distribution(engine, _json(raw_descriptor))
    project = _personal_private(_repository(repository), owner=True)
    source_repo = _repo_record(distribution["repository"])
    if source_repo.get("private") is not True or source_repo["owner"].get("type") != "Organization":
        raise PrivateAssetError(
            "The approved source must be an accessible laboratory private repository."
        )
    if not _SHA1.fullmatch(source_sha) or source_sha == "0" * 40:
        raise ValueError("Supply the actual student's committed calculation/workflow SHA.")
    if not re.fullmatch(r"refs/heads/[A-Za-z0-9][A-Za-z0-9._/-]*", ref) or ".." in ref:
        raise ValueError("Supply an exact safe heads ref.")
    if not _WORKFLOW.fullmatch(workflow_path):
        raise ValueError("Supply the exact .github/workflows YAML path.")
    actual_ref = _api(f"repos/{repository}/git/ref/{ref[5:]}")
    if actual_ref.get("ref") != ref or actual_ref.get("object", {}).get("sha") != source_sha:
        raise PrivateAssetError(
            "The requested private project ref no longer matches its committed SHA."
        )
    workflow = _api(f"repos/{repository}/contents/{workflow_path}?ref={source_sha}")
    if workflow.get("type") != "file" or workflow.get("path") != workflow_path:
        raise PrivateAssetError("The exact project commit has no requested workflow file.")
    source_release = _api(
        f"repos/{distribution['repository']}/releases/tags/{quote(distribution['release_tag'], safe='')}"
    )
    if source_release.get("tag_name") != distribution["release_tag"]:
        raise PrivateAssetError("The approved source release identity changed.")
    matches = [
        asset
        for asset in source_release.get("assets", [])
        if asset.get("name") == distribution["archive_name"]
    ]
    if len(matches) != 1:
        raise PrivateAssetError(
            "The approved source must contain exactly one literal named archive."
        )
    asset = matches[0]
    created = _utc_now()
    task = uuid.uuid4().hex
    record = {
        "schema_version": SCHEMA,
        "task_id": task,
        "purpose": PURPOSE,
        "engine": engine,
        "approved_distribution": distribution,
        "approved_distribution_sha256": _sha(canonical_json(distribution)),
        "approved_descriptor_file_sha256": descriptor_sha256,
        "source": {
            "repository": distribution["repository"],
            "repository_id": source_repo["id"],
            "release_tag": distribution["release_tag"],
            "release_id": _positive_id(source_release["id"]),
            "asset_id": _positive_id(asset["id"]),
            "asset_name": distribution["archive_name"],
            "size_bytes": _positive_id(asset["size"]),
            "sha256": distribution["sha256"],
            "version": distribution[f"{engine}_version"],
            "platform": distribution["platform"],
            "architecture": distribution["architecture"],
        },
        "destination": {
            "repository": repository,
            "repository_id": project["id"],
            "owner_id": project["owner"]["id"],
            "release_tag": f"cochem-private-{task}",
            "release_id": None,
            "asset_id": None,
            "asset_name": distribution["archive_name"],
            "size_bytes": asset["size"],
            "sha256": distribution["sha256"],
        },
        "project": {"ref": ref, "source_sha": source_sha, "workflow_path": workflow_path},
        "created_at": _iso(created),
        "expires_at": _iso(created + timedelta(hours=expires_hours)),
        "status": "preparing",
    }
    _asset_identity(asset, record["source"])
    journal = {"receipt": record, "history": []}
    _write_private(journal_path, canonical_json(journal), exclusive=True)
    try:
        with tempfile.TemporaryDirectory(prefix="cochem-private-engine-") as directory:
            archive = Path(directory) / distribution["archive_name"]
            _journal(journal_path, journal, "downloading_approved_source")
            _download(distribution["repository"], record["source"], archive)
            current = _personal_private(repository, owner=True)
            if current["id"] != project["id"] or current["owner"]["id"] != project["owner"]["id"]:
                raise PrivateAssetError("Private project identity changed before staging.")
            _journal(journal_path, journal, "creating_task_owned_release")
            release = _api(
                f"repos/{repository}/releases",
                method="POST",
                body={
                    "tag_name": record["destination"]["release_tag"],
                    "target_commitish": source_sha,
                    "name": f"CoChem temporary private engine {task}",
                    "body": _release_marker(record),
                    "draft": True,
                    "prerelease": False,
                },
            )
            record["destination"]["release_id"] = _positive_id(release["id"])
            _journal(journal_path, journal, "uploading_task_owned_asset")
            _task_release(record)
            before = _file_sha(archive)
            if before != (distribution["sha256"], asset["size"]):
                raise PrivateAssetError("Approved source bytes changed before upload.")
            uploaded = _upload(repository, release["id"], distribution["archive_name"], archive)
            record["destination"]["asset_id"] = _positive_id(uploaded["id"])
            _journal(journal_path, journal, "verifying_authenticated_readback")
            _asset_identity(uploaded, record["destination"])
            if _file_sha(archive) != before:
                raise PrivateAssetError("Local approved source changed while uploading.")
            readback = Path(directory) / "authenticated-readback.bin"
            _download(repository, record["destination"], readback)
            _personal_private(repository, owner=True)
            _task_release(record)
            record["status"] = "ready"
            _receipt_shape(record)
            raw = canonical_json(record)
            _write_private(receipt, raw, exclusive=True)
            _journal(journal_path, journal, "ready", ready_receipt_sha256=_sha(raw))
            return {
                "receipt_path": str(receipt),
                "receipt_sha256": _sha(raw),
                "task_id": task,
                "status": "ready",
            }
    except BaseException:
        _journal(journal_path, journal, "interrupted_retained_for_repair")
        raise


def validate_actions_context(receipt: dict[str, Any]) -> dict[str, Any]:
    receipt = _receipt_shape(receipt)
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise PrivateAssetError(
            "Staged-asset consumption requires the owning GitHub Actions worker."
        )
    target, project = receipt["destination"], receipt["project"]
    if any(
        os.environ.get(variable) != expected
        for variable, expected in (
            ("GITHUB_REPOSITORY", target["repository"]),
            ("GITHUB_REPOSITORY_ID", str(target["repository_id"])),
            ("GITHUB_REPOSITORY_OWNER_ID", str(target["owner_id"])),
            ("GITHUB_SHA", project["source_sha"]),
            ("GITHUB_REF", project["ref"]),
            (
                "GITHUB_WORKFLOW_REF",
                f"{target['repository']}/{project['workflow_path']}@{project['ref']}",
            ),
        )
    ):
        raise PrivateAssetError(
            "Actions repository/ref/commit/workflow identity differs from the receipt."
        )
    actual = _personal_private(target["repository"], owner=False)
    if actual["id"] != target["repository_id"] or actual["owner"]["id"] != target["owner_id"]:
        raise PrivateAssetError("Live private repository identity differs from the receipt.")
    release = _task_release(receipt)
    assets = release.get("assets", [])
    if len(assets) != 1:
        raise PrivateAssetError("The task-owned release has unrecognized or shared assets.")
    _asset_identity(assets[0], target)
    return actual


def consume_staged_asset(receipt: dict[str, Any], *, destination: Path) -> dict[str, Any]:
    validate_actions_context(receipt)
    _download(receipt["destination"]["repository"], receipt["destination"], destination)
    try:
        validate_actions_context(receipt)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return {
        "archive_path": str(destination),
        "sha256": receipt["destination"]["sha256"],
        "size_bytes": receipt["destination"]["size_bytes"],
    }


def _matches_run(run: dict[str, Any], receipt: dict[str, Any]) -> bool:
    return (
        run.get("head_sha") == receipt["project"]["source_sha"]
        and str(run.get("path", "")).split("@", 1)[0] == receipt["project"]["workflow_path"]
        and receipt["task_id"]
        in re.findall(r"(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])", str(run.get("display_title", "")))
    )


def cleanup_staged_asset(*, receipt_path: Path, receipt_sha256: str, run_id: int) -> dict[str, Any]:
    _codespaces()
    raw = _safe_path(receipt_path).read_bytes()
    if _sha(raw) != _digest(receipt_sha256):
        raise ValueError("The retained ready receipt digest changed.")
    record = _receipt_shape(_json(raw), allow_expired=True)
    if canonical_json(record) != raw:
        raise ValueError("The immutable ready receipt must remain canonical.")
    target = record["destination"]
    current = _personal_private(target["repository"], owner=True)
    if current["id"] != target["repository_id"] or current["owner"]["id"] != target["owner_id"]:
        raise PrivateAssetError("Cleanup repository identity changed.")
    run = _api(f"repos/{target['repository']}/actions/runs/{_positive_id(run_id)}")
    if not _matches_run(run, record) or run.get("status") != "completed":
        raise PrivateAssetError(
            "Cleanup requires this exact task's actual completed/cancelled Actions run."
        )
    for page in range(1, 11):
        runs = _api(
            f"repos/{target['repository']}/actions/runs?head_sha={record['project']['source_sha']}&per_page=100&page={page}"
        )
        if (
            not isinstance(runs, dict)
            or type(runs.get("total_count")) is not int
            or runs["total_count"] < 0
            or not isinstance(runs.get("workflow_runs"), list)
        ):
            raise PrivateAssetError("The provider did not return a complete actual run inventory.")
        if runs["total_count"] > 1000:
            raise PrivateAssetError(
                "Run inventory exceeds the bounded lifecycle audit; retain assets."
            )
        entries = runs["workflow_runs"]
        if any(
            _matches_run(item, record) and item.get("status") != "completed" for item in entries
        ):
            raise PrivateAssetError("A matching task run is still active; retain private assets.")
        if len(entries) < 100:
            break
    release = _task_release(record)
    if len(release.get("assets", [])) != 1:
        raise PrivateAssetError("Cleanup refuses a release with unrecognized or shared assets.")
    _asset_identity(release["assets"][0], target)
    journal_path = Path(str(receipt_path) + ".journal.json")
    journal = _json(_safe_path(journal_path).read_bytes())
    if journal.get("receipt") != record:
        raise PrivateAssetError("Lifecycle journal no longer describes the exact owned receipt.")
    _journal(journal_path, journal, "deleting_completed_task_release", completed_run_id=run_id)
    _api(f"repos/{target['repository']}/releases/{target['release_id']}", method="DELETE")
    _journal(journal_path, journal, "cleaned", completed_run_id=run_id)
    return {
        "status": "cleaned",
        "task_id": record["task_id"],
        "release_id": target["release_id"],
        "run_id": run_id,
    }


def repair_staging(*, receipt_path: Path) -> dict[str, Any]:
    _codespaces()
    journal_path = _private_output(Path(str(receipt_path) + ".journal.json"))
    journal = _json(_safe_path(journal_path).read_bytes())
    record = journal["receipt"]
    if record.get("schema_version") != SCHEMA or not _TASK.fullmatch(record.get("task_id", "")):
        raise ValueError("A genuine retained staging intent is required.")
    target = record["destination"]
    current = _personal_private(target["repository"], owner=True)
    if current["id"] != target["repository_id"] or current["owner"]["id"] != target["owner_id"]:
        raise PrivateAssetError("Repair repository identity changed.")
    approved = _distribution(record["engine"], record["approved_distribution"])
    if _sha(canonical_json(approved)) != record["approved_distribution_sha256"]:
        raise ValueError("The retained approved distribution changed.")
    if target.get("release_id") is None:
        # A crash can occur after provider creation but before its response is
        # journaled. Discover only the exact unguessable task tag and marker.
        matches = []
        for page in range(1, 11):
            releases = _api(f"repos/{target['repository']}/releases?per_page=100&page={page}")
            if not isinstance(releases, list):
                raise PrivateAssetError("The provider did not return a complete release inventory.")
            matches.extend(
                item
                for item in releases
                if item.get("tag_name") == target["release_tag"]
                and item.get("body") == _release_marker(record)
            )
            if len(releases) < 100:
                break
        else:
            raise PrivateAssetError("Release inventory exceeds repair budget; retain the intent.")
        if len(matches) != 1:
            raise PrivateAssetError(
                "No unique owned release found; intent is retained without deleting anything."
            )
        target["release_id"] = _positive_id(matches[0]["id"])
    release = _task_release(record)
    matches = [
        item for item in release.get("assets", []) if item.get("name") == target["asset_name"]
    ]
    if len(matches) != 1 or len(release.get("assets", [])) != 1:
        _journal(journal_path, journal, "incomplete_owned_release_retained")
        raise PrivateAssetError(
            "Owned upload is incomplete or contains unknown assets; retain for explicit review."
        )
    target["asset_id"] = _positive_id(matches[0]["id"])
    _asset_identity(matches[0], target)
    with tempfile.TemporaryDirectory(prefix="cochem-private-repair-") as directory:
        _download(target["repository"], target, Path(directory) / "readback.bin")
    record["status"] = "ready"
    _receipt_shape(record)
    raw = canonical_json(record)
    if receipt_path.exists():
        if receipt_path.read_bytes() != raw:
            raise PrivateAssetError("Repair refuses to overwrite a different ready receipt.")
    else:
        _write_private(receipt_path, raw, exclusive=True)
    _journal(journal_path, journal, "ready_repaired", ready_receipt_sha256=_sha(raw))
    return {
        "status": "ready",
        "receipt_path": str(receipt_path),
        "receipt_sha256": _sha(raw),
        "task_id": record["task_id"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    stage = commands.add_parser("stage")
    stage.add_argument("--engine", choices=("orca", "cfour"), required=True)
    stage.add_argument("--descriptor", type=Path, required=True)
    stage.add_argument("--descriptor-sha256", required=True)
    stage.add_argument("--repository", required=True)
    stage.add_argument("--ref", required=True)
    stage.add_argument("--source-sha", required=True)
    stage.add_argument("--workflow-path", required=True)
    stage.add_argument("--receipt", type=Path, required=True)
    stage.add_argument("--expires-hours", type=int, default=6)
    consume = commands.add_parser("consume")
    consume.add_argument("--receipt", type=Path, required=True)
    consume.add_argument("--receipt-sha256", required=True)
    consume.add_argument("--archive", type=Path, required=True)
    cleanup = commands.add_parser("cleanup")
    cleanup.add_argument("--receipt", type=Path, required=True)
    cleanup.add_argument("--receipt-sha256", required=True)
    cleanup.add_argument("--run-id", type=int, required=True)
    repair = commands.add_parser("repair")
    repair.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "stage":
            result = stage_private_asset(
                engine=args.engine,
                descriptor=args.descriptor,
                descriptor_sha256=args.descriptor_sha256,
                repository=args.repository,
                ref=args.ref,
                source_sha=args.source_sha,
                workflow_path=args.workflow_path,
                receipt=args.receipt,
                expires_hours=args.expires_hours,
            )
        elif args.command == "consume":
            receipt = load_staging_receipt(
                _safe_path(args.receipt).read_bytes(), args.receipt_sha256
            )
            result = consume_staged_asset(receipt, destination=args.archive)
        elif args.command == "cleanup":
            result = cleanup_staged_asset(
                receipt_path=args.receipt, receipt_sha256=args.receipt_sha256, run_id=args.run_id
            )
        else:
            result = repair_staging(receipt_path=args.receipt)
        print(canonical_json(result).decode("utf-8"))
        return 0
    except (PrivateAssetError, ValueError, OSError, KeyError) as exc:
        # Errors name the failed boundary, never credentials/provider responses.
        print(f"Private asset operation failed: {exc}", file=__import__("sys").stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
