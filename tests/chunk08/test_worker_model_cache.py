# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Unit test for Deliverable 5 (Suggestion #75):
Worker-Resident GPU MLFF Model Cache Singleton.
Verifies that WorkerModelCache returns the identical resident model object on
consecutive calls, initializes thread-safely, and maintains persistent model weights.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from cochem_base.core_engine.cochem_core_parsl_executors import WorkerModelCache


def test_worker_model_cache_identity_and_persistence() -> None:
    """Verify that WorkerModelCache returns identical resident model instance

    across consecutive get_model() calls and persists weights in memory.
    """
    with tempfile.TemporaryDirectory() as td:
        dummy_weights = Path(td) / "mace_model.pt"
        dummy_weights.write_bytes(b"AUTHENTIC_MODEL_WEIGHTS_COCHEM")

        # First retrieval initializes and caches the resident model
        model_1 = WorkerModelCache.get_model(
            model_name="MACE-OFF24m",
            weights_path=dummy_weights,
            device="cpu",
        )

        # Second retrieval with identical signature must return identical cached instance
        model_2 = WorkerModelCache.get_model(
            model_name="MACE-OFF24m",
            weights_path=dummy_weights,
            device="cpu",
        )

        assert model_1 is model_2
        assert id(model_1) == id(model_2)


def test_worker_model_cache_multithreaded_safety() -> None:
    """Verify thread-safety of WorkerModelCache under concurrent access."""
    import concurrent.futures

    with tempfile.TemporaryDirectory() as td:
        weights_file = Path(td) / "aimnet2_model.pt"
        weights_file.write_bytes(b"AIMNET2_WEIGHTS_COCHEM")

        def _fetch_model() -> int:
            m = WorkerModelCache.get_model(
                model_name="AIMNet2",
                weights_path=weights_file,
                device="cpu",
            )
            return id(m)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(_fetch_model) for _ in range(20)]
            model_ids = [f.result() for f in futures]

        # All threads must receive the exact same singleton instance
        assert len(set(model_ids)) == 1
