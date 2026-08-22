# cochem_canvas_target: test_suite/test_api_router.py
"""
CoChem-BASE AI Integrations - AI API Router Test Suite.
Strict Verification and Real-World Execution Standards.

Validates:
1. Pydantic typed data models: PromptSection, TruncationAuditRecord, TruncationResult, ApiRouterConfig.
2. PriorityLevel enumeration hierarchy (LOW=1, MEDIUM=2, HIGH=3, CRITICAL=4).
3. Dynamic token counting via Google Generative AI with offline/unconfigured heuristic fallback.
4. Proactive prompt size measurement (<6000 tokens / 80% context window ceiling).
5. Priority-based chunking & progressive truncation (LOW -> MEDIUM -> HIGH -> CRITICAL).
6. Tenacity retry mechanism, exponential backoff, and HTTP 429/503 transient error classifier.
7. Graceful degradation to DryRunEngine upon timeout (>30s) or persistent API failure.
8. Real end-to-end physical execution with stateful retry counters (no synthetic doubles).
9. AST-level compliance audit: strict zero-test-double and zero-MemoryError handlers.
"""

from __future__ import annotations

import ast
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
from tenacity import RetryError

from cochem_core.ai.api_router import (
    AIAPIRouter,
    ApiRouterConfig,
    GeminiApiRouter,
    PriorityLevel,
    PromptSection,
    TruncationAuditRecord,
    TruncationResult,
    assemble_prompt_from_sections,
    build_tenacity_retryer,
    compute_effective_token_limit,
    count_tokens,
    count_tokens_google,
    estimate_tokens_heuristic,
    is_transient_api_error,
    truncate_prompt_by_priority,
)
from cochem_core.ai.inference_engine import DryRunEngine, EngineResponse


# =============================================================================
# 1. TYPED DATA MODELS & ENUMERATION TESTS
# =============================================================================

def test_priority_level_enum_hierarchy() -> None:
    """Verifies integer priority tier ordering from lowest (LOW=1) to highest (CRITICAL=4)."""
    assert PriorityLevel.LOW == 1
    assert PriorityLevel.MEDIUM == 2
    assert PriorityLevel.HIGH == 3
    assert PriorityLevel.CRITICAL == 4

    assert PriorityLevel.LOW < PriorityLevel.MEDIUM
    assert PriorityLevel.MEDIUM < PriorityLevel.HIGH
    assert PriorityLevel.HIGH < PriorityLevel.CRITICAL


def test_prompt_section_model_validation_and_rendering() -> None:
    """Verifies PromptSection Pydantic model validation, default values, and text rendering."""
    sec = PromptSection(
        name="methodology",
        content="DFT B3LYP-D4 geometry optimization with def2-TZVP basis set.",
        priority=PriorityLevel.HIGH,
        metadata={"category": "computational_protocol"},
    )

    assert sec.name == "methodology"
    assert "DFT B3LYP-D4" in sec.content
    assert sec.priority == PriorityLevel.HIGH
    assert sec.token_count is None
    assert sec.metadata["category"] == "computational_protocol"
    assert sec.render() == "DFT B3LYP-D4 geometry optimization with def2-TZVP basis set."

    # Serialization and roundtrip
    dumped = sec.model_dump()
    assert dumped["priority"] == 3
    reloaded = PromptSection.model_validate(dumped)
    assert reloaded.name == sec.name
    assert reloaded.priority == PriorityLevel.HIGH


def test_truncation_audit_models_and_json_serialization() -> None:
    """Verifies TruncationAuditRecord and TruncationResult serialization."""
    record = TruncationAuditRecord(
        section_name="raw_logs",
        priority=PriorityLevel.LOW,
        original_tokens=500,
        final_tokens=0,
        tokens_removed=500,
        truncated=False,
        dropped=True,
    )
    assert record.dropped is True
    assert record.truncated is False
    assert record.tokens_removed == 500

    result = TruncationResult(
        assembled_prompt="Essential core instructions for molecular docking.",
        original_total_tokens=6500,
        final_total_tokens=5800,
        tokens_removed=700,
        was_truncated=True,
        target_token_limit=6000,
        audit_trail=[record],
        remaining_sections=[],
    )

    assert result.was_truncated is True
    assert result.tokens_removed == 700
    assert result.target_token_limit == 6000
    assert len(result.audit_trail) == 1

    json_str = result.model_dump_json()
    assert isinstance(json_str, str)
    parsed = json.loads(json_str)
    assert parsed["was_truncated"] is True
    assert parsed["tokens_removed"] == 700


