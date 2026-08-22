"""
Physical Unit and Integration Test Suite for CoChem Core Registry Manager.
Verifies HDF5 state registry, atomic file locking, Mendeleev dynamic queries,
lineage UUID tracking, PRNG seed locking, basis set archival, schema migration,
and comprehensive exception invariants.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict
import pytest
from pydantic import BaseModel, Field

from core_engine.cochem_core_registry_manager import (
    BasisSetNotFoundError,
    IsotopeStabilityError,
    RecordNotFoundError,
    RegistryError,
    RegistryLockError,
    RegistryManager,
    SchemaMigrationError,
)


class SampleJobModel(BaseModel):
    command: list[str] = Field(default_factory=lambda: ["echo", "test"])
    product_class: str = "Product_A"
    atom_count: int = 12
    converged: bool = True


class SampleHardwareModel(BaseModel):
    cpu_cores: int = 8
    ram_gb: float = 32.0
    gpu_profile: str = "RTX_4090"


def test_registry_initialization_and_topology(tmp_path: Path):
    reg_file = tmp_path / "registry.h5"
    rm = RegistryManager(registry_path=str(reg_file))
    assert Path(rm.registry_path).exists()
    assert Path(rm.lock_path) == Path(str(reg_file) + ".lock")

    stats = rm.get_registry_stats()
    assert stats["jobs_count"] == 0
    assert stats["hardware_profiles_count"] == 0
    assert stats["provenance_count"] == 0
    assert stats["basis_sets_count"] == 0
    assert stats["seeds_count"] == 0
    assert stats["version"] == RegistryManager.SCHEMA_VERSION

    # Re-initialization on existing registry
    rm2 = RegistryManager(registry_path=str(reg_file))
    assert rm2.get_registry_stats()["version"] == RegistryManager.SCHEMA_VERSION


def test_transaction_context_manager(tmp_path: Path):
    reg_file = tmp_path / "trans_test.h5"
    rm = RegistryManager(registry_path=str(reg_file))

    with rm.transaction("a") as h5:
        assert "jobs" in h5
        assert "provenance" in h5
        h5["metadata"].attrs["custom_test_key"] = "test_value"

    with rm.transaction("r") as h5:
        assert h5["metadata"].attrs["custom_test_key"] == "test_value"


def test_mendeleev_isotopic_mass_resolution():
    # Common elements without explicit mass number (most abundant)
    mass_c = RegistryManager.get_isotopic_mass("C")
    assert isinstance(mass_c, float)
    assert 11.99 < mass_c < 12.02

    mass_h = RegistryManager.get_isotopic_mass("H")
    assert isinstance(mass_h, float)
    assert 1.007 < mass_h < 1.009

    # Explicit isotopes
    mass_c12 = RegistryManager.get_isotopic_mass("C", 12)
    assert mass_c12 == 12.0

    mass_c13 = RegistryManager.get_isotopic_mass("C", 13)
    assert 13.003 < mass_c13 < 13.004

    mass_h2 = RegistryManager.get_isotopic_mass("H", 2)
    assert 2.014 < mass_h2 < 2.015

    # Case insensitivity and whitespace handling
    mass_n = RegistryManager.get_isotopic_mass("  n  ")
    assert 14.00 < mass_n < 14.01


def test_mendeleev_error_handling():
    # Non-existent element
    with pytest.raises(IsotopeStabilityError):
        RegistryManager.get_isotopic_mass("NonExistentElement123")

    # Non-existent isotope of real element
    with pytest.raises(ValueError, match="not found in Mendeleev database"):
        RegistryManager.get_isotopic_mass("C", 999)

    # Invalid mass number type
    with pytest.raises(ValueError, match="Mass number must be an integer"):
        RegistryManager.get_isotopic_mass("C", "invalid")  # type: ignore

    # Empty or invalid symbols
    with pytest.raises(ValueError):
        RegistryManager.get_isotopic_mass("")
    with pytest.raises(ValueError):
        RegistryManager.get_isotopic_mass(None)  # type: ignore


def test_get_all_isotopes():
    c_isotopes = RegistryManager.get_all_isotopes("C")
    assert isinstance(c_isotopes, list)
    assert len(c_isotopes) > 0
    mass_numbers = [iso["mass_number"] for iso in c_isotopes]
    assert 12 in mass_numbers
    assert 13 in mass_numbers

    # Invalid symbols
    with pytest.raises(ValueError):
        RegistryManager.get_all_isotopes("")
    with pytest.raises(IsotopeStabilityError):
        RegistryManager.get_all_isotopes("InvalidElement999")


def test_job_registration_and_lifecycle(tmp_path: Path):
    reg_file = tmp_path / "jobs_reg.h5"
    rm = RegistryManager(registry_path=str(reg_file))

    # Invalid job_id
    with pytest.raises(ValueError):
        rm.register_job("", {"status": "pending"})
    with pytest.raises(ValueError):
        rm.register_job(None, {"status": "pending"})  # type: ignore

    # Register via dict
    job1_data = {
        "command": ["orca", "calc.inp"],
        "status": "submitted",
        "nested_meta": {"tier": 3, "tags": ["opt", "freq"]},
        "walltime_limit": 3600,
        "null_val": None,
    }
    rm.register_job("job_001", job1_data)

    # Retrieve job
    rec = rm.get_job("job_001")
    assert rec is not None
    assert rec["command"] == ["orca", "calc.inp"]
    assert rec["status"] == "submitted"
    assert rec["nested_meta"] == {"tier": 3, "tags": ["opt", "freq"]}
    assert rec["walltime_limit"] == 3600
    assert rec["null_val"] is None
    assert "registered_at" in rec

    # Register via Pydantic model
    job2_model = SampleJobModel(product_class="Product_C", atom_count=24)
    rm.register_job("job_002", job2_model)
    rec2 = rm.get_job("job_002")
    assert rec2 is not None
    assert rec2["product_class"] == "Product_C"
    assert rec2["atom_count"] == 24
    assert rec2["converged"] is True

    # Update job status
    rm.update_job_status("job_001", "completed", return_code=0, energy=-154.234)
    updated = rm.get_job("job_001")
    assert updated is not None
    assert updated["status"] == "completed"
    assert updated["return_code"] == 0
    assert updated["energy"] == -154.234
    assert "updated_at" in updated

    # Update non-existent job
    with pytest.raises(ValueError, match="Cannot update status for non-existent job"):
        rm.update_job_status("non_existent_job", "running")

    # Get non-existent job
    assert rm.get_job("non_existent_job") is None

    # Get all jobs
    all_jobs = rm.get_all_jobs()
    assert len(all_jobs) == 2
    job_ids = [j["job_id"] for j in all_jobs]
    assert "job_001" in job_ids
    assert "job_002" in job_ids

    # Delete job
    assert rm.delete_job("job_001") is True
    assert rm.get_job("job_001") is None
    assert rm.delete_job("job_001") is False


def test_hardware_profiles_lifecycle(tmp_path: Path):
    reg_file = tmp_path / "hw_reg.h5"
    rm = RegistryManager(registry_path=str(reg_file))

    # Invalid profile_id
    with pytest.raises(ValueError):
        rm.register_hardware_profile("", {"host": "node1"})

    # Register via dict
    hw_dict = {
        "host": "node-01",
        "physical_cores": 16,
        "ram_gb": 64.0,
        "features": ["avx512", "cuda"],
    }
    rm.register_hardware_profile("hw_node1", hw_dict)

    # Register via Pydantic
    hw_model = SampleHardwareModel(cpu_cores=32, ram_gb=128.0, gpu_profile="A100")
    rm.register_hardware_profile("hw_node2", hw_model)

    # Retrieval
    p1 = rm.get_hardware_profile("hw_node1")
    assert p1 is not None
    assert p1["physical_cores"] == 16
    assert p1["features"] == ["avx512", "cuda"]

    p2 = rm.get_hardware_profile("hw_node2")
    assert p2 is not None
    assert p2["cpu_cores"] == 32
    assert p2["gpu_profile"] == "A100"

    # Non-existent profile
    assert rm.get_hardware_profile("hw_missing") is None

    # Get all
    all_hw = rm.get_all_hardware_profiles()
    assert len(all_hw) == 2

    # Deletion
    assert rm.delete_hardware_profile("hw_node1") is True
    assert rm.delete_hardware_profile("hw_node1") is False
    assert rm.get_hardware_profile("hw_node1") is None


def test_provenance_and_lineage_chain(tmp_path: Path):
    reg_file = tmp_path / "prov_reg.h5"
    rm = RegistryManager(registry_path=str(reg_file))

    # Invalid record_id
    with pytest.raises(ValueError):
        rm.add_provenance_record("", {"action": "test"})

    # Add root record
    root_uuid = rm.add_provenance_record("root_calc", {
        "step": "geometry_opt",
        "software": "orca-6.1",
        "parameters": {"functional": "r2SCAN-3c"},
    })
    assert root_uuid.startswith("lin_")

    # Add child record
    child_uuid = rm.add_provenance_record("freq_calc", {
        "step": "vibrational_frequencies",
        "parent_uuid": root_uuid,
        "software": "orca-6.1",
    })
    assert child_uuid.startswith("lin_")

    # Add grandchild record
    grandchild_uuid = rm.add_provenance_record("rot_const_derivation", {
        "step": "vpt2_analysis",
        "parent_uuid": child_uuid,
        "software": "cochem-core",
    })

    # Retrieve single record
    rec = rm.get_provenance_record("freq_calc")
    assert rec is not None
    assert rec["step"] == "vibrational_frequencies"
    assert rec["parent_uuid"] == root_uuid

    # Trace lineage chain from leaf
    chain = rm.get_lineage_chain("rot_const_derivation")
    assert len(chain) == 3
    assert chain[0]["record_id"] == "rot_const_derivation"
    assert chain[1]["record_id"] == "freq_calc"
    assert chain[2]["record_id"] == "root_calc"

    # Get all records
    all_recs = rm.get_all_provenance_records()
    assert len(all_recs) == 3

    # Delete record
    assert rm.delete_provenance_record("rot_calc_missing") is False
    assert rm.delete_provenance_record("rot_const_derivation") is True
    assert rm.get_provenance_record("rot_const_derivation") is None


def test_prng_seed_locking_and_verification(tmp_path: Path):
    reg_file = tmp_path / "seed_reg.h5"
    rm = RegistryManager(registry_path=str(reg_file))

    # Lock global and local seeds
    s1 = rm.lock_prng_seed(42, scope="global", metadata={"purpose": "rdkit_conformer"})
    s2 = rm.lock_prng_seed(1337, scope="quantum_monte_carlo")

    assert s1 == 42
    assert s2 == 1337

    # Retrieve
    assert rm.get_locked_seed("global") == 42
    assert rm.get_locked_seed("quantum_monte_carlo") == 1337
    assert rm.get_locked_seed("unlocked_scope") is None

    # Verification
    assert rm.verify_prng_seed(42, "global") is True
    assert rm.verify_prng_seed(999, "global") is False
    assert rm.verify_prng_seed(42, "unlocked_scope") is False

    # List all
    seeds = rm.list_locked_seeds()
    assert seeds["global"] == 42
    assert seeds["quantum_monte_carlo"] == 1337

    # Invalid seed input
    with pytest.raises(ValueError):
        rm.lock_prng_seed("not_an_int")  # type: ignore


def test_embedded_basis_set_archival(tmp_path: Path):
    reg_file = tmp_path / "basis_reg.h5"
    rm = RegistryManager(registry_path=str(reg_file))

    basis_content = """! def2-TZVP basis set
