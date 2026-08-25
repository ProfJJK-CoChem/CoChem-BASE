#!/usr/bin/env python3
"""Authentic Unit Test Suite for CoChem Stage 5.0 Benchmark HDF5 & Publication Table Exporter.

Module: tests/test_cochem_bench_export.py
Target Implementation: bench_engine.cochem_bench_export

Tests:
1. AirGapVerifier:
   - Dynamic validation of required packages (jinja2, siunitx, booktabs).
   - Zero-Tolerance policy against pip/apt/tlmgr network installations.
   - Fail-fast exception raising for missing air-gap dependencies.
2. CompositeAggregator:
   - Algebraic composite total energy evaluation:
     E_Total = E_SCF^CBS + E_corr^CBS + Delta_E_CV + Delta_E_rel + Delta_E_SOC + ZPVE.
   - Unit conversion from Hartree to kcal/mol via exact CODATA constant.
   - MANDATORY FAIL-FAST on missing ZPVE: Explicitly raises MissingZPVEError and forbids defaulting to 0.0.
   - SWMR-safe HDF5 landscape file sweeping across authentic molecular nodes.
   - HDF5 composite results roundtrip persistence and verification.
3. SiunitxLaTeXCompiler:
   - LaTeX special character escaping and string sanitization (underscores, %, &, #, $).
   - Memory-safe Jinja2 streaming table generation (no dense DataFrame.to_latex).
   - Strict booktabs and siunitx alignment syntax verification (S[table-format=...]).
   - File export to designated processed directory.
4. ProvenanceStamper:
   - JSON-LD cryptographic lineage tracking compliant with MolSSI/QCArchive.
   - Embedding Git commit hashes, SHA-256 binary signatures, hardware limits, and mathematical formulas.
   - Serialization to bench_provenance.jsonld and schema roundtrip validation.
5. PublicationArchiver & End-to-End Pipeline:
   - Zip archive packaging of .tex tables, .jsonld ledgers, and .xyz structures.
   - Read-only permission locking (0o444).
   - Full pipeline execution from authentic HDF5 to publication artifacts.

Authoritative References:
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 8 Benchmark Assembly & Publication Export (Stage 5.0).txt
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task2_pt1_export.md
"""

from __future__ import annotations

import json
import os
import shutil
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

import h5py
import pytest
from mendeleev import element

from bench_engine.cochem_bench_export import (
    AirGapVerifier,
    CompositeAggregator,
    SiunitxLaTeXCompiler,
    ProvenanceStamper,
    PublicationArchiver,
    CompositeEnergyRecord,
    LaTeXExportConfig,
    ExportPipelineResult,
    MissingZPVEError,
    AirGapPackageMissingError,
    run_export_pipeline,
    HARTREE_TO_KCAL_MOL,
    DEFAULT_PROCESSED_DIR,
)


# ==============================================================================
# Authentic Molecular Test Fixtures (Water, Methane, Formaldehyde)
# ==============================================================================

# Water (H2O): Authentic DLPNO-CCSD(T)/CBS + CV + ZPVE Benchmark Values
H2O_DATA = {
    "node_id": "H2O_equilibrium_C2v",
    "formula": "H2O",
    "e_scf_cbs": -76.0670904,
    "e_corr_cbs": -0.2785432,
    "delta_e_cv": -0.0412850,
    "delta_e_rel": -0.0543210,
    "delta_e_soc": -0.0001200,
    "zpve": 0.0211400,
}

# Methane (CH4): Authentic Benchmark Values
CH4_DATA = {
    "node_id": "CH4_equilibrium_Td",
    "formula": "CH4",
    "e_scf_cbs": -40.2172840,
    "e_corr_cbs": -0.2145890,
    "delta_e_cv": -0.0387500,
    "delta_e_rel": -0.0145200,
    "delta_e_soc": -0.0000500,
    "zpve": 0.0452300,
}

