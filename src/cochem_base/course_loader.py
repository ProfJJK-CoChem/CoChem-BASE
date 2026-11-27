"""CoChem-BASE dynamic CoChem-CURE course acquisition & pathway loader.

Pure-stdlib module (with optional runtime import of ``cochem_cure.provider``)
implementing the "Is this a course?" split between standalone ``CoChem-BASE``
research workflows and dynamic ``ProfJJK-CoChem/CoChem-CURE`` course profiles.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "cochem.course-provider/1"
COURSE_MODE_STATE_SCHEMA = "cochem.course-mode-state/1"
DEFAULT_FALLBACK_COURSE_IDS: tuple[str, ...] = (
    "CHEM311",
    "CHEM312",
    "CHEM490",
    "CHEM410",
    "CHEM411",
)
CURE_REPOSITORY = "ProfJJK-CoChem/CoChem-CURE"
CURE_REPO_URL = "https://github.com/ProfJJK-CoChem/CoChem-CURE.git"

_REQUIRED_PROVIDER_ATTRS: tuple[str, ...] = (
    "SCHEMA_VERSION",
    "list_courses",
    "get_course_profile",
    "get_course_pathway",
    "get_course_milestones",
    "get_allowed_course_ids",
    "validate_course_id",
)
_CURE_MISSING_MSG = (
    "CoChem-CURE is not installed; answer Yes to 'Is this a course?' to obtain it."
)
_ALLOWED_URL_PREFIXES: tuple[str, ...] = (
    "https://",
    "http://",
    "git+https://",
    "git+http://",
    "file://",
    "git+file://",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_artifact_root(artifact_dir: Path | str | None = None) -> Path:
    """Resolve the persistent artifact root honoring COCHEM_ARTIFACT_DIR (fail-closed on symlinks)."""
    raw = (
        artifact_dir
        if artifact_dir is not None
        else (
            os.environ.get("COCHEM_ARTIFACT_DIR")
            or os.environ.get("COCHEM_ARTIFACTS")
            or (Path.home() / "CoChem_Artifacts")
        )
    )
    candidate = Path(raw).expanduser()
    if candidate.is_symlink():
        raise ValueError(f"Refusing symlinked artifact directory: {candidate}")
    # Walk existing parent components to reject symlink traversal in the leaf chain.
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate)
    for part in candidate.parts:
        if part == "..":
            raise ValueError(f"Path traversal ('..') is forbidden in artifact_dir: {raw!r}")
    resolved = candidate.resolve()
    if resolved.is_symlink():
        raise ValueError(f"Refusing symlinked resolved artifact directory: {resolved}")
    return resolved


def _course_mode_state_path(artifact_dir: Path | str | None = None) -> tuple[Path, Path]:
    """Return ``(artifact_root, <artifact_root>/StudentSetup/course-mode.json)`` with symlink/traversal checks."""
    root = _resolve_artifact_root(artifact_dir)
    setup_dir = root / "StudentSetup"
    if setup_dir.is_symlink():
        raise ValueError(f"Refusing symlinked StudentSetup directory: {setup_dir}")
    state_path = setup_dir / "course-mode.json"
    if state_path.is_symlink():
        raise ValueError(f"Refusing symlinked course-mode state file: {state_path}")
    resolved_setup = setup_dir.resolve()
    resolved_state = state_path.resolve()
    try:
        resolved_setup.relative_to(root)
        resolved_state.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"course-mode state path escaped artifact root {root}: {state_path}"
        ) from exc
    return root, state_path


def _default_course_mode_state() -> dict[str, Any]:
    return {
        "schema": COURSE_MODE_STATE_SCHEMA,
        "is_course": False,
        "mode": "research",
        "selected_course_id": None,
        "cure_repository": CURE_REPOSITORY,
        "updated_at_utc": None,
    }


def _validate_selected_course_id(selected_course_id: str | None) -> str | None:
    if selected_course_id is None:
        return None
    if not isinstance(selected_course_id, str):
        raise ValueError(f"selected_course_id must be a string or None, got {type(selected_course_id).__name__}")
    cleaned = selected_course_id.strip()
    if not cleaned:
        return None
    if any(tok in cleaned for tok in ("/", "\\", "..", "\x00")):
        raise ValueError(f"Invalid selected_course_id: {selected_course_id!r}")
    return cleaned


def load_course_mode_state(artifact_dir: Path | None = None) -> dict[str, Any]:
    """Load persisted course-mode selection from ``<artifact_dir>/StudentSetup/course-mode.json``."""
    _, state_path = _course_mode_state_path(artifact_dir)
    if not state_path.exists():
        return _default_course_mode_state()
    if not state_path.is_file() or state_path.is_symlink():
        raise ValueError(f"Expected a regular file for course-mode state: {state_path}")
    raw = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError(f"Malformed course-mode state in {state_path}: expected JSON object")
    is_course = bool(raw.get("is_course", False))
    selected_course_id = _validate_selected_course_id(raw.get("selected_course_id"))
    if not is_course:
        selected_course_id = None
    return {
        "schema": str(raw.get("schema") or COURSE_MODE_STATE_SCHEMA),
        "is_course": is_course,
        "mode": "course" if is_course else "research",
        "selected_course_id": selected_course_id,
        "cure_repository": str(raw.get("cure_repository") or CURE_REPOSITORY),
        "updated_at_utc": raw.get("updated_at_utc"),
    }


def save_course_mode_state(
    is_course: bool,
    selected_course_id: str | None = None,
    artifact_dir: Path | None = None,
) -> Path:
    """Atomically persist course-mode selection to ``<artifact_dir>/StudentSetup/course-mode.json``."""
    if not isinstance(is_course, bool):
        raise ValueError(f"is_course must be a boolean, got {type(is_course).__name__}")
    cleaned_course_id = _validate_selected_course_id(selected_course_id) if is_course else None
    _, state_path = _course_mode_state_path(artifact_dir)
    setup_dir = state_path.parent
    setup_dir.mkdir(parents=True, exist_ok=True)
    if setup_dir.is_symlink():
        raise ValueError(f"Refusing symlinked StudentSetup directory: {setup_dir}")

    payload = {
        "schema": COURSE_MODE_STATE_SCHEMA,
        "is_course": is_course,
        "mode": "course" if is_course else "research",
        "selected_course_id": cleaned_course_id,
        "cure_repository": CURE_REPOSITORY,
        "updated_at_utc": _utc_now(),
    }
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"

    fd, tmp_name = tempfile.mkstemp(prefix=".course-mode-", suffix=".tmp", dir=str(setup_dir))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded)
        if state_path.is_symlink():
            raise ValueError(f"Refusing symlinked course-mode state file: {state_path}")
        os.replace(tmp_path, state_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    return state_path


def _import_cure_provider() -> Any | None:
    """Import ``cochem_cure.provider`` and validate its canonical schema and callable contract."""
    try:
        mod = importlib.import_module("cochem_cure.provider")
    except ImportError:
        return None
    if getattr(mod, "SCHEMA_VERSION", None) != SCHEMA_VERSION:
        return None
    for attr in _REQUIRED_PROVIDER_ATTRS[1:]:
        if not callable(getattr(mod, attr, None)):
            return None
    return mod


def _require_cure_provider() -> Any:
    mod = _import_cure_provider()
    if mod is None:
        raise RuntimeError(_CURE_MISSING_MSG)
    return mod


def is_cure_installed() -> bool:
    """Return True iff ``cochem_cure.provider`` is importable and matches ``cochem.course-provider/1``."""
    return _import_cure_provider() is not None


def _is_valid_cure_checkout(path: Path) -> bool:
    return path.is_dir() and not path.is_symlink() and (path / "pyproject.toml").is_file()


def _discover_local_cure_repo(local_repo_dir: Path | None = None) -> Path | None:
    if local_repo_dir is not None:
        explicit = Path(local_repo_dir).expanduser()
        if explicit.is_symlink():
            raise RuntimeError(f"Refusing symlinked local CoChem-CURE directory: {explicit}")
        resolved = explicit.resolve()
        if not _is_valid_cure_checkout(resolved):
            raise RuntimeError(
                f"Specified local_repo_dir is not a valid CoChem-CURE checkout (missing pyproject.toml): {resolved}"
            )
        return resolved

    candidates: list[Path] = []
    repos_env = os.environ.get("COCHEM_REPOS_DIR")
    if repos_env:
        candidates.append(Path(repos_env).expanduser() / "CoChem-CURE")

    # Sibling checkout relative to CoChem-BASE/src/cochem_base/course_loader.py
    here = Path(__file__).resolve()
    if len(here.parents) >= 4:
        candidates.append(here.parents[3] / "CoChem-CURE")

    for cand in candidates:
        if cand.is_symlink():
            continue
        if _is_valid_cure_checkout(cand) and (cand / ".git").exists():
            return cand.resolve()
    return None


def _extract_tar_safely(tar_path: Path, dest_dir: Path) -> None:
    dest_resolved = dest_dir.resolve()
    with tarfile.open(tar_path, "r") as archive:
        for member in archive.getmembers():
            if member.issym() or member.islnk():
                raise RuntimeError(f"Refusing symlink/hardlink in git archive: {member.name!r}")
            member_path = (dest_dir / member.name).resolve()
            try:
                member_path.relative_to(dest_resolved)
            except ValueError as exc:
                raise RuntimeError(f"Refusing path traversal in git archive: {member.name!r}") from exc
        if sys.version_info >= (3, 12):
            archive.extractall(dest_dir, filter="data")
        else:
            archive.extractall(dest_dir)


def _stage_local_repo_readonly(local_checkout: Path, stage_dir: Path, *, revision: str | None, timeout: float) -> str:
    """Export a read-only snapshot of ``local_checkout`` into ``stage_dir`` without writing to the source checkout."""
    if (local_checkout / ".git").exists():
        ref = revision.strip() if revision and revision.strip() else "HEAD"
        if ref.startswith("-") or any(ch.isspace() for ch in ref):
            raise RuntimeError(f"Invalid git revision: {revision!r}")
        tar_path = stage_dir.parent / "cure_archive.tar"
        proc = subprocess.run(
            ["git", "-C", str(local_checkout), "archive", "--format=tar", "-o", str(tar_path), ref],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout).strip()
            raise RuntimeError(
                f"git archive failed for local CoChem-CURE checkout {local_checkout} ({ref}): {detail}"
            )
        stage_dir.mkdir(parents=True, exist_ok=True)
        _extract_tar_safely(tar_path, stage_dir)
        return "local_git_archive"

    shutil.copytree(
        local_checkout,
        stage_dir,
        ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", "*.egg-info", "build", "dist", ".pytest_cache"),
        symlinks=False,
    )
    return "local_snapshot"


def _verify_cure_in_interpreter(python_executable: str, *, timeout: float) -> bool:
    """Verify ``cochem_cure.provider`` imports and satisfies ``SCHEMA_VERSION`` in the target interpreter."""
    target_same = False
    try:
        target_same = Path(python_executable).resolve() == Path(sys.executable).resolve()
    except OSError:
        target_same = python_executable == sys.executable

    if target_same:
        importlib.invalidate_caches()
        return is_cure_installed()

    check_code = (
        "import importlib; "
        "m = importlib.import_module('cochem_cure.provider'); "
        f"assert getattr(m, 'SCHEMA_VERSION', None) == {SCHEMA_VERSION!r}; "
        "print('OK')"
    )
    proc = subprocess.run(
        [python_executable, "-B", "-c", check_code],
        capture_output=True,
        text=True,
        check=False,
        timeout=min(timeout, 60.0),
    )
    return proc.returncode == 0 and "OK" in proc.stdout


def obtain_cure_repository(
    *,
    python_executable: str | None = None,
    local_repo_dir: Path | None = None,
    repo_url: str = CURE_REPO_URL,
    revision: str | None = None,
    timeout: float = 180.0,
) -> dict[str, Any]:
    """Ensure ``CoChem-CURE`` is installed and verifiable in the target Python environment.

    - If already installed in the target interpreter, returns immediately with
      ``{"status": "already_installed", "source": "installed"}`` without pip or network I/O.
    - Otherwise prefers a read-only ``git archive HEAD`` snapshot of a local checkout
      (``local_repo_dir``, ``$COCHEM_REPOS_DIR/CoChem-CURE``, or sibling ``../CoChem-CURE``)
      installed via ``pip install --no-deps --no-build-isolation`` (zero writes to source checkout).
    - If no local checkout exists, installs from ``git+{repo_url}`` (optionally ``@{revision}``)
      via ``pip install --no-input --no-deps``.
    - Always verifies ``cochem_cure.provider`` and ``SCHEMA_VERSION`` post-install,
      raising ``RuntimeError`` on any failure.
    """
    py = str(python_executable or sys.executable)

    if _verify_cure_in_interpreter(py, timeout=timeout):
        return {
            "status": "already_installed",
            "source": "installed",
            "repository": CURE_REPOSITORY,
            "schema_version": SCHEMA_VERSION,
        }

    local_checkout = _discover_local_cure_repo(local_repo_dir)
    if local_checkout is not None:
        with tempfile.TemporaryDirectory(prefix="cochem_cure_stage_") as tmp_dir:
            stage_dir = Path(tmp_dir) / "src_snapshot"
            source_kind = _stage_local_repo_readonly(
                local_checkout,
                stage_dir,
                revision=revision,
                timeout=timeout,
            )
            cmd = [
                py,
                "-m",
                "pip",
                "install",
                "--no-input",
                "--no-deps",
                "--no-build-isolation",
                str(stage_dir),
            ]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
            if proc.returncode != 0:
                detail = (proc.stderr or proc.stdout).strip()
                raise RuntimeError(
                    f"Failed to install CoChem-CURE from local snapshot {local_checkout} "
                    f"(exit {proc.returncode}): {detail}"
                )
        if not _verify_cure_in_interpreter(py, timeout=timeout):
            raise RuntimeError(
                "CoChem-CURE pip install completed from local snapshot, but "
                f"'cochem_cure.provider' failed SCHEMA_VERSION ({SCHEMA_VERSION!r}) verification."
            )
        return {
            "status": "installed",
            "source": source_kind,
            "local_repo_dir": str(local_checkout),
            "repository": CURE_REPOSITORY,
            "schema_version": SCHEMA_VERSION,
        }

    cleaned_url = str(repo_url or "").strip()
    if not cleaned_url or cleaned_url.startswith("-") or not cleaned_url.startswith(_ALLOWED_URL_PREFIXES):
        raise RuntimeError(f"Unsupported CoChem-CURE repository URL: {repo_url!r}")
    spec = cleaned_url if cleaned_url.startswith("git+") else f"git+{cleaned_url}"
    if revision is not None and str(revision).strip():
        cleaned_rev = str(revision).strip()
        if cleaned_rev.startswith("-") or any(ch.isspace() for ch in cleaned_rev):
            raise RuntimeError(f"Invalid CoChem-CURE revision: {revision!r}")
        spec = f"{spec}@{cleaned_rev}"

    cmd = [py, "-m", "pip", "install", "--no-input", "--no-deps", spec]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise RuntimeError(
            f"Failed to obtain CoChem-CURE from {spec} (exit {proc.returncode}): {detail}"
        )
    if not _verify_cure_in_interpreter(py, timeout=timeout):
        raise RuntimeError(
            "CoChem-CURE pip install completed from remote repository, but "
            f"'cochem_cure.provider' failed SCHEMA_VERSION ({SCHEMA_VERSION!r}) verification."
        )
    return {
        "status": "installed",
        "source": "remote_git",
        "repo_url": cleaned_url,
        "revision": revision,
        "repository": CURE_REPOSITORY,
        "schema_version": SCHEMA_VERSION,
    }


def list_cure_courses() -> list[dict[str, Any]]:
    """Return available course metadata dictionaries from installed ``CoChem-CURE``."""
    provider = _require_cure_provider()
    return list(provider.list_courses())


def get_cure_course_profile(course_id: str) -> dict[str, Any]:
    """Return the canonical course profile dictionary from installed ``CoChem-CURE``."""
    provider = _require_cure_provider()
    canonical = provider.validate_course_id(course_id)
    return dict(provider.get_course_profile(canonical))


def get_cure_course_pathway(course_id: str) -> dict[str, Any]:
    """Return the canonical course pathway dictionary from installed ``CoChem-CURE``."""
    provider = _require_cure_provider()
    canonical = provider.validate_course_id(course_id)
    return dict(provider.get_course_pathway(canonical))


def get_cure_milestones(course_id: str) -> list[dict[str, Any]]:
    """Return the canonical course milestones list from installed ``CoChem-CURE``."""
    provider = _require_cure_provider()
    canonical = provider.validate_course_id(course_id)
    return list(provider.get_course_milestones(canonical))


def get_allowed_course_ids() -> tuple[str, ...]:
    """Return allowed course IDs from ``CoChem-CURE`` when installed, else ``DEFAULT_FALLBACK_COURSE_IDS``."""
    provider = _import_cure_provider()
    if provider is None:
        return DEFAULT_FALLBACK_COURSE_IDS
    raw_ids = provider.get_allowed_course_ids()
    cleaned = tuple(str(cid).strip() for cid in raw_ids if str(cid).strip())
    return cleaned if cleaned else DEFAULT_FALLBACK_COURSE_IDS


def _format_pathway_text(pathway: Mapping[str, Any], milestones: Sequence[Mapping[str, Any]]) -> str:
    profile = pathway.get("profile") if isinstance(pathway.get("profile"), Mapping) else {}
    course_id = str(profile.get("course_id") or pathway.get("course_id") or "")
    title = str(profile.get("title") or pathway.get("title") or course_id)
    institution = str(profile.get("institution") or "")
    summary = str(profile.get("summary") or "")
    lines = [f"{course_id}: {title}".strip(": ")]
    if institution:
        lines.append(f"Institution: {institution}")
    if summary:
        lines.append(f"Summary: {summary}")
    if milestones:
        lines.append("Milestones:")
        for item in milestones:
            mid = item.get("id") or item.get("milestone_id") or item.get("code") or ""
            mtitle = item.get("title") or item.get("name") or str(item)
            lines.append(f"  - {mid}: {mtitle}".replace("- : ", "- "))
    guide = str(pathway.get("guide_markdown") or "").strip()
    if guide:
        lines.append("")
        lines.append(guide)
    return "\n".join(lines)


def _emit(payload: Mapping[str, Any], *, as_json: bool, text: str) -> None:
    if as_json:
        print(json.dumps(dict(payload), indent=2, sort_keys=True))
    else:
        print(text)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m cochem_base.course_loader",
        description="Configure standalone research vs. CoChem-CURE course mode and inspect course pathways.",
    )
    parser.add_argument(
        "--is-course",
        choices=("yes", "no"),
        default=None,
        help="Answer 'Is this a course?' non-interactively (yes or no).",
    )
    parser.add_argument(
        "--course",
        default=None,
        help="Course ID to select or inspect (requires CoChem-CURE).",
    )
    parser.add_argument(
        "--obtain",
        action="store_true",
        help="Obtain and verify ProfJJK-CoChem/CoChem-CURE if not already installed.",
    )
    parser.add_argument(
        "--list-courses",
        action="store_true",
        help="List available course profiles from CoChem-CURE.",
    )
    parser.add_argument(
        "--show-pathway",
        action="store_true",
        help="Display the full pathway and milestones for --course.",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Override artifact directory for StudentSetup/course-mode.json.",
    )
    parser.add_argument(
        "--local-repo-dir",
        type=Path,
        default=None,
        help="Optional local CoChem-CURE checkout to install read-only via git archive.",
    )
    parser.add_argument(
        "--revision",
        default=None,
        help="Optional git revision/branch/tag when obtaining CoChem-CURE.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit machine-readable JSON output.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    interactive = (
        args.is_course is None
        and args.course is None
        and not args.obtain
        and not args.list_courses
        and not args.show_pathway
    )

    try:
        if interactive:
            answer = input("Is this a course? [y/N]: ").strip().lower()
            is_course = answer in {"y", "yes"}
            if not is_course:
                state_path = save_course_mode_state(False, None, artifact_dir=args.artifact_dir)
                state = load_course_mode_state(artifact_dir=args.artifact_dir)
                result = {
                    "ok": True,
                    "state": state,
                    "state_path": str(state_path),
                    "cure_installed": is_cure_installed(),
                }
                _emit(
                    result,
                    as_json=args.as_json,
                    text=(
                        "Standalone research mode saved (CoChem-CURE not required). "
                        f"State: {state_path}"
                    ),
                )
                return 0

            obtain_result = obtain_cure_repository(
                local_repo_dir=args.local_repo_dir,
                revision=args.revision,
            )
            courses = list_cure_courses()
            selected: str | None = None
            if courses:
                if not args.as_json:
                    print("Available CoChem-CURE courses:")
                    for entry in courses:
                        print(f"  - {entry.get('course_id')}: {entry.get('title', '')}")
                if sys.stdin.isatty():
                    chosen = input("Select course ID (or press Enter to skip): ").strip()
                    if chosen:
                        selected = _require_cure_provider().validate_course_id(chosen)
            state_path = save_course_mode_state(True, selected, artifact_dir=args.artifact_dir)
            state = load_course_mode_state(artifact_dir=args.artifact_dir)
            result = {
                "ok": True,
                "state": state,
                "state_path": str(state_path),
                "obtain": obtain_result,
                "courses": courses,
                "cure_installed": True,
            }
            _emit(
                result,
                as_json=args.as_json,
                text=f"Course mode saved ({selected or 'no course selected yet'}). State: {state_path}",
            )
            return 0

        result: dict[str, Any] = {"ok": True}
        text_lines: list[str] = []

        if args.is_course == "no":
            state_path = save_course_mode_state(False, None, artifact_dir=args.artifact_dir)
            result["state"] = load_course_mode_state(artifact_dir=args.artifact_dir)
            result["state_path"] = str(state_path)
            result["cure_installed"] = is_cure_installed()
            text_lines.append(
                f"Standalone research mode saved (CoChem-CURE not required). State: {state_path}"
            )
            _emit(result, as_json=args.as_json, text="\n".join(text_lines))
            return 0

        if args.obtain:
            obtain_info = obtain_cure_repository(
                local_repo_dir=args.local_repo_dir,
                revision=args.revision,
            )
            result["obtain"] = obtain_info
            text_lines.append(f"CoChem-CURE: {obtain_info['status']} ({obtain_info['source']})")

        selected_course_id: str | None = None
        if args.course is not None:
            provider = _require_cure_provider()
            selected_course_id = provider.validate_course_id(args.course)
            result["selected_course_id"] = selected_course_id

        if args.is_course == "yes" or selected_course_id is not None:
            state_path = save_course_mode_state(
                True,
                selected_course_id,
                artifact_dir=args.artifact_dir,
            )
            result["state"] = load_course_mode_state(artifact_dir=args.artifact_dir)
            result["state_path"] = str(state_path)
            text_lines.append(
                f"Course mode saved (course={selected_course_id or 'unselected'}). State: {state_path}"
            )

        if args.list_courses:
            courses = list_cure_courses()
            result["courses"] = courses
            text_lines.append("Available CoChem-CURE courses:")
            for entry in courses:
                text_lines.append(f"  - {entry.get('course_id')}: {entry.get('title', '')}")

        if args.show_pathway:
            target_course = selected_course_id
            if target_course is None:
                persisted = load_course_mode_state(artifact_dir=args.artifact_dir)
                target_course = persisted.get("selected_course_id")
            if not target_course:
                raise RuntimeError("Specify --course <id> to display a course pathway.")
            pathway = get_cure_course_pathway(target_course)
            milestones = get_cure_milestones(target_course)
            result["pathway"] = pathway
            result["milestones"] = milestones
            text_lines.append(_format_pathway_text(pathway, milestones))

        result["cure_installed"] = is_cure_installed()
        _emit(result, as_json=args.as_json, text="\n".join(text_lines) or "OK")
        return 0
    except (RuntimeError, ValueError, KeyError, OSError) as exc:
        if args.as_json:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
