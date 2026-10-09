#!/usr/bin/env python3
"""Create a separate sealed copy with one exact reviewed H/O basis addon.

The approved licensed installation is verified before and after copying. No
binary, library, helper or original installation is modified. Inputs and all
licensed copies remain outside the source checkout. The checksum-pinned addon
combines public BSE entries with a retained native H:PWCVTZ alias; it remains
private data, never executable installer code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from cochem_base.core_engine.cfour_basis_profile import BASIS_PROFILE, DERIVED_INVENTORY_SHA256
from cochem_base.core_engine.cfour_runtime import _packaged_inventory, verify_cfour_runtime
from scripts.provision_cfour import (
    PROVENANCE_NAME, REPOSITORY_ROOT, interrogate_runtime, verify_runtime,
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def derive_inventory(vendor: bytes, genbas: bytes, addon: bytes) -> tuple[bytes, bytes]:
    """Derive only the fixed reviewed inventory, checking the complete parent chain."""
    if (_sha(vendor) != BASIS_PROFILE['parent_inventory_sha256']
            or _sha(genbas) != BASIS_PROFILE['parent_genbas_sha256']
            or _sha(addon) != BASIS_PROFILE['addon_sha256']):
        raise ValueError('CFOUR parent inventory, vendor GENBAS or reviewed addon checksum changed.')
    derived = genbas + b'\n\n' + addon
    if _sha(derived) != BASIS_PROFILE['derived_genbas_sha256']:
        raise ValueError('CFOUR derived GENBAS does not match the reviewed profile.')
    inventory = json.loads(vendor)
    inventory['basis_derivation'] = BASIS_PROFILE
    matches = 0
    for record in inventory['files']:
        if record['path'] == 'basis/GENBAS':
            record.update(size=len(derived), sha256=_sha(derived))
            matches += 1
    if matches != 1:
        raise ValueError('CFOUR parent inventory has no unique vendor GENBAS.')
    inventory['files'].extend([
        {'path': 'provenance/vendor-manifest.json', 'size': len(vendor), 'sha256': _sha(vendor)},
        {'path': 'provenance/basis-addon.GENBAS', 'size': len(addon), 'sha256': _sha(addon)},
    ])
    inventory['files'].sort(key=lambda record: record['path'])
    encoded = (json.dumps(inventory, sort_keys=True, indent=2) + '\n').encode()
    if _sha(encoded) != DERIVED_INVENTORY_SHA256:
        raise ValueError('Derived CFOUR complete inventory is not the reviewed fixed identity.')
    return encoded, derived


def provision_basis_profile(parent: Path, addon_path: Path, destination: Path) -> dict:
    parent = parent.expanduser().resolve(strict=True)
    addon_path = addon_path.expanduser().absolute()
    if any(path.is_symlink() for path in (addon_path, *addon_path.parents)):
        raise ValueError('The reviewed CFOUR basis addon and its parent paths cannot be symlinks.')
    addon_path = addon_path.resolve(strict=True)
    destination = destination.expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError('Choose a fresh derived CFOUR installation directory.')
    destination = destination.resolve()
    if (destination.is_relative_to(REPOSITORY_ROOT) or destination.is_relative_to(parent)
            or parent.is_relative_to(destination)):
        raise ValueError('Derived CFOUR must be outside the source checkout and separate from its parent.')
    if addon_path.is_symlink() or not addon_path.is_file():
        raise ValueError('The reviewed CFOUR basis addon must be a regular file.')
    original = verify_runtime(parent)
    vendor = (parent / 'manifest.json').read_bytes()
    addon = addon_path.read_bytes()
    inventory, genbas = derive_inventory(vendor, (parent / 'basis/GENBAS').read_bytes(), addon)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.cochem-cfour-derived-', dir=destination.parent))
    # On failure preserve the staging directory for inspection. Never remove the
    # approved parent or overwrite an existing destination.
    copied = staging / 'runtime'
    shutil.copytree(parent, copied, symlinks=True,
                    ignore=lambda folder, names: [PROVENANCE_NAME] if Path(folder) == parent else [])
    (copied / 'basis/GENBAS').write_bytes(genbas)
    provenance = copied / 'provenance'
    provenance.mkdir()
    (provenance / 'vendor-manifest.json').write_bytes(vendor)
    (provenance / 'basis-addon.GENBAS').write_bytes(addon)
    (copied / 'manifest.json').write_bytes(inventory)
    _packaged_inventory(copied)
    native = interrogate_runtime(copied)
    if verify_runtime(parent) != original:
        raise ValueError('The approved parent CFOUR runtime changed during derivation.')
    receipt = {
        'schema_version': 2, 'software': 'CFOUR', 'status': 'available',
        'archive_sha256': BASIS_PROFILE['parent_archive_sha256'],
        'runtime_manifest_sha256': DERIVED_INVENTORY_SHA256,
        'basis_derivation': BASIS_PROFILE,
        'native_cfour_version': native['native_cfour_version'],
        'native_probe': native,
        'licensed_parent_modified': False,
        'scientific_accuracy_claim': None,
    }
    (copied / PROVENANCE_NAME).write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    _packaged_inventory(copied)
    copied.rename(destination)
    staging.rmdir()
    verified = verify_cfour_runtime(destination / 'bin/xcfour', environment={})
    return {'status': 'available', 'profile': BASIS_PROFILE['profile'],
            'prefix': str(destination), 'runtime_inventory_sha256': DERIVED_INVENTORY_SHA256,
            'runtime_seal_sha256': verified['runtime_seal_sha256'],
            'files_verified': verified['files_verified'], 'native_cfour_version': '2.1',
            'licensed_parent_modified': False, 'scientific_accuracy_claim': None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--addon', type=Path, required=True)
    parser.add_argument('--install-root', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(provision_basis_profile(args.parent, args.addon, args.install_root), indent=2))


if __name__ == '__main__':
    main()
