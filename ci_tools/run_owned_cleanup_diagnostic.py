"""Record an actual native cleanup diagnosis without certifying acceptance."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
for diagnostic_stream in (sys.stdout, sys.stderr):
    if hasattr(diagnostic_stream, "reconfigure"):
        diagnostic_stream.reconfigure(encoding="utf-8")
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ci_tools.base_ci import (InfrastructureIntegrityError, _control_evidence_directory,
    _copy_reviewed_source, _git, _profile_environment, _source_origin_receipts,
    tracked_source_snapshot, verify_source_binding)

OBSERVER_SHA256 = "1042dfd4486b91eac869b5adf49246343f6a081a3093abae5621792848a94c4e"
TEST_SHA256 = "354ad7a7f44b91d7439e82c42f471b6e513661122360a9473c31a41fa04a04ee"


def write_private(path: Path, value: object) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    supplied = arguments.output
    if (not supplied.is_absolute() or supplied.is_symlink()
            or supplied.resolve().is_relative_to(root)):
        raise ValueError("Diagnostic evidence must be an absolute external directory")
    output = supplied.resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    report = {"scope": "Native engineering diagnosis; never release acceptance",
              "release_accepted": False, "executed": False, "diagnostic_complete": False}
    before = tracked_source_snapshot(root)
    write_private(output / "source-before.json", before)
    try:
        binding = verify_source_binding(root, expected_revision=arguments.expected_revision)
        report["source_binding"] = binding
        observer = root / "ci_tools/native_owned_cleanup_observer.py"
        test = root / "tests/ci_tools/test_quarantine_owned_processes.py"
        if (hashlib.sha256(observer.read_bytes()).hexdigest() != OBSERVER_SHA256
                or hashlib.sha256(test.read_bytes()).hexdigest() != TEST_SHA256):
            raise InfrastructureIntegrityError("Diagnostic producer differs from reviewed native controls")
        external_observer = output / "observer.py"
        shutil.copyfile(observer, external_observer)
        external_observer.chmod(0o600)
        if hashlib.sha256(external_observer.read_bytes()).hexdigest() != OBSERVER_SHA256:
            raise InfrastructureIntegrityError("External diagnostic observer copy differs")
        from ci_tools.zero_trust_runner import QuarantineEnvironment
        descendants = output / "descendant-origins"
        descendants.mkdir(mode=0o700)
        with QuarantineEnvironment(base_dir=output / "quarantine", preserve_on_failure=True) as quarantine:
            copied = quarantine.quarantine_dir
            _copy_reviewed_source(root, copied, binding)
            copied_before = tracked_source_snapshot(copied)
            write_private(output / "copied-source-before.json", copied_before)
            if copied_before != before or _git(copied, ["status", "--porcelain=v1", "-z"]):
                raise InfrastructureIntegrityError("Diagnostic copy differs from committed source")
            environment = _profile_environment(root, copied)
            environment.update(COCHEM_SOURCE_QUARANTINE_ROOT=str(copied),
                COCHEM_SOURCE_QUARANTINE_ORIGINAL=str(root),
                COCHEM_SOURCE_QUARANTINE_EVIDENCE=str(descendants),
                COCHEM_SOURCE_QUARANTINE_REVISION=binding["revision"],
                COCHEM_CI_CONTROL_EVIDENCE_DIR=str(_control_evidence_directory(output)))
            bootstrap = ("import runpy,sys;sys.path.insert(0,sys.argv[1]);"
                "from ci_tools.source_quarantine import activate_from_environment;"
                "activate_from_environment();sys.argv=sys.argv[2:];"
                "runpy.run_path(sys.argv[0],run_name='__main__')")
            completed = quarantine.run_command([sys.executable, "-I", "-B", "-c", bootstrap,
                str(copied), str(external_observer), str(copied), str(output / "native-observations")],
                timeout=120, environment=environment)
            report.update(executed=True, native_command_exit_code=completed.exit_code,
                native_command_timed_out=completed.timed_out)
            write_private(output / "native-command.json", completed.to_dict())
            copied_after = tracked_source_snapshot(copied)
            write_private(output / "copied-source-after.json", copied_after)
            report["copied_source_unchanged"] = copied_before == copied_after
            report["copied_git_clean"] = not bool(_git(copied, ["status", "--porcelain=v1", "-z"]))
            origins = _source_origin_receipts(descendants, copied, root, binding["revision"])
            write_private(output / "child-authority.json", origins)
            report["child_authority_verified"] = bool(origins["records"]) and not (
                origins["authority_errors"] or origins["failed"])
            receipt = output / "native-observations/native-diagnostic-receipt.json"
            if receipt.is_file():
                observation = json.loads(receipt.read_text(encoding="utf-8"))
                cases = observation.get("actual_cases", [])
                report["original_assertions_passed"] = bool(len(cases) == 4 and all(
                    case.get("original_assertions_passed") is True for case in cases))
                report["diagnostic_complete"] = bool(completed.passed and len(cases) == 4
                    and observation.get("source_revision") == binding["revision"]
                    and observation.get("source_unchanged") is True
                    and report["copied_source_unchanged"] and report["copied_git_clean"]
                    and report["child_authority_verified"])
        report["outer_cleanup_observations"] = [item.to_dict() for item in quarantine.cleanup_observations]
    except Exception as error:
        report["diagnostic_error_type"] = type(error).__name__
        raise
    finally:
        after = tracked_source_snapshot(root)
        write_private(output / "source-after.json", after)
        report["original_source_unchanged"] = before == after
        write_private(output / "diagnostic-summary.json", report)
    return 0 if (report["diagnostic_complete"] and report["original_source_unchanged"]
                 and report.get("original_assertions_passed") is True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
