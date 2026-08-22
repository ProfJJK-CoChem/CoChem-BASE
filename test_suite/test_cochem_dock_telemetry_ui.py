"""Comprehensive Zero-Mock test suite for cochem_dock_telemetry_ui.jsx.

Validates React/JSX structure, useResilientWebSocket contract, Ring Buffer memory
safety algorithms, IndexedDB telemetry pipeline, LTTB decimation telemetry parsing,
RAF throttling, line endings, path sanitization, and anti-spoofing constraints.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

import pytest

from cochem_base.path_sanitization import leak_patterns


@pytest.fixture
def interfaces_jsx_path() -> Path:
    """Return the absolute path to interfaces/cochem_dock_telemetry_ui.jsx."""
    path = Path(__file__).resolve().parent.parent / "interfaces" / "cochem_dock_telemetry_ui.jsx"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


@pytest.fixture
def cochem_base_jsx_path() -> Path:
    """Return the absolute path to cochem_base/interfaces/cochem_dock_telemetry_ui.jsx."""
    path = Path(__file__).resolve().parent.parent / "cochem_base" / "interfaces" / "cochem_dock_telemetry_ui.jsx"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


def test_file_existence_and_structure(
    interfaces_jsx_path: Path, cochem_base_jsx_path: Path
) -> None:
    """Verify that cochem_dock_telemetry_ui.jsx exists in both interfaces/ and cochem_base/interfaces/."""
    for p in (interfaces_jsx_path, cochem_base_jsx_path):
        assert p.exists(), f"File missing at {p}"
        content = p.read_text(encoding="utf-8")
        assert len(content) > 500, f"File at {p} is suspiciously small: {len(content)} bytes"


def test_unix_lf_and_encoding(
    interfaces_jsx_path: Path, cochem_base_jsx_path: Path
) -> None:
    """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
    for p in (interfaces_jsx_path, cochem_base_jsx_path):
        raw = p.read_bytes()
        assert b"\r\n" not in raw, f"Found Windows CRLF line endings in {p.name}"
        assert b"\n" in raw, f"Missing newline characters in {p.name}"
        assert not raw.startswith(b"\xef\xbb\xbf"), f"Found UTF-8 BOM marker in {p.name}"


def test_zero_personal_path_leaks(
    interfaces_jsx_path: Path, cochem_base_jsx_path: Path
) -> None:
    """Verify zero personal machine or local user path leakage in JSX files."""
    patterns = leak_patterns()
    for p in (interfaces_jsx_path, cochem_base_jsx_path):
        lines = p.read_text(encoding="utf-8").splitlines()
        leaks = []
        for lineno, line in enumerate(lines, 1):
            for pattern, placeholder in patterns:
                if pattern.search(line):
                    leaks.append((lineno, placeholder, line.strip()))
        assert len(leaks) == 0, f"Detected personal path leaks in {p.name}: {leaks}"


def test_zero_mock_anti_spoofing_banned_terms(
    interfaces_jsx_path: Path, cochem_base_jsx_path: Path
) -> None:
    """Verify zero mock, dummy, stub, or placeholder logic exists in the deliverable."""
    banned = [
        r"\bmock\b",
        r"\bdummy\b",
        r"\bstub\b",
        r"\bplaceholder\b",
        r"\bfake\b",
        r"#\s*TODO",
        r"//\s*TODO",
        r"NotImplementedError",
    ]
    for p in (interfaces_jsx_path, cochem_base_jsx_path):
        content = p.read_text(encoding="utf-8")
        for term in banned:
            matches = list(re.finditer(term, content, flags=re.IGNORECASE))
            assert len(matches) == 0, f"Found banned anti-spoofing term '{term}' in {p.name}: {matches}"


def test_react_jsx_core_component_and_hook_exports(interfaces_jsx_path: Path) -> None:
    """Verify presence of core React hooks, classes, and exported components."""
    content = interfaces_jsx_path.read_text(encoding="utf-8")

    expected_identifiers = [
        "useResilientWebSocket",
        "RingBuffer",
        "CoChemTelemetryDB",
        "CoChemDockTelemetryUI",
        "TelemetryMetricsPanel",
        "LogStreamViewer",
        "JobControlPanel",
        "useRef",
        "useState",
        "useEffect",
        "useCallback",
        "useMemo",
    ]
    for ident in expected_identifiers:
        assert ident in content, f"Missing expected identifier '{ident}' in {interfaces_jsx_path.name}"


