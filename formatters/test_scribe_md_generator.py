"""Zero-Mock Integration and Unit Test Suite for MarkdownBuilder (Stage 6.3).

Verifies dynamic Markdown User Guide compilation, YAML frontmatter
serialization, Mermaid.js workflow diagram synthesis, GFM pipe table
formatting, thermodynamic insights placeholder scrubbing, warning callout
blockquotes, hardware telemetry reporting, and non-destructive timestamped
overwrite protection.
"""

from __future__ import annotations

import pathlib
from typing import Any

import pandas as pd
import yaml

from formatters.scribe_md_generator import MarkdownBuilder


def test_builder_initialization(tmp_path: pathlib.Path) -> None:
    """Verifies default and custom path resolution during initialization."""
    # Test default initialization
    default_builder = MarkdownBuilder()
    assert isinstance(default_builder, MarkdownBuilder)
    expected_default_dir = (
        pathlib.Path.home() / "CoChem_Artifacts" / "Report_Archive"
    ).resolve()
    assert default_builder.output_dir == expected_default_dir
    assert default_builder.filename == "CoChem_User_Guide.md"

    # Test custom output directory initialization
    custom_dir = tmp_path / "custom_reports"
    custom_builder = MarkdownBuilder(
        output_dir=custom_dir, filename="Custom_Guide.md"
    )
    assert custom_builder.output_dir == custom_dir.resolve()
    assert custom_builder.filename == "Custom_Guide.md"
    assert custom_dir.exists()


def test_yaml_frontmatter_and_metadata(tmp_path: pathlib.Path) -> None:
    """Verifies YAML frontmatter generation and yaml.safe_load parsing."""
    builder = MarkdownBuilder(output_dir=tmp_path)
    hash_str = "a1b2c3d4e5f6789012345678abcdef0123456789abcdef0123456789abcdef01"
    metadata: dict[str, Any] = {
        "title": "CoChem Computational Analysis User Guide - Ethanol Conformer",
        "generated_at": "2026-08-24T12:00:00",
        "version": "2.0.0",
        "pipeline_hash": hash_str,
        "environment": "Local-Linux (Debian)",
        "fair_compliance": True,
        "experiment_id": "EXP-2026-ETH-001",
    }

    frontmatter = builder.generate_yaml_frontmatter(metadata)

    assert frontmatter.startswith("---\n")
    assert frontmatter.endswith("\n---")

    # Strip delimiters and parse using real PyYAML safe_load
    stripped_content = frontmatter.strip("-").strip()
    parsed_yaml = yaml.safe_load(stripped_content)

    assert isinstance(parsed_yaml, dict)
    assert (
        parsed_yaml["title"]
        == "CoChem Computational Analysis User Guide - Ethanol Conformer"
    )
    assert parsed_yaml["version"] == "2.0.0"
    assert parsed_yaml["pipeline_hash"] == hash_str
    assert parsed_yaml["environment"] == "Local-Linux (Debian)"
    assert parsed_yaml["fair_compliance"] is True
    assert parsed_yaml["experiment_id"] == "EXP-2026-ETH-001"


def test_mermaid_flowchart_synthesis(tmp_path: pathlib.Path) -> None:
    """Verifies dynamic Mermaid.js flowchart generation for active stages."""
    builder = MarkdownBuilder(output_dir=tmp_path)

    # Test specific active stages subset
    active_stages = ["Stage 0.0", "Stage 1.0", "Stage 2.0", "Stage 6.0"]
    flowchart = builder.generate_mermaid_flowchart(active_stages)

    assert "```mermaid" in flowchart
    assert "graph TD" in flowchart
    assert "```" in flowchart
    assert 'S0["Stage 0.0: Configuration & Resource Guards"]' in flowchart
    assert 'S1["Stage 1.0: Conformer Generation (CREST/ORCA)"]' in flowchart
    assert 'S2["Stage 2.0: Geometry Optimization"]' in flowchart
    assert 'S6["Stage 6.0: Document Synthesis (SCRIBE)"]' in flowchart
    assert "S0" in flowchart and "-->" in flowchart and "S1" in flowchart
    assert "S2" in flowchart and "-->" in flowchart and "S6" in flowchart
    # Verify stages not in subset are omitted
    assert "S3" not in flowchart
    assert "S4" not in flowchart
    assert "S5" not in flowchart

    # Test single stage
    single_flowchart = builder.generate_mermaid_flowchart(["Stage 1.0"])
    assert 'S1["Stage 1.0: Conformer Generation (CREST/ORCA)"]' in single_flowchart
    assert "-->" not in single_flowchart

    # Test stage >= 10 collision protection
    custom_stages = ["Stage 10.0: Post-Process", "Stage 0.0"]
    custom_flowchart = builder.generate_mermaid_flowchart(custom_stages)
    assert 'S_custom_1["Stage 10.0: Post-Process"]' in custom_flowchart
    assert 'S0["Stage 0.0: Configuration & Resource Guards"]' in custom_flowchart

    # Test default stages (None passed)
    default_flowchart = builder.generate_mermaid_flowchart()
    assert 'S0["Stage 0.0: Configuration & Resource Guards"]' in default_flowchart
    assert 'S6["Stage 6.0: Document Synthesis (SCRIBE)"]' in default_flowchart
    assert "S5" in default_flowchart


