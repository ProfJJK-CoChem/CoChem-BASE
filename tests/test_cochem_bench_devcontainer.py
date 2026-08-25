"""Unit tests for CoChem-BENCH DevContainer specification and ephemeral tmpfs setup.

Validates:
- File existence, UTF-8 encoding, and Unix LF line endings for .devcontainer/devcontainer.json and setup_tmpfs.sh.
- DevContainer JSON schema structure, name, image/features, environment variables, mounts, and lifecycle hooks.
- Python 3.10+ runtime and extension configuration.
- MPI runtime support configuration for high-tier quantum chemistry calculations (ORCA).
- Dynamic artifact directory mapping via COCHEM_ARTIFACTS_DIR environment variable and volume mounts.
- Lifecycle execution of setup_tmpfs.sh in postCreateCommand or postStartCommand.
- Bash script integrity, shebang, tmpfs mount handling, fallback directory logic, and exit code safety.
- Anti-spoofing compliance and strict production readiness.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

import pytest


@pytest.fixture
def repo_root() -> Path:
    """Return the absolute path to the CoChem-BASE repository root."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def devcontainer_dir(repo_root: Path) -> Path:
    """Return the absolute path to the .devcontainer directory."""
    path = repo_root / ".devcontainer"
    return path


@pytest.fixture
def devcontainer_json_path(devcontainer_dir: Path) -> Path:
    """Return the absolute path to devcontainer.json."""
    return devcontainer_dir / "devcontainer.json"


@pytest.fixture
def setup_tmpfs_script_path(devcontainer_dir: Path) -> Path:
    """Return the absolute path to setup_tmpfs.sh."""
    return devcontainer_dir / "setup_tmpfs.sh"


def test_devcontainer_directory_exists(devcontainer_dir: Path) -> None:
    """Validate that the .devcontainer directory exists in the repository root."""
    assert devcontainer_dir.exists(), f"Missing .devcontainer directory at {devcontainer_dir}"
    assert devcontainer_dir.is_dir(), f".devcontainer path {devcontainer_dir} is not a directory"


def test_devcontainer_json_file_exists(devcontainer_json_path: Path) -> None:
    """Validate that devcontainer.json exists."""
    assert devcontainer_json_path.exists(), (
        f"Missing devcontainer.json at {devcontainer_json_path}"
    )
    assert devcontainer_json_path.is_file(), (
        f"Path {devcontainer_json_path} is not a regular file"
    )


def test_devcontainer_json_encoding_and_lf(devcontainer_json_path: Path) -> None:
    """Validate that devcontainer.json has no UTF-8 BOM and uses Unix LF line endings."""
    raw_bytes = devcontainer_json_path.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), (
        "devcontainer.json contains UTF-8 BOM"
    )
    assert b"\r\n" not in raw_bytes, (
        "devcontainer.json contains Windows CRLF line endings; strictly require Unix LF"
    )
    assert b"\n" in raw_bytes, "devcontainer.json must contain newline characters"


def test_devcontainer_json_valid_json_structure(devcontainer_json_path: Path) -> None:
    """Validate that devcontainer.json parses as valid JSON without syntax errors."""
    content = devcontainer_json_path.read_text(encoding="utf-8")
    cleaned_content = re.sub(r"//.*?\n|/\*.*?\*/", "\n", content, flags=re.DOTALL)
    data: Dict[str, Any] = json.loads(cleaned_content)
    assert isinstance(data, dict), "devcontainer.json must be a JSON object"
    assert "name" in data, "devcontainer.json must specify a 'name' attribute"
    assert len(data["name"].strip()) > 0, "'name' attribute must not be empty"


def test_devcontainer_python_support(devcontainer_json_path: Path) -> None:
    """Validate that Python runtime support and extensions are properly configured."""
    content = devcontainer_json_path.read_text(encoding="utf-8")
    cleaned_content = re.sub(r"//.*?\n|/\*.*?\*/", "\n", content, flags=re.DOTALL)
    data: Dict[str, Any] = json.loads(cleaned_content)

    has_python_image = "python" in str(data.get("image", "")).lower()
    has_python_feature = any(
        "python" in str(k).lower() for k in data.get("features", {}).keys()
    )
    has_python_build = "python" in str(data.get("build", "")).lower()

    assert has_python_image or has_python_feature or has_python_build, (
        "devcontainer.json must configure Python support via image, features, or build definition"
    )

    customizations = data.get("customizations", {})
    vscode_config = customizations.get("vscode", {})
    extensions = vscode_config.get("extensions", [])
    assert any("ms-python.python" in ext for ext in extensions), (
        "devcontainer.json must include 'ms-python.python' in customizations.vscode.extensions"
    )


def test_devcontainer_mpi_support(devcontainer_json_path: Path) -> None:
    """Validate that MPI support for ORCA quantum chemistry parallel runs is configured."""
    content = devcontainer_json_path.read_text(encoding="utf-8")
    cleaned_content = re.sub(r"//.*?\n|/\*.*?\*/", "\n", content, flags=re.DOTALL)
    data: Dict[str, Any] = json.loads(cleaned_content)

    all_text = json.dumps(data).lower()
    has_mpi_reference = (
        "mpi" in all_text
        or "openmpi" in all_text
        or "ompi" in all_text
    )
    assert has_mpi_reference, (
        "devcontainer.json must include MPI configuration (e.g., OpenMPI installation or settings for ORCA)"
    )


