"""Zero-Mock Integration and Unit Test Suite for MarkdownBuilder (Stage 6.3).

Verifies dynamic Markdown User Guide compilation, YAML frontmatter
serialization, Mermaid.js workflow diagram synthesis, GFM pipe table
formatting, thermodynamic insights placeholder scrubbing, warning callout
blockquotes, hardware telemetry reporting, and non-destructive timestamped
overwrite protection.
"""

from __future__ import annotations

import datetime
import pathlib
import re
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pytest
import yaml

from formatters.scribe_md_generator import MarkdownBuilder


def test_markdown_builder_initialization(tmp_path: pathlib.Path) -> None:
    """Verifies default and custom path resolution during initialization (Task 61 & 68)."""
    # 1. Test default initialization
    default_builder = MarkdownBuilder()
    assert isinstance(default_builder, MarkdownBuilder)
    expected_default_dir = (
        pathlib.Path.home() / "CoChem_Artifacts" / "Report_Archive"
    ).resolve()
    assert default_builder.output_dir == expected_default_dir
    assert default_builder.base_filename == "CoChem_User_Guide.md"
    assert default_builder.filename == "CoChem_User_Guide.md"

    # 2. Test custom output directory initialization and auto-creation
    custom_dir = tmp_path / "custom_reports" / "sub_folder"
    assert not custom_dir.exists()
    custom_builder = MarkdownBuilder(
        output_dir=custom_dir, base_filename="Custom_Guide.md"
    )
    assert custom_builder.output_dir == custom_dir.resolve()
    assert custom_builder.base_filename == "Custom_Guide.md"
    assert custom_dir.exists()


def test_yaml_frontmatter_and_system_matrix() -> None:
    """Verifies YAML frontmatter generation and Stage 0 system matrix section (Tasks 61 & 62)."""
    builder = MarkdownBuilder()
    hash_str = "a1b2c3d4e5f6789012345678abcdef0123456789abcdef0123456789abcdef01"
    metadata: Dict[str, Any] = {
        "title": "CoChem Computational Analysis User Guide - Ethanol Conformer",
        "date": "2026-08-24 12:00:00",
        "cochem_version": "2.0.0",
        "run_id": "EXP-2026-ETH-001",
        "target_molecule": "Ethanol",
        "smiles": "CCO",
        "environment_tier": "Local-Linux (Debian)",
        "fair_compliance": True,
        "path_entry": pathlib.Path("/tmp/work_dir"),
        "precision_score": np.float64(99.99),
        "iteration_count": np.int64(42),
    }

    frontmatter = builder.generate_yaml_frontmatter(metadata)

    # Assert YAML delimiters
    assert frontmatter.startswith("---\n")
    assert frontmatter.endswith("\n---")

    # Parse YAML content
    stripped_content = frontmatter.strip("-").strip()
    parsed_yaml = yaml.safe_load(stripped_content)

    assert isinstance(parsed_yaml, dict)
    assert (
        parsed_yaml["title"]
        == "CoChem Computational Analysis User Guide - Ethanol Conformer"
    )
    assert parsed_yaml["cochem_version"] == "2.0.0"
    assert parsed_yaml["run_id"] == "EXP-2026-ETH-001"
    assert parsed_yaml["target_molecule"] == "Ethanol"
    assert parsed_yaml["smiles"] == "CCO"
    assert parsed_yaml["environment_tier"] == "Local-Linux (Debian)"
    assert parsed_yaml["fair_compliance"] is True
    assert parsed_yaml["precision_score"] == 99.99
    assert parsed_yaml["iteration_count"] == 42

    # Test Stage 0 System Matrix section
    system_matrix: Dict[str, Any] = {
        "engines": {"ORCA": "6.1.1", "Gaussian": "G16-C01", "Psi4": "1.9.1", "PySCF": "2.8.0"},
        "host": {
            "environment_tier": "Local-Linux (Debian)",
            "node_architecture": "x86_64",
            "cpu_cores": 32,
            "gpu_model": "NVIDIA A100-SXM4-80GB",
            "host_ram": "128 GB",
            "python_version": "3.10.12",
            "config_hash": hash_str,
        },
    }
    sys_section = builder.generate_system_matrix_section(system_matrix)

    assert "## Computational Provenance & System Matrix" in sys_section
    assert "### 1.1 Compute Engines & Versions" in sys_section
    assert "- **ORCA**: `6.1.1`" in sys_section
    assert "- **Gaussian**: `G16-C01`" in sys_section
    assert "- **Psi4**: `1.9.1`" in sys_section
    assert "- **PySCF**: `2.8.0`" in sys_section
    assert "### 1.2 Host Architecture & Resource Allocation" in sys_section
    assert "- **Environment Tier**: Local-Linux (Debian)" in sys_section
    assert "- **Node Architecture**: x86_64" in sys_section
    assert "- **CPU Allocation**: 32" in sys_section
    assert "- **GPU Device**: NVIDIA A100-SXM4-80GB" in sys_section
    assert "- **Host RAM**: 128 GB" in sys_section
    assert "- **Python Runtime Version**: `3.10.12`" in sys_section
    assert f"- **Configuration SHA-256**: `{hash_str}`" in sys_section


