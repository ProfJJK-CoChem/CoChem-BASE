"""# zero-stub anti-spoofing engine
Zero-Trust Quarantine Runner Module (ci_tools/zero_trust_runner.py)

Creates sterile, ephemeral execution directories (/tmp/cochem_exec_<uuid>/ or %TEMP%/cochem_exec_<uuid>)
for isolated execution, tests, and verification. Manages only the process groups
and descendants owned by its commands.

Complies with Method Matrix v4, CoChem Anti-Spoofing Protocol v2, and WBS Task 1.2.2.
"""

from __future__ import annotations

import atexit
import ctypes
import logging
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger("zero_trust_runner")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


@dataclass(frozen=True)
class QuarantineCleanupObservation:
    """Owned work termination and separately observed OS collection custody."""
    launcher_pid: int
    launcher_returncode: Optional[int]
    owned_work_stopped: bool
    ownership_scope: str
    collection_observation: str
    external_reaping_pending: tuple[tuple[int, float], ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "launcher_pid": self.launcher_pid, "launcher_returncode": self.launcher_returncode,
            "owned_work_stopped": self.owned_work_stopped, "ownership_scope": self.ownership_scope,
            "collection_observation": self.collection_observation,
            "external_reaping_pending": [{"pid": pid, "create_time": created}
                                         for pid, created in self.external_reaping_pending],
        }


@dataclass
class QuarantineResult:
    """Result of a command executed within the sterile quarantine environment."""
    exit_code: int
    stdout: str
    stderr: str
    quarantine_dir: str
    duration_s: float
    passed: bool
    timed_out: bool = False
    cleanup_observation: Optional[QuarantineCleanupObservation] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "quarantine_dir": self.quarantine_dir,
            "duration_s": self.duration_s,
            "passed": self.passed,
            "timed_out": self.timed_out,
        }
        if self.cleanup_observation is not None:
            result["cleanup_observation"] = self.cleanup_observation.to_dict()
        return result


_ACTIVE_PROCESSES: set[subprocess.Popen] = set()
_PROCESS_LOCK = threading.RLock()
_LOCK_TIMEOUT_S = 0.25
_CLEANUP_TIMEOUT_S = 3.0


class _IOCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
    )]


class _JobBasicLimits(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
    ]


class _JobExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JobBasicLimits), ("IoInfo", _IOCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryLimit", ctypes.c_size_t), ("PeakJobMemoryLimit", ctypes.c_size_t),
    ]


class _JobAccounting(ctypes.Structure):
    _fields_ = [
        ("TotalUserTime", ctypes.c_int64), ("TotalKernelTime", ctypes.c_int64),
        ("ThisPeriodTotalUserTime", ctypes.c_int64),
        ("ThisPeriodTotalKernelTime", ctypes.c_int64),
        ("TotalPageFaultCount", ctypes.c_uint32),
        ("TotalProcesses", ctypes.c_uint32), ("ActiveProcesses", ctypes.c_uint32),
        ("TotalTerminatedProcesses", ctypes.c_uint32),
    ]


