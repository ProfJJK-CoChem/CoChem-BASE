"""Constrain reviewed BASE source in ordinary and explicit isolated children.

Only namespaces present in the copied source are constrained. Registered
third-party providers and installed runtimes retain their actual locations.
"""
from __future__ import annotations

import atexit
import hashlib
import importlib.util
import json
import os
import runpy
import sys
import tomllib
import uuid
from pathlib import Path
from typing import Any

CONTEXT_KEYS = ("COCHEM_SOURCE_QUARANTINE_ROOT", "COCHEM_SOURCE_QUARANTINE_ORIGINAL",
                "COCHEM_SOURCE_QUARANTINE_EVIDENCE", "COCHEM_SOURCE_QUARANTINE_REVISION")
_active: dict[str, Any] | None = None
FORBIDDEN_ROOTS_KEY = "COCHEM_SOURCE_QUARANTINE_RETIRED_ROOTS"


def inside(path: Any, root: Path) -> bool:
    try:
        return Path(path).resolve().is_relative_to(root)
    except (TypeError, ValueError, OSError):
        return False


def source_paths(copied: Path) -> list[str]:
    return [str(copied / "ci_tools/quarantine_startup"), str(copied / "src"),
            str(copied / "src/cochem_base"), str(copied), str(copied / "Libraries")]


def _project_identity(root: Path) -> str | None:
    try:
        value = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8")).get("project", {}).get("name")
    except (OSError, ValueError):
        return None
    return value.lower().replace("_", "-").replace(".", "-") if isinstance(value, str) else None


def _foreign_checkout_source(path: Any, state: dict[str, Any], projects: dict[Path, str | None],
                             *, resolved: Path | None = None) -> bool:
    """Recognize aliases from an actual other BASE checkout by file ownership.

    Discovery reads only ancestor metadata and reviewed relative source paths.
    It never blocks the other project's unrelated providers or executes Git.
    Positive roots remain observed foreign lineage even if metadata changes.
    """
    if not state.get("project_identity"):
        return False
    try:
        actual = Path(path).resolve() if resolved is None else resolved
        if actual.is_relative_to(state["copied"]):
            return False
        for ancestor in actual.parents:
            if ancestor not in projects:
                projects[ancestor] = _project_identity(ancestor)
            if projects[ancestor] != state["project_identity"]:
                continue
            relative = actual.relative_to(ancestor)
            for subtree in state["source_subtrees"]:
                if relative == subtree or subtree in relative.parents:
                    state["retired_roots"].add((ancestor / subtree).resolve())
                    return True
    except (TypeError, ValueError, OSError):
        return False
    return False


def loaded_origins(state: dict[str, Any]) -> dict[str, Any]:
    origins, escaped, projects = {}, [], {}
    for name, module in list(sys.modules.items()):
        if module is None:
            continue
        paths = list(getattr(module, "__path__", ()) or ())
        filename = getattr(module, "__file__", None)
        # Python's real stdin entry point uses a compiler label, not a source
        # file. Keep aliases and every actual namespace path under inspection.
        stdin_main = (name == "__main__" and module is sys.modules.get("__main__")
                      and filename == "<stdin>" and sys.argv[:1] == ["-"]
                      and getattr(module, "__spec__", None) is None)
        if filename and not stdin_main:
            paths.append(filename)
        # Re-resolve on every observation so moved symlinks remain visible.
        # Resolving once per module path avoids filesystem work for each
        # retired root without caching authority across observations.
        resolved_paths: list[Path | None] = []
        for path in paths:
            try:
                resolved_paths.append(Path(path).resolve())
            except (TypeError, ValueError, OSError):
                resolved_paths.append(None)
        # Path equality/hash preserve the host's filesystem case rules.
        # Ancestor membership avoids raising/catching relative_to errors for
        # every unrelated retired root; all paths were freshly resolved above.
        ancestors = [frozenset((path, *path.parents)) if path is not None else frozenset()
                     for path in resolved_paths]
        owned = name.split(".")[0] in state["owned"]
        foreign_source = any(not parents.isdisjoint(state.get("retired_roots", ())) for parents in ancestors)
        if not foreign_source:
            foreign_source = any(path is not None and _foreign_checkout_source(path, state, projects, resolved=path)
                                 for path in resolved_paths)
        if owned or foreign_source or any(state["copied"] in parents for parents in ancestors):
            origins[name] = paths
        if foreign_source or any(state["original"] in parents for parents in ancestors) or (
                owned and any(state["copied"] not in parents for parents in ancestors)):
            escaped.append(name)
    if _active is state:
        os.environ[FORBIDDEN_ROOTS_KEY] = json.dumps(sorted(str(root) for root in state["retired_roots"]))
    return {"origins": origins, "escaped": escaped}


