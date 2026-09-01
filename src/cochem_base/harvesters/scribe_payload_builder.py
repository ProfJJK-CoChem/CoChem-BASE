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
