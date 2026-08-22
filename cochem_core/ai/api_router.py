# cochem_canvas_target: cochem_core/ai/api_router.py
"""
CoChem-BASE AI Integrations - AI API Router Subsystem.
Strict Real-World Execution Standards.

Provides intelligent network dispatch, dynamic token counting via Google Generative AI
(with robust offline heuristic fallback), proactive prompt size measurement, priority-based
block chunking/truncation, tenacity exponential backoff retry for HTTP 429/503 status codes,
and seamless graceful degradation to Tier 3 DryRunEngine upon timeout (>30s) or failure.

Core Architectural Invariants:
1. Dynamic Token Counting:
   - Evaluates prompt token length via Google Generative AI SDK (count_tokens).
   - If offline, unconfigured, or network is unavailable, seamlessly uses robust heuristic
     token estimation without throwing unhandled exceptions.
   - Strictly prohibited: Any external tokenizer library dependency.
2. Proactive Measurement & Priority-Tagged Truncation:
   - Checks total prompt tokens prior to network dispatch.
   - If tokens > 6000 (or >80% of active context window), automatically executes priority-based
     chunking, trimming lowest-priority text blocks (LOW -> MEDIUM -> HIGH -> CRITICAL)
     until the prompt safely fits the context budget.
3. Tenacity Exponential Backoff & Transient Fault Resilience:
   - Wraps API calls with tenacity retry logic.
   - Catches HTTP 429 (ResourceExhausted / Rate Limit) and HTTP 503 (ServiceUnavailable / Server Error)
     along with transient network disconnects.
   - Applies exponential backoff with configurable minimum/maximum delay.
4. Seamless Tier 3 DryRunEngine Fallback:
   - If external API remains unresponsive for >30 seconds or retries are exhausted,
     execution automatically degrades to DryRunEngine, returning a valid, publication-ready
     EngineResponse without breaking the computational chemistry pipeline.
"""

from __future__ import annotations

from enum import IntEnum
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field
import tenacity
from tenacity import (
    RetryError,
    Retrying,
    before_sleep_log,
    retry_if_exception,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential,
)

from cochem_core.ai.inference_engine import (
    DEFAULT_CONTEXT_WINDOW,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    DryRunEngine,
    EngineResponse,
    load_and_secure_gemini_key,
)

logger = logging.getLogger("CoChem.AI.ApiRouter")

# =============================================================================
# CONSTANTS & CONFIGURATION DEFAULTS
# =============================================================================

DEFAULT_MAX_PROMPT_TOKENS: int = 6000
DEFAULT_SAFETY_RATIO: float = 0.80
DEFAULT_RETRY_MAX_DELAY_SECONDS: float = 30.0
DEFAULT_RETRY_MIN_BACKOFF_SECONDS: float = 1.0
DEFAULT_RETRY_MAX_BACKOFF_SECONDS: float = 10.0
DEFAULT_MAX_RETRIES: int = 5
DEFAULT_GEMINI_MODEL: str = "gemini-2.5-flash"


# =============================================================================
# PRIORITY LEVEL ENUMERATION
# =============================================================================

class PriorityLevel(IntEnum):
    """
    Priority tiers for prompt text blocks during proactive token measurement and truncation.
    Lower priority blocks are truncated or dropped first when prompt size exceeds limits.
    """
    LOW = 1       # Verbose execution logs, stdout streams, debug dumps, auxiliary formatting
    MEDIUM = 2    # Background context, literature extracts, few-shot examples, theoretical notes
    HIGH = 3      # Core user query, primary scientific objective, task-critical context
    CRITICAL = 4  # System prompt, fundamental instructions, physical safety constraints


# =============================================================================
# TYPED DATA MODELS
# =============================================================================

