"""Actual optional patched CREST identity, distinct from upstream stock version."""
import os
from pathlib import Path

import pytest

from cochem_base.orchestrator.cochem_setup_phase_3 import audit_single_binary


def test_genuine_reviewed_crest_source_distribution_binds_immutable_components():
    executable = os.environ.get('COCHEM_TEST_PATCHED_CREST_EXECUTABLE')
    if not executable or not Path(executable).is_file():
        pytest.skip('Reviewed patched CREST installation not provided')
    audit = audit_single_binary('crest', custom_path=executable)
    assert audit.is_available, audit.error_detail
    assert audit.version == '3.0.2+topos-generic-paths-v1'
    assert str(Path(executable).parent / 'source.patch') in audit.native_components
    assert str(Path(executable).parent / 'installation.json') in audit.native_components
    assert len(audit.native_components) > 2
