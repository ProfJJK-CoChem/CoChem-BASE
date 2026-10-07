"""Shared fixtures backed by the current machine and real filesystem state."""

import json
import os

import psutil
import pytest


@pytest.fixture
def audited_registry(tmp_path):
    """Persist actual host hardware bounds for execution-router integration tests."""
    path = tmp_path / "cochem_system_config.json"
    path.write_text(json.dumps({
        "hardware": {
            "physical_cpu_cores": psutil.cpu_count(logical=False),
            "logical_cpu_cores": psutil.cpu_count(logical=True),
            "ram_gb": psutil.virtual_memory().total / 1024**3,
        },
        "execution": {"default_engine": "subprocess"},
    }), encoding="utf-8")
    return path


@pytest.fixture
def configured_registry(audited_registry):
    """Select a real host audit file, restoring the caller's binding afterwards."""
    previous = os.environ.get("COCHEM_CONFIG")
    os.environ["COCHEM_CONFIG"] = str(audited_registry)
    try:
        yield audited_registry
    finally:
        if previous is None:
            os.environ.pop("COCHEM_CONFIG", None)
        else:
            os.environ["COCHEM_CONFIG"] = previous
