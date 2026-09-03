"""Unit tests for unified hierarchical configuration manager.

Verifies resolution hierarchy (CLI > ENV > Project TOML > Legacy > Defaults),
environment variable typed coercion, legacy deprecation warnings, path sanitization,
and Pydantic v2 immutability.
"""

import os
import warnings
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.cochem.core.config import CoChemConfigManager, sanitize_path


def test_config_defaults(tmp_path: Path) -> None:
    """Verify built-in default values across all sections."""
    manager = CoChemConfigManager(project_root=tmp_path)
    config = manager.load_config()

    assert config.core.log_level == "INFO"
    assert config.core.max_workers == 4
    assert config.telemetry.ring_buffer_capacity == 65536
    assert config.telemetry.mask_secrets is True
    assert config.database.wal_mode is True
    assert config.database.busy_timeout_ms == 5000
    assert config.qmmm.default_memory_mb == 4096


def test_config_hierarchy_precedence(tmp_path: Path) -> None:
    """Verify CLI overrides ENV which overrides project TOML which overrides defaults."""
    project_toml = tmp_path / "cochem.toml"
    project_toml.write_text(
        """
[core]
log_level = "DEBUG"
max_workers = 8

[telemetry]
ring_buffer_capacity = 32768
""",
        encoding="utf-8",
    )

    old_env = os.environ.get("COCHEM__CORE__MAX_WORKERS")
    os.environ["COCHEM__CORE__MAX_WORKERS"] = "16"
    try:
        # 1. TOML + ENV (ENV wins for max_workers=16, TOML sets log_level=DEBUG)
        manager = CoChemConfigManager(project_root=tmp_path)
        cfg1 = manager.load_config()
        assert cfg1.core.log_level == "DEBUG"
        assert cfg1.core.max_workers == 16
        assert cfg1.telemetry.ring_buffer_capacity == 32768

        # 2. CLI override takes top precedence (max_workers=32)
        manager_cli = CoChemConfigManager(
            project_root=tmp_path,
            cli_overrides={"core__max_workers": 32},
        )
        cfg2 = manager_cli.load_config()
        assert cfg2.core.max_workers == 32
        assert cfg2.core.log_level == "DEBUG"
    finally:
        if old_env is not None:
            os.environ["COCHEM__CORE__MAX_WORKERS"] = old_env
        else:
            os.environ.pop("COCHEM__CORE__MAX_WORKERS", None)


def test_env_var_typed_coercion(tmp_path: Path) -> None:
    """Verify environment variables undergo typed coercion into booleans, floats, and integers."""
    keys_to_clean = [
        "COCHEM__TELEMETRY__MASK_SECRETS",
        "COCHEM__ORCHESTRATION__HEARTBEAT_INTERVAL_SEC",
        "COCHEM__CORE__MAX_WORKERS",
    ]
    saved_env = {k: os.environ.get(k) for k in keys_to_clean}

    os.environ["COCHEM__TELEMETRY__MASK_SECRETS"] = "false"
    os.environ["COCHEM__ORCHESTRATION__HEARTBEAT_INTERVAL_SEC"] = "25.5"
    os.environ["COCHEM__CORE__MAX_WORKERS"] = "12"

    try:
        manager = CoChemConfigManager(project_root=tmp_path)
        config = manager.load_config()

        assert config.telemetry.mask_secrets is False
        assert config.orchestration.heartbeat_interval_sec == 25.5
        assert config.core.max_workers == 12
    finally:
        for k, v in saved_env.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)


def test_legacy_cochem_json_deprecation_warning(tmp_path: Path) -> None:
    """Verify loading legacy cochem.json emits a DeprecationWarning while parsing values."""
    legacy_json = tmp_path / "cochem.json"
    legacy_json.write_text(
        '{"core": {"log_level": "WARNING", "max_workers": 6}}',
        encoding="utf-8",
    )

    manager = CoChemConfigManager(project_root=tmp_path)
    with warnings.catch_warnings(record=True) as recorded_warnings:
        warnings.simplefilter("always")
        config = manager.load_config()

        deprecation_hits = [
            w for w in recorded_warnings if issubclass(w.category, DeprecationWarning)
        ]
        assert len(deprecation_hits) >= 1
        assert "cochem.json" in str(deprecation_hits[0].message)
        assert "deprecated" in str(deprecation_hits[0].message).lower()

    assert config.core.log_level == "WARNING"
    assert config.core.max_workers == 6


def test_path_sanitization() -> None:
    """Verify relative paths, environment variables, and user home expansion."""
    resolved = sanitize_path("./test_scratch")
    assert resolved.is_absolute()
    assert resolved.name == "test_scratch"

    old_val = os.environ.get("TEST_CHEM_DIR")
    os.environ["TEST_CHEM_DIR"] = "node_scratch"
    try:
        var_resolved = sanitize_path("$TEST_CHEM_DIR/calc")
        assert var_resolved.is_absolute()
        assert "node_scratch" in str(var_resolved)
    finally:
        if old_val is not None:
            os.environ["TEST_CHEM_DIR"] = old_val
        else:
            os.environ.pop("TEST_CHEM_DIR", None)


def test_config_immutability(tmp_path: Path) -> None:
    """Verify root and child configuration models enforce Pydantic v2 frozen immutability."""
    manager = CoChemConfigManager(project_root=tmp_path)
    config = manager.load_config()

    with pytest.raises(ValidationError):
        config.core.max_workers = 100  # type: ignore

    with pytest.raises(ValidationError):
        config.database.busy_timeout_ms = 1000  # type: ignore