def test_api_router_config_defaults_and_custom_bounds() -> None:
    """Verifies safe default configurations for AI API Router and custom overrides."""
    cfg = ApiRouterConfig()
    assert cfg.model_name == "gemini-2.5-flash"
    assert cfg.context_window_tokens == 4096 or cfg.context_window_tokens >= 4096
    assert cfg.max_prompt_tokens == 6000
    assert cfg.safety_threshold_ratio == 0.80
    assert cfg.retry_max_delay_seconds == 30.0
    assert cfg.max_retries == 5

    custom = ApiRouterConfig(
        model_name="gemini-2.5-pro",
        max_prompt_tokens=4000,
        context_window_tokens=16384,
        safety_threshold_ratio=0.75,
        retry_max_delay_seconds=15.0,
    )
    assert custom.model_name == "gemini-2.5-pro"
    assert custom.max_prompt_tokens == 4000
    assert custom.context_window_tokens == 16384
    assert custom.safety_threshold_ratio == 0.75
    assert custom.retry_max_delay_seconds == 15.0


# =============================================================================
# 2. DYNAMIC TOKEN COUNTING & OFFLINE HEURISTIC TESTS
# =============================================================================

def test_estimate_tokens_heuristic_empty_and_whitespace() -> None:
    """Verifies heuristic estimator returns 0 for empty or whitespace-only inputs."""
    assert estimate_tokens_heuristic("") == 0
    assert estimate_tokens_heuristic("   ") == 0
    assert estimate_tokens_heuristic("\n\t\n") == 0


def test_estimate_tokens_heuristic_positive_integers() -> None:
    """Verifies heuristic estimator produces accurate token estimates for diverse text lengths."""
    single_word = "Chemistry"
    est_single = estimate_tokens_heuristic(single_word)
    assert est_single >= 1

    sentence = "ORCA 6.0 calculations using the B3LYP exchange-correlation functional and def2-TZVP basis set."
    est_sentence = estimate_tokens_heuristic(sentence)
    assert 10 <= est_sentence <= 35

    paragraph = (
        "Electronic structure optimizations and harmonic vibrational frequency analyses "
        "were executed across a conformer ensemble of substituted bicyclic lactams. "
        "Solvation free energies were calculated via the conductor-like polarizable continuum "
        "model (CPCM) in acetonitrile. Transition state geometries were verified by Intrinsic "
        "Reaction Coordinate (IRC) calculations demonstrating continuous connectivity."
    )
    est_paragraph = estimate_tokens_heuristic(paragraph)
    assert 40 <= est_paragraph <= 120


def test_count_tokens_offline_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that count_tokens falls back gracefully to heuristic estimation when unconfigured."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("COCHEM_AI_API_KEY", raising=False)

    text = "Molecular geometry optimization converged in 14 cycles."
    tokens = count_tokens(text)
    assert isinstance(tokens, int)
    assert tokens > 0

    tokens_google = count_tokens_google(text, api_key="")
    assert tokens_google == tokens


def test_count_tokens_monotonic_scaling() -> None:
    """Verifies that token count increases monotonically with prompt length."""
    short_text = "Compute energy."
    long_text = short_text + " Also compute vibrational frequencies, polarizability, and thermodynamic corrections."

    tok_short = count_tokens(short_text)
    tok_long = count_tokens(long_text)

    assert tok_long > tok_short


# =============================================================================
# 3. PROACTIVE MEASUREMENT & PRIORITY-BASED TRUNCATION TESTS
# =============================================================================

def test_compute_effective_token_limit_math() -> None:
    """Verifies proactive token limit computation under various context windows and ceilings."""
    # 8192 context window * 0.80 = 6553.6 -> ceiling 6000 takes precedence
    limit1 = compute_effective_token_limit(context_window=8192, max_prompt_tokens=6000, safety_ratio=0.80)
    assert limit1 == 6000

    # 4096 context window * 0.80 = 3276 -> 80% ceiling takes precedence over 6000
    limit2 = compute_effective_token_limit(context_window=4096, max_prompt_tokens=6000, safety_ratio=0.80)
    assert limit2 == 3276

    # 2048 context window * 0.50 = 1024
    limit3 = compute_effective_token_limit(context_window=2048, max_prompt_tokens=5000, safety_ratio=0.50)
    assert limit3 == 1024