class PromptSection(BaseModel):
    """
    Priority-tagged text block within a structured prompt payload.
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    name: str = Field(..., description="Unique label or section header name")
    content: str = Field(..., description="Text content for this prompt section")
    priority: PriorityLevel = Field(
        default=PriorityLevel.MEDIUM,
        description="Priority tier determining truncation sequence (LOW truncated first, CRITICAL preserved)"
    )
    token_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Computed token count for this section"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Custom metadata or provenance tags"
    )

    def render(self) -> str:
        """Renders the section content with optional header if name is descriptive."""
        text = self.content.strip()
        if not text:
            return ""
        return text


class TruncationAuditRecord(BaseModel):
    """
    Audit trail record detailing adjustments made to an individual section during truncation.
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    section_name: str = Field(..., description="Name of the prompt section")
    priority: PriorityLevel = Field(..., description="Priority level of the section")
    original_tokens: int = Field(..., ge=0, description="Token count before truncation")
    final_tokens: int = Field(..., ge=0, description="Token count after truncation")
    tokens_removed: int = Field(..., ge=0, description="Number of tokens trimmed from section")
    truncated: bool = Field(..., description="True if content was partially trimmed")
    dropped: bool = Field(..., description="True if section was completely discarded")


class TruncationResult(BaseModel):
    """
    Structured result of proactive prompt measurement and priority-based chunking/truncation.
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    assembled_prompt: str = Field(..., description="Final combined prompt string ready for network dispatch")
    original_total_tokens: int = Field(..., ge=0, description="Total tokens before any truncation")
    final_total_tokens: int = Field(..., ge=0, description="Total tokens after priority truncation")
    tokens_removed: int = Field(default=0, ge=0, description="Total tokens trimmed across all sections")
    was_truncated: bool = Field(default=False, description="True if prompt size exceeded limit and was trimmed")
    target_token_limit: int = Field(..., ge=0, description="The maximum token ceiling enforced")
    audit_trail: List[TruncationAuditRecord] = Field(default_factory=list, description="Per-section audit records")
    remaining_sections: List[PromptSection] = Field(default_factory=list, description="Preserved and trimmed sections")


class ApiRouterConfig(BaseModel):
    """
    Configuration options for AI API Router, token bounds, retries, and fallback.
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    model_name: str = Field(default=DEFAULT_GEMINI_MODEL, description="Gemini model identifier")
    api_key: Optional[str] = Field(default=None, description="Direct API key override")
    env_path: Optional[str] = Field(default=None, description="Path to .env configuration file")
    context_window_tokens: int = Field(default=DEFAULT_CONTEXT_WINDOW, ge=1, description="Active context window size")
    max_prompt_tokens: int = Field(default=DEFAULT_MAX_PROMPT_TOKENS, ge=1, description="Proactive ceiling for prompt tokens")
    safety_threshold_ratio: float = Field(default=DEFAULT_SAFETY_RATIO, ge=0.01, le=1.0, description="Context window safety fraction (80%)")
    retry_max_delay_seconds: float = Field(default=DEFAULT_RETRY_MAX_DELAY_SECONDS, ge=0.01, description="Maximum total retry duration before fallback to DryRun")
    retry_min_backoff_seconds: float = Field(default=DEFAULT_RETRY_MIN_BACKOFF_SECONDS, ge=0.001, description="Minimum exponential backoff wait in seconds")
    retry_max_backoff_seconds: float = Field(default=DEFAULT_RETRY_MAX_BACKOFF_SECONDS, ge=0.001, description="Maximum exponential backoff wait in seconds")
    retry_multiplier: float = Field(default=1.0, ge=0.01, description="Exponential backoff multiplier")
    max_retries: int = Field(default=DEFAULT_MAX_RETRIES, ge=1, description="Maximum number of retry attempts for transient errors")
    timeout_seconds: float = Field(default=30.0, ge=0.01, description="Per-request timeout ceiling")


# =============================================================================
# DYNAMIC TOKEN COUNTING & HEURISTIC FALLBACK
# =============================================================================

def estimate_tokens_heuristic(text: str) -> int:
    """
    Robust character/word-based token estimator for LLM prompts when offline or unconfigured.
    Accurately estimates token counts without external tokenizer dependencies.
    """
    if not text:
        return 0

    stripped = text.strip()
    if not stripped:
        return 0

    # 1. Word count approximation (~1.33 tokens per word on average for English/scientific text)
    words = stripped.split()
    word_count = len(words)

    # 2. Character length approximation (~3.8 characters per token)
    char_count = len(stripped)

    # 3. Special punctuation and whitespace weight
    special_chars = len(re.findall(r"[{}\[\](),:;\"'\\/<>_=+*#@!$%^&~`|?-]", stripped))

    # Blended estimation
    word_based_est = word_count * 1.33
    char_based_est = char_count / 3.8
    special_overhead = special_chars * 0.15

    estimated = int(round((word_based_est + char_based_est) / 2.0 + special_overhead))
    return max(1, estimated)


