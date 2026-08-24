Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-SCRIBE\.in-progress\08_scribe_md_generator.md.
Original prompt:
# Phase 4, Task 9: Dynamic Markdown User Guide Compiler (`formatters/scribe_md_generator.py`)

**Target Output Repository:** `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE`  
**Target Files to Create:**
- `formatters/scribe_md_generator.py`
- `formatters/test_scribe_md_generator.py`

## Objective
Implement the production-grade dynamic Markdown User Guide compiler module (`MarkdownBuilder`) and its comprehensive zero-mock integration test suite (`test_scribe_md_generator.py`) for CoChem-SCRIBE (Stage 6.3). This module bridges the **Mathematical Air-Gap** for rapid laboratory inspection, interactive browser rendering, and Codespaces development by synthesizing structured `CoChem_User_Guide.md` documentation. The compiler parses harvested chemistry payloads, formats YAML frontmatter, constructs dynamic Mermaid.js execution flowcharts, converts conformational and vibrational DataFrames into GitHub-Flavored Markdown (GFM) tables, renders non-fatal execution warnings into callout blockquotes (`> **WARNING**: ...`), aggregates CPU/GPU peak hardware telemetry, and enforces non-destructive timestamped overwrite protection. The implementation must strictly adhere to the **CoChem-SCRIBE Software Requirements Specification (SRS Phase 4, Task 9, Tasks 61–70)**, **Method Matrix v4**, the **Zero-Mock Anti-Spoofing Protocol**, **FAIR Data Principles**, and the **6-Tier Environment Matrix** (Local-Windows WSL, Local-MacOS OrbStack, Local-Linux Debian, Codespaces, GitHub Actions, HPC).

---

## Technical Specifications & Architecture

### 1. Architectural Philosophy: Markdown Synchronization & Air-Gap Bridge (SRS §9.1, §9.3)
- **Air-Gap Documentation Bridge:** While `scribe_templater.py` compiles formal LaTeX manuscripts, `scribe_md_generator.py` generates an immediate, human-readable, web-friendly User Guide bypassing LaTeX compiler requirements.
- **Dynamic Mermaid.js Workflow Visualization (SRS §9.3.2, Task 63):** The generator dynamically compiles a Mermaid diagram block (````mermaid graph TD ... ````) representing the exact sequence of active CoChem calculation and analysis stages executed in the current pipeline run.
- **Non-Destructive Overwrite Protection (SRS §9.3.5, Task 69):** To prevent destructive loss of researcher annotations or previous run notes, the builder checks for existing `CoChem_User_Guide.md` files and appends timestamped archives (`CoChem_User_Guide_YYYYMMDD_HHMMSS.md` or timestamped execution blocks) rather than overwriting.
- **Deterministic Cross-Platform Pathing (SRS §9.3.5, Task 68):** Path resolution must strictly utilize `pathlib.Path.home()` and OS-agnostic path libraries to guarantee flawless execution across all 6-Tier Environment nodes without relying on POSIX-only shell environment variables.
- **100% Offline Air-Gap Execution:** All markdown generation, YAML serialization, GFM table conversion, Mermaid diagram generation, and file operations must execute strictly locally without external network sockets or third-party web API calls.

---

## Deliverable 1: `formatters/scribe_md_generator.py`

### 1. Class Architecture & Interface Contract (`MarkdownBuilder`)

Define the `MarkdownBuilder` class in `formatters/scribe_md_generator.py` with complete Python 3.10+ typing (`typing.Dict`, `typing.Any`, `typing.Optional`, `typing.Union`, `typing.List`, `pathlib.Path`, `pandas.DataFrame`):

