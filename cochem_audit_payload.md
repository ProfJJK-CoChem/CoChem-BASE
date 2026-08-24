Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-SCRIBE\.in-progress\prompt_scribe_md_generator.md.
Original prompt:
# Phase 4, Task 9: Markdown User Guide & GFM Table Generator (`formatters/scribe_md_generator.py`)

**Target Output Repository:** `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE`  
**Target Files to Create:**
- `formatters/scribe_md_generator.py`
- `formatters/test_scribe_md_generator.py`

## Objective
Implement the production-grade Markdown User Guide and table generator engine (`MarkdownBuilder`) along with comprehensive zero-mock integration tests (`test_scribe_md_generator.py`) for CoChem-SCRIBE (Stage 6.3). This module bridges the **Mathematical Air-Gap** by securely compiling LLM-generated thermodynamic narrative insights together with exact physical numerical tensors (HDF5 conformer and vibrational DataFrames), Stage 0 system matrices, Mermaid.js execution flowcharts, hardware telemetry metrics, and non-fatal audit log warnings into a standalone, publication-grade, human-readable `CoChem_User_Guide.md`. The implementation must strictly adhere to the **CoChem-SCRIBE Software Requirements Specification (SRS Phase 4, Task 9, Tasks 61–70)**, **Method Matrix v4**, the **Zero-Mock Anti-Spoofing Protocol**, **FAIR Data Principles**, and the **6-Tier Environment Matrix** (Local-Windows WSL, Local-MacOS OrbStack, Local-Linux Debian, Codespaces, GitHub Actions, HPC).

---

## Technical Specifications & Architecture

### 1. Architectural Philosophy: The Air-Gap Markdown Synthesis & Provenance (SRS §9.1, §9.3)
- **Air-Gap Integration Boundary:** At Stage 6.3, the Mathematical Air-Gap is bridged. The `MarkdownBuilder` combines isolated generative LLM insights with verified physical tensors and system telemetry into a web-ready, human-readable document for laboratory researchers without requiring a local LaTeX installation.
- **Strict Computational Provenance:** Every generated User Guide must embed valid YAML frontmatter and a Stage 0 system matrix readout documenting active engines (e.g., Gaussian, ORCA, Psi4), node hostnames, and environment tiers to ensure complete FAIR traceability.
- **GFM Table Standardization & Visual Flowcharts:** Numerical DataFrames (conformer energies, vibrational frequencies) must be transformed into standard GitHub-Flavored Markdown (GFM) pipe tables (`|`), and active pipeline stages must be visually diagrammed via standard Mermaid.js flowchart syntax (`mermaid graph TD...`).
- **Non-Destructive Safe Pathing & Overwrite Protection:** Markdown files must be written securely to the user's home directory (`pathlib.Path.home() / "CoChem_Artifacts" / "Report_Archive"`). If `CoChem_User_Guide.md` already exists, the engine must never destructively overwrite manual notes; it must append a timestamped version (`CoChem_User_Guide_YYYYMMDD_HHMMSS.md`).
- **100% Offline Air-Gap Execution:** All frontmatter formatting, Mermaid flowchart synthesis, GFM table conversion, telemetry parsing, and disk I/O must execute locally and deterministically without external cloud dependencies or outbound network calls.

---

## Deliverable 1: `formatters/scribe_md_generator.py`

### 1. Class Architecture & Interface Contract (`MarkdownBuilder`)

Define the `MarkdownBuilder` class in `formatters/scribe_md_generator.py` with complete Python 3.10+ typing (`pathlib.Path`, `typing.Dict`, `typing.Any`, `typing.Optional`, `typing.Union`, `typing.List`, `pandas.DataFrame`):

