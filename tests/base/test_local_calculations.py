"""Real filesystem/index authority negatives; no fabricated native results.

Positive new producer/archive/reopen qualification requires scheduled genuine
native results and is deliberately separate from these engineering contracts.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from ci_tools.source_quarantine import source_paths
from cochem_base.calc.local_publication import (
    INDEX_LIMIT,
    LocalFilesError,
    digest,
    read_member,
    sidecar,
)
from cochem_base.interfaces.local_calculations import (
    INDEX_LOCK_WAIT_SECONDS,
    LocalCalculationStore,
    _atomic_file,
    _bind_observation_sources,
    _bind_record_execution,
)
from cochem_base.interfaces.student_request import canonical_json


def test_empty_index_does_not_discover_arbitrary_native_or_zip_files(tmp_path):
    (tmp_path / "untrusted.zip").write_bytes(b"Not a calculation archive")
    fake = tmp_path / "GUI" / ("run_" + "1" * 32) / "Results"
    fake.mkdir(parents=True)
    (fake / "execution.json").write_bytes(b'{"status":"EXECUTION_VERIFIED"}')
    store = LocalCalculationStore(tmp_path)
    assert store.list_saved() == ()
    with pytest.raises(ValueError, match="not a registered"):
        store.reopen_saved("job_" + "1" * 32)
    with pytest.raises(ValueError):
        store.register_completed({"status": "EXECUTION_VERIFIED"}, results_directory=fake)
    assert store.list_saved() == () and not (tmp_path / "LocalCalculations").exists()


def test_custom_root_outside_managed_gui_location_and_links_are_refused(tmp_path):
    root = tmp_path / "managed"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    store = LocalCalculationStore(root)
    with pytest.raises(ValueError):
        store.register_completed({}, results_directory=outside)
    (root / "aliased").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        store.register_completed({}, results_directory=root / "aliased")
    assert not (root / "LocalCalculations").exists()


@pytest.mark.parametrize("kind", ["malformed", "symlink", "too-many", "wrong-order"])
def test_bad_index_fails_closed_without_reset_or_eviction(tmp_path, kind):
    store = LocalCalculationStore(tmp_path)
    store._prepare_store()
    path = store.directory / "index.json"
    if kind == "malformed":
        path.write_bytes(b"Not JSON")
    elif kind == "symlink":
        target = tmp_path / "private-sentinel"
        target.write_bytes(b"Preserve this file")
        path.symlink_to(target)
    else:
        count = INDEX_LIMIT + 1 if kind == "too-many" else 1
        entries = {f"job_{number:032x}": {"path": f"records/job_{number:032x}.json", "sha256": "0" * 64}
                   for number in range(count)}
        order = list(entries) if kind == "too-many" else []
        path.write_bytes(canonical_json({"schema_version": "cochem.local-calculation-index/1", "records": entries, "order": order}))
    before = path.read_bytes()
    with pytest.raises((ValueError, OSError)):
        store.list_saved()
    assert path.read_bytes() == before


def test_corrupt_individual_record_remains_in_place_and_unindexed_orphan_is_not_trusted(tmp_path):
    store = LocalCalculationStore(tmp_path)
    store._prepare_store()
    identifiers = ["job_" + token * 32 for token in ("1", "2")]
    records = {}
    for identifier in identifiers:
        data = canonical_json({"engineering_marker": identifier})
        _atomic_file(store.directory / "records", identifier + ".json", data, immutable=True)
        records[identifier] = {"path": "records/" + identifier + ".json", "sha256": digest(data)}
    orphan = "job_" + "3" * 32
    _atomic_file(store.directory / "records", orphan + ".json", b"Unindexed engineering marker", immutable=True)
    _atomic_file(store.directory, "index.json", canonical_json({"schema_version": "cochem.local-calculation-index/1", "records": records, "order": identifiers}))
    summaries = store.list_saved()
    assert [item.record_id for item in summaries] == identifiers
    assert all(not item.available and item.notice for item in summaries)
    with pytest.raises(ValueError, match="not a registered"):
        store.reopen_saved(orphan)
    assert (store.directory / "records" / (orphan + ".json")).read_bytes() == b"Unindexed engineering marker"


def test_atomic_immutable_record_does_not_overwrite_previous_bytes(tmp_path):
    _atomic_file(tmp_path, "record.json", b"Original engineering record", immutable=True)
    with pytest.raises(FileExistsError):
        _atomic_file(tmp_path, "record.json", b"Attempted replacement", immutable=True)
    assert (tmp_path / "record.json").read_bytes() == b"Original engineering record"


def test_reread_provenance_cannot_pair_with_earlier_validated_bytes(tmp_path):
    path = tmp_path / "evidence.txt"
    path.write_bytes(b"Original engineering evidence, not a native observation")
    checksum = tmp_path / "evidence.txt.sha256"
    checksum.write_bytes(sidecar(path.name, path.read_bytes()))
    contents = {name: read_member(tmp_path, name) for name in (path.name, checksum.name)}
    provenance = [{"path": str(tmp_path / name), "sha256": digest(data)} for name, data in contents.items()]
    observation = {"source": provenance[0], "provenance_sources": provenance}
    _bind_observation_sources(observation, contents, tmp_path)
    path.write_bytes(b"Later real filesystem replacement evidence")
    checksum.write_bytes(sidecar(path.name, path.read_bytes()))
    later = [{"path": str(target), "sha256": digest(target.read_bytes())} for target in (path, checksum)]
    with pytest.raises(ValueError, match="byte snapshot"):
        _bind_observation_sources({"source": later[0], "provenance_sources": later}, contents, tmp_path)
    with pytest.raises(ValueError, match="byte snapshot"):
        _bind_observation_sources({"source": provenance[0], "provenance_sources": [provenance[0], later[1]]}, contents, tmp_path)


@pytest.mark.parametrize("rewrite", [False, True])
def test_final_receipt_snapshot_refuses_coherent_whitespace_replacement(tmp_path, rewrite):
    # Filesystem/envelope control only: this document makes no engine/status or
    # scientific-result claim and never invokes native admission or a solver.
    path = tmp_path / "execution.json"
    checksum = tmp_path / "execution.json.sha256"
    first = canonical_json({"engineering_envelope_only": True, "identity": "original"})
    path.write_bytes(first)
    checksum.write_bytes(sidecar(path.name, first))
    phase_a = read_member(tmp_path, path.name)
    record = {"receipt_sha256": digest(phase_a)}
    assert read_member(tmp_path, checksum.name) == sidecar(path.name, phase_a)
    if rewrite:
        replacement = json.dumps(json.loads(first), indent=4).encode() + b"\n"
        path.write_bytes(replacement)
        checksum.write_bytes(sidecar(path.name, replacement))
    final_contents = {name: read_member(tmp_path, name) for name in (path.name, checksum.name)}
    assert json.loads(phase_a) == json.loads(final_contents[path.name])
    assert final_contents[checksum.name] == sidecar(path.name, final_contents[path.name])
    if rewrite:
        assert digest(final_contents[path.name]) != record["receipt_sha256"]
        with pytest.raises(LocalFilesError, match="between validation phases"):
            _bind_record_execution(record, final_contents)
        assert path.read_bytes() == replacement  # Refusal never repairs bytes.
    else:
        _bind_record_execution(record, final_contents)


@pytest.mark.parametrize("replace", [False, True])
def test_actual_open_parent_replacement_is_refused_and_unchanged_path_works(tmp_path, replace):
    root = Path(__file__).resolve().parents[2]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=os.pathsep.join(source_paths(root)))
    child = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "directory-child", str(tmp_path), str(int(replace))],
        env=env, capture_output=True, text=True, timeout=30)
    assert child.returncode == 0, child.stdout + child.stderr


def _run_filesystem_child(tmp_path, case):
    root = Path(__file__).resolve().parents[2]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=os.pathsep.join(source_paths(root)))
    result = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "filesystem-child", str(tmp_path), case],
        env=env, capture_output=True, text=True, timeout=40)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("phase,kind", [(phase, kind) for phase in ("mkdir", "lock", "temp", "link", "replace")
                                      for kind in ("symlink", "directory")] + [("unchanged", "directory")])
def test_mutations_never_follow_actual_replaced_ancestor(tmp_path, phase, kind):
    _run_filesystem_child(tmp_path, "mutation:" + phase + ":" + kind)


@pytest.mark.parametrize("case", ["copy", "copy-hardlink", "copy-grow", "copy-change", "copy-ancestor", "cwd", "enter-race",
    "publication-failure", "publication-stage-owner"])
def test_shared_copy_and_fd_cwd_with_actual_files_and_subprocess(tmp_path, case):
    _run_filesystem_child(tmp_path, case)


def test_actual_held_index_lock_has_unchanged_ten_second_deadline_and_retry(tmp_path):
    root = Path(__file__).resolve().parents[2]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=os.pathsep.join(source_paths(root)))
    command = [sys.executable, "-B", str(Path(__file__).resolve()), "filesystem-child", str(tmp_path)]
    (tmp_path / "native-output-sentinel").write_bytes(b"Retained native output engineering sentinel")
    owner = subprocess.Popen([*command, "lock-owner"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 15
        while not (tmp_path / "actual-lock-held").exists() and owner.poll() is None and time.monotonic() < deadline:
            time.sleep(.01)
        assert (tmp_path / "actual-lock-held").exists()
        waiter = subprocess.run([*command, "lock-waiter"], env=env, capture_output=True, text=True, timeout=25)
        assert waiter.returncode == 0, waiter.stdout + waiter.stderr
        observed = json.loads((tmp_path / "actual-lock-wait.json").read_text())
        assert INDEX_LOCK_WAIT_SECONDS <= observed["elapsed_seconds"] <= INDEX_LOCK_WAIT_SECONDS + 5
        assert observed["deadline_seconds"] == 10.0
    finally:
        (tmp_path / "release-actual-lock").write_bytes(b"Release this owned engineering process")
        try:
            stdout, stderr = owner.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            owner.terminate()
            stdout, stderr = owner.communicate(timeout=10)
    assert owner.returncode == 0, stdout + stderr
    with LocalCalculationStore(tmp_path)._index_lock():
        assert (tmp_path / "native-output-sentinel").read_bytes() == b"Retained native output engineering sentinel"


@pytest.mark.parametrize("field,value", [("label", True), ("label", "Saved calculation 999 · GFN2-xTB · Geometry optimization"),
    ("results_relative", "/outside"), ("receipt_sha256", False), ("exclusions", [None])])
def test_malformed_record_schema_is_an_unavailable_row(tmp_path, field, value):
    from cochem_base.calc.local_publication import EXCLUSIONS, SCOPE
    store = LocalCalculationStore(tmp_path)
    store._prepare_store()
    identifier = "job_" + "1" * 32
    record = {"schema_version": "cochem.saved-local-calculation/1", "record_id": identifier,
        "results_relative": "GUI/run_" + "1" * 32 + "/Results", "receipt_sha256": "0" * 64,
        "inventory_sha256": "0" * 64, "input_context_sha256": "0" * 64,
        "label": "Saved calculation 1 · GFN2-xTB · Geometry optimization", "scope": SCOPE, "exclusions": list(EXCLUSIONS)}
    record[field] = value
    raw = canonical_json(record)
    _atomic_file(store.directory / "records", identifier + ".json", raw, immutable=True)
    _atomic_file(store.directory, "index.json", canonical_json({"schema_version": "cochem.local-calculation-index/1",
        "order": [identifier], "records": {identifier: {"path": "records/" + identifier + ".json", "sha256": digest(raw)}}}))
    rows = store.list_saved()
    assert len(rows) == 1 and not rows[0].available and rows[0].label == "Saved calculation 1 — unavailable"


def test_actual_two_process_index_admission_preserves_both_entries_and_child_authority(tmp_path):
    root = Path(__file__).resolve().parents[2]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=os.pathsep.join(source_paths(root)))
    command = [sys.executable, "-B", str(Path(__file__).resolve())]
    first = subprocess.Popen([*command, "index-child", str(tmp_path), "1"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    second = None
    try:
        deadline = time.monotonic() + 15
        while not (tmp_path / "entered-1").exists() and time.monotonic() < deadline and first.poll() is None:
            time.sleep(.01)
        assert (tmp_path / "entered-1").exists()
        second = subprocess.Popen([*command, "index-child", str(tmp_path), "2"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        deadline = time.monotonic() + 15
        while not (tmp_path / "attempt-2").exists() and time.monotonic() < deadline and second.poll() is None:
            time.sleep(.01)
        assert (tmp_path / "attempt-2").exists() and not (tmp_path / "entered-2").exists()
        (tmp_path / "release-first").write_bytes(b"Release actual file-lock owner")
        stdout, stderr = first.communicate(timeout=20)
        assert first.returncode == 0, stdout + stderr
        stdout, stderr = second.communicate(timeout=20)
        assert second.returncode == 0, stdout + stderr
    finally:
        (tmp_path / "release-first").write_bytes(b"Ensure owned children can exit")
        for process in (first, second):
            if process is not None:
                try:
                    process.communicate(timeout=20)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    process.communicate(timeout=10)
    store = LocalCalculationStore(tmp_path)
    index = store._index()
    assert index["order"] == ["job_" + "1" * 32, "job_" + "2" * 32]
    assert len(index["records"]) == 2
    assert all(not item.available for item in store.list_saved())  # Markers never become computed evidence.


def _assert_child_source():
    root = Path(__file__).resolve().parents[2]
    if os.environ.get("COCHEM_SOURCE_QUARANTINE_ROOT"):
        startup = sys.modules.get("sitecustomize")
        assert startup is not None and Path(startup.__file__).resolve() == root / "ci_tools/quarantine_startup/sitecustomize.py"
        guard = sys.modules.get("ci_tools.source_quarantine")
        assert guard is not None and guard._active["copied"] == root
    import cochem_base.calc.local_publication as publication
    import cochem_base.core.managed_files as managed
    import cochem_base.interfaces.local_calculations as records
    assert Path(publication.__file__).resolve() == root / "src/cochem_base/calc/local_publication.py"
    assert Path(records.__file__).resolve() == root / "src/cochem_base/interfaces/local_calculations.py"
    assert Path(managed.__file__).resolve() == root / "src/cochem_base/core/managed_files.py"


def _child(directory, token):
    _assert_child_source()
    store = LocalCalculationStore(directory)
    (directory / ("attempt-" + token)).write_bytes(b"Entering actual admission")
    with store._index_lock():
        (directory / ("entered-" + token)).write_bytes(b"Actual file lock acquired")
        if token == "1":
            deadline = time.monotonic() + 15
            while not (directory / "release-first").exists() and time.monotonic() < deadline:
                time.sleep(.01)
            assert (directory / "release-first").exists()
        index = store._index()
        identifier = "job_" + token * 32
        marker = canonical_json({"engineering_marker": identifier})
        _atomic_file(store.directory / "records", identifier + ".json", marker, immutable=True)
        index["records"][identifier] = {"path": "records/" + identifier + ".json", "sha256": digest(marker)}
        index["order"].append(identifier)
        _atomic_file(store.directory, "index.json", canonical_json(index))


def _directory_child(directory, replace):
    _assert_child_source()
    root = directory / "owned"
    parent = root / "subdirectory"
    parent.mkdir(parents=True)
    original = b"Original engineering file under retained parent fd"
    (parent / "evidence").write_bytes(original)
    changed = {"done": False}

    def replace_during_real_leaf_open(event, arguments):
        if not replace or changed["done"] or event != "open" or arguments[0] != "evidence":
            return
        changed["done"] = True
        parent.rename(root / "moved-original-parent")
        parent.mkdir()
        (parent / "evidence").write_bytes(b"Replacement engineering sentinel at current path")

    # Process-local scheduling at an actual os.open audit boundary. No parser,
    # filesystem function or downstream result is patched or fabricated.
    sys.addaudithook(replace_during_real_leaf_open)
    if replace:
        with pytest.raises(LocalFilesError, match="directory chain"):
            read_member(root, "subdirectory/evidence")
        assert changed["done"]
        assert (root / "moved-original-parent/evidence").read_bytes() == original
        assert (parent / "evidence").read_bytes() == b"Replacement engineering sentinel at current path"
    else:
        assert read_member(root, "subdirectory/evidence") == original
        assert not changed["done"]


def _filesystem_child(directory, case):
    _assert_child_source()
    from cochem_base.core.managed_files import (
        ManagedPathError,
        atomic_write_bytes,
        copy_regular_file,
        open_directory_chain,
        read_file_bytes,
    )
    if case in {"publication-failure", "publication-stage-owner"}:
        from cochem_base.calc.calculation_service import _publish_run_artifacts
        sandbox = directory / "sandbox"
        sandbox.mkdir()
        (sandbox / "matrix_config.validated.json").write_bytes(b'{"engineering_boundary_only":true}')
        changing = sandbox / "input.xyz"
        geometry = b"3\nPublication filesystem engineering only\nO 0 0 0\nH 0 -.757 .587\nH 0 .757 .587\n"
        changing.write_bytes(geometry)
        output = directory / "Results"
        receipt = {"status": "EXECUTION_VERIFIED", "engine": "xtb", "method": "GFN2-xTB", "operation": "single_point",
            "run_id": "job_" + "1" * 32, "dry_run": False, "config_file": str(directory / "config.json"), "output_dir": str(output)}
        config = canonical_json({"geometry": geometry.decode(), "charge": 0, "multiplicity": 1})
        observed = {"source_opened": False, "done": False, "stage": None}

        def observe_real_publication(event, args):
            if event == "os.mkdir" and isinstance(args[0], str) and args[0].startswith(".Results."):
                observed["stage"] = directory / args[0]
            if event != "open" or observed["done"]:
                return
            name = args[0]
            if case == "publication-failure":
                if name == "input.xyz":
                    observed["source_opened"] = True
                elif (observed["source_opened"] and isinstance(name, str) and name.startswith(".")
                      and name.endswith(".tmp") and args[2] & os.O_CREAT):
                    observed["done"] = True
                    with changing.open("ab") as stream:
                        stream.write(b"Actual growth after source identity capture")
            elif observed["stage"] is not None and output.is_dir() and not observed["stage"].exists():
                observed["done"] = True
                observed["stage"].mkdir(mode=0o700)
                (observed["stage"] / "new-owner-sentinel").write_bytes(b"Replacement owner after successful promotion")

        sys.addaudithook(observe_real_publication)
        if case == "publication-failure":
            with pytest.raises(ManagedPathError):
                _publish_run_artifacts(sandbox, output, retained_receipt=receipt, submitted_config=config)
            assert observed["done"] and not output.exists() and observed["stage"].is_dir()
            assert observed["stage"].stat().st_mode & 0o777 == 0o700
            assert (sandbox / "matrix_config.validated.json").read_bytes() == b'{"engineering_boundary_only":true}'
        else:
            result = _publish_run_artifacts(sandbox, output, retained_receipt=receipt, submitted_config=config)
            assert result["status"] == "EXECUTION_VERIFIED" and observed["done"]
            assert (output / "input.xyz").read_bytes() == geometry
            assert (observed["stage"] / "new-owner-sentinel").read_bytes() == b"Replacement owner after successful promotion"
        return
    if case in {"lock-owner", "lock-waiter"}:
        store = LocalCalculationStore(directory)
        if case == "lock-owner":
            with store._index_lock():
                (directory / "actual-lock-held").write_bytes(b"Production index lock acquired")
                deadline = time.monotonic() + 35
                while not (directory / "release-actual-lock").exists() and time.monotonic() < deadline:
                    time.sleep(.01)
                assert (directory / "release-actual-lock").exists()
        else:
            started = time.monotonic()
            with pytest.raises(ManagedPathError, match="history is busy"):
                with store._index_lock():
                    raise AssertionError("Held lock was incorrectly admitted")
            elapsed = time.monotonic() - started
            (directory / "actual-lock-wait.json").write_text(json.dumps({"elapsed_seconds": elapsed, "deadline_seconds": INDEX_LOCK_WAIT_SECONDS}))
        return
    if case.startswith("mutation:"):
        phase, kind = case.split(":")[1:]
        root, outside = directory / "managed", directory / "outside"
        root.mkdir()
        outside.mkdir()
        store = LocalCalculationStore(root)
        if phase != "mkdir":
            store._prepare_store()
        replacement_records = outside / "LocalCalculations" / "records"
        replacement_records.mkdir(parents=True)
        (outside / "sentinel").write_bytes(b"Outside owner sentinel")
        (replacement_records / "record.json").write_bytes(b"Outside record owner")
        (replacement_records.parent / "index.lock").write_bytes(b"Outside lock owner")
        observed = {"done": False, "temporary": None}

        def replace_at_actual_mutation(event, args):
            if observed["done"] or phase == "unchanged":
                return
            filename = args[0] if args else None
            matched = ((phase == "mkdir" and event == "os.mkdir" and filename == "LocalCalculations")
                or (phase == "lock" and event == "open" and filename == "index.lock")
                or (phase == "temp" and event == "open" and isinstance(filename, str) and filename.startswith(".") and filename.endswith(".tmp"))
                or (phase == "link" and event == "os.link") or (phase == "replace" and event == "os.rename"))
            if not matched:
                return
            observed["done"] = True
            root.rename(directory / "original-owned-root")
            if kind == "symlink":
                root.symlink_to(outside, target_is_directory=True)
            else:
                root.mkdir()
                (root / "LocalCalculations" / "records").mkdir(parents=True)
                (root / "sentinel").write_bytes(b"Replacement directory owner")
                (root / "LocalCalculations/records/record.json").write_bytes(b"Replacement record owner")
                (root / "LocalCalculations/index.lock").write_bytes(b"Replacement lock owner")
            if phase == "temp":
                target = (outside if kind == "symlink" else root) / "LocalCalculations" / "records" / filename
                target.write_bytes(b"Replacement temporary owner")
                observed["temporary"] = target

        sys.addaudithook(replace_at_actual_mutation)
        if phase == "unchanged":
            atomic_write_bytes(store.directory / "records", "record.json", b"Original owned bytes", immutable=True,
                expected_chain=store._records_chain)
            assert (store.directory / "records/record.json").read_bytes() == b"Original owned bytes"
        else:
            with pytest.raises((ManagedPathError, OSError)):
                if phase == "mkdir":
                    store._prepare_store()
                elif phase == "lock":
                    with store._index_lock():
                        raise AssertionError("Replaced ancestor was admitted")
                else:
                    atomic_write_bytes(store.directory / "records", "record.json", b"Owned mutation bytes",
                        immutable=phase == "link", expected_chain=store._records_chain)
            assert observed["done"]
            if observed["temporary"] is not None:
                assert observed["temporary"].read_bytes() == b"Replacement temporary owner"
        assert (outside / "sentinel").read_bytes() == b"Outside owner sentinel"
        assert (replacement_records / "record.json").read_bytes() == b"Outside record owner"
        assert (replacement_records.parent / "index.lock").read_bytes() == b"Outside lock owner"
        if observed["done"] and kind == "directory":
            assert (root / "sentinel").read_bytes() == b"Replacement directory owner"
            assert (root / "LocalCalculations/records/record.json").read_bytes() == b"Replacement record owner"
            assert (root / "LocalCalculations/index.lock").read_bytes() == b"Replacement lock owner"
        return
    if case == "enter-race":
        import errno
        root = directory / "before-entry"
        root.mkdir()
        outside = directory / "entry-replacement"
        outside.mkdir()
        bound = open_directory_chain(root)
        descriptor = bound.fd
        root.rename(directory / "original-before-entry")
        root.symlink_to(outside, target_is_directory=True)
        with pytest.raises((ManagedPathError, OSError)):
            with bound:
                raise AssertionError("Replaced path was incorrectly entered")
        with pytest.raises(OSError) as error:
            os.fstat(descriptor)
        assert error.value.errno == errno.EBADF
        bound.close()  # Deterministic idempotent close cannot hit a reused fd.
        return
    if case == "cwd":
        from cochem_base.core_engine.cochem_core_subprocess_broker import safe_subprocess_run
        root = directory / "owned-cwd"
        root.mkdir()
        (root / "relative-input.txt").write_bytes(b"Original bound cwd input")
        outside = directory / "outside-cwd"
        outside.mkdir()
        (outside / "relative-input.txt").write_bytes(b"Outside replacement sentinel")
        with open_directory_chain(root) as bound:
            cwd, descriptors = bound.subprocess_cwd()
            assert descriptors == (bound.fd,) and cwd.startswith(("/proc/self/fd/", "/dev/fd/"))
            expected = os.fstat(bound.fd)
            root.rename(directory / "original-cwd-moved")
            root.symlink_to(outside, target_is_directory=True)
            code = "import json,os,pathlib; s=os.stat('.'); print(json.dumps({'dev':s.st_dev,'ino':s.st_ino,'input':pathlib.Path('relative-input.txt').read_text()}))"
            completed = safe_subprocess_run([sys.executable, "-B", "-c", code], cwd=cwd, pass_fds=descriptors,
                timeout=10, required_disk_gb=0, capture_output=True, text=True)
            value = json.loads(completed.stdout)
            assert (value["dev"], value["ino"]) == (expected.st_dev, expected.st_ino)
            assert value["input"] == "Original bound cwd input"
        assert (outside / "relative-input.txt").read_bytes() == b"Outside replacement sentinel"
        return
    source_parent, destination_path = directory / "native-source", directory / "native-destination"
    source_parent.mkdir()
    destination_path.mkdir()
    source = source_parent / "scientific-data.bin"
    data = bytes(range(256)) * 4096
    source.write_bytes(data)
    source.chmod(0o400)
    os.utime(source, ns=(1_700_000_000_123456789, 1_700_000_001_987654321))
    if case == "copy-hardlink":
        (source_parent / "source-alias").hardlink_to(source)
        with pytest.raises(ManagedPathError):
            read_file_bytes(source, max_bytes=len(data))
    observed = {"done": False}

    def change_actual_copy_source(event, args):
        if observed["done"] or event != "open":
            return
        name = args[0]
        if case == "copy-ancestor" and name == source.name:
            observed["done"] = True
            source_parent.rename(directory / "original-source-moved")
            outside = directory / "outside-source"
            outside.mkdir()
            (outside / source.name).write_bytes(b"Outside source owner sentinel")
            source_parent.symlink_to(outside, target_is_directory=True)
        elif case in {"copy-grow", "copy-change"} and isinstance(name, str) and name.startswith(".") and name.endswith(".tmp"):
            observed["done"] = True
            source.chmod(0o600)
            if case == "copy-grow":
                with source.open("ab") as stream:
                    stream.write(b"Actual growth")
            else:
                with source.open("r+b") as stream:
                    stream.write(b"Z")
            os.utime(source, ns=(1_700_000_000_123456789, 1_700_000_002_987654321))

    sys.addaudithook(change_actual_copy_source)
    with open_directory_chain(destination_path) as destination:
        if case in {"copy-grow", "copy-change", "copy-ancestor"}:
            with pytest.raises((ManagedPathError, OSError)):
                copy_regular_file(source, destination, source.name)
            assert observed["done"] and not (destination_path / source.name).exists()
        else:
            before = source.stat()
            size, checksum = copy_regular_file(source, destination, source.name)
            copied = destination_path / source.name
            metadata = copied.stat()
            assert size == len(data) and checksum == digest(data)
            assert metadata.st_mode & 0o777 == before.st_mode & 0o777
            assert metadata.st_mtime_ns == before.st_mtime_ns and metadata.st_atime_ns == source.stat().st_atime_ns
            assert copied.read_bytes() == data and copied.stat().st_nlink == 1


if __name__ == "__main__":
    if sys.argv[1] == "index-child":
        _child(Path(sys.argv[2]), sys.argv[3])
    else:
        if sys.argv[1] == "directory-child":
            _directory_child(Path(sys.argv[2]), bool(int(sys.argv[3])))
        else:
            assert sys.argv[1] == "filesystem-child"
            _filesystem_child(Path(sys.argv[2]), sys.argv[3])
