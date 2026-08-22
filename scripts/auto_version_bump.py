#!/usr/bin/env python3
"""Auto Version Bump Hook & CLI: Deterministic Semantic Versioning for CoChem.

This script manages deterministic Semantic Version (SemVer 2.0.0) iterations
across the CoChem ecosystem. It operates both as an automated Git hook
(e.g., pre-push or post-merge) and as a standalone CLI tool to prevent pipeline
and dependency drift.

Enforcement Rules:
1. Zero-Mock, Real Implementation: Physical Git inspect and file mutation.
2. SemVer 2.0.0 Compliance: Strictly validates and increments (major.minor.patch).
3. Conventional Commits Analysis:
   - BREAKING CHANGE or '!': Major bump (X.0.0)
   - feat / feature: Minor bump (0.X.0)
   - fix / chore / docs / refactor / perf / test: Patch bump (0.0.X)
4. Central Version Synchronization:
   - Updates pyproject.toml (`version = "..."`)
   - Updates package __init__.py (`__version__ = "..."`)
   - Preserves formatting, comments, and structure.
5. Strict Unix LF line endings and UTF-8 encoding.
"""

from __future__ import annotations

import argparse
import dataclasses
import enum
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

logger = logging.getLogger("auto_version_bump")

# Regular expression adhering strictly to SemVer 2.0.0 specification
SEMVER_REGEX = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z.-]+))?"
    r"(?:\+(?P<build>[0-9A-Za-z.-]+))?$"
)

# Regex patterns for finding/replacing version declarations
PYPROJECT_VERSION_REGEX = re.compile(r'(?m)^(\s*version\s*=\s*["\'])([^"\']+)(["\'])')
INIT_VERSION_REGEX = re.compile(r'(?m)^(\s*__version__\s*=\s*["\'])([^"\']+)(["\'])')


class BumpType(str, enum.Enum):
    """Semantic version bump categories."""

    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"
    AUTO = "auto"


@dataclasses.dataclass(frozen=True)
class SemVer:
    """Immutable representation of a Semantic Version (SemVer 2.0.0)."""

    major: int
    minor: int
    patch: int
    prerelease: Optional[str] = None
    build: Optional[str] = None

    def __str__(self) -> str:
        """Render standard Semantic Version string."""
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            base = f"{base}-{self.prerelease}"
        if self.build:
            base = f"{base}+{self.build}"
        return base

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return (self.major, self.minor, self.patch, self.prerelease) == (
            other.major,
            other.minor,
            other.patch,
            other.prerelease,
        )

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        # Primary comparison by major.minor.patch
        if (self.major, self.minor, self.patch) != (other.major, other.minor, other.patch):
            return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)
        # Normal version has higher precedence than pre-release version
        if self.prerelease is None and other.prerelease is not None:
            return False
        if self.prerelease is not None and other.prerelease is None:
            return True
        if self.prerelease is not None and other.prerelease is not None:
            # SemVer 2.0.0 §11.4: Compare dot-separated identifiers
            self_parts = self.prerelease.split(".")
            other_parts = other.prerelease.split(".")
            for sp, op in zip(self_parts, other_parts, strict=False):
                if sp == op:
                    continue
                sp_is_num = sp.isdigit()
                op_is_num = op.isdigit()
                if sp_is_num and op_is_num:
                    return int(sp) < int(op)
                elif sp_is_num and not op_is_num:
                    return True
                elif not sp_is_num and op_is_num:
                    return False
                else:
                    return sp < op
            return len(self_parts) < len(other_parts)
        return False

    def __le__(self, other: object) -> bool:
        return self < other or self == other

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return not (self <= other)

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return not (self < other)

    def bump(self, bump_type: BumpType) -> SemVer:
        """Compute the next SemVer instance based on the bump type."""
        if bump_type == BumpType.MAJOR:
            return SemVer(major=self.major + 1, minor=0, patch=0)
        elif bump_type == BumpType.MINOR:
            return SemVer(major=self.major, minor=self.minor + 1, patch=0)
        elif bump_type == BumpType.PATCH:
            return SemVer(major=self.major, minor=self.minor, patch=self.patch + 1)
        else:
            raise ValueError(f"Unsupported bump type: {bump_type}")