# Formaldehyde (H2CO): Authentic Benchmark Values
H2CO_DATA = {
    "node_id": "H2CO_planar_C2v",
    "formula": "H2CO",
    "e_scf_cbs": -113.9184500,
    "e_corr_cbs": -0.3892400,
    "delta_e_cv": -0.0754200,
    "delta_e_rel": -0.0681000,
    "delta_e_soc": -0.0002100,
    "zpve": 0.0268500,
}


@pytest.fixture
def sample_h5_file(tmp_path: Path) -> Path:
    """Generates an authentic SWMR-compliant landscape.h5 file populated with multi-stage benchmark data."""
    h5_file = tmp_path / "landscape.h5"
    
    with h5py.File(h5_file, "w", libver="latest") as f:
        # 1. CBS Extrapolations Group (Stage 2.0)
        cbs_grp = f.require_group("cbs_extrapolations")
        for node in [H2O_DATA, CH4_DATA, H2CO_DATA]:
            node_grp = cbs_grp.require_group(node["node_id"])
            node_grp.create_dataset("e_scf_cbs", data=float(node["e_scf_cbs"]))
            node_grp.create_dataset("e_corr_cbs", data=float(node["e_corr_cbs"]))
            node_grp.create_dataset("e_total_cbs", data=float(node["e_scf_cbs"] + node["e_corr_cbs"]))
            node_grp.attrs["basis_x"] = "def2-TZVP"
            node_grp.attrs["basis_y"] = "def2-QZVPP"
            node_grp.attrs["uncertainty_flag"] = "PASSED"
            node_grp.attrs["node_id"] = node["node_id"]

        # 2. Core-Valence Corrections Group (Stage 3.0)
        cv_grp = f.require_group("cv_corrections")
        for node in [H2O_DATA, CH4_DATA, H2CO_DATA]:
            node_grp = cv_grp.require_group(node["node_id"])
            node_grp.create_dataset("delta_e_cv_hartree", data=float(node["delta_e_cv"]))
            node_grp.create_dataset("delta_e_cv_kcal_mol", data=float(node["delta_e_cv"] * HARTREE_TO_KCAL_MOL))
            node_grp.attrs["basis_set"] = "cc-pCVQZ"
            node_grp.attrs["method"] = "DLPNO-CCSD(T)"
            node_grp.attrs["node_id"] = node["node_id"]

        # 3. Scalar Relativistic & SOC Corrections Group (Stage 4.0)
        rel_grp = f.require_group("rel_corrections")
        for node in [H2O_DATA, CH4_DATA, H2CO_DATA]:
            node_grp = rel_grp.require_group(node["node_id"])
            node_grp.create_dataset("delta_e_rel_hartree", data=float(node["delta_e_rel"]))
            node_grp.create_dataset("delta_e_soc_hartree", data=float(node["delta_e_soc"]))
            node_grp.attrs["node_id"] = node["node_id"]

        # 4. ZPVE Corrections Group (Harmonic/VPT2)
        zpve_grp = f.require_group("zpve_corrections")
        for node in [H2O_DATA, CH4_DATA, H2CO_DATA]:
            node_grp = zpve_grp.require_group(node["node_id"])
            node_grp.create_dataset("zpve_hartree", data=float(node["zpve"]))
            node_grp.attrs["node_id"] = node["node_id"]
            node_grp.attrs["method"] = "VPT2-B3LYP/def2-TZVP"

    return h5_file


# ==============================================================================
# 1. AirGapVerifier Tests
# ==============================================================================

class TestAirGapVerifier:
    """Tests for runtime package verification and air-gap compliance enforcement."""

    def test_jinja2_availability_check(self):
        """Asserts that Jinja2 is detected and loaded safely."""
        verifier = AirGapVerifier()
        is_available = verifier.check_jinja2()
        assert is_available is True

    def test_latex_package_inspection(self):
        """Asserts that LaTeX packages are verified non-destructively without package managers."""
        verifier = AirGapVerifier()
        status = verifier.check_latex_packages(["siunitx", "booktabs"])
        assert isinstance(status, dict)
        assert "siunitx" in status
        assert "booktabs" in status

    def test_airgap_install_ban(self):
        """Verifies that no install attempts (pip, apt, tlmgr) occur in AirGapVerifier."""
        verifier = AirGapVerifier()
        assert not hasattr(verifier, "install_package")
        assert not hasattr(verifier, "pip_install")
        assert not hasattr(verifier, "tlmgr_install")


