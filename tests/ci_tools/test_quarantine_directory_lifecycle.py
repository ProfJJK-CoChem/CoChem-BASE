"""Native directory retirement controls for proposal §3.5 and Task 1 S6.

Windows controls hold real CreateFileW handles without FILE_SHARE_DELETE.
POSIX controls observe its different open-directory deletion semantics. These
filesystem checks provide neither chemical nor student deployment acceptance.
"""

from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
import stat
import subprocess
import threading
import time
from ctypes import wintypes
from pathlib import Path

import pytest

from ci_tools.zero_trust_runner import QuarantineEnvironment, _CLEANUP_TIMEOUT_S


REPOSITORY = Path(__file__).resolve().parents[2]


class NativeDirectoryHandle:
    """Own one actual native handle; no production routine is replaced."""

    def __init__(self, directory):
        self.directory = directory
        self.lock = threading.Lock()
        self.closed = False
        self.closed_at = None
        self.close_error = None
        if os.name == "nt":
            self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            self.kernel.CreateFileW.argtypes = [
                wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
            ]
            self.kernel.CreateFileW.restype = wintypes.HANDLE
            self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            self.kernel.CloseHandle.restype = wintypes.BOOL
            self.kernel.GetHandleInformation.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            self.kernel.GetHandleInformation.restype = wintypes.BOOL
            # GENERIC_READ; share READ|WRITE, deliberately exclude DELETE;
            # OPEN_EXISTING; FILE_FLAG_BACKUP_SEMANTICS opens a directory.
            self.handle = self.kernel.CreateFileW(str(directory), 0x80000000, 0x3, None, 3, 0x02000000, None)
            if self.handle == ctypes.c_void_p(-1).value:
                raise ctypes.WinError(ctypes.get_last_error())
        else:
            self.handle = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))

    def observation(self):
        with self.lock:
            assert not self.closed
            if os.name == "nt":
                flags = wintypes.DWORD()
                if not self.kernel.GetHandleInformation(self.handle, ctypes.byref(flags)):
                    raise ctypes.WinError(ctypes.get_last_error())
                return {"mechanism": "CreateFileW", "share_delete": False, "handle_flags": flags.value}
            info = os.fstat(self.handle)
            assert stat.S_ISDIR(info.st_mode)
            return {
                "mechanism": "os.open-directory", "device": info.st_dev,
                "inode": info.st_ino, "link_count": info.st_nlink,
            }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.close()

    def close(self):
        with self.lock:
            if self.closed:
                return
            try:
                if os.name == "nt":
                    if not self.kernel.CloseHandle(self.handle):
                        raise ctypes.WinError(ctypes.get_last_error())
                else:
                    os.close(self.handle)
            except OSError as error:
                self.close_error = error
                raise
            self.closed = True
            self.closed_at = time.monotonic()


@pytest.fixture
def directory_control(tmp_path):
    owner = tmp_path / "cochem-native-directory-lifecycle"
    owner.mkdir(mode=0o700)
    foreign = owner / "foreign-directory"
    foreign.mkdir(mode=0o700)
    sentinel = foreign / "foreign-input.txt"
    sentinel.write_bytes(b"Foreign native filesystem input must remain unchanged.\n")
    quarantine = QuarantineEnvironment(base_dir=owner, prefix="owned-directory-")
    quarantine.__enter__()
    assert not quarantine._active_processes
    return owner, quarantine, sentinel


def _file_snapshot(path):
    info = path.stat()
    return {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "device": info.st_dev, "inode": info.st_ino,
        "mode": info.st_mode, "size": info.st_size, "mtime_ns": info.st_mtime_ns,
    }


def _publish_control(owner, control, details):
    receipt = {"schema_version": 1, "control": control, "native_os": os.name, **details}
    payload = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (owner / "native-directory-control.json").write_bytes(payload)
    supplied = os.environ.get("COCHEM_CI_CONTROL_EVIDENCE_DIR")
    if supplied:
        destination = Path(supplied)
        if (not destination.is_absolute() or destination.is_symlink() or not destination.is_dir()
                or destination.resolve() != destination.absolute()
                or destination.resolve().is_relative_to(REPOSITORY)):
            raise ValueError("Directory controls require an existing external evidence directory")
        target = destination / ("directory-control-" + hashlib.sha256(payload).hexdigest() + ".json")
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(descriptor, "wb") as output:
            output.write(payload)


