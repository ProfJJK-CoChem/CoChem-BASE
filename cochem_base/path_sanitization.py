"""Portable path mappings used by repository audit utilities."""

import os
import re
from pathlib import Path
from typing import Dict, List, Pattern, Tuple

from cochem_base.config_loader import get_base_root, resolve_mapped_path


def get_agents_dir() -> Path:
    configured = os.environ.get("COCHEM_AGENTS_DIR")
    return resolve_mapped_path(configured, get_base_root()) if configured else get_base_root() / ".agents"


def get_agent_templates_dir() -> Path:
    configured = os.environ.get("COCHEM_GEMINI_AGENTS_DIR")
    return (
        resolve_mapped_path(configured, Path.home())
        if configured
        else Path.home() / ".gemini" / "config" / "agents"
    )


def placeholder_values() -> Dict[str, Path]:
    workspace = resolve_mapped_path(
        os.environ.get("COCHEM_WORKSPACE_ROOT", get_base_root().parent),
        get_base_root().parent,
    )
    shared_root = resolve_mapped_path(
        os.environ.get("COCHEM_SHARED_ROOT", workspace.parent),
        workspace.parent,
    )
    return {
        "<USER_HOME>": Path.home().resolve(),
        "<COCHEM_WORKSPACE>": workspace,
        "<GDRIVE_ROOT>": shared_root,
    }


def path_variants(path: Path) -> Tuple[str, ...]:
    native = str(path)
    posix = path.as_posix()
    return tuple(dict.fromkeys((native, posix)))


def sanitize_local_paths(content: str) -> str:
    sanitized = content
    values = sorted(placeholder_values().items(), key=lambda item: len(str(item[1])), reverse=True)
    for placeholder, path in values:
        for variant in path_variants(path):
            sanitized = re.sub(re.escape(variant), placeholder, sanitized, flags=re.IGNORECASE)
    return sanitized


def leak_patterns() -> List[Tuple[Pattern[str], str]]:
    patterns: List[Tuple[Pattern[str], str]] = []
    for placeholder, path in placeholder_values().items():
        for variant in path_variants(path):
            patterns.append((re.compile(re.escape(variant), re.IGNORECASE), placeholder))
    return patterns
