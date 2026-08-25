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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\formatters\scribe_md_generator.py ---
"""Dynamic Markdown User Guide Compiler & GFM Table Generator for CoChem-SCRIBE.

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
from collections.abc import Iterable, Sequence
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
    "1.0": ("S1", "Stage 1.0: Conformer Generation"),
    "2.0": ("S2", "Stage 2.0: DFT Optimization"),
    "3.0": ("S3", "Stage 3.0: Frequency & Thermochemistry"),
    "4.0": ("S4", "Stage 4.0: Sinc-DVR Dynamic Tunneling"),
    "5.0": ("S5", "Stage 5.0: Telemetry Aggregation"),
    "6.0": ("S6", "Stage 6.0: SCRIBE Document Synthesis"),
}

STAGE_DESCRIPTIONS_FALLBACK: dict[str, str] = {
    "0": "Stage 0.0: Configuration & Resource Guards",
    "0.0": "Stage 0.0: Configuration & Resource Guards",
    "1": "Stage 1.0: Conformer Generation",
    "1.0": "Stage 1.0: Conformer Generation",
    "2": "Stage 2.0: DFT Optimization",
    "2.0": "Stage 2.0: DFT Optimization",
    "3": "Stage 3.0: Frequency & Thermochemistry",
    "3.0": "Stage 3.0: Frequency & Thermochemistry",
    "4": "Stage 4.0: Sinc-DVR Dynamic Tunneling",
    "4.0": "Stage 4.0: Sinc-DVR Dynamic Tunneling",
    "5": "Stage 5.0: Telemetry Aggregation",
    "5.0": "Stage 5.0: Telemetry Aggregation",
    "6": "Stage 6.0: SCRIBE Document Synthesis",
    "6.0": "Stage 6.0: SCRIBE Document Synthesis",
}


def _sanitize_for_yaml(val: Any) -> Any:
    """Recursively converts non-serializable objects into YAML-safe primitives."""
    if val is None:
        return None
    if isinstance(val, np.floating):
        return float(val)
    if isinstance(val, np.integer):
        return int(val)
    if isinstance(val, np.bool_):
        return bool(val)
    if isinstance(val, bool):
        return bool(val)
    if isinstance(val, int):
        return int(val)
    if isinstance(val, float):
        return float(val)
    if isinstance(val, str):
        return str(val)
    if isinstance(val, os.PathLike | pathlib.PurePath):
        if hasattr(val, "as_posix"):
            return val.as_posix()
        return str(val).replace("\\", "/")
    if isinstance(val, np.ndarray):
        return [_sanitize_for_yaml(item) for item in val.tolist()]
    if isinstance(val, datetime.date | datetime.datetime):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(val, dict):
        return {str(k): _sanitize_for_yaml(v) for k, v in val.items()}
    if isinstance(val, list | tuple | set):
        return [_sanitize_for_yaml(item) for item in val]
    return str(val)


def _get_first_present(
    data: dict[str, Any], keys: list[str], default: Any = "N/A"
) -> Any:
    """Safely retrieves the first present key value from data."""
    for k in keys:
        if k in data and data[k] is not None:
            return data[k]
    return default


_get_present_val = _get_first_present


class MarkdownBuilder:
    """Markdown User Guide and GFM Table synthesis engine for CoChem-SCRIBE.

    Generates structured, publication-grade Markdown documentation
    (CoChem_User_Guide.md) enriched with YAML frontmatter, Stage 0
    provenance matrices, dynamic Mermaid.js flowcharts, GitHub-Flavored
    Markdown (GFM) tables, thermodynamic analysis narratives, hardware
    telemetry charts, and non-fatal audit warning blockquotes. Enforces
    cross-platform safe pathing and non-destructive timestamped overwrite
    protection.
    """

    def __init__(
        self,
        output_dir: str | pathlib.Path | None = None,
        base_filename: str = "CoChem_User_Guide.md",
        filename: str | None = None,
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

    def generate_yaml_frontmatter(
        self, metadata: dict[str, Any] | None = None
    ) -> str:
        """Generates valid YAML frontmatter block with run provenance and metadata.

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
        if (
            "run_id" not in meta
            and "experiment_id" not in meta
            and "pipeline_hash" not in meta
        ):
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

    def generate_system_matrix_section(
        self, system_matrix: dict[str, Any] | None = None
    ) -> str:
        """Generates Markdown readout of Stage 0 active compute engines and nodes.

        Args:
            system_matrix: System configuration and execution environment data.

        Returns:
            Formatted Markdown section under Stage 1 provenance header.
        """
        matrix = system_matrix if isinstance(system_matrix, dict) else {}
        lines: list[str] = [
            "## 1. System Execution Environment & Provenance",
            "",
            "### 1.1 Compute Engines & Versions",
        ]

        engines = matrix.get("engines")
        if isinstance(engines, dict) and engines:
            for engine, ver in engines.items():
                lines.append(f"- **{engine}**: `{ver}`")
        elif isinstance(engines, list | tuple | set) and engines:
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
            default=_get_first_present(
                matrix, ["environment_tier", "environment"], "Unknown / Heterogeneous"
            ),
        )
        node_arch = _get_first_present(
            host_info,
            ["node_architecture", "architecture", "node_arch"],
            default=_get_first_present(
                matrix,
                ["node_architecture", "architecture"],
                platform.machine() or "x86_64",
            ),
        )
        cpu_cores = _get_first_present(
            host_info,
            ["cpu_cores", "cpu", "cores"],
            default=_get_first_present(matrix, ["cpu_cores", "cpu", "cores"], "N/A"),
        )
        gpu_device = _get_first_present(
            host_info,
            ["gpu_model", "gpu_device", "gpu"],
            default=_get_first_present(
                matrix, ["gpu_model", "gpu_device", "gpu"], "N/A"
            ),
        )
        host_ram = _get_first_present(
            host_info,
            ["host_ram", "memory_allocation", "host_ram_gb", "ram_gb"],
            default=_get_first_present(
                matrix,
                ["host_ram", "memory_allocation", "host_ram_gb", "ram_gb"],
                "N/A",
            ),
        )
        py_version = _get_first_present(
            host_info,
            ["python_version", "python"],
            default=_get_first_present(
                matrix, ["python_version", "python"], sys.version.split()[0]
            ),
        )
        cfg_hash = _get_first_present(
            matrix,
            ["config_hash", "pipeline_hash"],
            default=_get_first_present(
                host_info, ["config_hash", "pipeline_hash"], "N/A"
            ),
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
        stage_item: str | int | float | dict[str, Any], custom_idx: int
    ) -> tuple[str, str, int]:
        """Resolves stage item into a sanitized node ID, label, and custom index."""
        if isinstance(stage_item, dict):
            raw_id = str(
                stage_item.get("id")
                or stage_item.get("stage")
                or f"S_custom_{custom_idx}"
            )
            label = str(stage_item.get("name") or stage_item.get("label") or raw_id)
            clean_id = re.sub(r"[^a-zA-Z0-9_]", "_", raw_id)
            if not re.match(r"^S(?:_|\d)", clean_id):
                clean_id = f"S_{clean_id}"
            return clean_id, label.replace('"', "'"), custom_idx + 1

        if (
            isinstance(stage_item, int | float | np.integer | np.floating)
            and not isinstance(stage_item, bool)
        ):
            val_float = float(stage_item)
            val_int = int(val_float)
            stage_str = f"{val_int}.0" if val_float == val_int else f"{val_float}"
            if stage_str in STAGE_DEFINITIONS:
                nid, lbl = STAGE_DEFINITIONS[stage_str]
                return nid, lbl, custom_idx
            clean_id = (
                f"S{val_int}"
                if val_float == val_int
                else f"S_{str(val_float).replace('.', '_')}"
            )
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
        active_stages: Sequence[Any] | None = None,
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
        self,
        active_stages: Sequence[Any] | None = None,
    ) -> str:
        """Synthesizes a Mermaid.js graph TD diagram block mapping active stages.

        Args:
            active_stages: Optional sequence of active stage identifier strings/ints.

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

    def dataframe_to_gfm_table(
        self,
        df: pd.DataFrame | list[dict[str, Any]] | dict[str, Any] | None,
        table_title: str | None = None,
    ) -> str:
        """Converts a pandas DataFrame into a standard GFM pipe table.

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
            str(col)
            .replace("\r\n", "<br>")
            .replace("\n", "<br>")
            .replace("|", r"\|")
            .strip()
            for col in target_df.columns
        ]

        alignments: list[str] = []
        for col in target_df.columns:
            is_numeric = (
                pd.api.types.is_numeric_dtype(target_df[col])
                and not pd.api.types.is_bool_dtype(target_df[col])
            )
            alignments.append("---:" if is_numeric else ":---")

        rows: list[str] = []
        if table_title:
            rows.append(f"### {table_title}")
            rows.append("")

        header_line = "| " + " | ".join(headers) + " |"
        rows.append(header_line)

        sep_line = "| " + " | ".join(alignments) + " |"
        rows.append(sep_line)

        for row in target_df.itertuples(index=False):
            row_cells = []
            for col, val in zip(target_df.columns, row, strict=False):
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

        if isinstance(val, int | np.integer) and not isinstance(val, bool):
            return str(val)

        if isinstance(val, float | np.floating):
            if float(val).is_integer() and any(
                k in col_name.lower()
                for k in [
                    "#",
                    "mode",
                    "index",
                    "idx",
                    "step",
                    "iteration",
                    "count",
                    "num",
                ]
            ):
                return str(int(val))
            return MarkdownBuilder._format_float_cell(float(val), col_name)

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

    def format_thermodynamic_insights(self, insights_text: str | None = None) -> str:
        """Formats thermodynamic analytical insights under section 2.

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
                "narrative commentary.*"
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
                "*Analytical data was aggregated without additional "
                "narrative commentary.*"
            )
        else:
            lines.append(cleaned)

        lines.append("")
        return "\n".join(lines)

    # Backward compatibility alias
    inject_thermodynamic_insights = format_thermodynamic_insights

    def format_audit_warnings(
        self,
        warnings: Iterable[str | None] | str | dict[str, Any] | None = None,
    ) -> str:
        """Aggregates non-fatal warnings into Markdown callout blockquotes.

        Args:
            warnings: Optional list, string, or dict of warnings.

        Returns:
            Formatted callout blockquote string.
        """
        no_warn_msg = (
            "> **NOTE**: No non-fatal execution warnings recorded during this "
            "pipeline run.\n"
        )
        if not warnings:
            return no_warn_msg

        if isinstance(warnings, str):
            warn_list = [warnings]
        elif isinstance(warnings, dict):
            warn_list = [f"{k}: {v}" for k, v in warnings.items()]
        elif isinstance(warnings, Iterable):
            warn_list = [
                str(w)
                for w in warnings
                if w is not None and str(w).strip() != "None"
            ]
        else:
            warn_list = [str(warnings)]

        lines: list[str] = []
        for w in warn_list:
            if w is None or str(w).strip() == "None":
                continue
            w_clean = str(w).strip()
            if w_clean:
                lines.append(f"> **WARNING**: {w_clean}")

        if not lines:
            return no_warn_msg

        return "\n\n".join(lines) + "\n"

    # Backward compatibility alias
    format_warning_blockquotes = format_audit_warnings

    def format_hardware_telemetry(
        self, telemetry: dict[str, Any] | None = None
    ) -> str:
        """Formats CPU/GPU peak usage metrics as a structured Markdown list.

        Args:
            telemetry: Dictionary of hardware telemetry metrics.

        Returns:
            Formatted Markdown section under ## Hardware Resource Telemetry.
        """
        telem = telemetry if isinstance(telemetry, dict) else {}

        # 1. GPU VRAM
        peak_gpu = "N/A"
        for k in ["peak_gpu_vram_mb", "gpu_peak_vram_mb", "gpu_vram_peak_mb"]:
            if k in telem and telem[k] is not None:
                val = telem[k]
                if (
                    isinstance(val, int | float | np.integer | np.floating)
                    and not isinstance(val, bool)
                ):
                    peak_gpu = f"{float(val):.1f} MB"
                elif isinstance(val, str):
                    peak_gpu = val
                break
        if peak_gpu == "N/A":
            for k in ["peak_gpu_vram_gb", "gpu_peak_vram_gb"]:
                if k in telem and telem[k] is not None:
                    val = telem[k]
                    if (
                        isinstance(val, int | float | np.integer | np.floating)
                        and not isinstance(val, bool)
                    ):
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
            if (
                isinstance(raw_gpu, int | float | np.integer | np.floating)
                and not isinstance(raw_gpu, bool)
            ):
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
        if (
            isinstance(peak_cpu, int | float | np.integer | np.floating)
            and not isinstance(peak_cpu, bool)
        ):
            peak_cpu = f"{float(peak_cpu):.1f}%"

        # 3. Wall clock
        wall_clock = _get_first_present(
            telem,
            [
                "wall_clock_seconds",
                "wall_clock_time",
                "execution_time",
                "wall_clock",
                "elapsed_time",
            ],
            default="N/A",
        )
        if (
            isinstance(wall_clock, int | float | np.integer | np.floating)
            and not isinstance(wall_clock, bool)
        ):
            wall_clock = f"{float(wall_clock):.2f} s"

        # 4. RAM
        peak_ram = "N/A"
        for k in ["peak_ram_mb"]:
            if k in telem and telem[k] is not None:
                val = telem[k]
                if (
                    isinstance(val, int | float | np.integer | np.floating)
                    and not isinstance(val, bool)
                ):
                    peak_ram = f"{float(val):.1f} MB"
                elif isinstance(val, str):
                    peak_ram = val
                break
        if peak_ram == "N/A":
            for k in ["peak_ram_gb", "host_ram_gb"]:
                if k in telem and telem[k] is not None:
                    val = telem[k]
                    if (
                        isinstance(val, int | float | np.integer | np.floating)
                        and not isinstance(val, bool)
                    ):
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
            if (
                isinstance(raw_ram, int | float | np.integer | np.floating)
                and not isinstance(raw_ram, bool)
            ):
                val_float = float(raw_ram)
                peak_ram = (
                    f"{val_float:.1f} MB"
                    if val_float > RAM_THRESHOLD_MB
                    else f"{val_float:.1f} GB"
                )
            elif isinstance(raw_ram, str):
                peak_ram = raw_ram

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
                "gpu_vram_peak_mb",
                "gpu_peak_vram_gb",
                "peak_gpu_vram_gb",
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
                "peak_ram_gb",
                "host_ram_gb",
                "warnings",
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
        self, payload: dict[str, Any], keys: list[str]
    ) -> pd.DataFrame | None:
        """Extracts and standardizes DataFrame from payload given fallback keys."""
        if not isinstance(payload, dict):
            return None
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

    def build_user_guide(self, payload: dict[str, Any] | None = None) -> str:
        """Assembles the complete Markdown User Guide document from payload.

        Args:
            payload: Harvested pipeline data, system matrix, telemetry, and DataFrames.

        Returns:
            Complete GitHub-Flavored Markdown user guide string.
        """
        data = payload if isinstance(payload, dict) else {}
        sections: list[str] = []

        # 1. YAML Frontmatter
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        for k in [
            "title",
            "pipeline_hash",
            "environment",
            "environment_tier",
            "run_id",
            "target_molecule",
            "smiles",
        ]:
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
        target_dir: str | pathlib.Path | None = None,
        base_filename: str | None = None,
    ) -> pathlib.Path:
        """Saves Markdown document to target directory with overwrite protection.

        Args:
            content: Markdown formatted text.
            target_dir: Optional directory path. Defaults to self.output_dir.
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
        builder = MarkdownBuilder(
            output_dir=tmp_path, base_filename="CoChem_User_Guide.md"
        )

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
        assert fm.startswith("---\n") and fm.endswith("\n---"), (
            "Frontmatter delimiters failed"
        )

        # 2. Test System Matrix Section
        sys_mat = {
            "engines": {"ORCA": "6.1.1", "PySCF": "2.8.0"},
            "host": {
                "cpu_cores": 8,
                "gpu_device": "RTX 4090",
                "host_ram": "32 GB",
            },
        }
        sys_sec = builder.generate_system_matrix_section(sys_mat)
        assert "## 1. System Execution Environment & Provenance" in sys_sec, (
            "System matrix header missing"
        )
        assert "**ORCA**: `6.1.1`" in sys_sec, "ORCA engine readout missing"

        # 3. Test Mermaid Flowchart
        flowchart = builder.generate_mermaid_flowchart(
            ["0.0", "1.0", "2.0", "3.0", "6.0"]
        )
        assert "```mermaid" in flowchart and "graph TD" in flowchart, (
            "Mermaid syntax error"
        )
        assert (
            "S0" in flowchart and "-->" in flowchart and "S1" in flowchart
        ), "Stage connections missing"

        # 4. Test GFM Table
        sample_df = pd.DataFrame({
            "Conformer": ["C1", "C2"],
            "Energy (Hartree)": [-154.1234567, -154.1122334],
            "Rel Energy (kcal/mol)": [0.00, 7.04],
        })
        table_out = builder.dataframe_to_gfm_table(
            sample_df, table_title="Conformer Summary"
        )
        assert "### Conformer Summary" in table_out, "Table title missing"
        assert "-154.123457" in table_out, "Hartree rounding format incorrect"

        # 5. Test Full Document Assembly & Overwrite Protection
        payload = {
            "metadata": meta,
            "system_matrix": sys_mat,
            "active_stages": ["0.0", "1.0", "6.0"],
            "conformers_df": sample_df,
            "thermodynamic_insights": (
                "Ethanol conformer analysis completed. <<INSERT_PLACEHOLDER>>"
            ),
            "warnings": ["Minor SCF oscillation resolved."],
            "telemetry": {
                "peak_gpu_vram": 2048.0,
                "peak_cpu_percent": 45.2,
                "wall_clock_seconds": 12.34,
            },
        }
        doc_content = builder.build_user_guide(payload)
        file_1 = builder.save_user_guide(doc_content)
        assert file_1.exists() and file_1.name == "CoChem_User_Guide.md", (
            "File 1 save failed"
        )

        file_2 = builder.save_user_guide(doc_content)
        assert file_2.exists() and file_2 != file_1, (
            "Overwrite protection failed"
        )
        assert file_2.name.startswith("CoChem_User_Guide_"), (
            "Timestamped filename format incorrect"
        )

    logger.info("[SCRIBE MD GENERATOR PRE-FLIGHT VERIFIED]")

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\formatters\test_scribe_md_generator.py ---
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
import pathlib
import re
from typing import Any

