"""Real filesystem controls for immutable source-origin receipt publication.

These controls implement the proposal's atomic I/O invariant (§3.4) and Task 1
S5 state serialization (§3.5), independently checked under S6 (§3.6). They do
not provide chemistry, hosted runner, or student deployment acceptance.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import signal
import stat
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from ci_tools import source_quarantine
from ci_tools.base_ci import _source_origin_receipts


@pytest.fixture
def receipt_control(tmp_path):
    owner = tmp_path / "cochem-atomic-source-receipts"
    owner.mkdir(mode=0o700)
    evidence = owner / "published"
    evidence.mkdir(mode=0o700)
    source = Path(source_quarantine.__file__).resolve().parents[1]
    original_value = os.environ.get("COCHEM_SOURCE_QUARANTINE_ORIGINAL")
    original = Path(original_value).resolve() if original_value else owner / "original"
    if original_value is None:
        original.mkdir(mode=0o700)
    revision = os.environ.get("COCHEM_SOURCE_QUARANTINE_REVISION")
    if revision is None:
        revision = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            check=True, timeout=15,
        ).stdout.strip()
    assert len(revision) == 40 and all(character in "0123456789abcdef" for character in revision)
    state = {
        "copied": source,
        "original": original,
        "evidence": evidence,
        "revision": revision,
        "instance": uuid.uuid4().hex,
        "retired_roots": set(),
    }
    return owner, state


def _result():
    return {
        "passed": True,
        "origins": {"ci_tools.source_quarantine": [str(Path(source_quarantine.__file__).resolve())]},
        "removed_editables": {},
    }


def _destination(state, stage="initial", *, pid=None):
    actual_pid = os.getpid() if pid is None else pid
    return state["evidence"] / f"{actual_pid}-{state['instance']}-{stage}.json"


def _outside_files(owner, evidence):
    return {
        path.relative_to(owner): path
        for path in owner.rglob("*")
        if path.is_file() and not path.is_symlink() and not path.is_relative_to(evidence)
    }


def _retained_staging(owner, evidence, before):
    files = _outside_files(owner, evidence)
    retained = [files[relative] for relative in files.keys() - before.keys()]
    assert len(retained) == 1, sorted(str(path) for path in retained)
    path = retained[0]
    assert path.name == "record.json"
    assert path.parent.parent == owner
    assert path.parent.name.startswith(".cochem-source-receipt-")
    assert path.stat().st_dev == evidence.stat().st_dev
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    return path


def test_complete_source_receipt_is_private_and_parser_valid(receipt_control):
    owner, state = receipt_control
    before = _outside_files(owner, state["evidence"])
    result = _result()
    result["diagnostic_text"] = "Complete UTF-8 source observation: Δ and isotope ¹³C"
    source_quarantine._receipt(state, "initial", result)
    destination = _destination(state)
    raw = destination.read_bytes()
    assert raw.endswith(b"\n")
    record = json.loads(raw)
    assert record == {
        "schema_version": 1,
        "pid": os.getpid(),
        "parent_pid": os.getppid(),
        "interpreter": sys.executable,
        "stage": "initial",
        "source_root": str(state["copied"]),
        "original_root": str(state["original"]),
        "source_revision": state["revision"],
        "startup_source_sha256": hashlib.sha256(Path(source_quarantine.__file__).read_bytes()).hexdigest(),
        "retired_source_roots": [],
        **result,
    }
    assert list(state["evidence"].iterdir()) == [destination]
    assert _outside_files(owner, state["evidence"]) == before
    assert not any(path.name.startswith(".cochem-source-receipt-") for path in owner.iterdir())
    if os.name == "posix":
        assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    observations = _source_origin_receipts(
        state["evidence"], state["copied"], state["original"], state["revision"])
    assert not observations["authority_errors"] and not observations["failed"]
    assert len(observations["records"]) == 1
    assert observations["startup_only"] == [{
        "pid": os.getpid(), "instance": state["instance"],
        "scope": "startup-only-no-finalizer-observation",
    }]


@pytest.mark.parametrize("kind", ["regular", "directory"])
def test_existing_source_receipt_is_never_replaced(receipt_control, kind):
    owner, state = receipt_control
    destination = _destination(state)
    if kind == "regular":
        source_quarantine._receipt(state, "initial", _result())
        original = destination.read_bytes()
        original_stat = destination.stat()
    else:
        destination.mkdir(mode=0o700)
        original_stat = destination.stat()
    before = _outside_files(owner, state["evidence"])
    attempted = {**_result(), "publication_attempt": "Must not replace prior filesystem authority"}
    with pytest.raises(OSError):
        source_quarantine._receipt(state, "initial", attempted)
    assert destination.stat().st_ino == original_stat.st_ino
    if kind == "regular":
        assert destination.read_bytes() == original
    else:
        assert destination.is_dir() and not list(destination.iterdir())
    staged = _retained_staging(owner, state["evidence"], before)
    assert json.loads(staged.read_bytes())["publication_attempt"] == attempted["publication_attempt"]
    observations = _source_origin_receipts(
        state["evidence"], state["copied"], state["original"], state["revision"])
    if kind == "regular":
        assert len(observations["records"]) == 1 and not observations["authority_errors"]
        assert "publication_attempt" not in observations["records"][0]
    else:
        assert not observations["records"]
        assert len(observations["authority_errors"]) == 1
        assert observations["authority_errors"][0]["file"] == destination.name


def test_existing_link_cannot_redirect_source_receipt(receipt_control):
    owner, state = receipt_control
    target = owner / "existing-target.json"
    original = b"Immutable native filesystem target\n"
    target.write_bytes(original)
    destination = _destination(state)
    link_kind = "symlink"
    capability_error = None
    try:
        destination.symlink_to(target)
    except OSError as error:
        assert os.name == "nt"
        assert error.errno in {errno.EACCES, errno.EPERM} or getattr(error, "winerror", None) == 1314
        capability_error = {"errno": error.errno, "winerror": getattr(error, "winerror", None)}
        os.link(target, destination)
        link_kind = "hardlink-native-symlink-privilege-unavailable"
    original_target_stat = target.stat()
    original_link_stat = destination.lstat()
    before = _outside_files(owner, state["evidence"])
    with pytest.raises(OSError):
        source_quarantine._receipt(state, "initial", _result())
    assert target.read_bytes() == original and destination.read_bytes() == original
    assert target.stat().st_ino == original_target_stat.st_ino
    assert destination.lstat().st_ino == original_link_stat.st_ino
    if link_kind == "symlink":
        assert destination.is_symlink() and destination.resolve() == target.resolve()
    staged = _retained_staging(owner, state["evidence"], before)
    assert json.loads(staged.read_bytes())["passed"] is True
    (owner / "native-link-control.json").write_text(json.dumps({
        "link_kind": link_kind,
        "native_symlink_capability_error": capability_error,
        "original_target_sha256": hashlib.sha256(original).hexdigest(),
        "staging_path": str(staged),
    }, indent=2) + "\n", encoding="utf-8")


def test_strict_reader_rejects_genuinely_truncated_final_bytes(receipt_control):
    owner, state = receipt_control
    source_quarantine._receipt(state, "initial", _result())
    destination = _destination(state)
    original = destination.read_bytes()
    (owner / "complete-control-baseline.json").write_bytes(original)
    with destination.open("r+b") as handle:
        handle.truncate(len(original) // 2)
        handle.flush()
        os.fsync(handle.fileno())
    truncated = destination.read_bytes()
    assert truncated == original[:len(original) // 2]
    with pytest.raises(json.JSONDecodeError):
        json.loads(truncated)
    observations = _source_origin_receipts(
        state["evidence"], state["copied"], state["original"], state["revision"])
    assert not observations["records"] and not observations["startup_only"]
    assert len(observations["authority_errors"]) == 1
    assert observations["authority_errors"][0]["file"] == destination.name
    assert destination.read_bytes() == truncated


INITIAL_FAILURE_CHILD = r'''
import json, os, pathlib, sys
source = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(source))
from ci_tools import source_quarantine
owner = pathlib.Path(sys.argv[2])
marker = owner / "application-payload-ran"
print(json.dumps({"pid": os.getpid(), "mode": sys.argv[3]}), flush=True)
try:
    if sys.argv[3] in {"native-file-size-limit", "native-file-size-interruption"}:
        import resource, signal
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_FSIZE, (128, 128))
        disposition = signal.SIG_DFL if sys.argv[3] == "native-file-size-interruption" else signal.SIG_IGN
        signal.signal(signal.SIGXFSZ, disposition)
        source_quarantine.activate_from_environment()
    else:
        state = {
            "copied": source,
            "original": pathlib.Path(os.environ["COCHEM_SOURCE_QUARANTINE_ORIGINAL"]),
            "evidence": pathlib.Path(os.environ["COCHEM_SOURCE_QUARANTINE_EVIDENCE"]),
            "revision": os.environ["COCHEM_SOURCE_QUARANTINE_REVISION"],
            "instance": sys.argv[4],
            "retired_roots": set(),
        }
        source_quarantine._receipt(state, "initial", {
            "passed": True,
            "origins": {"ci_tools.source_quarantine": [source_quarantine.__file__]},
            "zz_unencodable_diagnostic": {"Actual unsupported JSON value"},
        })
except (OSError, TypeError) as error:
    print(json.dumps({"error_type": type(error).__name__, "errno": getattr(error, "errno", None)}), flush=True)
    raise
marker.write_text("Application body continued after initial receipt publication\n", encoding="utf-8")
'''


@pytest.mark.parametrize("failure", ["serialization", "native-write", "native-interruption"])
def test_failed_initial_publication_never_exposes_partial_or_runs_body(receipt_control, failure):
    owner, state = receipt_control
    # Windows has no resource.RLIMIT_FSIZE. Its native no-replace collision and
    # link controls above remain mandatory; this branch runs a genuine writer
    # serialization failure and records that file-limit coverage is unavailable.
    modes = {"native-write": "native-file-size-limit", "native-interruption": "native-file-size-interruption"}
    mode = modes[failure] if failure in modes and os.name == "posix" else "serialization"
    environment = dict(os.environ)
    environment.update({
        "COCHEM_SOURCE_QUARANTINE_ROOT": str(state["copied"]),
        "COCHEM_SOURCE_QUARANTINE_ORIGINAL": str(state["original"]),
        "COCHEM_SOURCE_QUARANTINE_EVIDENCE": str(state["evidence"]),
        "COCHEM_SOURCE_QUARANTINE_REVISION": state["revision"],
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    before = _outside_files(owner, state["evidence"])
    process = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", INITIAL_FAILURE_CHILD,
         str(state["copied"]), str(owner), mode, state["instance"]],
        cwd=state["copied"], env=environment,
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        check=False, timeout=30,
    )
    assert process.returncode != 0, process.stdout
    child_lines = process.stdout.splitlines()
    assert len(child_lines) == (1 if mode == "native-file-size-interruption" else 2), process.stdout
    child = json.loads(child_lines[0])
    native_error = None if mode == "native-file-size-interruption" else json.loads(child_lines[1])
    assert child["pid"] > 0 and child["pid"] != os.getpid() and child["mode"] == mode
    assert not (owner / "application-payload-ran").exists()
    assert not list(state["evidence"].iterdir())
    staged = _retained_staging(owner, state["evidence"], before)
    partial = staged.read_bytes()
    assert partial
    with pytest.raises(json.JSONDecodeError):
        json.loads(partial)
    if mode in {"native-file-size-limit", "native-file-size-interruption"}:
        assert len(partial) == 128
        if mode == "native-file-size-interruption":
            assert process.returncode == -signal.SIGXFSZ
        else:
            assert native_error == {"error_type": "OSError", "errno": errno.EFBIG}
    else:
        assert native_error == {"error_type": "TypeError", "errno": None}
    observations = _source_origin_receipts(
        state["evidence"], state["copied"], state["original"], state["revision"])
    assert not observations["records"] and not observations["authority_errors"]
    # Save real native outcomes beside retained staging, outside the authority
    # directory. No malformed record is admitted, deleted or relabeled valid.
    (owner / "initial-publication-failure.json").write_text(json.dumps({
        "requested_control": failure,
        "executed_control": mode,
        "posix_file_limit_available": os.name == "posix",
        "child_pid": child["pid"],
        "child_exit_code": process.returncode,
        "native_error": native_error,
        "stdout": process.stdout,
        "stderr": process.stderr,
        "retained_staging_path": str(staged),
        "retained_staging_sha256": hashlib.sha256(partial).hexdigest(),
        "retained_staging_bytes": len(partial),
        "application_body_observed": False,
    }, indent=2) + "\n", encoding="utf-8")
