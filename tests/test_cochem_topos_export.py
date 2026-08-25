"""
Comprehensive Zero-Mock Unit Tests for CoChem-TOPOS Stage 5.1 FAIR Export.
(tests/test_cochem_topos_export.py)

Validates:
1. Jinja2-based publication-grade LaTeX Supporting Information generation and siunitx formatting.
2. Jinja2-based LaTeX SI table snippet generation with booktabs and siunitx rules.
3. Automated CrossRef / static fallback BibTeX citation generation.
4. Physical Boltzmann population distributions and thermodynamic enthalpy scaling.
5. Deterministic SHA-256 cryptographic provenance manifests and environment hashing.
6. Standalone Cartesian coordinate (.xyz) conformer extraction.
7. Immutable read-only FAIR archive packaging (TOPOS_Final_Ensemble.zip).
8. Air-gap safety and network fault resilience.

Strictly complies with the Zero-Mock Mandate, Anti-Spoofing Protocol v2,
and Mendeleev Atomic Mass Mandate.
"""

from __future__ import annotations

import json
import logging
import math
import zipfile
from pathlib import Path

import h5py
import numpy as np
import pytest

try:
    from cochem_topos.cochem_topos_export import (
        DEFAULT_TEMPERATURE_K,
        GAS_CONSTANT_KCAL_MOL_K,
        HARTREE_TO_KCAL_MOL,
        STATIC_METHOD_CITATIONS,
        TOPOSFAIRExporter,
        _compute_sha256,
        apply_readonly_lock,
        calculate_boltzmann_weights,
        remove_readonly_lock,
        sanitize_latex,
    )
except ImportError:
    from export_utils.cochem_topos_export import (  # type: ignore[no-redef]
        DEFAULT_TEMPERATURE_K,
        GAS_CONSTANT_KCAL_MOL_K,
        HARTREE_TO_KCAL_MOL,
        STATIC_METHOD_CITATIONS,
        TOPOSFAIRExporter,
        _compute_sha256,
        apply_readonly_lock,
        calculate_boltzmann_weights,
        remove_readonly_lock,
        sanitize_latex,
    )


def _create_sample_landscape_h5(h5_path: Path) -> None:
    """Populates an authentic multi-tier HDF5 database with real molecular structures."""
    with h5py.File(h5_path, "w", libver="latest") as f:
        dedup = f.create_group("deduplicated_isomers")

        # Isomer 1: Water conformer A
        iso1 = dedup.create_group("water_conf_01")
        t1 = iso1.create_group("T1_MACE_OFF24M")
        t1.attrs["electronic_energy_hartree"] = -76.400000
        t1.attrs["enthalpy_hartree"] = -76.350000
        t1.attrs["free_energy_hartree"] = -76.380000
        t1.attrs["zpe_hartree"] = 0.021000
        t1.attrs["dipole_moment_debye"] = 1.854
        t1.attrs["rotational_constants_mhz"] = np.array([835840.0, 435350.0, 278139.0])
        t1.attrs["method"] = "MACE-OFF24m"
        t1.attrs["basis_set"] = "MLFF"
        t1.create_dataset(
            "geometry_xyz",
            data="3\nWater Isomer 1 T1\nO 0.000000 0.000000 0.117300\nH 0.000000 0.757200 -0.469200\nH 0.000000 -0.757200 -0.469200"
        )

        t2 = iso1.create_group("T2_ORCA_DFT")
        t2.attrs["electronic_energy_hartree"] = -76.435678
        t2.attrs["enthalpy_hartree"] = -76.385432
        t2.attrs["free_energy_hartree"] = -76.415000
        t2.attrs["zpe_hartree"] = 0.021500
        t2.attrs["dipole_moment_debye"] = 1.855
        t2.attrs["rotational_constants_mhz"] = np.array([835900.0, 435400.0, 278150.0])
        t2.attrs["method"] = "wB97M-V"
        t2.attrs["basis_set"] = "def2-TZVPP"
        t2.create_dataset(
            "geometry_xyz",
            data="3\nWater Isomer 1 T2 Opt\nO 0.000000 0.000000 0.117000\nH 0.000000 0.757000 -0.468000\nH 0.000000 -0.757000 -0.468000"
        )

        # Isomer 2: Water conformer B (Higher energy conformer)
        iso2 = dedup.create_group("water_conf_02")
        t2_2 = iso2.create_group("T2_ORCA_DFT")
        t2_2.attrs["electronic_energy_hartree"] = -76.430000
        t2_2.attrs["enthalpy_hartree"] = -76.380000
        t2_2.attrs["free_energy_hartree"] = -76.410000
        t2_2.attrs["zpe_hartree"] = 0.021200
        t2_2.attrs["dipole_moment_debye"] = 1.902
        t2_2.attrs["rotational_constants_mhz"] = np.array([830000.0, 430000.0, 275000.0])
        t2_2.attrs["method"] = "wB97M-V"
        t2_2.attrs["basis_set"] = "def2-TZVPP"
        t2_2.create_dataset(
            "geometry_xyz",
            data="3\nWater Isomer 2 T2\nO 0.000000 0.000000 0.120000\nH 0.000000 0.760000 -0.470000\nH 0.000000 -0.760000 -0.470000"
        )


