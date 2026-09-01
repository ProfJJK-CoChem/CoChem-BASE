"""
Physical Zero-Mock Verification Suite for CoChem-Mobile Responsive UI (REQ-MOB-006 - REQ-MOB-008).

Strict Zero-Mock Mandate:
- 100% real threads, real timers, real FileLock concurrency, real ipywidgets.
- Zero mock libraries, zero stubs, zero artificial bypasses.
"""

from __future__ import annotations

import time
from concurrent.futures import Future  # zero-stub anti-spoof Future
from pathlib import Path
from typing import Any

import ipywidgets
import pydantic
import pytest

from cochem.gui.debounce import TrailingDebounce, debounce
from cochem.gui.responsive_layout import (
    ResponsiveMobileLayout,
    inject_mobile_css,
    load_css,
)
from cochem.gui.schemas import (
    QuantumAdvancedConfig,
    resolve_execution_device,
)


class TestQuantumAdvancedConfig:
    """Rigorous physical validation of QuantumAdvancedConfig Pydantic schema."""

    def test_default_initialization(self) -> None:
        """Verify default field values comply with quantum chemistry defaults."""
        config = QuantumAdvancedConfig()
        assert config.grid_level == 3
        assert config.max_scf_cycles == 100
        assert config.soscf_fallback is True
        assert config.conv_tol == 1e-6
        assert config.cuda_acceleration is False

    def test_valid_custom_parameters(self) -> None:
        """Verify valid parameter boundaries can be instantiated."""
        config = QuantumAdvancedConfig(
            grid_level=6,
            max_scf_cycles=350,
            soscf_fallback=False,
            conv_tol=1e-8,
            cuda_acceleration=True,
        )
        assert config.grid_level == 6
        assert config.max_scf_cycles == 350
        assert config.soscf_fallback is False
        assert config.conv_tol == 1e-8
        assert config.cuda_acceleration is True

    @pytest.mark.parametrize("invalid_grid", [0, 8, 9, -1, 10])
    def test_invalid_grid_level_raises(self, invalid_grid: int) -> None:
        """Verify grid levels outside [1, 7] are rejected by schema."""
        with pytest.raises(pydantic.ValidationError):
            QuantumAdvancedConfig(grid_level=invalid_grid)  # type: ignore[arg-type]

    @pytest.mark.parametrize("invalid_scf", [5, 9, 501, 1000, -50])
    def test_invalid_max_scf_cycles_raises(self, invalid_scf: int) -> None:
        """Verify max_scf_cycles outside [10, 500] are rejected."""
        with pytest.raises(pydantic.ValidationError):
            QuantumAdvancedConfig(max_scf_cycles=invalid_scf)

    @pytest.mark.parametrize("invalid_tol", [0.0, -1e-6, 1e-2, 0.5, 2.0])
    def test_invalid_conv_tol_raises(self, invalid_tol: float) -> None:
        """Verify conv_tol outside (0.0, 1e-3] is rejected."""
        with pytest.raises(pydantic.ValidationError):
            QuantumAdvancedConfig(conv_tol=invalid_tol)

    def test_frozen_immutability(self) -> None:
        """Verify instance mutation is prohibited under ConfigDict(frozen=True)."""
        config = QuantumAdvancedConfig()
        with pytest.raises((pydantic.ValidationError, TypeError)):
            config.max_scf_cycles = 200  # type: ignore[misc]

    def test_extra_fields_forbidden(self) -> None:
        """Verify extra unexpected fields are strictly forbidden."""
        with pytest.raises(pydantic.ValidationError):
            QuantumAdvancedConfig(unrecognized_custom_flag=42)  # type: ignore[call-arg]


class TestResolveExecutionDevice:
    """Validation of hardware detection and fallback logic."""

    def test_cuda_disabled_returns_cpu(self) -> None:
        """Verify explicit cuda_acceleration=False always returns 'cpu'."""
        config = QuantumAdvancedConfig(cuda_acceleration=False)
        device = resolve_execution_device(config)
        assert device == "cpu"

    def test_cuda_fallback_resolution(self) -> None:
        """Verify fallback when cuda_acceleration=True."""
        config = QuantumAdvancedConfig(cuda_acceleration=True)
        device = resolve_execution_device(config)
        assert device in ("cpu", "cuda")


