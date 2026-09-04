"""Zero-Mock Architecture, Provenance, Hardware & Concurrency Test Suite (Part 6).

Validates Suggestions #53, #57, #58, and #59.
Adheres strictly to Method Matrix v4 and Zero-Mock Anti-Spoofing Protocol v2.
Real physical execution: authentic JSON-LD local schemas, genuine NVML hardware checks,
real HDF5 SWMR files, and node-local scratch locking.
"""

from __future__ import annotations

import json
import os
import pathlib
import threading
import time
from typing import List

import h5py

from cochem_base.core.cochem_provenance import DAGNode, get_local_prov_context
from cochem_base.core.cochem_version import get_vcs_provenance
from cochem_base.core.metadata import collect_hardware_metadata
from cochem_base.core_engine.cochem_core_pes_store import (
    PESPointRecord,
    PESStore,
)


def test_w3c_prov_o_jsonld_serialization() -> None:
    """Validate W3C PROV-O JSON-LD conformer lineage serialization and air-gapped context resolution (Suggestion #53)."""
    # 1. Verify offline local context resolution
    context_doc = get_local_prov_context()
    assert "@context" in context_doc
    ctx = context_doc["@context"]
    assert ctx.get("prov") == "http://www.w3.org/ns/prov#"
    assert ctx.get("cochem") == "https://cochem.org/schema/core#"
    assert "wasDerivedFrom" in ctx
    assert "wasGeneratedBy" in ctx

    # 2. Instantiate DAGNode for an activity (optimization step)
    activity_node = DAGNode(
        node_id="opt_step_001",
        node_type="activity",
        activity_type="cochem:Optimization",
        started_at_time="2026-09-04T00:00:00Z",
        ended_at_time="2026-09-04T00:01:30Z",
        metadata={"engine": "ORCA", "method": "wB97M-V", "basis": "def2-TZVP"},
    )
    act_jsonld = activity_node.to_prov_jsonld()
    assert act_jsonld["@id"] == "urn:cochem:conformer:opt_step_001"
    assert "prov:Activity" in act_jsonld["@type"]
    assert "cochem:Optimization" in act_jsonld["@type"]
    assert act_jsonld["prov:startedAtTime"] == "2026-09-04T00:00:00Z"
    assert act_jsonld["prov:endedAtTime"] == "2026-09-04T00:01:30Z"

    # 3. Instantiate DAGNode for an entity (resulting conformer)
    conformer_node = DAGNode(
        node_id="conf_c2h6_min01",
        node_type="entity",
        parents=["conf_initial_guess"],
        activity="opt_step_001",
        relative_energy_kcal_mol=0.0,
        rotational_constants_mhz=[199824.5, 199824.1, 199820.0],
        metadata={"multiplicity": 1, "charge": 0},
    )
    conf_jsonld = conformer_node.to_prov_jsonld()
    assert conf_jsonld["@id"] == "urn:cochem:conformer:conf_c2h6_min01"
    assert "prov:Entity" in conf_jsonld["@type"]
    assert "cochem:Conformer" in conf_jsonld["@type"]
    assert conf_jsonld["prov:wasDerivedFrom"] == [{"@id": "urn:cochem:conformer:conf_initial_guess"}]
    assert conf_jsonld["prov:wasGeneratedBy"] == {"@id": "urn:cochem:activity:opt_step_001"}
    assert conf_jsonld["cochem:relativeEnergy"] == 0.0
    assert conf_jsonld["cochem:rotationalConstants"] == [199824.5, 199824.1, 199820.0]

    # Verify standard JSON serialization succeeds
    serialized = json.dumps(conf_jsonld)
    assert "urn:cochem:conformer:conf_c2h6_min01" in serialized


def test_vcs_provenance_container_introspection(tmp_path: pathlib.Path) -> None:
    """Validate dynamic VCS provenance and importlib.metadata distribution fallback (Suggestion #57)."""
    # 1. In a directory without .git, verify fallback to importlib.metadata
    isolated_dir = tmp_path / "stripped_container_root"
    isolated_dir.mkdir(parents=True, exist_ok=True)

    prov = get_vcs_provenance(root_path=isolated_dir)
    assert isinstance(prov, dict)
    assert "status" in prov
    # Since CoChem-BASE is installed in this python environment, status must be DISTRIBUTION_PACKAGE
    assert prov["status"] == "DISTRIBUTION_PACKAGE"
    assert prov["vcs_type"] == "installed_wheel"
    assert "version" in prov
    assert len(prov["version"]) > 0
    assert "installer" in prov
    assert "file_count" in prov
    assert prov["file_count"] > 0

    # 2. When executed from repo root with .git present, queries commit information
    repo_prov = get_vcs_provenance()
    assert isinstance(repo_prov, dict)
    assert "status" in repo_prov
    assert repo_prov["status"] in ("GIT_REPOSITORY", "DISTRIBUTION_PACKAGE")