```python
import os
import re
import json
import logging
import pathlib
from datetime import datetime
from typing import Dict, Any, Optional, Union, List
import pandas as pd

class MarkdownBuilder:
    """Dynamic Markdown User Guide Compiler for CoChem-SCRIBE.
    
    Synthesizes structured CoChem_User_Guide.md reports containing YAML frontmatter,
    Stage 0 provenance metadata, dynamic Mermaid.js execution flowcharts,
    GitHub-Flavored Markdown (GFM) tables, thermodynamic analytical insights,
    non-fatal warning callout blockquotes, hardware telemetry metrics, and
    non-destructive timestamped overwrite protection.
    """
    def __init__(
        self,
        output_dir: Optional[Union[str, pathlib.Path]] = None,
        filename: str = "CoChem_User_Guide.md"
    ) -> None:
        """Initializes MarkdownBuilder with dynamic path resolution and target filename."""
        pass

    def generate_yaml_frontmatter(self, metadata: Dict[str, Any]) -> str:
        """Generates strict YAML frontmatter containing run metadata, timestamp, and pipeline provenance."""
        pass

    def generate_system_matrix_section(self, system_matrix: Dict[str, Any]) -> str:
        """Generates Stage 0 system matrix readout (active engines, nodes, cores, GPU) for audit compliance."""
        pass

    def generate_mermaid_flowchart(self, active_stages: Optional[List[str]] = None) -> str:
        """Dynamically synthesizes a Mermaid.js diagram (graph TD) mapping active CoChem pipeline stages."""
        pass

    def format_gfm_table(
        self,
        df: pd.DataFrame,
        title: Optional[str] = None
    ) -> str:
        """Converts a pandas DataFrame into a clean GitHub-Flavored Markdown (GFM) pipe table."""
        pass

    def inject_thermodynamic_insights(self, insights_text: str) -> str:
        """Formats and wraps LLM-generated thermodynamic insights under ## Thermodynamic Analysis."""
        pass

    def format_warning_blockquotes(self, warnings: Optional[List[str]] = None) -> str:
        """Formats non-fatal system warnings into Markdown callout blockquotes (> **WARNING**: ...)."""
        pass

    def format_telemetry_section(self, telemetry_data: Dict[str, Any]) -> str:
        """Formats peak CPU/GPU usage, wall-clock execution time, and memory metrics into a structured Markdown section."""
        pass

    def build_user_guide(self, data_payload: Dict[str, Any]) -> str:
        """Assembles the complete CoChem_User_Guide.md document string from the aggregated data payload."""
        pass

    def write_user_guide(
        self,
        content: str,
        destination_path: Optional[Union[str, pathlib.Path]] = None
    ) -> pathlib.Path:
        """Writes Markdown content to disk with non-destructive timestamped overwrite protection."""
        pass
```

---

### 2. Detailed Functional Requirements (Tasks 61–70)

#### 2.1 Class Initialization & Cross-Platform Pathing (Tasks 61 & 68)
- Implement `__init__(self, output_dir=None, filename="CoChem_User_Guide.md")`:
  - If `output_dir` is not provided, dynamically resolve default destination:
    `pathlib.Path.home() / "CoChem_Artifacts" / "Report_Archive"`
  - Set `self.output_dir = pathlib.Path(output_dir).resolve()`
  - Set `self.filename = filename`
  - Ensure parent directories exist dynamically upon initialization or write (`self.output_dir.mkdir(parents=True, exist_ok=True)`).
  - Ensure zero reliance on POSIX-only shell environment variables (e.g., `$HOME`), using `pathlib.Path.home()` for cross-platform compatibility across Windows WSL, macOS OrbStack, Linux Debian, Codespaces, GitHub Actions, and HPC.

#### 2.2 YAML Frontmatter & Stage 0 System Matrix (Task 62)
- Implement `generate_yaml_frontmatter(self, metadata: Dict[str, Any]) -> str`:
  - Generate strict YAML block bounded by `---` lines at the top of the file:
    ```yaml
    ---
    title: "CoChem Computational Analysis User Guide"
    generated_at: "2026-08-23T12:00:00"
    version: "2.0.0"
    pipeline_hash: "a1b2c3d4..."
    environment: "Local-Linux (Debian)"
    fair_compliance: true
    ---
    ```
- Implement `generate_system_matrix_section(self, system_matrix: Dict[str, Any]) -> str`:
  - Render a structured Markdown section under `## 1. System Execution Environment & Provenance`:
    - Active quantum/molecular engines and exact versions (e.g., ORCA 6.1.1, xTB 6.7.1, MACE-OFF23).
    - Host architecture details: CPU core allocation, GPU device model, host RAM, environment tier.
    - Configuration SHA-256 hash verifying reproducibility.

