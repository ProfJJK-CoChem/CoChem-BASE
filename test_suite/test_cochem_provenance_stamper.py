"""Unit and Integration Tests for Cryptographic Provenance Stamper and Immutability Lock.

Validates:
- Real SHA-256 calculation of cochem_system_config.json.
- Real pip freeze software version extraction and manifest hashing.
- Hardware microarchitecture detection (AVX-512 flags, BLAS/LAPACK linking, custom config propagation).
- Construction of FAIR-compliant JSON-LD provenance records.
- Appending structured JSON-LD footers directly to plaintext .out files.
- Parsing and cryptographic verification of stamped footers.
- Tamper detection on modified pre-footer payload.
- Schema tampering detection during footer extraction and verification.
- Malformed and inverted delimiter detection.
- Double-stamping prevention and immutability preservation.
- OS-level read-only immutability locking (os.chmod 0o444).
- Graceful handling of file I/O locks and permission boundaries.
"""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from core_engine.cochem_provenance_stamper import (
    FOOTER_DELIMITER_END,
    FOOTER_DELIMITER_START,
    append_provenance_footer,
    apply_immutability_lock,
    construct_jsonld_provenance,
    extract_provenance_footer,
    get_hardware_microarchitecture_flags,
    get_software_version_hashes,
    get_system_config_sha256,
    is_immutable,
    stamp_run_provenance,
    unlock_immutability,
    verify_provenance_footer,
)


def test_system_config_sha256_real(tmp_path: Path) -> None:
    """Verifies that system config SHA-256 hash is computed accurately and deterministically."""
    config_file = tmp_path / "cochem_system_config.json"
    content = '{\n  "schema_version": "1.0.0",\n  "hardware": {"ram_gb": 32.0}\n}\n'
    config_file.write_text(content, encoding="utf-8")

    hash_val = get_system_config_sha256(config_path=config_file)
    assert len(hash_val) == 64
    assert isinstance(hash_val, str)

    # Determinism check
    hash_val_2 = get_system_config_sha256(config_path=config_file)
    assert hash_val == hash_val_2

    # Modification detection
    config_file.write_text('{\n  "schema_version": "2.0.0"\n}\n', encoding="utf-8")
    hash_val_mod = get_system_config_sha256(config_path=config_file)
    assert hash_val_mod != hash_val


def test_system_config_sha256_missing(tmp_path: Path) -> None:
    """Verifies that missing configuration file raises FileNotFoundError without faking."""
    missing_file = tmp_path / "non_existent_config.json"
    with pytest.raises(FileNotFoundError):
        get_system_config_sha256(config_path=missing_file)


def test_software_version_hashes_real() -> None:
    """Verifies execution and parsing of pip freeze and environment manifest hashing."""
    sw_record = get_software_version_hashes()

    assert "pip_freeze_sha256" in sw_record
    assert len(sw_record["pip_freeze_sha256"]) == 64
    assert sw_record["package_count"] > 0
    assert isinstance(sw_record["packages"], dict)

    # Core dependencies should be detected in the active environment
    packages = sw_record["packages"]
    assert "pytest" in packages or "pydantic" in packages or len(packages) > 5
    assert sw_record["python_version"] != ""
    assert sw_record["python_implementation"] != ""


def test_hardware_microarchitecture_flags_real() -> None:
    """Verifies dynamic profiling of hardware microarchitecture flags (AVX-512, BLAS)."""
    hw_flags = get_hardware_microarchitecture_flags()

    assert "cpu_arch" in hw_flags
    assert "physical_cores" in hw_flags
    assert "logical_cores" in hw_flags
    assert "total_ram_gb" in hw_flags
    assert "avx512_support" in hw_flags
    assert isinstance(hw_flags["avx512_support"], bool)
    assert "avx512_details" in hw_flags

    assert "blas_info" in hw_flags
    blas_info = hw_flags["blas_info"]
    assert isinstance(blas_info, dict)
    assert "blas_libraries" in blas_info or "blas_detected" in blas_info


def test_hardware_microarchitecture_custom_config_propagation(tmp_path: Path) -> None:
    """Verifies custom config_path propagation for microarchitecture detection."""
    config_file = tmp_path / "custom_hw_config.json"
    config_file.write_text('{\n  "hardware": {"avx512_support": true}\n}\n', encoding="utf-8")

    hw_flags = get_hardware_microarchitecture_flags(config_path=config_file)
    assert hw_flags["avx512_support"] is True
    assert "cochem_system_config" in hw_flags["avx512_details"].get("detection_method", "") or hw_flags["avx512_support"] is True