def test_mermaid_flowchart_generation() -> None:
    """Verifies dynamic Mermaid.js flowchart generation for active stages (Task 63)."""
    builder = MarkdownBuilder()

    # Test specific active stages subset
    active_stages = ["0.0", "1.0", "2.0", "3.0", "6.0"]
    flowchart = builder.generate_mermaid_flowchart(active_stages)

    assert "```mermaid" in flowchart
    assert "graph TD" in flowchart
    assert "```" in flowchart
    assert "S0" in flowchart
    assert "S1" in flowchart
    assert "S2" in flowchart
    assert "S3" in flowchart
    assert "S6" in flowchart
    assert "-->" in flowchart

    # Test single stage
    single_flowchart = builder.generate_mermaid_flowchart(["1.0"])
    assert "S1" in single_flowchart
    assert "-->" not in single_flowchart

    # Test custom stage handling with dirty IDs
    custom_stages = [{"id": "Stage 10.0 (Extended)", "name": "Custom Sinc-DVR Extended"}, 0]
    custom_flowchart = builder.generate_mermaid_flowchart(custom_stages)
    assert "S_Stage_10_0__Extended_" in custom_flowchart
    assert "Custom Sinc-DVR Extended" in custom_flowchart
    assert "S0" in custom_flowchart

    # Test default stages when None passed
    default_flowchart = builder.generate_mermaid_flowchart()
    assert "S0" in default_flowchart
    assert "S6" in default_flowchart
    assert "S5" in default_flowchart


def test_dataframe_to_gfm_table() -> None:
    """Verifies GFM pipe table conversion from pandas DataFrames (Task 65)."""
    builder = MarkdownBuilder()

    # 1. Realistic conformer DataFrame with numeric floats and special cells
    conf_data = {
        "Conformer ID": ["Conf_01", "Conf_02", "Conf_03"],
        "Relative Energy (kcal/mol)": [0.000, 0.423, 1.875],
        "Hartree Energy (Eh)": [-154.1234567, -154.1227891, -154.1204682],
        "Symmetry": ["C1", "Cs", "C1"],
        "Boltzmann Population (%)": [68.4, 24.1, 7.5],
        "Notes": ["Global min\nVerified", "Local min", "High energy | Pipe"],
    }
    conf_df = pd.DataFrame(conf_data)

    conf_table = builder.dataframe_to_gfm_table(conf_df, table_title="Conformer Distribution")

    assert "### Conformer Distribution" in conf_table
    assert (
        "| Conformer ID | Relative Energy (kcal/mol) | "
        "Hartree Energy (Eh) | Symmetry | "
        "Boltzmann Population (%) | Notes |"
    ) in conf_table
    assert "-154.123457" in conf_table
    assert "0.42" in conf_table
    assert "Global min<br>Verified" in conf_table
    assert r"High energy \| Pipe" in conf_table

    # 2. Realistic vibrational DataFrame
    vib_data = {
        "Mode #": [1, 2, 3],
        "Frequency (cm-1)": [120.5, 450.2, 3100.8],
        "IR Intensity (km/mol)": [5.2, 34.8, 120.4],
        "Zero-Point Energy (kcal/mol)": [0.17, 0.64, 4.43],
    }
    vib_df = pd.DataFrame(vib_data)
    vib_table = builder.dataframe_to_gfm_table(vib_df, table_title="Vibrational Analysis")
    assert "### Vibrational Analysis" in vib_table
    assert "| Mode # | Frequency (cm-1) | IR Intensity (km/mol) | Zero-Point Energy (kcal/mol) |" in vib_table
    assert "120.50" in vib_table
    assert "34.80" in vib_table

    # 3. Empty DataFrame handling
    empty_df = pd.DataFrame()
    empty_table = builder.dataframe_to_gfm_table(empty_df, table_title="Empty Table")
    assert "### Empty Table" in empty_table
    assert "*No tabular data available.*" in empty_table

    # 4. List of dicts coercion and column newline / substring precision test
    list_records = [
        {"Conformer\nID": "C1", "Dehydration Barrier (kcal/mol)": 15.23456, "Total Energy (Eh)": -154.1234567},
        {"Conformer\nID": "C2", "Dehydration Barrier (kcal/mol)": 18.98765, "Total Energy (Eh)": -154.1122334},
    ]
    coerced_table = builder.dataframe_to_gfm_table(list_records, table_title="Advanced Table")
    assert "### Advanced Table" in coerced_table
    assert "| Conformer<br>ID | Dehydration Barrier (kcal/mol) | Total Energy (Eh) |" in coerced_table
    assert "15.23" in coerced_table
    assert "-154.123457" in coerced_table


