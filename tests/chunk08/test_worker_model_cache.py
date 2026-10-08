"""Resident-cache identity on the genuine official MACE-OFF24 medium checkpoint.

This opt-in ML profile requires its approved scientific silo and checksum-pinned
checkpoint; arbitrary bytes are not model evidence and never replace it.
"""
from __future__ import annotations
import concurrent.futures
import hashlib
import os
from pathlib import Path
import pytest
from cochem_base.core_engine.cochem_core_parsl_executors import WorkerModelCache

CHECKPOINT_SHA256 = 'e5ccf5837f685899811a68754e7c994393bfd1a81720393b03c643b46c70bc69'

@pytest.fixture
def official_checkpoint():
    value = os.environ.get('COCHEM_MACE_OFF24_CHECKPOINT')
    if not value:
        pytest.fail('The real ML cache profile requires COCHEM_MACE_OFF24_CHECKPOINT and its approved MACE/Torch silo')
    path = Path(value).resolve(strict=True)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == CHECKPOINT_SHA256
    WorkerModelCache.clear()
    yield path
    WorkerModelCache.clear()

def test_worker_model_cache_identity_and_persistence(official_checkpoint):
    first = WorkerModelCache.get_model('MACE-OFF24m', official_checkpoint, 'cpu')
    second = WorkerModelCache.get_model('MACE-OFF24m', official_checkpoint, 'cpu')
    assert first is second
    assert first.weights_path == official_checkpoint
    assert callable(first.model_instance)
    assert type(first.model_instance).__module__.startswith('mace.')

def test_worker_model_cache_multithreaded_safety(official_checkpoint):
    def retrieve():
        model = WorkerModelCache.get_model('MACE-OFF24m', official_checkpoint, 'cpu')
        assert callable(model.model_instance)
        return id(model)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        identifiers = list(executor.map(lambda _: retrieve(), range(20)))
    assert len(set(identifiers)) == 1
    assert hashlib.sha256(official_checkpoint.read_bytes()).hexdigest() == CHECKPOINT_SHA256