@dataclasses.dataclass
class VersionBumpResult:
    """Summary of a version bump execution."""

    old_version: str
    new_version: str
    bump_type: BumpType
    updated_files: List[Path]
    is_dry_run: bool


def parse_semver(version_str: str) -> SemVer:
    """Parse a semantic version string into a SemVer object.

    Args:
        version_str: The version string (e.g., '0.1.0', '1.2.3-rc.1').

    Returns:
        SemVer object.

    Raises:
        ValueError: If the string does not strictly match SemVer 2.0.0.
    """
    clean_str = version_str.strip().lstrip("v")
    match = SEMVER_REGEX.match(clean_str)
    if not match:
        raise ValueError(
            f"Invalid Semantic Version string: '{version_str}'. Must follow SemVer 2.0.0 format (e.g. 0.1.0)."
        )

    return SemVer(
        major=int(match.group("major")),
        minor=int(match.group("minor")),
        patch=int(match.group("patch")),
        prerelease=match.group("prerelease"),
        build=match.group("build"),
    )


def bump_version_string(current_version: str, bump_type_str: str | BumpType) -> str:
    """Helper to parse a version string, apply bump, and return new version string.

    Args:
        current_version: Current version string (e.g. '0.1.0').
        bump_type_str: Bump category ('major', 'minor', 'patch').

    Returns:
        Updated version string.
    """
    v = parse_semver(current_version)
    b_type = BumpType(bump_type_str.lower())
    new_v = v.bump(b_type)
    return str(new_v)


def analyze_commits_for_bump(commits: Sequence[str]) -> BumpType:
    """Analyze commit messages according to Conventional Commits specification.

    Rules:
    - Breaking changes (BREAKING CHANGE or 'type!:') -> BumpType.MAJOR
    - Features ('feat:' or 'feature:') -> BumpType.MINOR
    - Fixes, chores, docs, refactors, etc. -> BumpType.PATCH

    Args:
        commits: List of commit message bodies/subjects.

    Returns:
        Calculated BumpType (MAJOR, MINOR, or PATCH).
    """
    if not commits:
        return BumpType.PATCH

    has_breaking = False
    has_feature = False

    breaking_pattern = re.compile(
        r"(?:BREAKING CHANGE|BREAKING-CHANGE|\b\w+(\([^\)]+\))?!:)",
        re.IGNORECASE,
    )
    feature_pattern = re.compile(
        r"^(?:feat|feature)(?:\([^\)]+\))?:",
        re.IGNORECASE | re.MULTILINE,
    )

    for msg in commits:
        if breaking_pattern.search(msg):
            has_breaking = True
            break
        if feature_pattern.search(msg):
            has_feature = True

    if has_breaking:
        return BumpType.MAJOR
    elif has_feature:
        return BumpType.MINOR
    else:
        return BumpType.PATCH


def read_version_from_file(file_path: Path) -> Optional[str]:
    """Extract version string from a pyproject.toml or python source file.

    Args:
        file_path: Path to the version-bearing file.

    Returns:
        Extracted version string, or None if not found.
    """
    if not file_path.exists():
        return None

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.warning("Failed to read %s: %s", file_path, exc)
        return None

    if file_path.name == "pyproject.toml":
        match = PYPROJECT_VERSION_REGEX.search(content)
        if match:
            return match.group(2)
    elif file_path.suffix == ".py":
        match = INIT_VERSION_REGEX.search(content)
        if match:
            return match.group(2)

    return None


def update_file_version(file_path: Path, new_version: str) -> bool:
    """Update version declaration in pyproject.toml or python source file.

    Preserves line endings as Unix LF and ensures UTF-8 encoding.

    Args:
        file_path: Path to the target file.
        new_version: The new version string to write.

    Returns:
        True if version was found and updated, False otherwise.
    """
    if not file_path.exists():
        return False

    content = file_path.read_text(encoding="utf-8")
    updated = False

    if file_path.name == "pyproject.toml":
        if PYPROJECT_VERSION_REGEX.search(content):
            content = PYPROJECT_VERSION_REGEX.sub(
                r"\g<1>" + new_version + r"\g<3>", content, count=1
            )
            updated = True
    elif file_path.suffix == ".py":
        if INIT_VERSION_REGEX.search(content):
            content = INIT_VERSION_REGEX.sub(r"\g<1>" + new_version + r"\g<3>", content, count=1)
            updated = True

    if updated:
        # Enforce LF line endings
        content_lf = content.replace("\r\n", "\n")
        file_path.write_bytes(content_lf.encode("utf-8"))

    return updated


