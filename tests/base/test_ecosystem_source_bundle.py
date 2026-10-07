"""Checks for reviewed source archive restoration; no chemical outputs are mocked."""
import hashlib
import importlib.util
import io
import json
import tarfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('restore_ecosystem_sources', ROOT / 'scripts/restore_ecosystem_sources.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def _bundle(tmp_path, *, unsafe=False):
    folder=tmp_path/'bundle'
    folder.mkdir()
    manifest={'schema_version':'cochem-source-bundle/1','sources':{}}
    for name in ('topos','torq'):
        archive=folder/f'{name}.tar.gz'
        with tarfile.open(archive,'w:gz') as tar:
            member=tarfile.TarInfo('../escape' if unsafe and name=='topos' else 'pyproject.toml')
            content=b'[project]\nname="fixture-source"\n'
            member.size=len(content)
            tar.addfile(member,io.BytesIO(content))
        manifest['sources'][name]={'commit':'a'*40,'size_bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}
    (folder/'manifest.json').write_text(json.dumps(manifest))
    return folder


def test_restores_hash_verified_sources(tmp_path):
    bundle=_bundle(tmp_path)
    manifest=json.loads((bundle/'manifest.json').read_text())
    result=module.restore(bundle,tmp_path/'sources',topos_ref='a'*40,torq_ref='a'*40)
    assert result==manifest
    assert (tmp_path/'sources/topos/pyproject.toml').is_file()
    assert (tmp_path/'sources/torq/pyproject.toml').is_file()
    assert json.loads((tmp_path/'sources/source-bundle-receipt.json').read_text())==manifest


def test_rejects_wrong_commit_before_creating_output(tmp_path):
    bundle=_bundle(tmp_path)
    with pytest.raises(ValueError,match='commit'):
        module.restore(bundle,tmp_path/'sources',topos_ref='b'*40,torq_ref='a'*40)
    assert not (tmp_path/'sources').exists()


def test_rejects_altered_archive_before_creating_output(tmp_path):
    bundle=_bundle(tmp_path)
    (bundle/'topos.tar.gz').write_bytes(b'changed')
    with pytest.raises(ValueError,match='checksum'):
        module.restore(bundle,tmp_path/'sources',topos_ref='a'*40,torq_ref='a'*40)
    assert not (tmp_path/'sources').exists()


def test_rejects_traversal_before_creating_output(tmp_path):
    bundle=_bundle(tmp_path,unsafe=True)
    with pytest.raises(ValueError,match='Unsafe'):
        module.restore(bundle,tmp_path/'sources',topos_ref='a'*40,torq_ref='a'*40)
    assert not (tmp_path/'sources').exists()
    assert not (tmp_path/'escape').exists()