```python
import os
import sys
import json
import logging
import pathlib
import datetime
from typing import Dict, Any, Optional, Union, List
import pandas as pd

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
        base_filename: str = "CoChem_User_Guide.md"
    ) -> None:
        """Initializes MarkdownBuilder with dynamic output directory resolution."""
        pass

    def generate_yaml_frontmatter(self, metadata: Dict[str, Any]) -> str:
        """Generates valid YAML frontmatter block containing run provenance and metadata."""
        pass

    def generate_system_matrix_section(self, system_matrix: Dict[str, Any]) -> str:
        """Generates Markdown readout of Stage 0 active computational engines and hardware nodes."""
        pass

    def generate_mermaid_flowchart(self, active_stages: List[Union[str, int, Dict[str, Any]]]) -> str:
        """Dynamically synthesizes a Mermaid.js graph TD diagram block mapping active CoChem stages."""
        pass

    def dataframe_to_gfm_table(
        self,
        df: pd.DataFrame,
        table_title: Optional[str] = None
    ) -> str:
        """Converts a pandas DataFrame into a standard GitHub-Flavored Markdown (GFM) pipe table."""
        pass

    def format_thermodynamic_insights(self, insights_text: str) -> str:
        """Formats LLM-generated thermodynamic analytical insights under ## Thermodynamic Analysis."""
        pass

    def format_audit_warnings(self, warnings: List[str]) -> str:
        """Aggregates non-fatal warnings from cochem_audit_log into Markdown callout blockquotes."""
        pass

    def format_hardware_telemetry(self, telemetry: Dict[str, Any]) -> str:
        """Formats CPU/GPU peak usage metrics and compute timings as a structured Markdown list."""
        pass

    def build_user_guide(self, payload: Dict[str, Any]) -> str:
        """Assembles the complete Markdown User Guide document from the provided payload dictionary."""
        pass

    def save_user_guide(
        self,
        content: str,
        target_dir: Optional[Union[str, pathlib.Path]] = None,
        base_filename: Optional[str] = None
    ) -> pathlib.Path:
        """Saves Markdown document to user home directory with timestamped overwrite protection."""
        pass
```

---

### 2. Detailed Functional Requirements (Tasks 61–69)

#### 2.1 Initialization & Dynamic Path Resolution (Tasks 61 & 68)
- If `output_dir` is not provided, dynamically resolve the path relative to the user's home directory:
  `pathlib.Path.home() / "CoChem_Artifacts" / "Report_Archive"`
- Ensure parent directories are created automatically on demand (`output_dir.mkdir(parents=True, exist_ok=True)`).
- Ensure strict cross-platform path resolution using Python's `pathlib.Path` across all 6 environments (Windows WSL, macOS OrbStack, Linux Debian, Codespaces, GitHub Actions, HPC).

#### 2.2 YAML Frontmatter & Stage 0 System Matrix (Tasks 61 & 62)
- Implement `generate_yaml_frontmatter(self, metadata: Dict[str, Any]) -> str`:
  - Enclose frontmatter within standard `---` opening and closing delimiters.
  - Include key metadata fields: `title`, `date` (ISO format `%Y-%m-%d %H:%M:%S`), `cochem_version`, `run_id`, `target_molecule`, `smiles`, and `environment_tier`.
- Implement `generate_system_matrix_section(self, system_matrix: Dict[str, Any]) -> str`:
  - Produce a structured `## Computational Provenance & System Matrix` section.
  - Detail active quantum chemistry engines (e.g., ORCA, Gaussian, Psi4, PySCF), node architecture, CPU core count, GPU model, memory allocation, and Python runtime version.

#### 2.3 Dynamic Mermaid.js Flowchart Synthesis (Task 63)
- Implement `generate_mermaid_flowchart(self, active_stages: List[Union[str, int, Dict[str, Any]]]) -> str`:
  - Dynamically construct a fenced Mermaid flowchart block:
    ````markdown
    ```mermaid
    graph TD
        S0[Stage 0: Environment & Guards] --> S1[Stage 1: Conformer Generation]
        S1 --> S2[Stage 2: DFT Optimization]
        S2 --> S3[Stage 3: Frequency & Thermochemistry]
        S3 --> S4[Stage 4: Sinc-DVR Dynamic Tunneling]
        S4 --> S5[Stage 5: Telemetry Aggregation]
        S5 --> S6[Stage 6: SCRIBE Document Synthesis]
    ```
    ````
  - Highlight active stages vs bypassed stages based on the passed execution topology.

#### 2.4 Thermodynamic Analytical Insights Formatting (Task 64)
- Implement `format_thermodynamic_insights(self, insights_text: str) -> str`:
  - Create a designated `## Thermodynamic Analysis` header section.
  - Inject the sanitized LLM analytical narrative, ensuring scientific notation and physical quantities are preserved.