def test_gfm_table_pipe_formatting(tmp_path: pathlib.Path) -> None:
    """Verifies GFM pipe table conversion from pandas DataFrames."""
    builder = MarkdownBuilder(output_dir=tmp_path)

    data = {
        "Conformer ID": ["Conf_01", "Conf_02", "Conf_03"],
        "Relative Energy (kcal/mol)": [0.000, 0.423, 1.875],
        "Hartree Energy (Eh)": [-154.1234567, -154.1227891, -154.1204682],
        "Symmetry": ["C1", "Cs", "C1"],
        "Boltzmann Population (%)": [68.4, 24.1, 7.5],
        "Notes": ["Global min\nVerified", "Local min", "High energy"],
    }
    df = pd.DataFrame(data)

    table_md = builder.format_gfm_table(df, title="Conformer Distribution")

    assert "### Conformer Distribution" in table_md
    assert (
        "| Conformer ID | Relative Energy (kcal/mol) | "
        "Hartree Energy (Eh) | Symmetry | "
        "Boltzmann Population (%) | Notes |"
    ) in table_md
    assert (
        "| :--- | ---: | ---: | :--- | ---: | :--- |" in table_md
    )
    assert "-154.123457" in table_md
    assert "Global min<br>Verified" in table_md


def test_warning_callouts_and_telemetry(tmp_path: pathlib.Path) -> None:
    """Verifies warning blockquotes and hardware telemetry formatting."""
    builder = MarkdownBuilder(output_dir=tmp_path)

    # 1. Non-empty warnings
    warnings = [
        "SCF convergence required dampening on step 4.",
        "GPU VRAM spike near 90% during Hessian computation.",
    ]
    warning_block = builder.format_warning_blockquotes(warnings)
    assert (
        "> **WARNING**: SCF convergence required dampening on step 4."
        in warning_block
    )
    assert (
        "> **WARNING**: GPU VRAM spike near 90% during Hessian computation."
        in warning_block
    )

    # 2. Empty warnings fallback
    empty_block = builder.format_warning_blockquotes([])
    assert (
        "> **NOTE**: No non-fatal execution warnings recorded during this run."
        in empty_block
        or "No non-fatal execution warnings" in empty_block
    )

    none_block = builder.format_warning_blockquotes(None)
    assert "No non-fatal execution warnings" in none_block

    # 3. Telemetry section
    telemetry = {
        "peak_gpu_vram": "18.4 GB",
        "peak_cpu_percent": 87.5,
        "wall_clock_seconds": 124.58,
        "peak_host_ram": 16384.0,
        "gpu_active": True,
    }
    telemetry_md = builder.format_telemetry_section(telemetry)
    assert (
        "## 4. Hardware Telemetry & Compute Resource Allocation"
        in telemetry_md
    )
    assert "**Peak GPU VRAM Usage**: 18.4 GB" in telemetry_md
    assert "**Peak CPU Usage**: 87.5%" in telemetry_md
    assert "**Wall-Clock Execution Time**: 124.58 s" in telemetry_md
    assert "**Peak Host RAM / Memory Footprint**: 16384.0 MB" in telemetry_md
    assert "**Gpu Active**: True" in telemetry_md


