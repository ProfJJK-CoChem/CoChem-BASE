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


def test_actual_stock_crest_installer_metadata_remains_supported(tmp_path):
    import hashlib
    import json
    import shutil

    executable = os.environ.get('COCHEM_TEST_STOCK_CREST_EXECUTABLE')
    if not executable or not Path(executable).is_file():
        pytest.skip('Actual stock CREST3.0.2 installation not provided')
    binary = tmp_path / 'crest'
    shutil.copy2(executable, binary)
    (tmp_path / 'installation.json').write_text(json.dumps({
        'version': '3.0.2', 'build': 'GNU12; static Linux x86_64',
        'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}))
    result = audit_single_binary('crest', custom_path=binary)
    assert result.is_available, result.error_detail
    assert result.version == '3.0.2' and not result.native_components
