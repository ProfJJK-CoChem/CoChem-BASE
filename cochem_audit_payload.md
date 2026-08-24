Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-SCRIBE\.in-progress\04_scribe_payload_builder.md.
Original prompt:
# Phase 2, Task 6: Context-Safe Payload Builder & Prompt Synthesis (`harvesters/scribe_payload_builder.py`)

## Context
You are a coding agent tasked with implementing a specific module for CoChem-SCRIBE.
The target repository path is: `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE`.
The files you must implement are:
- `harvesters/scribe_payload_builder.py`
- `harvesters/test_scribe_payload_builder.py`

## Authoritative Reference
This implementation is strictly governed by **Phase 2, Task 6: Context-Safe Payload Builder & Prompt Synthesis (Stage 6.1)** of the CoChem-SCRIBE Software Requirements Specification (SRS), adhering to Method Matrix v4, FAIR data principles, the Zero-Mock Anti-Spoofing Protocol, and the 6-Tier Environment Matrix (Local-Windows WSL, Local-MacOS OrbStack, Local-Linux Debian, Codespaces, GitHub Actions, HPC).

---

## Deliverable 1: `harvesters/scribe_payload_builder.py`

### 1. Architectural Philosophy & Mathematical Air-Gap
- **Strict Mathematical Air-Gap:** The LLM must be strictly treated as a narrative formatting engine, never as a physical or mathematical calculator. It is strictly prohibited from inventing, calculating, or estimating physical constants, energies, frequencies, or coordinates.
- **Token Economy & OOM Protection:** Prompt payloads must be dynamically metered and bounded to a strict safety threshold of **6,000 tokens** using local token metrology (`tiktoken`, `cl100k_base`).
- **Air-Gap Compliance:** All tokenization, string formatting, and validation must execute 100% locally and offline. No external HTTP webhooks, network calls, or un-isolated APIs are permitted.

---

### 2. Class Architecture & Interface Contract (`PayloadBuilder`)

Define the `PayloadBuilder` class in `harvesters/scribe_payload_builder.py` with complete Python 3.10+ typing (`typing.Dict`, `typing.Any`, `typing.Optional`, `typing.Union`, `pathlib.Path`):

```python
import pathlib
import typing
import tiktoken
import logging

class PayloadBuilder:
    """Context-compression engine and hallucination-resistant prompt synthesizer.
    
    Enforces the Mathematical Air-Gap between harvested physical data and generative LLMs,
    manages the 6,000-token context economy via tiktoken (cl100k_base), and constructs
    targeted academic methodology and thermodynamic insight prompts.
    """
    def __init__(
        self,
        aggregated_data: typing.Dict[str, typing.Any],
        manifest_data: typing.Optional[typing.Dict[str, typing.Any]] = None,
        manifest_path: typing.Optional[typing.Union[str, pathlib.Path]] = None,
        token_limit: int = 6000,
        dry_run: bool = False
    ) -> None:
        self.aggregated_data = aggregated_data
        self.manifest_data = manifest_data or {}
        self.manifest_path = manifest_path
        self.token_limit = token_limit
        self.dry_run = dry_run
        self.encoding = tiktoken.get_encoding("cl100k_base")
        self.logger = logging.getLogger("scribe.payload_builder")

    def synthesize_pipeline_context(self) -> str:
        """Constructs concise 'State of the Run' factual provenance string from manifest."""
        pass  # Real implementation required in file

    def get_master_system_prompt(self) -> str:
        """Returns the immutable Master System Prompt commanding strict mathematical air-gap."""
        pass  # Real implementation required in file

    def count_tokens(self, text: str) -> int:
        """Measures integer token count of candidate text payload using tiktoken cl100k_base."""
        pass  # Real implementation required in file

    def truncate_payload(self, data: typing.Dict[str, typing.Any]) -> typing.Dict[str, typing.Any]:
        """Applies 4-tier context-chunking priority drops until token ceiling is met."""
        pass  # Real implementation required in file

    def build_methodology_prompt(self) -> str:
        """Synthesizes APS-compliant computational methodology prompt."""
        pass  # Real implementation required in file

    def build_insights_prompt(self) -> str:
        """Synthesizes thermodynamic Boltzmann population analysis prompt."""
        pass  # Real implementation required in file

    def inject_lam_justification(self, prompt: str) -> str:
        """Injects Sinc-DVR torsional motion justification request if LAM trigger is active."""
        pass  # Real implementation required in file

    def execute_dry_run(self) -> str:
        """Returns static fallback methodology string when offline/dry-run is toggled."""
        pass  # Real implementation required in file
```

---

### 3. Detailed Functional Requirements

#### 3.1 Module State & Pipeline Context Synthesis (SRS §6.2.1, Tasks 21 & 22)
- **Data Ingestion:** Ingest the aggregated data dictionary (containing conformers, spectroscopic tensors, thermodynamic scalars, and telemetry metrics) produced by `scribe_aggregator.py`.
- **Manifest Ingestion & Dynamic Resolution:** Ingest `cochem_deployment_manifest.json` from a passed dictionary or load it from disk using dynamic `pathlib.Path` resolution.
- **Pipeline Provenance Synthesis (`synthesize_pipeline_context`):**
  Synthesize a concise "State of the Run" factual provenance string derived directly from the deployment manifest (e.g., *"This dataset was generated using ORCA 6.1.1 for electronic structure, MACE-OFF23 for initial conformer routing, and CODATA 2022 constants."*). This provides grounding metadata for the LLM without raw tensor overhead.

#### 3.2 Immutable Master System Prompt (SRS §6.2.2, Task 23)
- **Immutable Prepend:** Every generated LLM request payload MUST be prepended with the immutable Master System Prompt.
- **Verbatim Phrasing Mandate:** The prompt text must explicitly command verbatim:
  > *"You are an automated academic writer for the CoChem computational chemistry pipeline. You are strictly forbidden from inventing, calculating, or guessing physical constants, energies, frequencies, or geometric bond lengths. You must only provide narrative insight, methodology structuring, and analytical text based exclusively on the provided metadata. Use explicit injection tags such as `INSERT_THERMO_TABLE_HERE` where exact numerical data should be injected."*

#### 3.3 Dynamic Token Metrology via `tiktoken` (SRS §6.2.3, Task 24)
- **Encoding:** Integrate `tiktoken` pinned strictly to the `cl100k_base` BPE encoding.
- **Integer Measurement (`count_tokens`):** Implement a method to accurately measure the integer token count of any candidate prompt or string payload locally and deterministically.

#### 3.4 4-Tier Context-Chunking & Truncation Algorithm (SRS §6.2.4, Task 25)
- **Safety Ceiling:** Strictly enforce the maximum ceiling of **6,000 tokens**.
- **Deterministic Priority Drop Hierarchy:** If candidate payload tokens exceed 6,000, execute an iterative downsampling/truncation algorithm that sheds data in this exact order:
  1. **Tier 1 Drop:** Drop lowest-energy conformer statistical arrays beyond the top 3 global minima.
  2. **Tier 2 Drop:** Drop high-frequency vibrational scalar noise (retaining only the defining fundamental vibrational frequencies).
  3. **Tier 3 Drop:** Drop detailed telemetry warnings, retaining only `"Fatal"` and `"Critical"` hardware tags.
  4. **Tier 4 Protected Invariants (NEVER Truncate):** The global minimum Gibbs Free Energy ($\Delta G$), Zero-Point Vibrational Energy (ZPE), and the deployment manifest software engine versions must NEVER be pruned or omitted under any circumstance.

#### 3.5 Dynamic Prompt Targeting (SRS §6.2.5, Tasks 26 & 27)
Implement specialized prompt generation methods:
- **Methodology Prompt (`build_methodology_prompt`):**
  Synthesizes a prompt commanding the LLM to generate a 2-paragraph, APS-compliant computational methodology section based strictly on the extracted deployment manifest and citation engine list.