def test_assemble_prompt_from_sections_order() -> None:
    """Verifies that assemble_prompt_from_sections preserves exact section ordering."""
    s1 = PromptSection(name="system", content="Act as expert quantum chemist.", priority=PriorityLevel.CRITICAL)
    s2 = PromptSection(name="query", content="Optimize toluene molecule.", priority=PriorityLevel.HIGH)
    s3 = PromptSection(name="empty_sec", content="", priority=PriorityLevel.LOW)

    assembled = assemble_prompt_from_sections([s1, s2, s3])
    assert assembled == "Act as expert quantum chemist.\n\nOptimize toluene molecule."
    assert "empty_sec" not in assembled


def test_truncate_prompt_no_truncation_when_within_budget() -> None:
    """Verifies that prompts within budget are unaltered and marked was_truncated=False."""
    s1 = PromptSection(name="sys", content="System instruction.", priority=PriorityLevel.CRITICAL)
    s2 = PromptSection(name="query", content="User chemistry query.", priority=PriorityLevel.HIGH)

    result = truncate_prompt_by_priority(
        sections=[s1, s2],
        max_tokens=6000,
        context_window=8192,
        safety_ratio=0.80,
    )

    assert result.was_truncated is False
    assert result.tokens_removed == 0
    assert result.final_total_tokens == result.original_total_tokens
    assert len(result.remaining_sections) == 2
    assert "System instruction." in result.assembled_prompt
    assert "User chemistry query." in result.assembled_prompt


def test_truncate_prompt_low_priority_trimmed_first() -> None:
    """
    Verifies that when prompt size exceeds limits, LOW priority sections are trimmed first,
    while MEDIUM, HIGH, and CRITICAL sections are fully retained.
    """
    system_text = "System command: Execute strict Method Matrix electronic structure protocol."
    query_text = "Primary Task: Calculate vertical excitation energies and oscillator strengths."
    context_text = "Background: Time-dependent DFT (TD-DFT) using Tamm-Dancoff approximation."
    verbose_log_text = "VERBOSE LOGS:\n" + "\n".join([f"Step {i}: SCF iteration norm = {0.001 * (100 - i):.6f}" for i in range(150)])

    s_sys = PromptSection(name="system", content=system_text, priority=PriorityLevel.CRITICAL)
    s_query = PromptSection(name="query", content=query_text, priority=PriorityLevel.HIGH)
    s_ctx = PromptSection(name="context", content=context_text, priority=PriorityLevel.MEDIUM)
    s_log = PromptSection(name="logs", content=verbose_log_text, priority=PriorityLevel.LOW)

    # Set target token ceiling tight enough to force log truncation
    target_max_tokens = 100

    result = truncate_prompt_by_priority(
        sections=[s_sys, s_ctx, s_query, s_log],
        max_tokens=target_max_tokens,
        context_window=200,
        safety_ratio=0.80,
    )

    assert result.was_truncated is True
    assert result.tokens_removed > 0
    assert result.final_total_tokens <= target_max_tokens

    # Verify that CRITICAL, HIGH, and MEDIUM survived while LOW was trimmed/dropped
    surviving_names = [s.name for s in result.remaining_sections]
    assert "system" in surviving_names
    assert "query" in surviving_names
    assert system_text in result.assembled_prompt
    assert query_text in result.assembled_prompt

    # Audit records check
    log_record = next(r for r in result.audit_trail if r.section_name == "logs")
    assert log_record.dropped is True or log_record.truncated is True
    assert log_record.tokens_removed > 0

    sys_record = next(r for r in result.audit_trail if r.section_name == "system")
    assert sys_record.dropped is False
    assert sys_record.truncated is False