def find_version_files(repo_root: Path) -> List[Path]:
    """Find all candidate central version files in the repository.

    Discovers pyproject.toml at root and __init__.py files in top-level packages.

    Args:
        repo_root: Repository root directory.

    Returns:
        List of existing paths containing version definitions.
    """
    found: List[Path] = []
    root = repo_root.resolve()

    pyproject = root / "pyproject.toml"
    if pyproject.exists() and read_version_from_file(pyproject) is not None:
        found.append(pyproject)

    # Search for top-level python packages with __init__.py
    for child in root.iterdir():
        if (
            child.is_dir()
            and not child.name.startswith((".", "__"))
            and child.name not in ("build", "dist", "tests", "test_suite", "scripts")
        ):
            init_file = child / "__init__.py"
            if init_file.exists() and read_version_from_file(init_file) is not None:
                found.append(init_file)

    return found


def get_git_commits(
    repo_root: Path,
    since_ref: Optional[str] = None,
    max_count: int = 50,
) -> List[str]:
    """Retrieve recent commit messages from the physical git repository.

    Args:
        repo_root: Root of the git repository.
        since_ref: Optional baseline ref (e.g. tag or commit hash).
        max_count: Maximum number of commits to retrieve.

    Returns:
        List of commit message strings.
    """
    if not (repo_root / ".git").exists():
        return []

    cmd = ["git", "-C", str(repo_root), "log", f"-n{max_count}", "--pretty=format:%B%x1e"]
    if since_ref:
        cmd.insert(4, f"{since_ref}..HEAD")

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=30,
        )
        raw_output = proc.stdout.decode("utf-8", errors="replace")
        commits = [c.strip() for c in raw_output.split("\x1e") if c.strip()]
        return commits
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return []


def is_main_branch(
    repo_root: Path,
    target_branches: Sequence[str] = ("main", "master"),
) -> bool:
    """Check if the current repository branch matches target stable branches.

    Args:
        repo_root: Git repository root.
        target_branches: Tuple of branch names considered production/main.

    Returns:
        True if current branch is in target_branches, False otherwise.
    """
    if not (repo_root / ".git").exists():
        return True

    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=15,
        )
        current_branch = proc.stdout.decode("utf-8").strip()
        return current_branch in target_branches
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return False


def determine_next_version(
    repo_root: Path,
    bump_override: str = "auto",
    since_ref: Optional[str] = None,
) -> Tuple[str, BumpType]:
    """Determine the next Semantic Version for the repository.

    Args:
        repo_root: Repository root path.
        bump_override: Bump directive ('auto', 'patch', 'minor', 'major').
        since_ref: Git reference point to analyze commits from.

    Returns:
        Tuple of (new_version_string, bump_type_used).
    """
    version_files = find_version_files(repo_root)
    current_version = None
    for vf in version_files:
        ver = read_version_from_file(vf)
        if ver:
            current_version = ver
            break

    if not current_version:
        current_version = "0.1.0"

    v = parse_semver(current_version)

    if bump_override.lower() in ("major", "minor", "patch"):
        bump_type = BumpType(bump_override.lower())
    else:
        # Auto bump based on commit analysis
        commits = get_git_commits(repo_root, since_ref=since_ref)
        bump_type = analyze_commits_for_bump(commits)

    next_v = v.bump(bump_type)
    return str(next_v), bump_type