def test_non_destructive_overwrite_protection(tmp_path: pathlib.Path) -> None:
    """Verifies timestamped file creation when target file already exists."""
    output_dir = tmp_path / "guide_output"
    builder = MarkdownBuilder(
        output_dir=output_dir, filename="CoChem_User_Guide.md"
    )

    # Write initial guide
    initial_content = "# Initial Guide\n\nFirst run notes by researcher."
    path_1 = builder.write_user_guide(initial_content)

    assert path_1.exists()
    assert path_1.name == "CoChem_User_Guide.md"
    assert path_1.read_text(encoding="utf-8") == initial_content

    # Write second guide - must NOT overwrite path_1
    second_content = "# Second Guide\n\nUpdated pipeline output data."
    path_2 = builder.write_user_guide(second_content)

    assert path_2.exists()
    assert path_2 != path_1
    assert path_2.name.startswith("CoChem_User_Guide_")
    assert path_2.suffix == ".md"

    # Verify initial file remains unmodified
    assert path_1.read_text(encoding="utf-8") == initial_content
    # Verify second file contains new content
    assert path_2.read_text(encoding="utf-8") == second_content


def test_end_to_end_user_guide_generation(tmp_path: pathlib.Path) -> None:
    """Verifies full end-to-end user guide assembly and disk persistence."""
    output_dir = tmp_path / "e2e_output"
    builder = MarkdownBuilder(
        output_dir=output_dir, filename="CoChem_User_Guide.md"
    )

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

    pipe_hash = (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    payload: dict[str, Any] = {
        "metadata": {
            "title": "Ethanol Conformational & Vibrational User Guide",
            "version": "2.0.0",
            "pipeline_hash": pipe_hash,
            "environment": "Local-Windows WSL",
            "fair_compliance": True,
        },
        "overview": (
            "Detailed conformational analysis of ethanol executed under ORCA."
        ),
        "system_matrix": {
            "engines": {"ORCA": "6.1.1", "xTB": "6.7.1", "MACE": "MACE-OFF23"},
            "host": {
                "environment_tier": "Local-Windows WSL",
                "cpu_cores": 16,
                "gpu_device": "NVIDIA RTX 4090",
                "host_ram": "64 GB",
            },
            "config_hash": pipe_hash,
        },
        "active_stages": [
            "Stage 0.0",
            "Stage 1.0",
            "Stage 2.0",
            "Stage 3.0",
            "Stage 6.0",
        ],
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
    written_path = builder.write_user_guide(markdown_content)

    assert written_path.exists()
    disk_content = written_path.read_text(encoding="utf-8")

    # Assert YAML Frontmatter
    assert disk_content.startswith("---\n")
    assert f"pipeline_hash: {pipe_hash}" in disk_content

    # Assert System Matrix
    assert "## 1. System Execution Environment & Provenance" in disk_content
    assert "- **ORCA**: `6.1.1`" in disk_content
    assert "- **CPU Allocation**: 16" in disk_content

    # Assert Mermaid Chart
    assert "```mermaid" in disk_content
    assert 'S0["Stage 0.0: Configuration & Resource Guards"]' in disk_content
    assert 'S3["Stage 3.0: Frequency & Thermochemistry"]' in disk_content

    # Assert Tables
    assert (
        "| Conformer | Relative Energy (kcal/mol) | Symmetry |" in disk_content
    )
    assert (
        "| Mode # | Frequency (cm-1) | IR Intensity (km/mol) |" in disk_content
    )

    # Assert Insights & Placeholder Scrubbing
    assert "## 2. Thermodynamic & Structural Analysis" in disk_content
    assert (
        "The global minimum conformer exhibits stabilization via internal "
        "hydrogen bonding."
    ) in disk_content
    assert "<<INSERT_PLACEHOLDER>>" not in disk_content

    # Assert Warnings Callout
    assert (
        "> **WARNING**: Low-frequency torsional mode (< 50 cm^-1) detected."
        in disk_content
    )

    # Assert Telemetry
    assert (
        "## 4. Hardware Telemetry & Compute Resource Allocation"
        in disk_content
    )
    assert "**Peak GPU VRAM Usage**: 4.2 GB" in disk_content
    assert (
        "**Wall-Clock Execution Time**: 45.20 s" in disk_content
        or "**Wall-Clock Execution Time**: 45.2 s" in disk_content
    )