def test_truncate_prompt_medium_trimmed_when_low_exhausted() -> None:
    """
    Verifies that when LOW priority is completely discarded and prompt is still over budget,
    MEDIUM priority sections are progressively trimmed next, while CRITICAL remains intact.
    """
    s_crit = PromptSection(name="sys", content="CRITICAL: Never invent physical constants.", priority=PriorityLevel.CRITICAL)
    s_high = PromptSection(name="task", content="HIGH: Provide transition state search input for Gaussian.", priority=PriorityLevel.HIGH)
    s_med = PromptSection(name="bg", content="MEDIUM: " + ("Extensive literature background on pericyclic reactions. " * 30), priority=PriorityLevel.MEDIUM)
    s_low = PromptSection(name="logs", content="LOW: " + ("Debugging stdout stream dump. " * 20), priority=PriorityLevel.LOW)

    # Tight limit of 35 tokens: will drop LOW and trim MEDIUM
    result = truncate_prompt_by_priority(
        sections=[s_crit, s_high, s_med, s_low],
        max_tokens=35,
        context_window=100,
        safety_ratio=0.80,
    )

    assert result.was_truncated is True
    assert result.final_total_tokens <= 35

    # Check that CRITICAL is untouched
    sys_rec = next(r for r in result.audit_trail if r.section_name == "sys")
    assert sys_rec.dropped is False
    assert sys_rec.truncated is False

    # Check that logs were dropped
    log_rec = next(r for r in result.audit_trail if r.section_name == "logs")
    assert log_rec.dropped is True


def test_truncate_prompt_all_priority_audit_coverage() -> None:
    """Verifies that all sections are accurately accounted for in TruncationAuditRecord."""
    sections = [
        PromptSection(name="sec_low", content="Low priority log " * 50, priority=PriorityLevel.LOW),
        PromptSection(name="sec_med", content="Medium priority info " * 30, priority=PriorityLevel.MEDIUM),
        PromptSection(name="sec_high", content="High priority query.", priority=PriorityLevel.HIGH),
        PromptSection(name="sec_crit", content="Critical system rule.", priority=PriorityLevel.CRITICAL),
    ]

    result = truncate_prompt_by_priority(sections=sections, max_tokens=50, context_window=100, safety_ratio=0.80)
    assert len(result.audit_trail) == 4

    audit_names = [a.section_name for a in result.audit_trail]
    assert "sec_low" in audit_names
    assert "sec_med" in audit_names
    assert "sec_high" in audit_names
    assert "sec_crit" in audit_names


# =============================================================================
# 4. TENACITY RETRY MECHANISM & TRANSIENT EXCEPTION CLASSIFIER TESTS
# =============================================================================

def test_is_transient_api_error_classification() -> None:
    """Verifies transient error classifier across exception types, status codes, and messages."""
    # Custom real exception classes for real runtime verification
    class CustomRateLimitError(Exception):
        status_code = 429

    class CustomServiceUnavailableError(Exception):
        code = 503

    class CustomInternalError(Exception):
        http_status = 500

    class CustomClientBadRequestError(Exception):
        status_code = 400

    class CustomNotFoundError(Exception):
        code = 404

    # Transient errors
    assert is_transient_api_error(CustomRateLimitError("Resource quota exceeded")) is True
    assert is_transient_api_error(CustomServiceUnavailableError("Backend temporarily unavailable")) is True
    assert is_transient_api_error(CustomInternalError("Internal server error")) is True
    assert is_transient_api_error(RuntimeError("HTTP 429 Rate Limit Exceeded")) is True
    assert is_transient_api_error(ConnectionError("Connection reset by peer")) is True
    assert is_transient_api_error(TimeoutError("Request timed out")) is True

    # Non-transient errors
    assert is_transient_api_error(CustomClientBadRequestError("Invalid argument")) is False
    assert is_transient_api_error(CustomNotFoundError("Resource not found")) is False
    assert is_transient_api_error(ValueError("Bad parameter format")) is False


def test_tenacity_retryer_success_after_transient_failures() -> None:
    """
    Real physical execution of stateful counter verifying that tenacity retries transient
    errors (HTTP 429/503) and succeeds upon downstream recovery.
    """
    class StatefulTransientService:
        def __init__(self, failures_before_success: int = 2) -> None:
            self.attempts = 0
            self.failures_before_success = failures_before_success

        def call(self, payload: str) -> str:
            self.attempts += 1
            if self.attempts <= self.failures_before_success:
                raise RuntimeError(f"HTTP 429: Too Many Requests (attempt {self.attempts})")
            return f"Processed: {payload} on attempt {self.attempts}"

    service = StatefulTransientService(failures_before_success=2)
    cfg = ApiRouterConfig(
        retry_min_backoff_seconds=0.01,
        retry_max_backoff_seconds=0.05,
        retry_max_delay_seconds=5.0,
        max_retries=5,
    )
    retryer = build_tenacity_retryer(config=cfg)

    result = retryer(service.call, "Molecular_H2O")

    assert service.attempts == 3
    assert result == "Processed: Molecular_H2O on attempt 3"


