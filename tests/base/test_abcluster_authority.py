"""ABCluster component identity; metadata is separate from scientific acceptance."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from cochem_base.cochem_core_registry_schema import EnginePaths
from cochem_base.orchestrator.cochem_setup_phase_3 import (
    audit_single_binary,
    extract_semantic_version,
)


def test_abcluster_requires_its_own_anchored_component_banner():
    assert EnginePaths().abcluster is None
    assert extract_semantic_version('ABCluster package\nrigidmol 3.4\nGNU 12.2.0', 'abcluster') == '3.4'
    assert extract_semantic_version('compiler version 3.4', 'abcluster') is None
    assert extract_semantic_version('rigidmol 3.4\nrigidmol 3.5', 'abcluster') is None


def test_actual_rigidmol_metadata_audit():
    binary = os.environ.get('COCHEM_TEST_ABCLUSTER_EXECUTABLE')
    if not binary or not Path(binary).is_file():
        pytest.skip('Actual optional ABCluster installation not provided')
    result = audit_single_binary('abcluster', custom_path=binary)
    assert result.is_available, result.error_detail
    assert result.version == '3.4'
    assert result.path == binary and result.sha256_hash