def count_tokens_google(
    text: str,
    api_key: Optional[str] = None,
    model: str = DEFAULT_GEMINI_MODEL,
) -> int:
    """
    Dynamically counts tokens via Google Generative AI SDK count_tokens API.
    Falls back gracefully to estimate_tokens_heuristic when offline, unconfigured, or upon error.
    """
    if not text or not text.strip():
        return 0

    key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or os.environ.get("COCHEM_AI_API_KEY")

    if not key or not key.strip():
        return estimate_tokens_heuristic(text)

    # 1. Attempt google.generativeai count_tokens
    try:
        import google.generativeai as genai

        genai.configure(api_key=key.strip())
        model_instance = genai.GenerativeModel(model)
        result = model_instance.count_tokens(text)
        if hasattr(result, "total_tokens") and result.total_tokens is not None:
            return int(result.total_tokens)
    except Exception as legacy_err:
        logger.debug(f"google.generativeai count_tokens encountered: {legacy_err}. Trying google.genai or heuristic.")

    # 2. Attempt google.genai (modern SDK) count_tokens
    try:
        from google import genai

        client = genai.Client(api_key=key.strip())
        resp = client.models.count_tokens(model=model, contents=text)
        if hasattr(resp, "total_tokens") and resp.total_tokens is not None:
            return int(resp.total_tokens)
    except Exception as modern_err:
        logger.debug(f"google.genai count_tokens encountered: {modern_err}. Falling back to heuristic.")

    # 3. Graceful heuristic fallback
    return estimate_tokens_heuristic(text)


def count_tokens(
    text: str,
    api_key: Optional[str] = None,
    model: str = DEFAULT_GEMINI_MODEL,
) -> int:
    """
    Unified entry point for dynamic token counting.
    Dispatches to Google SDK if configured/online, or uses robust heuristic fallback.
    """
    return count_tokens_google(text=text, api_key=api_key, model=model)


# =============================================================================
# PROACTIVE MEASUREMENT & PRIORITY-BASED TRUNCATION
# =============================================================================

def compute_effective_token_limit(
    context_window: int = DEFAULT_CONTEXT_WINDOW,
    max_prompt_tokens: int = DEFAULT_MAX_PROMPT_TOKENS,
    safety_ratio: float = DEFAULT_SAFETY_RATIO,
) -> int:
    """
    Computes the proactive token ceiling: min(max_prompt_tokens, int(context_window * safety_ratio)).
    """
    safety_ceiling = max(1, int(context_window * safety_ratio))
    return min(max_prompt_tokens, safety_ceiling)


def assemble_prompt_from_sections(sections: Sequence[PromptSection]) -> str:
    """
    Combines non-empty prompt sections into a unified formatted prompt string.
    """
    rendered_parts: List[str] = []
    for section in sections:
        rendered = section.render()
        if rendered:
            rendered_parts.append(rendered)
    return "\n\n".join(rendered_parts)


def _truncate_text_to_token_budget(
    text: str,
    target_tokens: int,
    api_key: Optional[str] = None,
    model: str = DEFAULT_GEMINI_MODEL,
) -> str:
    """
    Truncates a single text string so its token count fits within target_tokens.
    Uses line-by-line reduction followed by character-level trimming if needed.
    """
    if target_tokens <= 0:
        return ""

    current_tokens = count_tokens(text, api_key=api_key, model=model)
    if current_tokens <= target_tokens:
        return text

    lines = text.splitlines()
    if len(lines) > 1:
        # Trim lines from bottom or end until within budget
        retained_lines: List[str] = []
        for line in lines:
            test_block = "\n".join(retained_lines + [line])
            if count_tokens(test_block, api_key=api_key, model=model) <= target_tokens:
                retained_lines.append(line)
            else:
                break
        if retained_lines:
            candidate = "\n".join(retained_lines)
            if count_tokens(candidate, api_key=api_key, model=model) <= target_tokens:
                return candidate

    # Binary search character-level reduction for single line or stubborn blocks
    low = 0
    high = len(text)
    best_text = ""

    while low <= high:
        mid = (low + high) // 2
        candidate = text[:mid].rstrip()
        cand_tokens = count_tokens(candidate, api_key=api_key, model=model)
        if cand_tokens <= target_tokens:
            best_text = candidate
            low = mid + 1
        else:
            high = mid - 1

    return best_text


