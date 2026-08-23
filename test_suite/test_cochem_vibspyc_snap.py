"""Zero-Mock Unit and Integration Tests for SpycFit Snapshot & Publication Export.

Validates:
- Strict Zero-Mock compliance (all tests run on physical disks using tmp_path).
- Target directory resolution with state dir environment variable and platformdirs fallback.
- FitProvenancePayload schema validation, bounds checks, and JSON file roundtrips.
- Iterative SHA-256 hashing across empty, small, and multi-chunk files.
- AASTeX and LaTeX longtable generation with siunitx, booktabs, frozen parameter replacement, and top-200 truncation.
- Model-to-DOI mapping for Watson reduction, IAM, ERHAM, JAX, PyArrow, and quantum engines.
- CrossRef JSON parsing and clean BibTeX generation with deduplication.
- Dynamic compression strategy evaluation (ZIP vs ZSTD).
- Archive bundling (.zip and .tar.zst) and integrity verification.
- Cross-platform read-only artifact sealing.
- End-to-end snapshot orchestration pipeline.
- Module re-exports and interface consistency.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import stat
import tarfile
import zipfile
from pathlib import Path
from typing import Any

import pytest
import zstandard

from cochem_base.interfaces.cochem_vibspyc_snap import (
    FitProvenancePayload,
    evaluate_compression_strategy,
    export_spycfit_snapshot,
    format_citations_to_bib,
    generate_aastex_longtables,
    get_required_dois,
    get_spycfit_processed_dir,
    hash_dataset_iteratively,
    package_fit_artifacts,
    resolve_processed_workspace_dir,
    seal_artifact_read_only,
)


def test_target_directory_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies target directory resolution via custom path, environment variable, and fallback."""
    # 1. Custom directory argument
    custom_target = tmp_path / "custom_processed"
    resolved_custom = resolve_processed_workspace_dir(custom_target)
    assert resolved_custom == custom_target.resolve()

    # 2. Environment variable override
    env_dir = tmp_path / "cochem_state"
    monkeypatch.setenv("COCHEM_STATE_DIR", str(env_dir))
    resolved_env = get_spycfit_processed_dir()
    expected_env = env_dir / "SpycFit_Workspace" / "Processed"
    assert resolved_env == expected_env.resolve()

    # 3. Fallback when environment variable is unset
    monkeypatch.delenv("COCHEM_STATE_DIR", raising=False)
    resolved_fallback = get_spycfit_processed_dir()
    assert "SpycFit_Workspace" in str(resolved_fallback)
    assert str(resolved_fallback).endswith("Processed")


def test_fit_provenance_payload_validation(tmp_path: Path) -> None:
    """Verifies schema validation, ISO timestamp verification, and disk roundtrips."""
    valid_timestamp = "2026-08-23T09:15:00+00:00"
    payload_dict: dict[str, Any] = {
        "session_id": "spycfit_session_alpha_001",
        "timestamp": valid_timestamp,
        "dataset_hashes": {
            "spectrum_raw.ftm": "a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0",
            "assignment_linelist.dat": "b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef01",
        },
        "chi_squared": 1.0428,
        "huber_loss_delta": 0.0035,
        "rms_mhz": 0.0125,
        "rms_cm_inv": 0.000417,
        "jacobian_condition_number": 42.15,
        "sobol_parameter_audit": {
            "A_rot": True,
            "B_rot": True,
            "C_rot": True,
            "DJ": True,
            "DJK": True,
            "DK": False,
            "V3_barrier": True,
        },
        "semantic_git_history": [
            "commit 9fa410b: Initialize IAM rotational hamiltonian",
            "commit 3bc289d: Converge Levenberg-Marquardt fit with Huber loss",
        ],
        "active_models": ["Watson_A_Reduction", "IAM_Internal_Rotation", "JAX_Backend"],
        "additional_metadata": {
            "temperature_kelvin": 1.5,
            "pulse_duration_us": 1.0,
        },
    }

    payload = FitProvenancePayload.model_validate(payload_dict)
    assert payload.session_id == "spycfit_session_alpha_001"
    assert payload.chi_squared == 1.0428
    assert payload.huber_loss_delta == 0.0035
    assert payload.sobol_parameter_audit["DK"] is False

    # Save to disk and re-load
    json_path = tmp_path / "fit_provenance.json"
    written_path = payload.to_json_file(json_path)
    assert written_path.exists()

    loaded_payload = FitProvenancePayload.from_json_file(json_path)
    assert loaded_payload.session_id == payload.session_id
    assert loaded_payload.dataset_hashes == payload.dataset_hashes
    assert loaded_payload.rms_mhz == payload.rms_mhz

    # Invalid timestamp test
    invalid_dict = dict(payload_dict)
    invalid_dict["timestamp"] = "not-an-iso-date"
    with pytest.raises(ValueError):
        FitProvenancePayload.model_validate(invalid_dict)

    # Negative chi squared test
    invalid_dict_chi = dict(payload_dict)
    invalid_dict_chi["chi_squared"] = -0.5
    with pytest.raises(ValueError):
        FitProvenancePayload.model_validate(invalid_dict_chi)

    # Negative rms_mhz test
    invalid_dict_rms = dict(payload_dict)
    invalid_dict_rms["rms_mhz"] = -0.01
    with pytest.raises(ValueError):
        FitProvenancePayload.model_validate(invalid_dict_rms)

    # Missing file for from_json_file
    missing_json = tmp_path / "missing_provenance.json"
    with pytest.raises(FileNotFoundError):
        FitProvenancePayload.from_json_file(missing_json)