def update_repository_version(
    repo_root: Path,
    new_version: Optional[str] = None,
    bump_type: str = "auto",
    dry_run: bool = False,
    target_files: Optional[Sequence[Path]] = None,
) -> VersionBumpResult:
    """Execute version bumping across all repository version files.

    Args:
        repo_root: Path to repository root.
        new_version: Explicit new version, or None to calculate automatically.
        bump_type: Bump calculation type if new_version is None.
        dry_run: If True, simulate changes without writing to disk.
        target_files: Optional explicit list of files to update.

    Returns:
        VersionBumpResult summary.
    """
    root = repo_root.resolve()
    files = list(target_files) if target_files else find_version_files(root)

    # Read current version
    current_version = None
    for f in files:
        ver = read_version_from_file(f)
        if ver:
            current_version = ver
            break

    if not current_version:
        current_version = "0.1.0"

    if new_version is not None:
        target_ver_str = str(parse_semver(new_version))
        applied_bump = BumpType.AUTO
    else:
        target_ver_str, applied_bump = determine_next_version(root, bump_override=bump_type)

    updated_paths: List[Path] = []

    if not dry_run:
        for f in files:
            if update_file_version(f, target_ver_str):
                updated_paths.append(f)
    else:
        updated_paths = list(files)

    return VersionBumpResult(
        old_version=current_version,
        new_version=target_ver_str,
        bump_type=applied_bump,
        updated_files=updated_paths,
        is_dry_run=dry_run,
    )


def get_git_hooks_dir(repo_root: Path) -> Path:
    """Resolve the git hooks directory for standard repositories, worktrees, and submodules.

    Args:
        repo_root: Path to repository root.

    Returns:
        Path to hooks directory.
    """
    git_entry = repo_root / ".git"
    if not git_entry.exists():
        raise RuntimeError(f"Not a git repository: {repo_root}")

    if git_entry.is_file():
        # Handle worktree / submodule git pointer file
        try:
            content = git_entry.read_text(encoding="utf-8").strip()
            if content.startswith("gitdir:"):
                target_dir = Path(content.split("gitdir:", 1)[1].strip())
                if not target_dir.is_absolute():
                    target_dir = (repo_root / target_dir).resolve()
                return target_dir / "hooks"
        except Exception as exc:
            logger.debug("Failed reading .git pointer file: %s", exc)

    return git_entry / "hooks"


def install_git_hook(repo_root: Path, hook_name: str = "pre-push") -> Path:
    """Install auto_version_bump hook into git hooks directory.

    Args:
        repo_root: Repository root path.
        hook_name: Hook trigger name (e.g. 'pre-push', 'post-merge').

    Returns:
        Path to the installed hook script.
    """
    hooks_dir = get_git_hooks_dir(repo_root)
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hooks_dir / hook_name

    hook_script_content = f"""#!/usr/bin/env bash
# CoChem Auto Version Bumping Hook: {hook_name}
# Automatically increments version and keeps downstream environments synchronized.

python scripts/auto_version_bump.py --hook-mode {hook_name}
exit $?
"""
    # Enforce LF endings
    hook_script_content_lf = hook_script_content.replace("\r\n", "\n")
    hook_path.write_bytes(hook_script_content_lf.encode("utf-8"))

    # Make executable on POSIX systems
    try:
        current_stat = hook_path.stat().st_mode
        hook_path.chmod(current_stat | 0o755)
    except Exception:
        pass

    return hook_path


def handle_pre_push_hook(
    repo_root: Path,
    dry_run: bool = False,
    stdin_input: Optional[str] = None,
) -> int:
    """Handle Git pre-push hook invocation.

    Inspects standard input for push destination refs and triggers version bump
    when pushing to main/master branches.

    Args:
        repo_root: Repository root.
        dry_run: Dry run flag.
        stdin_input: Optional simulated or explicit stdin content.

    Returns:
        Exit code (0 on success).
    """
    is_main = is_main_branch(repo_root)

    # Check stdin lines if available
    # Git pre-push stdin format: <local ref> <local sha> <remote ref> <remote sha>
    raw_input = stdin_input
    if raw_input is None and not sys.stdin.isatty():
        try:
            raw_input = sys.stdin.read().strip()
        except Exception:
            raw_input = None

    if raw_input:
        for line in raw_input.splitlines():
            parts = line.split()
            if len(parts) >= 3:
                remote_ref = parts[2]
                if "refs/heads/main" in remote_ref or "refs/heads/master" in remote_ref:
                    is_main = True

    if not is_main:
        print("[AUTO-VERSION-BUMP] Not pushing to main branch; skipping version increment.")
        return 0

    print("[AUTO-VERSION-BUMP] Push to main branch detected. Performing version bump...")
    result = update_repository_version(repo_root=repo_root, bump_type="auto", dry_run=dry_run)
    print(f"[AUTO-VERSION-BUMP] Version incremented: {result.old_version} -> {result.new_version}")
    return 0