C 0
S 3 1.00
  100.0 0.1
  20.0 0.2
  5.0 0.7
"""
    basis_file = tmp_path / "def2-tzvp.basis"
    basis_file.write_text(basis_content, encoding="utf-8")

    # Invalid label
    with pytest.raises(ValueError):
        rm.embed_basis_set_archive(str(reg_file), str(basis_file), "")

    # Non-existent file when is_content=False
    with pytest.raises(FileNotFoundError):
        rm.embed_basis_set_archive(str(reg_file), "non_existent_file_path.basis", "bad_basis", is_content=False)

    # Embed via file path
    rm.embed_basis_set_archive(
        h5_path=str(reg_file),
        basis_file_path=str(basis_file),
        label="def2-TZVP",
        is_content=False,
    )

    # Embed directly via raw content
    rm.embed_basis_set_archive(
        h5_path=str(reg_file),
        basis_file_path="! cc-pVDZ basis set\nH 0\nS 2 1.00\n",
        label="cc-pVDZ",
        is_content=True,
    )

    # Verify presence
    assert rm.has_embedded_basis_set("def2-TZVP") is True
    assert rm.has_embedded_basis_set("cc-pVDZ") is True
    assert rm.has_embedded_basis_set("non_existent_basis") is False

    # Retrieve content
    retrieved = rm.get_embedded_basis_set("def2-TZVP")
    assert "! def2-TZVP basis set" in retrieved

    # List all
    basis_list = rm.list_embedded_basis_sets()
    assert "def2-TZVP" in basis_list
    assert "cc-pVDZ" in basis_list

    # Delete
    assert rm.delete_embedded_basis_set("cc-pVDZ") is True
    assert rm.has_embedded_basis_set("cc-pVDZ") is False
    assert rm.delete_embedded_basis_set("cc-pVDZ") is False

    # Retrieve non-existent basis set
    with pytest.raises(BasisSetNotFoundError):
        rm.get_embedded_basis_set("non_existent")


def test_legacy_schema_migration(tmp_path: Path):
    import h5py
    reg_file = tmp_path / "legacy_registry.h5"

    # Create a bare legacy HDF5 file with version 0.1 and only jobs group
    with h5py.File(reg_file, "w") as h5:
        h5.attrs["version"] = "0.1"
        h5.create_group("jobs")

    rm = RegistryManager(registry_path=str(reg_file))
    report = rm.migrate_legacy_schema()

    assert report["previous_version"] == "0.1"
    assert report["current_version"] == RegistryManager.SCHEMA_VERSION

    # Verify newly created groups exist
    with rm.transaction("r") as h5:
        assert h5.attrs["version"] == RegistryManager.SCHEMA_VERSION
        assert "hardware_profiles" in h5
        assert "provenance" in h5
        assert "embedded_basis_sets" in h5
        assert "seeds" in h5


def test_metadata_arbitrary_key_values(tmp_path: Path):
    reg_file = tmp_path / "meta_reg.h5"
    rm = RegistryManager(registry_path=str(reg_file))

    rm.set_metadata("pipeline_run_id", "pipe_98765")
    rm.set_metadata("convergence_criteria", {"tol_e": 1e-6, "tol_g": 1e-4})
    rm.set_metadata("is_production", True)

    assert rm.get_metadata("pipeline_run_id") == "pipe_98765"
    assert rm.get_metadata("convergence_criteria") == {"tol_e": 1e-6, "tol_g": 1e-4}
    assert rm.get_metadata("is_production") is True
    assert rm.get_metadata("non_existent_key", default="fallback") == "fallback"


def test_custom_exception_hierarchy():
    assert issubclass(IsotopeStabilityError, RegistryError)
    assert issubclass(RegistryLockError, RegistryError)
    assert issubclass(RecordNotFoundError, RegistryError)
    assert issubclass(BasisSetNotFoundError, RegistryError)
    assert issubclass(SchemaMigrationError, RegistryError)
