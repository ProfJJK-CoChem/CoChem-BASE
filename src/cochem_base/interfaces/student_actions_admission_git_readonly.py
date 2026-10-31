"""Workflow-only, bounded native Git DATA reader; no remote mutation or science.

Fresh REST identity/ref/run checks remain authority. This backend materializes
only immutable raw Git objects and feeds the unchanged AdmissionStore validator.
Linux per-file/address-space limits are hard; the aggregate disk monitor is a
sampled abort threshold with possible overshoot, not a filesystem quota.
"""
from __future__ import annotations

import hashlib
import ctypes
import importlib.util
import math
import os
from pathlib import Path
import selectors
import shutil
import signal
import stat
import struct
import subprocess
import sys
import tempfile
import time
import urllib.parse


def _contract():
    if __package__:
        from . import student_actions_admission
        return student_actions_admission
    path = Path(__file__).with_name("student_actions_admission.py")
    spec = importlib.util.spec_from_file_location("cochem_readonly_admission", path)
    if spec is None or spec.loader is None:
        raise ImportError("The reviewed admission contract is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


contract = _contract()
FETCH_DEPTH = 257
MAX_OBJECTS = 1542
MAX_RAW_BYTES = 30041501  # 257*(50+16+16+16+16)KiB +257*157B.
MAX_CACHE_BYTES = 64 * 1024 * 1024
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_ADDRESS_SPACE = 512 * 1024 * 1024
STAGING_ABORT_BYTES = 80 * 1024 * 1024
COMMIT_LIMIT = 16 * 1024
TREE_LIMIT = 157
MEMBER_LIMITS = {"request.json": 50 * 1024, "intent.json": 16 * 1024,
                 "state.json": 16 * 1024, "binding.json": 16 * 1024}
GIT = Path("/usr/bin/git")
PRLIMIT = Path("/usr/bin/prlimit")
LOCAL_REF = "refs/heads/cochem-observed-admission"
_ACTIVE_LEASE = None


def _fail(message):
    raise contract.AdmissionError(message)


def _oid(raw, kind):
    return hashlib.sha1(kind.encode() + b" " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def _sha(value):
    if not isinstance(value, str) or not contract.HEX40.fullmatch(value):
        _fail("The Git object identity is not an exact SHA-1")
    return value


class _SubreaperLease:
    """One canonical-loaded-module lease in a fresh, single-threaded Linux CLI.

    This is not a generic GUI/threaded host supervisor. No signal handler is
    changed, and only exact verified adopted children are ever collected.
    """
    def __init__(self,deadline):
        self.pid = os.getpid()
        self.deadline = deadline
        self.ticks = Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]
        self.libc = ctypes.CDLL(None,use_errno=True)
        self.previous = None
        self.restored = False
        self.entry_tasks = None
        self.entry_children = None

    def _get(self):
        value = ctypes.c_int()
        if self.libc.prctl(37,ctypes.byref(value),0,0,0) != 0 or value.value not in (0,1):
            _fail('The Linux metadata child-subreaper state is unavailable')
        return value.value

    def _set(self,value):
        if self.libc.prctl(36,value,0,0,0) != 0:
            _fail('The Linux metadata child-subreaper state could not be set')

    def owns_current_process(self):
        try:
            ticks = Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]
        except (OSError,IndexError):
            return False
        return self.pid == os.getpid() and ticks == self.ticks and _ACTIVE_LEASE is self

    def acquire(self):
        global _ACTIVE_LEASE
        if _ACTIVE_LEASE is not None:
            _fail('Only one isolated admission metadata context may be active')
        try:
            tasks = {path.name for path in Path('/proc/self/task').iterdir()}
        except OSError:
            _fail('The isolated metadata process task/child inventory is unavailable')
        self.entry_tasks = sorted(tasks)
        if tasks != {str(self.pid)}:
            _fail('Admission metadata requires exactly one OS thread')
        if signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL:
            _fail('Admission metadata requires default SIGCHLD')
        self.entry_children = self._direct_children()
        if self.entry_children:
            _fail('Admission metadata requires no existing children')
        self.previous = self._get()
        _ACTIVE_LEASE = self
        try:
            self._set(1)
            if self._get() != 1:
                _fail('The Linux metadata child-subreaper lease did not activate')
        except BaseException:
            self.restore()
            raise

    def _direct_children(self):
        # /proc/TID/children is optional and absent on the observed host. Read
        # actual PPIDs instead; missing/unreadable live stat is never empty.
        # With exactly one task and default SIGCHLD there is no other waiter
        # that could reap our child during this entry inventory. Only a truly
        # vanished unrelated entry can therefore be skipped.
        children = []
        try:
            with os.scandir('/proc') as entries:
                for entry in entries:
                    if time.time() >= self.deadline:
                        _fail('The inherited admission metadata deadline expired')
                    if not entry.name.isascii() or not entry.name.isdigit():
                        continue
                    path = Path('/proc')/entry.name
                    try:
                        with (path/'stat').open('rb') as handle:
                            raw = handle.read(4097)
                    except FileNotFoundError:
                        try:
                            path.lstat()
                        except FileNotFoundError:
                            continue
                        _fail('A live process has no readable metadata stat inventory')
                    prefix,separator,tail = raw.rpartition(b')')
                    fields = tail.split()
                    if (len(raw)>4096 or not separator or prefix.split(b' ',1)[0]!=entry.name.encode()
                            or len(fields)<20 or len(fields[0])!=1
                            or any(not fields[index].isdigit() for index in (1,2,3,19))):
                        _fail('The live process metadata stat inventory is malformed')
                    if int(fields[1]) == self.pid:
                        children.append({'pid':int(entry.name),'start_ticks':fields[19].decode('ascii')})
        except OSError:
            _fail('The isolated metadata process task/child inventory is unavailable')
        if time.time() >= self.deadline:
            _fail('The inherited admission metadata deadline expired')
        return children

    def restore(self):
        global _ACTIVE_LEASE
        if self.restored:
            return
        if not self.owns_current_process() or self.previous not in (0,1):
            _fail('Refusing to restore a metadata lease not owned by this process')
        self._set(self.previous)
        if self._get() != self.previous:
            _fail('The prior Linux child-subreaper state could not be restored')
        self.restored = True
        _ACTIVE_LEASE = None

    def observation(self):
        return {'owner_pid':self.pid,'owner_start_ticks':self.ticks,
                'previous_bit':self.previous,'restored':self.restored,
                'entry_tasks':self.entry_tasks,'entry_direct_children':self.entry_children,
                'scope':'single-loaded-module isolated single-thread Linux CLI'}