class _WindowsJob:
    """Own a kernel Job before allowing its suspended launcher to execute."""

    def __init__(self) -> None:
        self.handle = None
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.kernel.CreateJobObjectW.restype = wintypes.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
        ]
        self.kernel.SetInformationJobObject.restype = wintypes.BOOL
        self.kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.kernel.AssignProcessToJobObject.restype = wintypes.BOOL
        self.kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.kernel.TerminateJobObject.restype = wintypes.BOOL
        self.kernel.QueryInformationJobObject.argtypes = [
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self.kernel.QueryInformationJobObject.restype = wintypes.BOOL
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        try:
            self.handle = self.kernel.CreateJobObjectW(None, None)
            if not self.handle:
                raise ctypes.WinError(ctypes.get_last_error())
            limits = _JobExtendedLimits()
            limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
            if not self.kernel.SetInformationJobObject(
                self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits),
            ):
                raise ctypes.WinError(ctypes.get_last_error())
        except BaseException:
            try:
                self.close()
            except OSError as error:
                logger.warning("Partial Windows Job cleanup failed: %s", error)
            raise

    def assign_and_resume(self, process: subprocess.Popen) -> None:
        if not self.kernel.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())
        resume = ctypes.WinDLL("ntdll").NtResumeProcess
        resume.argtypes = [wintypes.HANDLE]
        resume.restype = ctypes.c_long
        status = resume(int(process._handle))
        if status != 0:
            raise RuntimeError(f"Windows quarantine launcher resume failed: NTSTATUS {status:#x}")

    def close(self) -> None:
        if self.handle:
            if not self.kernel.CloseHandle(self.handle):
                raise ctypes.WinError(ctypes.get_last_error())
            self.handle = None

    def stop(self, timeout: float) -> bool:
        """Verify zero active Job members before retiring its ownership handle."""
        if not self.handle:
            return True
        if not self.kernel.TerminateJobObject(self.handle, 1):
            raise ctypes.WinError(ctypes.get_last_error())
        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            if self.active_processes() == 0:
                self.close()
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))

    def active_processes(self) -> int:
        if not self.handle:
            return 0
        accounting = _JobAccounting()
        if not self.kernel.QueryInformationJobObject(
            self.handle, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None,
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return accounting.ActiveProcesses


def _windows_directory_security(path: Path, *, enforce: bool) -> dict:
    """Set/check a protected native DACL; POSIX mode bits are not Windows ACLs."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    security = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel.GetCurrentProcess.argtypes = []
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    security.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    security.OpenProcessToken.restype = wintypes.BOOL
    security.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                            wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    security.GetTokenInformation.restype = wintypes.BOOL
    security.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    security.ConvertSidToStringSidW.restype = wintypes.BOOL
    security.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p,
    ]
    security.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL
    security.SetFileSecurityW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p]
    security.SetFileSecurityW.restype = wintypes.BOOL
    security.GetFileSecurityW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p,
                                        wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    security.GetFileSecurityW.restype = wintypes.BOOL
    security.GetSecurityDescriptorControl.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.WORD),
                                                      ctypes.POINTER(wintypes.DWORD)]
    security.GetSecurityDescriptorControl.restype = wintypes.BOOL
    security.GetSecurityDescriptorDacl.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.BOOL),
        ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.BOOL)]
    security.GetSecurityDescriptorDacl.restype = wintypes.BOOL
    security.GetAclInformation.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.c_int]
    security.GetAclInformation.restype = wintypes.BOOL
    security.GetAce.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p)]
    security.GetAce.restype = wintypes.BOOL

    def sid_text(sid: int) -> str:
        text = wintypes.LPWSTR()
        if not security.ConvertSidToStringSidW(sid, ctypes.byref(text)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return text.value
        finally:
            if kernel.LocalFree(ctypes.cast(text, ctypes.c_void_p)):
                raise ctypes.WinError(ctypes.get_last_error())

    token = wintypes.HANDLE()
    if not security.OpenProcessToken(kernel.GetCurrentProcess(), 0x0008, ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        size = wintypes.DWORD()
        security.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
        if not size.value:
            raise ctypes.WinError(ctypes.get_last_error())
        user = ctypes.create_string_buffer(size.value)
        if not security.GetTokenInformation(token, 1, user, size, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        current_sid = sid_text(ctypes.cast(user, ctypes.POINTER(ctypes.c_void_p)).contents.value)
    finally:
        if not kernel.CloseHandle(token):
            raise ctypes.WinError(ctypes.get_last_error())
    allowed = {current_sid, "S-1-5-18", "S-1-5-32-544"}
    if enforce:
        descriptor = ctypes.c_void_p()
        sddl = "D:P" + "".join(f"(A;OICI;FA;;;{sid})" for sid in sorted(allowed))
        if not security.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, ctypes.byref(descriptor), None):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not security.SetFileSecurityW(str(path), 0x80000004, descriptor):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            if kernel.LocalFree(descriptor):
                raise ctypes.WinError(ctypes.get_last_error())
    size = wintypes.DWORD()
    security.GetFileSecurityW(str(path), 4, None, 0, ctypes.byref(size))
    if not size.value:
        raise ctypes.WinError(ctypes.get_last_error())
    actual = ctypes.create_string_buffer(size.value)
    if not security.GetFileSecurityW(str(path), 4, actual, size, ctypes.byref(size)):
        raise ctypes.WinError(ctypes.get_last_error())
    control, revision = wintypes.WORD(), wintypes.DWORD()
    if not security.GetSecurityDescriptorControl(actual, ctypes.byref(control), ctypes.byref(revision)):
        raise ctypes.WinError(ctypes.get_last_error())
    present, defaulted, acl = wintypes.BOOL(), wintypes.BOOL(), ctypes.c_void_p()
    if not security.GetSecurityDescriptorDacl(actual, ctypes.byref(present), ctypes.byref(acl), ctypes.byref(defaulted)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not control.value & 0x1000 or not present.value or not acl.value:
        raise PermissionError("Windows quarantine root does not have a protected, explicit DACL")
    counts = (wintypes.DWORD * 3)()
    if not security.GetAclInformation(acl, counts, ctypes.sizeof(counts), 2):
        raise ctypes.WinError(ctypes.get_last_error())
    principals = set()
    for index in range(counts[0]):
        ace = ctypes.c_void_p()
        if not security.GetAce(acl, index, ctypes.byref(ace)):
            raise ctypes.WinError(ctypes.get_last_error())
        header = (ctypes.c_ubyte * 4).from_address(ace.value)
        mask = ctypes.c_uint32.from_address(ace.value + 4).value
        if header[0] != 0 or header[1] != 3 or mask != 0x001F01FF:
            raise PermissionError("Unexpected access entry on Windows quarantine root")
        principals.add(sid_text(ace.value + 8))
    if principals != allowed or counts[0] != len(allowed):
        raise PermissionError("Unexpected principal access on Windows quarantine root")
    return {"protected_dacl": True, "allowed_principal_count": len(allowed)}


@dataclass
class _ProcessOwner:
    """Launch-time ownership, retained even after communicate reaps the leader."""

    owns_posix_group: bool
    leader: Any = None
    descendants: tuple = ()
    windows_job: Optional[_WindowsJob] = None
    external_reaping_pending: tuple = ()


_PROCESS_OWNERS: Dict[subprocess.Popen, _ProcessOwner] = {}


def _enable_owned_descendant_reaping() -> None:
    """Allow Linux to adopt orphaned workers at launch time, never on import."""
    if sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(36, 1, 0, 0, 0) != 0:
            logger.warning("Cannot adopt owned descendants (errno %s)", ctypes.get_errno())


def _capture_process_owner(
    process: subprocess.Popen, owns_group: bool, windows_job: Optional[_WindowsJob] = None,
) -> _ProcessOwner:
    owner = _ProcessOwner(owns_group, windows_job=windows_job)
    if psutil is not None:
        try:
            owner.leader = psutil.Process(process.pid)
            owner.leader.create_time()  # Cache the actual launch generation.
            owner.descendants = tuple(owner.leader.children(recursive=True))
        except psutil.NoSuchProcess:
            logger.debug("Launcher %s exited before process discovery", process.pid)
    return owner


def _register_process(process: subprocess.Popen, owner: _ProcessOwner) -> None:
    if not _PROCESS_LOCK.acquire(timeout=_LOCK_TIMEOUT_S):
        raise RuntimeError("Quarantine process registration exceeded its lock deadline")
    try:
        _ACTIVE_PROCESSES.add(process)
        _PROCESS_OWNERS[process] = owner
    finally:
        _PROCESS_LOCK.release()


def _unregister_process(process: subprocess.Popen) -> None:
    if not _PROCESS_LOCK.acquire(timeout=_LOCK_TIMEOUT_S):
        # Its launch identity remains available for a later bounded retry.
        return
    try:
        _ACTIVE_PROCESSES.discard(process)
        _PROCESS_OWNERS.pop(process, None)
    finally:
        _PROCESS_LOCK.release()


def _reap_owned_group(group_id: int) -> None:
    """Collect only adopted zombies in this command's dedicated group."""
    if not sys.platform.startswith("linux") or psutil is None:
        return
    for child in psutil.Process().children():
        try:
            if os.getpgid(child.pid) == group_id and child.status() == psutil.STATUS_ZOMBIE:
                os.waitpid(child.pid, os.WNOHANG)
        except (ChildProcessError, ProcessLookupError, PermissionError,
                psutil.NoSuchProcess, psutil.AccessDenied):
            continue


def _stop_owned_process(
    process: subprocess.Popen, owner: _ProcessOwner, timeout: float = _CLEANUP_TIMEOUT_S,
) -> bool:
    """Boundedly stop owned work; Popen alone collects its launcher's status."""
    deadline = time.monotonic() + max(0.0, timeout)
    if owner.windows_job is not None:
        # Checked Job assignment happened before resume. If setup failed before
        # assignment, the launcher is still suspended and cannot have workers.
        if not owner.windows_job.stop(max(0.0, deadline - time.monotonic())):
            return False
        if process.poll() is None:
            try:
                process.terminate()
            except ProcessLookupError:
                logger.debug("Owned suspended Windows launcher already exited")
        try:
            process.wait(timeout=max(0.001, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            return False
        return True
    descendants = list(owner.descendants)
    leader_present = False
    if psutil is not None:
        try:
            current = psutil.Process(process.pid)
            if owner.leader is None:
                if process.returncode is not None:
                    return False
                owner.leader = current
                owner.leader.create_time()
            if (owner.leader.pid != process.pid
                    or current.create_time() != owner.leader.create_time()):
                logger.warning("Refusing changed launcher generation PID %s", process.pid)
                return False
            leader_present = True
            descendants.extend(owner.leader.children(recursive=True))
        except psutil.NoSuchProcess:
            if owner.leader is None and owner.owns_posix_group:
                return False
        except psutil.AccessDenied:
            logger.warning("Cannot verify owned launcher PID %s", process.pid)
            return False
    descendants = list(dict.fromkeys(descendants))
    owner.descendants = tuple(descendants)
    owns_group = owner.owns_posix_group and os.name != "nt" and process.pid != os.getpgrp()

    if owns_group:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            logger.debug("Owned group %s unavailable for TERM", process.pid)
    if os.name == "nt" and (leader_present or psutil is None and process.poll() is None):
        # CREATE_NEW_PROCESS_GROUP does not contain a Windows process tree.
        # Taskkill is scoped to this still-verified launcher, never a bare exited PID.
        try:
            taskkill = subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                capture_output=True, check=False,
                timeout=max(0.001, deadline - time.monotonic()),
            )
            if taskkill.returncode != 0:
                logger.warning("Owned Windows tree cleanup failed: %s", taskkill.stderr)
        except (OSError, subprocess.TimeoutExpired) as error:
            logger.warning("Owned Windows tree cleanup failed: %s", error)
    for child in descendants:
        try:
            child.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if process.poll() is None:
        try:
            process.terminate()
            process.wait(timeout=min(0.25, max(0.001, deadline - time.monotonic())))
        except (ProcessLookupError, subprocess.TimeoutExpired):
            logger.debug("Owned launcher %s needs forced cleanup", process.pid)
    if owns_group:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            logger.debug("Owned group %s unavailable for KILL", process.pid)
    for child in descendants:
        try:
            child.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if process.poll() is None:
        try:
            process.kill()
        except ProcessLookupError:
            logger.debug("Owned launcher %s already exited", process.pid)
    try:
        process.wait(timeout=max(0.001, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        return False
    if descendants:
        same_generation = []
        for child in descendants:
            try:
                if child.is_running():
                    same_generation.append(child)
            except psutil.NoSuchProcess:
                continue
            except psutil.AccessDenied:
                return False
        _, alive = psutil.wait_procs(same_generation, timeout=max(0.0, deadline - time.monotonic()))
        if alive:
            if sys.platform.startswith("linux"):
                return False
            terminal = dict(owner.external_reaping_pending)
            for child in alive:
                try:
                    if not child.is_running():
                        continue
                    if child.status() != psutil.STATUS_ZOMBIE:
                        return False
                    created = child.create_time()
                    if not child.is_running():
                        continue
                    terminal[child.pid] = created
                except psutil.NoSuchProcess:
                    continue
                except psutil.AccessDenied:
                    return False
            owner.external_reaping_pending = tuple(sorted(terminal.items()))
            if terminal:
                logger.info("Owned descendants terminated; system reaper owns terminal PIDs %s", terminal)
    if owns_group:
        while True:
            _reap_owned_group(process.pid)
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                break
            except PermissionError:
                return False
            if psutil is not None and not sys.platform.startswith("linux"):
                members, current_terminal = set(), set()
                terminal = dict(owner.external_reaping_pending)
                for member in psutil.process_iter(["pid"]):
                    try:
                        if member.pid <= 0 or os.getpgid(member.pid) != process.pid:
                            continue
                        current = psutil.Process(member.pid)
                        created = current.create_time()
                        if os.getpgid(current.pid) != process.pid:
                            continue
                        status = current.status()
                        if not current.is_running():
                            if psutil.pid_exists(current.pid):
                                return False
                            continue
                        if os.getpgid(current.pid) != process.pid:
                            return False
                        identity = (current.pid, created)
                        members.add(identity)
                        if status == psutil.STATUS_ZOMBIE:
                            terminal[current.pid] = created
                            current_terminal.add(identity)
                    except (ProcessLookupError, psutil.NoSuchProcess):
                        continue
                    except (PermissionError, psutil.AccessDenied):
                        return False
                if members and members == current_terminal:
                    owner.external_reaping_pending = tuple(sorted(terminal.items()))
                    logger.info("Owned workers terminated; system reaper owns terminal PIDs %s", terminal)
                    break
            if time.monotonic() >= deadline:
                return False
            time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
    elif os.name == "nt" and not leader_present:
        # An exited Windows launcher provides no group boundary or complete
        # descendant discovery. Do not certify unobserved orphan cleanup.
        return False
    return process.poll() is not None


def sweep_zombie_processes(processes: Optional[Sequence[subprocess.Popen]] = None) -> int:
    """Stop only explicitly owned quarantine commands and their descendants.

    Libraries and callers may own other children of this interpreter. A process
    tree scan rooted at the interpreter would kill them and steal their statuses.
    """
    if not _PROCESS_LOCK.acquire(timeout=_LOCK_TIMEOUT_S):
        return 0
    try:
        owned = [(process, _PROCESS_OWNERS.get(process))
                 for process in (_ACTIVE_PROCESSES if processes is None else processes)]
    finally:
        _PROCESS_LOCK.release()
    terminated_count = 0
    deadline = time.monotonic() + _CLEANUP_TIMEOUT_S
    for process, owner in owned:
        was_active = process.poll() is None
        try:
            # Explicit caller handles are allowed, but never infer ownership of
            # the caller's shared POSIX group from an arbitrary Popen PID.
            owner = owner or _capture_process_owner(process, False)
            finished = _stop_owned_process(process, owner, max(0.0, deadline - time.monotonic()))
        except Exception as error:
            finished = False
            logger.warning("Owned command cleanup failed: %s", error)
        if finished:
            terminated_count += int(was_active)
            _unregister_process(process)
        else:
            logger.warning("Retaining incomplete owned command cleanup PID %s", process.pid)
    return terminated_count


# Only explicit handles launched by this module are registered here.
atexit.register(sweep_zombie_processes)


class QuarantineEnvironment:
    """Context manager providing an isolated, ephemeral execution directory."""

    def __init__(
        self,
        base_dir: Optional[Union[str, Path]] = None,
        prefix: str = "cochem_exec_",
        copy_paths: Optional[Sequence[Union[str, Path]]] = None,
        preserve_on_failure: bool = False,
    ) -> None:
        if base_dir:
            self.base_dir = Path(base_dir).resolve()
        else:
            self.base_dir = Path(tempfile.gettempdir()).resolve()

        self.prefix = prefix
        self.copy_paths = [Path(p).resolve() for p in copy_paths] if copy_paths else []
        self.preserve_on_failure = preserve_on_failure
        self.quarantine_id = str(uuid.uuid4())
        self.quarantine_dir = self.base_dir / f"{self.prefix}{self.quarantine_id}"
        self._active_processes: set[subprocess.Popen] = set()
        self._process_owners: Dict[subprocess.Popen, _ProcessOwner] = {}
        self._cleanup_observations: List[QuarantineCleanupObservation] = []

    @property
    def cleanup_observations(self) -> tuple[QuarantineCleanupObservation, ...]:
        return tuple(self._cleanup_observations)

    def _record_cleanup(self, process: subprocess.Popen, owner: _ProcessOwner, finished: bool) -> QuarantineCleanupObservation:
        scope = "windows-job" if owner.windows_job is not None else (
            "posix-group" if owner.owns_posix_group else "explicit-parent-handle")
        collection = ("terminal-workers-awaiting-system-reaper" if owner.external_reaping_pending else
                      ("owned-boundary-empty" if finished else "incomplete"))
        observation = QuarantineCleanupObservation(process.pid, process.returncode, finished, scope,
                                                   collection, tuple(owner.external_reaping_pending))
        self._cleanup_observations.append(observation)
        return observation

    def __enter__(self) -> "QuarantineEnvironment":
        self.quarantine_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
        self._enforce_private_root()
        for src_path in self.copy_paths:
            if src_path.exists():
                dest_path = self.quarantine_dir / src_path.name
                if src_path.is_file():
                    shutil.copy2(src_path, dest_path)
                elif src_path.is_dir():
                    shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
        return self

    def _enforce_private_root(self) -> None:
        """Restore privacy after repository copying may transfer root metadata."""
        if os.name == "posix":
            self.quarantine_dir.chmod(0o700)
            if stat.S_IMODE(self.quarantine_dir.stat().st_mode) != 0o700:
                raise PermissionError(f"Quarantine directory is not private: {self.quarantine_dir}")
        elif os.name == "nt":
            _windows_directory_security(self.quarantine_dir, enforce=True)

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        deadline = time.monotonic() + _CLEANUP_TIMEOUT_S
        for process in list(self._active_processes):
            try:
                finished = _stop_owned_process(
                    process, self._process_owners[process],
                    max(0.0, deadline - time.monotonic()),
                )
            except BaseException as error:
                if exc_val is None and not isinstance(error, Exception):
                    raise
                finished = False
                logger.warning("Quarantine context cleanup failed: %s", error)
            self._record_cleanup(process, self._process_owners[process], finished)
            if finished:
                _unregister_process(process)
                self._active_processes.discard(process)
                self._process_owners.pop(process, None)
        if self._active_processes:
            logger.warning("Preserving quarantine with incomplete owned cleanup: %s", self.quarantine_dir)
        elif exc_type is not None and self.preserve_on_failure:
            logger.warning(f"Preserving failed quarantine directory: {self.quarantine_dir}")
        else:
            shutil.rmtree(self.quarantine_dir, ignore_errors=True)

    def run_command(
        self,
        command: Sequence[str],
        timeout: int = 300,
        env_overrides: Optional[Dict[str, str]] = None,
        *,
        environment: Optional[Dict[str, str]] = None,
    ) -> QuarantineResult:
        """Execute a command strictly inside the quarantine directory."""
        env = (os.environ if environment is None else environment).copy()
        if env_overrides:
            env.update(env_overrides)

        # Explicit caller overrides take precedence over inherited bindings.
        # The CLI sets these to its copied quarantine checkout.
        root_env = env.get("COCHEM_ROOT")
        if (root_env and "PYTHONPATH" not in (env_overrides or {})
                and (environment is None or "PYTHONPATH" not in environment)):
            env["PYTHONPATH"] = str(Path(root_env).resolve())
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        start_time = time.monotonic()
        cleanup_observation = None
        try:
            self._enforce_private_root()
            _enable_owned_descendant_reaping()
            windows_job = _WindowsJob() if os.name == "nt" else None
            launch_options: Dict[str, Any] = {"start_new_session": os.name != "nt"}
            if os.name == "nt":
                # Require the actual Windows flag rather than silently launching
                # inside the caller's console process group.
                launch_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000004
            owner = _ProcessOwner(os.name != "nt", windows_job=windows_job)
            try:
                process = subprocess.Popen(
                    list(command), cwd=str(self.quarantine_dir), env=env,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, encoding="utf-8", errors="strict",
                    **launch_options,
                )
            except BaseException:
                if windows_job is not None:
                    try:
                        windows_job.close()
                    except OSError as cleanup_error:
                        logger.warning("Unlaunched Windows Job cleanup failed: %s", cleanup_error)
                raise
            try:
                self._active_processes.add(process)
                self._process_owners[process] = owner
                owner = _capture_process_owner(process, os.name != "nt", windows_job)
                self._process_owners[process] = owner
                _register_process(process, owner)
                if windows_job is not None:
                    windows_job.assign_and_resume(process)
                stdout, stderr = process.communicate(timeout=timeout)
                result = subprocess.CompletedProcess(list(command), process.returncode, stdout, stderr)
            finally:
                original_exception = sys.exc_info()[1]
                try:
                    finished = _stop_owned_process(process, owner)
                except BaseException as cleanup_error:
                    if original_exception is None and not isinstance(cleanup_error, Exception):
                        raise
                    finished = False
                    logger.warning("Owned command cleanup failed: %s", cleanup_error)
                cleanup_observation = self._record_cleanup(process, owner, finished)
                if finished:
                    _unregister_process(process)
                    self._active_processes.discard(process)
                    self._process_owners.pop(process, None)
                if process.stdout is not None:
                    process.stdout.close()
                if process.stderr is not None:
                    process.stderr.close()
                if not finished:
                    message = f"Owned command cleanup incomplete for PID {process.pid}"
                    if original_exception is None:
                        raise RuntimeError(message)
                    logger.warning("%s; preserving %s", message, type(original_exception).__name__)
            duration = time.monotonic() - start_time
            passed = (result.returncode == 0)
            return QuarantineResult(
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                quarantine_dir=str(self.quarantine_dir),
                duration_s=round(duration, 4),
                passed=passed,
                timed_out=False,
                cleanup_observation=cleanup_observation,
            )
        except subprocess.TimeoutExpired as e:
            duration = time.monotonic() - start_time
            logger.error(f"Quarantine command timed out after {timeout} seconds: {e}")
            return QuarantineResult(
                exit_code=124,
                stdout=e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or ""),
                stderr=e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or f"TimeoutExpired: {e}"),
                quarantine_dir=str(self.quarantine_dir),
                duration_s=round(duration, 4),
                passed=False,
                timed_out=True,
                cleanup_observation=cleanup_observation,
            )
        except Exception as e:
            duration = time.monotonic() - start_time
            logger.error(f"Quarantine execution failed with error: {e}")
            return QuarantineResult(
                exit_code=1,
                stdout="",
                stderr=str(e),
                quarantine_dir=str(self.quarantine_dir),
                duration_s=round(duration, 4),
                passed=False,
                timed_out=False,
                cleanup_observation=cleanup_observation,
            )


def run_in_quarantine(
    command: Sequence[str],
    timeout: int = 300,
    env_overrides: Optional[Dict[str, str]] = None,
    copy_paths: Optional[Sequence[Union[str, Path]]] = None,
) -> QuarantineResult:
    """Convenience function to run a command inside a fresh quarantine directory."""
    with QuarantineEnvironment(copy_paths=copy_paths) as qe:
        return qe.run_command(command, timeout=timeout, env_overrides=env_overrides)


def main() -> int:
    import argparse
    import hashlib
    import json

    parser = argparse.ArgumentParser(description="Zero-Trust Quarantine Runner")
    parser.add_argument("--nonce", type=str, help="Cryptographic nonce for ExecutionReceipt", default="UNKNOWN_NONCE")
    parser.add_argument("--expected-revision", help="Full immutable reviewed Git commit SHA")
    parser.add_argument("--development", action="store_true", help="Explicit non-release execution of tracked working source")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to run in quarantine")
    args = parser.parse_args()

    if not args.command:
        logger.error("Usage: zero_trust_runner.py [--nonce NONCE] <command...>")
        return 1

    command = args.command
    if command[0] == "--":
        command = command[1:]
    if not command:
        logger.error("A quarantine command is required")
        return 1

    cwd = Path.cwd().resolve()
    if __package__ in (None, ""):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.dont_write_bytecode = True
    from ci_tools.base_ci import (
        InfrastructureIntegrityError,
        _copy_reviewed_source,
        _profile_environment,
        tracked_source_snapshot,
        verify_source_binding,
    )
    try:
        binding = verify_source_binding(
            cwd, expected_revision=args.expected_revision, development=args.development,
        )
        source_before = tracked_source_snapshot(cwd)
    except InfrastructureIntegrityError as error:
        logger.error("%s", error)
        return 1

    with QuarantineEnvironment() as qe:
        # The reviewed copy excludes student files, licensed runtimes and parent
        # Git configuration. Generic run_command/copy_paths remain caller APIs.
        _copy_reviewed_source(cwd, qe.quarantine_dir, binding)
        copied_before = tracked_source_snapshot(qe.quarantine_dir)

        # Rewrite proven source paths only. Runtime/input paths and all other
        # literal argument bytes keep their caller meaning.
        new_command = []
        for arg in command:
            prefix, separator, value = arg.partition("=") if arg.startswith("-") else ("", "", arg)
            if not separator and arg.startswith("-"):
                new_command.append(arg)
                continue
            candidate = Path(value)
            original = candidate if candidate.is_absolute() else cwd / candidate
            rewritten = value
            try:
                canonical = original.resolve()
                if canonical.is_relative_to(cwd):
                    relative = canonical.relative_to(cwd).as_posix()
                    if relative in source_before or relative == "." or any(
                        name.startswith(relative + "/") for name in source_before
                    ):
                        rewritten = str(qe.quarantine_dir / relative)
                    elif not candidate.is_absolute() and canonical.exists():
                        rewritten = str(canonical)
                elif not candidate.is_absolute() and canonical.exists():
                    rewritten = str(canonical)
            except (OSError, ValueError):
                # A program string or arbitrary literal is not a filesystem path.
                rewritten = value
            new_command.append(prefix + separator + rewritten)

        # 3. Set PYTHONPATH and COCHEM_ROOT strictly to quarantine directory
        extra_paths = [str(qe.quarantine_dir)]
        for relative in ("src", "ci_tools"):
            copied_directory = qe.quarantine_dir / relative
            if copied_directory.is_dir():
                extra_paths.append(str(copied_directory))

        env_overrides = _profile_environment(cwd, qe.quarantine_dir)
        env_overrides["PYTHONPATH"] = os.pathsep.join(extra_paths)
        res = qe.run_command(new_command, timeout=300, environment=env_overrides)
        source_after = tracked_source_snapshot(cwd)
        copied_after = tracked_source_snapshot(qe.quarantine_dir)
        post_binding_error = None
        try:
            verify_source_binding(cwd, expected_revision=binding["revision"], development=args.development)
            verify_source_binding(qe.quarantine_dir, expected_revision=binding["revision"], development=args.development)
        except InfrastructureIntegrityError as error:
            post_binding_error = str(error)

    changed_original = sorted(name for name in source_before.keys() | source_after.keys()
                              if source_before.get(name) != source_after.get(name))
    changed_copy = sorted(name for name in copied_before.keys() | copied_after.keys()
                          if copied_before.get(name) != copied_after.get(name))
    if changed_original or changed_copy or post_binding_error:
        res.exit_code = 1
        res.passed = False
        res.stderr += "\n[HARD_ABORT: SOURCE CHANGED DURING QUARANTINE EXECUTION]"
    def source_seal(snapshot: dict) -> str:
        return hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    source_report = {
        "binding": binding,
        "source_before_sha256": source_seal(source_before),
        "source_after_sha256": source_seal(source_after),
        "copied_before_sha256": source_seal(copied_before),
        "copied_after_sha256": source_seal(copied_after),
        "source_changed": changed_original, "copied_source_changed": changed_copy,
        "post_binding_error": post_binding_error,
        "cleanup_observation": res.cleanup_observation.to_dict() if res.cleanup_observation is not None else None,
        "release_accepted": bool(binding["release_accepted"] and res.passed),
    }
    print("SOURCE_BINDING_REPORT: " + json.dumps(source_report, sort_keys=True))

    if res.stdout:
        print(res.stdout)
    if res.stderr:
        print(res.stderr, file=sys.stderr)

    # Generate Cryptographic ExecutionReceipt
    stdout_hash = hashlib.sha256((res.stdout or "").encode('utf-8')).hexdigest()
    stderr_hash = hashlib.sha256((res.stderr or "").encode('utf-8')).hexdigest()
    receipt = f"\n=== EXECUTION RECEIPT ===\nNONCE: {args.nonce}\nEXIT_CODE: {res.exit_code}\nDURATION: {res.duration_s}s\nSTDOUT_HASH: {stdout_hash}\nSTDERR_HASH: {stderr_hash}\n===========================\n"
    print(receipt)

    return res.exit_code

if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    sys.exit(main())
