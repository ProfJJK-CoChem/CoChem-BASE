"""Bind a student BASE controller to its separately pinned native TORQ source.

This invokes TORQ's original transport validator. It never changes a request,
approval, calculator, workflow outcome, or scientific result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from scripts import manage_modules as manager

REQUIRED_NATIVE_FILES = (
    "ci_tools/actions_request.py",
    "ci_tools/qualify_pyscf_image.py",
    "ci_tools/annotate_ci_failure.py",
    "ci_tools/requirements-pyscf-py312.txt",
    "docker/engines/pyscf/Dockerfile",
    "src/cochem_torq/application.py",
    "src/cochem_torq/service.py",
)


def native_spec(manifest: Path = manager.DEFAULT_MANIFEST) -> dict:
    spec = manager.load_manifest(manifest)["modules"]["torq"]
    if spec.get("distribution") != "CoChem-TORQ":
        raise ValueError("Native TORQ requires the reviewed CoChem-TORQ distribution.")
    return spec


def resolve_catalog(manifest: Path, output: Path) -> dict:
    """Expose only reviewed repository and immutable scientific source identity."""
    spec = native_spec(manifest)
    values = {"repository": spec["repository"], "revision": spec["revision"]}
    with output.open("a", encoding="utf-8") as stream:
        for key, value in values.items():
            stream.write(f"{key}={value}\n")
    return values


def verify_source(
    controller: Path,
    source: Path,
    manifest: Path,
    output: Path,
    *,
    expected_controller_sha: str,
    observed_controller_sha: str,
) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", expected_controller_sha):
        raise ValueError("Native TORQ requires an immutable approved BASE controller SHA.")
    if expected_controller_sha != observed_controller_sha:
        raise ValueError("The owning student controller differs from the approved submission.")
    controller = controller.resolve(strict=True)
    source = source.resolve(strict=True)
    if source.is_relative_to(controller) or controller.is_relative_to(source):
        raise ValueError("Scientific TORQ and student BASE controller checkouts must be separate.")
    actual = manager._git(controller, "rev-parse", "HEAD")
    if actual != observed_controller_sha:
        raise ValueError("The checked-out BASE controller differs from its workflow event SHA.")
    if manager._git(controller, "status", "--porcelain", "--untracked-files=all", "--ignored"):
        raise ValueError("The checked-out BASE controller is modified.")
    catalog = manifest.resolve(strict=True)
    if not catalog.is_relative_to(controller):
        raise ValueError("Native TORQ catalog must belong to the checked-out student controller.")
    spec = native_spec(catalog)
    observed_origin = manager._git(source, "config", "--get", "remote.origin.url")
    expected_origin = manager._repository_url(spec)
    if observed_origin not in {expected_origin, expected_origin.removesuffix(".git")}:
        raise manager.ModuleInstallationError(
            "Native TORQ source origin differs from its reviewed repository."
        )

    def native_git_reader(command, **options):
        """Perform genuine Git reads; normalize only the validated URL spelling.

        actions/checkout uses the same HTTPS repository URL without .git. This
        accepted spelling is retained below, while the shared install verifier
        receives its canonical equivalent. Commit, tree and byte checks still
        come directly from the original real Git subprocess and file inventory.
        """
        observed = manager._run(command, **options)
        if command[3:] == ["config", "--get", "remote.origin.url"]:
            if observed not in {expected_origin, expected_origin.removesuffix(".git")}:
                raise manager.ModuleInstallationError(
                    "Native TORQ source origin changed during verification."
                )
            return expected_origin
        return observed

    identity = manager._source_integrity(source, spec, runner=native_git_reader)
    for name in REQUIRED_NATIVE_FILES:
        path = source / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(
                "The reviewed source does not contain the required native TORQ worker."
            )
    evidence = {
        "schema_version": "cochem.native-torq-controller/1",
        "controller_repository": os.environ.get("GITHUB_REPOSITORY"),
        "controller_commit": actual,
        "torq_repository": spec["repository"],
        "torq_commit": spec["revision"],
        "observed_torq_origin": observed_origin,
        "catalog_sha256": hashlib.sha256(catalog.read_bytes()).hexdigest(),
        "catalog_spec_sha256": manager._digest_json(spec),
        **identity,
        "transport_schema": "cochem.torq.request/1",
        "scientific_calculation_performed": False,
        "scientific_release_certified": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(evidence, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return evidence


def validate_transport(source: Path, request: Path, approval: Path) -> None:
    """Use the unmodified pinned native validator and preserve its exit status."""
    subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(source / "ci_tools/actions_request.py"),
            "--output",
            str(request),
            "--approved-plan-output",
            str(approval),
        ],
        cwd=source,
        check=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="operation", required=True)
    resolve = subparsers.add_parser("resolve")
    resolve.add_argument("--manifest", type=Path, default=manager.DEFAULT_MANIFEST)
    resolve.add_argument("--output", type=Path, required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--controller", type=Path, required=True)
    verify.add_argument("--source", type=Path, required=True)
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)
    if arguments.operation == "resolve":
        resolve_catalog(arguments.manifest, arguments.output)
    else:
        verify_source(
            arguments.controller,
            arguments.source,
            arguments.manifest,
            arguments.output,
            expected_controller_sha=os.environ["TORQ_EXPECTED_SOURCE_SHA"],
            observed_controller_sha=os.environ["GITHUB_SHA"],
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