import h5py
import numpy as np
import pandas as pd
import pytest
import yaml

from formatters.scribe_md_generator import MarkdownBuilder

# ---------------------------------------------------------------------------
# Zero-Mock Physical Fixtures (Real Disk I/O via tmp_path)
# ---------------------------------------------------------------------------


@pytest.fixture
def hdf5_physical_payload(tmp_path: pathlib.Path) -> pathlib.Path:
    """Generates a physical landscape.h5 file with authentic HDF5 hierarchies.

    Under the Zero-Mock mandate, this fixture writes real numerical arrays and
    attributes using h5py in latest library format without mock bypasses.

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
) -> dict[str, Any]:
    """Generates authentic JSON audit logs and metadata dictionary on disk.

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
    audit_log_path.write_text(
        json.dumps(audit_data, indent=2), encoding="utf-8"
    )

    manifest_path = tmp_path / "cochem_deployment_manifest.json"
    manifest_data = {
        "ORCA": "6.1.1",
        "xTB": "6.7.1",
        "MACE-OFF23": "2023.1",
    }
    manifest_path.write_text(
        json.dumps(manifest_data, indent=2), encoding="utf-8"
    )

    metadata = {
        "title": "CoChem Computational Analysis User Guide",
        "version": "2.0.0",
        "generated_at": "2026-08-23T12:00:00",
        "pipeline_hash": (
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        ),
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
    """Returns a real pandas.DataFrame with conformer ranking data.

    Returns:
        Structured DataFrame with conformer IDs, energies, and symmetry.
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
    """Test Case 1: MarkdownBuilder Initialization & Dynamic Pathing (Tasks 61 & 68).

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

    # 3. Verify path resolution is pure Python pathlib without POSIX $HOME
    assert not str(custom_builder.output_dir).startswith("$")


def test_yaml_frontmatter_and_system_matrix_generation(
    tmp_path: pathlib.Path,
    sample_metadata_and_telemetry: dict[str, Any],
) -> None:
    """Test Case 2: YAML Frontmatter & System Matrix Generation (Task 62).

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
    assert (
        f"- **Configuration SHA-256**: `{metadata['pipeline_hash']}`"
        in sys_section
    )


def test_dynamic_mermaid_flowchart_synthesis() -> None:
    """Test Case 3: Dynamic Mermaid.js Flowchart Synthesis (Task 63).

    Verifies dynamic Mermaid.js graph TD diagram generation mapping active stages,
    ensuring standard stage nodes, directed edge transitions, and valid rendering.
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
    """Test Case 4: GFM Table Pipe Formatting (Task 65).

    Verifies conversion of real pandas DataFrames into standard GFM pipe tables,
    alignment rows, numeric precision preservation, and empty table fallbacks.
    """
    builder = MarkdownBuilder()

    # 1. Format sample conformer DataFrame
    table_output = builder.format_gfm_table(
        sample_conformer_dataframe, table_title="Conformer Energetic Ranking"
    )

    assert "### Conformer Energetic Ranking" in table_output
    assert (
        "| Conformer ID | Relative Energy (kcal/mol) | "
        "Hartree Energy (Eh) | Symmetry | Boltzmann Population (%) |"
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
    """Test Case 5: Thermodynamic Insights Injection & Token Scrubbing (Task 64).

    Verifies rendering of section ## 2. Thermodynamic & Structural Analysis,
    placeholder token sanitization (<<INSERT_*>>, [PLACEHOLDER]), and empty fallback.
    """
    builder = MarkdownBuilder()

    # 1. Narrative with internal placeholder tokens to scrub
    raw_insights = (
        "The global minimum conformer demonstrates significant stabilization. "
        "<<INSERT_THERMO_TABLE>> The calculated barrier is 14.5 kcal/mol. "
        "[PLACEHOLDER] Vibrational zero-point energy indicates strong "
        "zero-point motion."
    )
    rendered = builder.inject_thermodynamic_insights(raw_insights)

    assert "## 2. Thermodynamic & Structural Analysis" in rendered
    assert (
        "The global minimum conformer demonstrates significant stabilization."
        in rendered
    )
    assert "The calculated barrier is 14.5 kcal/mol." in rendered
    assert (
        "Vibrational zero-point energy indicates strong zero-point motion."
        in rendered
    )
    assert "<<INSERT_THERMO_TABLE>>" not in rendered
    assert "[PLACEHOLDER]" not in rendered

    # 2. Passing empty string or None renders clean professional fallback
    empty_rendered = builder.inject_thermodynamic_insights("")
    assert "## 2. Thermodynamic & Structural Analysis" in empty_rendered
    assert (
        "*Analytical data was aggregated without additional "
        "narrative commentary.*" in empty_rendered
    )

    none_rendered = builder.inject_thermodynamic_insights(None)
    assert "## 2. Thermodynamic & Structural Analysis" in none_rendered
    assert (
        "*Analytical data was aggregated without additional "
        "narrative commentary.*" in none_rendered
    )


def test_audit_warnings_callout_blockquotes_and_hardware_telemetry(
    tmp_path: pathlib.Path,
    sample_metadata_and_telemetry: dict[str, Any],
) -> None:
    """Test Case 6: Audit Warnings Callouts & Hardware Telemetry (Tasks 66 & 67).

    Verifies aggregation of non-fatal audit log warnings into GitHub-style callouts,
    empty warnings fallback, and formatting of hardware telemetry section with GPU, CPU,
    and wall-clock execution metrics.
    """
    builder = MarkdownBuilder(output_dir=tmp_path)
    telemetry_data = sample_metadata_and_telemetry["raw_telemetry"]

    # 1. Non-empty warnings formatting
    warnings = telemetry_data["warnings"]
    warning_block = builder.format_warning_blockquotes(warnings)
    assert (
        "> **WARNING**: SCF convergence required dampening on step 4."
        in warning_block
    )
    assert "> **WARNING**: GPU VRAM spike near 85%." in warning_block

    # 2. Empty warnings fallback
    empty_block = builder.format_warning_blockquotes([])
    assert (
        "> **NOTE**: No non-fatal execution warnings recorded during this "
        "pipeline run." in empty_block
    )

    none_block = builder.format_warning_blockquotes(None)
    assert (
        "> **NOTE**: No non-fatal execution warnings recorded during this "
        "pipeline run." in none_block
    )

    # 3. Hardware telemetry section formatting
    telem_section = builder.format_telemetry_section(telemetry_data)
    assert (
        "## 4. Hardware Telemetry & Compute Resource Allocation"
        in telem_section
    )
    assert "- **Peak GPU VRAM Usage**: 4250.0 MB" in telem_section
    assert "- **Peak CPU Usage**: 88.5%" in telem_section
    assert "- **Wall-Clock Execution Time**: 142.50 s" in telem_section


def test_non_destructive_timestamped_overwrite_protection(
    tmp_path: pathlib.Path,
) -> None:
    """Test Case 7: Non-Destructive Overwrite Protection (Tasks 68 & 69).

    Verifies that calling write_user_guide multiple times preserves existing files,
    creates timestamped copies with pattern CoChem_User_Guide_*.md, and UTF-8 encoding.
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
    assert (
        re.match(r"^CoChem_User_Guide_\d{8}_\d{6}(?:_\d+)?\.md$", file_2.name)
        is not None
    )
    assert file_2.suffix == ".md"

    # 3. Assert original file remains completely unmodified
    assert file_1.read_text(encoding="utf-8") == initial_content
    assert file_2.read_text(encoding="utf-8") == second_content


def test_end_to_end_user_guide_generation(
    tmp_path: pathlib.Path,
    hdf5_physical_payload: pathlib.Path,
    sample_metadata_and_telemetry: dict[str, Any],
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

    thermo_df = pd.DataFrame({
        "Property": [
            "Zero-Point Energy (ZPE)",
            "Enthalpy (H)",
            "Gibbs Free Energy (G)",
        ],
        "Value (Hartree)": [zpe, enthalpy, gibbs],
    })

    vib_df = pd.DataFrame({
        "Mode #": list(range(1, len(vib_freqs) + 1)),
        "Frequency (cm-1)": vib_freqs,
    })

    metadata = sample_metadata_and_telemetry
    telemetry = metadata["raw_telemetry"]
    engines = metadata["raw_engines"]

    payload: dict[str, Any] = {
        "metadata": {
            "title": metadata["title"],
            "version": metadata["version"],
            "generated_at": metadata["generated_at"],
            "pipeline_hash": metadata["pipeline_hash"],
            "environment": metadata["environment"],
            "fair_compliance": metadata["fair_compliance"],
        },
        "overview": (
            "Complete computational quantum chemistry report for "
            "conformer exploration, vibrational spectroscopy, and "
            "thermodynamic state functions."
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
        "active_stages": [
            "Stage 0.0",
            "Stage 1.0",
            "Stage 2.0",
            "Stage 3.0",
            "Stage 6.0",
        ],
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
    assert (
        "Conformational search identified Conf_01 as the global minimum."
        in generated_md
    )
    assert "<<INSERT_THERMO>>" not in generated_md
    assert "| Zero-Point Energy (ZPE) | 0.085400 |" in generated_md

    # 7. Vibrational / Spectroscopic Analysis Table
    assert "## Spectroscopic & Vibrational Analysis" in generated_md
    assert "| 1 | 450.20 |" in generated_md

    # 8. Execution Warnings
    assert "### Execution Warnings & Audit Trail" in generated_md
    assert (
        "> **WARNING**: SCF convergence required dampening on step 4."
        in generated_md
    )

    # 9. Hardware Telemetry
    assert (
        "## 4. Hardware Telemetry & Compute Resource Allocation"
        in generated_md
    )
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

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.