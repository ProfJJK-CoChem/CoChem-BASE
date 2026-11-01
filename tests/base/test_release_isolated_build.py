"""Real offline PEP 517 builds with separate owned dependency environments."""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
import subprocess
import tarfile
import zipfile
from pathlib import Path

import pytest
from build import BuildBackendException

from scripts import verify_release_ci
from tests.base.test_pinned_pip_runtime import _caller_pip, offline_env, wheel

ROOT = Path(__file__).resolve().parents[2]
assert Path(verify_release_ci.__file__).resolve() == ROOT / "scripts/verify_release_ci.py"
assert Path(verify_release_ci._build_release_artifacts.__code__.co_filename).resolve() == ROOT / "scripts/verify_release_ci.py"


def _dependency_wheel(directory, name, module, value):
    """A real, installable tiny engineering dependency with a complete RECORD."""
    directory.mkdir(exist_ok=True)
    version = "1.0"
    normalized = name.replace("-", "_")
    metadata = normalized + "-" + version + ".dist-info"
    files = {
        module + ".py": ("VALUE = " + repr(value) + "\n").encode(),
        metadata + "/METADATA": ("Metadata-Version: 2.1\nName: " + name + "\nVersion: " + version + "\n").encode(),
        metadata + "/WHEEL": b"Wheel-Version: 1.0\nGenerator: real-engineering-fixture\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
    }
    records = io.StringIO()
    writer = csv.writer(records, lineterminator="\n")
    for member, data in files.items():
        writer.writerow([member, "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode(), len(data)])
    writer.writerow([metadata + "/RECORD", "", ""])
    files[metadata + "/RECORD"] = records.getvalue().encode()
    path = directory / (normalized + "-" + version + "-py3-none-any.whl")
    with zipfile.ZipFile(path, "w") as archive:
        for member, data in files.items():
            archive.writestr(member, data)
    return path


BACKEND = r'''
import base64, csv, hashlib, importlib.metadata, importlib.util, io, json, pathlib, sys, tarfile, time, zipfile
import static_build_dependency

ROOT = pathlib.Path(__file__).parent

def _requires(kind):
    print('REAL STATIC HOOK ' + kind + ': ' + static_build_dependency.VALUE)
    print('REAL HOOK STDERR ' + kind, file=sys.stderr)
    return ['cochem-build-dynamic==1.0']

def get_requires_for_build_sdist(config_settings=None):
    return _requires('sdist')

def get_requires_for_build_wheel(config_settings=None):
    return _requires('wheel')

def _state(kind):
    import dynamic_build_dependency
    assert static_build_dependency.VALUE == 'installed static dependency'
    assert dynamic_build_dependency.VALUE == 'installed dynamic dependency'
    prefix = pathlib.Path(sys.prefix).resolve()
    dependencies = {}
    for name, module in [('cochem-build-static', static_build_dependency), ('cochem-build-dynamic', dynamic_build_dependency)]:
        assert pathlib.Path(module.__file__).resolve().is_relative_to(prefix)
        dist = importlib.metadata.distribution(name)
        for relative, encoded, size in csv.reader(dist.read_text('RECORD').splitlines()):
            member = pathlib.Path(dist.locate_file(relative)).resolve()
            assert member.is_relative_to(prefix)
            if encoded:
                data = member.read_bytes()
                algorithm, expected = encoded.split('=', 1)
                assert base64.urlsafe_b64encode(hashlib.new(algorithm, data).digest()).rstrip(b'=').decode() == expected
                assert len(data) == int(size)
        dependencies[name] = {'version': dist.version, 'origin': module.__file__, 'RECORD_verified': True}
    return {'kind': kind, 'prefix': sys.prefix, 'base_prefix': sys.base_prefix,
            'backend': __file__, 'dependencies': dependencies,
            'pip_in_build_env': importlib.util.find_spec('pip') is not None}

def build_sdist(sdist_directory, config_settings=None):
    report = _state('sdist')
    (ROOT / 'sdist-witness.json').write_text(json.dumps(report))
    target = pathlib.Path(sdist_directory) / 'cochem-release-fixture-1.0.tar.gz'
    with tarfile.open(target, 'w:gz') as archive:
        if (ROOT / 'unsafe-sdist').exists():
            bad = tarfile.TarInfo('../escaped-source')
            bad.size = 4
            archive.addfile(bad, io.BytesIO(b'fail'))
        else:
            archive.add(ROOT, arcname='cochem-release-fixture-1.0')
    return target.name

def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    report = _state('wheel')
    if (ROOT / 'fail-wheel').exists():
        print('REAL BACKEND FAILURE STDOUT')
        print('REAL BACKEND FAILURE STDERR', file=sys.stderr)
        raise RuntimeError('genuine fixture backend wheel failure')
    if (ROOT / 'slow-wheel').exists():
        print('REAL BACKEND WAIT', flush=True)
        time.sleep(90)
    dist = 'cochem_release_fixture-1.0.dist-info'
    files = {'cochem_release_fixture/__init__.py': b'VALUE = 42\n',
             'cochem_release_fixture/build-origin.json': json.dumps(report).encode(),
             dist + '/METADATA': b'Metadata-Version: 2.1\nName: cochem-release-fixture\nVersion: 1.0\n',
             dist + '/WHEEL': b'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n'}
    records = io.StringIO()
    writer = csv.writer(records, lineterminator='\n')
    for name, data in files.items():
        writer.writerow([name, 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode(), len(data)])
    writer.writerow([dist + '/RECORD', '', ''])
    files[dist + '/RECORD'] = records.getvalue().encode()
    target = pathlib.Path(wheel_directory) / 'cochem_release_fixture-1.0-py3-none-any.whl'
    with zipfile.ZipFile(target, 'w') as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return target.name
'''


def _isolated_project(tmp_path, mode="success"):
    project = tmp_path / "source"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        '[build-system]\nrequires=["cochem-build-static==1.0; python_version >= \'3.10\'"]\n'
        'build-backend="backend"\nbackend-path=["."]\n')
    (project / "backend.py").write_text(BACKEND)
    if mode in ("fail-wheel", "slow-wheel", "unsafe-sdist"):
        (project / mode).write_text("actual fixture branch")
    links = tmp_path / "dependency wheels"
    if mode != "missing-static":
        _dependency_wheel(links, "cochem-build-static", "static_build_dependency", "installed static dependency")
    else:
        links.mkdir()
    if mode != "missing-dynamic":
        _dependency_wheel(links, "cochem-build-dynamic", "dynamic_build_dependency", "installed dynamic dependency")
    return project, links


@pytest.mark.parametrize("placement_config", [False, True])
def test_public_builder_installs_real_static_dynamic_dependencies_and_builds_from_sdist(
        tmp_path, wheel, offline_env, placement_config):
    assert __debug__
    caller = _caller_pip()
    project, links = _isolated_project(tmp_path)
    original = {name: (project / name).read_bytes() for name in ("pyproject.toml", "backend.py")}
    out = tmp_path / "output"
    out.mkdir()
    environment = dict(offline_env, COCHEM_PINNED_PIP_WHEEL=str(wheel), PIP_FIND_LINKS=links.as_uri())
    foreign = tmp_path / "foreign-placement"
    foreign.mkdir()
    sentinel = foreign / "keep-original"
    sentinel.write_bytes(b"untouched")
    if placement_config:
        config = tmp_path / "pip.ini"
        config.write_text('[install]\nroot = ' + str(foreign) + '\nprefix = ' + str(foreign) + '\nuser = true\n')
        environment.update(PIP_ROOT=str(foreign), PIP_PREFIX=str(foreign), PIP_TARGET=str(foreign),
                           PIP_USER="1", PYTHONUSERBASE=str(foreign), PIP_CONFIG_FILE=str(config))
    sdist, built = verify_release_ci._build_release_artifacts(project, out / "dist", out, environment, timeout=90)
    assert sdist.name.endswith('.tar.gz') and built.name.endswith('.whl')
    with zipfile.ZipFile(built) as archive:
        report = json.loads(archive.read('cochem_release_fixture/build-origin.json'))
    first = json.loads((project / "sdist-witness.json").read_text())
    assert first['kind'] == 'sdist' and report['kind'] == 'wheel'
    assert first['prefix'] != report['prefix']
    assert Path(first['backend']).resolve() == project / 'backend.py'
    assert Path(report['backend']).parent.name == 'cochem-release-fixture-1.0'
    assert Path(report['backend']).parent != project
    for witness in (first, report):
        assert witness['prefix'] != witness['base_prefix'] and not witness['pip_in_build_env']
        assert not Path(witness['prefix']).exists()
        assert all(row['version'] == '1.0' and row['RECORD_verified'] for row in witness['dependencies'].values())
    assert not list(out.glob('release-build-*'))
    assert all((project / name).read_bytes() == value for name, value in original.items())
    assert list(foreign.iterdir()) == [sentinel] and sentinel.read_bytes() == b'untouched'
    assert _caller_pip() == caller
    assert 'REAL STATIC HOOK sdist' in (out / 'build-sdist-hook-1.log').read_text()
    assert 'REAL HOOK STDERR wheel' in (out / 'build-wheel-hook-1.log.stderr.log').read_text()


@pytest.mark.parametrize('mode', ['missing-static', 'missing-dynamic', 'fail-wheel', 'unsafe-sdist'])
def test_real_dependency_backend_and_unsafe_archive_failures_keep_logs_and_cleanup(tmp_path, wheel, offline_env, mode):
    caller = _caller_pip()
    project, links = _isolated_project(tmp_path, mode)
    out = tmp_path / 'output'
    out.mkdir()
    environment = dict(offline_env, COCHEM_PINNED_PIP_WHEEL=str(wheel), PIP_FIND_LINKS=links.as_uri())
    expected = (tarfile.OutsideDestinationError if mode == 'unsafe-sdist'
                else BuildBackendException if mode == 'fail-wheel' else RuntimeError)
    with pytest.raises(expected) as failure:
        verify_release_ci._build_release_artifacts(project, out / 'dist', out, environment, timeout=90)
    assert not list(out.glob('release-build-*')) and not list((out / 'dist').glob('*.whl'))
    assert not (out / 'escaped-source').exists() and _caller_pip() == caller
    if mode == 'missing-static':
        assert 'cochem-build-static' in (out / 'build-sdist-static.log.stderr.log').read_text()
        assert not list(out.glob('build-*-hook-*.log'))
    elif mode == 'missing-dynamic':
        assert 'cochem-build-dynamic' in (out / 'build-sdist-dynamic.log.stderr.log').read_text()
        assert 'REAL STATIC HOOK sdist' in (out / 'build-sdist-hook-1.log').read_text()
    elif mode == 'fail-wheel':
        assert isinstance(failure.value.exception, RuntimeError)
        assert len(list((out / 'dist').glob('*.tar.gz'))) == 1
        assert any('REAL BACKEND FAILURE STDOUT' in path.read_text() for path in out.glob('build-wheel-hook-*.log'))
        assert any('genuine fixture backend wheel failure' in path.read_text() for path in out.glob('build-wheel-hook-*.stderr.log'))


def test_whole_build_deadline_expires_in_genuine_backend_and_cleans_owned_environments(tmp_path, wheel, offline_env):
    project, links = _isolated_project(tmp_path, 'slow-wheel')
    out = tmp_path / 'output'
    out.mkdir()
    caller = _caller_pip()
    with pytest.raises(BuildBackendException) as failure:
        verify_release_ci._build_release_artifacts(project, out / 'dist', out,
            dict(offline_env, COCHEM_PINNED_PIP_WHEEL=str(wheel), PIP_FIND_LINKS=links.as_uri()), timeout=45)
    assert any('REAL BACKEND WAIT' in path.read_text() for path in out.glob('build-wheel-hook-*.log'))
    assert isinstance(failure.value.exception, subprocess.TimeoutExpired)
    assert not list(out.glob('release-build-*')) and not list((out / 'dist').glob('*.whl'))
    assert _caller_pip() == caller