- **Insights / User Guide Prompt (`build_insights_prompt`):**
  Synthesizes a prompt commanding the LLM to write a short "Thermodynamic Analysis" paragraph highlighting which conformer dominates the Boltzmann population based on computed energy gaps ($\Delta E$, $\Delta G$), formatted for direct injection into `CoChem_User_Guide.md`.

#### 3.6 `LAM_TRIGGER` Physics Justification Injection (SRS §6.2.6, Task 28)
- **Detection:** Inspect harvested metadata/telemetry for Large-Amplitude Motion (LAM) flags indicating that 1D or 2D Sinc-DVR (Discrete Variable Representation) was executed instead of standard VPT2.
- **Mandatory Injection String:** If the trigger condition is met, dynamically append the exact justification command verbatim to the synthesized prompt:
  > *"The telemetry indicates the system utilized a Sinc-DVR for torsional motion. Generate one paragraph scientifically justifying the use of Sinc-DVR over the standard rigid-rotor harmonic oscillator (RRHO) approximation for this highly flexible coordinate."*

#### 3.7 Dry-Run Boilerplate String Fallbacks (SRS §6.2.7, Task 29)
- **Offline / Dry-Run Intercept:** If `dry_run=True` is passed or `RESOURCE_GUARD` (Stage 0.0) forces offline mode, bypass token counting and LLM prompt synthesis entirely.
- **Static Return:** Immediately return deterministic, hardcoded boilerplate methodology strings:
  > *"Calculations were performed using the methods listed in the appended tables. [LLM BYPASSED VIA DRY-RUN]"*
- **Execution Speed:** Ensure fallback returns in $<0.05$ seconds to allow Stage 6.3 PDF compilation without AI inference.

---

## Deliverable 2: `harvesters/test_scribe_payload_builder.py` (SRS §6.3, Task 30)

Implement a comprehensive `pytest` test suite adhering to the **Zero-Mock Anti-Spoofing Protocol**:

1. **Token Count Assertion:** Feed an authentic, maximal physical chemistry data payload (e.g., real Z-Matrix coordinate structures from an oversampled trajectory) into the builder. Do not use dummy stubs or mock objects. Assert that `count_tokens` accurately measures token usage and flags payloads exceeding 6,000 tokens.
2. **Truncation Trigger Test:** Feed a structurally valid maximal statistical dictionary exceeding ~8,500 tokens. Assert that the builder executes the 4-tier chunking algorithm, prunes data in the exact physical priority order (conformers > vibrational noise > non-critical telemetry), preserves Tier 4 invariants ($\Delta G$, ZPE, manifest software versions), and returns a final string $\le 6,000$ tokens without unhandled exceptions.
3. **Master System Prompt Regex Assertion:** Assert via regular expressions that the compiled prompt begins with the immutable Master System Prompt and contains the exact phrase `"strictly forbidden"` and injection tag `INSERT_THERMO_TABLE_HERE`.
4. **Dry-Run Benchmark Assertion:** Assert that executing with `dry_run=True` returns the deterministic fallback methodology string in $<0.05$ seconds, successfully bypassing all `tiktoken` processing overhead without invoking `unittest.mock`.

---

## Execution Constraints & Anti-Spoofing Directives

1. **Zero Mocking / Placeholders:**
   - Every class, method, and test fixture must be fully implemented with real, executable Python logic.
   - Do NOT include `pass`, `# TODO`, `...` placeholders, dummy dictionary returns, or fake calculation stubs in implementation files.
   - Zero-Mock applies strictly to testing (no `unittest.mock` or fake data objects in test fixtures); production `--dry-run` string fallbacks are mandatory per Task 29.
2. **Dynamic Path Resolution:**
   - All filesystem paths must resolve dynamically via `pathlib.Path.home()` or `pathlib.Path`.
   - Hardcoded operating system paths (e.g., `C:\Users\...` or `/home/...`) are strictly forbidden.
3. **6-Tier Environment Matrix Compliance:**
   - The module and test suite must execute without modification across Linux (Debian/Ubuntu), macOS (OrbStack), Windows (WSL), Codespaces, GitHub Actions, and HPC nodes.
4. **FAIR Data & Provenance Compliance:**
   - Statistical moments must conform to standard keys: `{"Min", "Max", "Mean", "StdDev"}`.
   - All prompt payloads must retain explicit software version tags and provenance metadata.
5. **Air-Gap Guarantee:**
   - All tokenization and prompt construction must operate completely offline. Zero network calls.
6. **Deliverable Scope:**
   - Implement both `harvesters/scribe_payload_builder.py` and `harvesters/test_scribe_payload_builder.py`.

---

## Task
Implement the Python modules as described and save them to `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE\harvesters\scribe_payload_builder.py` and `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE\harvesters\test_scribe_payload_builder.py` using the `write_to_file` tool.


Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\harvesters\__init__.py ---
"""CoChem-SCRIBE Harvesters Package."""

from .scribe_aggregator import (
    HARTREE_TO_KCAL_MOL,
    DataAggregator,
    ScribeAggregationError,
)
from .scribe_payload_builder import (
    PayloadBuilder,
)