def handle_post_merge_hook(repo_root: Path, dry_run: bool = False) -> int:
    """Handle Git post-merge hook invocation.

    Triggers version bump after merge into main branch.

    Args:
        repo_root: Repository root.
        dry_run: Dry run flag.

    Returns:
        Exit code (0 on success).
    """
    if not is_main_branch(repo_root):
        print("[AUTO-VERSION-BUMP] Not on main branch; skipping post-merge version increment.")
        return 0

    print("[AUTO-VERSION-BUMP] Merge to main branch detected. Performing version bump...")
    result = update_repository_version(repo_root=repo_root, bump_type="auto", dry_run=dry_run)
    print(f"[AUTO-VERSION-BUMP] Version incremented: {result.old_version} -> {result.new_version}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="auto_version_bump",
        description="Deterministic Semantic Version Auto-Bumping Hook for CoChem repositories.",
    )
    parser.add_argument(
        "--repo-root",
        "-r",
        dest="repo_root",
        type=str,
        default=".",
        help="Path to repository root (default: current working directory).",
    )
    parser.add_argument(
        "--bump",
        "-b",
        dest="bump",
        choices=["auto", "patch", "minor", "major"],
        default="auto",
        help="Semantic version bump type (default: auto via commit analysis).",
    )
    parser.add_argument(
        "--set-version",
        "-s",
        dest="set_version",
        type=str,
        default=None,
        help="Set an explicit Semantic Version string directly.",
    )
    parser.add_argument(
        "--dry-run",
        "-d",
        dest="dry_run",
        action="store_true",
        default=False,
        help="Simulate version bump without modifying files on disk.",
    )
    parser.add_argument(
        "--hook-mode",
        dest="hook_mode",
        choices=["pre-push", "post-merge", "generic"],
        default=None,
        help="Execute in Git hook mode (e.g., pre-push or post-merge).",
    )
    parser.add_argument(
        "--install-hook",
        dest="install_hook",
        choices=["pre-push", "post-merge"],
        default=None,
        help="Install auto_version_bump as a Git hook in .git/hooks/.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        dest="verbose",
        action="store_true",
        default=False,
        help="Enable detailed diagnostic logging.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Main CLI entry point.

    Args:
        argv: Optional sequence of CLI argument strings.

    Returns:
        0 on success, 1 on error.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")
    else:
        logging.basicConfig(level=logging.INFO, format="%(message)s")

    root = Path(args.repo_root).resolve()

    if args.install_hook:
        try:
            hook_path = install_git_hook(root, hook_name=args.install_hook)
            print(
                f"[AUTO-VERSION-BUMP] Successfully installed {args.install_hook} hook to {hook_path}"
            )
            return 0
        except Exception as exc:
            print(f"[AUTO-VERSION-BUMP ERROR] Hook installation failed: {exc}", file=sys.stderr)
            return 1

    if args.hook_mode == "pre-push":
        return handle_pre_push_hook(root, dry_run=args.dry_run)
    elif args.hook_mode == "post-merge":
        return handle_post_merge_hook(root, dry_run=args.dry_run)

    # Standard / CLI execution
    try:
        res = update_repository_version(
            repo_root=root,
            new_version=args.set_version,
            bump_type=args.bump,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"[AUTO-VERSION-BUMP ERROR] Version bump failed: {exc}", file=sys.stderr)
        return 1

    mode_tag = " [DRY RUN]" if res.is_dry_run else ""
    print(
        f"[AUTO-VERSION-BUMP]{mode_tag} Version updated: {res.old_version} -> {res.new_version} ({res.bump_type})"
    )
    for f in res.updated_files:
        try:
            rel = f.relative_to(root)
        except ValueError:
            rel = f
        print(f"  - Synchronized: {rel}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
