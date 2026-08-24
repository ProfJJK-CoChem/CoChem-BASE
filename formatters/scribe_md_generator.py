"""Dynamic Markdown User Guide Compiler for CoChem-SCRIBE (Stage 6.3).

Synthesizes structured CoChem_User_Guide.md reports containing YAML frontmatter,
Stage 0 provenance metadata, dynamic Mermaid.js execution flowcharts,
GitHub-Flavored Markdown (GFM) tables, thermodynamic analytical insights,
non-fatal warning callout blockquotes, hardware telemetry metrics, and
non-destructive timestamped overwrite protection.
"""

from __future__ import annotations

import logging
import pathlib
import re
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
import yaml

logger = logging.getLogger(__name__)

# Constants for formatting thresholds
VRAM_THRESHOLD_MB: float = 100.0
RAM_THRESHOLD_MB: float = 100.0
HIGH_VAL_THRESHOLD: float = 10000.0
LOW_VAL_THRESHOLD: float = 1e-4

# Standard Stage definition catalog for Mermaid diagram synthesis
STAGE_DEFINITIONS: dict[str, tuple[str, str]] = {
    "0.0": ("S0", "Stage 0.0: Configuration & Resource Guards"),
    "1.0": ("S1", "Stage 1.0: Conformer Generation (CREST/ORCA)"),
    "2.0": ("S2", "Stage 2.0: Geometry Optimization"),
    "3.0": ("S3", "Stage 3.0: Frequency & Thermochemistry"),
    "4.0": ("S4", "Stage 4.0: Spectroscopic Analysis (TORQ)"),
    "5.0": ("S5", "Stage 5.0: Voigt Spectral Deconvolution (SpycFit)"),
    "6.0": ("S6", "Stage 6.0: Document Synthesis (SCRIBE)"),
}