#### 2.5 DataFrame to GFM Table Conversion (Task 65)
- Implement `dataframe_to_gfm_table(self, df: pd.DataFrame, table_title: Optional[str] = None) -> str`:
  - Convert any `pandas.DataFrame` into standard GitHub-Flavored Markdown (GFM) pipe table syntax.
  - Generate the header row with column names: `| Col1 | Col2 | Col3 |`.
  - Generate alignment separator row: `| :--- | :---: | ---: |` (or standard `| --- | --- |`).
  - Format numeric float values cleanly (preserving significant figures, avoiding scientific notation truncation).
  - Include optional `### <table_title>` subheader if `table_title` is supplied.
  - Handle empty DataFrames gracefully with a placeholder markdown italic note `*No tabular data available.*`.

#### 2.6 Hardware Telemetry & Audit Warnings Blockquotes (Tasks 66 & 67)
- Implement `format_audit_warnings(self, warnings: List[str]) -> str`:
  - Aggregate non-fatal warnings extracted from `cochem_audit_log.json` or payload dictionary.
  - Format each warning as a distinct Markdown blockquote callout:
    `> **WARNING**: <warning_message>`
  - If no warnings are present, return an empty string or omit the section cleanly.
- Implement `format_hardware_telemetry(self, telemetry: Dict[str, Any]) -> str`:
  - Create `## Hardware Resource Telemetry` section.
  - Format peak memory usage (RAM in GB/MB), peak GPU VRAM, CPU average load %, total calculation runtime, and wall-clock execution timestamps into a clean, bulleted Markdown list.

#### 2.7 Safe Writing & Timestamped Overwrite Protection (Tasks 68 & 69)
- Implement `save_user_guide(self, content: str, target_dir: Optional[Union[str, pathlib.Path]] = None, base_filename: Optional[str] = None) -> pathlib.Path`:
  - Determine destination folder (`target_dir` or `self.output_dir`).
  - Target default filename `CoChem_User_Guide.md`.
  - **Non-Destructive Overwrite Check (Task 69):** If `CoChem_User_Guide.md` already exists at the destination path, do NOT overwrite it. Dynamically generate a timestamped filename:
    `timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")`
    `final_filename = f"CoChem_User_Guide_{timestamp}.md"`
  - Write file with explicit `utf-8` encoding.
  - Return the `pathlib.Path` of the written file.

#### 2.8 Local Pre-Flight CLI Validation
- Include an `if __name__ == '__main__':` execution block at the bottom of `formatters/scribe_md_generator.py`.
- When invoked directly from CLI:
  1. Instantiate `MarkdownBuilder` with local temporary test paths.
  2. Verify YAML frontmatter generation, Mermaid graph block formatting, GFM table rendering, and non-destructive overwrite protection.
  3. Print `[SCRIBE MD GENERATOR PRE-FLIGHT VERIFIED]` upon successful verification.

---

## Deliverable 2: `formatters/test_scribe_md_generator.py`

### 1. Test Architecture & Zero-Mock Protocol (Task 70)
Implement a complete `pytest` test suite in `formatters/test_scribe_md_generator.py` conforming to the **Zero-Mock Anti-Spoofing Protocol**:
- **Zero-Mock Enforcement:** Strictly prohibit `unittest.mock`, `mocker`, or synthetic simulated strings. Tests must execute the real `MarkdownBuilder` methods against real DataFrames and real filesystem paths using `pytest`'s `tmp_path` fixture.

### 2. Required Test Suite Specifications
1. **`test_markdown_builder_initialization(tmp_path)`:**
   - Verify default directory resolution to `pathlib.Path.home() / "CoChem_Artifacts" / "Report_Archive"`.
   - Verify custom directory initialization and automatic directory creation.
2. **`test_yaml_frontmatter_and_system_matrix()`:**
   - Generate frontmatter and system matrix from sample metadata dictionaries.
   - Assert presence of `---` delimiters, ISO date strings, runtime engines, and node specs.
