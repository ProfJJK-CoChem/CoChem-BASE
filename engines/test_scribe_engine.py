#!/usr/bin/env python3
"""
Unit Test Suite for CoChem-SCRIBE LLM Engine Initialization & Hardware Routing.

Governed strictly by Phase 3, Task 7 (Section 7.2, Tasks 31-40) of the CoChem-SCRIBE
Software Requirements Specification (SRS), adhering to Method Matrix v4,
the Zero-Mock Anti-Spoofing Protocol, FAIR Data Principles, and the Air-Gap Compliance Directive.
"""

from __future__ import annotations

from tests.test_scribe_engine import (
    test_anti_spoof_ast_compliance,
    test_async_generate_wrapper,
    test_dry_run_engine_generation_and_streaming,
    test_engine_inheritance_and_contract,
    test_factory_router_get_engine,
    test_gemini_engine_airgap_and_permissions,
    test_local_llama_engine_hardware_and_oom_trap,
    test_telemetry_and_audit_logging,
)

__all__ = [
    "test_engine_inheritance_and_contract",
    "test_dry_run_engine_generation_and_streaming",
    "test_async_generate_wrapper",
    "test_gemini_engine_airgap_and_permissions",
    "test_local_llama_engine_hardware_and_oom_trap",
    "test_factory_router_get_engine",
    "test_telemetry_and_audit_logging",
    "test_anti_spoof_ast_compliance",
]