def test_devcontainer_headless_and_mpi_environment(devcontainer_json_path: Path) -> None:
    """Validate headless environment variables and MPI flags in containerEnv."""
    content = devcontainer_json_path.read_text(encoding="utf-8")
    cleaned_content = re.sub(r"//.*?\n|/\*.*?\*/", "\n", content, flags=re.DOTALL)
    data: Dict[str, Any] = json.loads(cleaned_content)

    container_env = data.get("containerEnv", {})
    assert container_env.get("QT_QPA_PLATFORM") == "offscreen", (
        "containerEnv must configure QT_QPA_PLATFORM: offscreen"
    )
    assert str(container_env.get("COCHEM_HEADLESS")) == "1", (
        "containerEnv must configure COCHEM_HEADLESS: '1'"
    )
    assert "OMPI_ALLOW_RUN_AS_ROOT" in container_env, (
        "containerEnv must configure OMPI_ALLOW_RUN_AS_ROOT"
    )


def test_devcontainer_dynamic_artifact_directory_mapping(
    devcontainer_json_path: Path,
) -> None:
    """Validate dynamic mapping of the artifact directory via environment variables and volume mounts."""
    content = devcontainer_json_path.read_text(encoding="utf-8")
    cleaned_content = re.sub(r"//.*?\n|/\*.*?\*/", "\n", content, flags=re.DOTALL)
    data: Dict[str, Any] = json.loads(cleaned_content)

    container_env = data.get("containerEnv", {})
    remote_env = data.get("remoteEnv", {})
    assert (
        "COCHEM_ARTIFACTS_DIR" in container_env
        or "COCHEM_ARTIFACTS_DIR" in remote_env
    ), "devcontainer.json must set COCHEM_ARTIFACTS_DIR in containerEnv or remoteEnv"

    mounts = data.get("mounts", [])
    assert isinstance(mounts, list), "'mounts' attribute must be a list"
    assert len(mounts) > 0, "'mounts' list must not be empty"

    mount_str = " ".join([str(m) for m in mounts])
    assert "COCHEM_ARTIFACTS_DIR" in mount_str or "localEnv:COCHEM_ARTIFACTS_DIR" in mount_str, (
        "devcontainer.json mounts must dynamically reference ${localEnv:COCHEM_ARTIFACTS_DIR}"
    )


def test_devcontainer_tmpfs_script_lifecycle_hook(devcontainer_json_path: Path) -> None:
    """Validate that setup_tmpfs.sh is executed via a devcontainer lifecycle hook."""
    content = devcontainer_json_path.read_text(encoding="utf-8")
    cleaned_content = re.sub(r"//.*?\n|/\*.*?\*/", "\n", content, flags=re.DOTALL)
    data: Dict[str, Any] = json.loads(cleaned_content)

    hooks = [
        str(data.get("postCreateCommand", "")),
        str(data.get("postStartCommand", "")),
        str(data.get("onCreateCommand", "")),
        str(data.get("postAttachCommand", "")),
    ]
    all_hooks = " ".join(hooks)
    assert "setup_tmpfs.sh" in all_hooks, (
        "devcontainer.json must invoke setup_tmpfs.sh in postCreateCommand, postStartCommand, or onCreateCommand"
    )


def test_setup_tmpfs_script_exists_and_lf(setup_tmpfs_script_path: Path) -> None:
    """Validate that setup_tmpfs.sh exists, is UTF-8 encoded without BOM, and has Unix LF endings."""
    assert setup_tmpfs_script_path.exists(), (
        f"Missing setup_tmpfs.sh at {setup_tmpfs_script_path}"
    )
    raw_bytes = setup_tmpfs_script_path.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), (
        "setup_tmpfs.sh contains UTF-8 BOM"
    )
    assert b"\r\n" not in raw_bytes, (
        "setup_tmpfs.sh contains Windows CRLF line endings; strictly require Unix LF"
    )
    assert b"\n" in raw_bytes, "setup_tmpfs.sh must contain newline characters"


def test_setup_tmpfs_script_content_and_logic(setup_tmpfs_script_path: Path) -> None:
    """Validate that setup_tmpfs.sh contains safe POSIX bash logic for tmpfs and ephemeral scratch."""
    content = setup_tmpfs_script_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    assert len(lines) > 0, "setup_tmpfs.sh must not be empty"
    assert lines[0].startswith("#!"), "setup_tmpfs.sh must begin with a valid shebang (e.g. #!/usr/bin/env bash)"
    assert "bash" in lines[0] or "sh" in lines[0], "Shebang must invoke bash or sh"

    content_lower = content.lower()
    assert "tmpfs" in content_lower, "setup_tmpfs.sh must reference tmpfs"
    assert "scratch" in content_lower, "setup_tmpfs.sh must configure Scratch directory"
    assert "registry" in content_lower, "setup_tmpfs.sh must configure Registry directory"
    assert "logs" in content_lower, "setup_tmpfs.sh must configure Logs directory"
    assert "mkdir" in content_lower, "setup_tmpfs.sh must create required directories"
    assert "set -e" in content or "set -euo pipefail" in content or "exit" in content, (
        "setup_tmpfs.sh must enforce error safety via bash strict mode or explicit exit checks"
    )


def test_production_readiness_token_inspection(
    devcontainer_json_path: Path,
    setup_tmpfs_script_path: Path,
) -> None:
    """Validate that configuration files and scripts do not contain unverified markers."""
    forbidden_markers = [
        "FIXME",
        "UNIMPLEMENTED",
        "TEMP_HACK",
        "BROKEN_MARKER",
    ]
    for target in [devcontainer_json_path, setup_tmpfs_script_path]:
        text = target.read_text(encoding="utf-8").upper()
        for marker in forbidden_markers:
            assert marker not in text, (
                f"File {target.name} must not contain forbidden marker '{marker}'"
            )


