#!/usr/bin/env python3
"""
CoChem-SCRIBE Stage 6.2 Inference Engine & Hallucination Traps.

Governed strictly by Phase 3, Task 8 of the CoChem-SCRIBE Software Requirements
Specification (SRS), adhering to Method Matrix v4, the Anti-Spoofing Protocol
(LESSON-2026-AUDIT-007), FAIR Data Principles, and the Air-Gap Compliance Directive.

Defines the ScribeInferenceManager orchestrator which manages LLM inference execution,
enforces Pydantic structured output schemas, executes regex sweeping to trap and invalidate
hallucinated physical constants and coordinates, preserves whitelisted Jinja2 and LaTeX tags,
enforces 120s asynchronous watchdog timeouts, performs markdown syntax auto-repairs,
and manages a 3-strike retry fallback loop with structured factual omission notices.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from datetime import datetime, timezone
import json
import logging
import os
import pathlib
import platform
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, Union

_MODULE_DIR = pathlib.Path(__file__).resolve().parent
_REPO_ROOT = _MODULE_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pydantic import BaseModel, Field

from engines.scribe_engine import (
    calculate_model_cost,
    estimate_token_count,
    get_default_artifacts_dir,
    get_default_audit_log_path,
    get_default_report_archive_dir,
    get_engine,
    record_audit_event,
)

logger = logging.getLogger("cochem.scribe_inference")

# =============================================================================
# CONSTANTS & FALLBACK NOTICES
# =============================================================================

DEFAULT_INFERENCE_TIMEOUT: float = 120.0
DEFAULT_MAX_RETRIES: int = 3

FALLBACK_METHODOLOGY_NOTICE: str = "[Methodology generation omitted due to validation fallback]"
FALLBACK_INSIGHTS_NOTICE: str = "[AI narrative insights omitted to preserve mathematical air-gap]"
FALLBACK_JUSTIFICATIONS_NOTICE: str = "[Algorithmic justifications bypassed via fallback]"
REDACTION_TAG: str = "[REDACTED_HALLUCINATED_VALUE]"

# Whitelist pattern for Jinja2 placeholders and LaTeX table/figure injection anchors
TAG_PATTERN: re.Pattern = re.compile(r"(\{\{[\s\S]*?\}\}|\<\<[\s\S]*?\>\>)")

# Mathematical Air-Gap Regex: catches numbers coupled with physical/chemical units
PHYSICAL_UNITS_REGEX: re.Pattern = re.compile(
    r"(?<![\w\\])(?:[-+]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*"
    r"(?:\\text\{\\AA\{\}\}|\\text\{\\AA\}|\\AA\{\}|\\AA|Å|Angstroms?|kcal/mol|kJ/mol|Hartrees?|Eh|E_h|cm\^\{-1\}|cm\^-1|cm-1|MHz|GHz|THz|nm|eV|Bohrs?|a\.u\.|arb\.\s*u\.|Debyes?|\bD\b)",
    re.IGNORECASE,
)


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================

class ScribeInferenceError(Exception):
    """Base exception for all CoChem-SCRIBE inference execution failures."""


class ScribeTimeoutError(ScribeInferenceError):
    """Raised when LLM inference exceeds the asynchronous watchdog timeout threshold."""


class ScribeValidationError(ScribeInferenceError):
    """Raised when LLM output violates schema structure or mathematical air-gap constraints."""


# =============================================================================
# PYDANTIC SCHEMA
# =============================================================================

class ScribeInferenceOutput(BaseModel):
    """Pydantic schema enforcing structured JSON output from LLM inference."""

    methodology: str = Field(
        ...,
        description="APS/ACS-compliant narrative covering computational methods.",
    )
    insights: str = Field(
        ...,
        description="Thermodynamic population observations and Boltzmann weighting insights.",
    )
    justifications: str = Field(
        default="",
        description="Scientific justifications for algorithmic choices (e.g., Sinc-DVR).",
    )


ScribeOutputSchema = ScribeInferenceOutput


# =============================================================================
# INFERENCE MANAGER & HALLUCINATION TRAP
# =============================================================================

class ScribeInferenceManager:
    """
    Inference orchestrator, regex hallucination trap, and watchdog manager.

    Coordinates execution between PayloadBuilder and ScribeLLMEngine, enforcing
    the mathematical air-gap, regex scrubbing, Jinja2/LaTeX tag preservation,
    120s timeout watchdogs, markdown syntax validation, and 3-strike fallback.
    """

    def __init__(
        self,
        engine: Optional[Any] = None,
        timeout: float = DEFAULT_INFERENCE_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        log_path: Optional[Union[str, pathlib.Path]] = None,
        raise_on_fallback: bool = False,
        timeout_seconds: Optional[float] = None,
        telemetry_log_path: Optional[Union[str, pathlib.Path]] = None,
        audit_log_path: Optional[Union[str, pathlib.Path]] = None,
    ) -> None:
        self.engine = engine
        effective_timeout = timeout_seconds if timeout_seconds is not None else timeout
        self.timeout = float(effective_timeout)
        self.timeout_seconds = self.timeout
        self.max_retries = int(max_retries)

        effective_log_path = telemetry_log_path if telemetry_log_path is not None else log_path
        self.telemetry_log_path = (
            pathlib.Path(effective_log_path).resolve()
            if effective_log_path
            else (pathlib.Path.home() / "CoChem_Artifacts" / "Logs" / "scribe_telemetry.log")
        )
        self.log_path = self.telemetry_log_path
        self.audit_log_path = (
            pathlib.Path(audit_log_path).resolve()
            if audit_log_path
            else get_default_audit_log_path()
        )
        self.raise_on_fallback = raise_on_fallback
        self.logger = logging.getLogger("cochem.scribe_inference")

    def parse_json_response(self, raw_text: str) -> ScribeOutputSchema:
        """
        Parses raw text or markdown code fences into a validated ScribeOutputSchema model.

        Extracts JSON from ```json ... ```, ``` ... ```, or raw strings and validates against ScribeOutputSchema.
        Raises ScribeValidationError on malformed JSON or schema non-conformance.
        """
        if not raw_text or not raw_text.strip():
            raise ScribeValidationError("Empty response received from LLM engine")

        clean_text = raw_text.strip()

        # Extract from code fences if present
        fence_patterns = [
            re.compile(r"```json\s*([\s\S]*?)\s*```", re.IGNORECASE),
            re.compile(r"```\s*([\s\S]*?)\s*```"),
        ]

        candidate_json: Optional[str] = None
        for pattern in fence_patterns:
            match = pattern.search(clean_text)
            if match:
                candidate_json = match.group(1).strip()
                break

        if candidate_json is None:
            start_idx = clean_text.find("{")
            end_idx = clean_text.rfind("}")
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                candidate_json = clean_text[start_idx : end_idx + 1].strip()
            else:
                candidate_json = clean_text

        try:
            data = json.loads(candidate_json)
            if not isinstance(data, dict):
                raise ScribeValidationError(f"Expected JSON object (dict), got {type(data).__name__}")
            return ScribeOutputSchema.model_validate(data)
        except (json.JSONDecodeError, Exception) as exc:
            raise ScribeValidationError(f"JSON parsing or schema validation failed: {exc}") from exc

    def scrub_text(self, text: str) -> Tuple[str, List[str]]:
        """
        Sweeps narrative text for unauthorized numerical floats coupled with physical/chemical units,
        surgically replaces them with REDACTION_TAG, records audit events,
        while strictly whitelisting and preserving Jinja2 ({{ ... }}) and LaTeX (<< ... >>) tags.

        Returns:
            Tuple[str, List[str]]: (clean_text, matches_found)
        """
        if not text:
            return text, []

        placeholders: List[str] = []

        def mask_tag(match: re.Match[str]) -> str:
            idx = len(placeholders)
            placeholders.append(match.group(0))
            return f"__COCHEM_WHITESPACE_TAG_MASK_{idx}__"

        # Step 1: Pre-mask whitelisted template tags
        masked_text = TAG_PATTERN.sub(mask_tag, text)

        # Step 2: Sweep for unauthorized physical units coupled with numbers
        matches: List[str] = []
        for m in PHYSICAL_UNITS_REGEX.finditer(masked_text):
            matched_str = m.group(0)
            matches.append(matched_str)

        # Surgical redaction of detected physical floats
        redacted_text = PHYSICAL_UNITS_REGEX.sub(REDACTION_TAG, masked_text)

        # Step 3: Restore whitelisted tags
        restored_text = redacted_text
        for idx, tag in enumerate(placeholders):
            restored_text = restored_text.replace(f"__COCHEM_WHITESPACE_TAG_MASK_{idx}__", tag)

        # Step 4: Record audit event if redaction occurred
        if matches:
            try:
                record_audit_event(
                    event_type="MATH_AIRGAP_REDACTION",
                    details={
                        "redacted_matches": matches,
                        "count": len(matches),
                    },
                    audit_log_path=self.audit_log_path,
                )
            except Exception as exc:
                self.logger.warning(f"Failed to record redaction audit event: {exc}")

        return restored_text, matches

    def check_markdown_syntax(self, text: str) -> str:
        """
        Verifies delimiter balance for bold markers, LaTeX math blocks, and code fences,
        applying lightweight deterministic auto-repair to prevent downstream rendering failures.
        """
        if not text:
            return text

        repaired = text

        # 1. Bold marker balance (**)
        bold_count = repaired.count("**")
        if bold_count % 2 != 0:
            repaired = repaired + "**"

        # 2. LaTeX math block balance ($$)
        math_block_count = repaired.count("$$")
        if math_block_count % 2 != 0:
            repaired = repaired + "\n$$"

        # 3. LaTeX inline math delimiters \( and \)
        open_inline = repaired.count(r"\(")
        close_inline = repaired.count(r"\)")
        if open_inline > close_inline:
            repaired = repaired + (r"\)" * (open_inline - close_inline))

        # 4. Code fence balance (```)
        fence_count = repaired.count("```")
        if fence_count % 2 != 0:
            repaired = repaired + "\n```"

        return repaired

    def log_telemetry(
        self,
        engine_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost: float,
        status: str,
        latency_seconds: float = 0.0,
        strike_count: int = 0,
    ) -> None:
        """Appends structured telemetry records and audit events to dynamic artifact paths."""
        try:
            self.telemetry_log_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            self.logger.warning(f"Could not create telemetry log directory: {exc}")

        try:
            self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            self.logger.warning(f"Could not create audit log directory: {exc}")

        timestamp = datetime.now(timezone.utc).isoformat()
        record = {
            "timestamp": timestamp,
            "event_type": "SCRIBE_INFERENCE_TELEMETRY",
            "engine": engine_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "estimated_cost_usd": round(cost, 8),
            "status": status,
            "latency_seconds": round(latency_seconds, 6),
            "strike_count": strike_count,
            "platform": platform.platform(),
            "python_version": sys.version,
        }

        # Telemetry log append
        try:
            with open(self.telemetry_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as exc:
            self.logger.warning(f"Failed to append to telemetry log {self.telemetry_log_path}: {exc}")

        # Central audit log append
        try:
            record_audit_event(
                event_type="SCRIBE_INFERENCE_TELEMETRY",
                details={
                    "engine": engine_name,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                    "estimated_cost_usd": round(cost, 8),
                    "status": status,
                    "latency_seconds": round(latency_seconds, 6),
                    "strike_count": strike_count,
                },
                audit_log_path=self.audit_log_path,
            )
        except Exception as exc:
            self.logger.warning(f"Failed to record audit event: {exc}")

    async def run_inference(self, prompt: str) -> ScribeOutputSchema:
        """
        Asynchronously executes inference with watchdog timeout, schema validation,
        mathematical air-gap regex scrubbing, and 3-strike retry loop.
        """
        if self.engine is None:
            from engines.scribe_engine import get_engine
            self.engine = get_engine()

        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            start_time = time.perf_counter()
            try:
                # Dispatch generation
                if hasattr(self.engine, "async_generate") and callable(self.engine.async_generate):
                    coro = self.engine.async_generate(prompt)
                elif hasattr(self.engine, "generate") and callable(self.engine.generate):
                    coro = asyncio.to_thread(self.engine.generate, prompt)
                elif callable(self.engine):
                    coro = asyncio.to_thread(self.engine, prompt)
                else:
                    raise ScribeInferenceError(f"Engine {self.engine} has no generate or async_generate method")

                # Watchdog timeout
                raw_text = await asyncio.wait_for(coro, timeout=self.timeout_seconds)
                latency = time.perf_counter() - start_time

                # Parse JSON
                schema_obj = self.parse_json_response(raw_text)

                # Math air-gap verification and markdown syntax check for each field
                for field_name in ["methodology", "insights", "justifications"]:
                    field_val = getattr(schema_obj, field_name, "")
                    if field_val:
                        scrubbed_val, matches = self.scrub_text(field_val)
                        if matches:
                            self.logger.warning(
                                f"Mathematical Air-Gap violation on attempt {attempt}/{self.max_retries} in {field_name}: {matches}"
                            )
                            raise ScribeValidationError(
                                f"Mathematical Air-Gap violation: hallucinated physical quantity detected: {matches}"
                            )
                        repaired_val = self.check_markdown_syntax(scrubbed_val)
                        setattr(schema_obj, field_name, repaired_val)

                # Calculate token metrics & cost
                prompt_tokens = estimate_token_count(prompt)
                combined_output = f"{schema_obj.methodology} {schema_obj.insights} {schema_obj.justifications}"
                completion_tokens = estimate_token_count(combined_output)
                model_name = getattr(self.engine, "model_name", "unknown")
                cost = calculate_model_cost(model_name, prompt_tokens, completion_tokens)

                self.log_telemetry(
                    engine_name=type(self.engine).__name__,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cost=cost,
                    status="SUCCESS",
                    latency_seconds=latency,
                    strike_count=attempt - 1,
                )
                return schema_obj

            except asyncio.TimeoutError as exc:
                latency = time.perf_counter() - start_time
                self.logger.warning(
                    f"LLM inference timed out after {self.timeout_seconds}s (attempt {attempt}/{self.max_retries})"
                )
                last_error = ScribeTimeoutError(f"LLM inference timed out after {self.timeout_seconds}s")
                self.log_telemetry(
                    engine_name=type(self.engine).__name__ if self.engine else "UnknownEngine",
                    prompt_tokens=estimate_token_count(prompt),
                    completion_tokens=0,
                    cost=0.0,
                    status="TIMEOUT",
                    latency_seconds=latency,
                    strike_count=attempt,
                )

            except ScribeValidationError as exc:
                latency = time.perf_counter() - start_time
                self.logger.warning(
                    f"Schema or math air-gap validation failed (attempt {attempt}/{self.max_retries}): {exc}"
                )
                last_error = exc
                self.log_telemetry(
                    engine_name=type(self.engine).__name__ if self.engine else "UnknownEngine",
                    prompt_tokens=estimate_token_count(prompt),
                    completion_tokens=0,
                    cost=0.0,
                    status="VALIDATION_ERROR",
                    latency_seconds=latency,
                    strike_count=attempt,
                )

            except Exception as exc:
                latency = time.perf_counter() - start_time
                self.logger.warning(
                    f"Inference execution failed (attempt {attempt}/{self.max_retries}): {exc}"
                )
                last_error = exc if isinstance(exc, ScribeInferenceError) else ScribeInferenceError(str(exc))
                self.log_telemetry(
                    engine_name=type(self.engine).__name__ if self.engine else "UnknownEngine",
                    prompt_tokens=estimate_token_count(prompt),
                    completion_tokens=0,
                    cost=0.0,
                    status="EXECUTION_ERROR",
                    latency_seconds=latency,
                    strike_count=attempt,
                )

        # All retries exhausted
        self.log_telemetry(
            engine_name=type(self.engine).__name__ if self.engine else "UnknownEngine",
            prompt_tokens=estimate_token_count(prompt),
            completion_tokens=0,
            cost=0.0,
            status="FALLBACK_EXHAUSTED",
            latency_seconds=0.0,
            strike_count=self.max_retries,
        )

        if self.raise_on_fallback:
            raise ScribeInferenceError(f"Inference failed after max retries: strikes exhausted ({last_error})")

        return ScribeOutputSchema(
            methodology=FALLBACK_METHODOLOGY_NOTICE,
            insights=FALLBACK_INSIGHTS_NOTICE,
            justifications=FALLBACK_JUSTIFICATIONS_NOTICE,
        )

    def execute_inference(self, prompt: str) -> ScribeOutputSchema:
        """
        Synchronous wrapper executing asynchronous inference safely across existing or new event loops.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, self.run_inference(prompt))
                return future.result()
        else:
            return asyncio.run(self.run_inference(prompt))