def constrain_source(copied: Path, original: Path) -> dict[str, Any]:
    copied, original = copied.resolve(), original.resolve()
    if copied == original or not copied.is_dir() or not original.is_dir():
        raise RuntimeError("[HARD_ABORT: SOURCE QUARANTINE ESCAPE] Invalid source boundary")
    owned: set[str] = set()
    subtrees: set[Path] = set()
    for base in (copied / "src", copied / "src/cochem_base", copied):
        if not base.is_dir():
            continue
        for entry in base.iterdir():
            name = entry.stem if entry.is_file() and entry.suffix == ".py" else entry.name
            if name.isidentifier() and ((entry.is_file() and entry.suffix == ".py")
                                       or (entry.is_dir() and any(entry.rglob("*.py")))):
                owned.add(name)
                subtrees.add(entry.relative_to(copied))
    inherited = json.loads(os.environ.get(FORBIDDEN_ROOTS_KEY, "[]"))
    if not isinstance(inherited, list) or any(not isinstance(path, str) or not Path(path).is_absolute()
                                            or inside(path, copied) for path in inherited):
        raise RuntimeError("[HARD_ABORT: SOURCE QUARANTINE ESCAPE] Invalid retired source lineage")
    roots = {Path(path).resolve() for path in inherited}
    # Collect the precise owned paths before checking already-loaded modules;
    # an actual BASE file remains foreign even when imported under an alias.
    for module in list(sys.modules.values()):
        mapping, namespaces = getattr(module, "MAPPING", None), getattr(module, "NAMESPACES", None)
        if not isinstance(mapping, dict) or not isinstance(namespaces, dict):
            continue
        for key in set(mapping) | set(namespaces):
            if key.split(".")[0] not in owned:
                continue
            values = [mapping[key]] if key in mapping else []
            values.extend(namespaces.get(key, []))
            for value in values:
                path = Path(value)
                if not path.is_absolute() or inside(path, copied):
                    continue
                candidates = [path] if path.is_dir() else [path, path.with_suffix(".py"), path.with_suffix(".pyc")]
                roots.update(candidate.resolve() for candidate in candidates)
    state = {"copied": copied, "original": original, "owned": owned, "retired_roots": roots,
             "project_identity": _project_identity(copied),
             "source_subtrees": sorted(subtrees, key=lambda path: len(path.parts), reverse=True)}
    # Previously loaded foreign BASE modules must be refused, never discarded
    # to hide an import that already executed before this startup boundary.
    if loaded_origins(state)["escaped"]:
        raise RuntimeError("[HARD_ABORT: SOURCE QUARANTINE ESCAPE] Previously loaded source escaped")
    sys.path[:] = [entry for entry in sys.path if entry and not inside(entry, original)]
    retired, removed = set(), {}
    for name, module in list(sys.modules.items()):
        mapping, namespaces = getattr(module, "MAPPING", None), getattr(module, "NAMESPACES", None)
        if not isinstance(mapping, dict) or not isinstance(namespaces, dict):
            continue
        selected = {key for key in set(mapping) | set(namespaces) if key.split(".")[0] in owned}
        if not selected:
            continue
        module.MAPPING = {key: value for key, value in mapping.items() if key not in selected}
        module.NAMESPACES = {key: value for key, value in namespaces.items() if key not in selected}
        removed[name] = sorted(selected)
        if not module.MAPPING and not module.NAMESPACES:
            retired.add(name)
            placeholder = getattr(module, "PATH_PLACEHOLDER", None)
            if placeholder is not None:
                sys.path[:] = [entry for entry in sys.path if entry != placeholder]
                sys.path_importer_cache.pop(placeholder, None)
    sys.meta_path[:] = [finder for finder in sys.meta_path if getattr(finder, "__module__", "") not in retired]
    sys.path_hooks[:] = [hook for hook in sys.path_hooks if getattr(hook, "__module__", "") not in retired]
    if loaded_origins(state)["escaped"]:
        raise RuntimeError("[HARD_ABORT: SOURCE QUARANTINE ESCAPE] Previously loaded retired source escaped")
    sys.path[:0] = [path for path in source_paths(copied) if path not in sys.path]
    initial = {}
    for name in sorted(owned):
        spec = importlib.util.find_spec(name)
        if spec is None:
            continue
        paths = list(spec.submodule_search_locations or ())
        if spec.origin not in (None, "built-in", "frozen"):
            paths.append(spec.origin)
        if any(not inside(path, copied) for path in paths):
            raise RuntimeError("[HARD_ABORT: SOURCE QUARANTINE ESCAPE] Initial package origin escaped")
        initial[name] = paths
    state.update(initial=initial, removed=removed)
    return state


