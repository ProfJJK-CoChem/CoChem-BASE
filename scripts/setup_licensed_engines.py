#!/usr/bin/env python3
"""Provision approved engines for an authorized student's private GitHub project.

The normal Codespaces GitHub authorization downloads private release assets;
credentials are never passed to installers or native engines. Installation and
non-secret environment bindings live outside the checkout. This verifies the
approved distributions and their runtime probes, not scientific accuracy.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

try:
    from . import install_openmpi, provision_cfour, provision_orca
except ImportError:
    import install_openmpi
    import provision_cfour
    import provision_orca

REPO_ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT_NAME = "codespaces-environment.json"
ENVIRONMENT_KEYS = frozenset({
    "COCHEM_ORCA_BIN", "ORCA_CMD", "ORCA_PATH", "COCHEM_MPIRUN_BIN",
    "COCHEM_MPIEXEC_BIN", "COCHEM_ORCA_MPIRUN_BIN", "COCHEM_ORCA_LD_LIBRARY_PATH",
    "COCHEM_ORCA_PROVENANCE", "COCHEM_CFOUR_AVAILABLE", "COCHEM_CFOUR_BIN",
    "COCHEM_XCFOUR_BIN", "CFOUR_CMD", "CFOUR_EXE", "CFOUR_HOME", "CFOUR_ROOT",
    "CFOUR_BIN", "COCHEM_CFOUR_GENBAS", "CFOUR_GENBAS", "COCHEM_CFOUR_ECPDATA",
    "CFOUR_ECPDATA", "COCHEM_CFOUR_LD_LIBRARY_PATH", "COCHEM_CFOUR_PROVENANCE",
    "COCHEM_CFOUR_MPI_AVAILABLE", "COCHEM_CFOUR_OPENMP_AVAILABLE",
})
BOOLEAN_VALUES = {"COCHEM_CFOUR_AVAILABLE": "true", "COCHEM_CFOUR_MPI_AVAILABLE": "false",
                  "COCHEM_CFOUR_OPENMP_AVAILABLE": "true"}


def external_artifact_root(path: Path) -> Path:
    root = path.expanduser().resolve()
    if root == Path(root.anchor) or root.is_relative_to(REPO_ROOT):
        raise ValueError("Engine artifacts must be outside the source checkout and filesystem root.")
    runtime = root / "licensed-engines"
    if runtime.is_symlink() or not runtime.resolve().is_relative_to(root):
        raise ValueError("The external licensed engine directory must not be a symlink.")
    return root


def github_repository(remote: str) -> str:
    """Resolve a GitHub origin without exposing possible URL credentials."""
    if remote.startswith("git@github.com:"):
        repository = remote.removeprefix("git@github.com:")
    else:
        parsed = urlparse(remote)
        if parsed.scheme not in {"https", "ssh"} or parsed.hostname != "github.com":
            raise ValueError("The project origin must identify a github.com repository.")
        repository = parsed.path.lstrip("/")
    repository = repository.removesuffix(".git")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9._-]*", repository):
        raise ValueError("The project origin must identify OWNER/REPOSITORY.")
    return repository


def github_call(arguments: list[str], *, repository_root: Path = REPO_ROOT) -> str:
    """Keep authentication solely in gh and never emit its credential-bearing errors."""
    result = subprocess.run(["gh", *arguments], cwd=repository_root, stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, check=False, timeout=900)
    if result.returncode:
        raise ValueError("GitHub access failed. Check the Codespaces repository permissions and your lab access.")
    return result.stdout


def require_private_repository(repository: str) -> None:
    metadata = json.loads(github_call(["api", f"repos/{repository}"]))
    if (not isinstance(metadata, dict) or metadata.get("full_name", "").lower() != repository.lower()
            or metadata.get("private") is not True):
        raise ValueError("Licensed engines require a private project and private distribution repositories.")


def require_private_project() -> str:
    origin = subprocess.run(["git", "remote", "get-url", "origin"], cwd=REPO_ROOT,
                            stdin=subprocess.DEVNULL, capture_output=True, text=True,
                            check=False, timeout=15)
    if origin.returncode:
        raise ValueError("Cannot resolve this project's GitHub origin.")
    repository = github_repository(origin.stdout.strip())
    require_private_repository(repository)
    return repository


def installer_environment() -> dict[str, str]:
    """Allow only OS/toolchain inputs; no GitHub or other credentials reach children."""
    allowed = {"PATH", "HOME", "TMPDIR", "TMP", "TEMP", "LANG", "LC_ALL",
               "SSL_CERT_FILE", "SSL_CERT_DIR", "CURL_CA_BUNDLE", "REQUESTS_CA_BUNDLE"}
    result = {key: value for key, value in os.environ.items() if key in allowed}
    result.setdefault("PATH", "/usr/local/bin:/usr/bin:/bin")
    result["LANG"] = result["LC_ALL"] = "C"
    return result


def checked_installer(arguments: list[str]) -> None:
    subprocess.run([sys.executable, *arguments], cwd=REPO_ROOT, env=installer_environment(),
                   stdin=subprocess.DEVNULL, check=True)


def validate_environment(payload: dict, artifact_root: Path) -> tuple[dict[str, str], list[str]]:
    """Parse data, never shell code; prevent additional secrets or checkout paths."""
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("Invalid licensed environment schema.")
    values, paths = payload.get("values"), payload.get("path_entries")
    if not isinstance(values, dict) or not set(values).issubset(ENVIRONMENT_KEYS):
        raise ValueError("Licensed environment contains an unsupported variable.")
    if (not isinstance(paths, list) or any(not isinstance(path, str) for path in paths)
            or len(paths) != len(set(paths))):
        raise ValueError("Invalid licensed executable path entries.")
    runtime_root = external_artifact_root(artifact_root) / "licensed-engines"
    for key, value in values.items():
        if not isinstance(value, str) or not value or any(char in value for char in "\r\n\x00"):
            raise ValueError("Licensed environment values must be nonempty single-line strings.")
        if key in BOOLEAN_VALUES:
            if value != BOOLEAN_VALUES[key]:
                raise ValueError("Invalid licensed engine capability flag.")
            continue
        for part in value.split(os.pathsep) if key.endswith("LD_LIBRARY_PATH") else [value]:
            path = Path(part)
            if not path.is_absolute() or not path.resolve().is_relative_to(runtime_root.resolve()):
                raise ValueError("Licensed runtime bindings must remain inside external engine artifacts.")
    for entry in paths:
        if (not isinstance(entry, str) or any(char in entry for char in "\r\n\x00")
                or not Path(entry).is_absolute()
                or not Path(entry).resolve().is_relative_to(runtime_root.resolve())
                or Path(entry).name == "bin" and any(part.startswith("openmpi") for part in Path(entry).parts)):
            raise ValueError("Invalid licensed executable directory.")
    return values, paths


def load_environment(artifact_root: Path) -> tuple[dict[str, str], list[str]]:
    path = external_artifact_root(artifact_root) / "licensed-engines" / ENVIRONMENT_NAME
    if not path.exists() and not path.is_symlink():
        return {}, []
    if path.is_symlink() or not path.is_file():
        raise ValueError("Licensed environment must be a regular data file.")
    return validate_environment(json.loads(path.read_text(encoding="utf-8")), artifact_root)


def save_environment(root: Path, payload: dict) -> None:
    values, paths = validate_environment(payload, root)
    destination = root / "licensed-engines"
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    # No eval/source is used by the dashboard. This optional terminal helper
    # contains only the same allowlisted paths, quoted as literal shell words.
    shell = "".join(f"export {key}={shlex.quote(value)}\n" for key, value in sorted(values.items()))
    if paths:
        shell += f"export PATH={shlex.quote(os.pathsep.join(paths))}:\"${{PATH:-}}\"\n"
    for name, contents in ((ENVIRONMENT_NAME, json.dumps(payload, indent=2, sort_keys=True) + "\n"),
                           ("codespaces-environment.sh", shell)):
        descriptor, temporary = tempfile.mkstemp(prefix=f".{name}.", dir=destination)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(contents)
            Path(temporary).replace(destination / name)
        finally:
            Path(temporary).unlink(missing_ok=True)


def verify_file_inventory(prefix: Path, records: dict, excluded: str) -> None:
    if not isinstance(records, dict) or not records:
        raise ValueError("Installed runtime lacks its complete file inventory; choose a fresh artifact root.")
    actual = {str(path.relative_to(prefix)) for path in prefix.rglob("*")
              if path.is_file() or path.is_symlink()} - {excluded}
    if actual != set(records):
        raise ValueError("Installed runtime file inventory changed; choose a fresh artifact root.")
    for name, record in records.items():
        path = prefix / name
        if (not path.resolve().is_relative_to(prefix.resolve()) or not isinstance(record, dict)
                or Path(name).is_absolute() or ".." in Path(name).parts):
            raise ValueError("Unsafe installed runtime inventory.")
        if "symlink" in record:
            if not path.is_symlink() or os.readlink(path) != record["symlink"]:
                raise ValueError("Installed runtime link changed.")
        elif (path.is_symlink() or not path.is_file() or path.stat().st_size != record.get("bytes")
              or provision_orca.sha256_file(path) != record.get("sha256")):
            raise ValueError("Installed runtime bytes changed; choose a fresh artifact root.")


def verify_existing(engine: str, prefix: Path, manifest: dict) -> None:
    if engine == "cfour":
        provision_cfour.verify_runtime(prefix)
        return
    provenance = prefix / "cochem-orca-provenance.json"
    if provenance.is_symlink() or not provenance.is_file():
        raise ValueError("Existing ORCA has no verified provisioning receipt; choose a fresh artifact root.")
    report = json.loads(provenance.read_text())
    if report.get("distribution") != manifest or report.get("archive_sha256") != manifest["sha256"]:
        raise ValueError("Existing ORCA distribution identity differs from the approved manifest.")
    verify_file_inventory(prefix, report.get("files"), provenance.name)
    mpi_prefix = prefix.parent / "openmpi-4.1.8"
    mpi_receipt = mpi_prefix / "cochem-openmpi-provenance.json"
    if mpi_receipt.is_symlink() or not mpi_receipt.is_file():
        raise ValueError("Existing Open MPI has no verified runtime inventory.")
    mpi = json.loads(mpi_receipt.read_text())
    if mpi.get("version") != "4.1.8" or mpi.get("source_sha256") != install_openmpi.SOURCE_SHA256:
        raise ValueError("Existing Open MPI identity differs from the approved build.")
    verify_file_inventory(mpi_prefix, mpi.get("files"), mpi_receipt.name)


def provision_selected(engines: list[str], root: Path, jobs: int) -> dict:
    """Reject public origins before any archive fetch and reuse only verified bytes."""
    root = external_artifact_root(root)
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise ValueError("Approved engine distributions require Linux x86_64 (including WSL2).")
    project = require_private_project()
    manifests = {"orca": provision_orca.load_distribution_manifest(),
                 "cfour": provision_cfour.load_distribution_manifest()}
    runtime = root / "licensed-engines"
    state_path = runtime / ENVIRONMENT_NAME
    values, paths = load_environment(root)
    state = json.loads(state_path.read_text()) if state_path.is_file() else {}
    providers = state.get("providers", {})
    if not isinstance(providers, dict):
        raise ValueError("Invalid installed provider state.")
    # Preflight every selected destination before doing any downloads.
    for engine in engines:
        prefix = runtime / engine
        require_private_repository(manifests[engine]["repository"])
        if prefix.exists() or prefix.is_symlink():
            if engine not in providers or prefix.is_symlink():
                raise ValueError("An unrecorded engine directory already exists; choose a fresh artifact root.")
            verify_existing(engine, prefix, manifests[engine])
        elif engine == "orca" and (runtime / "openmpi-4.1.8").exists():
            raise ValueError("Open MPI already exists without ORCA; choose a fresh artifact root.")
    runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix=".private-download-", dir=runtime) as temporary:
        staging = Path(temporary)
        env_file, path_file = staging / "env", staging / "path"
        env_file.touch()
        path_file.touch()
        for engine in engines:
            prefix = runtime / engine
            if prefix.exists():
                continue
            manifest = manifests[engine]
            github_call(["release", "download", manifest["release_tag"], "--repo", manifest["repository"],
                         "--pattern", manifest["archive_name"], "--dir", str(staging)])
            archive = staging / manifest["archive_name"]
            provision_orca.verified_digest(archive, manifest["sha256"])
            arguments = [str(REPO_ROOT / "scripts" / f"provision_{engine}.py"),
                         "--archive", str(archive), "--install-root", str(prefix),
                         "--github-env", str(env_file), "--github-path", str(path_file)]
            if engine == "orca":
                mpi = runtime / "openmpi-4.1.8"
                build_root = runtime / "openmpi-build"
                build_root.mkdir(parents=True, exist_ok=True, mode=0o700)
                # The controller downloads public source with the configured
                # proxy/CA. The subsequent credential-free compiler and MPI
                # processes reuse the cache only after the installer's own
                # independently pinned checksum verification.
                install_openmpi.download_source(build_root)
                checked_installer([str(REPO_ROOT / "scripts/install_openmpi.py"), "--prefix", str(mpi),
                                   "--build-root", str(build_root), "--jobs", str(jobs)])
                arguments += ["--mpi-prefix", str(mpi)]
            checked_installer(arguments)
            providers[engine] = {"prefix": str(prefix), "distribution_sha256": manifest["sha256"]}
            # Publish successful per-engine bindings immediately. A subsequent
            # provider failure leaves a reusable honest partial installation.
            updates = dict(line.split("=", 1) for line in env_file.read_text().splitlines())
            values.update(updates)
            paths = list(dict.fromkeys([*paths, *path_file.read_text().splitlines()]))
            state = {"schema_version": 1, "project": project, "providers": providers,
                     "values": values, "path_entries": paths,
                     "scope": "Pinned private distributions and runtime discovery; no calculation accuracy claim"}
            save_environment(root, state)
    return {"engines": engines, "project": project, "artifacts": str(root),
            "environment": str(state_path), "scope": "Provisioning only; Stage 0 authorizes calculations"}


def refresh_stage0(root: Path) -> bool:
    python = root / "ui-env/bin/python"
    if not python.is_file():
        return False
    try:
        from .hosted_dashboard import runtime_environment
    except ImportError:
        from hosted_dashboard import runtime_environment
    runtime = runtime_environment(root)
    selected = ENVIRONMENT_KEYS | {"COCHEM_ARTIFACT_DIR", "COCHEM_CONFIG", "COCHEM_MANIFEST_PATH",
                                  "COCHEM_CORE_SILO", "COCHEM_UI_SILO", "COCHEM_CALC_SILO",
                                  "COCHEM_ML_SILO", "QT_QPA_PLATFORM", "COCHEM_HEADLESS",
                                  "XTB_CMD", "COCHEM_XTB_BIN", "XTBPATH", "PATH",
                                  "JUPYTER_DATA_DIR", "JUPYTER_RUNTIME_DIR", "JUPYTER_CONFIG_DIR",
                                  "IPYTHONDIR", "XDG_CACHE_HOME", "TMPDIR"}
    environment = {**installer_environment(), **{key: value for key, value in runtime.items() if key in selected}}
    subprocess.run([str(python), str(REPO_ROOT / "cli.py"), "setup", "--all", "--skip-heavy",
                    "--artifact-dir", str(root), "--min-disk-space-gb", "1", "--json"],
                   cwd=REPO_ROOT, env=environment,
                   stdin=subprocess.DEVNULL, check=True)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("orca", "cfour", "both"), default="both")
    parser.add_argument("--artifacts", type=Path,
                        default=Path(os.environ.get("COCHEM_ARTIFACT_DIR", "~/CoChem_Artifacts")))
    parser.add_argument("--jobs", type=int, choices=range(1, 33), default=2)
    parser.add_argument("--no-refresh-stage0", action="store_true",
                        help="Use before the initial dashboard setup; refresh Stage 0 afterwards.")
    args = parser.parse_args(argv)
    try:
        root = external_artifact_root(args.artifacts)
        result = provision_selected(["orca", "cfour"] if args.engine == "both" else [args.engine], root, args.jobs)
        result["stage0_refreshed"] = False if args.no_refresh_stage0 else refresh_stage0(root)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Licensed engine setup failed: {error}\n")
    print(json.dumps(result, indent=2))
    if not result["stage0_refreshed"]:
        print("Run python3 scripts/hosted_dashboard.py setup before requesting calculations.")
    print("If the dashboard was already running, stop and resume this Codespace so it loads the new engine bindings. "
          "Start a fresh dashboard with python3 scripts/hosted_dashboard.py start.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