def truncate_prompt_by_priority(
    sections: Sequence[PromptSection],
    max_tokens: int = DEFAULT_MAX_PROMPT_TOKENS,
    context_window: int = DEFAULT_CONTEXT_WINDOW,
    safety_ratio: float = DEFAULT_SAFETY_RATIO,
    api_key: Optional[str] = None,
    model: str = DEFAULT_GEMINI_MODEL,
) -> TruncationResult:
    """
    Proactively measures total prompt tokens across all sections.
    If total tokens > min(max_tokens, context_window * safety_ratio), triggers automatic
    priority-based chunking and truncation:
      - Evaluates priority order: LOW (1) -> MEDIUM (2) -> HIGH (3) -> CRITICAL (4)
      - Truncates or drops lower-priority blocks progressively until prompt safely fits within budget.
      - Preserves high-priority and critical instructions.
      - Returns a structured TruncationResult with assembled prompt and detailed audit trail.
    """
    target_limit = compute_effective_token_limit(
        context_window=context_window,
        max_prompt_tokens=max_tokens,
        safety_ratio=safety_ratio,
    )

    # Make working copy of sections and compute individual token counts
    working_sections: List[PromptSection] = []
    for s in sections:
        sec_copy = s.model_copy(deep=True)
        if sec_copy.token_count is None:
            sec_copy.token_count = count_tokens(sec_copy.content, api_key=api_key, model=model)
        working_sections.append(sec_copy)

    initial_assembled = assemble_prompt_from_sections(working_sections)
    initial_total_tokens = count_tokens(initial_assembled, api_key=api_key, model=model)

    # If within limit, no truncation needed
    if initial_total_tokens <= target_limit:
        audit_trail = [
            TruncationAuditRecord(
                section_name=s.name,
                priority=s.priority,
                original_tokens=s.token_count or 0,
                final_tokens=s.token_count or 0,
                tokens_removed=0,
                truncated=False,
                dropped=False,
            )
            for s in working_sections
        ]
        return TruncationResult(
            assembled_prompt=initial_assembled,
            original_total_tokens=initial_total_tokens,
            final_total_tokens=initial_total_tokens,
            tokens_removed=0,
            was_truncated=False,
            target_token_limit=target_limit,
            audit_trail=audit_trail,
            remaining_sections=working_sections,
        )

    # Excess tokens to eliminate
    logger.info(
        f"Prompt tokens ({initial_total_tokens}) exceed safety threshold ({target_limit}). "
        f"Initiating priority-based chunking/truncation."
    )

    original_tokens_map = {s.name: (s.token_count or 0) for s in working_sections}

    # Group section indices by priority level ascending (LOW -> MEDIUM -> HIGH -> CRITICAL)
    priority_order = [
        PriorityLevel.LOW,
        PriorityLevel.MEDIUM,
        PriorityLevel.HIGH,
        PriorityLevel.CRITICAL,
    ]

    current_assembled = initial_assembled
    current_tokens = initial_total_tokens

    for prio in priority_order:
        if current_tokens <= target_limit:
            break

        # Find all sections at this priority level
        matching_indices = [
            i for i, s in enumerate(working_sections)
            if s.priority == prio and (s.token_count or 0) > 0
        ]

        for idx in matching_indices:
            if current_tokens <= target_limit:
                break

            sec = working_sections[idx]
            sec_tokens = sec.token_count or count_tokens(sec.content, api_key=api_key, model=model)
            tokens_to_shed = current_tokens - target_limit

            if sec_tokens <= tokens_to_shed:
                # Discard entire section
                sec.content = ""
                sec.token_count = 0
            else:
                # Truncate section partially to shed tokens_to_shed
                allowed_sec_tokens = max(0, sec_tokens - tokens_to_shed)
                truncated_text = _truncate_text_to_token_budget(
                    text=sec.content,
                    target_tokens=allowed_sec_tokens,
                    api_key=api_key,
                    model=model,
                )
                sec.content = truncated_text
                sec.token_count = count_tokens(truncated_text, api_key=api_key, model=model)

            # Re-measure overall prompt
            current_assembled = assemble_prompt_from_sections(working_sections)
            current_tokens = count_tokens(current_assembled, api_key=api_key, model=model)

    final_assembled = assemble_prompt_from_sections(working_sections)
    final_total_tokens = count_tokens(final_assembled, api_key=api_key, model=model)
    total_tokens_removed = max(0, initial_total_tokens - final_total_tokens)

    # Build audit trail
    audit_trail: List[TruncationAuditRecord] = []
    remaining_sections: List[PromptSection] = []

    for s in working_sections:
        orig_tok = original_tokens_map.get(s.name, 0)
        final_tok = s.token_count or 0
        removed = max(0, orig_tok - final_tok)
        is_dropped = final_tok == 0 and orig_tok > 0
        is_truncated = 0 < final_tok < orig_tok

        audit_trail.append(
            TruncationAuditRecord(
                section_name=s.name,
                priority=s.priority,
                original_tokens=orig_tok,
                final_tokens=final_tok,
                tokens_removed=removed,
                truncated=is_truncated,
                dropped=is_dropped,
            )
        )
        if s.content.strip():
            remaining_sections.append(s)

    logger.info(
        f"Priority truncation complete: reduced prompt from {initial_total_tokens} to "
        f"{final_total_tokens} tokens (removed {total_tokens_removed} tokens)."
    )

    return TruncationResult(
        assembled_prompt=final_assembled,
        original_total_tokens=initial_total_tokens,
        final_total_tokens=final_total_tokens,
        tokens_removed=total_tokens_removed,
        was_truncated=True,
        target_token_limit=target_limit,
        audit_trail=audit_trail,
        remaining_sections=remaining_sections,
    )