class TestAirGapCSSCompliance:
    """Verification of air-gapped responsive CSS stylesheets."""

    def test_load_css_airgap_and_structure(self) -> None:
        """Verify CSS contains zero external URLs, CDN imports, and adheres to WCAG touch targets."""
        css = load_css()
        assert len(css) > 200

        # Strict Air-Gap Verification: Zero HTTP/HTTPS links, Zero @import network fetches
        assert "http://" not in css
        assert "https://" not in css
        assert "@import" not in css

        # WCAG 2.1 AA 44x44px Touch Target Verification
        assert "min-width: 44px" in css
        assert "min-height: 44px" in css

        # Sticky Dispatch Action Bar Verification
        assert ".cochem-sticky-dispatch" in css
        assert "position: sticky" in css
        assert "bottom: 0" in css
        assert "z-index: 1000" in css

        # Responsive Media Query Column Collapse Verification
        assert "@media (max-width: 767.98px)" in css
        assert "grid-template-columns: 1fr" in css

    def test_inject_mobile_css_widget(self) -> None:
        """Verify inject_mobile_css creates valid ipywidgets.HTML element."""
        widget = inject_mobile_css()
        assert isinstance(widget, ipywidgets.HTML)
        assert "<style>" in widget.value
        assert "</style>" in widget.value
        assert ".cochem-sticky-dispatch" in widget.value


class TestTrailingDebounce:
    """Physical multi-threading verification of TrailingDebounce coordinator."""

    def test_rapid_invocations_only_executes_final(self) -> None:
        """
        Verify that 10 rapid invocations within the debounce window
        result in only a single final execution.
        """
        recorded_calls: list[int] = []

        def target_handler(val: int) -> None:
            recorded_calls.append(val)

        debouncer = TrailingDebounce(target_handler, wait_seconds=0.25)
        assert debouncer.wait_seconds == 0.25
        assert debouncer.is_pending() is False

        # Fire 10 rapid invocations
        for i in range(10):
            debouncer(i)
            time.sleep(0.01)

        assert debouncer.is_pending() is True
        assert debouncer.call_count == 10
        assert len(recorded_calls) == 0

        # Wait for debounce window (0.25 s) to expire with margin
        time.sleep(0.35)

        assert debouncer.is_pending() is False
        assert len(recorded_calls) == 1
        assert recorded_calls[0] == 9
        assert debouncer.execution_count == 1

    def test_cancel_aborts_execution(self) -> None:
        """Verify cancellation immediately stops any scheduled execution."""
        recorded_calls: list[str] = []

        def target_handler(msg: str) -> None:
            recorded_calls.append(msg)

        debouncer = TrailingDebounce(target_handler, wait_seconds=0.25)
        debouncer("first_run")
        assert debouncer.is_pending() is True

        debouncer.cancel()
        assert debouncer.is_pending() is False

        # Wait to confirm timer was truly cancelled
        time.sleep(0.35)
        assert len(recorded_calls) == 0

    def test_flush_immediately_executes(self) -> None:
        """Verify flush triggers immediate execution and returns value."""
        def adder(a: int, b: int) -> int:
            return a + b

        debouncer = TrailingDebounce(adder, wait_seconds=0.25)
        debouncer(14, 28)
        assert debouncer.is_pending() is True

        result = debouncer.flush()
        assert result == 42
        assert debouncer.is_pending() is False
        assert debouncer.execution_count == 1

        # Subsequent timer should not re-run
        time.sleep(0.35)
        assert debouncer.execution_count == 1

    def test_debounce_decorator_usage(self) -> None:
        """Verify @debounce decorator wrapping behavior."""
        invoked_values: list[float] = []

        @debounce(wait_seconds=0.15)
        def on_update(v: float) -> None:
            invoked_values.append(v)

        on_update(1.0)
        on_update(2.0)
        on_update(3.5)

        assert on_update.is_pending() is True
        time.sleep(0.25)

        assert on_update.is_pending() is False
        assert len(invoked_values) == 1
        assert invoked_values[0] == 3.5


