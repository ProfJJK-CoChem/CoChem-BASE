# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
CoChem-SCRIBE Engine Package.

Hardware-aware AI execution factory handling remote API requests,
local GGUF models, and deterministic offline dry-runs.
"""

from .scribe_engine import (
    DRY_RUN_OUTPUT_TEXT,
    DryRunEngine,
    GeminiEngine,
    LocalLlamaEngine,
    ScribeLLMEngine,
    ScribeNetworkException,
    calculate_model_cost,
    estimate_token_count,
    get_default_artifacts_dir,
    get_default_audit_log_path,
    get_default_env_path,
    get_default_models_dir,
    get_default_report_archive_dir,
    get_engine,
    record_audit_event,
)
from .scribe_inference import (
    FALLBACK_INSIGHTS_NOTICE,
    FALLBACK_JUSTIFICATIONS_NOTICE,
    FALLBACK_METHODOLOGY_NOTICE,
    ScribeInferenceError,
    ScribeInferenceManager,
    ScribeInferenceOutput,
    ScribeOutputSchema,
    ScribeTimeoutError,
    ScribeValidationError,
)

__all__ = [
    "DRY_RUN_OUTPUT_TEXT",
    "ScribeNetworkException",
    "ScribeLLMEngine",
    "LocalLlamaEngine",
    "GeminiEngine",
    "DryRunEngine",
    "get_engine",
    "record_audit_event",
    "get_default_artifacts_dir",
    "get_default_report_archive_dir",
    "get_default_audit_log_path",
    "get_default_env_path",
    "get_default_models_dir",
    "estimate_token_count",
    "calculate_model_cost",
    "ScribeInferenceError",
    "ScribeTimeoutError",
    "ScribeValidationError",
    "ScribeInferenceOutput",
    "ScribeOutputSchema",
    "ScribeInferenceManager",
    "FALLBACK_METHODOLOGY_NOTICE",
    "FALLBACK_INSIGHTS_NOTICE",
    "FALLBACK_JUSTIFICATIONS_NOTICE",
]