def _directory_link(link, target):
    try:
        link.symlink_to(target, target_is_directory=True)
        return {"kind": "symlink", "native_symlink_error": None}
    except OSError as error:
        assert os.name == "nt"
        assert error.errno in {errno.EACCES, errno.EPERM} or getattr(error, "winerror", None) == 1314
        result = subprocess.run(
            ["cmd", "/d", "/c", "mklink", "/J", str(link), str(target)],
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            check=False, timeout=10,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert getattr(link.lstat(), "st_file_attributes", 0) & 0x400
        assert link.resolve() == target.resolve()
        return {
            "kind": "junction-native-symlink-privilege-unavailable",
            "native_symlink_error": {"errno": error.errno, "winerror": getattr(error, "winerror", None)},
        }


def test_actual_directory_handle_release_allows_owned_retirement(directory_control):
    owner, quarantine, sentinel = directory_control
    root = quarantine.quarantine_dir
    foreign_before = _file_snapshot(sentinel)
    with NativeDirectoryHandle(root) as handle:
        before = handle.observation()
        if os.name == "nt":
            with pytest.raises(PermissionError) as observed:
                os.rmdir(root)
            assert observed.value.winerror == 32
            assert root.is_dir() and not list(root.iterdir())
            probe_outcome = {"native_rmdir": "sharing-violation", "winerror": 32}
        else:
            # POSIX permits rmdir of an open directory. Use a separate actual
            # probe so the owned root exercises the real helper below as well.
            probe = owner / "posix-open-directory-probe"
            probe.mkdir(mode=0o700)
            with NativeDirectoryHandle(probe) as probe_handle:
                original_probe = probe_handle.observation()
                os.rmdir(probe)
                assert not probe.exists()
                probe_observation = probe_handle.observation()
                assert probe_observation["inode"] == original_probe["inode"]
                probe_outcome = {"native_rmdir": "open-directory-removal-permitted", **probe_observation}
        started = time.monotonic()
        release = threading.Timer(0.05, handle.close)
        release.start()
        try:
            quarantine._remove_owned_directory()
            finished = time.monotonic()
            assert not root.exists()
        finally:
            release.join(timeout=1)
            handle.close()
        assert not release.is_alive() and handle.close_error is None
    assert _file_snapshot(sentinel) == foreign_before
    _publish_control(owner, "directory-handle-release", {
        "handle_before": before, "native_probe": probe_outcome,
        "scheduled_release_delay_s": 0.05,
        "observed_release_elapsed_s": handle.closed_at - started,
        "retirement_elapsed_s": finished - started,
        "owned_root_removed": True, "foreign_file_unchanged": True,
        "windows_sharing_violation_observed": os.name == "nt",
    })


def test_persistent_directory_handle_keeps_native_failure_visible(directory_control):
    owner, quarantine, sentinel = directory_control
    root = quarantine.quarantine_dir
    identity = (root.stat().st_dev, root.stat().st_ino)
    foreign_before = _file_snapshot(sentinel)
    handle = NativeDirectoryHandle(root)
    started = time.monotonic()
    try:
        if os.name == "nt":
            with pytest.raises(PermissionError) as observed:
                quarantine._remove_owned_directory()
            elapsed = time.monotonic() - started
            assert observed.value.winerror == 32
            assert elapsed >= _CLEANUP_TIMEOUT_S
            assert elapsed < _CLEANUP_TIMEOUT_S + 2
            assert root.is_dir() and not list(root.iterdir())
            assert (root.stat().st_dev, root.stat().st_ino) == identity
            outcome = {"retirement": "visible-sharing-violation", "winerror": 32, "owned_root_retained": True}
        else:
            quarantine._remove_owned_directory()
            elapsed = time.monotonic() - started
            assert not root.exists()
            assert (handle.observation()["device"], handle.observation()["inode"]) == identity
            outcome = {"retirement": "open-directory-removal-permitted", "owned_root_retained": False}
        assert _file_snapshot(sentinel) == foreign_before
        live_handle = handle.observation()
    finally:
        handle.close()
    # A Windows failure's empty owned root is deliberately retained even after
    # handle release, together with the actual outcome for the gate archive.
    if os.name == "nt":
        assert root.is_dir()
    _publish_control(owner, "persistent-directory-handle", {
        **outcome, "elapsed_s": elapsed, "cleanup_budget_s": _CLEANUP_TIMEOUT_S,
        "handle_before_release": live_handle, "foreign_file_unchanged": True,
        "windows_sharing_violation_observed": os.name == "nt",
    })


@pytest.mark.parametrize("boundary", ["regular-file", "directory-link"])
def test_changed_owned_root_refuses_without_touching_foreign_input(directory_control, boundary):
    owner, quarantine, sentinel = directory_control
    root = quarantine.quarantine_dir
    foreign_before = _file_snapshot(sentinel)
    if boundary == "regular-file":
        os.rmdir(root)
        original = b"A real regular file replaced the test-owned directory boundary.\n"
        root.write_bytes(original)
        link = None
    else:
        retained_owned = owner / "retained-original-owned-directory"
        root.rename(retained_owned)
        link = _directory_link(root, sentinel.parent)
        assert root.resolve() == sentinel.parent.resolve()
    with pytest.raises(PermissionError, match="source boundary changed"):
        quarantine._remove_owned_directory()
    assert _file_snapshot(sentinel) == foreign_before
    if boundary == "regular-file":
        assert root.read_bytes() == original
    else:
        assert root.resolve() == sentinel.parent.resolve()
        assert retained_owned.is_dir() and not list(retained_owned.iterdir())
    _publish_control(owner, "changed-owned-root-" + boundary, {
        "boundary": boundary, "native_directory_link": link,
        "refusal_visible": True, "foreign_file_unchanged": True,
    })


def test_owned_cleanup_unlinks_foreign_directory_alias_without_following_it(directory_control):
    owner, quarantine, sentinel = directory_control
    foreign_before = _file_snapshot(sentinel)
    directory_before = sentinel.parent.stat()
    root = quarantine.quarantine_dir
    alias = root / "foreign-directory-alias"
    link = _directory_link(alias, sentinel.parent)
    assert alias.resolve() == sentinel.parent.resolve()
    quarantine._remove_owned_directory()
    assert not root.exists()
    assert sentinel.parent.is_dir()
    directory_after = sentinel.parent.stat()
    assert (directory_after.st_dev, directory_after.st_ino, directory_after.st_mode, directory_after.st_mtime_ns) == (
        directory_before.st_dev, directory_before.st_ino, directory_before.st_mode, directory_before.st_mtime_ns)
    assert _file_snapshot(sentinel) == foreign_before
    _publish_control(owner, "foreign-directory-alias", {
        "native_directory_link": link, "owned_root_removed": True,
        "foreign_directory_unchanged": True, "foreign_file_unchanged": True,
    })