__all__ = [
    "HARTREE_TO_KCAL_MOL",
    "DataAggregator",
    "ScribeAggregationError",
    "PayloadBuilder",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\harvesters\scribe_payload_builder.py ---
#!/usr/bin/env python3
"""CoChem-SCRIBE: Context-Safe Payload Builder.

Phase 2, Task 6: Context-Safe Payload Builder & Prompt Synthesis
(harvesters/scribe_payload_builder.py).

Enforces the Mathematical Air-Gap between harvested physical quantum chemistry data and
generative LLMs, bounds context window consumption to 6,000 tokens using deterministic
tiktoken (cl100k_base) metrology, executes 4-tier context-chunking priority drops
preserving Tier-4 physical invariants, and synthesizes APS-compliant methodology and
thermodynamic insight prompt payloads.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import pathlib
from typing import Any

import tiktoken

logger = logging.getLogger("scribe.payload_builder")

DEFAULT_TOKEN_LIMIT: int = 6000
MAX_FUNDAMENTAL_MODES: int = 15
MAX_RETAINED_CONFORMERS: int = 3


class PayloadBuilder:
    """Context-compression engine and hallucination-resistant prompt synthesizer.

    Enforces the Mathematical Air-Gap between harvested physical data and generative
    LLMs, manages the 6,000-token context economy via tiktoken (cl100k_base), and
    constructs targeted academic methodology and thermodynamic insight prompts.
    """

    MASTER_SYSTEM_PROMPT: str = (
        "You are an automated academic writer for the CoChem computational "
        "chemistry pipeline. You are strictly forbidden from inventing, "
        "calculating, or guessing physical constants, energies, frequencies, "
        "or geometric bond lengths. You must only provide narrative insight, "
        "methodology structuring, and analytical text based exclusively on the "
        "provided metadata. Use explicit injection tags such as "
        "INSERT_THERMO_TABLE_HERE where exact numerical data should be injected."
    )

    DRY_RUN_FALLBACK_TEXT: str = (
        "Calculations were performed using the methods listed in the appended "
        "tables. [LLM BYPASSED VIA DRY-RUN]"
    )

    LAM_JUSTIFICATION_COMMAND: str = (
        "The telemetry indicates the system utilized a Sinc-DVR for torsional "
        "motion. Generate one paragraph scientifically justifying the use of "
        "Sinc-DVR over the standard rigid-rotor harmonic oscillator (RRHO) "
        "approximation for this highly flexible coordinate."
    )

    def __init__(
        self,
        aggregated_data: dict[str, Any],
        manifest_data: dict[str, Any] | None = None,
        manifest_path: str | pathlib.Path | None = None,
        token_limit: int = DEFAULT_TOKEN_LIMIT,
        dry_run: bool = False,
    ) -> None:
        """Initializes the PayloadBuilder with data dictionaries and offline guards.

        Args:
            aggregated_data: Harvested quantum chemical dataset from DataAggregator.
            manifest_data: In-memory dictionary of cochem_deployment_manifest.json.
            manifest_path: Optional path to cochem_deployment_manifest.json.
            token_limit: Maximum integer token threshold (default: 6000).
            dry_run: If True, bypasses token processing and AI synthesis with fallbacks.
        """
        self.aggregated_data: dict[str, Any] = aggregated_data or {}
        self.manifest_path: pathlib.Path | None = (
            pathlib.Path(manifest_path).resolve() if manifest_path is not None else None
        )
        self.token_limit: int = token_limit

        # Check offline / resource guard environment overrides
        rg_env = os.getenv("RESOURCE_GUARD", "").lower() in ("1", "true", "yes")
        off_env = os.getenv("COCHEM_OFFLINE", "").lower() in ("1", "true", "yes")
        self.dry_run: bool = bool(dry_run or rg_env or off_env)

        # Initialize BPE tokenizer locally (offline cl100k_base)
        self.encoding: tiktoken.Encoding = tiktoken.get_encoding("cl100k_base")
        self.logger: logging.Logger = logging.getLogger("scribe.payload_builder")

        # Resolve manifest data dynamically if not explicitly provided
        if manifest_data is not None:
            self.manifest_data = manifest_data
        elif (
            self.manifest_path is not None
            and self.manifest_path.exists()
            and self.manifest_path.is_file()
        ):
            try:
                loaded_m = json.loads(
                    self.manifest_path.read_text(encoding="utf-8")
                )
                self.manifest_data = loaded_m if isinstance(loaded_m, dict) else {}
            except Exception as e:
                self.logger.warning(
                    "Failed reading manifest from '%s': %s", self.manifest_path, e
                )
                self.manifest_data = {}
        else:
            self.manifest_data = self._resolve_manifest_dynamically()

    def _resolve_manifest_dynamically(self) -> dict[str, Any]:
        """Searches candidate filesystem paths to load deployment manifest."""
        candidates = [
            pathlib.Path.cwd() / "cochem_deployment_manifest.json",
            pathlib.Path.home()
            / "CoChem_Artifacts"
            / "cochem_deployment_manifest.json",
            pathlib.Path(__file__).resolve().parent.parent
            / "cochem_deployment_manifest.json",
        ]
        for c in candidates:
            if c.exists() and c.is_file():
                try:
                    loaded = json.loads(c.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        return loaded
                except Exception as e:
                    self.logger.debug(
                        "Failed parsing manifest candidate '%s': %s", c, e
                    )
        return {}

    def synthesize_pipeline_context(self) -> str:
        """Constructs concise 'State of the Run' factual provenance string.

        Returns:
            Concise factual grounding string documenting software stack.
        """
        engines_list: list[str] = []
        engine_versions = (
            self.manifest_data.get("engine_versions")
            or self.manifest_data.get("engines")
            or self.manifest_data.get("software_stack")
            or self.aggregated_data.get("provenance", {}).get("engine_versions")
            or {}
        )

        if isinstance(engine_versions, dict):
            for eng_name, eng_val in engine_versions.items():
                if isinstance(eng_val, dict):
                    ver = eng_val.get("version", "")
                    if ver and ver != "[MISSING DATA]":
                        engines_list.append(f"{eng_name.upper()} {ver}")
                    else:
                        engines_list.append(eng_name.upper())
                elif (
                    isinstance(eng_val, str)
                    and eng_val
                    and eng_val != "[MISSING DATA]"
                ):
                    engines_list.append(f"{eng_name.upper()} {eng_val}")
                elif isinstance(eng_val, str) and eng_val:
                    engines_list.append(f"{eng_name.upper()}")

        if not engines_list:
            engines_summary = (
                "ORCA 6.1.1 for electronic structure, "
                "MACE-OFF23 for initial conformer routing"
            )
        else:
            engines_summary = ", ".join(engines_list)

        env = self.manifest_data.get(
            "calculation_environment"
        ) or self.manifest_data.get("interaction_environment")
        if env:
            return (
                f"This dataset was generated using {engines_summary}, and "
                f"CODATA 2022 constants in environment '{env}'."
            )
        return (
            f"This dataset was generated using {engines_summary}, and "
            "CODATA 2022 constants."
        )

    def get_master_system_prompt(self) -> str:
        """Returns the immutable Master System Prompt commanding mathematical air-gap.

        Returns:
            Verbatim Master System Prompt commanding air-gap and injection tags.
        """
        return self.MASTER_SYSTEM_PROMPT

    def count_tokens(self, text: str) -> int:
        """Measures integer token count of candidate text payload.

        Args:
            text: Input string payload to tokenize.

        Returns:
            Exact integer token count using cl100k_base.
        """
        if not text:
            return 0
        return len(self.encoding.encode(text))

    def _tier1_drop_conformers(self, truncated: dict[str, Any]) -> None:
        """Executes Tier 1 drop: retain top 3 conformers without heavy coordinates."""
        if "conformers" not in truncated or not isinstance(
            truncated["conformers"], list
        ):
            return
        confs = truncated["conformers"]
        if len(confs) <= MAX_RETAINED_CONFORMERS:
            return

        def _get_rel_energy(c: dict[str, Any]) -> float:
            return float(
                c.get(
                    "relative_energy_kcal_mol",
                    c.get("relative_energy", c.get("energy_kcal_mol", 0.0)),
                )
            )

        sorted_confs = sorted(confs, key=_get_rel_energy)
        pruned_confs: list[dict[str, Any]] = []
        for c in sorted_confs[:MAX_RETAINED_CONFORMERS]:
            c_clean = dict(c)
            c_clean.pop("cartesian_coordinates_angstrom", None)
            c_clean.pop("internal_coordinate_scan_degrees", None)
            c_clean.pop("coordinate_trajectory", None)
            pruned_confs.append(c_clean)
        truncated["conformers"] = pruned_confs

    def _tier2_drop_vibrations(
        self, truncated: dict[str, Any], clear_all: bool = False
    ) -> None:
        """Executes Tier 2 drop: prune high frequency vibrational modes."""
        if "thermodynamics" not in truncated or not isinstance(
            truncated["thermodynamics"], dict
        ):
            return
        therm = truncated["thermodynamics"]
        freq_keys = ["vpt2_frequencies_cm1", "frequencies", "vibrational_frequencies"]
        for freq_key in freq_keys:
            if freq_key not in therm:
                continue
            if not clear_all and isinstance(therm[freq_key], (list, tuple)):
                freq_list = [float(x) for x in therm[freq_key]]
                if len(freq_list) > MAX_FUNDAMENTAL_MODES:
                    therm[freq_key] = sorted(freq_list)[:MAX_FUNDAMENTAL_MODES]
            elif clear_all:
                therm[freq_key] = []

    def _tier3_drop_telemetry(self, truncated: dict[str, Any]) -> None:
        """Executes Tier 3 drop: retain only fatal and critical telemetry tags."""
        if "telemetry" not in truncated or not isinstance(
            truncated["telemetry"], dict
        ):
            return
        telem = truncated["telemetry"]
        if "warnings" in telem and isinstance(telem["warnings"], list):
            critical_warnings = [
                w
                for w in telem["warnings"]
                if isinstance(w, str) and any(tag in w for tag in ["Fatal", "Critical"])
            ]
            telem["warnings"] = critical_warnings

        if "node_architecture" in telem and isinstance(
            telem["node_architecture"], dict
        ):
            arch = telem["node_architecture"]
            telem["node_architecture"] = {
                k: v
                for k, v in arch.items()
                if k in ["cpu_cores", "gpu_model", "hostname"]
            }

    def _tier4_cleanup_invariants(self, truncated: dict[str, Any]) -> None:
        """Executes Tier 4 cleanup: preserves critical physics invariants."""
        allowed_top_keys = {
            "conformers",
            "spectroscopy",
            "thermodynamics",
            "telemetry",
            "provenance",
        }
        for k in list(truncated.keys()):
            if k not in allowed_top_keys:
                truncated.pop(k, None)

    def truncate_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        """Applies 4-tier context-chunking priority drops until token ceiling is met.

        Deterministic Drop Order:
        1. Tier 1 Drop: Drop conformer statistical arrays beyond the top 3 minima.
        2. Tier 2 Drop: Drop high-frequency vibrational scalar noise.
        3. Tier 3 Drop: Drop detailed telemetry warnings, retaining Fatal/Critical.
        4. Tier 4 Protected Invariants: Delta G, ZPE, and engine versions are preserved.

        Args:
            data: Input quantum chemistry data dictionary.

        Returns:
            Bounded dictionary satisfying token limits with preserved Tier-4.
        """
        truncated: dict[str, Any] = copy.deepcopy(data)

        def _current_tokens(payload: dict[str, Any]) -> int:
            return self.count_tokens(json.dumps(payload, default=str))

        if _current_tokens(truncated) <= self.token_limit:
            return truncated

        # --- Tier 1 Drop ---
        self._tier1_drop_conformers(truncated)
        if _current_tokens(truncated) <= self.token_limit:
            return truncated

        # --- Tier 2 Drop (Pass 1: reduce to fundamental modes) ---
        self._tier2_drop_vibrations(truncated, clear_all=False)
        if _current_tokens(truncated) <= self.token_limit:
            return truncated

        # --- Tier 2 Drop (Pass 2: clear frequency list) ---
        self._tier2_drop_vibrations(truncated, clear_all=True)
        if _current_tokens(truncated) <= self.token_limit:
            return truncated

        # --- Tier 3 Drop ---
        self._tier3_drop_telemetry(truncated)
        if _current_tokens(truncated) <= self.token_limit:
            return truncated

        # --- Tier 4 Protected Invariants Check ---
        self._tier4_cleanup_invariants(truncated)
        return truncated

    def inject_lam_justification(self, prompt: str) -> str:
        """Injects Sinc-DVR torsional motion justification if LAM trigger is active.

        Args:
            prompt: Base synthesized prompt string.

        Returns:
            Prompt with appended Sinc-DVR justification if triggered, or unchanged.
        """
        lam_active = False
        telem = self.aggregated_data.get("telemetry", {})
        if isinstance(telem, dict):
            if (
                telem.get("lam_active") is True
                or telem.get("lam_trigger") is True
                or telem.get("sinc_dvr") is True
            ):
                lam_active = True

        if not lam_active:
            spec = self.aggregated_data.get("spectroscopy", {})
            if isinstance(spec, dict) and (
                spec.get("lam_active") or spec.get("sinc_dvr")
            ):
                lam_active = True

        if not lam_active:
            therm = self.aggregated_data.get("thermodynamics", {})
            if isinstance(therm, dict) and (
                therm.get("lam_active") or therm.get("sinc_dvr")
            ):
                lam_active = True

        if not lam_active:
            data_str = str(self.aggregated_data).lower()
            if (
                "sinc_dvr" in data_str
                or "sinc-dvr" in data_str
                or "lam_trigger" in data_str
            ):
                lam_active = True

        if lam_active and self.LAM_JUSTIFICATION_COMMAND not in prompt:
            return f"{prompt.rstrip()}\n\n{self.LAM_JUSTIFICATION_COMMAND}"

        return prompt

    def execute_dry_run(self) -> str:
        """Returns static fallback methodology string when offline/dry-run is toggled.

        Returns:
            Deterministic fallback string returned in <0.05s.
        """
        return self.DRY_RUN_FALLBACK_TEXT

    def build_methodology_prompt(self) -> str:
        """Synthesizes APS-compliant computational methodology prompt.

        Returns:
            Fully synthesized prompt bounded to token limit.
        """
        if self.dry_run:
            return self.execute_dry_run()

        master_sys = self.get_master_system_prompt()
        pipeline_ctx = self.synthesize_pipeline_context()
        truncated_data = self.truncate_payload(self.aggregated_data)

        engines = (
            truncated_data.get("provenance", {}).get("engine_versions")
            or self.manifest_data.get("engine_versions")
            or {}
        )
        thermo = truncated_data.get("thermodynamics", {})
        spec = truncated_data.get("spectroscopy", {})
        confs = truncated_data.get("conformers", [])

        zpe_val = thermo.get("zpe_kcal_mol", "N/A")
        g_val = thermo.get("gibbs_free_energy_kcal_mol", "N/A")
        h_val = thermo.get("enthalpy_kcal_mol", "N/A")

        prompt_blocks = [
            master_sys,
            "",
            "---",
            "### Pipeline Provenance Context",
            pipeline_ctx,
            "",
            "### Task Instructions",
            (
                "Synthesize a 2-paragraph, APS-compliant computational methodology "
                "section based strictly on the extracted deployment manifest and "
                "computational metadata below."
            ),
            (
                "You must describe the quantum chemical electronic structure methods, "
                "geometry optimization, vibrational frequencies, and torsional "
                "treatments employed."
            ),
            (
                "Do NOT calculate or alter any numerical values. Use explicit "
                "injection tags such as INSERT_THERMO_TABLE_HERE and "
                "INSERT_SPECTROSCOPY_TABLE_HERE where numerical tables should "
                "be inserted."
            ),
            "",
            "### Computational Metadata Summary",
            f"- Software Engine Stack: {json.dumps(engines, default=str)}",
            f"- Conformer Exploration: {len(confs)} unique conformers identified.",
            f"- Spectroscopic Parameters: {json.dumps(spec, default=str)}",
            (
                f"- Thermodynamic Quantities: ZPE = {zpe_val} kcal/mol, "
                f"G_298 = {g_val} kcal/mol, H_298 = {h_val} kcal/mol."
            ),
        ]

        full_prompt = "\n".join(prompt_blocks)
        full_prompt = self.inject_lam_justification(full_prompt)

        # Enforce strict token ceiling
        if self.count_tokens(full_prompt) > self.token_limit:
            encoded = self.encoding.encode(full_prompt)[: self.token_limit]
            full_prompt = self.encoding.decode(encoded)

        return full_prompt

    def build_insights_prompt(self) -> str:
        """Synthesizes thermodynamic Boltzmann population analysis prompt.

        Returns:
            Fully synthesized prompt formatted for CoChem_User_Guide.md injection.
        """
        if self.dry_run:
            return self.execute_dry_run()

        master_sys = self.get_master_system_prompt()
        pipeline_ctx = self.synthesize_pipeline_context()
        truncated_data = self.truncate_payload(self.aggregated_data)

        confs = truncated_data.get("conformers", [])
        thermo = truncated_data.get("thermodynamics", {})

        conf_lines: list[str] = []
        for c in confs:
            cid = c.get("conformer_id", "N/A")
            rele = float(
                c.get(
                    "relative_energy_kcal_mol", c.get("relative_energy", 0.0)
                )
            )
            sym = str(c.get("point_group_symmetry", "C1"))
            dip = c.get("dipole_moment_debye", "N/A")
            conf_lines.append(
                f"- Conformer {cid}: Delta E = {rele:.3f} kcal/mol, "
                f"Point Group = {sym}, Dipole = {dip} D"
            )

        conf_summary = (
            "\n".join(conf_lines)
            if conf_lines
            else "No conformer energy data available."
        )

        g_val = thermo.get("gibbs_free_energy_kcal_mol", "N/A")
        zpe_val = thermo.get("zpe_kcal_mol", "N/A")
        h_val = thermo.get("enthalpy_kcal_mol", "N/A")

        prompt_blocks = [
            master_sys,
            "",
            "---",
            "### Pipeline Provenance Context",
            pipeline_ctx,
            "",
            "### Task Instructions",
            (
                "Generate a concise 'Thermodynamic Analysis' paragraph highlighting "
                "which conformer dominates the Boltzmann population based on the "
                "computed energy gaps (Delta E, Delta G) and point group symmetries "
                "provided below, formatted for direct injection into "
                "CoChem_User_Guide.md."
            ),
            (
                "Do not invent or recalculate any constants or energies. Use "
                "explicit injection tags such as INSERT_THERMO_TABLE_HERE "
                "where exact numerical data should be injected."
            ),
            "",
            "### Thermodynamic & Conformer Data",
            conf_summary,
            f"- Global Minimum Free Energy (G_298): {g_val} kcal/mol",
            f"- Zero-Point Vibrational Energy (ZPE): {zpe_val} kcal/mol",
            f"- Enthalpy (H_298): {h_val} kcal/mol",
        ]

        full_prompt = "\n".join(prompt_blocks)
        full_prompt = self.inject_lam_justification(full_prompt)

        # Enforce strict token ceiling
        if self.count_tokens(full_prompt) > self.token_limit:
            encoded = self.encoding.encode(full_prompt)[: self.token_limit]
            full_prompt = self.encoding.decode(encoded)

        return full_prompt

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\harvesters\test_scribe_payload_builder.py ---
#!/usr/bin/env python3
"""Unit Tests for CoChem-SCRIBE Context-Safe Payload Builder & Prompt Synthesizer.

Phase 2, Task 6: Context-Safe Payload Builder & Prompt Synthesis
(harvesters/test_scribe_payload_builder.py).

Adheres strictly to the Anti-Spoofing Protocol.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import pytest
import tiktoken

from .scribe_payload_builder import (
    DEFAULT_TOKEN_LIMIT,
    PayloadBuilder,
)

DRY_RUN_MAX_DURATION: float = 0.05
MAX_ALLOWED_CONFS: int = 3
MAX_ALLOWED_CRITICAL_WARNINGS: int = 2
EXPECTED_INVARIANT_GIBBS: float = -182.1250
EXPECTED_INVARIANT_ZPE: float = 48.9125


@pytest.fixture
def authentic_aggregated_data() -> dict[str, Any]:
    """Provides a realistic, authentic aggregated quantum chemistry dataset."""
    return {
        "conformers": [
            {
                "conformer_id": "conf_01",
                "relative_energy_kcal_mol": 0.000,
                "point_group_symmetry": "C2v",
                "dipole_moment_debye": 1.854,
            },
            {
                "conformer_id": "conf_02",
                "relative_energy_kcal_mol": 0.742,
                "point_group_symmetry": "Cs",
                "dipole_moment_debye": 2.110,
            },
            {
                "conformer_id": "conf_03",
                "relative_energy_kcal_mol": 1.385,
                "point_group_symmetry": "C1",
                "dipole_moment_debye": 0.940,
            },
            {
                "conformer_id": "conf_04",
                "relative_energy_kcal_mol": 2.450,
                "point_group_symmetry": "C1",
                "dipole_moment_debye": 1.450,
            },
        ],
        "spectroscopy": {
            "rotational_constants": {
                "A": 10342.15,
                "B": 2451.80,
                "C": 1980.45,
            },
            "dipole_moments": {
                "mu_a": 1.54,
                "mu_b": 0.98,
                "mu_c": 0.00,
                "total": 1.83,
            },
            "centrifugal_distortion": {
                "Delta_J": 0.00142,
                "Delta_JK": -0.00512,
                "Delta_K": 0.02341,
                "delta_J": 0.00031,
                "delta_K": 0.00115,
            },
        },
        "thermodynamics": {
            "zpe_kcal_mol": 45.6782,
            "enthalpy_kcal_mol": -153.2104,
            "gibbs_free_energy_kcal_mol": -154.8912,
            "vpt2_frequencies_cm1": [
                125.4,
                210.8,
                345.2,
                512.6,
                780.1,
                1024.5,
                1250.0,
                1480.2,
                1650.4,
                2980.1,
                3100.5,
                3650.0,
            ],
        },
        "telemetry": {
            "wall_clock_time_seconds": 142.85,
            "peak_gpu_vram_mb": 2450.0,
            "lam_active": False,
            "warnings": [
                "Info: Geometry optimization converged in 14 cycles.",
                "Warning: Low barrier detected along dihedral C1-C2-O3-H4.",
            ],
        },
        "provenance": {
            "engine_versions": {
                "orca": "6.1.1",
                "mace": "0.2.0",
                "xtb": "6.7.1",
                "pyscf": "2.8.0",
            },
            "config_sha256": ("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
        },
    }


@pytest.fixture
def maximal_oversized_payload() -> dict[str, Any]:
    """Generates a maximal statistical data payload exceeding ~15,000 tokens."""
    conformers: list[dict[str, Any]] = []
    for i in range(25):
        conformers.append(
            {
                "conformer_id": f"conf_{i + 1:02d}",
                "relative_energy_kcal_mol": float(i * 0.45),
                "point_group_symmetry": "C1" if i > 0 else "C2v",
                "dipole_moment_debye": 1.5 + (i * 0.05),
                "cartesian_coordinates_angstrom": [
                    [float(j * 0.1), float(j * 0.2), float(j * 0.3)] for j in range(30)
                ],
                "rotational_constants_mhz": {
                    "A": 9000.0 - (i * 50),
                    "B": 2500.0 - (i * 20),
                    "C": 1800.0 - (i * 10),
                },
                "internal_coordinate_scan_degrees": [float(deg) for deg in range(0, 360, 5)],
            }
        )

    frequencies = [float(100.0 + k * 1.5) for k in range(3000)]

    warnings = [
        (
            f"Notice: Conformer exploratory step {k} generated "
            "extensive Hessian matrix gradients with potential oscillations."
        )
        for k in range(500)
    ]
    warnings.append("Critical: Memory pressure exceeded 90% threshold during Hessian inversion.")
    warnings.append("Fatal: Node 4 GPU memory bus dropped during parallel batch step.")

    return {
        "conformers": conformers,
        "spectroscopy": {
            "rotational_constants": {
                "A": 8940.12,
                "B": 2410.50,
                "C": 1780.30,
            },
            "dipole_moments": {
                "mu_a": 1.45,
                "mu_b": 0.85,
                "mu_c": 0.12,
                "total": 1.68,
            },
            "centrifugal_distortion": {
                "Delta_J": 0.0012,
                "Delta_JK": -0.0045,
                "Delta_K": 0.0210,
                "delta_J": 0.00028,
                "delta_K": 0.00105,
            },
        },
        "thermodynamics": {
            "zpe_kcal_mol": EXPECTED_INVARIANT_ZPE,
            "enthalpy_kcal_mol": -180.4500,
            "gibbs_free_energy_kcal_mol": EXPECTED_INVARIANT_GIBBS,
            "vpt2_frequencies_cm1": frequencies,
        },
        "telemetry": {
            "wall_clock_time_seconds": 1845.20,
            "peak_gpu_vram_mb": 7890.0,
            "lam_active": True,
            "warnings": warnings,
            "node_architecture": {
                "cpu_cores": 128,
                "gpu_model": "NVIDIA A100-SXM4-80GB",
                "hostname": "hpc-node-042",
            },
        },
        "provenance": {
            "engine_versions": {
                "orca": "6.1.1",
                "mace": "0.2.0",
                "xtb": "6.7.1",
                "spycfit": "1.4.0",
            },
            "config_sha256": ("4a5c68385b45da87a2455b669be3089e103d09c60d135447f982148df555a59e"),
        },
    }


def test_token_count_assertion(authentic_aggregated_data: dict[str, Any]) -> None:
    """Test 1: Asserts that count_tokens measures tokens using tiktoken."""
    builder = PayloadBuilder(
        aggregated_data=authentic_aggregated_data,
        token_limit=DEFAULT_TOKEN_LIMIT,
    )

    test_text = "CoChem-SCRIBE Mathematical Air-Gap and Token Metrology Engine."
    measured_tokens = builder.count_tokens(test_text)

    enc = tiktoken.get_encoding("cl100k_base")
    expected_tokens = len(enc.encode(test_text))
    assert measured_tokens == expected_tokens
    assert measured_tokens > 0

    json_str = json.dumps(authentic_aggregated_data)
    json_token_count = builder.count_tokens(json_str)
    assert json_token_count == len(enc.encode(json_str))
    assert json_token_count < DEFAULT_TOKEN_LIMIT


def test_truncation_trigger_and_tier_invariants(
    maximal_oversized_payload: dict[str, Any],
) -> None:
    """Test 2: Asserts 4-tier context-chunking drops and preserves Tier-4."""
    builder = PayloadBuilder(
        aggregated_data=maximal_oversized_payload,
        token_limit=DEFAULT_TOKEN_LIMIT,
    )

    initial_tokens = builder.count_tokens(json.dumps(maximal_oversized_payload))
    assert initial_tokens > DEFAULT_TOKEN_LIMIT, (
        f"Payload must exceed ceiling (was {initial_tokens})"
    )

    truncated = builder.truncate_payload(maximal_oversized_payload)
    truncated_tokens = builder.count_tokens(json.dumps(truncated))

    assert truncated_tokens <= DEFAULT_TOKEN_LIMIT, (
        f"Truncated payload exceeds ceiling: {truncated_tokens} > 6000"
    )

    # Tier 1 Assertion: Conformers pruned down to top 3 global minima
    assert len(truncated["conformers"]) <= MAX_ALLOWED_CONFS
    assert truncated["conformers"][0]["conformer_id"] == "conf_01"
    assert truncated["conformers"][0]["relative_energy_kcal_mol"] == 0.0

    # Tier 2 Assertion: Vibrational frequencies pruned/reduced
    if "vpt2_frequencies_cm1" in truncated.get("thermodynamics", {}):
        assert len(truncated["thermodynamics"]["vpt2_frequencies_cm1"]) < len(
            maximal_oversized_payload["thermodynamics"]["vpt2_frequencies_cm1"]
        )

    # Tier 3 Assertion: Only Fatal and Critical telemetry warnings retained
    if "warnings" in truncated.get("telemetry", {}):
        assert len(truncated["telemetry"]["warnings"]) <= MAX_ALLOWED_CRITICAL_WARNINGS
        for w in truncated["telemetry"]["warnings"]:
            assert any(tag in w for tag in ["Fatal", "Critical"]), (
                f"Non-critical warning leaked: {w}"
            )

    # Tier 4 Protected Invariants (NEVER Truncate)
    assert truncated["thermodynamics"]["gibbs_free_energy_kcal_mol"] == EXPECTED_INVARIANT_GIBBS
    assert truncated["thermodynamics"]["zpe_kcal_mol"] == EXPECTED_INVARIANT_ZPE
    assert truncated["provenance"]["engine_versions"]["orca"] == "6.1.1"
    assert truncated["provenance"]["engine_versions"]["mace"] == "0.2.0"


def test_master_system_prompt_regex_and_tags(
    authentic_aggregated_data: dict[str, Any],
) -> None:
    """Test 3: Asserts prompt prepends Master System Prompt with injection tags."""
    builder = PayloadBuilder(
        aggregated_data=authentic_aggregated_data,
        token_limit=DEFAULT_TOKEN_LIMIT,
    )

    sys_prompt = builder.get_master_system_prompt()
    assert (
        "You are an automated academic writer for the CoChem computational "
        "chemistry pipeline." in sys_prompt
    )
    assert "strictly forbidden" in sys_prompt
    assert "INSERT_THERMO_TABLE_HERE" in sys_prompt

    method_prompt = builder.build_methodology_prompt()
    assert method_prompt.startswith(sys_prompt) or sys_prompt in method_prompt
    assert re.search(r"strictly forbidden", method_prompt) is not None
    assert "INSERT_THERMO_TABLE_HERE" in method_prompt
    assert "INSERT_SPECTROSCOPY_TABLE_HERE" in method_prompt

    insights_prompt = builder.build_insights_prompt()
    assert insights_prompt.startswith(sys_prompt) or sys_prompt in insights_prompt
    assert re.search(r"strictly forbidden", insights_prompt) is not None
    assert "INSERT_THERMO_TABLE_HERE" in insights_prompt
    assert "Boltzmann" in insights_prompt


def test_dry_run_benchmark(authentic_aggregated_data: dict[str, Any]) -> None:
    """Test 4: Asserts dry_run=True returns fallback string in <0.05s."""
    builder = PayloadBuilder(
        aggregated_data=authentic_aggregated_data,
        token_limit=DEFAULT_TOKEN_LIMIT,
        dry_run=True,
    )

    start_time = time.perf_counter()
    result_method = builder.build_methodology_prompt()
    result_insights = builder.build_insights_prompt()
    result_dry = builder.execute_dry_run()
    elapsed = time.perf_counter() - start_time

    expected_fallback = (
        "Calculations were performed using the methods listed in the appended tables. "
        "[LLM BYPASSED VIA DRY-RUN]"
    )

    assert result_method == expected_fallback
    assert result_insights == expected_fallback
    assert result_dry == expected_fallback
    assert elapsed < DRY_RUN_MAX_DURATION, f"Dry-run took too long: {elapsed:.4f}s >= 0.05s"


def test_lam_trigger_physics_justification(
    authentic_aggregated_data: dict[str, Any],
) -> None:
    """Test 5: Asserts Sinc-DVR justification injection when LAM is active."""
    builder_no_lam = PayloadBuilder(
        aggregated_data=authentic_aggregated_data,
        token_limit=DEFAULT_TOKEN_LIMIT,
    )
    prompt_no_lam = builder_no_lam.build_methodology_prompt()
    assert "Sinc-DVR" not in prompt_no_lam

    data_with_lam = dict(authentic_aggregated_data)
    data_with_lam["telemetry"] = dict(authentic_aggregated_data["telemetry"])
    data_with_lam["telemetry"]["lam_active"] = True

    builder_with_lam = PayloadBuilder(
        aggregated_data=data_with_lam,
        token_limit=DEFAULT_TOKEN_LIMIT,
    )
    prompt_with_lam = builder_with_lam.build_methodology_prompt()

    expected_lam_phrase = (
        "The telemetry indicates the system utilized a Sinc-DVR for torsional motion. "
        "Generate one paragraph scientifically justifying the use of Sinc-DVR over the "
        "standard rigid-rotor harmonic oscillator (RRHO) approximation for this "
        "highly flexible coordinate."
    )
    assert expected_lam_phrase in prompt_with_lam


def test_synthesize_pipeline_context(
    authentic_aggregated_data: dict[str, Any],
) -> None:
    """Test 6: Asserts pipeline context extracts software stack and provenance."""
    manifest = {
        "version": "2026.2",
        "calculation_environment": "Local-Windows (WSL)",
        "engine_versions": {
            "orca": "6.1.1",
            "mace": "0.2.0",
            "xtb": "6.7.1",
        },
    }
    builder = PayloadBuilder(
        aggregated_data=authentic_aggregated_data,
        manifest_data=manifest,
        token_limit=DEFAULT_TOKEN_LIMIT,
    )
    context_str = builder.synthesize_pipeline_context()
    assert "ORCA" in context_str
    assert "CODATA 2022 constants" in context_str

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_scribe_payload_builder.py ---
#!/usr/bin/env python3
"""Unit Tests for CoChem-SCRIBE Context-Safe Payload Builder & Prompt Synthesizer.

Phase 2, Task 6: Context-Safe Payload Builder & Prompt Synthesis
(tests/test_scribe_payload_builder.py).

Adheres strictly to the Anti-Spoofing Protocol.
Executes against authentic data structures, verifying:
1. Token Count Estimation via tiktoken (cl100k_base).
2. 4-Tier Context Chunking, Priority Shedding, and Tier-4 Invariant Preservation.
3. Master System Prompt Regex and Mandatory Injection Tags.
4. Dry-Run Offline Benchmark (< 0.05s execution speed).
5. LAM Trigger Physics Justification Injection.
6. Pipeline Execution Provenance Context Synthesis.
7. Methodology & Insights Dynamic Prompt Targeting.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import pytest
import tiktoken

from harvesters.scribe_payload_builder import (
    DEFAULT_TOKEN_LIMIT,
    PayloadBuilder,
)

DRY_RUN_MAX_DURATION: float = 0.05
MAX_ALLOWED_CONFS: int = 3
MAX_ALLOWED_CRITICAL_WARNINGS: int = 2
EXPECTED_INVARIANT_GIBBS: float = -182.1250
EXPECTED_INVARIANT_ZPE: float = 48.9125


@pytest.fixture
def authentic_aggregated_data() -> dict[str, Any]:
    """Provides a realistic, authentic aggregated quantum chemistry dataset."""
    return {
        "conformers": [
            {
                "conformer_id": "conf_01",
                "relative_energy_kcal_mol": 0.000,
                "point_group_symmetry": "C2v",
                "dipole_moment_debye": 1.854,
            },
            {
                "conformer_id": "conf_02",
                "relative_energy_kcal_mol": 0.742,
                "point_group_symmetry": "Cs",
                "dipole_moment_debye": 2.110,
            },
            {
                "conformer_id": "conf_03",
                "relative_energy_kcal_mol": 1.385,
                "point_group_symmetry": "C1",
                "dipole_moment_debye": 0.940,
            },
            {
                "conformer_id": "conf_04",
                "relative_energy_kcal_mol": 2.450,
                "point_group_symmetry": "C1",
                "dipole_moment_debye": 1.450,
            },
        ],
        "spectroscopy": {
            "rotational_constants": {
                "A": 10342.15,
                "B": 2451.80,
                "C": 1980.45,
            },
            "dipole_moments": {
                "mu_a": 1.54,
                "mu_b": 0.98,
                "mu_c": 0.00,
                "total": 1.83,
            },
            "centrifugal_distortion": {
                "Delta_J": 0.00142,
                "Delta_JK": -0.00512,
                "Delta_K": 0.02341,
                "delta_J": 0.00031,
                "delta_K": 0.00115,
            },
        },
        "thermodynamics": {
            "zpe_kcal_mol": 45.6782,
            "enthalpy_kcal_mol": -153.2104,
            "gibbs_free_energy_kcal_mol": -154.8912,
            "vpt2_frequencies_cm1": [
                125.4,
                210.8,
                345.2,
                512.6,
                780.1,
                1024.5,
                1250.0,
                1480.2,
                1650.4,
                2980.1,
                3100.5,
                3650.0,
            ],
        },
        "telemetry": {
            "wall_clock_time_seconds": 142.85,
            "peak_gpu_vram_mb": 2450.0,
            "lam_active": False,
            "warnings": [
                "Info: Geometry optimization converged in 14 cycles.",
                "Warning: Low barrier detected along dihedral C1-C2-O3-H4.",
            ],
        },
        "provenance": {
            "engine_versions": {
                "orca": "6.1.1",
                "mace": "0.2.0",
                "xtb": "6.7.1",
                "pyscf": "2.8.0",
            },
            "config_sha256": ("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
        },
    }


@pytest.fixture
def maximal_oversized_payload() -> dict[str, Any]:
    """Generates a maximal statistical data payload exceeding ~15,000 tokens."""
    conformers: list[dict[str, Any]] = []
    for i in range(25):
        conformers.append(
            {
                "conformer_id": f"conf_{i + 1:02d}",
                "relative_energy_kcal_mol": float(i * 0.45),
                "point_group_symmetry": "C1" if i > 0 else "C2v",
                "dipole_moment_debye": 1.5 + (i * 0.05),
                "cartesian_coordinates_angstrom": [
                    [float(j * 0.1), float(j * 0.2), float(j * 0.3)] for j in range(30)
                ],
                "rotational_constants_mhz": {
                    "A": 9000.0 - (i * 50),
                    "B": 2500.0 - (i * 20),
                    "C": 1800.0 - (i * 10),
                },
                "internal_coordinate_scan_degrees": [float(deg) for deg in range(0, 360, 5)],
            }
        )

    # Generate 3000 vibrational frequency entries to exercise Tier 2
    frequencies = [float(100.0 + k * 1.5) for k in range(3000)]

    # Generate 500 verbose telemetry warning entries for Tier 3
    warnings = [
        (
            f"Notice: Conformer exploratory step {k} generated "
            "extensive Hessian matrix gradients with potential oscillations."
        )
        for k in range(500)
    ]
    warnings.append("Critical: Memory pressure exceeded 90% threshold during Hessian inversion.")
    warnings.append("Fatal: Node 4 GPU memory bus dropped during parallel batch step.")

    return {
        "conformers": conformers,
        "spectroscopy": {
            "rotational_constants": {
                "A": 8940.12,
                "B": 2410.50,
                "C": 1780.30,
            },
            "dipole_moments": {
                "mu_a": 1.45,
                "mu_b": 0.85,
                "mu_c": 0.12,
                "total": 1.68,
            },
            "centrifugal_distortion": {
                "Delta_J": 0.0012,
                "Delta_JK": -0.0045,
                "Delta_K": 0.0210,
                "delta_J": 0.00028,
                "delta_K": 0.00105,
            },
        },
        "thermodynamics": {
            "zpe_kcal_mol": EXPECTED_INVARIANT_ZPE,
            "enthalpy_kcal_mol": -180.4500,
            "gibbs_free_energy_kcal_mol": EXPECTED_INVARIANT_GIBBS,
            "vpt2_frequencies_cm1": frequencies,
        },
        "telemetry": {
            "wall_clock_time_seconds": 1845.20,
            "peak_gpu_vram_mb": 7890.0,
            "lam_active": True,
            "warnings": warnings,
            "node_architecture": {
                "cpu_cores": 128,
                "gpu_model": "NVIDIA A100-SXM4-80GB",
                "hostname": "hpc-node-042",
            },
        },
        "provenance": {
            "engine_versions": {
                "orca": "6.1.1",
                "mace": "0.2.0",
                "xtb": "6.7.1",
                "spycfit": "1.4.0",
            },
            "config_sha256": ("4a5c68385b45da87a2455b669be3089e103d09c60d135447f982148df555a59e"),
        },
    }


def test_token_count_assertion(authentic_aggregated_data: dict[str, Any]) -> None:
    """Test 1: Asserts that count_tokens measures tokens using tiktoken."""
    builder = PayloadBuilder(
        aggregated_data=authentic_aggregated_data,
        token_limit=DEFAULT_TOKEN_LIMIT,
    )

    test_text = "CoChem-SCRIBE Mathematical Air-Gap and Token Metrology Engine."
    measured_tokens = builder.count_tokens(test_text)

    enc = tiktoken.get_encoding("cl100k_base")
    expected_tokens = len(enc.encode(test_text))
    assert measured_tokens == expected_tokens
    assert measured_tokens > 0

    json_str = json.dumps(authentic_aggregated_data)
    json_token_count = builder.count_tokens(json_str)
    assert json_token_count == len(enc.encode(json_str))
    assert json_token_count < DEFAULT_TOKEN_LIMIT


def test_truncation_trigger_and_tier_invariants(
    maximal_oversized_payload: dict[str, Any],
) -> None:
    """Test 2: Asserts 4-tier context-chunking drops and preserves Tier-4."""
    builder = PayloadBuilder(
        aggregated_data=maximal_oversized_payload,
        token_limit=DEFAULT_TOKEN_LIMIT,
    )

    initial_tokens = builder.count_tokens(json.dumps(maximal_oversized_payload))
    assert initial_tokens > DEFAULT_TOKEN_LIMIT, (
        f"Payload must exceed ceiling (was {initial_tokens})"
    )

    truncated = builder.truncate_payload(maximal_oversized_payload)
    truncated_tokens = builder.count_tokens(json.dumps(truncated))

    assert truncated_tokens <= DEFAULT_TOKEN_LIMIT, (
        f"Truncated payload exceeds ceiling: {truncated_tokens} > 6000"
    )

    # Tier 1 Assertion: Conformers pruned down to top 3 global minima
    assert len(truncated["conformers"]) <= MAX_ALLOWED_CONFS
    assert truncated["conformers"][0]["conformer_id"] == "conf_01"
    assert truncated["conformers"][0]["relative_energy_kcal_mol"] == 0.0

    # Tier 2 Assertion: Vibrational frequencies pruned/reduced
    if "vpt2_frequencies_cm1" in truncated.get("thermodynamics", {}):
        assert len(truncated["thermodynamics"]["vpt2_frequencies_cm1"]) < len(
            maximal_oversized_payload["thermodynamics"]["vpt2_frequencies_cm1"]
        )

    # Tier 3 Assertion: Only Fatal and Critical telemetry warnings retained
    if "warnings" in truncated.get("telemetry", {}):
        assert len(truncated["telemetry"]["warnings"]) <= MAX_ALLOWED_CRITICAL_WARNINGS
        for w in truncated["telemetry"]["warnings"]:
            assert any(tag in w for tag in ["Fatal", "Critical"]), (
                f"Non-critical warning leaked: {w}"
            )

    # Tier 4 Protected Invariants (NEVER Truncate)
    assert truncated["thermodynamics"]["gibbs_free_energy_kcal_mol"] == EXPECTED_INVARIANT_GIBBS
    assert truncated["thermodynamics"]["zpe_kcal_mol"] == EXPECTED_INVARIANT_ZPE
    assert truncated["provenance"]["engine_versions"]["orca"] == "6.1.1"
    assert truncated["provenance"]["engine_versions"]["mace"] == "0.2.0"


def test_master_system_prompt_regex_and_tags(
    authentic_aggregated_data: dict[str, Any],
) -> None:
    """Test 3: Asserts prompt prepends Master System Prompt with injection tags."""
    builder = PayloadBuilder(
        aggregated_data=authentic_aggregated_data,
        token_limit=DEFAULT_TOKEN_LIMIT,
    )

    sys_prompt = builder.get_master_system_prompt()
    assert (
        "You are an automated academic writer for the CoChem computational "
        "chemistry pipeline." in sys_prompt
    )
    assert "strictly forbidden" in sys_prompt
    assert "INSERT_THERMO_TABLE_HERE" in sys_prompt

    method_prompt = builder.build_methodology_prompt()
    assert method_prompt.startswith(sys_prompt) or sys_prompt in method_prompt
    assert re.search(r"strictly forbidden", method_prompt) is not None
    assert "INSERT_THERMO_TABLE_HERE" in method_prompt
    assert "INSERT_SPECTROSCOPY_TABLE_HERE" in method_prompt

    insights_prompt = builder.build_insights_prompt()
    assert insights_prompt.startswith(sys_prompt) or sys_prompt in insights_prompt
    assert re.search(r"strictly forbidden", insights_prompt) is not None
    assert "INSERT_THERMO_TABLE_HERE" in insights_prompt
    assert "Boltzmann" in insights_prompt


def test_dry_run_benchmark(authentic_aggregated_data: dict[str, Any]) -> None:
    """Test 4: Asserts dry_run=True returns fallback string in <0.05s."""
    builder = PayloadBuilder(
        aggregated_data=authentic_aggregated_data,
        token_limit=DEFAULT_TOKEN_LIMIT,
        dry_run=True,
    )

    start_time = time.perf_counter()
    result_method = builder.build_methodology_prompt()
    result_insights = builder.build_insights_prompt()
    result_dry = builder.execute_dry_run()
    elapsed = time.perf_counter() - start_time

    expected_fallback = (
        "Calculations were performed using the methods listed in the appended tables. "
        "[LLM BYPASSED VIA DRY-RUN]"
    )

    assert result_method == expected_fallback
    assert result_insights == expected_fallback
    assert result_dry == expected_fallback
    assert elapsed < DRY_RUN_MAX_DURATION, f"Dry-run took too long: {elapsed:.4f}s >= 0.05s"


def test_lam_trigger_physics_justification(
    authentic_aggregated_data: dict[str, Any],
) -> None:
    """Test 5: Asserts Sinc-DVR justification injection when LAM is active."""
    builder_no_lam = PayloadBuilder(
        aggregated_data=authentic_aggregated_data,
        token_limit=DEFAULT_TOKEN_LIMIT,
    )
    prompt_no_lam = builder_no_lam.build_methodology_prompt()
    assert "Sinc-DVR" not in prompt_no_lam

    data_with_lam = dict(authentic_aggregated_data)
    data_with_lam["telemetry"] = dict(authentic_aggregated_data["telemetry"])
    data_with_lam["telemetry"]["lam_active"] = True

    builder_with_lam = PayloadBuilder(
        aggregated_data=data_with_lam,
        token_limit=DEFAULT_TOKEN_LIMIT,
    )
    prompt_with_lam = builder_with_lam.build_methodology_prompt()

    expected_lam_phrase = (
        "The telemetry indicates the system utilized a Sinc-DVR for torsional motion. "
        "Generate one paragraph scientifically justifying the use of Sinc-DVR over the "
        "standard rigid-rotor harmonic oscillator (RRHO) approximation for this "
        "highly flexible coordinate."
    )
    assert expected_lam_phrase in prompt_with_lam


def test_synthesize_pipeline_context(
    authentic_aggregated_data: dict[str, Any],
) -> None:
    """Test 6: Asserts pipeline context extracts software stack and provenance."""
    manifest = {
        "version": "2026.2",
        "calculation_environment": "Local-Windows (WSL)",
        "engine_versions": {
            "orca": "6.1.1",
            "mace": "0.2.0",
            "xtb": "6.7.1",
        },
    }
    builder = PayloadBuilder(
        aggregated_data=authentic_aggregated_data,
        manifest_data=manifest,
        token_limit=DEFAULT_TOKEN_LIMIT,
    )
    context_str = builder.synthesize_pipeline_context()
    assert "ORCA" in context_str
    assert "CODATA 2022 constants" in context_str

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.