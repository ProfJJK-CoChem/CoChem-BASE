"""Bind the explicitly reviewed CREST generic-calculator source modification."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

BUILD_ID = 'crest-3.0.2-generic-paths-v1'
PATCH_SHA256 = '9f22e2d9e0cd9b6aa8a6d41a0c32b6271d659c62498f888f0d5d889cc09aa8b9'
UPSTREAM_COMMIT = 'af7eb9927e2b36e24b14055f9eba3bea5be0014e'


def inspect_crest_source_distribution(binary: Path, environment: dict[str, str]) -> tuple[str | None, dict[str, str]]:
    """Stock installations remain ordinary engines; declared patched ones bind all members.

    The source manifest and patch are retained immutable runtime authority
    components, alongside the actual shared libraries. This reports identity,
    never a claim that a scientific search was performed during discovery.
    """
    manifest_path = binary.parent / 'installation.json'
    if not manifest_path.is_file():
        return None, {}
    metadata = json.loads(manifest_path.read_text())
    if metadata.get('build_id') != BUILD_ID:
        raise ValueError('Unknown declared CREST source distribution')
    patch = binary.parent / 'source.patch'
    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    if (metadata.get('upstream_repository') != 'https://github.com/crest-lab/crest'
            or metadata.get('upstream_commit') != UPSTREAM_COMMIT
            or metadata.get('upstream_version') != '3.0.2'
            or metadata.get('source_patch_sha256') != PATCH_SHA256
            or metadata.get('build_source_diff_sha256') != PATCH_SHA256
            or not patch.is_file() or patch.is_symlink() or digest(patch) != PATCH_SHA256
            or metadata.get('binary_sha256') != digest(binary)):
        raise ValueError('CREST binary/source-patch identity differs from the reviewed distribution')
    result = subprocess.run([str(binary), '--version'], capture_output=True, text=True,
                            env=environment, timeout=10, check=True)
    if f'TOPOS patch: {BUILD_ID}' not in result.stdout + result.stderr:
        raise ValueError('CREST source patch marker is absent from the actual executable')
    components = {str(manifest_path): digest(manifest_path), str(patch): digest(patch)}
    for item in metadata.get('shared_libraries', []):
        path = Path(item['path'])
        if not path.is_absolute() or not path.is_file() or digest(path) != item['sha256']:
            raise ValueError('CREST source distribution shared-library identity changed')
        components[str(path)] = item['sha256']
    if len(components) <= 2:
        raise ValueError('CREST source distribution lacks declared shared-library evidence')
    return '3.0.2+topos-generic-paths-v1', components