#### 2.3 Dynamic Mermaid.js Flowchart Synthesis (Task 63)
- Implement `generate_mermaid_flowchart(self, active_stages: Optional[List[str]] = None) -> str`:
  - Dynamically construct a Mermaid flowchart inside a fenced ````mermaid ... ```` block:
    ```mermaid
    graph TD
        S0["Stage 0.0: Configuration & Resource Guards"] --> S1["Stage 1.0: Conformer Generation (CREST/ORCA)"]
        S1 --> S2["Stage 2.0: Geometry Optimization"]
        S2 --> S3["Stage 3.0: Frequency & Thermochemistry"]
        S3 --> S4["Stage 4.0: Spectroscopic Analysis (TORQ)"]
        S4 --> S5["Stage 5.0: Voigt Spectral Deconvolution (SpycFit)"]
        S5 --> S6["Stage 6.0: Document Synthesis (SCRIBE)"]
    ```
  - If `active_stages` is provided, dynamically highlight executed nodes (e.g., styling active nodes with class definitions) or filter inactive stages from the diagram.
  - Return formatted flowchart ready for native rendering in GitHub, Codespaces, and GitLab Markdown viewers.

#### 2.4 Thermodynamic Analytical Insights Integration (Task 64)
- Implement `inject_thermodynamic_insights(self, insights_text: str) -> str`:
  - Format the LLM-generated methodology and thermodynamic analytical insights under `## 2. Thermodynamic & Structural Analysis`.
  - Scrub any leftover internal placeholder tokens (e.g., `<<INSERT_*>>`, `[PLACEHOLDER]`) or malformed whitespace.
  - If `insights_text` is empty or missing, provide a clean, descriptive fallback note stating analytical data was aggregated without additional narrative comments.

#### 2.5 GitHub-Flavored Markdown (GFM) Table Generation (Task 65)
- Implement `format_gfm_table(self, df: pd.DataFrame, title: Optional[str] = None) -> str`:
  - Convert `pandas.DataFrame` tables (e.g., conformer rankings, rotational constants, vibrational modes) into strict GFM pipe-delimited tables:
    ```markdown
    | Conformer ID | Relative Energy (kcal/mol) | Symmetry | Population (%) |
    | :--- | :--- | :--- | :--- |
    | Conf_01 | 0.00 | C1 | 68.4 |
    | Conf_02 | 0.42 | Cs | 24.1 |
    ```
  - Enforce proper column alignment separators (`:---` or `---:`).
  - Format floating-point numbers to appropriate significant figures (energies to 2–4 decimal places, frequencies to 1–2 decimal places).
  - Prepend table title/header when `title` is supplied.

#### 2.6 Hardware Telemetry & Non-Fatal Warnings Callout Blockquotes (Tasks 66 & 67)
- Implement `format_warning_blockquotes(self, warnings: Optional[List[str]] = None) -> str`:
  - Parse non-fatal warnings harvested from `cochem_audit_log.json`.
  - Format each warning as a distinct GitHub-style callout blockquote:
    `> **WARNING**: <warning_message>`
  - If `warnings` list is empty or `None`, render:
    `> **NOTE**: No non-fatal execution warnings recorded during this pipeline run.`
- Implement `format_telemetry_section(self, telemetry_data: Dict[str, Any]) -> str`:
  - Render `## 4. Hardware Telemetry & Compute Resource Allocation`.
  - Format peak GPU VRAM usage, CPU peak usage percentage, wall-clock time, and memory footprint as a clean Markdown list or summary table.

#### 2.7 Non-Destructive Overwrite Protection & File Persistence (Tasks 68 & 69)
- Implement `write_user_guide(self, content: str, destination_path: Optional[Union[str, pathlib.Path]] = None) -> pathlib.Path`:
  - Target destination: `destination_path` or `self.output_dir / self.filename`.
  - **Overwrite Protection Check:** Before writing, check if the file already exists on disk:
    - If the file exists: generate a timestamped filename to prevent destructive overwriting of user notes:
      `timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")`
      `final_path = target_dir / f"{target_stem}_{timestamp}{target_suffix}"`
    - If the file does not exist: write directly to `destination_path`.
  - Write content with UTF-8 encoding.
  - Return the final `pathlib.Path` written.