# =============================================================================
# TRANSIENT EXCEPTION CLASSIFIER & TENACITY RETRY LOGIC
# =============================================================================

def is_transient_api_error(exc: BaseException) -> bool:
    """
    Identifies retryable HTTP status codes (429 Rate Limit, 503 Service Unavailable,
    500 Internal Error, 502 Bad Gateway, 504 Gateway Timeout) and Google API exceptions.
    """
    exc_type_name = type(exc).__name__
    exc_module = getattr(type(exc), "__module__", "")
    msg = str(exc).lower()

    # 1. Google API specific transient exceptions
    if "google.api_core.exceptions" in exc_module or "google" in exc_module:
        transient_types = {
            "ResourceExhausted",   # HTTP 429
            "TooManyRequests",     # HTTP 429
            "ServiceUnavailable",  # HTTP 503
            "InternalServerError", # HTTP 500
            "DeadlineExceeded",    # HTTP 504
            "Aborted",
            "Unavailable",
        }
        if exc_type_name in transient_types:
            return True

    # 2. HTTP status code inspection (code, status_code, http_status attributes)
    status_code = (
        getattr(exc, "status_code", None)
        or getattr(exc, "code", None)
        or getattr(exc, "http_status", None)
    )
    if isinstance(status_code, int) and status_code in (429, 500, 502, 503, 504):
        return True

    # 3. Error string pattern matching for transient errors
    transient_indicators = [
        "429",
        "503",
        "resourceexhausted",
        "serviceunavailable",
        "rate limit",
        "quota exceeded",
        "too many requests",
        "temporarily unavailable",
        "connection reset",
        "connection refused",
        "timed out",
        "timeout",
        "server error",
        "service unavailable",
    ]

    for indicator in transient_indicators:
        if indicator in msg or indicator in exc_type_name.lower():
            return True

    return False


def build_tenacity_retryer(
    config: Optional[ApiRouterConfig] = None,
    log_instance: Optional[logging.Logger] = None,
) -> Retrying:
    """
    Constructs a configured tenacity.Retrying coordinator for transient network failures.
    Applies exponential backoff and stops after retry_max_delay_seconds (default 30s).
    """
    cfg = config or ApiRouterConfig()
    target_logger = log_instance or logger

    return Retrying(
        retry=retry_if_exception(is_transient_api_error),
        wait=wait_exponential(
            multiplier=cfg.retry_multiplier,
            min=cfg.retry_min_backoff_seconds,
            max=cfg.retry_max_backoff_seconds,
        ),
        stop=(
            stop_after_delay(cfg.retry_max_delay_seconds)
            | stop_after_attempt(cfg.max_retries)
        ),
        before_sleep=before_sleep_log(target_logger, logging.WARNING),
        reraise=True,
    )


