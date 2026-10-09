"""Metadata boundary tests; no invented executable or scientific result."""
import hashlib
import json
from pathlib import Path

import pytest

from cochem_base.core_engine import cfour_runtime
from cochem_base.core_engine.cfour_basis_profile import BASIS_PROFILE
from scripts.provision_cfour_basis_profile import derive_inventory, provision_basis_profile


def test_basis_profile_retains_original_licensed_build_and_exact_public_data():
    assert BASIS_PROFILE['parent_archive_sha256'] == cfour_runtime.APPROVED_ARCHIVE_SHA256
    assert BASIS_PROFILE['parent_inventory_sha256'] == cfour_runtime.APPROVED_INVENTORY_SHA256
    assert BASIS_PROFILE['profile'] == 'cochem-cfour-h-o-junchs-basis-v1'
    assert len(BASIS_PROFILE['public_sources']) == 3
    assert all(item['url'].startswith('https://www.basissetexchange.org/') for item in BASIS_PROFILE['public_sources'])


@pytest.mark.parametrize('changed', ['vendor', 'genbas', 'addon'])
def test_derivation_rejects_every_unreviewed_input_before_copying(changed, monkeypatch):
    values = dict(vendor=b'Explicit metadata control', genbas=b'Explicit vendor basis control', addon=b'Explicit addon control')
    for field, key in [('vendor', 'parent_inventory_sha256'), ('genbas', 'parent_genbas_sha256'), ('addon', 'addon_sha256')]:
        monkeypatch.setitem(BASIS_PROFILE, key, hashlib.sha256(values[field]).hexdigest())
    values[changed] += b'changed'
    with pytest.raises(ValueError, match='checksum changed'):
        derive_inventory(**values)


def test_derivation_refuses_existing_destination_without_touching_it(tmp_path):
    destination = tmp_path / 'existing'
    destination.mkdir()
    marker = destination / 'marker.txt'
    marker.write_text('Preserve existing installation')
    with pytest.raises(ValueError, match='fresh derived'):
        provision_basis_profile(tmp_path, marker, destination)
    assert marker.read_text() == 'Preserve existing installation'


def test_addon_symlink_is_rejected_before_resolution(tmp_path):
    addon = tmp_path / 'addon.txt'
    addon.write_text('Explicit text-only control')
    link = tmp_path / 'link.txt'
    link.symlink_to(addon)
    with pytest.raises(ValueError, match='cannot be symlinks'):
        provision_basis_profile(tmp_path, link, tmp_path.parent / 'fresh-control-destination')


def test_addon_parent_symlink_is_rejected_before_resolution(tmp_path):
    folder = tmp_path / 'actual'
    folder.mkdir()
    addon = folder / 'addon.txt'
    addon.write_text('Explicit text-only control')
    link = tmp_path / 'redirect'
    link.symlink_to(folder, target_is_directory=True)
    with pytest.raises(ValueError, match='cannot be symlinks'):
        provision_basis_profile(tmp_path, link / 'addon.txt', tmp_path.parent / 'fresh-control-destination')


def _metadata_control(root: Path, monkeypatch) -> Path:
    root.mkdir()
    ordinary = root / 'ordinary.txt'
    ordinary.write_text('Explicit text-only control; no runtime or physical result.')
    inventory = {'schema_version': 1, 'software': 'CFOUR', 'version': '2.1',
                 'source_sha256': cfour_runtime.APPROVED_SOURCE_SHA256,
                 'platform': 'linux-x86_64', 'minimum_glibc': '2.35', 'fortran_integer_bits': 64,
                 'blas': 'ILP64 OpenBLAS pthread', 'mpi': False, 'openmp': True,
                 'basis_derivation': BASIS_PROFILE,
                 'files': [{'path': ordinary.name, 'size': ordinary.stat().st_size,
                            'sha256': hashlib.sha256(ordinary.read_bytes()).hexdigest()}]}
    metadata = root / 'manifest.json'
    metadata.write_text(json.dumps(inventory))
    monkeypatch.setattr(cfour_runtime, 'DERIVED_INVENTORY_SHA256', hashlib.sha256(metadata.read_bytes()).hexdigest())
    return metadata


def test_reviewed_derived_metadata_seal_checks_every_runtime_file(tmp_path, monkeypatch):
    metadata = _metadata_control(tmp_path / 'control', monkeypatch)
    assert cfour_runtime._packaged_inventory(metadata.parent)['basis_derivation'] == BASIS_PROFILE
    (metadata.parent / 'ordinary.txt').write_text('Changed explicit control')
    with pytest.raises(ValueError, match='bytes changed'):
        cfour_runtime._packaged_inventory(metadata.parent)


def test_derived_metadata_cannot_omit_parent_chain_or_change_profile(tmp_path, monkeypatch):
    metadata = _metadata_control(tmp_path / 'control', monkeypatch)
    content = json.loads(metadata.read_text())
    del content['basis_derivation']['parent_inventory_sha256']
    metadata.write_text(json.dumps(content))
    monkeypatch.setattr(cfour_runtime, 'DERIVED_INVENTORY_SHA256', hashlib.sha256(metadata.read_bytes()).hexdigest())
    with pytest.raises(ValueError, match='basis provenance'):
        cfour_runtime._packaged_inventory(metadata.parent)


def test_derived_receipt_must_bind_actual_derived_inventory(tmp_path, monkeypatch):
    metadata = _metadata_control(tmp_path / 'control', monkeypatch)
    receipt = {'software': 'CFOUR', 'status': 'available',
               'archive_sha256': cfour_runtime.APPROVED_ARCHIVE_SHA256,
               'runtime_manifest_sha256': cfour_runtime.APPROVED_INVENTORY_SHA256,
               'native_cfour_version': '2.1'}
    (metadata.parent / cfour_runtime.PROVENANCE_NAME).write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match='provenance does not match'):
        cfour_runtime._packaged_inventory(metadata.parent)