def test_strictly_non_initializing_gpu_telemetry() -> None:
    """Validate strictly non-initializing GPU telemetry with zero CUDA context locking (Suggestion #58)."""
    # 1. Execute collect_hardware_metadata
    hw_info = collect_hardware_metadata()
    assert isinstance(hw_info, dict)
    assert "cpu" in hw_info
    assert "architecture" in hw_info["cpu"]
    assert "physical_cores" in hw_info["cpu"]
    assert "gpus" in hw_info
    assert isinstance(hw_info["gpus"], list)

    # 2. Zero-CUDA-Locking Invariant Mandate
    # Check if torch is in sys.modules, and if so, verify that CUDA was not initialized
    import sys
    if "torch" in sys.modules:
        import torch
        assert not torch.cuda.is_initialized(), "torch.cuda was initialized during hardware metadata collection!"


def test_pes_store_swmr_concurrency_and_local_locking(tmp_path: pathlib.Path) -> None:
    """Validate thread-safe SWMR HDF5 execution and node-local scratch FileLock enforcement (Suggestion #59)."""
    h5_file = tmp_path / "pes_swmr_test.h5"
    scratch_dir = tmp_path / "node_local_scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    # Set SLURM_TMPDIR to test local scratch lockfile redirection
    os.environ["SLURM_TMPDIR"] = str(scratch_dir.resolve())
    try:
        # 1. Initialize PESStore in SWMR mode
        store = PESStore(
            path=h5_file,
            complex_name="CO_H2O",
            symbols=["C", "O", "H", "H", "O"],
            swmr_mode=True,
        )

        # 2. Verify lockfile directory is placed in node-local scratch, not shared storage
        assert store.lock_dir.resolve() == scratch_dir.resolve()
        assert str(scratch_dir.resolve()) in str(store.lock_path.resolve())

        # 3. Concurrent read and write execution
        symbols = ["C", "O", "H", "H", "O"]
        base_coords = [0.0, 0.0, 0.0, 0.0, 0.0, 1.13, 2.0, 0.0, 0.0, 2.5, 0.7, 0.0, 2.5, -0.7, 0.0]
        method = "wB97M-V"
        basis = "def2-TZVP"

        # Register method first
        store.register_method(method_id="wb97mv_tzvp", method=method, basis=basis)

        written_points: List[str] = []
        errors: List[Exception] = []

        def worker_writer(thread_idx: int, num_pts: int) -> None:
            for i in range(num_pts):
                try:
                    # Deterministic perturbed geometry
                    geom = [c + 0.01 * (thread_idx + 1) * (i + 1) for c in base_coords]
                    pt = PESPointRecord(
                        coordinates=geom,
                        symbols=symbols,
                        method=method,
                        basis=basis,
                        method_id="wb97mv_tzvp",
                        energy=-189.12345 + 0.001 * (thread_idx + i),
                    )
                    store.add_point(pt)
                    written_points.append(pt.point_id)
                except Exception as exc:
                    errors.append(exc)

        def worker_reader(num_reads: int) -> None:
            for _ in range(num_reads):
                try:
                    pts = store.get_all_point_ids()
                    assert isinstance(pts, list)
                    time.sleep(0.005)
                except Exception as exc:
                    errors.append(exc)

        threads: List[threading.Thread] = []
        # Launch 3 writer threads and 2 reader threads
        for t_idx in range(3):
            t = threading.Thread(target=worker_writer, args=(t_idx, 5))
            threads.append(t)
        for _ in range(2):
            t = threading.Thread(target=worker_reader, args=(10,))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Encountered concurrency errors: {errors}"
        all_ids = store.get_all_point_ids()
        assert len(all_ids) == 15
        for pid in written_points:
            assert pid in all_ids

        # Verify dataset integrity and absence of B-tree corruption
        with h5py.File(h5_file, "r", libver="latest", swmr=True) as f:
            coords = f["/points/coordinates"]
            coords.refresh()
            assert coords.shape[0] == 15
            energies = f["/points/energies"]
            energies.refresh()
            assert energies.shape[0] == 15

    finally:
        os.environ.pop("SLURM_TMPDIR", None)
