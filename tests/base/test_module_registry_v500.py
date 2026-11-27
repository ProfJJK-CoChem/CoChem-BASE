"""Unit tests for CoChem-BASE v5.0.0 package ownership and module registry contracts (sys-1126-a3d4)."""
from __future__ import annotations

from pathlib import Path
import warnings

import pytest

import cochem_base
from cochem_base.interfaces.artifact_handoff import prepare_module_handoff
from cochem_base.interfaces.module_registry import (
    ModuleStatus,
    ModuleUnavailableError,
    assert_module_dispatchable,
    canonical_module_id,
    dispatch_module,
    get_module_capability,
    list_module_capabilities,
)


def test_cochem_base_is_real_package_with_reexport_parity() -> None:
    assert cochem_base.__file__ is not None
    assert Path(cochem_base.__file__).name == "__init__.py"
    assert isinstance(cochem_base.__version__, str) and len(cochem_base.__version__) > 0
    assert cochem_base.__license__ == "Apache-2.0"

    runtime = cochem_base.check_runtime_environment()
    assert runtime["version"] == cochem_base.__version__
    assert runtime["tier"] in {
        "LOCAL_WORKSTATION",
        "WSL2_WORKSTATION",
        "HPC_CLUSTER",
        "CI_PIPELINE",
        "CODESPACES",
    }
    assert hasattr(cochem_base, "interfaces")
    assert hasattr(cochem_base, "schemas")
    assert hasattr(cochem_base, "provenance")


def test_canonical_spyfy_without_warning() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert canonical_module_id("spyfy") == "spyfy"
        assert canonical_module_id("CoChem-SPYFY") == "spyfy"
    dep_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert dep_warnings == []

    cap = get_module_capability("spyfy")
    assert cap.module_id == "spyfy"
    assert cap.name == "CoChem-SPYFY"


def test_legacy_spycfit_alias_emits_deprecation_warning() -> None:
    with pytest.warns(DeprecationWarning, match="spyfy"):
        resolved = canonical_module_id("spycfit")
    assert resolved == "spyfy"

    with pytest.warns(DeprecationWarning, match="spyfy"):
        resolved_prefixed = canonical_module_id("CoChem-SPYCFIT")
    assert resolved_prefixed == "spyfy"


def test_orb_marked_unimplemented_and_dispatch_raises_module_unavailable(tmp_path: Path) -> None:
    assert issubclass(ModuleUnavailableError, RuntimeError)
    assert cochem_base.interfaces.ModuleUnavailableError is ModuleUnavailableError

    cap = get_module_capability("orb")
    assert cap.module_id == "orb"
    assert cap.name == "CoChem-ORB"
    assert cap.status == ModuleStatus.UNIMPLEMENTED
    assert cap.status.value == "UNIMPLEMENTED"
    assert cap.execution_verified is False

    with pytest.raises(ModuleUnavailableError, match="UNIMPLEMENTED"):
        assert_module_dispatchable("orb")

    with pytest.raises(ModuleUnavailableError, match="UNIMPLEMENTED"):
        dispatch_module("orb", "run_single_point")

    geom = tmp_path / "h2.xyz"
    geom.write_text("2\nH2\nH 0.0 0.0 0.0\nH 0.0 0.0 0.74\n", encoding="utf-8")
    with pytest.raises(ModuleUnavailableError, match="UNIMPLEMENTED"):
        prepare_module_handoff("orb", geom, tmp_path / "orb_handoff", operation="ingest")


def test_phantom_dock_removed_raises_value_error() -> None:
    listed_ids = {cap.module_id for cap in list_module_capabilities()}
    assert "dock" not in listed_ids
    assert "spycfit" not in listed_ids
    assert "spyfy" in listed_ids
    assert "orb" in listed_ids

    with pytest.raises(ValueError, match="Unknown ecosystem module"):
        canonical_module_id("dock")

    with pytest.raises(ValueError, match="Unknown ecosystem module"):
        get_module_capability("CoChem-DOCK")

    with pytest.raises(ValueError, match="Unknown ecosystem module"):
        dispatch_module("dock", "status")