def test_hash_dataset_iteratively(tmp_path: Path) -> None:
    """Verifies iterative SHA-256 calculation for empty, single-chunk, and multi-chunk files."""
    # 1. Multi-chunk data file
    data_content = b"CoChem Spectroscopic Linelist Data\nLine 1: 12450.32 MHz\nLine 2: 14890.11 MHz\n"
    file_path = tmp_path / "linelist.dat"
    file_path.write_bytes(data_content)

    expected_hash = hashlib.sha256(data_content).hexdigest()
    computed_hash = hash_dataset_iteratively(file_path, chunk_size=16)

    assert computed_hash == expected_hash
    assert len(computed_hash) == 64

    # 2. Empty file
    empty_path = tmp_path / "empty.dat"
    empty_path.write_bytes(b"")
    empty_hash = hash_dataset_iteratively(empty_path)
    assert empty_hash == hashlib.sha256(b"").hexdigest()

    # 3. Non-existent file error
    missing_file = tmp_path / "non_existent.bin"
    with pytest.raises(FileNotFoundError):
        hash_dataset_iteratively(missing_file)


def test_generate_aastex_longtables() -> None:
    """Verifies AASTeX and LaTeX table generation, siunitx formatting, frozen handling, and truncation."""
    parameters: list[dict[str, Any]] = [
        {
            "name": "A",
            "latex_name": r"A_0",
            "value": 5420.3182,
            "uncertainty": 0.0014,
            "unit": "MHz",
            "is_frozen": False,
            "description": "Principal rotational constant A",
        },
        {
            "name": "B",
            "latex_name": r"B_0",
            "value": 2314.1592,
            "uncertainty": 0.0008,
            "unit": "MHz",
            "is_frozen": False,
            "description": "Principal rotational constant B",
        },
        {
            "name": "C",
            "latex_name": r"C_0",
            "value": 1823.4567,
            "uncertainty": 0.0009,
            "unit": "MHz",
            "is_frozen": False,
            "description": "Principal rotational constant C",
        },
        {
            "name": "D_J",
            "latex_name": r"\Delta_J",
            "value": 0.00345,
            "uncertainty": None,
            "is_frozen": True,
            "description": "Quartic distortion DJ",
        },
        {
            "name": "D_JK",
            "latex_name": r"\Delta_{JK}",
            "value": -0.01234,
            "uncertainty": 0.0005,
            "unit": "MHz",
            "is_frozen": False,
            "sobol_audit": False,
            "description": "Quartic distortion DJK frozen by sobol audit",
        },
        {
            "name": "V3",
            "latex_name": r"V_3",
            "value": 350.5,
            "uncertainty": 0.1,
            "unit": "cm-1",
            "status": "fixed",
            "description": "Internal rotation barrier set fixed",
        },
    ]

    # Create 250 transition records to verify truncation to top 200
    transitions: list[dict[str, Any]] = []
    for idx in range(250):
        intensity_val = float(idx + 1) * 0.1
        transitions.append(
            {
                "upper_state": f"{idx+2}_1_{idx+2}",
                "lower_state": f"{idx+1}_0_{idx+1}",
                "observed_mhz": 10000.0 + idx * 25.5,
                "calculated_mhz": 10000.0 + idx * 25.5 + 0.004,
                "residual_mhz": -0.004,
                "uncertainty_mhz": 0.010,
                "intensity": intensity_val,
                "einstein_a": intensity_val * 1e-4,
            }
        )

    tables = generate_aastex_longtables(parameters, transitions, title_prefix="Ar-Furonitrile Fit")

    assert "parameters_table" in tables
    assert "transitions_table" in tables
    assert "combined_document" in tables

    param_table = tables["parameters_table"]
    trans_table = tables["transitions_table"]
    doc = tables["combined_document"]

    # Verify siunitx & booktabs markers
    assert r"\toprule" in param_table
    assert r"\midrule" in param_table
    assert r"\bottomrule" in param_table
    assert "siunitx" in doc or "S[" in param_table or r"\num{" in param_table

    # Verify frozen parameter handling: uncertainties replaced with Fixed or Set
    assert "Fixed" in param_table or "Set" in param_table

    # Verify transition truncation: only 200 rows rendered
    transition_row_markers = trans_table.count(r"\\")
    assert transition_row_markers <= 205
    assert transition_row_markers >= 190