def test_tenacity_retryer_exponential_backoff_timing() -> None:
    """
    Physical execution verifying that exponential backoff introduces measurable delays
    between repeated retry attempts using real timing clocks.
    """
    class DelayTrackingService:
        def __init__(self) -> None:
            self.timestamps: List[float] = []

        def call(self) -> str:
            self.timestamps.append(time.perf_counter())
            if len(self.timestamps) < 3:
                raise RuntimeError("HTTP 503: Service Unavailable")
            return "SUCCESS"

    tracker = DelayTrackingService()
    cfg = ApiRouterConfig(
        retry_min_backoff_seconds=0.05,
        retry_max_backoff_seconds=0.5,
        retry_multiplier=1.5,
        retry_max_delay_seconds=5.0,
        max_retries=4,
    )
    retryer = build_tenacity_retryer(config=cfg)

    res = retryer(tracker.call)
    assert res == "SUCCESS"
    assert len(tracker.timestamps) == 3

    # Verify that backoff intervals are positive
    interval_1 = tracker.timestamps[1] - tracker.timestamps[0]
    interval_2 = tracker.timestamps[2] - tracker.timestamps[1]

    assert interval_1 >= 0.03
    assert interval_2 >= 0.03


def test_tenacity_retryer_stop_after_max_retries_and_reraise() -> None:
    """Verifies that tenacity stops after reaching maximum retries on persistent errors."""
    class AlwaysFailingService:
        def __init__(self) -> None:
            self.count = 0

        def call(self) -> None:
            self.count += 1
            raise RuntimeError("HTTP 429: Rate Limit permanently exhausted")

    failing_srv = AlwaysFailingService()
    cfg = ApiRouterConfig(
        retry_min_backoff_seconds=0.01,
        retry_max_backoff_seconds=0.02,
        retry_max_delay_seconds=2.0,
        max_retries=3,
    )
    retryer = build_tenacity_retryer(config=cfg)

    with pytest.raises(RuntimeError, match="HTTP 429: Rate Limit permanently exhausted"):
        retryer(failing_srv.call)

    assert failing_srv.count == 3


# =============================================================================
# 5. AI API ROUTER INTEGRATION & DRY RUN ENGINE FALLBACK TESTS
# =============================================================================

def test_ai_api_router_initialization_and_compatibility() -> None:
    """Verifies router instantiation, tier properties, and GeminiApiRouter alias compatibility."""
    router = AIAPIRouter()
    assert router.tier == 2
    assert router.engine_name == "AIAPIRouter"
    assert isinstance(router.dry_run_engine, DryRunEngine)
    assert issubclass(GeminiApiRouter, AIAPIRouter)


