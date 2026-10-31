"""Shared fixtures backed by the current machine and real filesystem state."""

import json
import os
from pathlib import Path

import psutil
import pytest


@pytest.fixture(scope="session", autouse=True)
def pinned_pip_test_artifact(request, tmp_path_factory):
    """Deliver the real verified tool only to collected installer test modules."""
    affected = {
        "base/test_module_installer.py",
        "base/test_student_setup.py",
        "base/test_pinned_pip_runtime.py",
        "base/test_pip_command_context.py",
        "base/test_module_execution.py",
        "base/test_module_generation_compatibility.py",
        "test_bootstrap_environment.py",
    }
    tests = Path(__file__).parent
    selected = any(Path(item.path).is_relative_to(tests)
                   and Path(item.path).relative_to(tests).as_posix() in affected
                   for item in request.session.items)
    if not selected:
        yield None
        return
    # Import/obtain bytes only for the actual selected installation controls.
    # This is the production trust policy, not another downloader or pip shim.
    from scripts import manage_modules as installer

    previous = os.environ.get("COCHEM_PINNED_PIP_WHEEL")
    try:
        data = installer._pinned_pip_bytes(env=dict(os.environ), timeout=30)
        if previous is not None:
            artifact = Path(previous).absolute()
        else:
            artifact = tmp_path_factory.mktemp("pinned-pip") / installer.PINNED_PIP_FILENAME
            artifact.write_bytes(data)
            artifact.chmod(0o400)
        os.environ["COCHEM_PINNED_PIP_WHEEL"] = str(artifact)
        yield artifact
    finally:
        if previous is None:
            os.environ.pop("COCHEM_PINNED_PIP_WHEEL", None)
        else:
            os.environ["COCHEM_PINNED_PIP_WHEEL"] = previous


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