def test_get_required_dois() -> None:
    """Verifies DOI extraction for standard spectroscopic and quantum chemistry models."""
    models = [
        "Watson_A_Reduction",
        "watson-s-reduction",
        "IAM_Internal_Rotation",
        "ERHAM",
        "JAX_Backend",
        "PyArrow_Engine",
        "SPCAT",
        "ORCA",
        "CFOUR",
        "CREST",
        "xTB",
        "MACE",
        "AIMNet2",
        "unknown_custom_model",
    ]

    dois = get_required_dois(models)
    assert len(dois) >= 6
    # Watson reduction DOI
    assert any("10.1016/0022-2852(77)90184-7" in d or "10.1063" in d for d in dois)
    # JAX DOI
    assert any("10.5281/zenodo" in d for d in dois)
    # SPCAT DOI
    assert any("10.1016/0022-2852(91)90393-O" in d for d in dois)
    # ERHAM DOI
    assert any("10.1006/jmsp.1997.7432" in d for d in dois)
    # No duplicate DOIs
    assert len(dois) == len(set(dois))


def test_format_citations_to_bib() -> None:
    """Verifies parsing of CrossRef JSON metadata into clean, deduplicated BibTeX records."""
    crossref_items: list[dict[str, Any]] = [
        {
            "DOI": "10.1016/0022-2852(77)90184-7",
            "title": ["The determination of centrifugal distortion constants of asymmetric-top molecules"],
            "author": [{"given": "J. K. G.", "family": "Watson"}],
            "container-title": ["Journal of Molecular Spectroscopy"],
            "volume": "65",
            "issue": "1",
            "page": "123-133",
            "issued": {"date-parts": [[1977, 4, 1]]},
            "type": "journal-article",
            "publisher": "Elsevier BV",
        },
        {
            "DOI": "10.1016/0022-2852(91)90393-O",
            "title": ["The fitting and prediction of vibration-rotation spectra with spin interactions"],
            "author": [{"given": "Herbert M.", "family": "Pickett"}],
            "container-title": ["Journal of Molecular Spectroscopy"],
            "volume": "148",
            "issue": "2",
            "page": "371-377",
            "issued": {"date-parts": [[1991, 8, 1]]},
            "type": "journal-article",
            "publisher": "Elsevier BV",
        },
        # Duplicate entry with lowercase doi key
        {
            "doi": "10.1016/0022-2852(91)90393-O",
            "title": "The fitting and prediction of vibration-rotation spectra with spin interactions",
            "author": [{"given": "Herbert M.", "family": "Pickett"}],
            "container_title": "Journal of Molecular Spectroscopy",
            "volume": "148",
            "issued": {"date-parts": [[1991]]},
        },
    ]

    bib_str = format_citations_to_bib(crossref_items)
    assert "@article" in bib_str
    assert "Watson" in bib_str
    assert "Pickett" in bib_str
    assert "10.1016/0022-2852(77)90184-7" in bib_str
    assert "10.1016/0022-2852(91)90393-O" in bib_str

    # Ensure deduplicated: Pickett appears exactly once
    assert bib_str.count("10.1016/0022-2852(91)90393-O") == 1

    # Empty list handling
    assert format_citations_to_bib([]) == ""