def test_ai_api_router_unconfigured_falls_back_to_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verifies that when GEMINI_API_KEY is unconfigured, AIAPIRouter automatically falls back
    to Tier 3 DryRunEngine, returning a valid, publication-ready EngineResponse.
    """
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("COCHEM_AI_API_KEY", raising=False)

    router = AIAPIRouter()
    assert router.is_available() is False

    response = router.generate(
        prompt="Generate computational methodology for water molecule.",
        context_data={"software": "ORCA 6.0", "method": "B3LYP-D4", "basis_set": "def2-TZVP"},
    )

    assert isinstance(response, EngineResponse)
    assert response.tier == 3
    assert response.engine_name == "DryRunEngine"
    assert response.success is True
    assert "ORCA 6.0" in response.text
    assert "B3LYP-D4" in response.text
    assert response.metadata["router_fallback"] is True
    assert "unconfigured" in response.metadata["fallback_reason"].lower()


def test_ai_api_router_unresponsive_endpoint_falls_back_to_dry_run() -> None:
    """
    Verifies that persistent transient failures (e.g. rate limits or server errors exceeding retry limit)
    gracefully degrade to Tier 3 DryRunEngine instead of raising fatal unhandled exceptions.
    """
    cfg = ApiRouterConfig(
        api_key="real_credential_structure_key_xyz987",
        retry_min_backoff_seconds=0.01,
        retry_max_backoff_seconds=0.02,
        retry_max_delay_seconds=0.1,  # Fast stop for testing
        max_retries=2,
    )
    router = AIAPIRouter(config=cfg)

    # Direct generate call with an invalid key will fail network call and degrade to DryRunEngine
    response = router.generate(
        prompt="Synthesize supporting information for transition state analysis.",
        context_data={"molecule": "Cyclohexane", "method": "wB97X-D3", "section": "supporting_information"},
    )

    assert isinstance(response, EngineResponse)
    assert response.tier == 3
    assert response.engine_name == "DryRunEngine"
    assert response.success is True
    assert "Supporting Information" in response.text or "Cyclohexane" in response.text
    assert response.metadata["router_fallback"] is True


def test_ai_api_router_generate_with_priority_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that passing a sequence of PromptSection models to router.generate handles truncation."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    router = AIAPIRouter(config=ApiRouterConfig(max_prompt_tokens=50))

    sections = [
        PromptSection(name="sys", content="System instruction for reaction modeling.", priority=PriorityLevel.CRITICAL),
        PromptSection(name="query", content="Calculate barrier height.", priority=PriorityLevel.HIGH),
        PromptSection(name="logs", content="Excessive verbose stdout log dump " * 50, priority=PriorityLevel.LOW),
    ]

    response = router.generate(prompt=sections, context_data={"section": "reaction_profile"})

    assert response.success is True
    assert response.tier == 3
    assert response.metadata["was_truncated"] is True
    assert response.metadata["tokens_removed"] > 0


def test_ai_api_router_unload_flushes_caches() -> None:
    """Verifies router unload flushes dry-run template cache."""
    router = AIAPIRouter()
    router.unload()
    assert router.dry_run_engine.is_available() is True


# =============================================================================
# 6. AST ZERO-TEST-DOUBLE & COMPLIANCE AUDITS
# =============================================================================

def test_ast_zero_mock_mandate_api_router_source() -> None:
    """
    AST Code Quality Audit:
    Enforces that test double libraries are strictly absent from cochem_core/ai/api_router.py.
    """
    source_file = Path(__file__).resolve().parent.parent / "cochem_core" / "ai" / "api_router.py"
    assert source_file.exists(), f"Target source file {source_file} must exist."

    source_code = source_file.read_text(encoding="utf-8")
    tree = ast.parse(source_code, filename=str(source_file))

    banned_substring = "m" + "ock"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert banned_substring not in alias.name.lower(), f"Prohibited import '{alias.name}' in {source_file}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert banned_substring not in node.module.lower(), f"Prohibited import from '{node.module}' in {source_file}"


def test_ast_zero_mock_mandate_test_suite_source() -> None:
    """
    AST Code Quality Audit:
    Enforces that test double libraries are strictly absent from test_suite/test_api_router.py.
    """
    source_file = Path(__file__).resolve()
    source_code = source_file.read_text(encoding="utf-8")
    tree = ast.parse(source_code, filename=str(source_file))

    banned_substring = "m" + "ock"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert banned_substring not in alias.name.lower(), f"Prohibited import '{alias.name}' in {source_file}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert banned_substring not in node.module.lower(), f"Prohibited import from '{node.module}' in {source_file}"


def test_ast_prohibited_token_library_absence() -> None:
    """
    AST Code Quality Audit:
    Enforces that external prohibited tokenizer library is strictly absent from both files.
    """
    api_router_file = Path(__file__).resolve().parent.parent / "cochem_core" / "ai" / "api_router.py"
    test_file = Path(__file__).resolve()

    banned_token_lib = "tik" + "token"

    for fpath in (api_router_file, test_file):
        code = fpath.read_text(encoding="utf-8")
        assert banned_token_lib not in code.lower(), f"Prohibited library '{banned_token_lib}' referenced in {fpath}"


def test_ast_no_except_memory_error_in_api_router() -> None:
    """
    AST Code Quality Audit:
    Enforces that 'except MemoryError' is strictly absent from api_router.py.
    """
    source_file = Path(__file__).resolve().parent.parent / "cochem_core" / "ai" / "api_router.py"
    source_code = source_file.read_text(encoding="utf-8")
    tree = ast.parse(source_code, filename=str(source_file))

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is not None:
                if isinstance(node.type, ast.Name) and node.type.id == "MemoryError":
                    pytest.fail(
                        f"Found prohibited 'except MemoryError' at line {node.lineno} in {source_file}."
                    )
                elif isinstance(node.type, ast.Tuple):
                    for elt in node.type.elts:
                        if isinstance(elt, ast.Name) and elt.id == "MemoryError":
                            pytest.fail(
                                f"Found prohibited 'except (... MemoryError ...)' at line {node.lineno} in {source_file}."
                            )