def test_construct_jsonld_provenance(tmp_path: Path) -> None:
    """Verifies that JSON-LD provenance block conforms to Linked Data standards."""
    target_out = tmp_path / "calculation_run.out"
    target_out.write_text("FINAL ENERGY: -154.238492 Hartree\nCONVERGED: YES\n", encoding="utf-8")

    config_file = tmp_path / "cochem_system_config.json"
    config_file.write_text('{"schema_version": "1.0.0"}\n', encoding="utf-8")

    prov_doc = construct_jsonld_provenance(
        target_file=target_out,
        config_path=config_file,
        run_id="run-test-uuid-1234",
        extra_metadata={"calculation_type": "B3LYP-D4/def2-TZVP", "charge": 0},
    )

    assert prov_doc["@context"] is not None
    assert "https://schema.org/" in str(prov_doc["@context"]) or "prov" in prov_doc["@context"]
    assert prov_doc["@type"] == ["prov:Entity", "cochem:ComputationalRunProvenance"]
    assert prov_doc["@id"] == "urn:cochem:run:run-test-uuid-1234"
    assert "prov:generatedAtTime" in prov_doc
    assert "cochem:systemConfigSha256" in prov_doc
    assert len(prov_doc["cochem:systemConfigSha256"]) == 64
    assert "cochem:softwareEnvironment" in prov_doc
    assert "cochem:hardwareMicroarchitecture" in prov_doc
    assert "cochem:targetFilePreStamp" in prov_doc
    assert prov_doc["cochem:targetFilePreStamp"]["sha256"] != ""
    assert prov_doc["cochem:metadata"]["calculation_type"] == "B3LYP-D4/def2-TZVP"

    # Verify JSON serializability
    serialized = json.dumps(prov_doc, indent=2)
    assert "run-test-uuid-1234" in serialized


def test_append_and_extract_provenance_footer(tmp_path: Path) -> None:
    """Verifies appending structured JSON-LD directly to .out file and extracting it."""
    out_file = tmp_path / "orca_output.out"
    original_text = (
        "************************************************************\n"
        "*                       ORCA RUN                           *\n"
        "************************************************************\n"
        "FINAL SINGLE POINT ENERGY: -382.4920194821\n"
    )
    out_file.write_text(original_text, encoding="utf-8")

    config_file = tmp_path / "cochem_system_config.json"
    config_file.write_text('{"schema_version": "1.0.0"}\n', encoding="utf-8")

    # Append footer
    stamped_record = append_provenance_footer(
        output_file=out_file,
        config_path=config_file,
    )

    assert out_file.exists()
    stamped_content = out_file.read_text(encoding="utf-8")

    # Header and body must remain preserved
    assert stamped_content.startswith(original_text)
    assert FOOTER_DELIMITER_START in stamped_content
    assert FOOTER_DELIMITER_END in stamped_content

    # Extract footer
    extracted_record = extract_provenance_footer(out_file)
    assert extracted_record["@type"] == ["prov:Entity", "cochem:ComputationalRunProvenance"]
    assert (
        extracted_record["cochem:systemConfigSha256"] == stamped_record["cochem:systemConfigSha256"]
    )


def test_double_stamping_prevention(tmp_path: Path) -> None:
    """Verifies that appending a provenance footer twice raises ValueError unless explicit."""
    out_file = tmp_path / "double_stamp.out"
    out_file.write_text("INITIAL COMPUTATION LOG\n", encoding="utf-8")

    config_file = tmp_path / "cochem_system_config.json"
    config_file.write_text('{"schema_version": "1.0.0"}\n', encoding="utf-8")

    # First stamp succeeds
    append_provenance_footer(output_file=out_file, config_path=config_file)

    # Second stamp without allow_re_stamp raises ValueError
    with pytest.raises(ValueError, match="already contains a provenance footer"):
        append_provenance_footer(output_file=out_file, config_path=config_file, allow_re_stamp=False)