def test_evaluate_compression_strategy() -> None:
    """Verifies compression threshold logic."""
    threshold = 104857600  # 100 MiB
    assert evaluate_compression_strategy(50000000, threshold_bytes=threshold) == "ZIP"
    assert evaluate_compression_strategy(104857600, threshold_bytes=threshold) == "ZSTD"
    assert evaluate_compression_strategy(200000000, threshold_bytes=threshold) == "ZSTD"


def test_package_fit_artifacts_zip_and_zstd(tmp_path: Path) -> None:
    """Verifies packaging artifacts into ZIP and TAR.ZST archives and integrity testing."""
    source_dir = tmp_path / "artifacts_source"
    source_dir.mkdir()

    (source_dir / "fit_provenance.json").write_text('{"session": "alpha"}', encoding="utf-8")
    (source_dir / "parameters.tex").write_text(r"\begin{tabular} ... \end{tabular}", encoding="utf-8")
    (source_dir / "binary_data.dat").write_bytes(b"\x00\x01\x02\x03" * 1024)

    # 1. Package as ZIP
    zip_out = tmp_path / "package_output_zip"
    created_zip = package_fit_artifacts(source_dir, zip_out, strategy="ZIP")
    assert created_zip.exists()
    assert created_zip.suffix == ".zip"

    with zipfile.ZipFile(created_zip, "r") as zf:
        namelist = zf.namelist()
        assert "fit_provenance.json" in namelist
        assert "parameters.tex" in namelist
        assert "binary_data.dat" in namelist
        assert zf.read("fit_provenance.json").decode("utf-8") == '{"session": "alpha"}'

    # 2. Package as ZSTD
    zstd_out = tmp_path / "package_output_zstd"
    created_zstd = package_fit_artifacts(source_dir, zstd_out, strategy="ZSTD")
    assert created_zstd.exists()
    assert str(created_zstd).endswith(".tar.zst")

    # Decompress and verify tar contents
    dctx = zstandard.ZstdDecompressor()
    decompressed_tar_bytes = dctx.decompress(created_zstd.read_bytes())
    tar_dest = tmp_path / "decompressed.tar"
    tar_dest.write_bytes(decompressed_tar_bytes)

    with tarfile.open(tar_dest, "r") as tf:
        names = tf.getnames()
        assert any("fit_provenance.json" in n for n in names)
        assert any("parameters.tex" in n for n in names)
        assert any("binary_data.dat" in n for n in names)

    # 3. Invalid strategy
    with pytest.raises(ValueError):
        package_fit_artifacts(source_dir, zip_out, strategy="UNSUPPORTED_FORMAT")

    # 4. Non-existent source dir
    missing_dir = tmp_path / "missing_source_directory"
    with pytest.raises(NotADirectoryError):
        package_fit_artifacts(missing_dir, zip_out)


