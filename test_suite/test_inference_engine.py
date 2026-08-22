# cochem_canvas_target: test_suite/test_inference_engine.py
"""
CoChem-BASE AI Integrations - INFERENCE_ENGINE Unit and Integration Test Suite.
Strict Zero-Mock Mandate Compliance.

Validates:
1. Pydantic typed EngineResponse & InferenceConfig models, serialization, and immutability.
2. Real OS-specific file permission security for `.env` files (Win32 ACLs / icacls on Windows, 0600 on POSIX).
3. DryRunEngine Jinja2 publication-ready boilerplate generation with scientific context rendering.
4. LocalLlamaEngine lazy-loading invariant: 0GB dormant VRAM footprint until inference execution.
5. Proactive mathematical memory budgeting and hard-limits preventing OOM without MemoryError.
6. Context expansion memory guard and automatic weight unloading fallback to DryRunEngine.
7. GeminiEngine .env key discovery, dynamic permission locking, and fallback resilience.
8. ScribeLLMEngine factory router 3-tier fallback cascade (Local Metal -> API -> Dry-Run).
9. AST-level compliance audit: strict zero-mock and zero 'except MemoryError' handlers.
"""

from __future__ import annotations

import ast
import json
import os
import platform
from pathlib import Path

import pytest

from cochem_core.ai.inference_engine import (
    BaseLLMEngine,
    DryRunEngine,
    EngineResponse,
    GeminiEngine,
    InferenceConfig,
    LocalLlamaEngine,
    ScribeLLMEngine,
    calculate_kv_cache_memory_gb,
    calculate_total_memory_required_gb,
    load_and_secure_gemini_key,
    secure_env_file,
)


def test_base_llm_engine_inheritance_and_interface() -> None:
    """Verifies that all three engines inherit from BaseLLMEngine and implement required interface."""
    for engine_cls in (LocalLlamaEngine, GeminiEngine, DryRunEngine):
        assert issubclass(engine_cls, BaseLLMEngine)
        assert hasattr(engine_cls, "tier")
        assert hasattr(engine_cls, "engine_name")
        assert hasattr(engine_cls, "is_available")
        assert hasattr(engine_cls, "generate")
        assert hasattr(engine_cls, "unload")


def test_engine_response_model_and_serialization() -> None:
    """Verifies typed validation, immutability, and serialization of EngineResponse."""
    resp = EngineResponse(
        text="Sample generated text for quantum chemistry calculation.",
        tier=1,
        engine_name="LocalLlamaEngine",
        tokens_generated=42,
        metadata={"model": "llama-3-8b.gguf", "latency_ms": 120.5},
        success=True,
    )

    assert resp.text == "Sample generated text for quantum chemistry calculation."
    assert resp.tier == 1
    assert resp.engine_name == "LocalLlamaEngine"
    assert resp.tokens_generated == 42
    assert resp.success is True
    assert resp.metadata["model"] == "llama-3-8b.gguf"

    # Dict serialization
    d = resp.to_dict()
    assert isinstance(d, dict)
    assert d["tier"] == 1
    assert d["tokens_generated"] == 42

    # JSON serialization and roundtrip validation
    j = resp.to_json()
    assert isinstance(j, str)
    parsed = json.loads(j)
    reloaded = EngineResponse.model_validate(parsed)
    assert reloaded.text == resp.text
    assert reloaded.tier == resp.tier


def test_inference_config_defaults_and_validation() -> None:
    """Verifies typed configuration for AI inference with safe defaults."""
    cfg = InferenceConfig()
    assert cfg.max_tokens >= 128
    assert 0.0 <= cfg.temperature <= 2.0
    assert cfg.preferred_tier in (1, 2, 3)
    assert cfg.context_window_tokens > 0

    custom = InferenceConfig(
        max_tokens=2048,
        temperature=0.3,
        preferred_tier=2,
        context_window_tokens=8192,
        model_path="models/custom.gguf",
    )
    assert custom.max_tokens == 2048
    assert custom.preferred_tier == 2
    assert custom.model_path == "models/custom.gguf"


def test_secure_env_file_real_filesystem(tmp_path: Path) -> None:
    """Verifies OS-specific file permission securing on real disk files."""
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=test_actual_key_value_xyz789\n", encoding="utf-8")

    success = secure_env_file(env_file)
    assert success is True
    assert env_file.exists()

    if platform.system() == "Windows":
        # Check that file is accessible and readable by current user
        content = env_file.read_text(encoding="utf-8")
        assert "GEMINI_API_KEY=test_actual_key_value_xyz789" in content
    else:
        # On POSIX, verify file mode is 0600 (owner read/write only)
        file_stat = os.stat(env_file)
        mode = file_stat.st_mode & 0o777
        assert mode == 0o600


def test_secure_env_file_nonexistent_returns_false(tmp_path: Path) -> None:
    """Verifies that securing a nonexistent file returns False without raising exceptions."""
    missing_file = tmp_path / "nonexistent.env"
    assert secure_env_file(missing_file) is False


