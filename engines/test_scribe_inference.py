#!/usr/bin/env python3
"""
Unit Test Suite for CoChem-SCRIBE Inference Engine & Hallucination Traps.

Governed strictly by Phase 3, Task 8 of the CoChem-SCRIBE Software Requirements
Specification (SRS), adhering to Method Matrix v4, the Zero-Mock Anti-Spoofing Protocol
(LESSON-2026-AUDIT-007), FAIR Data Principles, and the Air-Gap Compliance Directive.
"""

from __future__ import annotations

from tests.test_scribe_inference import (
    test_anti_spoof_ast_compliance,
    test_cli_preflight_execution,
    test_default_engine_dynamic_loading,
    test_jinja2_and_latex_tag_preservation,
    test_markdown_syntax_checking_and_autorepair,
    test_math_airgap_regex_scrubber_detection,
    test_schema_validation_and_json_parsing,
    test_synchronous_execute_inference_wrapper,
    test_telemetry_and_audit_logging,
    test_three_strike_raise_on_fallback_mode,
    test_three_strike_retry_and_graceful_degradation,
    test_timeout_watchdog_execution,
)

__all__ = [
    "test_schema_validation_and_json_parsing",
    "test_math_airgap_regex_scrubber_detection",
    "test_jinja2_and_latex_tag_preservation",
    "test_markdown_syntax_checking_and_autorepair",
    "test_timeout_watchdog_execution",
    "test_three_strike_retry_and_graceful_degradation",
    "test_three_strike_raise_on_fallback_mode",
    "test_synchronous_execute_inference_wrapper",
    "test_telemetry_and_audit_logging",
    "test_default_engine_dynamic_loading",
    "test_anti_spoof_ast_compliance",
    "test_cli_preflight_execution",
]
