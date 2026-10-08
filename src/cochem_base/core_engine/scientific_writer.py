"""File-scoped scientific SWMR writer lifetimes and short reader snapshots.

A dedicated master thread owns the HDF5 handle and cross-platform writer lock.
Scopes share that single writer; standalone appends open and close a short scope.
Readers remain independent SWMR handles while the writer is streaming. A new job
schema is created only after existing local snapshots close and before SWMR starts.
"""
from __future__ import annotations

from concurrent.futures import Future
from contextlib import contextmanager
from functools import wraps
import os
from pathlib import Path
import queue
import threading
import time
from typing import Any, Callable

from cochem_base.core.cochem_core_registry_manager import FileLockTimeoutError


class ScientificSnapshotConflictError(RuntimeError):
    """A synchronous writer was requested from its own active read snapshot."""


class _ScientificStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.condition = threading.Condition()
        # HDF5 handles in one process share dataset chunk caches. refresh() must
        # not invalidate a writer's dirty chunk between assignment and flush.
        # This protects only each short row/snapshot, not the SWMR lifetime;
        # independent-process readers retain fully concurrent SWMR access.
        self.publication = threading.RLock()
        self.users = self.readers = 0
        self.reader_depth = threading.local()
        self.transition = self.closing = False
        self.thread: threading.Thread | None = None
        self.commands: queue.Queue = queue.Queue()

    def acquire(self) -> None:
        if getattr(self.reader_depth, "value", 0):
            raise ScientificSnapshotConflictError(
                "Close this store's reader snapshot before acquiring a scientific writer"
            )
        with self.condition:
            if not self.condition.wait_for(lambda: not self.closing, timeout=10):
                raise FileLockTimeoutError("Previous scientific writer did not close within ten seconds")
            self.users += 1

    def release(self) -> None:
        with self.condition:
            self.users -= 1
            if self.users or self.thread is None:
                return
            self.closing = True
            thread = self.thread
            future = Future()
            self.commands.put((None, None, None, future))
        try:
            future.result()
            thread.join()
        finally:
            with self.condition:
                self.thread = None
                self.closing = False
                self.condition.notify_all()

    @contextmanager
    def topology_transition(self):
        with self.condition:
            self.transition = True
            if not self.condition.wait_for(lambda: self.readers == 0, timeout=10):
                self.transition = False
                self.condition.notify_all()
                raise FileLockTimeoutError("Scientific reader snapshots did not close before a topology transition")
        try:
            with self.publication:
                yield
        finally:
            with self.condition:
                self.transition = False
                self.condition.notify_all()

    @contextmanager
    def snapshot(self):
        # An already admitted thread owns one logical snapshot until its outer
        # scope exits. A pending transition must wait for that thread; making
        # its nested GUI/canonical reads wait for the transition deadlocks both.
        depth = getattr(self.reader_depth, "value", 0)
        if depth:
            self.reader_depth.value = depth + 1
            try:
                with self.publication:
                    yield
            finally:
                self.reader_depth.value = depth
            return
        with self.condition:
            if not self.condition.wait_for(lambda: not self.transition, timeout=10):
                raise FileLockTimeoutError("Scientific archive topology transition exceeded ten seconds")
            self.readers += 1
        self.reader_depth.value = 1
        try:
            with self.publication:
                yield
        finally:
            self.reader_depth.value = 0
            with self.condition:
                self.readers -= 1
                self.condition.notify_all()

    def write(self, group_path: str, initialize: Callable, append: Callable) -> Any:
        if getattr(self.reader_depth, "value", 0):
            raise ScientificSnapshotConflictError(
                "Close this store's reader snapshot before appending scientific observations"
            )
        with self.condition:
            if self.users < 1 or self.closing:
                raise RuntimeError("Scientific append requires a live writer scope")
            if self.thread is None:
                self.thread = threading.Thread(target=self._run, name="CoChem-scientific-writer", daemon=False)
                self.thread.start()
            future = Future()
            self.commands.put((group_path, initialize, append, future))
        return future.result()

    def _run(self) -> None:
        from cochem_base.core.cochem_core_hdf5_manager import CoChemHDF5Manager
        manager = None
        context = writer = None

        def close() -> None:
            nonlocal context, writer
            if context is not None:
                old, context, writer = context, None, None
                old.__exit__(None, None, None)

        while True:
            group_path, initialize, append, future = self.commands.get()
            if group_path is None:
                try:
                    with self.topology_transition():
                        close()
                    future.set_result(None)
                except BaseException as error:
                    # Always release the physical writer handle/lock, even when
                    # a misbehaving snapshot exceeded its declared lifetime.
                    try:
                        close()
                    finally:
                        future.set_exception(error)
                if manager is not None:
                    manager.ipc_queue.close()
                    manager.gatekeeper.ipc_queue.close()
                return
            try:
                if writer is None or group_path not in writer:
                    with self.topology_transition():
                        close()
                        deadline = time.monotonic() + 10
                        while True:
                            try:
                                if manager is None:
                                    manager = CoChemHDF5Manager(h5_path=self.path)
                                initialize(manager)
                                pending = manager.swmr_writer()
                                opened = pending.__enter__()
                                context, writer = pending, opened
                                break
                            except BlockingIOError as error:
                                # Other-process snapshot readers may still hold
                                # their old read-open. Do not disable OS locking,
                                # mutate live SWMR topology or retry other errors.
                                if error.errno != 11 or time.monotonic() >= deadline:
                                    raise FileLockTimeoutError(
                                        "New scientific topology requires previous reader snapshots to close within ten seconds"
                                    ) from error
                                time.sleep(.01)
                with self.publication:
                    result = append(manager, writer)
                future.set_result(result)
            except BaseException as error:
                future.set_exception(error)


_stores_lock = threading.Lock()
_stores: dict[tuple[int, str], _ScientificStore] = {}


def _store(store_path: str | Path | None) -> _ScientificStore:
    from cochem_base.core.cochem_core_hdf5_manager import resolve_landscape_h5_path
    path = resolve_landscape_h5_path(store_path).resolve()
    key = (os.getpid(), str(path))
    with _stores_lock:
        if key not in _stores:
            _stores[key] = _ScientificStore(path)
        return _stores[key]


@contextmanager
def scientific_writer_scope(*, store_path: str | Path | None = None):
    """Keep one real writer alive throughout a producer, then flush/close it.

    New job topologies require short snapshot readers to close. Persistent raw
    readers must remain within a registered fixed-topology streaming session.
    """
    store = _store(store_path)
    store.acquire()
    try:
        yield store
    finally:
        store.release()


@contextmanager
def scientific_reader_snapshot(*, store_path: str | Path | None = None):
    """Coordinate only lifecycle transitions, never an active writer's file lock."""
    with _store(store_path).snapshot():
        yield


def scientific_producer(function):
    """Give existing native producer functions a guaranteed-close writer scope."""
    @wraps(function)
    def scoped(*args, **kwargs):
        with scientific_writer_scope(store_path=kwargs.get("store_path")):
            return function(*args, **kwargs)
    return scoped