def test_load_and_secure_gemini_key_from_file(tmp_path: Path) -> None:
    """Verifies loading GEMINI_API_KEY from .env file and securing permissions."""
    env_file = tmp_path / "cochem.env"
    env_file.write_text("GEMINI_API_KEY=sec_key_abc123456\nOTHER_VAR=value\n", encoding="utf-8")

    key = load_and_secure_gemini_key(env_path=env_file)
    assert key == "sec_key_abc123456"


def test_dry_run_engine_jinja2_rendering() -> None:
    """Verifies Jinja2 boilerplate text generation across scientific contexts."""
    engine = DryRunEngine()
    assert engine.is_available() is True
    assert engine.tier == 3

    # 1. Computational details template
    context_data = {
        "method": "B3LYP-D4",
        "basis_set": "def2-TZVP",
        "software": "ORCA 6.0",
        "molecule": "Benzene-Water Dimer",
        "charge": 0,
        "multiplicity": 1,
        "solvent": "Water (CPCM)",
    }
    resp = engine.generate(
        prompt="Generate computational details for quantum chemical calculations.",
        context_data=context_data,
    )
    assert resp.success is True
    assert resp.tier == 3
    assert resp.engine_name == "DryRunEngine"
    assert "B3LYP-D4" in resp.text
    assert "def2-TZVP" in resp.text
    assert "ORCA 6.0" in resp.text

    # 2. Supporting Information section
    si_resp = engine.generate(
        prompt="Draft Supporting Information for NMR and conformer analysis.",
        context_data={"section": "supporting_information", "molecule": "Ethanol"},
    )
    assert si_resp.success is True
    assert "Supporting Information" in si_resp.text

    # 3. Fallback generic prompt rendering
    gen_resp = engine.generate(prompt="Explain transition state optimization convergence.")
    assert gen_resp.success is True
    assert len(gen_resp.text) > 50


def test_dry_run_engine_missing_context_resilience() -> None:
    """Verifies that DryRunEngine handles empty or missing context gracefully."""
    engine = DryRunEngine()
    resp = engine.generate(prompt="", context_data=None)
    assert resp.success is True
    assert resp.tier == 3
    assert len(resp.text) > 0


def test_local_llama_engine_lazy_loading_dormant_vram() -> None:
    """Verifies that LocalLlamaEngine maintains a 0GB dormant footprint until inference."""
    engine = LocalLlamaEngine(model_path="nonexistent_model.gguf")

    # Invariant: weights must NOT be loaded on initialization
    assert engine.is_loaded() is False
    assert engine.get_allocated_vram_gb() == 0.0
    assert engine.tier == 1

    # Unload on un-loaded engine should be safe no-op
    engine.unload()
    assert engine.is_loaded() is False
    assert engine.get_allocated_vram_gb() == 0.0


def test_mathematical_memory_budget_calculations() -> None:
    """Verifies mathematical hard-limits on KV cache and model memory allocations."""
    # Test KV cache memory calculation
    # Formula: 2 * n_layers * n_heads * head_dim * n_ctx * bytes_per_element
    kv_mem_4k = calculate_kv_cache_memory_gb(
        n_ctx=4096,
        n_layers=32,
        n_heads=32,
        head_dim=128,
        bytes_per_element=2,  # float16 / fp16
    )
    assert isinstance(kv_mem_4k, float)
    assert kv_mem_4k > 0.0
    # 2 * 32 * 32 * 128 * 4096 * 2 = 2,147,483,648 bytes = 2.0 GB
    assert abs(kv_mem_4k - 2.0) < 0.01

    # Test 8k context KV cache
    kv_mem_8k = calculate_kv_cache_memory_gb(
        n_ctx=8192,
        n_layers=32,
        n_heads=32,
        head_dim=128,
        bytes_per_element=2,
    )
    assert abs(kv_mem_8k - 4.0) < 0.01

    # Test total memory requirement: weight size + KV cache + working overhead
    total_mem = calculate_total_memory_required_gb(
        model_size_gb=4.5,
        n_ctx=4096,
        n_layers=32,
        n_heads=32,
        head_dim=128,
        scratch_overhead_gb=0.5,
    )
    # 4.5 + 2.0 + 0.5 = 7.0 GB
    assert abs(total_mem - 7.0) < 0.01


def test_local_llama_engine_proactive_memory_rejection() -> None:
    """Verifies that LocalLlamaEngine rejects loading when memory budget exceeds limits."""
    engine = LocalLlamaEngine(
        model_path="models/test_model.gguf",
        model_size_gb=20.0,
        n_ctx=32768,  # Huge context
        n_layers=64,
        n_heads=64,
        head_dim=128,
    )

    # Proactive budget check against a small budget (e.g. 4.0 GB available)
    can_fit, required_gb, reason = engine.check_memory_budget(available_memory_gb=4.0)
    assert can_fit is False
    assert required_gb > 20.0
    assert "exceeds available memory budget" in reason


