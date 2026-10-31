"""Bounded GitHub Git-data admission transport; never force or edit source refs.

The local expected-parent engineering backend is deliberately separate. GitHub's
nonforce update is checked by fresh parent/readback; hosted behavior still needs
genuine service qualification. A failed write acknowledgement is never retried.
"""
from __future__ import annotations

import base64
from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import importlib.util
import math
import os
from pathlib import Path
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


def _contract():
    if __package__:
        from . import student_actions_admission
        return student_actions_admission
    spec = importlib.util.spec_from_file_location(
        "cochem_source_admission", Path(__file__).with_name("student_actions_admission.py"))
    if spec is None or spec.loader is None:
        raise ImportError("The source-local admission contract is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


contract = _contract()
MAX_RESPONSE = 4 * 1024 * 1024
MEMBERS = {"request.json", "intent.json", "state.json", "binding.json"}


MAX_CACHE_COMMITS = 256
MAX_CACHE_PAYLOAD_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class _CachedGitCommit:
    parent: str | None
    tree: str
    members: tuple[tuple[str, str], ...]
    metadata_bytes: int


class ImmutableGitObjects:
    """Session-owned verified Git objects, never current state or authorization.

    FIFO eviction is deterministic and does not move entries on reads. Raw blobs
    are deduplicated within a repository and retained only while an admitted
    commit references them. The byte budget counts immutable payload bytes and
    canonical commit/tree metadata, not Python allocator overhead or process RSS.
    """
    def __init__(self):
        self._lock = threading.RLock()
        self._commits = OrderedDict()
        self._blobs = {}
        self._references = {}
        self._payload_bytes = 0

    def statistics(self):
        with self._lock:
            return {"commits": len(self._commits), "blobs": len(self._blobs),
                    "payload_bytes": self._payload_bytes,
                    "maximum_commits": MAX_CACHE_COMMITS, "maximum_payload_bytes": MAX_CACHE_PAYLOAD_BYTES}

    def files(self, repository, commit):
        with self._lock:
            value = self._commits.get((repository, commit))
            if value is None:
                return None
            return ({name: self._blobs[(repository, sha)] for name, sha in value.members}, value.parent)

    def blob(self, repository, sha):
        with self._lock:
            return self._blobs.get((repository, sha))

    def _evict_oldest(self):
        (repository, unused_commit), value = self._commits.popitem(last=False)
        self._payload_bytes -= value.metadata_bytes
        for unused_name, sha in value.members:
            key = (repository, sha)
            self._references[key] -= 1
            if self._references[key] == 0:
                self._payload_bytes -= len(self._blobs.pop(key))
                del self._references[key]

    def admit(self, repository, commit, parent, tree, files):
        """Called only after complete commit/tree/blob verification by the adapter."""
        members = tuple((name, contract.blob_id(raw)) for name, raw in sorted(files.items()))
        metadata = len(contract.canonical({"commit": commit, "parent": parent, "tree": tree,
                                           "members": [list(item) for item in members]}))
        entry = _CachedGitCommit(parent, tree, members, metadata)
        unique = {(repository, sha): files[name] for name, sha in members}
        with self._lock:
            previous = self._commits.get((repository, commit))
            if previous is not None:
                if previous != entry or any(self._blobs[key] != raw for key, raw in unique.items()):
                    raise contract.AdmissionError("An immutable Git object changed within this session")
                return
            if metadata + sum(len(raw) for raw in unique.values()) > MAX_CACHE_PAYLOAD_BYTES:
                return  # A verified object can be read without becoming cache-resident.
            while self._commits:
                needed = metadata + sum(len(raw) for key, raw in unique.items() if key not in self._blobs)
                if (len(self._commits) < MAX_CACHE_COMMITS
                        and self._payload_bytes + needed <= MAX_CACHE_PAYLOAD_BYTES):
                    break
                self._evict_oldest()
            for key, raw in unique.items():
                if not isinstance(raw, bytes):
                    raise contract.AdmissionError("Only immutable verified Git bytes may be cached")
                if key not in self._blobs:
                    self._blobs[key] = raw
                    self._references[key] = 0
                    self._payload_bytes += len(raw)
                elif self._blobs[key] != raw:
                    raise contract.AdmissionError("A verified blob identity changed")
            for unused_name, sha in members:
                self._references[(repository, sha)] += 1
            self._commits[(repository, commit)] = entry
            self._payload_bytes += metadata


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


class ReadOnlyAPI:
    """Workflow metadata access under one inherited deadline.

    Per-open socket timeout is capped to remaining time, and completed reads are
    refused after the deadline. This is not a hard wall-clock interrupt for a
    trickling socket; the existing outer GitHub job timeout remains authoritative.
    """
    def __init__(self, token, *, deadline, api_url="https://api.github.com", allow_loopback=False):
        parsed = urllib.parse.urlsplit(api_url)
        local = (allow_loopback and parsed.scheme == "http"
                 and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
                 and not parsed.username and not parsed.password and not parsed.path
                 and not parsed.query and not parsed.fragment)
        if api_url != "https://api.github.com" and not local:
            raise contract.AdmissionError("Admission requires the verified GitHub API")
        if (not isinstance(token, str) or not token or type(deadline) not in (int, float)
                or not math.isfinite(deadline)):
            raise contract.AdmissionError("Read-only admission identity or deadline is missing")
        self.token, self.deadline, self.api_url = token, deadline, api_url
        self.opener = urllib.request.build_opener(_NoRedirect())
        self._admission_immutable_objects = ImmutableGitObjects()

    def _request(self, path, *, method="GET", body=None, **unused):
        if method != "GET" or body is not None:
            raise contract.AdmissionError("The workflow cannot write admission state")
        remaining = self.deadline - time.time()
        if remaining <= 0 or not path.startswith("/") or path.startswith("//"):
            raise contract.AdmissionError("Admission metadata budget or path is invalid")
        request = urllib.request.Request(self.api_url + path, headers={
            "Authorization": "Bearer " + self.token,
            "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "CoChem-BASE-admission"})
        try:
            with self.opener.open(request, timeout=min(30, remaining)) as response:
                raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise ValueError("Oversized metadata")
            value = contract.request_contract.strict_json(raw)
            if time.time() >= self.deadline:
                raise contract.AdmissionError("The inherited admission metadata budget expired")
            return value
        except urllib.error.HTTPError as error:
            failure = contract.TransportError("Read-only GitHub metadata was refused")
            failure.http_status = error.code
            raise failure from None
        except (urllib.error.URLError, OSError, ValueError, UnicodeError) as error:
            raise contract.TransportError("Read-only admission metadata could not be verified") from error


def _sha(value):
    if not isinstance(value, str) or not contract.HEX40.fullmatch(value):
        raise contract.AdmissionError("GitHub did not return an exact Git object identity")
    return value


def _call(api, path, *, method="GET", body=None):
    try:
        value = api._request(path, method=method, body=body)
        if not isinstance(value, dict):
            raise contract.TransportError("Invalid GitHub metadata acknowledgement", uncertain=method != "GET")
        return value
    except contract.AdmissionError:
        raise
    except (RuntimeError, OSError, ValueError) as error:
        failure = contract.TransportError("GitHub admission metadata request failed",
            uncertain=getattr(error, "uncertain", method != "GET"))
        failure.http_status = getattr(error, "http_status", None)
        raise failure from error


def content(api, repository, path, revision):
    """Read one bounded file at an exact commit, checking the actual blob ID."""
    _sha(revision)
    value = _call(api, f"/repos/{repository}/contents/{urllib.parse.quote(path, safe='/')}?ref={revision}")
    try:
        raw = base64.b64decode("".join(value["content"].split()), validate=True)
        if (value.get("type") != "file" or value.get("path") != path
                or value.get("encoding") != "base64" or len(raw) > MAX_RESPONSE
                or type(value.get("size")) is not int or value["size"] != len(raw)
                or value.get("sha") != contract.blob_id(raw)):
            raise ValueError("File identity mismatch")
        return raw
    except (KeyError, ValueError, TypeError, AttributeError) as error:
        raise contract.AdmissionError("The protected source file could not be verified") from error


def qualify_capability(api, *, canonical_repository, worker_sha, repository, source_sha, setup_hint=None):
    """The approved canonical descriptor is authority; project/setup only corroborate."""
    raw = content(api, canonical_repository, contract.DESCRIPTOR_PATH, worker_sha)
    descriptor = contract.parse_descriptor(raw)
    for path, expected in sorted(descriptor["required_files"].items()):
        for project, revision in ((canonical_repository, worker_sha), (repository, source_sha)):
            if contract.digest(content(api, project, path, revision)) != expected:
                raise contract.AdmissionError("This project's calculation workflow needs an instructor update")
    if content(api, repository, contract.DESCRIPTOR_PATH, source_sha) != raw:
        raise contract.AdmissionError("The project admission descriptor differs from approved BASE")
    hint = {"protocol": contract.PROTOCOL, "descriptor_sha256": contract.digest(raw),
            "ledger_ref": contract.LEDGER_REF}
    if setup_hint is not None and contract.canonical(setup_hint) != contract.canonical(hint):
        raise contract.AdmissionError("The setup check does not corroborate approved admission source")
    return hint


class GitAdmissionBackend:
    """Append only to the fixed data-only orphan ref; all members are verified."""
    def __init__(self, api, repository, *, read_only=False):
        if not isinstance(repository, str) or not contract.REPO.fullmatch(repository):
            raise contract.AdmissionError("Invalid admission project")
        self.api, self.repository, self.read_only = api, repository, read_only
        self.seen_tip = None
        self.cache = getattr(api, '_admission_immutable_objects', None)
        if not isinstance(self.cache, ImmutableGitObjects):
            raise contract.AdmissionError('Admission requires an authenticated session-owned object cache')
        self.base = f"/repos/{repository}/git"

    def tip(self):
        try:
            value = _call(self.api, self.base + "/ref/heads/cochem-student-admission-v1")
        except contract.TransportError as error:
            if getattr(error, "http_status", None) == 404 and self.seen_tip is None:
                return None
            raise
        if value.get("ref") != contract.LEDGER_REF or value.get("object", {}).get("type") != "commit":
            raise contract.AdmissionError("The admission ref is not the protected data ref")
        tip = _sha(value["object"].get("sha"))
        if self.seen_tip is not None and tip != self.seen_tip:
            current = tip
            for unused in range(contract.MAX_HISTORY):
                if current == self.seen_tip:
                    break
                unused_files, current = self.files(current)
                if current is None:
                    raise contract.AdmissionError("The observed admission history was replaced or rewound")
            else:
                raise contract.AdmissionError("Admission ancestry exceeds the reviewed bound")
        self.seen_tip = tip
        return tip

    def files(self, commit):
        _sha(commit)
        cached = self.cache.files(self.repository, commit)
        if cached is not None:
            return cached
        value = _call(self.api, self.base + "/commits/" + commit)
        parents = value.get("parents")
        if value.get("sha") != commit or not isinstance(parents, list) or len(parents) > 1:
            raise contract.AdmissionError("Admission commits require exact single-parent ancestry")
        parent = _sha(parents[0].get("sha")) if parents else None
        tree_sha = _sha(value.get("tree", {}).get("sha"))
        tree = _call(self.api, self.base + "/trees/" + tree_sha)
        entries = tree.get("tree")
        if tree.get("sha") != tree_sha or tree.get("truncated") is not False or not isinstance(entries, list):
            raise contract.AdmissionError("Admission tree is incomplete")
        files = {}
        for entry in entries:
            name = entry.get("path")
            if name not in MEMBERS or name in files or entry.get("mode") != "100644" or entry.get("type") != "blob":
                raise contract.AdmissionError("Admission contains a non-data, duplicate or redirected member")
            sha = _sha(entry.get("sha"))
            raw = self.cache.blob(self.repository, sha)
            if raw is None:
                blob = _call(self.api, self.base + "/blobs/" + sha)
                try:
                    raw = base64.b64decode("".join(blob["content"].split()), validate=True)
                    if (blob.get("encoding") != "base64" or len(raw) > contract.MAX_TRANSPORT
                            or type(blob.get("size")) is not int or blob["size"] != len(raw)
                            or blob.get("sha") != sha or contract.blob_id(raw) != sha):
                        raise ValueError("Blob identity mismatch")
                except (KeyError, ValueError, TypeError, AttributeError) as error:
                    raise contract.AdmissionError("Admission blob identity is invalid") from error
            files[name] = raw
        if set(files) not in ({"request.json", "intent.json", "state.json"}, MEMBERS):
            raise contract.AdmissionError("Admission lacks its immutable data records")
        encoded = b"".join(b"100644 " + name.encode() + b"\0" + bytes.fromhex(contract.blob_id(raw))
                           for name, raw in sorted(files.items()))
        actual_tree = hashlib.sha1(b"tree " + str(len(encoded)).encode() + b"\0" + encoded).hexdigest()
        if actual_tree != tree_sha:
            raise contract.AdmissionError("Admission tree object ID differs")
        self.cache.admit(self.repository, commit, parent, tree_sha, files)
        return dict(files), parent

    def commit(self, files, parent):
        if self.read_only:
            raise contract.AdmissionError("Workflow admission is read-only")
        if set(files) not in ({"request.json", "intent.json", "state.json"}, MEMBERS):
            raise contract.AdmissionError("Only exact admission data members may be written")
        entries = []
        for name, raw in sorted(files.items()):
            value = _call(self.api, self.base + "/blobs", method="POST",
                          body={"content": base64.b64encode(raw).decode(), "encoding": "base64"})
            if value.get("sha") != contract.blob_id(raw):
                raise contract.TransportError("Git blob write acknowledgement differs", uncertain=True)
            entries.append({"path": name, "mode": "100644", "type": "blob", "sha": value["sha"]})
        tree = _call(self.api, self.base + "/trees", method="POST", body={"tree": entries})
        tree_sha = _sha(tree.get("sha"))
        value = _call(self.api, self.base + "/commits", method="POST", body={
            "message": "CoChem data-only research admission", "tree": tree_sha,
            "parents": [parent] if parent is not None else []})
        commit = _sha(value.get("sha"))
        actual_files, actual_parent = self.files(commit)
        if actual_files != files or actual_parent != parent:
            raise contract.TransportError("Git commit readback differs", uncertain=True)
        return commit

    def advance(self, commit, parent):
        if self.read_only:
            raise contract.AdmissionError("Workflow admission is read-only")
        if self.tip() != parent:
            raise contract.Conflict("Another request changed the admission ref")
        unused_files, actual_parent = self.files(commit)
        if actual_parent != parent:
            raise contract.AdmissionError("The proposed transition has another parent")
        try:
            if parent is None:
                value = _call(self.api, self.base + "/refs", method="POST",
                              body={"ref": contract.LEDGER_REF, "sha": commit})
            else:
                value = _call(self.api, self.base + "/refs/heads/cochem-student-admission-v1", method="PATCH",
                              body={"sha": commit, "force": False})
        except contract.TransportError as error:
            if getattr(error, "http_status", None) in {409, 422}:
                raise contract.Conflict("The nonforce admission update lost contention") from error
            raise
        if value.get("ref") != contract.LEDGER_REF or value.get("object", {}).get("sha") != commit:
            raise contract.TransportError("The ref write acknowledgement differs", uncertain=True)
        if self.tip() != commit:
            raise contract.Conflict("The admission ref advanced before readback")


class ActionsAdmissionTransport:
    """Actual client request conventions; no new scientific request interpretation."""
    def __init__(self, client):
        self.client = client

    def dispatch(self, snapshot):
        intent = snapshot.intent
        return _call(self.client, f"/repos/{intent['repository']}/actions/workflows/{intent['workflow_id']}/dispatches",
            method="POST", body={"ref": intent["branch"], "inputs": {
                "request_id": intent["request_id"], "request_sha256": intent["payload_sha256"],
                "request_base64": base64.b64encode(snapshot.raw).decode(), "admission_anchor": snapshot.anchor}})

    def discover(self, intent):
        matches, seen, count = [], set(), None
        for page in range(1, 6):
            value = _call(self.client, f"/repos/{intent['repository']}/actions/workflows/{intent['workflow_id']}/runs"
                f"?event=workflow_dispatch&per_page=100&page={page}")
            runs, total = value.get("workflow_runs"), value.get("total_count")
            if (type(total) is not int or total < 0 or not isinstance(runs, list)
                    or len(runs) > 100 or count is not None and total != count):
                raise contract.AdmissionError("Run discovery pagination is incomplete or changed")
            count = total
            for run in runs:
                if not isinstance(run, dict) or not contract.positive(run.get("id")) or run["id"] in seen:
                    raise contract.AdmissionError("Run pagination repeated or omitted an identity")
                seen.add(run["id"])
                if run.get("display_title") == "CoChem student " + intent["request_id"]:
                    matches.append(self.observe(intent, run["id"]))
            if len(seen) > count or len(runs) < 100 and len(seen) != count:
                raise contract.AdmissionError("Run discovery returned a truncated or inconsistent page")
            if len(seen) == count:
                return matches, True
        return matches, False

    def observe(self, intent, run_id):
        if not contract.positive(run_id):
            raise contract.AdmissionError("A real run ID is required")
        return _call(self.client, f"/repos/{intent['repository']}/actions/runs/{run_id}")

    def cancel(self, intent, run_id):
        if not contract.positive(run_id):
            raise contract.AdmissionError("A real run ID is required for Stop")
        return _call(self.client, f"/repos/{intent['repository']}/actions/runs/{run_id}/cancel", method="POST")
