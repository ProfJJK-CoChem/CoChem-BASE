"""Zero-Mock Integration and Unit Test Suite for MarkdownBuilder (Stage 6.3).

Complies with CoChem-SCRIBE SRS Phase 4, Task 9 (Stage 6.3, Tasks 61-70),
Method Matrix v4, the Zero-Mock Anti-Spoofing Protocol, FAIR Data Principles,
and the 6-Tier Environment Matrix.

Verifies dynamic Markdown User Guide compilation, YAML frontmatter
serialization, Mermaid.js workflow diagram synthesis, GFM pipe table
formatting, thermodynamic insights placeholder scrubbing, warning callout
blockquotes, hardware telemetry reporting, and non-destructive timestamped
overwrite protection against real physical disk I/O and real data structures.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
from typing import Any, Dict, List, Optional, Tuple, Union

import h5py  # type: ignore[import-untyped]
import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import pytest
import yaml  # type: ignore[import-untyped]

from formatters.scribe_md_generator import MarkdownBuilder


# ---------------------------------------------------------------------------
# Zero-Mock Physical Fixtures (Real Disk I/O via tmp_path)
# ---------------------------------------------------------------------------


@pytest.fixture
def hdf5_physical_payload(tmp_path: pathlib.Path) -> pathlib.Path:
    """Generates a physical landscape.h5 file with authentic HDF5 hierarchies on real disk.

    Under the Zero-Mock mandate, this fixture writes real numerical arrays and attributes
    using h5py in latest library format without mock bypasses.

    Args:
        tmp_path: pytest temporary directory fixture on physical storage.

    Returns:
        Resolved pathlib.Path to the created landscape.h5 file.
    """
    h5_path = (tmp_path / "landscape.h5").resolve()
    with h5py.File(h5_path, mode="w", libver="latest") as h5f:
        # 1. Conformers hierarchy
        conf_group = h5f.create_group("conformers")

        c1 = conf_group.create_group("conf_01")
        c1.attrs["relative_energy"] = 0.0000
        c1.attrs["point_group_symmetry"] = "C2v"

        c2 = conf_group.create_group("conf_02")
        c2.attrs["relative_energy"] = 0.0035
        c2.attrs["point_group_symmetry"] = "Cs"

        # 2. Spectroscopy hierarchy
        spec_group = h5f.create_group("spectroscopy")
        spec_group.create_dataset(
            "rotational_constants",
            data=np.array([5420.5, 2810.2, 1950.8], dtype=np.float64),
        )
        spec_group.create_dataset(
            "dipole_moments",
            data=np.array([1.85, 0.42, 0.0], dtype=np.float64),
        )

        # 3. Thermodynamics hierarchy
        thermo_group = h5f.create_group("thermodynamics")
        thermo_group.attrs["zero_point_energy"] = 0.0854
        thermo_group.attrs["enthalpy"] = -154.0321
        thermo_group.attrs["gibbs_free_energy"] = -154.0654
        thermo_group.create_dataset(
            "vibrational_frequencies",
            data=np.array([450.2, 820.5, 1450.0, 3100.4], dtype=np.float64),
        )

    return h5_path


@pytest.fixture
def sample_metadata_and_telemetry(
    tmp_path: pathlib.Path,
) -> Dict[str, Any]:
    """Generates authentic JSON audit logs, deployment manifests, and metadata dictionary on disk.

    Args:
        tmp_path: pytest temporary directory fixture.

    Returns:
        Dictionary containing metadata, file paths, telemetry, and engine configs.
    """
    audit_log_path = tmp_path / "cochem_audit_log.json"
    audit_data = {
        "wall_clock_seconds": 142.5,
        "gpu_vram_peak_mb": 4250.0,
        "cpu_peak_percent": 88.5,
        "warnings": [
            "SCF convergence required dampening on step 4.",
            "GPU VRAM spike near 85%.",
        ],
    }
    audit_log_path.write_text(json.dumps(audit_data, indent=2), encoding="utf-8")

    manifest_path = tmp_path / "cochem_deployment_manifest.json"
    manifest_data = {
        "ORCA": "6.1.1",
        "xTB": "6.7.1",
        "MACE-OFF23": "2023.1",
    }
    manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    metadata = {
        "title": "CoChem Computational Analysis User Guide",
        "version": "2.0.0",
        "generated_at": "2026-08-23T12:00:00",
        "pipeline_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "environment": "Local-Linux (Debian)",
        "fair_compliance": True,
        "audit_log_file": audit_log_path,
        "deployment_manifest_file": manifest_path,
        "raw_telemetry": audit_data,
        "raw_engines": manifest_data,
    }
    return metadata


@pytest.fixture
def sample_conformer_dataframe() -> pd.DataFrame:
    """Returns a real pandas.DataFrame containing conformer energetic and geometric ranking data.

    Returns:
        Structured DataFrame with conformer IDs, energies, symmetry, and Boltzmann weights.
    """
    return pd.DataFrame({
        "Conformer ID": ["Conf_01", "Conf_02", "Conf_03"],
        "Relative Energy (kcal/mol)": [0.000, 0.423, 1.875],
        "Hartree Energy (Eh)": [-154.1234567, -154.1227891, -154.1204682],
        "Symmetry": ["C2v", "Cs", "C1"],
        "Boltzmann Population (%)": [68.4, 24.1, 7.5],
    })


# ---------------------------------------------------------------------------
# Required Test Cases (Tasks 61–70)
# ---------------------------------------------------------------------------


def test_markdown_builder_initialization_and_dynamic_pathing(
    tmp_path: pathlib.Path,
) -> None:
    """Test Case 1: MarkdownBuilder Initialization & Default Dynamic Pathing (Tasks 61 & 68).

    Verifies default and custom output directory resolution using pathlib.Path,
    automatic parent directory creation, and zero reliance on POSIX-only $HOME.
    """
    # 1. Default initialization resolves to ~/CoChem_Artifacts/Report_Archive
    default_builder = MarkdownBuilder()
    assert isinstance(default_builder, MarkdownBuilder)
    expected_default = (
        pathlib.Path.home() / "CoChem_Artifacts" / "Report_Archive"
    ).resolve()
    assert default_builder.output_dir == expected_default
    assert default_builder.base_filename == "CoChem_User_Guide.md"
    assert default_builder.filename == "CoChem_User_Guide.md"
    assert isinstance(default_builder.output_dir, pathlib.Path)

    # 2. Custom output directory and filename initialization
    custom_target = tmp_path / "custom_reports" / "sub_archive"
    assert not custom_target.exists()
    custom_builder = MarkdownBuilder(
        output_dir=custom_target, filename="custom_guide.md"
    )
    assert custom_builder.output_dir == custom_target.resolve()
    assert custom_builder.base_filename == "custom_guide.md"
    assert custom_builder.filename == "custom_guide.md"
    assert custom_target.exists()
    assert custom_target.is_dir()

    # 3. Verify path resolution is pure Python pathlib without POSIX shell $HOME dependency
    assert not str(custom_builder.output_dir).startswith("$")


def test_yaml_frontmatter_and_system_matrix_generation(
    tmp_path: pathlib.Path,
    sample_metadata_and_telemetry: Dict[str, Any],
) -> None:
    """Test Case 2: YAML Frontmatter & Stage 0 System Matrix Generation (Task 62).

    Verifies valid YAML frontmatter delimiter bounding and strict key-value parsing,
    along with Stage 0 system execution environment readout containing active engines,
    host architecture, and pipeline SHA-256 configuration hash.
    """
    builder = MarkdownBuilder(output_dir=tmp_path)
    metadata = sample_metadata_and_telemetry

    # 1. Test YAML Frontmatter Generation
    frontmatter = builder.generate_yaml_frontmatter(metadata)
    assert frontmatter.startswith("---\n")
    assert frontmatter.endswith("\n---")

    # Strip bounding lines and parse with safe_load
    yaml_body = frontmatter.strip("-").strip()
    parsed = yaml.safe_load(yaml_body)
    assert isinstance(parsed, dict)
    assert parsed["title"] == "CoChem Computational Analysis User Guide"
    assert parsed["version"] == "2.0.0"
    assert parsed["generated_at"] == "2026-08-23T12:00:00"
    assert (
        parsed["pipeline_hash"]
        == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    assert parsed["environment"] == "Local-Linux (Debian)"
    assert parsed["fair_compliance"] is True

    # 2. Test Stage 0 System Matrix Section Generation
    engines_dict = metadata["raw_engines"]
    system_matrix = {
        "engines": engines_dict,
        "host": {
            "environment_tier": "Local-Linux (Debian)",
            "node_architecture": "x86_64",
            "cpu_cores": 32,
            "gpu_model": "NVIDIA A100-SXM4-80GB",
            "host_ram": "128 GB",
            "python_version": "3.10.12",
            "config_hash": metadata["pipeline_hash"],
        },
    }
    sys_section = builder.generate_system_matrix_section(system_matrix)

    assert "## 1. System Execution Environment & Provenance" in sys_section
    assert "### 1.1 Compute Engines & Versions" in sys_section
    assert "- **ORCA**: `6.1.1`" in sys_section
    assert "- **xTB**: `6.7.1`" in sys_section
    assert "- **MACE-OFF23**: `2023.1`" in sys_section
    assert "### 1.2 Host Architecture & Resource Allocation" in sys_section
    assert "- **Environment Tier**: Local-Linux (Debian)" in sys_section
    assert "- **Node Architecture**: x86_64" in sys_section
    assert "- **CPU Allocation**: 32" in sys_section
    assert "- **GPU Device**: NVIDIA A100-SXM4-80GB" in sys_section
    assert "- **Host RAM**: 128 GB" in sys_section
    assert "- **Python Runtime Version**: `3.10.12`" in sys_section
    assert f"- **Configuration SHA-256**: `{metadata['pipeline_hash']}`" in sys_section


def test_dynamic_mermaid_flowchart_synthesis() -> None:
    """Test Case 3: Dynamic Mermaid.js Flowchart Synthesis (Task 63).

    Verifies dynamic Mermaid.js graph TD diagram generation mapping active stages,
    ensuring standard stage nodes, directed edge transitions, and valid Markdown rendering.
    """
    builder = MarkdownBuilder()

    # 1. Flowchart for specific active stages list
    active_stages = ["Stage 0.0", "Stage 1.0", "Stage 2.0", "Stage 6.0"]
    flowchart = builder.generate_mermaid_flowchart(active_stages)

    assert "```mermaid" in flowchart
    assert "graph TD" in flowchart
    assert "```" in flowchart
    assert 'S0["Stage 0.0: Configuration & Resource Guards"]' in flowchart
    assert 'S1["Stage 1.0: Conformer Generation"]' in flowchart
    assert 'S2["Stage 2.0: DFT Optimization"]' in flowchart
    assert 'S6["Stage 6.0: SCRIBE Document Synthesis"]' in flowchart
    assert "-->" in flowchart

    # Verify inactive stages are NOT rendered when an explicit list is provided
    assert "S3" not in flowchart
    assert "S4" not in flowchart
    assert "S5" not in flowchart

    # 2. Flowchart for single stage (no edge transition)
    single_chart = builder.generate_mermaid_flowchart(["Stage 0.0"])
    assert 'S0["Stage 0.0: Configuration & Resource Guards"]' in single_chart
    assert "-->" not in single_chart

    # 3. Default flowchart when None passed renders all stages
    default_chart = builder.generate_mermaid_flowchart()
    assert "S0" in default_chart
    assert "S1" in default_chart
    assert "S2" in default_chart
    assert "S3" in default_chart
    assert "S4" in default_chart
    assert "S5" in default_chart
    assert "S6" in default_chart


def test_gfm_table_pipe_formatting(
    sample_conformer_dataframe: pd.DataFrame,
) -> None:
    """Test Case 4: GitHub-Flavored Markdown (GFM) Table Pipe Formatting (Task 65).

    Verifies conversion of real pandas DataFrames into standard GFM pipe-delimited tables,
    alignment rows, numeric precision preservation, empty DataFrame fallback, and table titles.
    """
    builder = MarkdownBuilder()

    # 1. Format sample conformer DataFrame
    table_output = builder.format_gfm_table(
        sample_conformer_dataframe, table_title="Conformer Energetic Ranking"
    )

    assert "### Conformer Energetic Ranking" in table_output
    assert (
        "| Conformer ID | Relative Energy (kcal/mol) | Hartree Energy (Eh) | Symmetry | Boltzmann Population (%) |"
        in table_output
    )
    # Check alignment row
    assert "| :--- | ---: | ---: | :--- | ---: |" in table_output
    # Check data rows and precision formatting
    assert "| Conf_01 | 0.00 | -154.123457 | C2v | 68.40 |" in table_output
    assert "| Conf_02 | 0.42 | -154.122789 | Cs | 24.10 |" in table_output
    assert "| Conf_03 | 1.88 | -154.120468 | C1 | 7.50 |" in table_output

    # 2. Empty DataFrame returns graceful fallback indicator
    empty_df = pd.DataFrame()
    empty_output = builder.format_gfm_table(empty_df, table_title="Empty Table")
    assert "### Empty Table" in empty_output
    assert "*No tabular data available.*" in empty_output

    # 3. None input returns graceful fallback without crashing
    none_output = builder.format_gfm_table(None)
    assert "*No tabular data available.*" in none_output


def test_thermodynamic_insights_injection_and_token_scrubbing() -> None:
    """Test Case 5: Thermodynamic Analytical Insights Injection & Token Scrubbing (Task 64).

    Verifies rendering of section ## 2. Thermodynamic & Structural Analysis,
    placeholder token sanitization (<<INSERT_*>>, [PLACEHOLDER]), and empty/None fallback.
    """
    builder = MarkdownBuilder()

    # 1. Narrative with internal placeholder tokens to scrub
    raw_insights = (
        "The global minimum conformer demonstrates significant stabilization. "
        "<<INSERT_THERMO_TABLE>> The calculated barrier is 14.5 kcal/mol. "
        "[PLACEHOLDER] Vibrational zero-point energy indicates strong zero-point motion."
    )
    rendered = builder.inject_thermodynamic_insights(raw_insights)

    assert "## 2. Thermodynamic & Structural Analysis" in rendered
    assert "The global minimum conformer demonstrates significant stabilization." in rendered
    assert "The calculated barrier is 14.5 kcal/mol." in rendered
    assert "Vibrational zero-point energy indicates strong zero-point motion." in rendered
    assert "<<INSERT_THERMO_TABLE>>" not in rendered
    assert "[PLACEHOLDER]" not in rendered

    # 2. Passing empty string or None renders clean professional fallback
    empty_rendered = builder.inject_thermodynamic_insights("")
    assert "## 2. Thermodynamic & Structural Analysis" in empty_rendered
    assert (
        "*Analytical data was aggregated without additional narrative commentary.*"
        in empty_rendered
    )

    none_rendered = builder.inject_thermodynamic_insights(None)
    assert "## 2. Thermodynamic & Structural Analysis" in none_rendered
    assert (
        "*Analytical data was aggregated without additional narrative commentary.*"
        in none_rendered
    )


def test_audit_warnings_callout_blockquotes_and_hardware_telemetry(
    tmp_path: pathlib.Path,
    sample_metadata_and_telemetry: Dict[str, Any],
) -> None:
    """Test Case 6: Audit Warnings Callout Blockquotes & Hardware Telemetry (Tasks 66 & 67).

    Verifies aggregation of non-fatal audit log warnings into GitHub-style callouts,
    empty warnings fallback, and formatting of hardware telemetry section with GPU, CPU,
    and wall-clock execution metrics.
    """
    builder = MarkdownBuilder(output_dir=tmp_path)
    telemetry_data = sample_metadata_and_telemetry["raw_telemetry"]

    # 1. Non-empty warnings formatting
    warnings = telemetry_data["warnings"]
    warning_block = builder.format_warning_blockquotes(warnings)
    assert "> **WARNING**: SCF convergence required dampening on step 4." in warning_block
    assert "> **WARNING**: GPU VRAM spike near 85%." in warning_block

    # 2. Empty warnings fallback
    empty_block = builder.format_warning_blockquotes([])
    assert (
        "> **NOTE**: No non-fatal execution warnings recorded during this pipeline run."
        in empty_block
    )

    none_block = builder.format_warning_blockquotes(None)
    assert (
        "> **NOTE**: No non-fatal execution warnings recorded during this pipeline run."
        in none_block
    )

    # 3. Hardware telemetry section formatting
    telem_section = builder.format_telemetry_section(telemetry_data)
    assert "## 4. Hardware Telemetry & Compute Resource Allocation" in telem_section
    assert "- **Peak GPU VRAM Usage**: 4250.0 MB" in telem_section
    assert "- **Peak CPU Usage**: 88.5%" in telem_section
    assert "- **Wall-Clock Execution Time**: 142.50 s" in telem_section


def test_non_destructive_timestamped_overwrite_protection(
    tmp_path: pathlib.Path,
) -> None:
    """Test Case 7: Non-Destructive Timestamped Overwrite Protection & File Persistence (Tasks 68 & 69).

    Verifies that calling write_user_guide multiple times preserves existing files on disk,
    creates timestamped copies with pattern CoChem_User_Guide_*.md, and maintains UTF-8 encoding.
    """
    output_dir = tmp_path / "protected_reports"
    builder = MarkdownBuilder(
        output_dir=output_dir, filename="CoChem_User_Guide.md"
    )

    # 1. Write initial document
    initial_content = "# CoChem User Guide - Run 1\n\nInitial computational run."
    file_1 = builder.write_user_guide(initial_content)

    assert file_1.exists()
    assert file_1.is_file()
    assert file_1.name == "CoChem_User_Guide.md"
    assert file_1.read_text(encoding="utf-8") == initial_content

    # 2. Write second document to the same location
    second_content = "# CoChem User Guide - Run 2\n\nUpdated pipeline execution."
    file_2 = builder.write_user_guide(second_content)

    assert file_2.exists()
    assert file_2.is_file()
    assert file_2 != file_1
    assert re.match(r"^CoChem_User_Guide_\d{8}_\d{6}(?:_\d+)?\.md$", file_2.name) is not None
    assert file_2.suffix == ".md"

    # 3. Assert original file remains completely unmodified
    assert file_1.read_text(encoding="utf-8") == initial_content
    assert file_2.read_text(encoding="utf-8") == second_content


def test_end_to_end_user_guide_generation(
    tmp_path: pathlib.Path,
    hdf5_physical_payload: pathlib.Path,
    sample_metadata_and_telemetry: Dict[str, Any],
    sample_conformer_dataframe: pd.DataFrame,
) -> None:
    """Test Case 8: End-to-End User Guide Generation (Tasks 61–70).

    Assembles a full data payload containing YAML metadata, Stage 0 system matrix,
    conformer DataFrames, thermodynamic scalars, spectroscopic tables, audit warnings,
    and hardware telemetry. Executes build_user_guide and writes the result to disk.
    """
    builder = MarkdownBuilder(output_dir=tmp_path / "final_guide")

    # Read physical data from the authentic HDF5 file
    with h5py.File(hdf5_physical_payload, mode="r") as h5f:
        zpe = float(h5f["/thermodynamics"].attrs["zero_point_energy"])
        enthalpy = float(h5f["/thermodynamics"].attrs["enthalpy"])
        gibbs = float(h5f["/thermodynamics"].attrs["gibbs_free_energy"])
        vib_freqs = h5f["/thermodynamics/vibrational_frequencies"][:]
        rot_consts = h5f["/spectroscopy/rotational_constants"][:]

    thermo_df = pd.DataFrame({
        "Property": ["Zero-Point Energy (ZPE)", "Enthalpy (H)", "Gibbs Free Energy (G)"],
        "Value (Hartree)": [zpe, enthalpy, gibbs],
    })

    vib_df = pd.DataFrame({
        "Mode #": list(range(1, len(vib_freqs) + 1)),
        "Frequency (cm-1)": vib_freqs,
    })

    metadata = sample_metadata_and_telemetry
    telemetry = metadata["raw_telemetry"]
    engines = metadata["raw_engines"]

    payload: Dict[str, Any] = {
        "metadata": {
            "title": metadata["title"],
            "version": metadata["version"],
            "generated_at": metadata["generated_at"],
            "pipeline_hash": metadata["pipeline_hash"],
            "environment": metadata["environment"],
            "fair_compliance": metadata["fair_compliance"],
        },
        "overview": (
            "Complete computational quantum chemistry report for conformer exploration, "
            "vibrational spectroscopy, and thermodynamic state functions."
        ),
        "system_matrix": {
            "engines": engines,
            "host": {
                "environment_tier": metadata["environment"],
                "node_architecture": "x86_64",
                "cpu_cores": 32,
                "gpu_model": "NVIDIA A100-SXM4-80GB",
                "host_ram": "128 GB",
                "python_version": "3.10.12",
                "config_hash": metadata["pipeline_hash"],
            },
        },
        "active_stages": ["Stage 0.0", "Stage 1.0", "Stage 2.0", "Stage 3.0", "Stage 6.0"],
        "conformers_df": sample_conformer_dataframe,
        "thermodynamics_df": thermo_df,
        "thermodynamic_insights": (
            "Conformational search identified Conf_01 as the global minimum. "
            "<<INSERT_THERMO>> Vibrational analysis confirms all real frequencies."
        ),
        "vibrational_df": vib_df,
        "warnings": telemetry["warnings"],
        "telemetry": telemetry,
    }

    # Execute build_user_guide
    generated_md = builder.build_user_guide(payload)

    assert isinstance(generated_md, str)
    assert len(generated_md) > 0

    # 1. Frontmatter
    assert generated_md.startswith("---\n")
    assert "fair_compliance: true" in generated_md.lower()

    # 2. Title & Overview
    assert "# CoChem Computational Analysis User Guide" in generated_md
    assert "Complete computational quantum chemistry report" in generated_md

    # 3. System Matrix
    assert "## 1. System Execution Environment & Provenance" in generated_md
    assert "- **ORCA**: `6.1.1`" in generated_md

    # 4. Flowchart
    assert "## Pipeline Execution Flowchart" in generated_md
    assert "```mermaid" in generated_md
    assert 'S0["Stage 0.0: Configuration & Resource Guards"]' in generated_md

    # 5. Conformer Landscape Table
    assert "### Conformer Landscape" in generated_md
    assert "| Conf_01 | 0.00 | -154.123457 | C2v | 68.40 |" in generated_md

    # 6. Thermodynamic Analysis & Table
    assert "## 2. Thermodynamic & Structural Analysis" in generated_md
    assert "Conformational search identified Conf_01 as the global minimum." in generated_md
    assert "<<INSERT_THERMO>>" not in generated_md
    assert "| Zero-Point Energy (ZPE) | 0.085400 |" in generated_md

    # 7. Vibrational / Spectroscopic Analysis Table
    assert "## Spectroscopic & Vibrational Analysis" in generated_md
    assert "| 1 | 450.20 |" in generated_md

    # 8. Execution Warnings
    assert "### Execution Warnings & Audit Trail" in generated_md
    assert "> **WARNING**: SCF convergence required dampening on step 4." in generated_md

    # 9. Hardware Telemetry
    assert "## 4. Hardware Telemetry & Compute Resource Allocation" in generated_md
    assert "- **Peak GPU VRAM Usage**: 4250.0 MB" in generated_md
    assert "- **Peak CPU Usage**: 88.5%" in generated_md

    # Write document to disk and verify integrity
    written_file = builder.write_user_guide(generated_md)
    assert written_file.exists()
    assert written_file.is_file()
    assert written_file.read_text(encoding="utf-8") == generated_md


# ---------------------------------------------------------------------------
# Backwards Compatibility Discovery Aliases
# ---------------------------------------------------------------------------
test_markdown_builder_initialization = (
    test_markdown_builder_initialization_and_dynamic_pathing
)
test_yaml_frontmatter_and_system_matrix = (
    test_yaml_frontmatter_and_system_matrix_generation
)
test_mermaid_flowchart_generation = test_dynamic_mermaid_flowchart_synthesis
test_mermaid_flowchart_synthesis = test_dynamic_mermaid_flowchart_synthesis
test_dataframe_to_gfm_table = test_gfm_table_pipe_formatting
test_thermodynamic_insights_scrubbing = (
    test_thermodynamic_insights_injection_and_token_scrubbing
)
test_audit_warnings_and_telemetry_formatting = (
    test_audit_warnings_callout_blockquotes_and_hardware_telemetry
)
test_save_user_guide_overwrite_protection = (
    test_non_destructive_timestamped_overwrite_protection
)
test_build_user_guide_e2e = test_end_to_end_user_guide_generation