def _receipt(state: dict[str, Any], stage: str, result: dict[str, Any]) -> None:
    record = {"schema_version": 1, "pid": os.getpid(), "parent_pid": os.getppid(),
              "interpreter": sys.executable, "stage": stage,
              "source_root": str(state["copied"]), "original_root": str(state["original"]),
              "source_revision": state["revision"],
              "startup_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "retired_source_roots": sorted(str(root) for root in state.get("retired_roots", ())),
              **result}
    path = state["evidence"] / (str(os.getpid()) + "-" + state["instance"] + "-" + stage + ".json")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _finish(state: dict[str, Any]) -> None:
    try:
        result = loaded_origins(state)
        result["passed"] = not result["escaped"]
        _receipt(state, "final", result)
        if not result["passed"]:
            raise RuntimeError("[HARD_ABORT: SOURCE QUARANTINE ESCAPE] Child imported foreign source")
    except BaseException:
        os.write(2, b"[HARD_ABORT: SOURCE QUARANTINE ESCAPE] Child source verification failed\n")
        os._exit(1)


def activate_from_environment() -> dict[str, Any] | None:
    """Start a source-bound child; startup errors must escape to the shim."""
    global _active
    if not any(os.environ.get(key) for key in CONTEXT_KEYS):
        return None
    if not all(os.environ.get(key) for key in CONTEXT_KEYS):
        raise RuntimeError("[HARD_ABORT: SOURCE QUARANTINE ESCAPE] Incomplete child authority")
    declared_evidence = Path(os.environ[CONTEXT_KEYS[2]])
    copied, original, evidence = (Path(os.environ[key]).resolve() for key in CONTEXT_KEYS[:3])
    if (not declared_evidence.is_absolute() or declared_evidence.is_symlink() or not evidence.is_dir() or inside(evidence, copied)
            or inside(evidence, original) or Path(__file__).resolve().parents[1] != copied):
        raise RuntimeError("[HARD_ABORT: SOURCE QUARANTINE ESCAPE] Child startup source or evidence escaped")
    if _active is not None:
        if (_active["copied"] != copied or _active["original"] != original
                or _active["evidence"] != evidence or _active["revision"] != os.environ[CONTEXT_KEYS[3]]):
            raise RuntimeError("[HARD_ABORT: SOURCE QUARANTINE ESCAPE] Child authority changed")
        return _active
    preliminary = {"copied": copied, "original": original, "evidence": evidence,
                   "revision": os.environ[CONTEXT_KEYS[3]], "instance": uuid.uuid4().hex}
    try:
        state = constrain_source(copied, original)
    except BaseException as error:
        _receipt(preliminary, "initial", {"passed": False, "error_type": type(error).__name__})
        raise
    state.update(evidence=evidence, revision=preliminary["revision"], instance=preliminary["instance"])
    os.environ[FORBIDDEN_ROOTS_KEY] = json.dumps(sorted(str(root) for root in state["retired_roots"]))
    _receipt(state, "initial", {"passed": True, "origins": state["initial"], "removed_editables": state["removed"]})
    atexit.register(_finish, state)
    _active = state
    return state


def source_child_environment(environment: dict[str, str], *, selected_source: Path) -> dict[str, str]:
    """Restore only this active reviewed source after a build-env scrub.

    Ordinary interface setup keeps its clean build environment. A canonical
    source profile already owns a specific copied source, so its dependency
    probes must use that source rather than a foreign editable installation.
    """
    result = dict(environment)
    state = activate_from_environment()
    if state is None:
        return result
    if selected_source.resolve() != state["copied"]:
        raise RuntimeError("[HARD_ABORT: SOURCE QUARANTINE ESCAPE] Probe selected another source")
    result.update({key: os.environ[key] for key in CONTEXT_KEYS})
    result[FORBIDDEN_ROOTS_KEY] = json.dumps(sorted(str(root) for root in state["retired_roots"]))
    result["PYTHONPATH"] = os.pathsep.join(source_paths(state["copied"]))
    return result


def main() -> int:
    """Explicit source-bound launch for Python -I, which ignores PYTHONPATH."""
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    state = activate_from_environment()
    if state is None or len(sys.argv) < 2:
        raise ValueError("An isolated source child requires its authority and a tracked source script")
    script = Path(sys.argv[1]).resolve()
    if not script.is_file() or not script.is_relative_to(state["copied"]):
        raise ValueError("The isolated source script must be inside reviewed copied source")
    from ci_tools.base_ci import _git

    relative = script.relative_to(state["copied"]).as_posix()
    if relative not in _git(state["copied"], ["ls-files", "-z", "--", relative]).decode("utf-8").split("\0"):
        raise ValueError("The isolated source script must be tracked reviewed source")
    sys.argv = sys.argv[1:]
    runpy.run_path(str(script), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