#### 2.8 Unified Guide Assembly (`build_user_guide`)
- Implement `build_user_guide(self, data_payload: Dict[str, Any]) -> str`:
  - Harmonize all sections in logical sequence:
    1. YAML Frontmatter
    2. Document Title & Executive Overview
    3. Stage 0 System Matrix & Provenance
    4. Dynamic Mermaid.js Workflow Diagram
    5. Conformer Landscape GFM Table
    6. Thermodynamic Insights & Energy GFM Table
    7. Spectroscopic Parameters & Vibrational GFM Table
    8. Non-Fatal Execution Warnings Callout Blockquotes
    9. Hardware Telemetry Summary
  - Return complete, valid Markdown string.

---

## Deliverable 2: `formatters/test_scribe_md_generator.py`

Implement a complete `pytest` test suite conforming to the **Zero-Mock Anti-Spoofing Protocol** (Task 70):

1. **Zero-Mock Enforcement:**
   - Strictly prohibit `unittest.mock`, `mocker`, or simulated Markdown builders. All tests must execute real class methods, real `pandas.DataFrame` table transformations, and real file I/O using `tmp_path`.
2. **YAML Frontmatter & Metadata Test:**
   - Instantiate `MarkdownBuilder` and generate YAML frontmatter with test metadata.
   - Assert output begins with `---` and ends with `---`, contains valid YAML key-value pairs (`title`, `generated_at`, `version`, `pipeline_hash`), and parses cleanly via `yaml.safe_load`.
3. **Mermaid.js Flowchart Synthesis Test:**
   - Call `generate_mermaid_flowchart(["Stage 0.0", "Stage 1.0", "Stage 2.0", "Stage 6.0"])`.
   - Assert output contains ````mermaid` and `graph TD`, valid node definitions (`S0["..."]`), and valid edge transitions (`-->`).
4. **GFM Table Pipe Formatting Test:**
   - Create a real `pandas.DataFrame` containing conformer IDs, float energies, and symmetry labels.
   - Call `format_gfm_table()`.
   - Assert output contains pipe delimiters (`|`), header separator row (`|---|`), and correctly formatted float strings without missing cells.
5. **Warning Callouts & Telemetry Formatting Test:**
   - Pass a list of warning strings (`["SCF convergence required dampening on step 4.", "GPU VRAM spike near 90%."]`).
   - Assert output contains `> **WARNING**: SCF convergence required dampening...` blockquotes.
   - Pass empty warning list and assert clean `> **NOTE**:` fallback is rendered.
   - Pass telemetry dictionary and assert peak GPU, CPU, and wall-clock times are present in the formatted telemetry section.
6. **Non-Destructive Overwrite Protection Test:**
   - Write an initial `CoChem_User_Guide.md` inside `tmp_path`.
   - Write a second guide with `builder.write_user_guide()`.
   - Assert the original `CoChem_User_Guide.md` remains completely intact and un-overwritten.
   - Assert a new timestamped file (`CoChem_User_Guide_*.md`) was created and contains the updated content.
7. **End-to-End User Guide Generation Test:**
   - Assemble a realistic chemical data payload dictionary containing conformer DataFrames, thermodynamic scalars, spectroscopic tables, telemetry metrics, and narrative insights.
   - Execute `build_user_guide()` and `write_user_guide()`.
   - Read output file from disk and assert all sections (YAML frontmatter, Mermaid chart, GFM tables, insights, warnings, telemetry) are properly structured and valid Markdown.

---

## Execution Constraints & Anti-Spoofing Directives

1. **Zero Mocking / Placeholders:**
   - Every class, method, helper, and test case must be completely implemented with functional, executable logic.
   - Strictly NO `pass`, `# TODO`, `...`, or placeholder mock returns in output files.
2. **Dynamic Path Resolution & Air-Gap Compliance:**
   - All filesystem paths must resolve dynamically using `pathlib.Path.home()` or explicit arguments.
   - Hardcoded operating system paths (e.g., `C:\Users\...` or `/tmp/...`) are strictly forbidden.
   - All markdown generation and file persistence must execute 100% offline without external network sockets.
3. **6-Tier Environment Matrix Compliance:**
   - The module and tests must function identically across Linux (Debian/Ubuntu), macOS (OrbStack), Windows (WSL), Codespaces, GitHub Actions, and HPC clusters.
4. **FAIR Data & Provenance Compliance:**
   - Markdown tables and frontmatter must preserve exact physical values and SHA-256 pipeline hashes.
