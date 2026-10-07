"""Read the canonical package version without importing scientific dependencies."""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import tomllib


def get_version() -> str:
    """Prefer the reviewed checkout metadata; installed wheels use their metadata."""
    project_file = Path(__file__).resolve().parents[2] / "pyproject.toml"
    if project_file.is_file():
        with project_file.open("rb") as source:
            project = tomllib.load(source).get("project", {})
        if project.get("name", "").lower().replace("_", "-") == "cochem-base":
            return str(project["version"])
    try:
        return version("CoChem-BASE")
    except PackageNotFoundError:
        return "unknown"


__version__ = get_version()
