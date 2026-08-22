"""Portable path mappings used by repository audit utilities."""

import os
import re
from pathlib import Path

from cochem_base.config_loader import get_base_root, resolve_mapped_path


def get_agents_dir(base_root: Path | None = None) -> Path:
    configured = os.environ.get("COCHEM_AGENTS_DIR")
    if configured:
        return resolve_mapped_path(configured, get_base_root())
    root = base_root if base_root is not None else get_base_root()
    return (root / ".agents").resolve()


def get_agent_templates_dir() -> Path:
    configured = os.environ.get("COCHEM_GEMINI_AGENTS_DIR")
    return (
        resolve_mapped_path(configured, Path.home())
        if configured
        else (Path.home() / ".gemini" / "config" / "agents").resolve()
    )


def placeholder_values(custom_mappings: dict[str, str | Path] | None = None) -> dict[str, Path]:
    workspace = resolve_mapped_path(
        os.environ.get("COCHEM_WORKSPACE_ROOT", get_base_root().parent),
        get_base_root().parent,
    )
    shared_root = resolve_mapped_path(
        os.environ.get("COCHEM_SHARED_ROOT", workspace.parent),
        workspace.parent,
    )
    placeholders = {
        "<USER_HOME>": Path.home().resolve(),
        "<COCHEM_WORKSPACE>": workspace.resolve(),
        "<GDRIVE_ROOT>": shared_root.resolve(),
    }
    if custom_mappings:
        for k, v in custom_mappings.items():
            placeholders[k] = (Path(v).resolve() if not isinstance(v, Path) else v.resolve())
    return placeholders


def path_variants(path: Path) -> tuple[str, ...]:
    native = str(path)
    posix = path.as_posix()
    variants = [native, posix]
    if "\\" in native:
        variants.append(native.replace("\\", "\\\\"))
    seen = set()
    deduped = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            deduped.append(v)
    return tuple(sorted(deduped, key=len, reverse=True))


def sanitize_local_paths(content: str, custom_placeholders: dict[str, Path] | None = None) -> str:
    sanitized = content
    placeholders = custom_placeholders if custom_placeholders is not None else placeholder_values()
    values = sorted(placeholders.items(), key=lambda item: len(str(item[1])), reverse=True)
    for placeholder, path in values:
        for variant in path_variants(path):
            sanitized = re.sub(re.escape(variant), placeholder, sanitized, flags=re.IGNORECASE)
    return sanitized


def leak_patterns(custom_placeholders: dict[str, Path] | None = None) -> list[tuple[re.Pattern[str], str]]:
    patterns: list[tuple[re.Pattern[str], str]] = []
    placeholders = custom_placeholders if custom_placeholders is not None else placeholder_values()
    for placeholder, path in placeholders.items():
        for variant in path_variants(path):
            patterns.append((re.compile(re.escape(variant), re.IGNORECASE), placeholder))
    return patterns


def find_path_leaks(content: str, custom_placeholders: dict[str, Path] | None = None) -> list[tuple[int, str, str]]:
    leaks: list[tuple[int, str, str]] = []
    patterns = leak_patterns(custom_placeholders)
    for line_idx, line in enumerate(content.splitlines(), start=1):
        for pattern, token in patterns:
            if pattern.search(line):
                leaks.append((line_idx, token, line))
                break
    return leaks


def is_sanitized(content: str, custom_placeholders: dict[str, Path] | None = None) -> bool:
    return len(find_path_leaks(content, custom_placeholders)) == 0

