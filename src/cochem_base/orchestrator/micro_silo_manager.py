"""Fail-closed Python isolation and pinned dependency verification for Stage 0."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Sequence


class MicroSiloValidationError(SystemExit):
    """An isolated interpreter or its exact package contract could not be verified."""


def isolated_environment() -> dict[str, str]:
    """Drop inherited Python injection variables before starting a silo."""
    return {
        key: value for key, value in os.environ.items()
        if key not in {"PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE", "VIRTUAL_ENV"}
    }


def validate_pins(requirements: Sequence[str]) -> dict[str, str]:
    """Only exact wheel/distribution versions may cross the Stage 0 boundary."""
    pins = {}
    for requirement in requirements:
        match = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9_.-]*)==([A-Za-z0-9][A-Za-z0-9_.+!-]*)", requirement)
        if match is None:
            raise MicroSiloValidationError(f"Silo dependency must be exactly pinned: {requirement!r}")
        name, version = match.groups()
        key = re.sub(r"[-_.]+", "-", name).lower()
        if key in pins and pins[key] != version:
            raise MicroSiloValidationError(f"Conflicting pins for {name}")
        pins[key] = version
    return pins


def verify_micro_silo(
    root: str | Path,
    *,
    python_version: str,
    requirements: Sequence[str] = (),
    imports: Sequence[str] = (),
) -> dict:
    """Verify real sys.path isolation, interpreter ABI, pins and ``pip check``.

    The interpreter runs with ``-I`` and a sanitized environment. Import names
    are passed as JSON data, never interpolated into executable source code.
    """
    root = Path(root).resolve()
    python = root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    pins = validate_pins(requirements)
    script = """
import importlib, importlib.metadata, json, pathlib, re, site, sys, sysconfig
contract = json.loads(sys.argv[1])
root = pathlib.Path(contract['root']).resolve()
assert pathlib.Path(sys.prefix).resolve() == root, 'interpreter prefix is outside silo'
assert sys.prefix != sys.base_prefix, 'global interpreter is not a silo'
assert not site.ENABLE_USER_SITE, 'user site is enabled'
cfg = root / 'pyvenv.cfg'
assert cfg.is_file(), 'missing virtual environment configuration'
assert 'include-system-site-packages = false' in cfg.read_text().lower(), 'global site packages are enabled'
version = '.'.join(str(x) for x in sys.version_info[:3])
assert version == contract['version'] or version.startswith(contract['version'] + '.'), 'Python version drift'
for entry in sys.path:
    path = pathlib.Path(entry).resolve()
    if 'site-packages' in path.parts or 'dist-packages' in path.parts:
        assert path.is_relative_to(root), 'sys.path leaked global site packages'
    assert path.is_relative_to(root) or path.is_relative_to(pathlib.Path(sys.base_prefix).resolve()), 'sys.path leaked an external directory'
versions = {name: importlib.metadata.version(name) for name in contract['pins']}
assert versions == contract['pins'], 'installed dependency version drift'
stdlib_roots = {pathlib.Path(sysconfig.get_path(name)).resolve() for name in ('stdlib', 'platstdlib')}
distribution_map = importlib.metadata.packages_distributions()
for name in contract['imports']:
    module = importlib.import_module(name)
    origin = getattr(module, '__file__', None)
    locations = list(getattr(module, '__path__', ()))
    top = name.split('.')[0]
    def standard_path(value):
        path = pathlib.Path(value).resolve()
        return (top in sys.stdlib_module_names and
                not {'site-packages', 'dist-packages'}.intersection(path.parts) and
                any(path.is_relative_to(standard) for standard in stdlib_roots))
    spec = getattr(module, '__spec__', None)
    intrinsic = origin is None and not locations and spec is not None and spec.origin in {'built-in', 'frozen'}
    if intrinsic:
        assert top in sys.stdlib_module_names, 'nonstandard intrinsic import is outside silo'
        continue
    paths = ([origin] if origin else []) + locations
    assert paths, 'import has no verifiable origin or namespace paths'
    inside = all(pathlib.Path(path).resolve().is_relative_to(root) for path in paths)
    standard = all(standard_path(path) for path in paths)
    assert inside or standard, 'import origin or namespace path is outside silo'
    if standard:
        continue
    distributions = distribution_map.get(top, [])
    assert distributions, 'unversioned import inside silo'
    for distribution in distributions:
        key = re.sub(r'[-_.]+', '-', distribution).lower()
        assert key in contract['pins'], 'imported dependency is not pinned'
print(json.dumps({'python_version': version, 'packages': versions, 'imports': contract['imports']}))
"""
    contract = json.dumps({"root": str(root), "version": python_version, "pins": pins, "imports": list(imports)})
    try:
        result = subprocess.run(
            [str(python), "-I", "-c", script, contract],
            env=isolated_environment(), capture_output=True, text=True, timeout=30, check=True,
        )
        subprocess.run(
            [str(python), "-I", "-m", "pip", "check"],
            env=isolated_environment(), capture_output=True, text=True, timeout=60, check=True,
        )
        return json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise MicroSiloValidationError(f"Micro-silo validation failed for {root}: {detail}") from exc


def provision_isolated_silo(
    root: str | Path, *, python_version: str, requirements: Sequence[str] = (), imports: Sequence[str] = (),
) -> dict:
    """Create a native venv and install a closed set of pinned dependencies.

    Existing silos are verified without repairing drift silently. Missing
    transitive dependencies fail ``pip check``; the caller must pin them too.
    """
    root = Path(root).resolve()
    from cochem.core.context import assert_writable_path
    assert_writable_path(root)
    validate_pins(requirements)
    python = root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        current = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        if current != python_version and not current.startswith(python_version + "."):
            raise MicroSiloValidationError(f"Requested Python {python_version}; provisioner runs {current}")
        if root.exists() and any(root.iterdir()):
            raise MicroSiloValidationError(f"Refusing to overwrite a nonempty silo directory: {root}")
        root.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run([sys.executable, "-I", "-m", "venv", str(root)], env=isolated_environment(), check=True, capture_output=True, text=True, timeout=120)
            if requirements:
                subprocess.run(
                    [str(python), "-I", "-m", "pip", "install", "--disable-pip-version-check", "--no-input", "--no-deps", *requirements],
                    env=isolated_environment(), check=True, capture_output=True, text=True, timeout=300,
                )
        except (OSError, subprocess.SubprocessError) as exc:
            raise MicroSiloValidationError(f"Could not provision {root}: {getattr(exc, 'stderr', '') or exc}") from exc
    return verify_micro_silo(root, python_version=python_version, requirements=requirements, imports=imports)
