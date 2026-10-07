"""Restore checksum-bound downstream source snapshots; never download engines."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import tarfile
from pathlib import Path, PurePosixPath


def restore(bundle: Path, output: Path, *, topos_ref: str, torq_ref: str) -> dict:
    manifest = json.loads((bundle / 'manifest.json').read_text())
    if manifest.get('schema_version') != 'cochem-source-bundle/1':
        raise ValueError('Unknown source bundle schema')
    if set(manifest.get('sources', {})) != {'topos', 'torq'}:
        raise ValueError('Mandatory source bundle members missing')
    if output.exists():
        raise ValueError('Source destination must be fresh')
    plans = []
    for name, requested in [('topos', topos_ref), ('torq', torq_ref)]:
        source = manifest['sources'][name]
        if not re.fullmatch(r'[0-9a-f]{40}', requested) or source['commit'] != requested:
            raise ValueError(f'{name}: requested commit does not match reviewed archive')
        archive = bundle / (name + '.tar.gz')
        if archive.is_symlink() or not archive.is_file():
            raise ValueError('Source archive must be a regular file')
        data = archive.read_bytes()
        if len(data) != source['size_bytes'] or hashlib.sha256(data).hexdigest() != source['sha256']:
            raise ValueError('Source archive checksum mismatch')
        with tarfile.open(archive, 'r:gz') as tar:
            members = tar.getmembers()
            names = set()
            for member in members:
                path = PurePosixPath(member.name)
                if path.is_absolute() or '..' in path.parts or '\\' in member.name or not (member.isfile() or member.isdir()):
                    raise ValueError('Unsafe source archive member')
                if member.name in names:
                    raise ValueError('Duplicate source archive member')
                names.add(member.name)
            if sum(item.size for item in members) > 256 * 1024 * 1024:
                raise ValueError('Expanded source archive too large')
        plans.append((name, archive))
    output.mkdir(parents=True)
    for name, archive in plans:
        destination = output / name
        destination.mkdir()
        with tarfile.open(archive, 'r:gz') as tar:
            # Members were inspected before creating any output. Python 3.12's
            # data filter additionally enforces safe ownership/mode handling.
            tar.extractall(destination, filter='data')
        (destination / 'cochem-source-identity.json').write_text(json.dumps(manifest['sources'][name], indent=2) + '\n')
    (output / 'source-bundle-receipt.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--topos-ref', required=True)
    parser.add_argument('--torq-ref', required=True)
    args = parser.parse_args()
    restore(args.bundle, args.output, topos_ref=args.topos_ref, torq_ref=args.torq_ref)