class TestResponsiveMobileLayout:
    """Physical verification of ResponsiveMobileLayout widget composition and async pipeline."""

    def test_layout_initialization_and_progressive_disclosure(self) -> None:
        """Verify widget tree initialization, collapsed accordion, and sticky dispatch button."""
        layout = ResponsiveMobileLayout(
            default_formula="CH4",
            default_method="PBE0",
            default_basis="def2-SVP",
        )

        try:
            # 1. Verify primary inputs
            assert layout.formula_input.value == "CH4"
            assert layout.method_dropdown.value == "PBE0"
            assert layout.basis_dropdown.value == "def2-SVP"

            # 2. Progressive Disclosure Accordion: must be collapsed by default (selected_index=None)
            assert layout.accordion.selected_index is None
            assert layout.accordion.get_title(0) == "Advanced Quantum Settings"

            # 3. Sticky Dispatch Action Button
            assert layout.execute_button.description == "Execute Pipeline"
            assert "cochem-btn-primary" in layout.execute_button._dom_classes
            assert "cochem-sticky-dispatch" in layout.sticky_dispatch_bar._dom_classes

            # 4. Master Layout Container & Render
            root_widget = layout.render()
            assert isinstance(root_widget, ipywidgets.VBox)
            assert "cochem-mobile-layout" in root_widget._dom_classes

            # 5. Advanced Config Generation
            cfg = layout.get_advanced_config()
            assert isinstance(cfg, QuantumAdvancedConfig)
            assert cfg.grid_level == 3
            assert cfg.max_scf_cycles == 100
            assert cfg.soscf_fallback is True
            assert cfg.conv_tol == 1e-6
            assert cfg.cuda_acceleration is False
        finally:
            layout.close()

    def test_slider_debounced_updates(self) -> None:
        """Verify that slider changes trigger debounced config updates."""
        layout = ResponsiveMobileLayout()

        try:
            assert layout._config_updates_count == 0

            # Adjust slider values rapidly
            layout.grid_slider.value = 5
            layout.max_scf_slider.value = 250
            layout.conv_tol_slider.value = 1e-8

            # Wait for debounce window (250ms) to settle
            time.sleep(0.35)

            assert layout._config_updates_count >= 1
            cfg = layout.get_advanced_config()
            assert cfg.grid_level == 5
            assert cfg.max_scf_cycles == 250
            assert cfg.conv_tol == 1e-8
        finally:
            layout.close()

    def test_non_blocking_pipeline_execution_with_filelock(self, tmp_path: Path) -> None:
        """
        Verify async background dispatch executes via ThreadPoolExecutor
        and coordinates using real physical FileLock.
        """
        layout = ResponsiveMobileLayout(
            default_formula="H2O",
            default_method="B3LYP",
            default_basis="def2-TZVP",
        )

        test_lock_file = tmp_path / "cochem_mobile_test.lock"
        callback_results: list[Any] = []

        def on_done(res: Any) -> None:
            callback_results.append(res)

        try:
            # Trigger background execution
            fut = layout.execute_pipeline(callback=on_done, lock_path=test_lock_file)
            assert isinstance(fut, Future)

            # Wait for future resolution (timeout prevents infinite hang)
            result = fut.result(timeout=10.0)

            assert result["status"] == "SUCCESS"
            assert result["formula"] == "H2O"
            assert result["method"] == "B3LYP"
            assert result["basis"] == "def2-TZVP"
            assert result["resolved_device"] in ("cpu", "cuda")
            assert result["elapsed_seconds"] > 0.0

            # Ensure callback received the result
            time.sleep(0.1)
            assert len(callback_results) == 1
            assert callback_results[0]["status"] == "SUCCESS"
        finally:
            layout.close()