def test_seal_artifact_read_only(tmp_path: Path) -> None:
    """Verifies setting cross-platform read-only permissions."""
    sealed_file = tmp_path / "locked_provenance.json"
    sealed_file.write_text('{"locked": true}', encoding="utf-8")

    success = seal_artifact_read_only(sealed_file)
    assert success is True

    # Verification: check permissions
    file_stat = sealed_file.stat()
    assert not (file_stat.st_mode & stat.S_IWUSR)

    # Attempting write in write mode should raise PermissionError
    with pytest.raises(PermissionError):
        with open(sealed_file, "w", encoding="utf-8") as f:
            f.write('{"locked": false}')

    # Cleanup permissions so pytest temp directory cleaner won't fail
    os.chmod(sealed_file, stat.S_IWRITE | stat.S_IREAD)

    # Non-existent file sealing test
    missing_file = tmp_path / "not_there.json"
    with pytest.raises(FileNotFoundError):
        seal_artifact_read_only(missing_file)


def test_export_spycfit_snapshot_pipeline(tmp_path: Path) -> None:
    """Verifies the complete end-to-end snapshot generation and export workflow."""
    source_dir = tmp_path / "session_raw"
    source_dir.mkdir()

    raw_spectrum = source_dir / "chirp_spectrum.ftm"
    raw_spectrum.write_bytes(b"FTMW RAW DATA CHIRP 2-18 GHz" * 500)

    dataset_hash = hash_dataset_iteratively(raw_spectrum)

    payload = FitProvenancePayload(
        session_id="spycfit_full_pipeline_test",
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        dataset_hashes={"chirp_spectrum.ftm": dataset_hash},
        chi_squared=1.002,
        huber_loss_delta=0.001,
        rms_mhz=0.0084,
        rms_cm_inv=0.00028,
        jacobian_condition_number=18.4,
        sobol_parameter_audit={"A": True, "B": True, "C": True},
        semantic_git_history=["commit a1b2c3d: Pipeline validation"],
        active_models=["Watson_A_Reduction", "JAX_Backend", "SPCAT"],
    )

    parameters = [
        {"name": "A", "latex_name": "A_0", "value": 4500.12, "uncertainty": 0.01, "unit": "MHz", "is_frozen": False},
        {"name": "B", "latex_name": "B_0", "value": 2200.34, "uncertainty": 0.005, "unit": "MHz", "is_frozen": False},
    ]
    transitions = [
        {
            "upper_state": "1_1_1",
            "lower_state": "0_0_0",
            "observed_mhz": 6700.46,
            "calculated_mhz": 6700.458,
            "residual_mhz": 0.002,
            "uncertainty_mhz": 0.01,
            "intensity": 10.5,
        }
    ]

    export_dest = tmp_path / "snapshot_processed"

    result = export_spycfit_snapshot(
        payload=payload,
        source_dir=source_dir,
        output_dir=export_dest,
        optimized_params=parameters,
        transitions=transitions,
        title_prefix="CO2-H2O Complex Fit",
        strategy="ZSTD",
    )

    assert result["status"] == "SUCCESS"
    assert "archive_path" in result
    assert "provenance_path" in result
    assert "parameters_table_path" in result
    assert "transitions_table_path" in result
    assert "citations_bib_path" in result

    archive_path = Path(result["archive_path"])
    assert archive_path.exists()
    assert str(archive_path).endswith(".tar.zst")

    # Verify provenance file exists and is valid
    prov_path = Path(result["provenance_path"])
    assert prov_path.exists()
    loaded_prov = FitProvenancePayload.from_json_file(prov_path)
    assert loaded_prov.session_id == payload.session_id


def test_reexport_consistency() -> None:
    """Verifies that the top-level interfaces re-export matches canonical cochem_base module."""
    import cochem_base.interfaces.cochem_vibspyc_snap as canonical
    import interfaces.cochem_vibspyc_snap as reexported

    symbols = [
        "FitProvenancePayload",
        "get_spycfit_processed_dir",
        "resolve_processed_workspace_dir",
        "hash_dataset_iteratively",
        "generate_aastex_longtables",
        "get_required_dois",
        "format_citations_to_bib",
        "evaluate_compression_strategy",
        "package_fit_artifacts",
        "seal_artifact_read_only",
        "export_spycfit_snapshot",
    ]

    for sym in symbols:
        assert hasattr(canonical, sym), f"Canonical module missing symbol '{sym}'"
        assert hasattr(reexported, sym), f"Re-exported module missing symbol '{sym}'"
        assert getattr(canonical, sym) is getattr(reexported, sym)