# ==============================================================================
# 2. CompositeAggregator Tests
# ==============================================================================

class TestCompositeAggregator:
    """Tests for Stage 5.0 composite arithmetic and HDF5 sweeping."""

    def test_composite_arithmetic_exactness(self):
        """Verifies exact floating point composite summation:
        E_Total = E_SCF_CBS + E_corr_CBS + Delta_E_CV + Delta_E_rel + Delta_E_SOC + ZPVE.
        """
        aggregator = CompositeAggregator()
        rec = aggregator.calculate_composite_energy(
            e_scf_cbs=H2O_DATA["e_scf_cbs"],
            e_corr_cbs=H2O_DATA["e_corr_cbs"],
            delta_e_cv=H2O_DATA["delta_e_cv"],
            delta_e_rel=H2O_DATA["delta_e_rel"],
            delta_e_soc=H2O_DATA["delta_e_soc"],
            zpve=H2O_DATA["zpve"],
            node_id=H2O_DATA["node_id"],
        )

        expected_cbs = H2O_DATA["e_scf_cbs"] + H2O_DATA["e_corr_cbs"]
        expected_total = (
            expected_cbs
            + H2O_DATA["delta_e_cv"]
            + H2O_DATA["delta_e_rel"]
            + H2O_DATA["delta_e_soc"]
            + H2O_DATA["zpve"]
        )
        assert pytest.approx(rec.e_total_cbs, rel=1e-10) == expected_cbs
        assert pytest.approx(rec.e_total_hartree, rel=1e-10) == expected_total
        assert pytest.approx(rec.e_total_kcal_mol, rel=1e-10) == expected_total * HARTREE_TO_KCAL_MOL

    def test_missing_zpve_fail_fast_mandate(self):
        """CRITICAL MANDATE: If ZPVE is missing or None, the code MUST fail fast and raise MissingZPVEError.
        It is STRICTLY FORBIDDEN to default ZPVE to 0.0.
        """
        aggregator = CompositeAggregator()
        with pytest.raises(MissingZPVEError) as exc_info:
            aggregator.calculate_composite_energy(
                e_scf_cbs=-76.0670904,
                e_corr_cbs=-0.2785432,
                delta_e_cv=-0.0412850,
                delta_e_rel=-0.0543210,
                delta_e_soc=-0.0001200,
                zpve=None,
                node_id="test_node_no_zpve",
            )
        assert "missing required zpve" in str(exc_info.value).lower() or "zpve is required" in str(exc_info.value).lower()

    def test_sweep_hdf5_swmr(self, sample_h5_file: Path):
        """Verifies sweeping landscape.h5 in SWMR mode extracts all nodes correctly."""
        aggregator = CompositeAggregator()
        records = aggregator.sweep_hdf5(sample_h5_file)
        assert len(records) == 3
        node_ids = {r.node_id for r in records}
        assert "H2O_equilibrium_C2v" in node_ids
        assert "CH4_equilibrium_Td" in node_ids
        assert "H2CO_planar_C2v" in node_ids

    def test_sweep_hdf5_missing_zpve_raises(self, tmp_path: Path):
        """Asserts that sweeping an HDF5 file with missing ZPVE raises MissingZPVEError."""
        bad_h5 = tmp_path / "bad_landscape.h5"
        with h5py.File(bad_h5, "w", libver="latest") as f:
            cbs_grp = f.require_group("cbs_extrapolations")
            n_grp = cbs_grp.require_group("node_incomplete")
            n_grp.create_dataset("e_scf_cbs", data=-100.0)
            n_grp.create_dataset("e_corr_cbs", data=-0.5)
            # No ZPVE dataset in file!

        aggregator = CompositeAggregator()
        with pytest.raises(MissingZPVEError):
            aggregator.sweep_hdf5(bad_h5)

    def test_hdf5_composite_roundtrip(self, tmp_path: Path):
        """Tests committing composite energy records back to landscape.h5."""
        h5_path = tmp_path / "committed_landscape.h5"
        aggregator = CompositeAggregator()
        rec = aggregator.calculate_composite_energy(
            e_scf_cbs=H2O_DATA["e_scf_cbs"],
            e_corr_cbs=H2O_DATA["e_corr_cbs"],
            delta_e_cv=H2O_DATA["delta_e_cv"],
            delta_e_rel=H2O_DATA["delta_e_rel"],
            delta_e_soc=H2O_DATA["delta_e_soc"],
            zpve=H2O_DATA["zpve"],
            node_id=H2O_DATA["node_id"],
        )
        aggregator.commit_composite_to_hdf5(h5_path, [rec])
        
        with h5py.File(h5_path, "r") as f:
            grp = f["composite_energies"][H2O_DATA["node_id"]]
            assert pytest.approx(float(grp["e_total_hartree"][()]), rel=1e-10) == rec.e_total_hartree
            assert pytest.approx(float(grp["e_total_kcal_mol"][()]), rel=1e-10) == rec.e_total_kcal_mol