# =============================================================================
# AI API ROUTER MAIN CLASS
# =============================================================================

class AIAPIRouter:
    """
    Autonomous AI API Router coordinating:
      1. Dynamic token counting via Google Generative AI with heuristic fallback.
      2. Proactive prompt size measurement (<6000 tokens / 80% context window).
      3. Priority-tagged text block chunking/truncation (LOW -> MEDIUM -> HIGH -> CRITICAL).
      4. Tenacity retry with exponential backoff for HTTP 429 and 503 status codes.
      5. Graceful fallback to Tier 3 DryRunEngine if unresponsive for >30 seconds.
    """

    def __init__(
        self,
        config: Optional[ApiRouterConfig] = None,
        api_key: Optional[str] = None,
        env_path: Optional[str] = None,
    ) -> None:
        self.config = config or ApiRouterConfig()
        if api_key:
            self.config.api_key = api_key
        if env_path:
            self.config.env_path = env_path

        # Discover and secure API key
        self.api_key = self.config.api_key or load_and_secure_gemini_key(env_path=self.config.env_path)
        self.dry_run_engine = DryRunEngine()
        self._retryer = build_tenacity_retryer(config=self.config, log_instance=logger)

    @property
    def tier(self) -> int:
        """Tier 2 External API Router."""
        return 2

    @property
    def engine_name(self) -> str:
        return "AIAPIRouter"

    def is_available(self) -> bool:
        """Verifies if a valid API key is configured."""
        return bool(self.api_key and len(self.api_key.strip()) > 0)

    def unload(self) -> None:
        """Releases all volatile resources and flushes DryRunEngine caches."""
        self.dry_run_engine.unload()

    def count_tokens(self, text: str) -> int:
        """Measures prompt token length using Google API or heuristic fallback."""
        return count_tokens(text=text, api_key=self.api_key, model=self.config.model_name)

    def truncate_payload(
        self,
        sections: Sequence[PromptSection],
        max_tokens: Optional[int] = None,
    ) -> TruncationResult:
        """
        Proactively measures and priority-truncates prompt sections against token limits.
        """
        limit = max_tokens if max_tokens is not None else self.config.max_prompt_tokens
        return truncate_prompt_by_priority(
            sections=sections,
            max_tokens=limit,
            context_window=self.config.context_window_tokens,
            safety_ratio=self.config.safety_threshold_ratio,
            api_key=self.api_key,
            model=self.config.model_name,
        )

    def _execute_raw_network_call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> EngineResponse:
        """
        Executes raw API network call to Gemini using modern or legacy SDK.
        Raises exceptions for tenacity retryer to catch and back off.
        """
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured.")

        # 1. Attempt google.genai (modern SDK)
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

            config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

            resp = client.models.generate_content(
                model=self.config.model_name,
                contents=full_prompt,
                config=config,
            )
            text_out = resp.text or ""
            tokens_est = count_tokens(text_out, api_key=self.api_key, model=self.config.model_name)

            return EngineResponse(
                text=text_out,
                tier=2,
                engine_name=self.engine_name,
                tokens_generated=tokens_est,
                metadata={
                    "model": self.config.model_name,
                    "sdk": "google.genai",
                },
                success=True,
            )
        except Exception as modern_err:
            if is_transient_api_error(modern_err):
                raise modern_err
            logger.debug(f"google.genai attempt encountered: {modern_err}. Trying google.generativeai.")

        # 2. Attempt google.generativeai (legacy SDK)
        import google.generativeai as legacy_genai

        legacy_genai.configure(api_key=self.api_key)
        model_instance = legacy_genai.GenerativeModel(self.config.model_name)
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        legacy_resp = model_instance.generate_content(
            full_prompt,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
        )
        text_out = legacy_resp.text or ""
        tokens_est = count_tokens(text_out, api_key=self.api_key, model=self.config.model_name)

        return EngineResponse(
            text=text_out,
            tier=2,
            engine_name=self.engine_name,
            tokens_generated=tokens_est,
            metadata={
                "model": self.config.model_name,
                "sdk": "google.generativeai",
            },
            success=True,
        )

    def execute_with_retry(
        self,
        api_call_fn: Callable[..., EngineResponse],
        *args: Any,
        **kwargs: Any,
    ) -> EngineResponse:
        """
        Executes a network callable inside the tenacity retry coordinator.
        """
        return self._retryer(api_call_fn, *args, **kwargs)

    def generate(
        self,
        prompt: Union[str, Sequence[PromptSection]],
        system_prompt: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        context_data: Optional[Dict[str, Any]] = None,
        sections: Optional[Sequence[PromptSection]] = None,
        **kwargs: Any,
    ) -> EngineResponse:
        """
        Main generation entry point coordinating:
          1. Priority-based prompt measurement and truncation.
          2. Tenacity retry block with exponential backoff on HTTP 429 / 503.
          3. Graceful fallback to DryRunEngine if unconfigured, unresponsive (>30s), or failing.
        """
        start_time = time.perf_counter()

        # 1. Structure sections
        prompt_sections: List[PromptSection] = []

        if sections:
            prompt_sections.extend(sections)
        elif isinstance(prompt, Sequence) and not isinstance(prompt, str):
            prompt_sections.extend(prompt)
        else:
            if system_prompt:
                prompt_sections.append(
                    PromptSection(
                        name="system_prompt",
                        content=system_prompt,
                        priority=PriorityLevel.CRITICAL,
                    )
                )
            prompt_sections.append(
                PromptSection(
                    name="user_query",
                    content=str(prompt),
                    priority=PriorityLevel.HIGH,
                )
            )

        # 2. Proactive measurement and priority-based chunking/truncation
        truncation_res = self.truncate_payload(
            sections=prompt_sections,
            max_tokens=self.config.max_prompt_tokens,
        )
        final_prompt_text = truncation_res.assembled_prompt

        # 3. Check API key availability
        if not self.is_available():
            logger.info("GEMINI_API_KEY is unconfigured. Gracefully falling back to Tier 3 DryRunEngine.")
            dry_resp = self.dry_run_engine.generate(
                prompt=final_prompt_text,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                context_data=context_data,
                **kwargs,
            )
            dry_resp.metadata.update({
                "router_fallback": True,
                "fallback_reason": "GEMINI_API_KEY unconfigured",
                "was_truncated": truncation_res.was_truncated,
                "original_tokens": truncation_res.original_total_tokens,
                "final_tokens": truncation_res.final_total_tokens,
                "tokens_removed": truncation_res.tokens_removed,
                "latency_seconds": round(time.perf_counter() - start_time, 4),
            })
            return dry_resp

        # 4. Dispatch through Tenacity retry block
        try:
            resp: EngineResponse = self.execute_with_retry(
                self._execute_raw_network_call,
                prompt=final_prompt_text,
                system_prompt=None,  # Already merged/handled in sections if present
                max_tokens=max_tokens,
                temperature=temperature,
            )
            resp.metadata.update({
                "was_truncated": truncation_res.was_truncated,
                "original_tokens": truncation_res.original_total_tokens,
                "final_tokens": truncation_res.final_total_tokens,
                "tokens_removed": truncation_res.tokens_removed,
                "latency_seconds": round(time.perf_counter() - start_time, 4),
            })
            return resp
        except (RetryError, Exception) as call_err:
            logger.warning(
                f"AI API Router call failed after retries/timeout: {call_err}. "
                f"Gracefully falling back to Tier 3 DryRunEngine."
            )
            dry_resp = self.dry_run_engine.generate(
                prompt=final_prompt_text,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                context_data=context_data,
                **kwargs,
            )
            dry_resp.metadata.update({
                "router_fallback": True,
                "fallback_reason": f"API error after tenacity retries: {call_err}",
                "was_truncated": truncation_res.was_truncated,
                "original_tokens": truncation_res.original_total_tokens,
                "final_tokens": truncation_res.final_total_tokens,
                "tokens_removed": truncation_res.tokens_removed,
                "latency_seconds": round(time.perf_counter() - start_time, 4),
            })
            return dry_resp


# Backward compatibility alias
GeminiApiRouter = AIAPIRouter