def test_compute_sha256(tmp_path: Path):
    """Verifies deterministic SHA-256 calculation for arbitrary payloads."""
    test_file = tmp_path / "test_manifest.txt"
    test_file.write_text("CoChem Stage 5.1 FAIR Export Verification", encoding="utf-8")
    digest = _compute_sha256(test_file)
    assert isinstance(digest, str)
    assert len(digest) == 64
    digest_second = _compute_sha256(test_file)
    assert digest == digest_second


def test_topos_fair_exporter_init(tmp_path: Path):
    """Verifies initialization fails on missing database and succeeds on valid path."""
    h5_path = tmp_path / "landscape.h5"
    out_dir = tmp_path / "fair_export"

    with pytest.raises(FileNotFoundError):
        TOPOSFAIRExporter(h5_path, out_dir)

    with h5py.File(h5_path, "w") as f:
        f.attrs["initialized"] = True

    exporter = TOPOSFAIRExporter(h5_path, out_dir)
    assert exporter.hdf5_path == h5_path
    assert exporter.output_dir.exists()
    assert exporter.jinja_env is not None


def test_sanitize_latex():
    """Verifies proper escaping of LaTeX special characters."""
    assert sanitize_latex("isomer_001%_val&hash#$test{a}") == r"isomer\_001\%\_val\&hash\#\$test\{a\}"
    assert sanitize_latex("test~name^2") == r"test\textasciitilde{}name\textasciicircum{}2"
    assert sanitize_latex("") == ""


def test_calculate_boltzmann_weights_physics():
    """Verifies physical Boltzmann distribution weighting and normalization."""
    # 1. Equal energies -> equal populations
    weights_equal = calculate_boltzmann_weights([0.0, 0.0], DEFAULT_TEMPERATURE_K)
    assert len(weights_equal) == 2
    assert pytest.approx(weights_equal[0], rel=1e-5) == 0.5
    assert pytest.approx(weights_equal[1], rel=1e-5) == 0.5

    # 2. Known energy delta: Delta E = RT -> P_2 / P_1 = 1 / e
    rt = GAS_CONSTANT_KCAL_MOL_K * DEFAULT_TEMPERATURE_K
    weights_rt = calculate_boltzmann_weights([0.0, rt], DEFAULT_TEMPERATURE_K)
    expected_ratio = 1.0 / math.e
    assert pytest.approx(weights_rt[1] / weights_rt[0], rel=1e-4) == expected_ratio

    # 3. Sum of probabilities must strictly equal 1.0
    weights_multi = calculate_boltzmann_weights([0.0, 0.5, 1.2, 3.0], DEFAULT_TEMPERATURE_K)
    assert pytest.approx(sum(weights_multi), rel=1e-6) == 1.0

    # 4. Empty list handling
    assert calculate_boltzmann_weights([]) == []


def test_custom_temperature_boltzmann():
    """Evaluates population distribution across different temperatures."""
    energies = [0.0, 1.0]  # 1.0 kcal/mol gap
    w_low_t = calculate_boltzmann_weights(energies, temperature_k=100.0)
    w_std_t = calculate_boltzmann_weights(energies, temperature_k=298.15)
    w_high_t = calculate_boltzmann_weights(energies, temperature_k=1000.0)

    # Low T: ground state dominates heavily
    assert w_low_t[0] > w_std_t[0] > w_high_t[0]
    # High T: excited state population increases towards 0.5
    assert w_high_t[1] > w_std_t[1] > w_low_t[1]


def test_generate_bibtex_citations_static_fallback(tmp_path: Path):
    """Verifies cochem_citations.bib generation using authentic method citations."""
    h5_path = tmp_path / "landscape.h5"
    out_dir = tmp_path / "export_output"
    out_dir.mkdir(parents=True, exist_ok=True)

    _create_sample_landscape_h5(h5_path)

    exporter = TOPOSFAIRExporter(h5_path, out_dir)
    bib_path = exporter.generate_bibtex_citations()

    assert bib_path.exists()
    content = bib_path.read_text(encoding="utf-8")
    assert "@article{" in content
    assert "doi" in content.lower()
    assert "author" in content.lower()
    assert "cochem_citations.bib" == bib_path.name
    assert "wb97m_v" in content.lower() or "def2_tzvpp" in content.lower()


