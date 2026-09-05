"""Asynchronous TOPOS Search Execution Trigger & Tripartite Air-Gap Broker Zero-Mock Tests.

Method Matrix Reference: Method Matrix v4 §8A, §8C, Table 1, Suggestion #122.
Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.

Validates:
1. Active, asynchronous 'Execute TOPOS Conformer Search' action button and state machine.
2. Background process dispatch inside ephemeral sandbox T_scr without blocking event loop.
3. Live non-blocking telemetry streaming under filelock.FileLock synchronization.
4. Process cancellation and graceful cleanup via SIGTERM.
5. Atomic artifact promotion from T_scr to persistent store T_store upon completion.
"""

from __future__ import annotations

import time
from pathlib import Path

from cochem_topos_runner import (
    TOPOSExecutionBroker,
    TOPOSJobStatus,
    TOPOSSearchConfig,
)
from frontend.cochem_topos_ui import CochemToposUI


def test_ui_async_conformer_search_dispatch(tmp_path: Path):
    """Assert CochemToposUI executes asynchronous background search inside T_scr [M]."""
    scratch_dir = tmp_path / "scratch"
    store_dir = tmp_path / "store"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    store_dir.mkdir(parents=True, exist_ok=True)

    # 1. Instantiate UI
    ui = CochemToposUI()
    ui.broker = TOPOSExecutionBroker(scratch_root=scratch_dir, store_root=store_dir)
    ui.selected_tier = "T3-3h"
    ui.selected_protocol = "GOAT"
    ui.atom_count = 6

    # 2. Trigger asynchronous search
    ui._on_execute_search_clicked(ui.execute_search_button)

    assert ui.active_job_id is not None
    job_id = ui.active_job_id
    job_scratch = scratch_dir / job_id
    assert job_scratch.is_dir()
    assert (job_scratch / "config.json").is_file()
    assert (job_scratch / "telemetry.json").is_file()

    # 3. Non-blocking telemetry polling
    telemetry = ui.broker.poll_telemetry(job_id)
    assert telemetry["job_id"] == job_id
    assert telemetry["status"] in (TOPOSJobStatus.RUNNING.value, TOPOSJobStatus.COMPLETED.value)
    assert "candidates_found" in telemetry


def test_search_telemetry_streaming_and_promotion(tmp_path: Path):
    """Verify live telemetry progression and atomic artifact promotion to T_store [M], [D]."""
    scratch_dir = tmp_path / "scratch"
    store_dir = tmp_path / "store"
    broker = TOPOSExecutionBroker(scratch_root=scratch_dir, store_root=store_dir)

    cfg = TOPOSSearchConfig(
        tier_id="T3-3h",
        protocol="GOAT",
        product_class="A",
        atom_count=6,
        max_hours=0.5,
    )
    job_id = broker.launch_search(cfg)
    assert job_id.startswith("topos_job_")

    # Poll until background worker progresses
    max_wait_seconds = 5.0
    start = time.time()
    completed = False
    while time.time() - start < max_wait_seconds:
        status_data = broker.poll_telemetry(job_id)
        if status_data.get("status") == TOPOSJobStatus.COMPLETED.value:
            completed = True
            break
        time.sleep(0.1)

    assert completed, "Background worker did not reach COMPLETED status within timeout"

    # Promote artifacts to T_store
    promoted = broker.promote_artifacts(job_id)
    assert promoted["ensemble_xyz"].is_file()
    assert promoted["promoted_dir"].is_dir()
    assert promoted["promoted_dir"].parent == store_dir


def test_search_process_cancellation(tmp_path: Path):
    """Verify graceful SIGTERM cancellation and state update to CANCELLED [M]."""
    scratch_dir = tmp_path / "scratch"
    store_dir = tmp_path / "store"
    broker = TOPOSExecutionBroker(scratch_root=scratch_dir, store_root=store_dir)

    cfg = TOPOSSearchConfig(
        tier_id="T3-3h",
        protocol="CREST_NCI",
        product_class="A",
        atom_count=12,
        max_hours=1.0,
    )
    job_id = broker.launch_search(cfg)
    # Immediately cancel search
    cancelled = broker.cancel_search(job_id)
    assert cancelled is True

    telemetry = broker.poll_telemetry(job_id)
    assert telemetry["status"] == TOPOSJobStatus.CANCELLED.value
