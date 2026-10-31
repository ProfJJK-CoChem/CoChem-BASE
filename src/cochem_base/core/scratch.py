"""Read-only Stage 0 scratch admission; never select guessed storage or run science."""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from cochem_base.core.managed_files import (
    BoundDirectory,
    DirectoryChain,
    ManagedPathError,
    open_directory_chain,
)


class ScratchAuthorityError(RuntimeError):
    """The retained Stage 0 evidence cannot admit this scratch operation."""


def _absolute_lexical(path: str | Path, label: str) -> Path:
    # Original authority spelling is retained: resolving a replaced ancestor
    # would silently bless the destination selected by a symlink.
    candidate = Path(path)
    if not candidate.is_absolute() or ".." in candidate.parts:
        raise ScratchAuthorityError(f"{label} requires an absolute lexical path without traversal")
    return candidate


def _read_document(path: Path, label: str) -> tuple[dict, dict]:
    candidate = _absolute_lexical(path, label)
    try:
        with open_directory_chain(candidate.parent) as parent:
            raw = parent.read_file(candidate.name, max_bytes=16 * 1024 * 1024)
            parent.verify()
            chain = tuple((str(path), device, inode) for path, device, inode in parent.chain)
    except (OSError, ManagedPathError) as error:
        raise ScratchAuthorityError(
            f"{label} is missing, exceeds its evidence budget, or has changed identity/symlink redirection"
        ) from error

    def unique_fields(pairs):
        result = {}
        for name, value in pairs:
            if name in result:
                raise ScratchAuthorityError(f"{label} contains duplicate JSON fields")
            result[name] = value
        return result

    try:
        payload = json.loads(raw, object_pairs_hook=unique_fields)
        json.dumps(payload, allow_nan=False)
    except (ValueError, UnicodeError) as error:
        raise ScratchAuthorityError(f"{label} is not a finite JSON document") from error
    if not isinstance(payload, dict):
        raise ScratchAuthorityError(f"{label} requires a JSON object")
    return payload, {
        "path": str(candidate),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "parent_directory_chain": chain,
    }


def _canonical_report_digest(report: dict) -> str:
    # This is the exact report encoding used by build_stage0_authority.
    return hashlib.sha256(json.dumps(report, sort_keys=True, allow_nan=False).encode()).hexdigest()


def _read_phase_report(
    report: dict, phase: int, expected_digest: str, expected_status: str
) -> dict:
    if (
        report.get("status") != expected_status
        or report.get("errors")
        or _canonical_report_digest(report) != expected_digest
    ):
        raise ScratchAuthorityError(
            f"Phase {phase} report does not match its published Stage 0 authority"
        )
    elapsed = report.get("execution_time_sec")
    if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
        raise ScratchAuthorityError(
            f"Phase {phase} requires its finite nonnegative measured CLI timing"
        )
    path = report.get("artifact_path")
    if not isinstance(path, str):
        raise ScratchAuthorityError(f"Phase {phase} lacks its producer-recorded report path")
    actual, source = _read_document(Path(path), f"Phase {phase} report")
    # execute_phase enriches the model_dump AFTER the phase writes its own file.
    # Only this exact measured CLI field is absent from the raw phase document.
    raw_expected = {name: value for name, value in report.items() if name != "execution_time_sec"}
    # JSON true/1 and integer/float must remain distinct; Python dict
    # equality would accept a type-corrupted report under this transform.
    if _canonical_report_digest(actual) != _canonical_report_digest(raw_expected):
        raise ScratchAuthorityError(
            f"Phase {phase} retained report changed after Stage 0 publication"
        )
    return {
        **source,
        "phase_number": phase,
        "status": expected_status,
        "canonical_report_sha256": expected_digest,
        "cli_execution_time_sec": elapsed,
        "serialization_transform": "cochem.base.execute-phase.execution-time-enrichment/1",
        "transform_producer": "src/cochem_base/cli.py:execute_phase (reviewed f96ee3f)",
    }


@dataclass(frozen=True)
class ScratchAdmission:
    """A fresh evidence snapshot, not a reusable engine-execution permission."""

    directory: Path
    sources: tuple[dict, ...]
    registry_path: Path
    audited_base: Path
    directory_chain: DirectoryChain = ()
    audited_base_chain: DirectoryChain = ()

    def create_operation_directory(self, prefix: str) -> BoundDirectory:
        """Create one private child exclusively; do not remove any scientific files."""
        if prefix != "crest":
            raise ScratchAuthorityError(
                "This admission supports only the owned CREST scratch operation"
            )
        # A caller-created dataclass or stale snapshot cannot grant write scope.
        if admit_scratch(self.registry_path) != self:
            raise ScratchAuthorityError(
                "Scratch admission changed before the owned operation was created"
            )
        return _create_owned_crest_directory(
            self.directory,
            self.audited_base,
            expected_chain=self.directory_chain,
            expected_base_chain=self.audited_base_chain,
        )