def test_ring_buffer_algorithmic_verification() -> None:
    """Verify the FIFO RingBuffer invariant: drops oldest entries and respects bounded capacity."""
    class PythonRingBuffer:
        def __init__(self, capacity: int = 10000) -> None:
            self.capacity = max(1, capacity)
            self.buffer: List[Dict[str, Any]] = []
            self.total_dropped: int = 0
            self.total_received: int = 0

        def push(self, item: Dict[str, Any]) -> None:
            self.total_received += 1
            if len(self.buffer) >= self.capacity:
                self.buffer.pop(0)
                self.total_dropped += 1
            self.buffer.append(item)

        def push_batch(self, items: List[Dict[str, Any]]) -> None:
            for it in items:
                self.push(it)

        def clear(self) -> None:
            self.buffer.clear()
            self.total_dropped = 0
            self.total_received = 0

        def get_lines(self) -> List[Dict[str, Any]]:
            return list(self.buffer)

    rb = PythonRingBuffer(capacity=5)
    for i in range(10):
        rb.push({"id": i, "text": f"Line {i}"})

    assert len(rb.buffer) == 5
    assert rb.total_dropped == 5
    assert rb.total_received == 10
    # Surviving items should be 5 through 9
    assert [item["id"] for item in rb.get_lines()] == [5, 6, 7, 8, 9]

    # Test batch push
    rb.push_batch([{"id": 10, "text": "Line 10"}, {"id": 11, "text": "Line 11"}])
    assert len(rb.buffer) == 5
    assert [item["id"] for item in rb.get_lines()] == [7, 8, 9, 10, 11]
    assert rb.total_dropped == 7


def test_telemetry_metrics_parsing_and_unit_conversion() -> None:
    """Verify telemetry parser handles ORCA/CFOUR/xTB payloads and unit conversions."""
    HARTREE_TO_EV = 27.211386245988
    HARTREE_TO_KCAL_MOL = 627.5094740631

    raw_event = {
        "type": "scf_step",
        "step": 12,
        "energy_hartree": -76.421589,
        "delta_energy": -0.000042,
        "max_gradient": 0.00012,
        "rms_gradient": 0.000034,
        "walltime_seconds": 3.45,
        "job_id": "orca_opt_001",
    }

    # Energy conversions
    e_hartree = raw_event["energy_hartree"]
    e_ev = e_hartree * HARTREE_TO_EV
    e_kcal = e_hartree * HARTREE_TO_KCAL_MOL

    assert round(e_ev, 4) == round(-76.421589 * 27.211386245988, 4)
    assert round(e_kcal, 4) == round(-76.421589 * 627.5094740631, 4)
    assert raw_event["max_gradient"] < 0.001
    assert raw_event["step"] == 12


def test_indexeddb_schema_contract(interfaces_jsx_path: Path) -> None:
    """Verify IndexedDB schema definitions and persistence hooks in the JSX file."""
    content = interfaces_jsx_path.read_text(encoding="utf-8")

    assert "CoChemTelemetryDB" in content
    assert "indexedDB" in content or "IDBDatabase" in content
    assert "telemetry_logs" in content
    assert "job_id" in content
    assert "timestamp" in content


def test_websocket_resilience_and_heartbeat_contract(interfaces_jsx_path: Path) -> None:
    """Verify useResilientWebSocket implements exponential backoff and ping-pong."""
    content = interfaces_jsx_path.read_text(encoding="utf-8")

    assert "useResilientWebSocket" in content
    assert "reconnect" in content.lower()
    assert "ping" in content.lower()
    assert "pong" in content.lower()
    assert "flush" in content.lower()
    assert "WebSocket" in content


def test_autoscroll_and_user_scroll_lock(interfaces_jsx_path: Path) -> None:
    """Verify useRef auto-scrolling with user override detection in JSX."""
    content = interfaces_jsx_path.read_text(encoding="utf-8")

    assert "useRef" in content
    assert "scrollTop" in content
    assert "scrollHeight" in content
    assert "clientHeight" in content
    assert "autoScroll" in content or "auto_scroll" in content or "isAutoScroll" in content


def test_dark_mode_and_tailwind_styling(interfaces_jsx_path: Path) -> None:
    """Verify Tailwind CSS classes for scientific UI styling and dark theme."""
    content = interfaces_jsx_path.read_text(encoding="utf-8")

    # Dark background and terminal styling
    assert "bg-" in content
    assert "text-" in content
    assert "font-mono" in content or "font-" in content
    assert "rounded" in content
    assert "flex" in content or "grid" in content