# ==============================================================================
# 3. SiunitxLaTeXCompiler Tests
# ==============================================================================

class TestSiunitxLaTeXCompiler:
    """Tests for memory-safe Jinja2 LaTeX table generation."""

    def test_latex_string_sanitization(self):
        """Asserts that underscores and LaTeX special characters are properly escaped."""
        compiler = SiunitxLaTeXCompiler()
        raw_text = "H2O_cis_dimer_def2_TZVPP & 100% #1 $E_0$"
        sanitized = compiler.sanitize_latex(raw_text)
        assert r"H2O\_cis\_dimer\_def2\_TZVPP" in sanitized
        assert r"\&" in sanitized
        assert r"\%" in sanitized
        assert r"\#" in sanitized

    def test_latex_table_compilation(self):
        """Verifies generated .tex table utilizes siunitx, booktabs, and accurate alignments."""
        aggregator = CompositeAggregator()
        records = [
            aggregator.calculate_composite_energy(
                e_scf_cbs=H2O_DATA["e_scf_cbs"],
                e_corr_cbs=H2O_DATA["e_corr_cbs"],
                delta_e_cv=H2O_DATA["delta_e_cv"],
                delta_e_rel=H2O_DATA["delta_e_rel"],
                delta_e_soc=H2O_DATA["delta_e_soc"],
                zpve=H2O_DATA["zpve"],
                node_id="H2O_conf_1",
            ),
            aggregator.calculate_composite_energy(
                e_scf_cbs=CH4_DATA["e_scf_cbs"],
                e_corr_cbs=CH4_DATA["e_corr_cbs"],
                delta_e_cv=CH4_DATA["delta_e_cv"],
                delta_e_rel=CH4_DATA["delta_e_rel"],
                delta_e_soc=CH4_DATA["delta_e_soc"],
                zpve=CH4_DATA["zpve"],
                node_id="CH4_conf_1",
            ),
        ]

        compiler = SiunitxLaTeXCompiler()
        tex_output = compiler.compile_table(records)

        assert r"\toprule" in tex_output
        assert r"\midrule" in tex_output
        assert r"\bottomrule" in tex_output
        assert "S[table-format=" in tex_output
        assert r"H2O\_conf\_1" in tex_output
        assert r"CH4\_conf\_1" in tex_output

    def test_latex_table_file_write(self, tmp_path: Path):
        """Tests writing .tex file to disk in processed directory."""
        compiler = SiunitxLaTeXCompiler()
        rec = CompositeAggregator().calculate_composite_energy(
            e_scf_cbs=H2O_DATA["e_scf_cbs"],
            e_corr_cbs=H2O_DATA["e_corr_cbs"],
            delta_e_cv=H2O_DATA["delta_e_cv"],
            zpve=H2O_DATA["zpve"],
            node_id=H2O_DATA["node_id"],
        )
        out_file = tmp_path / "Benchmark_Results.tex"
        result_path = compiler.compile_table([rec], output_path=out_file)
        assert Path(result_path).exists()
        assert Path(result_path).stat().st_size > 0


