"""Descriptor-bound local files. No execution, archive or scientific policy.

Paths remain absolute and lexical throughout binding; resolving a replaced
ancestor before opening would turn a symlink into misleading apparent trust.
"""
from __future__ import annotations

import hashlib
import os
import stat
import uuid
from pathlib import Path

DirectoryChain = tuple[tuple[Path, int, int], ...]


class ManagedPathError(ValueError):
    """A local filesystem operation cannot retain its declared identity."""


def _lexical(path: Path) -> Path:
    value = Path(path).absolute()
    if value.anchor != "/" or ".." in value.parts:
        raise ManagedPathError("Managed paths need an ordinary absolute POSIX path without traversal")
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise ManagedPathError("This runtime lacks safe no-follow directory descriptors")
    return value


def _component(name: str) -> str:
    if not isinstance(name, str) or name in {"", ".", ".."} or "/" in name or "\x00" in name:
        raise ManagedPathError("A managed child must have one ordinary filename component")
    return name


def _inode(value: os.stat_result) -> tuple[int, int]:
    return value.st_dev, value.st_ino


def _open_chain(path: Path) -> tuple[int, DirectoryChain]:
    path = _lexical(path)
    descriptor = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    identity = os.fstat(descriptor)
    current = Path(path.anchor)
    chain = [(current, *_inode(identity))]
    try:
        for name in path.parts[1:]:
            child = os.open(_component(name), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
            current /= name
            chain.append((current, *_inode(os.fstat(descriptor))))
        return descriptor, tuple(chain)
    except BaseException:
        os.close(descriptor)
        raise


class BoundDirectory:
    """One independently owned directory descriptor with deterministic close."""

    def __init__(self, path: Path, descriptor: int, chain: DirectoryChain):
        self.path = path
        self._descriptor = descriptor
        self.chain = chain

    @property
    def fd(self) -> int:
        if self._descriptor < 0:
            raise ManagedPathError("The bound directory is already closed")
        return self._descriptor

    def __enter__(self) -> "BoundDirectory":
        try:
            self.verify()
            return self
        except BaseException:
            # A failed __enter__ never receives __exit__ from Python.
            self.close()
            raise

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def close(self) -> None:
        if self._descriptor >= 0:
            os.close(self._descriptor)
            self._descriptor = -1

    def verify(self) -> None:
        descriptor, current = _open_chain(self.path)
        try:
            if current != self.chain or _inode(os.fstat(self.fd)) != self.chain[-1][1:]:
                raise ManagedPathError("Managed directory chain changed during its operation")
        finally:
            os.close(descriptor)

    def child(self, name: str) -> "BoundDirectory":
        name = _component(name)
        self.verify()
        descriptor = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self.fd)
        identity = _inode(os.fstat(descriptor))
        path = self.path / name
        result = BoundDirectory(path, descriptor, (*self.chain, (path, *identity)))
        try:
            result.verify()
            return result
        except BaseException:
            result.close()
            raise

    def mkdir_child(self, name: str, *, mode: int = 0o700, exist_ok: bool = True) -> "BoundDirectory":
        name = _component(name)
        self.verify()
        try:
            os.mkdir(name, mode=mode, dir_fd=self.fd)
        except FileExistsError:
            if not exist_ok:
                raise
            # Existing children are opened below with O_DIRECTORY|O_NOFOLLOW.
            # They are never chmodded, deleted or treated as a creation claim.
            existing = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
            if not stat.S_ISDIR(existing.st_mode):
                raise ManagedPathError("Managed directory child is not an ordinary directory") from None
        self.verify()
        return self.child(name)

    def open_file(self, name: str, flags: int, *, mode: int = 0o600) -> int:
        name = _component(name)
        if flags & (os.O_TRUNC | os.O_APPEND):
            raise ManagedPathError("Managed file opens do not truncate or append to existing files")
        self.verify()
        descriptor = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, mode, dir_fd=self.fd)
        try:
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                raise ManagedPathError("Managed member must be an ordinary single-link file")
            self.verify()
            current = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
            if _inode(before) != _inode(current):
                raise ManagedPathError("Managed file identity changed during open")
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    def read_file(self, name: str, *, max_bytes: int) -> bytes:
        return _read_from_directory(self, name, max_bytes=max_bytes)

    def subprocess_cwd(self) -> tuple[str, tuple[int, ...]]:
        """A checked fd-alias cwd capability; caller holds us and passes the fd.

        Use the returned cwd AND pass_fds with the supported subprocess broker.
        No global chdir or preexec_fn is necessary. A later pathname replacement
        cannot redirect this kernel-managed fd alias to a different directory.
        """
        self.verify()
        expected = _inode(os.fstat(self.fd))
        for prefix in ("/proc/self/fd/", "/dev/fd/"):
            alias = prefix + str(self.fd)
            try:
                observed = os.stat(alias)
                if not stat.S_ISDIR(observed.st_mode) or _inode(observed) != expected:
                    continue
                probe = os.open(alias, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    if _inode(os.fstat(probe)) != expected:
                        continue
                finally:
                    os.close(probe)
                self.verify()
                return alias, (self.fd,)
            except OSError:
                # Try only the other explicit descriptor alias, never the
                # original plain pathname or a synthesized runtime directory.
                continue
        raise ManagedPathError("Bound CREST launch is unavailable: this runtime has no verified directory-fd alias")


def open_directory_chain(path: Path, *, expected_chain: DirectoryChain | None = None) -> BoundDirectory:
    path = _lexical(path)
    descriptor, chain = _open_chain(path)
    result = BoundDirectory(path, descriptor, chain)
    try:
        if expected_chain is not None and chain != expected_chain:
            raise ManagedPathError("Managed directory does not match its original identity chain")
        result.verify()
        return result
    except BaseException:
        result.close()
        raise


def read_file_bytes(path: Path, *, max_bytes: int) -> bytes:
    """Read one coherent bounded regular file, never a device/FIFO/symlink."""
    path = _lexical(path)
    with open_directory_chain(path.parent) as parent:
        return parent.read_file(path.name, max_bytes=max_bytes)


def _file_identity(value: os.stat_result) -> tuple[int, ...]:
    return (*_inode(value), value.st_size, value.st_mtime_ns, value.st_ctime_ns, value.st_nlink, value.st_mode)


def _read_from_directory(parent: BoundDirectory, name: str, *, max_bytes: int) -> bytes:
    if type(max_bytes) is not int or max_bytes < 0:
        raise ManagedPathError("Managed file size limit must be a nonnegative integer")
    descriptor = parent.open_file(name, os.O_RDONLY)
    try:
        before = os.fstat(descriptor)
        if not 0 <= before.st_size <= max_bytes:
            raise ManagedPathError("Managed file exceeds its bounded size")
        chunks, count = [], 0
        while chunk := os.read(descriptor, min(65536, max_bytes + 1 - count)):
            count += len(chunk)
            if count > max_bytes:
                raise ManagedPathError("Managed file grew beyond its bounded size")
            chunks.append(chunk)
        after = os.fstat(descriptor)
        parent.verify()
        current = os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
        if _file_identity(before) != _file_identity(after) or _file_identity(after) != _file_identity(current) or count != before.st_size:
            raise ManagedPathError("Managed file identity changed during its read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _publish_temporary(parent: BoundDirectory, temporary: str, descriptor: int, name: str, immutable: bool) -> None:
    identity = _inode(os.fstat(descriptor))
    parent.verify()
    current = os.stat(temporary, dir_fd=parent.fd, follow_symlinks=False)
    if _inode(current) != identity or current.st_nlink != 1:
        raise ManagedPathError("Owned staging identity changed before publication")
    if immutable:
        os.link(temporary, name, src_dir_fd=parent.fd, dst_dir_fd=parent.fd, follow_symlinks=False)
        parent.verify()
        current = os.stat(temporary, dir_fd=parent.fd, follow_symlinks=False)
        if _inode(current) != identity:
            raise ManagedPathError("Owned staging identity changed; replacement left untouched")
        os.unlink(temporary, dir_fd=parent.fd)
    else:
        os.replace(temporary, name, src_dir_fd=parent.fd, dst_dir_fd=parent.fd)
    parent.verify()
    target = os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
    if _inode(target) != identity or target.st_nlink != 1:
        raise ManagedPathError("Published file identity changed")
    os.fsync(parent.fd)


def atomic_write_bytes(directory: Path, name: str, data: bytes, *, immutable: bool = False,
                       expected_chain: DirectoryChain | None = None) -> None:
    """Publish via held directory fds; retain uncertain staging as untrusted.

    On failure no path-based cleanup follows a relocated/replacement owner.
    An unindexed staging file is preferable to deleting an uncertain identity.
    """
    name = _component(name)
    if not isinstance(data, bytes):
        raise ManagedPathError("Managed writes require immutable bytes")
    temporary = "." + uuid.uuid4().hex + ".tmp"
    with open_directory_chain(directory, expected_chain=expected_chain) as parent:
        descriptor = parent.open_file(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        try:
            with os.fdopen(descriptor, "wb", closefd=False) as output:
                output.write(data)
                output.flush()
                os.fsync(descriptor)
            _publish_temporary(parent, temporary, descriptor, name, immutable)
        finally:
            os.close(descriptor)


def copy_regular_file(source: Path, destination: BoundDirectory, name: str) -> tuple[int, str]:
    """Stream an unchanged regular native file, without an archive size cap.

    Source hardlinks remain accepted for publication compatibility only;
    authority/archive reads retain their stricter single-link rule. This does
    not classify the file as scientific data or authorize it for export.
    """
    source = _lexical(source)
    name = _component(name)
    with open_directory_chain(source.parent) as parent:
        parent.verify()
        descriptor = os.open(source.name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=parent.fd)
        try:
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode):
                raise ManagedPathError("Native publication source must be a regular file")
            destination.verify()
            temporary = "." + uuid.uuid4().hex + ".tmp"
            target = destination.open_file(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            try:
                hasher, count = hashlib.sha256(), 0
                with os.fdopen(target, "wb", closefd=False) as output:
                    while chunk := os.read(descriptor, min(65536, before.st_size + 1 - count)):
                        count += len(chunk)
                        if count > before.st_size:
                            raise ManagedPathError("Native publication source grew during copy")
                        output.write(chunk)
                        hasher.update(chunk)
                    output.flush()
                    os.fsync(target)
                parent.verify()
                after = os.fstat(descriptor)
                current = os.stat(source.name, dir_fd=parent.fd, follow_symlinks=False)
                if _file_identity(before) != _file_identity(after) or _file_identity(after) != _file_identity(current) or count != before.st_size:
                    raise ManagedPathError("Native publication source changed during copy")
                os.fchmod(target, stat.S_IMODE(after.st_mode))
                os.utime(target, ns=(after.st_atime_ns, after.st_mtime_ns))
                os.fsync(target)
                _publish_temporary(destination, temporary, target, name, False)
                return count, hasher.hexdigest()
            finally:
                os.close(target)
        finally:
            os.close(descriptor)
