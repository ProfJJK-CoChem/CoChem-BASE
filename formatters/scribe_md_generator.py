"""Dynamic Markdown User Guide Compiler & GFM Table Generator for CoChem-SCRIBE (Stage 6.3).

Synthesizes structured CoChem_User_Guide.md reports containing YAML frontmatter,
Stage 0 provenance metadata, dynamic Mermaid.js execution flowcharts,
GitHub-Flavored Markdown (GFM) tables, thermodynamic analytical insights,
non-fatal warning callout blockquotes, hardware telemetry metrics, and
non-destructive timestamped overwrite protection.
"""

from __future__ import annotations

import datetime
import logging
import os
import pathlib
import platform
import re
import sys
import tempfile
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
import yaml  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

# Constants for formatting thresholds
VRAM_THRESHOLD_MB: float = 100.0
RAM_THRESHOLD_MB: float = 100.0
HIGH_VAL_THRESHOLD: float = 10000.0
LOW_VAL_THRESHOLD: float = 1e-4

# Standard Stage definition catalog for Mermaid diagram synthesis
STAGE_DEFINITIONS: Dict[str, Tuple[str, str]] = {
    "0.0": ("S0", "Stage 0: Environment & Guards"),
    "1.0": ("S1", "Stage 1: Conformer Generation"),
    "2.0": ("S2", "Stage 2: DFT Optimization"),
    "3.0": ("S3", "Stage 3: Frequency & Thermochemistry"),
    "4.0": ("S4", "Stage 4: Sinc-DVR Dynamic Tunneling"),
    "5.0": ("S5", "Stage 5: Telemetry Aggregation"),
    "6.0": ("S6", "Stage 6: SCRIBE Document Synthesis"),
}

STAGE_DESCRIPTIONS_FALLBACK: Dict[str, str] = {
    "0": "Stage 0: Environment & Guards",
    "0.0": "Stage 0: Environment & Guards",
    "1": "Stage 1: Conformer Generation",
    "1.0": "Stage 1: Conformer Generation",
    "2": "Stage 2: DFT Optimization",
    "2.0": "Stage 2: DFT Optimization",
    "3": "Stage 3: Frequency & Thermochemistry",
    "3.0": "Stage 3: Frequency & Thermochemistry",
    "4": "Stage 4: Sinc-DVR Dynamic Tunneling",
    "4.0": "Stage 4: Sinc-DVR Dynamic Tunneling",
    "5": "Stage 5: Telemetry Aggregation",
    "5.0": "Stage 5: Telemetry Aggregation",
    "6": "Stage 6: SCRIBE Document Synthesis",
    "6.0": "Stage 6: SCRIBE Document Synthesis",
}


def _sanitize_for_yaml(val: Any) -> Any:
    """Recursively converts non-serializable objects (Path, numpy, datetime) into YAML-safe primitives."""
    if val is None:
        return None
    if isinstance(val, (np.floating,)):
        return float(val)
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.bool_,)):
        return bool(val)
    if isinstance(val, bool):
        return bool(val)
    if isinstance(val, int):
        return int(val)
    if isinstance(val, float):
        return float(val)
    if isinstance(val, str):
        return str(val)
    if isinstance(val, (os.PathLike, pathlib.PurePath)):
        if hasattr(val, "as_posix"):
            return val.as_posix()
        return str(val).replace("\\", "/")
    if isinstance(val, np.ndarray):
        return [_sanitize_for_yaml(item) for item in val.tolist()]
    if isinstance(val, (datetime.date, datetime.datetime)):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(val, dict):
        return {str(k): _sanitize_for_yaml(v) for k, v in val.items()}
    if isinstance(val, (list, tuple, set)):
        return [_sanitize_for_yaml(item) for item in val]
    return str(val)


def _get_first_present(data: Dict[str, Any], keys: List[str], default: Any = "N/A") -> Any:
    """Safely retrieves the first present key value, distinguishing between None and falsy zero."""
    for k in keys:
        if k in data and data[k] is not None:
            return data[k]
    return default


_get_present_val = _get_first_present