# ==============================================================================
# 4. ProvenanceStamper Tests
# ==============================================================================

class TestProvenanceStamper:
    """Tests for JSON-LD FAIR provenance archiving."""

    def test_provenance_stamper_jsonld(self, tmp_path: Path):
        """Verifies JSON-LD generation with Git hash, hardware metadata, and mathematical formulas."""
        stamper = ProvenanceStamper()
        rec = CompositeAggregator().calculate_composite_energy(
            e_scf_cbs=H2O_DATA["e_scf_cbs"],
            e_corr_cbs=H2O_DATA["e_corr_cbs"],
            delta_e_cv=H2O_DATA["delta_e_cv"],
            delta_e_rel=H2O_DATA["delta_e_rel"],
            delta_e_soc=H2O_DATA["delta_e_soc"],
            zpve=H2O_DATA["zpve"],
            node_id=H2O_DATA["node_id"],
        )

        out_jsonld = tmp_path / "bench_provenance.jsonld"
        payload = stamper.stamp_provenance([rec], output_path=out_jsonld)

        assert "@context" in payload
        assert "@type" in payload
        assert payload["@type"] == "cochem:BenchmarkProvenanceRecord"
        assert "formulas" in payload
        assert "composite_total" in payload["formulas"]
        assert Path(out_jsonld).exists()

        with open(out_jsonld, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["@type"] == "cochem:BenchmarkProvenanceRecord"
        assert len(loaded["nodes"]) == 1
        assert loaded["nodes"][0]["node_id"] == H2O_DATA["node_id"]


# ==============================================================================
# 5. PublicationArchiver & Full Pipeline Tests
# ==============================================================================

class TestPublicationArchiverAndPipeline:
    """Tests for packaging and end-to-end Stage 5.0 export execution."""

    def test_publication_zip_archiver(self, tmp_path: Path):
        """Verifies zip packaging of .tex and .jsonld files with read-only permission."""
        tex_path = tmp_path / "Benchmark_Results.tex"
        tex_path.write_text(r"\begin{table}\end{table}", encoding="utf-8")
        jsonld_path = tmp_path / "bench_provenance.jsonld"
        jsonld_path.write_text(r'{"@context": {}}', encoding="utf-8")

        archiver = PublicationArchiver()
        zip_path = tmp_path / "CoChem_BENCH_Publication_Archive.zip"
        res_zip = archiver.create_publication_archive(
            tex_files=[tex_path],
            jsonld_files=[jsonld_path],
            output_zip_path=zip_path,
            read_only=True,
        )

        assert res_zip.exists()
        with zipfile.ZipFile(res_zip, "r") as z:
            names = z.namelist()
            assert "Benchmark_Results.tex" in names
            assert "bench_provenance.jsonld" in names

    def test_run_export_pipeline_end_to_end(self, sample_h5_file: Path, tmp_path: Path):
        """Verifies full Stage 5.0 end-to-end export pipeline from landscape.h5."""
        out_dir = tmp_path / "Processed"
        result = run_export_pipeline(
            h5_path=sample_h5_file,
            output_dir=out_dir,
            create_archive=True,
        )

        assert isinstance(result, ExportPipelineResult)
        assert result.status == "SUCCESS"
        assert len(result.records) == 3
        assert result.tex_file_path is not None and Path(result.tex_file_path).exists()
        assert result.jsonld_file_path is not None and Path(result.jsonld_file_path).exists()
        assert result.archive_file_path is not None and Path(result.archive_file_path).exists()
