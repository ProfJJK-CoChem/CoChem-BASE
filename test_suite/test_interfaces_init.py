"""Comprehensive physical Zero-Mock test suite for cochem_base.interfaces subsystem.

Validates lazy loading architecture (PEP 562), exported symbols, type hinting integrity,
AttributeError handling, __dir__ reflection, LF line endings, and path sanitization.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import cochem_base.interfaces as interfaces
from cochem_base.path_sanitization import leak_patterns


@pytest.fixture
def interfaces_init_path() -> Path:
    """Return the absolute path to cochem_base/interfaces/__init__.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_base" / "interfaces" / "__init__.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


def test_file_encoding_and_lf_line_endings(interfaces_init_path: Path) -> None:
    """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
    raw = interfaces_init_path.read_bytes()
    assert b"\r\n" not in raw, "Found Windows CRLF (\\r\\n) line endings in interfaces/__init__.py"
    assert b"\n" in raw, "Missing newline characters in interfaces/__init__.py"
    assert not raw.startswith(b"\xef\xbb\xbf"), "Found UTF-8 BOM marker in interfaces/__init__.py"

    content = interfaces_init_path.read_text(encoding="utf-8")
    assert len(content) > 200, "File content is unexpectedly small."


def test_zero_personal_path_leaks(interfaces_init_path: Path) -> None:
    """Verify zero personal machine or local user path leakage in interfaces/__init__.py."""
    lines = interfaces_init_path.read_text(encoding="utf-8").splitlines()
    patterns = leak_patterns()
    leaks = []
    for lineno, line in enumerate(lines, 1):
        for pattern, placeholder in patterns:
            if pattern.search(line):
                leaks.append((lineno, placeholder, line.strip()))

    assert len(leaks) == 0, f"Detected personal path leaks in interfaces/__init__.py: {leaks}"


def test_docstring_and_architectural_overview(interfaces_init_path: Path) -> None:
    """Verify comprehensive architectural docstring is present on the module."""
    doc = interfaces.__doc__
    assert doc is not None and len(doc) > 100
    assert "WebGL" in doc
    assert "Fast Pass" in doc
    assert "Installer GUI" in doc
    assert "Telemetry" in doc


def test_module_all_exports_present() -> None:
    """Verify __all__ is a sorted list of non-empty public symbols."""
    assert hasattr(interfaces, "__all__")
    assert isinstance(interfaces.__all__, list)
    assert interfaces.__all__ == sorted(interfaces.__all__)

    expected_symbols = [
        "AxisLayout",
        "BrowserSparsityPayload",
        "DeploymentManifest",
        "ECOSYSTEM_REGISTRY",
        "FastPassWidget",
        "HAS_3DMOL",
        "MatrixElement",
        "PlotlyLayout",
        "PlotlyPayload",
        "PubChemProperty",
        "PubChemPropertyTable",
        "PubChemResponse",
        "ScatterTrace",
        "SparsityDimensions",
        "SynapInstallerGUI",
        "TelemetryEvent",
        "WebGLPacket",
        "WebGLStreamer",
        "WebSparsityMatrix",
        "app",
        "dock_app",
        "get_spectrum",
        "health_check",
        "lttb_decimate",
        "router",
        "visuals_router",
        "websocket_telemetry",
    ]
    for sym in expected_symbols:
        assert sym in interfaces.__all__, f"Symbol '{sym}' missing from interfaces.__all__"


@pytest.mark.parametrize(
    "symbol_name",
    [
        "BrowserSparsityPayload",
        "MatrixElement",
        "SparsityDimensions",
        "WebSparsityMatrix",
        "WebGLPacket",
        "WebGLStreamer",
        "TelemetryEvent",
        "app",
        "dock_app",
        "health_check",
        "lttb_decimate",
        "websocket_telemetry",
        "AxisLayout",
        "PlotlyLayout",
        "PlotlyPayload",
        "ScatterTrace",
        "get_spectrum",
        "router",
        "visuals_router",
        "FastPassWidget",
        "HAS_3DMOL",
        "PubChemProperty",
        "PubChemPropertyTable",
        "PubChemResponse",
        "DeploymentManifest",
        "ECOSYSTEM_REGISTRY",
        "SynapInstallerGUI",
    ],
)
def test_lazy_attribute_resolution(symbol_name: str) -> None:
    """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
    attr = getattr(interfaces, symbol_name)
    assert attr is not None
    # Verify cached in module dictionary
    assert symbol_name in interfaces.__dict__


def test_aliased_exports_equivalence() -> None:
    """Verify alias exports resolve to identical underlying objects."""
    assert interfaces.dock_app is interfaces.app
    assert interfaces.visuals_router is interfaces.router


def test_invalid_attribute_access_raises_attribute_error() -> None:
    """Verify accessing undefined attributes raises AttributeError with descriptive message."""
    with pytest.raises(AttributeError) as exc_info:
        _ = interfaces.NonExistentInterfaceSymbol
    assert "module 'cochem_base.interfaces' has no attribute 'NonExistentInterfaceSymbol'" in str(exc_info.value)


def test_dir_reflection_contains_all_and_globals() -> None:
    """Verify __dir__() lists all public exports and module globals."""
    dir_symbols = dir(interfaces)
    for sym in interfaces.__all__:
        assert sym in dir_symbols, f"Symbol '{sym}' missing from dir(interfaces)"
    assert "__all__" in dir_symbols
    assert "__getattr__" in dir_symbols
    assert "__dir__" in dir_symbols