class _GitChild:
    """One group-owned Linux metadata subprocess, with bounded private pipes."""
    def __init__(self, owner, arguments, *, token=False, persistent=False):
        self.owner, self.persistent = owner, persistent
        owner._remaining()
        self.output = bytearray()
        self.stderr_bytes = 0
        self.file_limit_error_observed = False
        self._stderr_tail = b''
        self.stdout_bytes = 0
        self.closed = False
        self.selector = selectors.DefaultSelector()
        command = [str(PRLIMIT), "--as=536870912:536870912", "--fsize=33554432:33554432", "--core=0:0", "--",
                   str(GIT), *arguments]
        self.process = subprocess.Popen(command, cwd=owner._root, env=owner._environment(token),
            stdin=subprocess.PIPE if persistent else subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        self.pid = self.process.pid
        self.start_ticks = self._ticks()
        self.record = {"pid": self.pid, "process_group": self.pid, "start_ticks": self.start_ticks,
            "operation": arguments[-1] if not persistent else "cat-file batch-command",
            "credential_scope": "private askpass environment only" if token else "no token",
            "hard_per_file_bytes": MAX_FILE_BYTES, "hard_address_space_bytes": MAX_ADDRESS_SPACE,
            "started_monotonic": time.monotonic(), "stopped": False,
            'adopted_reaped':[], 'actual_file_limit_signal_observed':False}
        owner._children.append(self)
        owner.diagnostics.append(self.record)
        for stream, tag in ((self.process.stdout, "stdout"), (self.process.stderr, "stderr")):
            os.set_blocking(stream.fileno(), False)
            self.selector.register(stream, selectors.EVENT_READ, tag)

    def _ticks(self):
        try:
            return Path(f"/proc/{self.pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
        except (OSError, IndexError):
            return None

    def _identity_is_owned(self):
        try:
            fields = Path(f"/proc/{self.pid}/stat").read_text().rsplit(")", 1)[1].split()
            return fields[19] == self.start_ticks and int(fields[2]) == self.pid and int(fields[3]) == self.pid
        except (OSError, ValueError, IndexError):
            return False

    def _exited(self):
        # WNOWAIT leaves the exact leader (including a zombie) unreaped. Its
        # reserved PID cannot be recycled into an unrelated process group before
        # descendant cleanup and our final wait(). No Popen.poll() is used.
        if not self._identity_is_owned():
            _fail("The native Git metadata launcher identity could not be confirmed")
        return os.waitid(os.P_PID, self.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)

    def _members(self):
        members = []
        for path in Path('/proc').iterdir():
            if not path.name.isdigit() or int(path.name) == self.pid:
                continue
            try:
                fields = (path/'stat').read_text().rsplit(')',1)[1].split()
                if int(fields[2]) == self.pid:
                    members.append({'pid':int(path.name),'state':fields[0],'start_ticks':fields[19],
                        'parent_pid':int(fields[1]),'process_group':int(fields[2]),'session':int(fields[3])})
            except (OSError, ValueError, IndexError):
                continue
        return members

    def _reap_adopted(self,members):
        if not self.owner._lease.owns_current_process() or not self._identity_is_owned():
            _fail('The owned unreaped Git leader and metadata subreaper lease are required')
        for observed in members:
            if (observed['state'] != 'Z' or observed['parent_pid'] != os.getpid()
                    or observed['process_group'] != self.pid or observed['session'] != self.pid):
                continue
            try:
                fields = Path(f"/proc/{observed['pid']}/stat").read_text().rsplit(')',1)[1].split()
            except FileNotFoundError:
                _fail('An adopted Git child disappeared before exact collection')
            actual = {'pid':observed['pid'],'state':fields[0],'start_ticks':fields[19],
                'parent_pid':int(fields[1]),'process_group':int(fields[2]),'session':int(fields[3])}
            if actual != observed or not self._identity_is_owned():
                _fail('An adopted Git child identity changed before exact collection')
            try:
                pid,status = os.waitpid(observed['pid'],os.WNOHANG)
            except ChildProcessError:
                _fail('The exact Git child is not adopted by this metadata owner')
            if pid == 0:
                continue
            if pid != observed['pid']:
                _fail('Exact adopted Git collection returned another identity')
            row = {**actual,'raw_wait_status':status,
                'exited':os.WIFEXITED(status),'signaled':os.WIFSIGNALED(status),
                'exit_code':os.WEXITSTATUS(status) if os.WIFEXITED(status) else None,
                'signal':os.WTERMSIG(status) if os.WIFSIGNALED(status) else None,
                'leader_identity_confirmed_unreaped_before_wait':True}
            self.record['adopted_reaped'].append(row)
            if os.WIFSIGNALED(status) and os.WTERMSIG(status) == signal.SIGXFSZ:
                self.record['actual_file_limit_signal_observed'] = True

    def _signal_owned(self, signum):
        if not self._identity_is_owned():
            _fail("Refusing to signal a Git metadata group after identity loss")
        os.killpg(self.pid, signum)

    def _pump(self):
        self.owner._remaining()
        self.owner._check_staging()
        for key, unused in self.selector.select(min(.05, self.owner._remaining())):
            raw = os.read(key.fd, 65536)
            if not raw:
                self.selector.unregister(key.fileobj)
                continue
            if key.data == "stderr":
                self.stderr_bytes += len(raw)
                combined = self._stderr_tail + raw
                self.file_limit_error_observed |= b'File too large' in combined or b'signal 25' in combined
                self._stderr_tail = combined[-64:]
                if self.stderr_bytes > 256 * 1024:
                    _fail("Git metadata error output exceeded its bound")
                # Never retain/log Git stderr: an upstream error can contain
                # private server text, names, headers or credential material.
            else:
                self.stdout_bytes += len(raw)
                self.output.extend(raw)
                limit = 64 * 1024 if self.persistent else 256 * 1024
                if len(self.output) > limit:
                    _fail("Git metadata output exceeded its bounded pipe buffer")

    def read(self, count):
        while len(self.output) < count:
            if self._exited() is not None and not self.selector.get_map():
                _fail("Git metadata pipe closed before the complete object")
            self._pump()
        raw = bytes(self.output[:count])
        del self.output[:count]
        return raw

    def line(self):
        while b"\n" not in self.output:
            if len(self.output) > 256:
                _fail("Git object header exceeded its bound")
            if self._exited() is not None and not self.selector.get_map():
                _fail("Git metadata header was incomplete")
            self._pump()
        end = self.output.index(b"\n") + 1
        if end > 256:
            _fail("Git object header exceeded its bound")
        return self.read(end)

    def send(self, raw):
        self.owner._remaining()
        if len(raw) > 128 or self._exited() is not None:
            _fail("Git metadata command is invalid or its owner stopped")
        self.process.stdin.write(raw)
        self.process.stdin.flush()

    def finish(self):
        while self._exited() is None or self.selector.get_map():
            self._pump()
        status = self._exited()
        if status.si_code != os.CLD_EXITED or status.si_status != 0:
            _fail("The bounded native Git metadata operation failed; no request was admitted")
        result = bytes(self.output)
        self.output.clear()
        self.close()
        return result

    def close(self):
        if self.closed:
            if self.record.get('stopped') is not True:
                _fail("Native Git metadata cleanup previously failed; its staging remains held")
            return
        if self.process.stdin is not None:
            try:
                self.process.stdin.close()
            except OSError:
                pass
        if not self._identity_is_owned():
            self.record.update(stopped=False,identity_lost=True)
            _fail("Native Git metadata owner identity was lost before cleanup")
        self.record['leader_state_before_cleanup']=Path(f'/proc/{self.pid}/stat').read_text().rsplit(')',1)[1].split()[0]
        self.record['waitid_completion_observed_before_cleanup']=self._exited() is not None
        self._signal_owned(signal.SIGTERM)
        started = time.monotonic()
        while time.monotonic()-started < 2.5:
            status, members = self._exited(), self._members()
            self._reap_adopted(members)
            members = self._members()
            if status is not None and not members:
                break
            if time.monotonic()-started >= .5:
                self._signal_owned(signal.SIGKILL)
            time.sleep(.01)
        self._reap_adopted(self._members())
        members = self._members()
        status = self._exited()
        # All signals were issued while the exact unreaped leader reserved its
        # identity. Reap only now; never signal this PGID after wait().
        code = self.process.wait(timeout=2)
        self.closed = True
        empty = status is not None and not members
        self.selector.close()
        self.process.stdout.close()
        self.process.stderr.close()
        self.record.update(exit_code=code, stopped=empty, stdout_bytes=self.stdout_bytes,
                           stderr_bytes=self.stderr_bytes, raw_output_logged=False,
                           actual_file_limit_error_observed=self.file_limit_error_observed,
                           cleanup_leader_identity_verified_before_signals=True,
                           leader_reaped_after_group_inspection=True,
                           external_reaping_pending=members,
                           elapsed_seconds=time.monotonic() - self.record["started_monotonic"])
        if not empty:
            _fail("Native Git metadata process-group cleanup could not be confirmed")
        self._stderr_tail = b''


class ReadOnlyGitAdmissionBackend:
    """Context-managed workflow DATA reader, never an admission/dispatch owner.

    The caller supplies the already authenticated ReadOnlyAPI and the SAME
    absolute deadline. Mutable API state is never cached. A final caller
    ``backend.tip() == snapshot.tip`` check is required before authorization.
    """
    def __init__(self, readonly_api, repository, *, work_root, deadline,
                 github_token_from_env="GITHUB_TOKEN", engineering_git_url=None,
                 allow_loopback=False):
        if (sys.platform != "linux" or not isinstance(repository, str)
                or not contract.REPO.fullmatch(repository) or type(deadline) not in (int, float)
                or not math.isfinite(deadline) or deadline != getattr(readonly_api, "deadline", None)
                or github_token_from_env != "GITHUB_TOKEN"):
            _fail("Native Git admission needs the same finite Linux workflow metadata deadline")
        self.api, self.repository, self.deadline = readonly_api, repository, deadline
        self.work_root = Path(work_root).absolute()
        source = Path(__file__).resolve().parents[3]
        if self.work_root.resolve() != self.work_root or self.work_root.is_relative_to(source):
            _fail("Admission object staging must be outside reviewed source")
        self.url = "https://github.com/" + repository + ".git"
        if engineering_git_url is not None:
            parsed = urllib.parse.urlsplit(engineering_git_url)
            if (not allow_loopback or parsed.scheme != "http"
                    or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                    or parsed.username or parsed.password or parsed.query or parsed.fragment
                    or parsed.path != "/" + repository + ".git"):
                _fail("The engineering Git transport must be an explicitly allowed exact loopback repository")
            self.url = engineering_git_url
        self._root = None
        self._children = []
        self._batch = None
        self._bare = None
        self._tip = None
        self._seen_tip = None
        self._fetches = 0
        self._cache = {}
        self._objects = {}
        self._raw_bytes = 0
        self._last_disk_sample = 0.0
        self._token = None
        self.diagnostics = []

    def _remaining(self):
        remaining = self.deadline - time.time()
        if remaining <= 0:
            _fail("The inherited admission metadata deadline expired")
        return remaining

    def __enter__(self):
        self._remaining()
        if self._root is not None:
            _fail('Admission object staging cannot be reused across contexts')
        self._lease = _SubreaperLease(self.deadline)
        self._lease.acquire()
        try:
            return self._enter_owned()
        except BaseException:
            self._lease.restore()
            if self.diagnostics:
                self.diagnostics[-1]['subreaper_lease'] = self._lease.observation()
            raise

    def _enter_owned(self):
        if self._root is not None:
            _fail("Admission object staging cannot be reused across contexts")
        self._remaining()
        for executable in (GIT, PRLIMIT):
            info = executable.stat()
            if (executable.resolve() != executable or not stat.S_ISREG(info.st_mode)
                    or info.st_uid != 0 or info.st_mode & 0o022 or not os.access(executable, os.X_OK)):
                _fail("The supported trusted native Git/limit tools are unavailable")
        self.work_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        root_info = self.work_root.lstat()
        if (self.work_root.resolve() != self.work_root or self.work_root.is_symlink()
                or not stat.S_ISDIR(root_info.st_mode) or root_info.st_uid != os.getuid()
                or stat.S_IMODE(root_info.st_mode) & 0o077):
            _fail("The admission staging root was redirected")
        token = os.environ.get("GITHUB_TOKEN", "")
        if not token or any(char.isspace() for char in token) or token != getattr(self.api, "token", None):
            _fail("Only this verification step's authenticated GitHub token may read Git data")
        home = os.environ.get('HOME')
        if not home or not Path(home).is_absolute() or Path.home() != Path(home):
            _fail("The native Git credential home scope is unavailable or ambiguous")
        self._home = home
        if any(path.exists() or path.is_symlink() for path in (Path(home)/'.netrc',Path(home)/'_netrc')):
            _fail("Ambient netrc credentials cannot be used for admission metadata")
        self._root = Path(tempfile.mkdtemp(prefix="readonly-", dir=self.work_root))
        info = self._root.lstat()
        self._root_identity = (info.st_dev, info.st_ino)
        self._token = token
        try:
            self._askpass = self._root / "askpass"
            self._askpass.write_text("#!/bin/sh\ncase \"$1\" in\n*Username*) printf '%s\\n' x-access-token;;\n*Password*) printf '%s\\n' \"$COCHEM_ADMISSION_GIT_TOKEN\";;\n*) exit 1;;\nesac\n")
            self._askpass.chmod(0o700)
            (self._root / "empty-template").mkdir(mode=0o700)
        except BaseException as original_error:
            self._token = None
            try:
                current = self._root.lstat()
                if self._root.resolve() != self._root or (current.st_dev,current.st_ino) != self._root_identity:
                    _fail("The failed admission setup no longer owns its staging root")
                shutil.rmtree(self._root)
                self.diagnostics.append({'entry_failed':True,'owned_root_removed':True,'token_cleared':True})
            except BaseException as cleanup_error:
                self.diagnostics.append({'entry_failed':True,'owned_root_removed':False,'token_cleared':True})
                raise contract.AdmissionError('Failed admission setup cleanup could not be confirmed') from original_error
            raise
        return self

    def _environment(self, token):
        # Strip Git/credential/trace/library injection, alternate objects,
        # templates, worktrees, SSH and lazy-fetch settings. Preserve the
        # platform's standard proxy routes below without logging their values.
        result = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C",
            "HOME": self._home,
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0", "GIT_SSH_COMMAND": "false",
            "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}
        for name in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY',
                     'http_proxy','https_proxy','all_proxy','no_proxy'):
            if name in os.environ:
                result[name]=os.environ[name]  # Never log proxy routes/credentials.
        if token:
            result.update(GIT_ASKPASS=str(self._askpass), COCHEM_ADMISSION_GIT_TOKEN=self._token)
        return result

    def _arguments(self, *arguments):
        return ["--git-dir=" + str(self._bare), "-c", "core.hooksPath=" + os.devnull,
            "-c", "credential.helper=", "-c", "http.followRedirects=false",
            "-c", "http.sslVerify=true", "-c", "protocol.allow=never",
            "-c", "protocol.https.allow=always", "-c", "protocol.http.allow=" + ("always" if self.url.startswith("http://") else "never"),
            "-c", "fetch.recurseSubmodules=false", "-c", "submodule.recurse=false",
            "-c", "fetch.unpackLimit=1", "-c", "gc.auto=0", "-c", "maintenance.auto=false",
            "-c", "fetch.writeCommitGraph=false", "-c", "core.logAllRefUpdates=false",
            "-c", "pack.writeReverseIndex=false", "-c", "pack.threads=1", *arguments]

    def _check_staging(self, force=False):
        if not force and time.monotonic() - self._last_disk_sample < .05:
            return
        self._last_disk_sample = time.monotonic()
        total = 0
        for parent, dirs, files in os.walk(self._root, followlinks=False):
            for name in dirs + files:
                path = Path(parent) / name
                try:value = path.lstat()
                except FileNotFoundError:continue  # Sample raced an ordinary Git rename/removal.
                if stat.S_ISLNK(value.st_mode):
                    _fail("Native Git staging contains a redirected member")
                if stat.S_ISREG(value.st_mode):
                    total += value.st_size
                    if value.st_size > MAX_FILE_BYTES:
                        _fail("Native Git staging file exceeded its hard per-file budget")
        if total > STAGING_ABORT_BYTES:
            _fail("Sampled native Git staging exceeded80MiB; no request was admitted")
        self._remaining()

    def _run(self, arguments, *, token=False):
        child = _GitChild(self, arguments, token=token)
        try:
            return child.finish()
        finally:
            child.close()

    def _fresh_tip(self):
        self._remaining()
        try:
            value = self.api._request(f"/repos/{self.repository}/git/ref/heads/cochem-student-admission-v1")
        except (RuntimeError, OSError) as error:
            if getattr(error, "http_status", None) == 404 and self._seen_tip is None:
                return None
            raise
        self._remaining()
        if (not isinstance(value, dict) or value.get("ref") != contract.LEDGER_REF
                or value.get("object", {}).get("type") != "commit"):
            _fail("Fresh admission ref metadata is invalid")
        return _sha(value["object"].get("sha"))

    def _header(self, oid, operation):
        self._batch.send(operation.encode() + b" " + oid.encode() + b"\n")
        parts = self._batch.line().rstrip(b"\n").split(b" ")
        if len(parts) != 3 or parts[0] != oid.encode("ascii") or not parts[2].isdigit():
            _fail("Git raw object type/size is missing or invalid")
        if parts[1] not in (b"commit", b"tree", b"blob"):
            _fail("Git raw object has an unsupported type")
        return parts[1].decode("ascii"), int(parts[2])

    def _raw(self, oid, kind, limit):
        _sha(oid)
        if oid in self._objects:
            old_kind, raw = self._objects[oid]
            if old_kind != kind or len(raw) > limit:
                _fail("A Git object was reused with another required type/size")
            return raw
        actual_kind, size = self._header(oid, "info")
        if actual_kind != kind or size > limit:
            _fail("Git object exceeds its exact required type/raw-byte bound")
        if len(self._objects) >= MAX_OBJECTS or self._raw_bytes + size > min(MAX_RAW_BYTES, MAX_CACHE_BYTES):
            _fail("The bounded immutable admission object graph is oversized")
        if self._header(oid, "contents") != (kind, size):
            _fail("Git object header changed before its bounded raw read")
        raw = self._batch.read(size)
        if self._batch.read(1) != b"\n" or _oid(raw, kind) != oid:
            _fail("Raw Git bytes do not bind their claimed object identity")
        self._objects[oid] = (kind, raw)
        self._raw_bytes += size
        return raw

    def _files(self, commit):
        raw = self._raw(commit, "commit", COMMIT_LIMIT)
        if b"\0" in raw or b"\n\n" not in raw:
            _fail("The raw Git commit header is malformed")
        header = raw.split(b"\n\n", 1)[0].splitlines()
        trees = [line[5:] for line in header if line.startswith(b"tree ")]
        parents = [line[7:] for line in header if line.startswith(b"parent ")]
        if len(trees) != 1 or len(parents) > 1:
            _fail("Admission Git history must have exactly one tree and at most one raw parent")
        if any(not value.isascii() for value in trees + parents):
            _fail("Raw Git tree/parent identity is not ASCII")
        tree = _sha(trees[0].decode("ascii"))
        parent = _sha(parents[0].decode("ascii")) if parents else None
        data = self._raw(tree, "tree", TREE_LIMIT)
        files, names, position = {}, [], 0
        while position < len(data):
            separator = data.find(b" ", position)
            end = data.find(b"\0", separator + 1)
            if separator < 0 or end < 0 or end + 21 > len(data):
                _fail("The raw admission tree is incomplete")
            raw_name = data[separator + 1:end]
            if not raw_name.isascii():
                _fail("The raw admission tree member name is not ASCII")
            mode, name = data[position:separator], raw_name.decode("ascii")
            oid = data[end + 1:end + 21].hex()
            if mode != b"100644" or name not in MEMBER_LIMITS or name in files:
                _fail("Admission trees contain only exact flat ordinary data members")
            names.append(name)
            files[name] = self._raw(oid, "blob", MEMBER_LIMITS[name])
            position = end + 21
        if names != sorted(names) or not {"request.json", "intent.json", "state.json"}.issubset(files):
            _fail("The admission tree is noncanonical or lacks required members")
        return files, parent

    def _materialize(self, expected):
        if self._fetches >= 2:
            _fail("Admission ref kept moving; the original request remains held")
        if self._batch is not None:
            self._batch.close()
            self._batch = None
        if self._bare is not None:
            shutil.rmtree(self._bare)
        self._fetches += 1
        self._bare = self._root / f"objects-{self._fetches}.git"
        self._objects, self._cache, self._raw_bytes = {}, {}, 0
        self._run(["init", "--bare", "--object-format=sha1", "--template=" + str(self._root / "empty-template"), str(self._bare)])
        self._run(self._arguments("fetch", "--quiet", "--no-tags", "--no-recurse-submodules", "--no-auto-maintenance",
            "--no-write-fetch-head", "--depth=257", self.url, contract.LEDGER_REF + ":" + LOCAL_REF), token=True)
        self._check_staging(force=True)
        forbidden = ["shallow", "objects/info/alternates", "info/grafts", "refs/replace"]
        if any((self._bare / name).exists() for name in forbidden) or list((self._bare / "objects/pack").glob("*.promisor")):
            _fail("Incomplete/shallow/replaced/promisor Git ancestry is not admission history")
        fetched = self._run(self._arguments("rev-parse", "--verify", LOCAL_REF)).decode().strip()
        if fetched != expected or self._fresh_tip() != expected:
            _fail("The fresh REST ref and materialized Git ref differ; no request was admitted")
        packs = list((self._bare / "objects/pack").glob("*.pack"))
        if len(packs) != 1:
            _fail("The isolated admission fetch did not produce one bounded pack")
        with packs[0].open("rb") as stream:
            magic, version, count = struct.unpack(">4sII", stream.read(12))
        if magic != b"PACK" or version not in (2, 3) or not 0 < count <= MAX_OBJECTS:
            _fail("The received Git pack has an invalid or oversized object count")
        self._batch = _GitChild(self, self._arguments("cat-file", "--batch-command"), persistent=True)
        current, seen = expected, set()
        while current is not None:
            if current in seen or len(seen) >= FETCH_DEPTH:
                _fail("Admission ancestry is cyclic or exceeds the sentinel depth")
            seen.add(current)
            files, parent = self._files(current)
            self._cache[current] = (files, parent)
            current = parent
        if len(self._objects) != count:
            _fail("The fetched pack contains objects outside the exact validated data ancestry")
        if self._seen_tip is not None and self._seen_tip not in seen:
            _fail("The admission data ref was replaced or rewound")
        self._check_staging(force=True)
        if self._fresh_tip() != expected:
            _fail("Admission state changed during raw-object verification")
        self._tip = self._seen_tip = expected
        self.diagnostics.append({"materialized_tip": expected, "raw_objects": len(self._objects),
            "pack_objects": count, "raw_payload_bytes": self._raw_bytes, "commits": len(seen),
            "sampled_staging_threshold_bytes": STAGING_ABORT_BYTES, "hard_aggregate_quota": False})

    def tip(self):
        if self._root is None:
            _fail("Native Git admission must run inside its owned context")
        current = self._fresh_tip()
        if current is None:
            return None
        if current != self._tip:
            self._materialize(current)
        return current

    def files(self, commit):
        self._remaining()
        _sha(commit)
        if commit not in self._cache:
            _fail("The requested commit is not in the complete freshly fetched admission ancestry")
        files, parent = self._cache[commit]
        return dict(files), parent

    def commit(self, *arguments, **keywords):
        _fail("The workflow object reader cannot create admission transitions")

    def advance(self, *arguments, **keywords):
        _fail("The workflow object reader cannot advance a project ref")

    def __exit__(self, exc_type, exc_value, traceback):
        errors = []
        try:
            for child in reversed(self._children):
                try:
                    child.close()
                except BaseException as error:
                    errors.append(type(error).__name__)
                if child.record.get('stopped') is not True:
                    errors.append('ChildCleanupIncomplete')
        finally:
            self._token = None
            try:
                self._lease.restore()
            except BaseException as error:
                errors.append(type(error).__name__)
        if self._root is not None:
            value = self._root.lstat()
            if self._root.resolve() != self._root or (value.st_dev, value.st_ino) != self._root_identity:
                errors.append("OwnedRootChanged")
            elif not errors:
                shutil.rmtree(self._root)
        self.diagnostics.append({"context_closed": not errors, "cleanup_errors": errors,
            "credentials_persisted": False, "bare_repository_uploaded": False,
            'subreaper_lease':self._lease.observation()})
        if errors:
            _fail("Owned native Git metadata cleanup was incomplete")