def _create_owned_crest_directory(
    directory: Path,
    audited_base: Path,
    *,
    expected_chain: DirectoryChain | None = None,
    expected_base_chain: DirectoryChain | None = None,
) -> BoundDirectory:
    """Allocate via the shared held directory capability, never full-path mkdir."""
    import uuid

    from cochem.core.context import assert_writable_path

    parent_path = _absolute_lexical(directory, "Admitted operation scratch")
    base_path = _absolute_lexical(audited_base, "Audited base scratch")
    if not parent_path.is_relative_to(base_path):
        raise ScratchAuthorityError("The admitted operation scratch is no longer available")
    try:
        with open_directory_chain(base_path, expected_chain=expected_base_chain) as base:
            with open_directory_chain(parent_path, expected_chain=expected_chain) as parent:
                if parent.chain[: len(base.chain)] != base.chain:
                    raise ScratchAuthorityError("The audited scratch directory chain changed")
                assert_writable_path(parent_path)
                child = parent.mkdir_child(f"crest_{uuid.uuid4().hex}", mode=0o700, exist_ok=False)
                try:
                    base.verify()
                    parent.verify()
                    child.verify()
                    return child
                except BaseException:
                    child.close()
                    raise
    except (OSError, ManagedPathError) as error:
        raise ScratchAuthorityError(
            "The admitted operation scratch directory identity changed"
        ) from error