def test_generate_bibtex_citations_from_config(tmp_path: Path):
    """Verifies citation compilation parses cochem_system_config.json."""
    h5_path = tmp_path / "landscape.h5"
    out_dir = tmp_path / "export_output"
    out_dir.mkdir(parents=True, exist_ok=True)

    with h5py.File(h5_path, "w") as f:
        f.attrs["init"] = 1

    config_data = {
        "engines": {
            "mace": {"version": "0.3.0"},
            "orca": {"version": "6.0.0"},
            "xtb": {"version": "6.7.0"},
            "crest": {"version": "3.0"}
        },
        "orca_version": "6.0.0"
    }
    config_file = out_dir / "cochem_system_config.json"
    config_file.write_text(json.dumps(config_data, indent=2), encoding="utf-8")

    exporter = TOPOSFAIRExporter(h5_path, out_dir)
    bib_path = exporter.generate_bibtex_citations(config_path=config_file)

    assert bib_path.exists()
    content = bib_path.read_text(encoding="utf-8")
    assert "mace" in content.lower()
    assert "orca" in content.lower()
    assert "xtb" in content.lower()
    assert "crest" in content.lower()


def test_latex_si_generation_jinja2(tmp_path: Path):
    """Verifies LaTeX Supporting Information generation via Jinja2, siunitx header bracing, and tier selection."""
    h5_path = tmp_path / "landscape.h5"
    out_dir = tmp_path / "fair_export"

    _create_sample_landscape_h5(h5_path)

    exporter = TOPOSFAIRExporter(h5_path, out_dir)
    tex_path = exporter.generate_latex_si("TOPOS_Supporting_Information.tex")

    assert tex_path.exists()
    content = tex_path.read_text(encoding="utf-8")

    # 1. Verify siunitx braces and column alignment
    assert r"{\textbf{Energy (\si{\hartree})}}" in content
    assert r"{\textbf{$\Delta H$ (\si{\kcalmol})}}" in content
    assert r"{\textbf{$\mu$ (\si{\debye})}}" in content
    assert r"{\textbf{Pop. (\%)}}" in content
    assert r"S[table-format=-4.6]" in content

    # 2. Verify highest tier was chosen (T2_ORCA_DFT over T1_MACE_OFF24M)
    assert r"water\_conf\_01" in content
    assert r"water\_conf\_02" in content
    assert r"T2\_ORCA\_DFT" in content
    assert "-76.435678" in content
    assert "Water Isomer 1 T2 Opt" in content

    # 3. Verify Cryptographic Provenance Section
    assert r"\section*{Cryptographic Provenance and Reproducibility}" in content
    assert r"Execution Provenance SHA-256:" in content
    assert r"Database SHA-256:" in content


def test_latex_si_tables_snippet_jinja2(tmp_path: Path):
    """Verifies dedicated LaTeX table snippet generation via Jinja2."""
    h5_path = tmp_path / "landscape.h5"
    out_dir = tmp_path / "fair_export"

    _create_sample_landscape_h5(h5_path)

    exporter = TOPOSFAIRExporter(h5_path, out_dir)
    table_path = exporter.generate_latex_si_tables("TOPOS_SI_Tables.tex")

    assert table_path.exists()
    content = table_path.read_text(encoding="utf-8")
    assert r"\begin{table}" in content
    assert r"\toprule" in content
    assert r"\midrule" in content
    assert r"\bottomrule" in content
    assert r"water\_conf\_01" in content
    assert r"water\_conf\_02" in content
    assert "-76.435678" in content