def test_audit_warnings_and_telemetry_formatting() -> None:
    """Verifies warning callout blockquotes and hardware telemetry formatting (Tasks 66 & 67)."""
    builder = MarkdownBuilder()

    # 1. Non-empty warnings aggregation with None filtering
    warnings = [
        None,
        "SCF convergence required dampening on step 4.",
        "GPU VRAM spike near 90% during Hessian computation.",
        "None",
    ]
    warning_block = builder.format_audit_warnings(warnings)
    assert (
        "> **WARNING**: SCF convergence required dampening on step 4."
        in warning_block
    )
    assert (
        "> **WARNING**: GPU VRAM spike near 90% during Hessian computation."
        in warning_block
    )
    assert "> **WARNING**: None" not in warning_block

    # 2. String warning handling (prevent character-splitting bug)
    single_warn = "Single non-fatal warning string."
    single_block = builder.format_audit_warnings(single_warn)
    assert "> **WARNING**: Single non-fatal warning string." in single_block
    assert "> **WARNING**: S\n" not in single_block

    # 3. Empty warnings fallback
    empty_block = builder.format_audit_warnings([])
    assert "> **NOTE**: No non-fatal execution warnings recorded" in empty_block

    none_block = builder.format_audit_warnings(None)
    assert "> **NOTE**: No non-fatal execution warnings recorded" in none_block

    # 4. Telemetry formatting with normal and 0.0 values
    telemetry: Dict[str, Any] = {
        "peak_gpu_vram": "18.4 GB",
        "peak_cpu_percent": 87.5,
        "wall_clock_seconds": 124.58,
        "peak_host_ram": 16384.0,
        "gpu_active": True,
    }
    telemetry_md = builder.format_hardware_telemetry(telemetry)
    assert "## Hardware Resource Telemetry" in telemetry_md
    assert "- **Peak GPU VRAM Usage**: 18.4 GB" in telemetry_md
    assert "- **Peak CPU Usage**: 87.5%" in telemetry_md
    assert "- **Wall-Clock Execution Time**: 124.58 s" in telemetry_md
    assert "- **Peak Host RAM / Memory Footprint**: 16384.0 MB" in telemetry_md
    assert "- **Gpu Active**: True" in telemetry_md

    # Test falsy zero telemetry
    zero_telemetry = {
        "peak_gpu_vram": 0.0,
        "peak_cpu_percent": 0.0,
        "wall_clock_seconds": 0.0,
        "peak_ram_mb": 0.0,
    }
    zero_md = builder.format_hardware_telemetry(zero_telemetry)
    assert "- **Peak GPU VRAM Usage**: 0.0 GB" in zero_md
    assert "- **Peak CPU Usage**: 0.0%" in zero_md
    assert "- **Wall-Clock Execution Time**: 0.00 s" in zero_md
    assert "- **Peak Host RAM / Memory Footprint**: 0.0 MB" in zero_md