class MarkdownBuilder:
    """Markdown User Guide and GFM Table synthesis engine for CoChem-SCRIBE (Stage 6.3).

    Generates structured, publication-grade Markdown documentation (CoChem_User_Guide.md)
    enriched with YAML frontmatter, Stage 0 provenance matrices, dynamic Mermaid.js flowcharts,
    GitHub-Flavored Markdown (GFM) tables, thermodynamic analysis narratives, hardware telemetry
    charts, and non-fatal audit warning blockquotes. Enforces cross-platform safe
    pathing and non-destructive timestamped overwrite protection.
    """

    def __init__(
        self,
        output_dir: Optional[Union[str, pathlib.Path]] = None,
        base_filename: str = "CoChem_User_Guide.md",
        filename: Optional[str] = None,
    ) -> None:
        """Initializes MarkdownBuilder with dynamic output directory resolution.

        Args:
            output_dir: Optional directory for output markdown. Defaults to
                Path.home() / "CoChem_Artifacts" / "Report_Archive".
            base_filename: Target output markdown filename. Defaults to
                "CoChem_User_Guide.md".
            filename: Alias for base_filename for backwards compatibility.
        """
        if output_dir is not None:
            self.output_dir = pathlib.Path(output_dir).resolve()
        else:
            self.output_dir = (
                pathlib.Path.home() / "CoChem_Artifacts" / "Report_Archive"
            ).resolve()

        self.base_filename = filename if filename is not None else base_filename
        self.filename = self.base_filename
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info("[SCRIBE-INIT] MarkdownBuilder initialized at %s", self.output_dir)

    def generate_yaml_frontmatter(self, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Generates valid YAML frontmatter block containing run provenance and metadata.

        Args:
            metadata: Run metadata dictionary.

        Returns:
            Strict YAML frontmatter block enclosed in '---'.
        """
        if isinstance(metadata, dict):
            meta = metadata.copy()
        else:
            meta = {}

        # Default core fields if missing
        if "title" not in meta:
            meta["title"] = "CoChem Computational Analysis User Guide"
        if "date" not in meta and "generated_at" not in meta:
            meta["date"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if "cochem_version" not in meta and "version" not in meta:
            meta["cochem_version"] = "2.0.0"
        if "run_id" not in meta and "experiment_id" not in meta and "pipeline_hash" not in meta:
            meta["run_id"] = "N/A"
        if "target_molecule" not in meta:
            meta["target_molecule"] = "N/A"
        if "smiles" not in meta:
            meta["smiles"] = "N/A"
        if "environment_tier" not in meta and "environment" not in meta:
            meta["environment_tier"] = "Local-Windows WSL"
        if "fair_compliance" not in meta:
            meta["fair_compliance"] = True

        sanitized_meta = _sanitize_for_yaml(meta)
        yaml_content = yaml.safe_dump(
            sanitized_meta, sort_keys=False, default_flow_style=False
        ).strip()
        return f"---\n{yaml_content}\n---"

    def generate_system_matrix_section(self, system_matrix: Optional[Dict[str, Any]] = None) -> str:
        """Generates Markdown readout of Stage 0 active computational engines and hardware nodes.

        Args:
            system_matrix: System configuration and execution environment data.

        Returns:
            Formatted Markdown section under ## Computational Provenance & System Matrix.
        """
        matrix = system_matrix if isinstance(system_matrix, dict) else {}
        lines: List[str] = [
            "## Computational Provenance & System Matrix",
            "",
            "### 1.1 Compute Engines & Versions",
        ]

        engines = matrix.get("engines")
        if isinstance(engines, dict) and engines:
            for engine, ver in engines.items():
                lines.append(f"- **{engine}**: `{ver}`")
        elif isinstance(engines, (list, tuple, set)) and engines:
            for item in engines:
                lines.append(f"- `{item}`")
        elif isinstance(engines, str) and engines.strip():
            lines.append(f"- `{engines.strip()}`")
        else:
            lines.append("- *No discrete calculation engines registered.*")

        lines.append("")
        lines.append("### 1.2 Host Architecture & Resource Allocation")

        host_val = matrix.get("host")
        host_info = host_val if isinstance(host_val, dict) else matrix

        env_tier = _get_first_present(
            host_info,
            ["environment_tier", "environment"],
            default=_get_first_present(matrix, ["environment_tier", "environment"], "Unknown / Heterogeneous"),
        )
        node_arch = _get_first_present(
            host_info,
            ["node_architecture", "architecture", "node_arch"],
            default=_get_first_present(matrix, ["node_architecture", "architecture"], platform.machine() or "x86_64"),
        )
        cpu_cores = _get_first_present(
            host_info,
            ["cpu_cores", "cpu", "cores"],
            default=_get_first_present(matrix, ["cpu_cores", "cpu", "cores"], "N/A"),
        )
        gpu_device = _get_first_present(
            host_info,
            ["gpu_model", "gpu_device", "gpu"],
            default=_get_first_present(matrix, ["gpu_model", "gpu_device", "gpu"], "N/A"),
        )
        host_ram = _get_first_present(
            host_info,
            ["host_ram", "memory_allocation", "host_ram_gb", "ram_gb"],
            default=_get_first_present(matrix, ["host_ram", "memory_allocation", "host_ram_gb", "ram_gb"], "N/A"),
        )
        py_version = _get_first_present(
            host_info,
            ["python_version", "python"],
            default=_get_first_present(matrix, ["python_version", "python"], sys.version.split()[0]),
        )
        cfg_hash = _get_first_present(
            matrix,
            ["config_hash", "pipeline_hash"],
            default=_get_first_present(host_info, ["config_hash", "pipeline_hash"], "N/A"),
        )

        lines.append(f"- **Environment Tier**: {env_tier}")
        lines.append(f"- **Node Architecture**: {node_arch}")
        lines.append(f"- **CPU Allocation**: {cpu_cores}")
        lines.append(f"- **GPU Device**: {gpu_device}")
        lines.append(f"- **Host RAM**: {host_ram}")
        lines.append(f"- **Python Runtime Version**: `{py_version}`")
        lines.append(f"- **Configuration SHA-256**: `{cfg_hash}`")
        lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _resolve_stage_node(
        stage_item: Union[str, int, float, Dict[str, Any]], custom_idx: int
    ) -> Tuple[str, str, int]:
        """Resolves a single stage item into a sanitized node ID, label, and updated custom index."""
        if isinstance(stage_item, dict):
            raw_id = str(stage_item.get("id") or stage_item.get("stage") or f"S_custom_{custom_idx}")
            label = str(stage_item.get("name") or stage_item.get("label") or raw_id)
            clean_id = re.sub(r"[^a-zA-Z0-9_]", "_", raw_id)
            if not re.match(r"^S(?:_|\d)", clean_id):
                clean_id = f"S_{clean_id}"
            return clean_id, label.replace('"', "'"), custom_idx + 1

        if isinstance(stage_item, (int, float, np.integer, np.floating)) and not isinstance(stage_item, bool):
            val_float = float(stage_item)
            val_int = int(val_float)
            stage_str = f"{val_int}.0" if val_float == val_int else f"{val_float}"
            if stage_str in STAGE_DEFINITIONS:
                nid, lbl = STAGE_DEFINITIONS[stage_str]
                return nid, lbl, custom_idx
            clean_id = f"S{val_int}" if val_float == val_int else f"S_{str(val_float).replace('.', '_')}"
            return clean_id, f"Stage {stage_str}", custom_idx

        stage_clean = str(stage_item).strip()

        # Direct check in catalog definitions
        for key, (node_id, label) in STAGE_DEFINITIONS.items():
            major = key.split(".")[0]
            pattern = (
                rf"(?<![\d.])(?:Stage\s+)?(?:{re.escape(key)}|{major}(?!\d))(?![\d.])"
            )
            if (
                re.search(pattern, stage_clean, flags=re.IGNORECASE)
                or stage_clean.upper() == node_id.upper()
            ):
                if ":" in stage_clean:
                    cleaned_label = stage_clean.replace('"', "'")
                    return node_id, cleaned_label, custom_idx
                return node_id, label, custom_idx

        cleaned_name = stage_clean.replace('"', "'")
        custom_id = f"S_custom_{custom_idx}"
        return custom_id, cleaned_name, custom_idx + 1

    def _resolve_mermaid_nodes(
        self,
        active_stages: Optional[Sequence[Any]] = None,
    ) -> List[Tuple[str, str]]:
        """Resolves stage list into ordered Mermaid node definitions."""
        if not active_stages:
            return [
                STAGE_DEFINITIONS[k]
                for k in ["0.0", "1.0", "2.0", "3.0", "4.0", "5.0", "6.0"]
            ]

        resolved_nodes: List[Tuple[str, str]] = []
        custom_idx = 1
        for stage_item in active_stages:
            node_id, label, custom_idx = self._resolve_stage_node(
                stage_item, custom_idx
            )
            resolved_nodes.append((node_id, label))
        return resolved_nodes

    def generate_mermaid_flowchart(
        self,
        active_stages: Optional[Sequence[Any]] = None,
    ) -> str:
        """Dynamically synthesizes a Mermaid.js graph TD diagram block mapping active CoChem stages.

        Args:
            active_stages: Optional list or sequence of active stage identifier strings, ints, or dicts.

        Returns:
            Fenced Mermaid.js flowchart string.
        """
        resolved_nodes = self._resolve_mermaid_nodes(active_stages)

        if not resolved_nodes:
            return (
                "```mermaid\n"
                "graph TD\n"
                '    S0["Stage 0: Environment & Guards"]\n'
                "```"
            )

        lines: List[str] = ["```mermaid", "graph TD"]

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

    def dataframe_to_gfm_table(
        self,
        df: Optional[Union[pd.DataFrame, List[Dict[str, Any]], Dict[str, Any]]],
        table_title: Optional[str] = None,
    ) -> str:
        """Converts a pandas DataFrame into a standard GitHub-Flavored Markdown (GFM) pipe table.

        Args:
            df: Input pandas DataFrame or coercible tabular dictionary/list.
            table_title: Optional title/header for the table.

        Returns:
            GFM formatted table string.
        """
        if df is None:
            if table_title:
                return f"### {table_title}\n\n*No tabular data available.*\n"
            return "*No tabular data available.*\n"

        target_df: pd.DataFrame
        if not isinstance(df, pd.DataFrame):
            try:
                target_df = pd.DataFrame(df)
            except Exception:
                if table_title:
                    return f"### {table_title}\n\n*No tabular data available.*\n"
                return "*No tabular data available.*\n"
        else:
            target_df = df

        if target_df.empty:
            if table_title:
                return f"### {table_title}\n\n*No tabular data available.*\n"
            return "*No tabular data available.*\n"

        headers = [
            str(col).replace("\r\n", "<br>").replace("\n", "<br>").replace("|", r"\|").strip()
            for col in target_df.columns
        ]

        alignments: List[str] = []
        for col in target_df.columns:
            is_numeric = (
                pd.api.types.is_numeric_dtype(target_df[col])
                and not pd.api.types.is_bool_dtype(target_df[col])
            )
            alignments.append("---:" if is_numeric else ":---")

        rows: List[str] = []
        if table_title:
            rows.append(f"### {table_title}")
            rows.append("")

        header_line = "| " + " | ".join(headers) + " |"
        rows.append(header_line)

        sep_line = "| " + " | ".join(alignments) + " |"
        rows.append(sep_line)

        for _, row in target_df.iterrows():
            row_cells = []
            for col in target_df.columns:
                val = row[col]
                formatted_val = self._format_cell_value(val, str(col))
                row_cells.append(formatted_val)
            rows.append("| " + " | ".join(row_cells) + " |")

        rows.append("")
        return "\n".join(rows)

    # Backward compatibility alias
    format_gfm_table = dataframe_to_gfm_table

    @staticmethod
    def _format_cell_value(val: Any, col_name: str) -> str:
        """Formats an individual DataFrame cell for GFM presentation."""
        if pd.isna(val) or val is None:
            return "N/A"

        if isinstance(val, (float, np.floating)):
            return MarkdownBuilder._format_float_cell(float(val), col_name)

        if isinstance(val, (int, np.integer)) and not isinstance(val, bool):
            return str(val)

        clean_str = str(val).replace("\r\n", "<br>").replace("\n", "<br>")
        return clean_str.replace("|", r"\|").strip()

    @staticmethod
    def _format_float_cell(val: float, col_name: str) -> str:
        """Formats float values based on column context and magnitude."""
        col_lower = col_name.lower()
        if "hartree" in col_lower or bool(
            re.search(r"(?:^|[\s_(\[])(?:eh|hartree)(?:$|[\s_)\]])", col_lower)
        ):
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
                "zpe",
                "rel",
            ]
        ):
            return f"{val:.2f}"
        if abs(val) >= HIGH_VAL_THRESHOLD or (0 < abs(val) < LOW_VAL_THRESHOLD):
            return f"{val:.4e}"
        return f"{val:.2f}"

    def format_thermodynamic_insights(self, insights_text: Optional[str] = None) -> str:
        """Formats LLM-generated thermodynamic analytical insights under ## Thermodynamic Analysis.

        Args:
            insights_text: Narrative text or analytical insights.

        Returns:
            Formatted Markdown section with placeholders scrubbed.
        """
        lines: List[str] = [
            "## Thermodynamic Analysis",
            "",
        ]

        if not insights_text or not isinstance(insights_text, str):
            lines.append(
                "*Analytical data was aggregated without additional narrative comments.*"
            )
            lines.append("")
            return "\n".join(lines)

        cleaned = re.sub(r"<<INSERT_[^>]*>>", "", insights_text, flags=re.IGNORECASE)
        cleaned = re.sub(r"\[PLACEHOLDER\]", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"<<PLACEHOLDER>>", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"<PLACEHOLDER>", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\{\{[^}]*\}\}", "", cleaned)
        cleaned = cleaned.strip()

        if not cleaned:
            lines.append(
                "*Analytical data was aggregated without additional narrative comments.*"
            )
        else:
            lines.append(cleaned)

        lines.append("")
        return "\n".join(lines)

    # Backward compatibility alias
    inject_thermodynamic_insights = format_thermodynamic_insights

    def format_audit_warnings(
        self,
        warnings: Optional[
            Union[Iterable[Optional[str]], str, Dict[str, Any]]
        ] = None,
    ) -> str:
        """Aggregates non-fatal warnings from cochem_audit_log into Markdown callout blockquotes.

        Args:
            warnings: Optional list, string, or dict of warnings.

        Returns:
            Formatted callout blockquote string.
        """
        if not warnings:
            return "> **NOTE**: No non-fatal execution warnings recorded during this pipeline run.\n"

        if isinstance(warnings, str):
            warn_list = [warnings]
        elif isinstance(warnings, dict):
            warn_list = [f"{k}: {v}" for k, v in warnings.items()]
        elif isinstance(warnings, Iterable):
            warn_list = [str(w) for w in warnings if w is not None and str(w).strip() != "None"]
        else:
            warn_list = [str(warnings)]

        lines: List[str] = []
        for w in warn_list:
            if w is None or str(w).strip() == "None":
                continue
            w_clean = str(w).strip()
            if w_clean:
                lines.append(f"> **WARNING**: {w_clean}")

        if not lines:
            return "> **NOTE**: No non-fatal execution warnings recorded during this pipeline run.\n"

        return "\n\n".join(lines) + "\n"

    # Backward compatibility alias
    format_warning_blockquotes = format_audit_warnings

    def format_hardware_telemetry(self, telemetry: Optional[Dict[str, Any]] = None) -> str:
        """Formats CPU/GPU peak usage metrics and compute timings as a structured Markdown list.

        Args:
            telemetry: Dictionary of hardware telemetry metrics.

        Returns:
            Formatted Markdown section under ## Hardware Resource Telemetry.
        """
        telem = telemetry if isinstance(telemetry, dict) else {}

        # 1. GPU VRAM
        peak_gpu = "N/A"
        for k in ["peak_gpu_vram_mb", "gpu_peak_vram_mb"]:
            if k in telem and telem[k] is not None:
                val = telem[k]
                if isinstance(val, (int, float, np.integer, np.floating)) and not isinstance(val, bool):
                    peak_gpu = f"{float(val):.1f} MB"
                elif isinstance(val, str):
                    peak_gpu = val
                break
        if peak_gpu == "N/A":
            for k in ["peak_gpu_vram_gb", "gpu_peak_vram_gb"]:
                if k in telem and telem[k] is not None:
                    val = telem[k]
                    if isinstance(val, (int, float, np.integer, np.floating)) and not isinstance(val, bool):
                        peak_gpu = f"{float(val):.1f} GB"
                    elif isinstance(val, str):
                        peak_gpu = val
                    break
        if peak_gpu == "N/A":
            raw_gpu = _get_first_present(
                telem,
                ["peak_gpu_vram", "gpu_vram", "peak_gpu"],
                default="N/A",
            )
            if isinstance(raw_gpu, (int, float, np.integer, np.floating)) and not isinstance(raw_gpu, bool):
                val_float = float(raw_gpu)
                peak_gpu = (
                    f"{val_float:.1f} MB"
                    if val_float > VRAM_THRESHOLD_MB
                    else f"{val_float:.1f} GB"
                )
            elif isinstance(raw_gpu, str):
                peak_gpu = raw_gpu

        # 2. CPU
        peak_cpu = _get_first_present(
            telem,
            ["peak_cpu_percent", "cpu_percent", "peak_cpu", "cpu_peak_percent"],
            default="N/A",
        )
        if isinstance(peak_cpu, (int, float, np.integer, np.floating)) and not isinstance(peak_cpu, bool):
            peak_cpu = f"{float(peak_cpu):.1f}%"

        # 3. Wall clock
        wall_clock = _get_first_present(
            telem,
            ["wall_clock_seconds", "wall_clock_time", "execution_time", "wall_clock", "elapsed_time"],
            default="N/A",
        )
        if isinstance(wall_clock, (int, float, np.integer, np.floating)) and not isinstance(wall_clock, bool):
            wall_clock = f"{float(wall_clock):.2f} s"

        # 4. RAM
        peak_ram = "N/A"
        for k in ["peak_ram_mb"]:
            if k in telem and telem[k] is not None:
                val = telem[k]
                if isinstance(val, (int, float, np.integer, np.floating)) and not isinstance(val, bool):
                    peak_ram = f"{float(val):.1f} MB"
                elif isinstance(val, str):
                    peak_ram = val
                break
        if peak_ram == "N/A":
            for k in ["peak_ram_gb", "host_ram_gb"]:
                if k in telem and telem[k] is not None:
                    val = telem[k]
                    if isinstance(val, (int, float, np.integer, np.floating)) and not isinstance(val, bool):
                        peak_ram = f"{float(val):.1f} GB"
                    elif isinstance(val, str):
                        peak_ram = val
                    break
        if peak_ram == "N/A":
            raw_ram = _get_first_present(
                telem,
                ["peak_host_ram", "memory_footprint", "peak_memory", "host_ram"],
                default="N/A",
            )
            if isinstance(raw_ram, (int, float, np.integer, np.floating)) and not isinstance(raw_ram, bool):
                val_float = float(raw_ram)
                peak_ram = (
                    f"{val_float:.1f} MB"
                    if val_float > RAM_THRESHOLD_MB
                    else f"{val_float:.1f} GB"
                )
            elif isinstance(raw_ram, str):
                peak_ram = raw_ram

        lines: List[str] = [
            "## Hardware Resource Telemetry",
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

    # Backward compatibility alias
    format_telemetry_section = format_hardware_telemetry

    def _extract_dataframe(
        self, payload: Dict[str, Any], keys: List[str]
    ) -> Optional[pd.DataFrame]:
        """Extracts and standardizes DataFrame from payload given fallback keys."""
        if not isinstance(payload, dict):
            return None
        for key in keys:
            val = payload.get(key)
            if val is not None:
                if isinstance(val, pd.DataFrame):
                    return val
                try:
                    if isinstance(val, (list, dict)):
                        return pd.DataFrame(val)
                except Exception:
                    pass
        return None

    def build_user_guide(self, payload: Optional[Dict[str, Any]] = None) -> str:
        """Assembles the complete Markdown User Guide document from the provided payload dictionary.

        Args:
            payload: Harvested pipeline data, system matrix, telemetry, and DataFrames.

        Returns:
            Complete GitHub-Flavored Markdown user guide string.
        """
        data = payload if isinstance(payload, dict) else {}
        sections: List[str] = []

        # 1. YAML Frontmatter
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        for k in ["title", "pipeline_hash", "environment", "environment_tier", "run_id", "target_molecule", "smiles"]:
            if k in data and k not in metadata:
                metadata[k] = data[k]

        sections.append(self.generate_yaml_frontmatter(metadata))

        # 2. Document Title & Executive Overview
        doc_title = metadata.get("title", "CoChem Computational Analysis User Guide")
        overview = (
            data.get("overview")
            or data.get("executive_summary")
            or (
                "This document provides a comprehensive summary of the "
                "computational quantum chemistry pipeline execution, including "
                "conformer exploration, thermodynamic properties, vibrational "
                "spectroscopy, and execution provenance."
            )
        )
        sections.append(f"# {doc_title}\n\n{overview}\n")

        # 3. Stage 0 System Matrix & Provenance
        sys_matrix = data.get("system_matrix", {})
        sys_dict = sys_matrix if isinstance(sys_matrix, dict) else {}
        sections.append(self.generate_system_matrix_section(sys_dict))

        # 4. Dynamic Mermaid.js Workflow Diagram
        active_stages = data.get("active_stages")
        mermaid_chart = self.generate_mermaid_flowchart(active_stages)
        sections.append(f"## Pipeline Execution Flowchart\n\n{mermaid_chart}\n")

        # 5. Conformer Landscape GFM Table
        conf_df = self._extract_dataframe(
            data, ["conformers_df", "conformer_df", "conformers"]
        )
        if conf_df is not None and not conf_df.empty:
            conf_table = self.dataframe_to_gfm_table(
                conf_df, table_title="Conformer Energetic & Geometric Ranking"
            )
            sections.append(f"### Conformer Landscape\n\n{conf_table}\n")

        # 6. Thermodynamic Analysis & Energy GFM Table
        insights = (
            data.get("thermodynamic_insights")
            or data.get("insights")
            or ""
        )
        sections.append(self.format_thermodynamic_insights(insights))

        thermo_df = self._extract_dataframe(
            data, ["thermodynamics_df", "thermo_df", "energies_df"]
        )
        if thermo_df is not None and not thermo_df.empty:
            thermo_table = self.dataframe_to_gfm_table(
                thermo_df,
                table_title="Thermodynamic State Functions & Zero-Point Energies",
            )
            sections.append(f"{thermo_table}\n")

        # 7. Spectroscopic Parameters & Vibrational GFM Table
        vib_df = self._extract_dataframe(
            data, ["vibrational_df", "spectroscopy_df", "vibrations_df"]
        )
        if vib_df is not None and not vib_df.empty:
            vib_table = self.dataframe_to_gfm_table(
                vib_df, table_title="Vibrational Modes & IR Intensities"
            )
            sections.append(
                f"## Spectroscopic & Vibrational Analysis\n\n{vib_table}\n"
            )

        # 8. Non-Fatal Execution Warnings Callout Blockquotes
        warnings = data.get("warnings")
        sections.append(
            f"### Execution Warnings & Audit Trail\n\n"
            f"{self.format_audit_warnings(warnings)}\n"
        )

        # 9. Hardware Telemetry Summary
        telemetry = data.get("telemetry", {})
        telem_dict = telemetry if isinstance(telemetry, dict) else {}
        sections.append(self.format_hardware_telemetry(telem_dict))

        return "\n".join(sections).strip() + "\n"

    def save_user_guide(
        self,
        content: str,
        target_dir: Optional[Union[str, pathlib.Path]] = None,
        base_filename: Optional[str] = None,
    ) -> pathlib.Path:
        """Saves Markdown document to user home directory with timestamped overwrite protection.

        Args:
            content: Markdown formatted text.
            target_dir: Optional explicit directory path. If omitted, uses self.output_dir.
            base_filename: Optional target filename. Defaults to self.base_filename.

        Returns:
            Resolved pathlib.Path of the written file.
        """
        dest_dir = (
            pathlib.Path(target_dir).resolve()
            if target_dir is not None
            else self.output_dir
        )
        dest_dir.mkdir(parents=True, exist_ok=True)

        fname = base_filename if base_filename is not None else self.base_filename
        target_path = (dest_dir / fname).resolve()

        if target_path.exists():
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            stem = target_path.stem
            suffix = target_path.suffix
            final_path = dest_dir / f"{stem}_{timestamp}{suffix}"

            count = 1
            while final_path.exists():
                final_path = dest_dir / f"{stem}_{timestamp}_{count}{suffix}"
                count += 1
        else:
            final_path = target_path

        final_path.write_text(str(content), encoding="utf-8")
        logger.info("[SCRIBE-SAVE] Saved Markdown User Guide to %s", final_path)
        return final_path

    # Backward compatibility alias
    write_user_guide = save_user_guide


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_path = pathlib.Path(tmp_dir_str)
        builder = MarkdownBuilder(output_dir=tmp_path, base_filename="CoChem_User_Guide.md")

        # 1. Test YAML Frontmatter
        meta = {
            "title": "CLI Pre-flight Ethanol Verification",
            "run_id": "PREFLIGHT-001",
            "target_molecule": "Ethanol",
            "smiles": "CCO",
            "environment_tier": "Local-Windows WSL",
            "path_ref": pathlib.Path("outputs/run_001"),
            "calc_score": np.float64(99.85),
        }
        fm = builder.generate_yaml_frontmatter(meta)
        assert fm.startswith("---\n") and fm.endswith("\n---"), "Frontmatter delimiters failed"

        # 2. Test System Matrix Section
        sys_mat = {
            "engines": {"ORCA": "6.1.1", "PySCF": "2.8.0"},
            "host": {"cpu_cores": 8, "gpu_device": "RTX 4090", "host_ram": "32 GB"},
        }
        sys_sec = builder.generate_system_matrix_section(sys_mat)
        assert "## Computational Provenance & System Matrix" in sys_sec, "System matrix header missing"
        assert "**ORCA**: `6.1.1`" in sys_sec, "ORCA engine readout missing"

        # 3. Test Mermaid Flowchart
        flowchart = builder.generate_mermaid_flowchart(["0.0", "1.0", "2.0", "3.0", "6.0"])
        assert "```mermaid" in flowchart and "graph TD" in flowchart, "Mermaid syntax error"
        assert "S0" in flowchart and "-->" in flowchart and "S1" in flowchart, "Stage connections missing"

        # 4. Test GFM Table
        sample_df = pd.DataFrame({
            "Conformer": ["C1", "C2"],
            "Energy (Hartree)": [-154.1234567, -154.1122334],
            "Rel Energy (kcal/mol)": [0.00, 7.04],
        })
        table_out = builder.dataframe_to_gfm_table(sample_df, table_title="Conformer Summary")
        assert "### Conformer Summary" in table_out, "Table title missing"
        assert "-154.123457" in table_out, "Hartree rounding format incorrect"

        # 5. Test Full Document Assembly & Overwrite Protection
        payload = {
            "metadata": meta,
            "system_matrix": sys_mat,
            "active_stages": ["0.0", "1.0", "6.0"],
            "conformers_df": sample_df,
            "thermodynamic_insights": "Ethanol conformer analysis completed. <<INSERT_PLACEHOLDER>>",
            "warnings": ["Minor SCF oscillation resolved."],
            "telemetry": {"peak_gpu_vram": 2048.0, "peak_cpu_percent": 45.2, "wall_clock_seconds": 12.34},
        }
        doc_content = builder.build_user_guide(payload)
        file_1 = builder.save_user_guide(doc_content)
        assert file_1.exists() and file_1.name == "CoChem_User_Guide.md", "File 1 save failed"

        file_2 = builder.save_user_guide(doc_content)
        assert file_2.exists() and file_2 != file_1, "Overwrite protection failed"
        assert file_2.name.startswith("CoChem_User_Guide_"), "Timestamped filename format incorrect"

    print("[SCRIBE MD GENERATOR PRE-FLIGHT VERIFIED]")