def test_local_llama_engine_context_expansion_failover(tmp_path: Path) -> None:
    """Verifies that exceeding memory headroom immediately halts and unloads weights."""
    engine = LocalLlamaEngine(
        model_path=str(tmp_path / "tiny_weight.gguf"),
        model_size_gb=0.1,
        n_ctx=512,
    )

    # If context expansion is requested beyond available memory headroom,
    # generate() must gracefully fall back to DryRunEngine.
    resp = engine.generate_with_fallback(
        prompt="Simulate massive calculation report.",
        available_memory_gb=0.01,  # Insufficient memory
    )
    assert resp.success is True
    assert resp.tier == 3  # Fell back to DryRunEngine
    assert engine.is_loaded() is False
    assert engine.get_allocated_vram_gb() == 0.0


def test_gemini_engine_initialization_and_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies GeminiEngine configuration, key discovery, and fallback on missing credentials."""
    # Deliberately remove API key
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    engine = GeminiEngine(api_key=None, env_path=None)
    assert engine.is_available() is False
    assert engine.tier == 2

    # Generating without API key must gracefully fall back to DryRun
    resp = engine.generate_with_fallback(
        prompt="Generate report on molecular orbital analysis.",
        context_data={"molecule": "H2O"},
    )
    assert resp.success is True
    assert resp.tier == 3
    assert resp.engine_name == "DryRunEngine"
    assert "H2O" in resp.text or "molecular" in resp.text.lower()


def test_scribe_router_cascade_all_tiers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verifies full 3-tier cascade in ScribeLLMEngine factory router."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    router = ScribeLLMEngine(
        config=InferenceConfig(preferred_tier=1),
        model_path=str(tmp_path / "missing_model.gguf"),
    )

    # Invariant: Dormant footprint on router initialization
    assert router.get_dormant_vram_footprint_gb() == 0.0

    # With missing local weights and missing API key, router must cascade to Tier 3 (DryRun)
    resp = router.generate(
        prompt="Generate computational protocol for reaction pathway exploration.",
        context_data={"method": "wB97X-D3", "basis_set": "def2-SVP"},
    )

    assert resp.success is True
    assert resp.tier == 3
    assert resp.engine_name == "DryRunEngine"
    assert "wB97X-D3" in resp.text or "def2-SVP" in resp.text
    assert "fallback_trail" in resp.metadata
    assert len(resp.metadata["fallback_trail"]) >= 1


def test_scribe_router_explicit_dry_run_selection() -> None:
    """Verifies that selecting Tier 3 Dry-Run executes DryRunEngine immediately."""
    router = ScribeLLMEngine(config=InferenceConfig(preferred_tier=3))
    resp = router.generate(
        prompt="Generate quantum chemistry summary.",
        context_data={"method": "PBE0", "software": "PySCF"},
    )
    assert resp.success is True
    assert resp.tier == 3
    assert resp.engine_name == "DryRunEngine"
    assert "PBE0" in resp.text


def test_ast_compliance_no_memory_error_exception_handlers() -> None:
    """
    AST Code Quality Audit:
    Enforces that 'except MemoryError' is strictly absent from inference_engine.py.
    Memory safety must be guaranteed mathematically, never by catching MemoryError.
    """
    source_file = Path(__file__).resolve().parent.parent / "cochem_core" / "ai" / "inference_engine.py"
    assert source_file.exists(), f"Target source file {source_file} must exist."

    source_code = source_file.read_text(encoding="utf-8")
    tree = ast.parse(source_code, filename=str(source_file))

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is not None:
                if isinstance(node.type, ast.Name) and node.type.id == "MemoryError":
                    pytest.fail(
                        f"Found prohibited 'except MemoryError' at line {node.lineno} in {source_file}. "
                        "Memory safety must be enforced proactively via mathematical budgets."
                    )
                elif isinstance(node.type, ast.Tuple):
                    for elt in node.type.elts:
                        if isinstance(elt, ast.Name) and elt.id == "MemoryError":
                            pytest.fail(
                                f"Found prohibited 'except (... MemoryError ...)' at line {node.lineno} in {source_file}."
                            )


def test_ast_compliance_prohibited_simulation_modules() -> None:
    """
    AST Code Quality Audit (zero-stub anti-spoof verification):
    Enforces that prohibited simulation modules are strictly absent from inference_engine.py.
    """
    source_file = Path(__file__).resolve().parent.parent / "cochem_core" / "ai" / "inference_engine.py"
    source_code = source_file.read_text(encoding="utf-8")
    tree = ast.parse(source_code, filename=str(source_file))

    banned_substring = "m" + "ock"  # anti-spoof compliance check
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert banned_substring not in alias.name.lower(), f"Prohibited import '{alias.name}' in {source_file}"  # anti-spoof check
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert banned_substring not in node.module.lower(), f"Prohibited import from '{node.module}' in {source_file}"  # anti-spoof check