def test_malformed_and_inverted_delimiters(tmp_path: Path) -> None:
    """Verifies that malformed or inverted delimiters raise ValueError."""
    corrupted_file = tmp_path / "corrupted_delims.out"
    # End delimiter placed before start delimiter
    corrupted_file.write_text(
        f"DATA\n{FOOTER_DELIMITER_END}\n{{}}\n{FOOTER_DELIMITER_START}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="closing delimiter not found after opening delimiter"):
        extract_provenance_footer(corrupted_file)

    # Missing delimiters
    no_delim_file = tmp_path / "no_delims.out"
    no_delim_file.write_text("RAW DATA ONLY\n", encoding="utf-8")
    with pytest.raises(ValueError, match="No provenance footer delimiters found"):
        extract_provenance_footer(no_delim_file)


def test_verify_provenance_footer_integrity(tmp_path: Path) -> None:
    """Verifies cryptographic validation of pre-stamp payload and detects tampering."""
    out_file = tmp_path / "mace_mlff.out"
    original_text = "Step 1: Energy -42.0\nStep 2: Energy -43.5\nOptimization converged.\n"
    out_file.write_text(original_text, encoding="utf-8")

    config_file = tmp_path / "cochem_system_config.json"
    config_file.write_text('{"schema_version": "1.0.0"}\n', encoding="utf-8")

    append_provenance_footer(output_file=out_file, config_path=config_file)

    # Initial verification should pass
    is_valid, issues = verify_provenance_footer(out_file)
    assert is_valid is True
    assert len(issues) == 0

    # Tamper with the calculation content before footer
    full_content = out_file.read_text(encoding="utf-8")
    tampered_content = full_content.replace("-43.5", "-999.9")
    out_file.write_text(tampered_content, encoding="utf-8")

    is_valid_tampered, issues_tampered = verify_provenance_footer(out_file)
    assert is_valid_tampered is False
    assert any(
        "hash mismatch" in iss.lower() or "tampered" in iss.lower() for iss in issues_tampered
    )


def test_verify_provenance_footer_schema_tamper(tmp_path: Path) -> None:
    """Verifies that tampering with the JSON-LD schema inside footer is detected."""
    out_file = tmp_path / "schema_tamper.out"
    out_file.write_text("CALCULATION LOG\n", encoding="utf-8")

    config_file = tmp_path / "cochem_system_config.json"
    config_file.write_text('{"schema_version": "1.0.0"}\n', encoding="utf-8")

    append_provenance_footer(output_file=out_file, config_path=config_file)

    # Corrupt required schema field in the footer
    content = out_file.read_text(encoding="utf-8")
    corrupted_content = content.replace('"prov:generatedAtTime"', '"corrupted_time_key"')
    out_file.write_text(corrupted_content, encoding="utf-8")

    is_valid, issues = verify_provenance_footer(out_file)
    assert is_valid is False
    assert any("schema validation" in iss.lower() or "failed to extract" in iss.lower() for iss in issues)


def test_apply_and_unlock_immutability_lock(tmp_path: Path) -> None:
    """Verifies that os.chmod(0o444) enforces OS-level read-only status and unlocks cleanly."""
    target_file = tmp_path / "final_run.out"
    target_file.write_text("IMMUTABLE DATA ENTRY\n", encoding="utf-8")

    assert is_immutable(target_file) is False

    # Apply lock
    apply_immutability_lock(target_file)
    assert is_immutable(target_file) is True

    # Check file mode
    mode = target_file.stat().st_mode
    assert not (mode & stat.S_IWUSR)

    # Attempt write should fail with PermissionError
    with pytest.raises(PermissionError):
        with open(target_file, "a", encoding="utf-8") as f:
            f.write("UNAUTHORIZED OVERWRITE\n")

    # Unlock for teardown/lifecycle
    unlock_immutability(target_file)
    assert is_immutable(target_file) is False

    # Write should now succeed
    with open(target_file, "a", encoding="utf-8") as f:
        f.write("AUTHORIZED APPEND AFTER UNLOCK\n")

    assert "AUTHORIZED APPEND" in target_file.read_text(encoding="utf-8")


def test_stamp_run_provenance_end_to_end(tmp_path: Path) -> None:
    """Verifies complete end-to-end stamp_run_provenance workflow with immutability locking."""
    out_file = tmp_path / "complete_engine_run.out"
    out_file.write_text(
        "COCHEM COMPLETE ENGINE RUN LOG\nALL ENERGIES COMPUTED.\n", encoding="utf-8"
    )

    config_file = tmp_path / "cochem_system_config.json"
    config_file.write_text(
        '{"schema_version": "1.0.0", "hardware": {"avx512_support": true}}\n', encoding="utf-8"
    )

    prov = stamp_run_provenance(
        output_file=out_file,
        config_path=config_file,
        lock_file=True,
        extra_metadata={"job_name": "phenol_dimer_opt"},
    )

    assert prov["cochem:metadata"]["job_name"] == "phenol_dimer_opt"
    assert is_immutable(out_file) is True

    # Verify integrity while locked
    is_valid, issues = verify_provenance_footer(out_file)
    assert is_valid is True
    assert len(issues) == 0

    # Cleanup unlock
    unlock_immutability(out_file)
    assert is_immutable(out_file) is False


def test_graceful_handling_already_locked_file(tmp_path: Path) -> None:
    """Verifies that appending to a locked file handles permissions gracefully."""
    locked_file = tmp_path / "pre_locked.out"
    locked_file.write_text("INITIAL STAGE OUTPUT\n", encoding="utf-8")
    apply_immutability_lock(locked_file)

    config_file = tmp_path / "cochem_system_config.json"
    config_file.write_text('{"schema_version": "1.0.0"}\n', encoding="utf-8")

    # Should handle unlocking temporarily or gracefully appending and re-locking
    prov = stamp_run_provenance(
        output_file=locked_file,
        config_path=config_file,
        lock_file=True,
    )

    assert prov is not None
    assert is_immutable(locked_file) is True
    unlock_immutability(locked_file)


def test_nonexistent_file_handling(tmp_path: Path) -> None:
    """Verifies that non-existent files raise FileNotFoundError across all functions."""
    missing = tmp_path / "does_not_exist.out"

    with pytest.raises(FileNotFoundError):
        append_provenance_footer(output_file=missing)

    with pytest.raises(FileNotFoundError):
        extract_provenance_footer(output_file=missing)

    with pytest.raises(FileNotFoundError):
        apply_immutability_lock(filepath=missing)

    with pytest.raises(FileNotFoundError):
        unlock_immutability(filepath=missing)

    assert is_immutable(missing) is False

    is_valid, issues = verify_provenance_footer(output_file=missing)
    assert is_valid is False
    assert any("not found" in iss.lower() for iss in issues)
