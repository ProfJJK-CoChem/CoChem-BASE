"""CoChem-BASE Root Test Suite Package Initializer.

Standardized pytest namespace discovery and test suite root configuration,
conforming strictly to SRS Document 10 §2 (Test Suite Namespace Organization),
Method Matrix v4 Standards, and CoChem Anti-Spoofing Protocol v3.

Provenance Tags:
- [M] Measured test suite paths, package traversal metadata, and pytest discovery anchors.
- [D] Derived test namespace hierarchy and module export definitions.
- [E] Estimated execution timeouts and test runner resource allocations.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Package Version and Metadata
__version__ = "0.1.0"
__author__ = "CoChem Development Team"
__license__ = "Proprietary / CoChem Standards"

# Standardized Paths for Pytest Discovery & Fixtures [M]
TESTS_ROOT: Path = Path(__file__).resolve().parent
REPO_ROOT: Path = TESTS_ROOT.parent
FIXTURES_DIR: Path = TESTS_ROOT / "fixtures"
INTEGRATION_DIR: Path = TESTS_ROOT / "integration"
MODELS_TEST_DIR: Path = TESTS_ROOT / "test_models"


def get_tests_root() -> Path:
    """Return the absolute path to the root tests directory [M]."""
    return TESTS_ROOT


def get_repo_root() -> Path:
    """Return the absolute path to the repository root directory [M]."""
    return REPO_ROOT


def get_fixtures_dir() -> Path:
    """Return the absolute path to the test fixtures directory [M]."""
    return FIXTURES_DIR


def get_integration_dir() -> Path:
    """Return the absolute path to the integration tests directory [M]."""
    return INTEGRATION_DIR


def get_models_test_dir() -> Path:
    """Return the absolute path to the model test suite directory [M]."""
    return MODELS_TEST_DIR


def list_available_test_modules(subpackage: Optional[str] = None) -> List[str]:
    """Discover and return all test module filenames (.py) in the test suite namespace [M].

    Args:
        subpackage: Optional relative subdirectory name within tests.

    Returns:
        Sorted list of test file names matching 'test_*.py'.
    """
    target_dir = TESTS_ROOT if subpackage is None else (TESTS_ROOT / subpackage)
    if not target_dir.exists() or not target_dir.is_dir():
        return []

    discovered: List[str] = []
    for entry in target_dir.iterdir():
        if entry.is_file() and entry.name.startswith("test_") and entry.suffix == ".py":
            discovered.append(entry.name)
    return sorted(discovered)


def discover_all_test_suites() -> Dict[str, List[str]]:
    """Recursively map and discover all test modules grouped by sub-namespace [M].

    Returns:
        Dictionary mapping namespace names to lists of test module names.
    """
    suite_map: Dict[str, List[str]] = {
        "root": list_available_test_modules(None),
    }

    if INTEGRATION_DIR.exists() and INTEGRATION_DIR.is_dir():
        suite_map["integration"] = list_available_test_modules("integration")

    if MODELS_TEST_DIR.exists() and MODELS_TEST_DIR.is_dir():
        suite_map["test_models"] = list_available_test_modules("test_models")

    return suite_map


def get_test_environment_metadata() -> Dict[str, Any]:
    """Retrieve host test execution environment metadata [M].

    Returns:
        Dictionary containing Python version, platform, headless flag, and root paths.
    """
    return {
        "python_version": sys.version,
        "platform": sys.platform,
        "headless": os.environ.get("COCHEM_HEADLESS", "1") == "1",
        "tests_root": str(TESTS_ROOT),
        "repo_root": str(REPO_ROOT),
    }


__all__ = [
    "__version__",
    "__author__",
    "__license__",
    "TESTS_ROOT",
    "REPO_ROOT",
    "FIXTURES_DIR",
    "INTEGRATION_DIR",
    "MODELS_TEST_DIR",
    "get_tests_root",
    "get_repo_root",
    "get_fixtures_dir",
    "get_integration_dir",
    "get_models_test_dir",
    "list_available_test_modules",
    "discover_all_test_suites",
    "get_test_environment_metadata",
]