def test_build_user_guide_e2e() -> None:
    """Verifies end-to-end user guide assembly from a complete payload (Tasks 61–67)."""
    builder = MarkdownBuilder()

    conf_df = pd.DataFrame({
        "Conformer": ["Conf_A", "Conf_B"],
        "Relative Energy (kcal/mol)": [0.0, 1.25],
        "Symmetry": ["C1", "C2"],
    })

    vib_df = pd.DataFrame({
        "Mode #": [1, 2, 3],
        "Frequency (cm-1)": [120.5, 450.2, 3100.8],
        "IR Intensity (km/mol)": [5.2, 34.8, 120.4],
    })

    pipe_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    payload: Dict[str, Any] = {
        "metadata": {
            "title": "Ethanol Conformational & Vibrational User Guide",
            "cochem_version": "2.0.0",
            "run_id": "RUN-2026-0824-001",
            "target_molecule": "Ethanol",
            "smiles": "CCO",
            "environment_tier": "Local-Windows WSL",
            "fair_compliance": True,
        },
        "overview": "Detailed conformational analysis of ethanol executed under ORCA.",
        "system_matrix": {
            "engines": {"ORCA": "6.1.1", "xTB": "6.7.1", "MACE": "MACE-OFF23"},
            "host": {
                "environment_tier": "Local-Windows WSL",
                "node_architecture": "x86_64",
                "cpu_cores": 16,
                "gpu_model": "NVIDIA RTX 4090",
                "host_ram": "64 GB",
                "python_version": "3.10.12",
                "config_hash": pipe_hash,
            },
        },
        "active_stages": ["0.0", "1.0", "2.0", "3.0", "6.0"],
        "conformers_df": conf_df,
        "thermodynamic_insights": (
            "The global minimum conformer exhibits stabilization via "
            "internal hydrogen bonding. <<INSERT_PLACEHOLDER>>"
        ),
        "vibrational_df": vib_df,
        "warnings": ["Low-frequency torsional mode (< 50 cm^-1) detected."],
        "telemetry": {
            "peak_gpu_vram": "4.2 GB",
            "peak_cpu_percent": 65.0,
            "wall_clock_seconds": 45.2,
            "peak_host_ram": "12.8 GB",
        },
    }

    markdown_content = builder.build_user_guide(payload)

    # Assert YAML Frontmatter
    assert markdown_content.startswith("---\n")
    assert "target_molecule: Ethanol" in markdown_content
    assert "smiles: CCO" in markdown_content

    # Assert Overview
    assert "# Ethanol Conformational & Vibrational User Guide" in markdown_content
    assert "Detailed conformational analysis of ethanol executed under ORCA." in markdown_content

    # Assert System Matrix
    assert "## Computational Provenance & System Matrix" in markdown_content
    assert "- **ORCA**: `6.1.1`" in markdown_content
    assert "- **CPU Allocation**: 16" in markdown_content

    # Assert Mermaid Flowchart
    assert "## Pipeline Execution Flowchart" in markdown_content
    assert "```mermaid" in markdown_content
    assert "S0" in markdown_content
    assert "S3" in markdown_content

    # Assert Conformer Table
    assert "### Conformer Landscape" in markdown_content
    assert "| Conformer | Relative Energy (kcal/mol) | Symmetry |" in markdown_content

    # Assert Thermodynamic Analysis & Insights
    assert "## Thermodynamic Analysis" in markdown_content
    assert "The global minimum conformer exhibits stabilization via internal hydrogen bonding." in markdown_content
    assert "<<INSERT_PLACEHOLDER>>" not in markdown_content

    # Assert Spectroscopic Analysis
    assert "## Spectroscopic & Vibrational Analysis" in markdown_content
    assert "| Mode # | Frequency (cm-1) | IR Intensity (km/mol) |" in markdown_content

    # Assert Warnings
    assert "### Execution Warnings & Audit Trail" in markdown_content
    assert "> **WARNING**: Low-frequency torsional mode (< 50 cm^-1) detected." in markdown_content

    # Assert Telemetry
    assert "## Hardware Resource Telemetry" in markdown_content
    assert "- **Peak GPU VRAM Usage**: 4.2 GB" in markdown_content
    assert "- **Peak CPU Usage**: 65.0%" in markdown_content

    # Test malformed payload resilience
    resilient_doc = builder.build_user_guide(None)
    assert "# CoChem Computational Analysis User Guide" in resilient_doc
    assert "## Computational Provenance & System Matrix" in resilient_doc


def test_save_user_guide_overwrite_protection(tmp_path: pathlib.Path) -> None:
    """Verifies non-destructive timestamped overwrite protection on disk (Tasks 68 & 69)."""
    output_dir = tmp_path / "guide_output"
    builder = MarkdownBuilder(
        output_dir=output_dir, base_filename="CoChem_User_Guide.md"
    )

    # 1. Save initial guide
    initial_content = "# Initial Guide\n\nFirst run notes by researcher."
    path_1 = builder.save_user_guide(initial_content)

    assert path_1.exists()
    assert path_1.name == "CoChem_User_Guide.md"
    assert path_1.read_text(encoding="utf-8") == initial_content

    # 2. Save second guide to the same target - must NOT overwrite path_1
    second_content = "# Second Guide\n\nUpdated pipeline output data."
    path_2 = builder.save_user_guide(second_content)

    assert path_2.exists()
    assert path_2 != path_1
    assert re.match(r"^CoChem_User_Guide_\d{8}_\d{6}(?:_\d+)?\.md$", path_2.name) is not None
    assert path_2.suffix == ".md"

    # Verify initial file remains unmodified and second file has new content
    assert path_1.read_text(encoding="utf-8") == initial_content
    assert path_2.read_text(encoding="utf-8") == second_content


# Aliases for backward compatibility test discovery
test_builder_initialization = test_markdown_builder_initialization
test_yaml_frontmatter_and_metadata = test_yaml_frontmatter_and_system_matrix
test_mermaid_flowchart_synthesis = test_mermaid_flowchart_generation
test_gfm_table_pipe_formatting = test_dataframe_to_gfm_table
test_warning_callouts_and_telemetry = test_audit_warnings_and_telemetry_formatting
test_end_to_end_user_guide_generation = test_build_user_guide_e2e
test_non_destructive_overwrite_protection = test_save_user_guide_overwrite_protection