class MarkdownBuilder:
    """Dynamic Markdown User Guide Compiler for CoChem-SCRIBE.

    Synthesizes structured CoChem_User_Guide.md reports containing YAML
    frontmatter, Stage 0 provenance metadata, dynamic Mermaid.js execution
    flowcharts, GitHub-Flavored Markdown (GFM) tables, thermodynamic
    analytical insights, non-fatal warning callout blockquotes, hardware
    telemetry metrics, and non-destructive timestamped overwrite protection.
    """

    def __init__(
        self,
        output_dir: str | pathlib.Path | None = None,
        filename: str = "CoChem_User_Guide.md",
    ) -> None:
        """Initializes MarkdownBuilder with dynamic path resolution.

        Args:
            output_dir: Optional directory for output markdown. Defaults to
                Path.home() / "CoChem_Artifacts" / "Report_Archive".
            filename: Target output markdown filename. Defaults to
                "CoChem_User_Guide.md".
        """
        if output_dir is not None:
            self.output_dir = pathlib.Path(output_dir).resolve()
        else:
            self.output_dir = (
                pathlib.Path.home() / "CoChem_Artifacts" / "Report_Archive"
            ).resolve()

        self.filename = filename
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_yaml_frontmatter(
        self, metadata: dict[str, Any] | None = None
    ) -> str:
        """Generates strict YAML frontmatter containing run metadata.

        Args:
            metadata: Run metadata dictionary.

        Returns:
            Strict YAML frontmatter block enclosed in '---'.
        """
        meta = metadata.copy() if metadata else {}

        # Ensure default core fields if missing
        if "title" not in meta:
            meta["title"] = "CoChem Computational Analysis User Guide"
        if "generated_at" not in meta:
            meta["generated_at"] = datetime.now().isoformat()
        if "version" not in meta:
            meta["version"] = "2.0.0"
        if "pipeline_hash" not in meta:
            meta["pipeline_hash"] = "N/A"
        if "environment" not in meta:
            meta["environment"] = "Local-Windows WSL"
        if "fair_compliance" not in meta:
            meta["fair_compliance"] = True

        yaml_content = yaml.safe_dump(
            meta, sort_keys=False, default_flow_style=False
        ).strip()
        return f"---\n{yaml_content}\n---"

    def generate_system_matrix_section(
        self, system_matrix: dict[str, Any] | None = None
    ) -> str:
        """Generates Stage 0 system matrix readout for audit compliance.

        Args:
            system_matrix: System configuration and execution environment data.

        Returns:
            Formatted Markdown section under 1. System Execution Environment.
        """
        matrix = system_matrix or {}
        lines: list[str] = [
            "## 1. System Execution Environment & Provenance",
            "",
            "### 1.1 Compute Engines & Versions",
        ]

        engines = matrix.get("engines", {})
        if isinstance(engines, dict) and engines:
            for engine, ver in engines.items():
                lines.append(f"- **{engine}**: `{ver}`")
        elif isinstance(engines, list) and engines:
            for item in engines:
                lines.append(f"- `{item}`")
        else:
            lines.append("- *No discrete calculation engines registered.*")

        lines.append("")
        lines.append("### 1.2 Host Architecture & Resource Allocation")

        host_info = (
            matrix.get("host", {})
            if isinstance(matrix.get("host"), dict)
            else matrix
        )

        env_tier = (
            host_info.get("environment_tier")
            or host_info.get("environment")
            or matrix.get("environment", "Unknown / Heterogeneous")
        )
        cpu_cores = (
            host_info.get("cpu_cores")
            or host_info.get("cpu")
            or matrix.get("cpu_cores", "N/A")
        )
        gpu_device = (
            host_info.get("gpu_device")
            or host_info.get("gpu")
            or host_info.get("gpu_model")
            or matrix.get("gpu_device", "N/A")
        )
        host_ram = (
            host_info.get("host_ram")
            or host_info.get("host_ram_gb")
            or host_info.get("ram_gb")
            or matrix.get("host_ram", "N/A")
        )
        cfg_hash = (
            matrix.get("config_hash")
            or matrix.get("pipeline_hash")
            or host_info.get("config_hash", "N/A")
        )

        lines.append(f"- **Environment Tier**: {env_tier}")
        lines.append(f"- **CPU Allocation**: {cpu_cores}")
        lines.append(f"- **GPU Device**: {gpu_device}")
        lines.append(f"- **Host RAM**: {host_ram}")
        lines.append(f"- **Configuration SHA-256**: `{cfg_hash}`")
        lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _resolve_stage_node(
        stage_item: str, custom_idx: int
    ) -> tuple[str, str, int]:
        """Resolves a single stage string into a node ID, label, and updated index."""
        stage_clean = stage_item.strip()
        for key, (node_id, label) in STAGE_DEFINITIONS.items():
            major = key.split(".")[0]
            pattern = (
                rf"(?<![\d.])(?:Stage\s+)?(?:{re.escape(key)}|{major}(?!\d))(?![\d.])"
            )
            if (
                re.search(pattern, stage_clean, flags=re.IGNORECASE)
                or stage_clean == node_id
            ):
                return node_id, label, custom_idx
        cleaned_name = stage_clean.replace('"', "'")
        custom_id = f"S_custom_{custom_idx}"
        return custom_id, cleaned_name, custom_idx + 1

    def _resolve_mermaid_nodes(
        self, active_stages: list[str] | None = None
    ) -> list[tuple[str, str]]:
        """Resolves stage list into ordered Mermaid node definitions."""
        if not active_stages:
            return [
                STAGE_DEFINITIONS[k]
                for k in ["0.0", "1.0", "2.0", "3.0", "4.0", "5.0", "6.0"]
            ]

        resolved_nodes: list[tuple[str, str]] = []
        custom_idx = 1
        for stage_item in active_stages:
            node_id, label, custom_idx = self._resolve_stage_node(
                stage_item, custom_idx
            )
            resolved_nodes.append((node_id, label))
        return resolved_nodes

    def generate_mermaid_flowchart(
        self, active_stages: list[str] | None = None
    ) -> str:
        """Dynamically synthesizes a Mermaid.js diagram (graph TD).

        Args:
            active_stages: Optional list of active stage identifier strings.

        Returns:
            Fenced Mermaid.js flowchart string.
        """
        resolved_nodes = self._resolve_mermaid_nodes(active_stages)

        if not resolved_nodes:
            return (
                "```mermaid\n"
                "graph TD\n"
                '    S0["Stage 0.0: Configuration & Resource Guards"]\n'
                "```"
            )

        lines: list[str] = ["```mermaid", "graph TD"]

        if len(resolved_nodes) == 1:
            node_id, label = resolved_nodes[0]
            lines.append(f'    {node_id}["{label}"]')
        else:
            for i in range(len(resolved_nodes) - 1):
                prev_id, prev_label = resolved_nodes[i]
                curr_id, curr_label = resolved_nodes[i + 1]
                if i == 0:
                    lines.append(
                        f'    {prev_id}["{prev_label}"] --> {curr_id}["{curr_label}"]'
                    )
                else:
                    lines.append(f'    {prev_id} --> {curr_id}["{curr_label}"]')

        lines.append("```")
        return "\n".join(lines)

    def format_gfm_table(
        self, df: pd.DataFrame, title: str | None = None
    ) -> str:
        """Converts a pandas DataFrame into a clean GFM pipe table.

        Args:
            df: Input pandas DataFrame.
            title: Optional title/header for the table.

        Returns:
            GFM formatted table string.
        """
        if df is None or df.empty:
            if title:
                return f"### {title}\n\n*No tabular data recorded.*\n"
            return ""

        headers = [str(col).replace("|", r"\|").strip() for col in df.columns]

        alignments: list[str] = []
        for col in df.columns:
            is_numeric = (
                pd.api.types.is_numeric_dtype(df[col])
                and not pd.api.types.is_bool_dtype(df[col])
            )
            alignments.append("---:" if is_numeric else ":---")

        rows: list[str] = []
        if title:
            rows.append(f"### {title}")
            rows.append("")

        header_line = "| " + " | ".join(headers) + " |"
        rows.append(header_line)

        sep_line = "| " + " | ".join(alignments) + " |"
        rows.append(sep_line)

        for _, row in df.iterrows():
            row_cells = []
            for col in df.columns:
                val = row[col]
                formatted_val = self._format_cell_value(val, str(col))
                row_cells.append(formatted_val)
            rows.append("| " + " | ".join(row_cells) + " |")

        rows.append("")
        return "\n".join(rows)

    @staticmethod
    def _format_cell_value(val: Any, col_name: str) -> str:
        """Formats an individual DataFrame cell for GFM presentation."""
        if pd.isna(val) or val is None:
            return "N/A"

        if isinstance(val, float | np.floating):
            return MarkdownBuilder._format_float_cell(float(val), col_name)

        if isinstance(val, int | np.integer) and not isinstance(val, bool):
            return str(val)

        clean_str = str(val).replace("\r\n", "<br>").replace("\n", "<br>")
        return clean_str.replace("|", r"\|").strip()

    @staticmethod
    def _format_float_cell(val: float, col_name: str) -> str:
        """Formats float values based on column context and magnitude."""
        col_lower = col_name.lower()
        if "hartree" in col_lower or "eh" in col_lower:
            return f"{val:.6f}"
        if any(
            k in col_lower
            for k in [
                "energy",
                "kcal",
                "kj",
                "population",
                "pop",
                "freq",
                "%",
                "intensity",
            ]
        ):
            return f"{val:.2f}"
        if abs(val) >= HIGH_VAL_THRESHOLD or (0 < abs(val) < LOW_VAL_THRESHOLD):
            return f"{val:.4e}"
        return f"{val:.2f}"

    def inject_thermodynamic_insights(
        self, insights_text: str | None = None
    ) -> str:
        """Formats and wraps LLM-generated thermodynamic insights.

        Args:
            insights_text: Narrative text or analytical insights.

        Returns:
            Formatted Markdown section with placeholders scrubbed.
        """
        lines: list[str] = [
            "## 2. Thermodynamic & Structural Analysis",
            "",
        ]

        if not insights_text or not isinstance(insights_text, str):
            lines.append(
                "*Analytical data was aggregated without additional "
                "narrative comments.*"
            )
            lines.append("")
            return "\n".join(lines)

        cleaned = re.sub(
            r"<<INSERT_[^>]*>>", "", insights_text, flags=re.IGNORECASE
        )
        cleaned = re.sub(r"\[PLACEHOLDER\]", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"<<PLACEHOLDER>>", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"<PLACEHOLDER>", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\{\{[^}]*\}\}", "", cleaned)
        cleaned = cleaned.strip()

        if not cleaned:
            lines.append(
                "*Analytical data was aggregated without additional "
                "narrative comments.*"
            )
        else:
            lines.append(cleaned)

        lines.append("")
        return "\n".join(lines)

    def format_warning_blockquotes(
        self, warnings: list[str] | None = None
    ) -> str:
        """Formats non-fatal system warnings into Markdown callout blockquotes.

        Args:
            warnings: Optional list of warning strings.

        Returns:
            Formatted callout blockquote string.
        """
        if not warnings:
            return (
                "> **NOTE**: No non-fatal execution warnings recorded "
                "during this pipeline run.\n"
            )

        lines: list[str] = []
        for w in warnings:
            w_clean = str(w).strip()
            if w_clean:
                lines.append(f"> **WARNING**: {w_clean}")

        if not lines:
            return (
                "> **NOTE**: No non-fatal execution warnings recorded "
                "during this pipeline run.\n"
            )

        return "\n\n".join(lines) + "\n"

    def format_telemetry_section(
        self, telemetry_data: dict[str, Any] | None = None
    ) -> str:
        """Formats peak CPU/GPU usage, wall-clock time, and memory metrics.

        Args:
            telemetry_data: Dictionary of hardware telemetry metrics.

        Returns:
            Formatted Markdown section under 4. Hardware Telemetry.
        """
        telem = telemetry_data or {}

        peak_gpu = (
            telem.get("peak_gpu_vram")
            or telem.get("peak_gpu_vram_mb")
            or telem.get("gpu_vram")
            or telem.get("peak_gpu")
            or telem.get("gpu_peak_vram_mb")
            or "N/A"
        )
        if isinstance(peak_gpu, int | float) and not isinstance(peak_gpu, bool):
            peak_gpu = (
                f"{peak_gpu:.1f} MB"
                if peak_gpu > VRAM_THRESHOLD_MB
                else f"{peak_gpu:.1f} GB"
            )

        peak_cpu = (
            telem.get("peak_cpu_percent")
            or telem.get("cpu_percent")
            or telem.get("peak_cpu")
            or telem.get("cpu_peak_percent")
            or "N/A"
        )
        if isinstance(peak_cpu, int | float) and not isinstance(peak_cpu, bool):
            peak_cpu = f"{peak_cpu:.1f}%"

        wall_clock = (
            telem.get("wall_clock_seconds")
            or telem.get("wall_clock_time")
            or telem.get("execution_time")
            or telem.get("wall_clock")
            or telem.get("elapsed_time")
            or "N/A"
        )
        if isinstance(wall_clock, int | float) and not isinstance(wall_clock, bool):
            wall_clock = f"{wall_clock:.2f} s"

        peak_ram = (
            telem.get("peak_ram_mb")
            or telem.get("peak_host_ram")
            or telem.get("memory_footprint")
            or telem.get("peak_memory")
            or telem.get("host_ram")
            or "N/A"
        )
        if isinstance(peak_ram, int | float) and not isinstance(peak_ram, bool):
            peak_ram = (
                f"{peak_ram:.1f} MB"
                if peak_ram > RAM_THRESHOLD_MB
                else f"{peak_ram:.1f} GB"
            )

        lines: list[str] = [
            "## 4. Hardware Telemetry & Compute Resource Allocation",
            "",
            f"- **Peak GPU VRAM Usage**: {peak_gpu}",
            f"- **Peak CPU Usage**: {peak_cpu}",
            f"- **Wall-Clock Execution Time**: {wall_clock}",
            f"- **Peak Host RAM / Memory Footprint**: {peak_ram}",
            "",
        ]

        extra_keys = {
            k: v
            for k, v in telem.items()
            if k
            not in [
                "peak_gpu_vram",
                "peak_gpu_vram_mb",
                "gpu_vram",
                "peak_gpu",
                "gpu_peak_vram_mb",
                "peak_cpu_percent",
                "cpu_percent",
                "peak_cpu",
                "cpu_peak_percent",
                "wall_clock_seconds",
                "wall_clock_time",
                "execution_time",
                "wall_clock",
                "elapsed_time",
                "peak_ram_mb",
                "peak_host_ram",
                "memory_footprint",
                "peak_memory",
                "host_ram",
            ]
        }
        if extra_keys:
            lines.append("### Additional Telemetry Metrics")
            for k, v in extra_keys.items():
                k_fmt = k.replace("_", " ").title()
                lines.append(f"- **{k_fmt}**: {v}")
            lines.append("")

        return "\n".join(lines)

    def _extract_dataframe(
        self, payload: dict[str, Any], keys: list[str]
    ) -> pd.DataFrame | None:
        """Extracts and standardizes DataFrame from payload given fallback keys."""
        for key in keys:
            val = payload.get(key)
            if val is not None:
                if isinstance(val, pd.DataFrame):
                    return val
                try:
                    if isinstance(val, list | dict):
                        return pd.DataFrame(val)
                except Exception:
                    pass
        return None

    def build_user_guide(
        self, data_payload: dict[str, Any] | None = None
    ) -> str:
        """Assembles the complete CoChem_User_Guide.md document string.

        Args:
            data_payload: Harvested pipeline data and DataFrames.

        Returns:
            Complete GitHub-Flavored Markdown user guide string.
        """
        payload = data_payload or {}
        sections: list[str] = []

        # 1. YAML Frontmatter
        metadata = payload.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        for k in ["title", "pipeline_hash", "environment"]:
            if k in payload and k not in metadata:
                metadata[k] = payload[k]

        sections.append(self.generate_yaml_frontmatter(metadata))

        # 2. Document Title & Executive Overview
        doc_title = metadata.get(
            "title", "CoChem Computational Analysis User Guide"
        )
        overview = (
            payload.get("overview")
            or payload.get("executive_summary")
            or (
                "This document provides a comprehensive summary of the "
                "computational quantum chemistry pipeline execution, including "
                "conformer exploration, thermodynamic properties, vibrational "
                "spectroscopy, and execution provenance."
            )
        )
        sections.append(f"# {doc_title}\n\n{overview}\n")

        # 3. Stage 0 System Matrix & Provenance
        sys_matrix = payload.get("system_matrix", {})
        sys_dict = sys_matrix if isinstance(sys_matrix, dict) else {}
        sections.append(self.generate_system_matrix_section(sys_dict))

        # 4. Dynamic Mermaid.js Workflow Diagram
        active_stages = payload.get("active_stages")
        mermaid_chart = self.generate_mermaid_flowchart(active_stages)
        sections.append(f"## Pipeline Execution Flowchart\n\n{mermaid_chart}\n")

        # 5. Conformer Landscape GFM Table
        conf_df = self._extract_dataframe(
            payload, ["conformers_df", "conformer_df", "conformers"]
        )
        if conf_df is not None and not conf_df.empty:
            conf_table = self.format_gfm_table(
                conf_df, title="Conformer Energetic & Geometric Ranking"
            )
            sections.append(f"### Conformer Landscape\n\n{conf_table}\n")

        # 6. Thermodynamic Insights & Energy GFM Table
        insights = (
            payload.get("thermodynamic_insights")
            or payload.get("insights")
            or ""
        )
        sections.append(self.inject_thermodynamic_insights(insights))

        thermo_df = self._extract_dataframe(
            payload, ["thermodynamics_df", "thermo_df", "energies_df"]
        )
        if thermo_df is not None and not thermo_df.empty:
            thermo_table = self.format_gfm_table(
                thermo_df,
                title="Thermodynamic State Functions & Zero-Point Energies",
            )
            sections.append(f"{thermo_table}\n")

        # 7. Spectroscopic Parameters & Vibrational GFM Table
        vib_df = self._extract_dataframe(
            payload, ["vibrational_df", "spectroscopy_df", "vibrations_df"]
        )
        if vib_df is not None and not vib_df.empty:
            vib_table = self.format_gfm_table(
                vib_df, title="Vibrational Modes & IR Intensities"
            )
            sections.append(
                f"## 3. Spectroscopic & Vibrational Analysis\n\n{vib_table}\n"
            )

        # 8. Non-Fatal Execution Warnings Callout Blockquotes
        warnings = payload.get("warnings")
        sections.append(
            f"### Execution Warnings & Audit Trail\n\n"
            f"{self.format_warning_blockquotes(warnings)}\n"
        )

        # 9. Hardware Telemetry Summary
        telemetry = payload.get("telemetry", {})
        telem_dict = telemetry if isinstance(telemetry, dict) else {}
        sections.append(self.format_telemetry_section(telem_dict))

        return "\n".join(sections).strip() + "\n"

    def write_user_guide(
        self,
        content: str,
        destination_path: str | pathlib.Path | None = None,
    ) -> pathlib.Path:
        """Writes Markdown content to disk with overwrite protection.

        Args:
            content: Markdown formatted text.
            destination_path: Optional explicit file path. If omitted, uses
                self.output_dir / self.filename.

        Returns:
            Resolved pathlib.Path of the written file.
        """
        if destination_path is not None:
            target_path = pathlib.Path(destination_path).resolve()
        else:
            target_path = (self.output_dir / self.filename).resolve()

        target_path.parent.mkdir(parents=True, exist_ok=True)

        if target_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            stem = target_path.stem
            suffix = target_path.suffix
            final_path = target_path.parent / f"{stem}_{timestamp}{suffix}"

            count = 1
            while final_path.exists():
                final_path = (
                    target_path.parent / f"{stem}_{timestamp}_{count}{suffix}"
                )
                count += 1
        else:
            final_path = target_path

        final_path.write_text(content, encoding="utf-8")
        return final_path