# =============================================================================
# CLI PRE-FLIGHT VALIDATION (SRS §8.2.9)
# =============================================================================

if __name__ == "__main__":
    from engines.scribe_engine import DryRunEngine

    print("[PRE-FLIGHT] Initializing ScribeInferenceManager with DryRunEngine...")
    manager = ScribeInferenceManager(engine=DryRunEngine(), timeout_seconds=10.0)

    # 1. JSON Schema parsing test
    sample_json = json.dumps({
        "methodology": "Calculations were performed using DFT with B3LYP functional.",
        "insights": "Conformer populations follow Boltzmann distribution.",
        "justifications": "Harmonic vibrational analysis confirmed all real frequencies.",
    })
    parsed = manager.parse_json_response(f"```json\n{sample_json}\n```")
    assert parsed.methodology == "Calculations were performed using DFT with B3LYP functional."
    print("[PRE-FLIGHT] Validating JSON schema extraction... PASSED")

    # 2. Math Air-Gap Regex Scrubber test
    test_hallucinated = "The equilibrium C-C bond length was computed as 1.54 \\AA{}."
    _, matches = manager.scrub_text(test_hallucinated)
    assert len(matches) > 0, f"Expected scrubber to catch 1.54 \\AA{{}}, got: {matches}"
    print(f"[PRE-FLIGHT] Validating Mathematical Air-Gap Regex Scrubber... PASSED (Caught: {matches})")

    # 3. Jinja2 & LaTeX tag preservation test
    test_tags = "The results are summarized in {{ physical_data_table }} and <<INSERT_TABLE_HERE>>."
    scrubbed_tags, tag_matches = manager.scrub_text(test_tags)
    assert len(tag_matches) == 0, f"Expected 0 matches on whitelisted tags, got: {tag_matches}"
    assert "{{ physical_data_table }}" in scrubbed_tags
    assert "<<INSERT_TABLE_HERE>>" in scrubbed_tags
    print("[PRE-FLIGHT] Validating Jinja2 & LaTeX tag preservation... PASSED")

    # 4. Markdown syntax auto-repair test
    unclosed_bold = "This is **bold text without closing."
    repaired_bold = manager.check_markdown_syntax(unclosed_bold)
    assert repaired_bold.endswith("**")
    print("[PRE-FLIGHT] Validating Markdown syntax auto-repair... PASSED")

    print("[SCRIBE INFERENCE PRE-FLIGHT VERIFIED]")