3. **`test_mermaid_flowchart_generation()`:**
   - Pass a sequence of active CoChem stages.
   - Assert output contains ```mermaid\ngraph TD...``` code fence and valid stage connection arrows (`-->`).
4. **`test_dataframe_to_gfm_table()`:**
   - Pass realistic conformer and vibrational DataFrames with numeric floats.
   - Assert output contains standard pipe `|` headers, separator rows (`|---|`), and properly formatted numeric cells without NaN corruptions.
5. **`test_audit_warnings_and_telemetry_formatting()`:**
   - Test warning aggregation with multiple sample warnings; assert each warning is rendered as `> **WARNING**: ...`.
   - Test telemetry formatting; assert list contains peak RAM, GPU VRAM, and CPU utilization metrics.
6. **`test_build_user_guide_e2e()`:**
   - Execute `build_user_guide()` with a full data payload containing metadata, system matrix, insights text, conformer DataFrame, vibrational DataFrame, warnings, and hardware metrics.
   - Assert complete document contains all expected sections (`## Thermodynamic Analysis`, `## Hardware Resource Telemetry`, etc.).
7. **`test_save_user_guide_overwrite_protection(tmp_path)`:**
   - Save initial `CoChem_User_Guide.md` in `tmp_path`.
   - Call `save_user_guide()` again on the same path.
   - Assert initial file remains intact and unmodified.
   - Assert second file is created with timestamped name format (`CoChem_User_Guide_\d{8}_\d{6}\.md`).

---

## Directives & Execution Constraints

1. **Target Deliverables:** Implement both `formatters/scribe_md_generator.py` and `formatters/test_scribe_md_generator.py`.
2. **Zero-Mock Anti-Spoofing Protocol:** Strictly NO mocks, fake return values, `pass` stubs, or `# TODO` placeholders in output files.
3. **Strict Python 3.10+ Standards:** Use type annotations, `pathlib.Path`, standard `logging` with `[SCRIBE-*]` markers, and explicit UTF-8 file encoding.
4. **Air-Gap Mandate:** 100% offline local execution. Zero network calls or external cloud dependencies.
5. **Method Matrix v4 & FAIR Principles:** Full provenance tracking with YAML frontmatter, Stage 0 system matrix, and deterministic GFM tabular conversions.
6. **6-Tier Matrix & Cross-Platform Defense:** Strict path resolution using `pathlib.Path` ensuring flawless operation across Windows WSL, macOS OrbStack, Linux Debian, Codespaces, GitHub Actions, and HPC nodes.

---