def test_energy_dataset_and_fallback_warning(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """Verifies fallback when energy is stored in dataset or missing."""
    h5_path = tmp_path / "landscape.h5"
    out_dir = tmp_path / "fair_export"

    with h5py.File(h5_path, "w") as f:
        geom_b = f.create_group("isomer_dataset_energy")
        t1 = geom_b.create_group("TIER_1_SCREEN")
        t1.create_dataset("electronic_energy_hartree", data=-76.123456)

        geom_c = f.create_group("isomer_missing_energy")
        geom_c.create_group("TIER_1_SCREEN")

    exporter = TOPOSFAIRExporter(h5_path, out_dir)
    with caplog.at_level(logging.WARNING):
        tex_path = exporter.generate_latex_si()

    content = tex_path.read_text(encoding="utf-8")
    assert "-76.123456" in content
    assert "0.000000" in content
    assert any("Missing electronic energy for geometry 'isomer_missing_energy'" in record.message for record in caplog.records)


def test_export_xyz_conformers(tmp_path: Path):
    """Verifies extraction of individual .xyz geometry files."""
    h5_path = tmp_path / "landscape.h5"
    out_dir = tmp_path / "export_output"

    _create_sample_landscape_h5(h5_path)

    exporter = TOPOSFAIRExporter(h5_path, out_dir)
    xyz_files = exporter.export_xyz_conformers()

    assert len(xyz_files) == 2
    filenames = [f.name for f in xyz_files]
    assert "water_conf_01.xyz" in filenames
    assert "water_conf_02.xyz" in filenames

    water_txt = (out_dir / "conformers_xyz" / "water_conf_01.xyz").read_text(encoding="utf-8")
    assert "Water Isomer 1 T2 Opt" in water_txt


def test_bundle_final_ensemble_and_readonly_lock(tmp_path: Path):
    """Verifies final ensemble zip packaging, provenance manifest, and immutability lock."""
    h5_dir = tmp_path / "calculations"
    h5_dir.mkdir()
    h5_path = h5_dir / "landscape.h5"
    out_dir = tmp_path / "export_output"
    out_dir.mkdir()

    _create_sample_landscape_h5(h5_path)

    # Add QM output artifact
    orca_out = h5_dir / "calc_01.out"
    orca_out.write_text("ORCA TERMINATED NORMALLY", encoding="utf-8")
    orca_gbw = h5_dir / "calc_01.gbw"
    orca_gbw.write_bytes(b"\x00\x01\x02\x03\x04\x05")

    exporter = TOPOSFAIRExporter(h5_path, out_dir)
    zip_path = exporter.bundle_final_ensemble("TOPOS_Final_Ensemble.zip", apply_immutability_lock=True)

    assert zip_path.exists()

    # Verify ZIP contents
    with zipfile.ZipFile(zip_path, "r") as zf:
        namelist = zf.namelist()
        assert "landscape.h5" in namelist
        assert "cochem_citations.bib" in namelist
        assert "TOPOS_Supporting_Information.tex" in namelist
        assert "TOPOS_SI_Tables.tex" in namelist
        assert "conformers_xyz/water_conf_01.xyz" in namelist
        assert "conformers_xyz/water_conf_02.xyz" in namelist
        assert "qm_artifacts/calc_01.out" in namelist
        assert "fair_manifest.json" in namelist

        manifest_data = json.loads(zf.read("fair_manifest.json").decode("utf-8"))
        assert manifest_data["archive_type"] == "CoChem-TOPOS FAIR Output"
        assert "fair_compliance" in manifest_data
        hashes = manifest_data["provenance_hashes"]
        assert "landscape.h5" in hashes
        assert "cochem_citations.bib" in hashes

    # Verify immutability / read-only lock helper
    remove_readonly_lock(zip_path)
    apply_readonly_lock(zip_path)
    assert zip_path.exists()
    remove_readonly_lock(zip_path)


def test_bundle_fair_archive_wrapper(tmp_path: Path):
    """Verifies backwards-compatible bundle_fair_archive wrapper."""
    h5_path = tmp_path / "landscape.h5"
    out_dir = tmp_path / "export_output"
    _create_sample_landscape_h5(h5_path)

    exporter = TOPOSFAIRExporter(h5_path, out_dir)
    zip_path = exporter.bundle_fair_archive("TOPOS_FAIR_Archive.zip")
    assert zip_path.exists()
    assert zip_path.name == "TOPOS_FAIR_Archive.zip"
    remove_readonly_lock(zip_path)


def test_query_crossref_doi_safely(tmp_path: Path):
    """Verifies CrossRef API queries fail safely without throwing unhandled network errors."""
    h5_path = tmp_path / "landscape.h5"
    out_dir = tmp_path / "export_output"
    with h5py.File(h5_path, "w") as f:
        f.attrs["init"] = 1

    exporter = TOPOSFAIRExporter(h5_path, out_dir)
    # Empty query should return None immediately
    assert exporter.query_crossref_doi("") is None
    assert exporter.query_crossref_doi("   ") is None
    # Real query should either return parsed dict or None (if air-gapped/timed out) without raising
    result = exporter.query_crossref_doi("10.1063/5.0004608", timeout=1.0)
    assert result is None or isinstance(result, dict)