5. **Deliverable Scope:**
   - Implement `formatters/scribe_md_generator.py` and `formatters/test_scribe_md_generator.py`.

---

## Task
Implement the Python modules and tests as described and save them to:
- `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE\formatters\scribe_md_generator.py`
- `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE\formatters\test_scribe_md_generator.py`
using the `write_to_file` tool.

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\formatters\__init__.py ---
"""CoChem-BASE Formatters Module."""

from .scribe_templater import Jinja2Templater
from .scribe_md_generator import MarkdownBuilder

__all__ = ["Jinja2Templater", "MarkdownBuilder"]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\formatters\scribe_md_generator.py ---
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

        yaml_content = yaml.dump(
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
        for key, (node_id, label) in STAGE_DEFINITIONS.items():
            if (
                key in stage_item
                or f"Stage {key[0]}" in stage_item
                or stage_item.strip() == node_id
            ):
                return node_id, label, custom_idx
        cleaned_name = stage_item.strip()
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

        return str(val).replace("|", r"\|").strip()

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
        if isinstance(peak_gpu, int | float):
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
        if isinstance(peak_cpu, int | float):
            peak_cpu = f"{peak_cpu:.1f}%"

        wall_clock = (
            telem.get("wall_clock_seconds")
            or telem.get("wall_clock_time")
            or telem.get("execution_time")
            or telem.get("wall_clock")
            or telem.get("elapsed_time")
            or "N/A"
        )
        if isinstance(wall_clock, int | float):
            wall_clock = f"{wall_clock:.2f} s"

        peak_ram = (
            telem.get("peak_ram_mb")
            or telem.get("peak_host_ram")
            or telem.get("memory_footprint")
            or telem.get("peak_memory")
            or telem.get("host_ram")
            or "N/A"
        )
        if isinstance(peak_ram, int | float):
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
                return (
                    val if isinstance(val, pd.DataFrame) else pd.DataFrame(val)
                )
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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\formatters\test_scribe_md_generator.py ---
"""Zero-Mock Integration and Unit Test Suite for MarkdownBuilder (Stage 6.3).

Verifies dynamic Markdown User Guide compilation, YAML frontmatter
serialization, Mermaid.js workflow diagram synthesis, GFM pipe table
formatting, thermodynamic insights placeholder scrubbing, warning callout
blockquotes, hardware telemetry reporting, and non-destructive timestamped
overwrite protection.
"""

from __future__ import annotations

import pathlib
import sys
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
        "Symmetry": ["C1", "Cs", "C1"],
        "Boltzmann Population (%)": [68.4, 24.1, 7.5],
    }
    df = pd.DataFrame(data)

    table_md = builder.format_gfm_table(df, title="Conformer Distribution")

    assert "### Conformer Distribution" in table_md
    assert (
        "| Conformer ID | Relative Energy (kcal/mol) | Symmetry | "
        "Boltzmann Population (%) |"
    ) in table_md
    assert (
        "| :--- | :--- | :--- | :--- |" in table_md
        or "| :--- | ---: | :--- | ---: |" in table_md
    )
    assert (
        "| Conf_01 | 0.00 | C1 | 68.40 |" in table_md
        or "| Conf_01 | 0.00 | C1 | 68.4 |" in table_md
    )
    assert (
        "| Conf_02 | 0.42 | Cs | 24.10 |" in table_md
        or "| Conf_02 | 0.42 | Cs | 24.1 |" in table_md
    )
    assert (
        "| Conf_03 | 1.88 | C1 | 7.50 |" in table_md
        or "| Conf_03 | 1.88 | C1 | 7.5 |" in table_md
    )


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
        "peak_host_ram": "32.1 GB",
    }
    telemetry_md = builder.format_telemetry_section(telemetry)
    assert (
        "## 4. Hardware Telemetry & Compute Resource Allocation"
        in telemetry_md
    )
    assert "**Peak GPU VRAM Usage**: 18.4 GB" in telemetry_md
    assert "**Peak CPU Usage**: 87.5%" in telemetry_md
    assert "**Wall-Clock Execution Time**: 124.58 s" in telemetry_md
    assert "**Peak Host RAM / Memory Footprint**: 32.1 GB" in telemetry_md


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

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.