## Task
Implement the Python modules and tests as described and save them to:
1. `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE\formatters\scribe_md_generator.py`
2. `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE\formatters\test_scribe_md_generator.py`
using the `write_to_file` tool.


Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\formatters\scribe_md_generator.py ---
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
from typing import Any, Dict, List, Optional, Tuple, Union

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
        meta = metadata.copy() if metadata else {}

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

        yaml_content = yaml.safe_dump(
            meta, sort_keys=False, default_flow_style=False
        ).strip()
        return f"---\n{yaml_content}\n---"

    def generate_system_matrix_section(self, system_matrix: Optional[Dict[str, Any]] = None) -> str:
        """Generates Markdown readout of Stage 0 active computational engines and hardware nodes.

        Args:
            system_matrix: System configuration and execution environment data.

        Returns:
            Formatted Markdown section under ## Computational Provenance & System Matrix.
        """
        matrix = system_matrix or {}
        lines: List[str] = [
            "## Computational Provenance & System Matrix",
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
            or matrix.get("environment_tier")
            or matrix.get("environment", "Unknown / Heterogeneous")
        )
        node_arch = (
            host_info.get("node_architecture")
            or host_info.get("architecture")
            or host_info.get("node_arch")
            or platform.machine()
            or "x86_64"
        )
        cpu_cores = (
            host_info.get("cpu_cores")
            or host_info.get("cpu")
            or host_info.get("cores")
            or matrix.get("cpu_cores", "N/A")
        )
        gpu_device = (
            host_info.get("gpu_model")
            or host_info.get("gpu_device")
            or host_info.get("gpu")
            or matrix.get("gpu_device", "N/A")
        )
        host_ram = (
            host_info.get("host_ram")
            or host_info.get("memory_allocation")
            or host_info.get("host_ram_gb")
            or host_info.get("ram_gb")
            or matrix.get("host_ram", "N/A")
        )
        py_version = (
            host_info.get("python_version")
            or host_info.get("python")
            or matrix.get("python_version")
            or sys.version.split()[0]
        )
        cfg_hash = (
            matrix.get("config_hash")
            or matrix.get("pipeline_hash")
            or host_info.get("config_hash", "N/A")
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
        stage_item: Union[str, int, Dict[str, Any]], custom_idx: int
    ) -> Tuple[str, str, int]:
        """Resolves a single stage item into a node ID, label, and updated custom index."""
        if isinstance(stage_item, dict):
            node_id = str(stage_item.get("id") or stage_item.get("stage") or f"S_custom_{custom_idx}")
            label = str(stage_item.get("name") or stage_item.get("label") or node_id)
            if not node_id.startswith("S"):
                node_id = f"S{node_id}".replace(".", "_")
            return node_id, label.replace('"', "'"), custom_idx + 1

        if isinstance(stage_item, int):
            stage_str = f"{stage_item}.0"
            if stage_str in STAGE_DEFINITIONS:
                nid, lbl = STAGE_DEFINITIONS[stage_str]
                return nid, lbl, custom_idx
            return f"S{stage_item}", f"Stage {stage_item}", custom_idx

        stage_clean = str(stage_item).strip()

        # Direct check in definitions
        for key, (node_id, label) in STAGE_DEFINITIONS.items():
            major = key.split(".")[0]
            # Match "Stage 0.0", "Stage 0", "0.0", "0", or "S0"
            pattern = (
                rf"(?<![\d.])(?:Stage\s+)?(?:{re.escape(key)}|{major}(?!\d))(?![\d.])"
            )
            if (
                re.search(pattern, stage_clean, flags=re.IGNORECASE)
                or stage_clean.upper() == node_id.upper()
            ):
                # If stage_clean has its own rich text, use it; otherwise use catalog label
                if ":" in stage_clean:
                    cleaned_label = stage_clean.replace('"', "'")
                    return node_id, cleaned_label, custom_idx
                return node_id, label, custom_idx

        cleaned_name = stage_clean.replace('"', "'")
        custom_id = f"S_custom_{custom_idx}"
        return custom_id, cleaned_name, custom_idx + 1

    def _resolve_mermaid_nodes(
        self, active_stages: Optional[List[Union[str, int, Dict[str, Any]]]] = None
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
        self, active_stages: Optional[List[Union[str, int, Dict[str, Any]]]] = None
    ) -> str:
        """Dynamically synthesizes a Mermaid.js graph TD diagram block mapping active CoChem stages.

        Args:
            active_stages: Optional list of active stage identifier strings, ints, or dicts.

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
        self, df: Optional[pd.DataFrame], table_title: Optional[str] = None
    ) -> str:
        """Converts a pandas DataFrame into a standard GitHub-Flavored Markdown (GFM) pipe table.

        Args:
            df: Input pandas DataFrame.
            table_title: Optional title/header for the table.

        Returns:
            GFM formatted table string.
        """
        if df is None or df.empty:
            if table_title:
                return f"### {table_title}\n\n*No tabular data available.*\n"
            return "*No tabular data available.*\n"

        headers = [str(col).replace("|", r"\|").strip() for col in df.columns]

        alignments: List[str] = []
        for col in df.columns:
            is_numeric = (
                pd.api.types.is_numeric_dtype(df[col])
                and not pd.api.types.is_bool_dtype(df[col])
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

        for _, row in df.iterrows():
            row_cells = []
            for col in df.columns:
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

    def format_audit_warnings(self, warnings: Optional[List[str]] = None) -> str:
        """Aggregates non-fatal warnings from cochem_audit_log into Markdown callout blockquotes.

        Args:
            warnings: Optional list of warning strings.

        Returns:
            Formatted callout blockquote string.
        """
        if not warnings:
            return "> **NOTE**: No non-fatal execution warnings recorded during this pipeline run.\n"

        lines: List[str] = []
        for w in warnings:
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
        telem = telemetry or {}

        peak_gpu = (
            telem.get("peak_gpu_vram")
            or telem.get("peak_gpu_vram_mb")
            or telem.get("gpu_vram")
            or telem.get("peak_gpu")
            or telem.get("gpu_peak_vram_mb")
            or "N/A"
        )
        if isinstance(peak_gpu, (int, float)) and not isinstance(peak_gpu, bool):
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
        if isinstance(peak_cpu, (int, float)) and not isinstance(peak_cpu, bool):
            peak_cpu = f"{peak_cpu:.1f}%"

        wall_clock = (
            telem.get("wall_clock_seconds")
            or telem.get("wall_clock_time")
            or telem.get("execution_time")
            or telem.get("wall_clock")
            or telem.get("elapsed_time")
            or "N/A"
        )
        if isinstance(wall_clock, (int, float)) and not isinstance(wall_clock, bool):
            wall_clock = f"{wall_clock:.2f} s"

        peak_ram = (
            telem.get("peak_ram_mb")
            or telem.get("peak_host_ram")
            or telem.get("memory_footprint")
            or telem.get("peak_memory")
            or telem.get("host_ram")
            or "N/A"
        )
        if isinstance(peak_ram, (int, float)) and not isinstance(peak_ram, bool):
            peak_ram = (
                f"{peak_ram:.1f} MB"
                if peak_ram > RAM_THRESHOLD_MB
                else f"{peak_ram:.1f} GB"
            )

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
        data = payload or {}
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

        final_path.write_text(content, encoding="utf-8")
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
import re
from typing import Any, Dict, List

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

    # Test custom stage handling
    custom_stages = ["Stage 10.0: Custom Sinc-DVR Extended", "0.0"]
    custom_flowchart = builder.generate_mermaid_flowchart(custom_stages)
    assert "S_custom_1" in custom_flowchart
    assert "Stage 10.0: Custom Sinc-DVR Extended" in custom_flowchart
    assert "S0" in custom_flowchart

    # Test default stages when None passed
    default_flowchart = builder.generate_mermaid_flowchart()
    assert "S0" in default_flowchart
    assert "S6" in default_flowchart
    assert "S5" in default_flowchart


def test_dataframe_to_gfm_table() -> None:
    """Verifies GFM pipe table conversion from pandas DataFrames (Task 65)."""
    builder = MarkdownBuilder()

    # 1. Realistic conformer DataFrame with numeric floats
    conf_data = {
        "Conformer ID": ["Conf_01", "Conf_02", "Conf_03"],
        "Relative Energy (kcal/mol)": [0.000, 0.423, 1.875],
        "Hartree Energy (Eh)": [-154.1234567, -154.1227891, -154.1204682],
        "Symmetry": ["C1", "Cs", "C1"],
        "Boltzmann Population (%)": [68.4, 24.1, 7.5],
        "Notes": ["Global min\nVerified", "Local min", "High energy"],
    }
    conf_df = pd.DataFrame(conf_data)

    conf_table = builder.dataframe_to_gfm_table(conf_df, table_title="Conformer Distribution")

    assert "### Conformer Distribution" in conf_table
    assert (
        "| Conformer ID | Relative Energy (kcal/mol) | "
        "Hartree Energy (Eh) | Symmetry | "
        "Boltzmann Population (%) | Notes |"
    ) in conf_table
    assert "| :--- | ---: | ---: | :--- | ---: | :--- |" in conf_table
    assert "-154.123457" in conf_table
    assert "0.42" in conf_table
    assert "Global min<br>Verified" in conf_table

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


def test_audit_warnings_and_telemetry_formatting() -> None:
    """Verifies warning callout blockquotes and hardware telemetry formatting (Tasks 66 & 67)."""
    builder = MarkdownBuilder()

    # 1. Non-empty warnings aggregation
    warnings = [
        "SCF convergence required dampening on step 4.",
        "GPU VRAM spike near 90% during Hessian computation.",
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

    # 2. Empty warnings fallback
    empty_block = builder.format_audit_warnings([])
    assert "> **NOTE**: No non-fatal execution warnings recorded" in empty_block

    none_block = builder.format_audit_warnings(None)
    assert "> **NOTE**: No non-fatal execution warnings recorded" in none_block

    # 3. Telemetry formatting
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

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.