def admit_scratch(registry_path: str | Path | None = None) -> ScratchAdmission:
    """Require actual complete setup reports, audited path and current context bounds.

    No registry lock or directory is created by admission. No directory is scaffolded,
    no authority is rewritten and no fallback is selected. Engine authorization
    remains a separate mandatory check at the actual CREST launch boundary.
    """
    from cochem.core.context import assert_writable_path, get_current_context
    from cochem_base.cochem_core_registry_schema import CoChemSystemConfig
    from cochem_base.orchestrator.stage0_authority import validate_stage0_scratch

    chosen = registry_path if registry_path is not None else os.environ.get("COCHEM_CONFIG")
    if chosen is None:
        # Match resolve_config_path's ordinary data-tier policy without its mkdir.
        artifacts = (
            os.environ.get("COCHEM_ARTIFACTS")
            or os.environ.get("COCHEM_ARTIFACT_DIR")
            or Path.home() / "CoChem_Artifacts"
        )
        chosen = Path(artifacts) / "Registry" / "cochem_system_config.json"
    path = _absolute_lexical(chosen, "Golden Registry")
    # Accept a directory spelling only by a no-follow binding of that directory.
    try:
        with open_directory_chain(path) as registry_directory:
            registry_directory.verify()
            registry_is_directory = True
    except NotADirectoryError:
        registry_is_directory = False
    except FileNotFoundError as error:
        raise ScratchAuthorityError(
            "Complete Stage 0 scratch authority is unavailable: Golden Registry is missing"
        ) from error
    except (OSError, ManagedPathError) as error:
        raise ScratchAuthorityError(
            "Golden Registry directory has symlink redirection or changed identity"
        ) from error
    if registry_is_directory:
        path /= "cochem_system_config.json"
    try:
        raw, registry_source = _read_document(path, "Golden Registry")
        config = CoChemSystemConfig.model_validate(raw)
        if (
            config.status not in {"LOCKED", "ACTIVE", "PASSED", "DEGRADED_OPERATIONAL"}
            or not config.verify_checksum()
            or config.stage0 is None
        ):
            raise ScratchAuthorityError(
                "Scratch requires a verified operational eleven-phase Stage 0 authority"
            )
        # Stage0Authority validates the unique complete 1..11 sequence/statuses.
        expected = {item.phase_number: item for item in config.stage0.phases}
        if set(expected) != set(range(1, 12)):
            raise ScratchAuthorityError("Scratch requires every published Stage 0 phase")
        artifacts = _absolute_lexical(
            raw.get("environment", {}).get("artifacts_dir", ""), "Raw audited artifact root"
        )
        if (
            _absolute_lexical(config.environment.artifacts_dir, "Audited artifact root")
            != artifacts
        ):
            raise ScratchAuthorityError("Registry parsing changed its original artifact path")
        with open_directory_chain(artifacts) as bound_artifacts:
            artifact_chain = bound_artifacts.chain
        summary, summary_source = _read_document(
            artifacts / "Registry" / "setup_summary.json", "Stage 0 summary"
        )
        if (
            summary.get("dry_run") is not False
            or summary.get("overall_status") != config.status
            or _absolute_lexical(summary.get("artifact_dir", ""), "Setup artifact root")
            != artifacts
            or _absolute_lexical(summary.get("registry_path", ""), "Setup registry path") != path
        ):
            raise ScratchAuthorityError(
                "The actual setup summary does not bind this audited root and registry"
            )
        entries = summary.get("phases_executed")
        if not isinstance(entries, list) or len(entries) != 11:
            raise ScratchAuthorityError("The setup summary must retain all eleven phase reports")
        reports, sources = {}, [registry_source, summary_source]
        for entry in entries:
            number = entry.get("phase_number") if isinstance(entry, dict) else None
            if type(number) is not int or number not in expected or number in reports:
                raise ScratchAuthorityError(
                    "The setup summary has invalid or duplicate phase identities"
                )
            published = expected[number]
            report = entry.get("report")
            if not isinstance(report, dict) or entry.get("status") != published.status:
                raise ScratchAuthorityError(
                    f"Phase {number} summary status differs from published authority"
                )
            report_path = _absolute_lexical(
                report.get("artifact_path", ""), f"Phase {number} artifact path"
            )
            if not report_path.is_relative_to(artifacts):
                raise ScratchAuthorityError(
                    f"Phase {number} report escapes the audited artifact root"
                )
            sources.append(_read_phase_report(report, number, published.sha256, published.status))
            reports[number] = report
        for raw_path in (
            reports[6].get("storage_paths", {}).get("scratch_directory", ""),
            reports[7].get("scratch", {}).get("scratch_directory", ""),
        ):
            _absolute_lexical(raw_path, "Producer-recorded scratch")
        raw_registry_scratch = _absolute_lexical(
            raw.get("environment", {}).get("scratch_dir", ""), "Raw registry scratch"
        )
        raw_scratch = _absolute_lexical(
            reports[6].get("storage_paths", {}).get("scratch_directory", ""), "Audited scratch"
        )
        with open_directory_chain(raw_scratch) as bound_base:
            base_chain = bound_base.chain
            scratch = _absolute_lexical(
                validate_stage0_scratch(reports[6], reports[7]), "Audited scratch"
            )
            bound_base.verify()
        if scratch != raw_scratch:
            raise ScratchAuthorityError("Phase validation changed its original scratch path")
        recorded = _absolute_lexical(config.environment.scratch_dir or "", "Registry scratch")
        if (
            scratch != recorded
            or raw_registry_scratch != scratch
            or _absolute_lexical(
                reports[7].get("scratch", {}).get("scratch_directory", ""), "Phase 7 scratch"
            )
            != scratch
        ):
            raise ScratchAuthorityError("Registry scratch differs from the actual phase 6/7 audit")
        forbidden = [Path(sys.prefix).absolute(), Path(__file__).resolve().parents[1]]
        forbidden += [Path(silo.root).absolute() for silo in config.stage0.micro_silos.values()]
        if any(scratch.is_relative_to(root.resolve()) for root in forbidden):
            raise ScratchAuthorityError(
                "Scratch cannot be inside an installed runtime or source package"
            )
        assert_writable_path(scratch)
        injected = reports[7].get("injected_env_vars", {})
        variables = {"COCH_SCRATCH", "COCHEM_SCRATCH", "COCHEM_SCRATCH_DIR"}
        variables.update(key for key in ("TMPDIR", "SLURM_TMPDIR") if key in injected)
        for variable in variables:
            value = os.environ.get(variable)
            if value and _absolute_lexical(value, variable) != scratch:
                raise ScratchAuthorityError(
                    f"{variable} conflicts with the audited Stage 0 scratch"
                )
        selected = scratch
        try:
            context = get_current_context()
        except RuntimeError:
            context = None
        if context is not None:
            selected = _absolute_lexical(context.scratch_dir, "Current operation scratch")
            if not selected.is_relative_to(scratch):
                raise ScratchAuthorityError(
                    "Current operation scratch is outside the audited scratch permission"
                )
            assert_writable_path(selected, context)
        with open_directory_chain(artifacts, expected_chain=artifact_chain) as final_artifacts:
            final_artifacts.verify()
        with open_directory_chain(scratch, expected_chain=base_chain) as final_base:
            final_base.verify()
        with open_directory_chain(selected) as bound_selected:
            selected_chain = bound_selected.chain
            if selected_chain[: len(base_chain)] != base_chain:
                raise ScratchAuthorityError("Selected operation scratch changed audited ancestry")
        # Refuse evidence changed during admission; never repair its authority.
        for source in sources:
            _, final = _read_document(Path(source["path"]), "Retained Stage 0 evidence")
            if final != {key: value for key, value in source.items() if key in final}:
                raise ScratchAuthorityError("Stage 0 evidence changed during scratch admission")
        return ScratchAdmission(selected, tuple(sources), path, scratch, selected_chain, base_chain)
    except (OSError, ManagedPathError) as error:
        raise ScratchAuthorityError(
            "Stage 0 evidence or scratch directory binding changed"
        ) from error
