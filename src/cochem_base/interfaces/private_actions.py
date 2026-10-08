"""Codespaces interface for calculation jobs in the student's private project.

Every remote operation uses the already authorized GitHub CLI identity. Licensed
assets are staged privately by the shared asset module; calculations execute in
the owning repository's Actions runner. No tokens are read or displayed.
"""

from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import re
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote, urlencode

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
REPO_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9._-]*")
TASK_PATTERN = re.compile(r"[0-9a-f]{32}")
SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
WORKFLOWS = {
    "orca": ".github/workflows/orca_calculation.yml",
    "cfour": ".github/workflows/cfour_calculation.yml",
}


class PrivateActionsError(RuntimeError):
    pass


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _gh(route: str, *, method: str = "GET", document: dict[str, Any] | None = None) -> Any:
    command = [
        "gh", "api", "--hostname", "github.com", "--method", method, route,
        "-H", "Accept: application/vnd.github+json",
        "-H", "X-GitHub-Api-Version: 2022-11-28",
    ]
    if document is not None:
        command.extend(["--input", "-"])
    environment = os.environ.copy()
    environment.update(GH_DEBUG="0", GH_PROMPT_DISABLED="1", GH_PAGER="cat")
    try:
        result = subprocess.run(
            command,
            input=_canonical(document) if document is not None else None,
            env=environment,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PrivateActionsError("The authorized GitHub CLI operation could not complete.") from exc
    if result.returncode:
        raise PrivateActionsError(
            "GitHub refused the project operation. Authenticate your own account "
            "through the approved browser flow and verify access to this private project."
        )
    if not result.stdout:
        return None
    if len(result.stdout) > 8 * 1024 * 1024:
        raise PrivateActionsError("The GitHub response exceeds the bounded project query.")
    try:
        return json.loads(result.stdout)
    except (UnicodeError, ValueError) as exc:
        raise PrivateActionsError("GitHub returned no valid project response.") from exc


@dataclass(frozen=True)
class PrivateProject:
    repository: str
    repository_id: int
    owner_id: int
    owner_login: str
    default_branch: str


def validate_private_project(
    repository: str, metadata: dict[str, Any], viewer: dict[str, Any]
) -> PrivateProject:
    owner = metadata.get("owner")
    if (
        REPO_PATTERN.fullmatch(repository) is None
        or metadata.get("full_name") != repository
        or metadata.get("private") is not True
        or metadata.get("visibility") not in (None, "private")
        or not isinstance(owner, dict)
        or owner.get("type") != "User"
        or type(metadata.get("id")) is not int
        or metadata["id"] < 1
        or type(owner.get("id")) is not int
        or owner["id"] < 1
        or viewer.get("type") != "User"
        or type(viewer.get("id")) is not int
        or viewer.get("id") != owner["id"]
        or viewer.get("login") != owner.get("login")
        or not isinstance(metadata.get("default_branch"), str)
        or not metadata["default_branch"]
    ):
        raise PrivateActionsError("Use a private project owned by the authenticated student's account.")
    return PrivateProject(
        repository=repository, repository_id=metadata["id"], owner_id=owner["id"],
        owner_login=owner["login"], default_branch=metadata["default_branch"],
    )


def validate_ref(ref: str) -> str:
    if (
        not isinstance(ref, str)
        or not ref.startswith("refs/heads/")
        or len(ref) > 255
        or any(value in ref for value in ("..", "@{", "\\", "//"))
        or any(ord(value) < 33 or value in "~^:?*[" for value in ref)
        or ref.endswith(("/", ".", ".lock"))
        or any(part.startswith(".") or not part for part in ref.split("/"))
    ):
        raise PrivateActionsError("Select an explicit, valid refs/heads/ project branch.")
    return ref


def run_belongs_to_task(
    run: dict[str, Any], receipt: dict[str, Any], repository: str
) -> bool:
    title = run.get("display_title")
    path = run.get("path")
    task = receipt["task_id"]
    project = receipt["project"]
    own = run.get("repository")
    head = run.get("head_repository")
    return bool(
        isinstance(title, str)
        and TASK_PATTERN.fullmatch(task) is not None
        and task in re.findall(r"(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])", title)
        and run.get("event") == "workflow_dispatch"
        and run.get("head_sha") == project["source_sha"]
        and run.get("head_branch") == project["ref"].removeprefix("refs/heads/")
        and isinstance(head, dict)
        and head.get("full_name") == repository
        and head.get("id") == receipt["destination"]["repository_id"]
        and isinstance(path, str)
        and path.split("@", 1)[0] == project["workflow_path"]
        and isinstance(own, dict)
        and own.get("full_name") == repository
        and own.get("id") == receipt["destination"]["repository_id"]
        and type(run.get("id")) is int
        and run["id"] > 0
    )


class PrivateActionsController:
    def __init__(self, repository: str, runtime: Path):
        if REPO_PATTERN.fullmatch(repository) is None:
            raise PrivateActionsError("Use an exact personal OWNER/REPOSITORY project.")
        selected = runtime.expanduser().absolute()
        if (
            any(parent.is_symlink() for parent in (selected, *selected.parents))
            or selected.resolve().is_relative_to(REPOSITORY_ROOT)
        ):
            raise PrivateActionsError("Private lifecycle receipts belong outside the checkout.")
        selected.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.repository = repository
        self.runtime = selected.resolve()

    @contextmanager
    def _locked(self) -> Iterator[None]:
        path = self.runtime / ".actions-lifecycle.lock"
        if path.is_symlink():
            raise PrivateActionsError("The lifecycle lock must not use symbolic links.")
        descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "a+b") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def stage_and_dispatch(
        self, payload: bytes, descriptor: Path, descriptor_sha256: str, *,
        ref: str, cores: int, maxcore_mb: int,
    ) -> dict[str, Any]:
        with self._locked():
            return self._stage_and_dispatch(
                payload, descriptor, descriptor_sha256,
                ref=ref, cores=cores, maxcore_mb=maxcore_mb,
            )

    def status(self, task_id: str) -> dict[str, Any]:
        with self._locked():
            return self._status(task_id)

    def cancel(self, task_id: str) -> dict[str, Any]:
        with self._locked():
            return self._cancel(task_id)

    def download(self, task_id: str) -> dict[str, Any]:
        with self._locked():
            return self._download(task_id)

    def cleanup(self, task_id: str) -> dict[str, Any]:
        with self._locked():
            return self._cleanup(task_id)

    def repair(self, task_id: str) -> dict[str, Any]:
        from scripts.private_engine_assets import repair_staging
        with self._locked():
            state = self.load(task_id)
            self.project()
            observed = repair_staging(receipt_path=Path(state["receipt_path"]))
            state["staging_repair_observation"] = observed
            state["history"].append({"event": "actual_staging_repair_observed",
                                     "at": datetime.now(timezone.utc).isoformat()})
            self._save(state)
            return state

    def select_run(self, task_id: str, run_id: int) -> dict[str, Any]:
        if type(run_id) is not int or run_id < 1:
            raise PrivateActionsError("Select an actual positive owning-project run ID.")
        with self._locked():
            state = self.load(task_id)
            receipt = self._receipt(state)
            run = _gh("repos/" + self.repository + "/actions/runs/" + str(run_id))
            if not run_belongs_to_task(run, receipt, self.repository):
                raise PrivateActionsError("The selected real run does not belong to this task.")
            state["run_id"] = run_id
            self._save(state)
            return self._status(task_id)

    def project(self) -> PrivateProject:
        if os.environ.get("CODESPACES", "").lower() != "true":
            raise PrivateActionsError("Private asset staging and dispatch require the Codespaces interface.")
        return validate_private_project(
            self.repository, _gh("repos/" + self.repository), _gh("user")
        )

    def _save(self, state: dict[str, Any]) -> None:
        path = self.runtime / (state["task_id"] + "-actions.json")
        encoded = _canonical(state)
        with tempfile.NamedTemporaryFile(mode="wb", dir=self.runtime, delete=False) as output:
            temporary = Path(output.name)
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, path)

    def load(self, task_id: str) -> dict[str, Any]:
        if TASK_PATTERN.fullmatch(task_id) is None:
            raise PrivateActionsError("Select an actual retained task UUID.")
        path = self.runtime / (task_id + "-actions.json")
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 128 * 1024:
            raise PrivateActionsError("The task has no bounded private lifecycle record.")
        state = json.loads(path.read_bytes())
        if not isinstance(state, dict):
            raise PrivateActionsError("A private lifecycle record must contain an object.")
        if state.get("task_id") != task_id or state.get("repository") != self.repository:
            raise PrivateActionsError("The lifecycle record belongs to another task/project.")
        return state

    def _receipt(self, state: dict[str, Any]) -> dict[str, Any]:
        from scripts.private_engine_assets import load_staging_receipt

        project = self.project()
        receipt_path = Path(state["receipt_path"])
        if receipt_path.is_symlink() or not receipt_path.is_file():
            raise PrivateActionsError("The original private staging receipt is unavailable.")
        receipt = load_staging_receipt(
            receipt_path.read_bytes(), state["receipt_sha256"], allow_expired=True
        )
        if (
            receipt["task_id"] != state["task_id"]
            or receipt["destination"]["repository"] != project.repository
            or receipt["destination"]["repository_id"] != project.repository_id
            or receipt["destination"]["owner_id"] != project.owner_id
        ):
            raise PrivateActionsError("Task staging does not belong to the current personal project.")
        return receipt

    def _stage_and_dispatch(
        self, payload: bytes, descriptor: Path, descriptor_sha256: str, *,
        ref: str, cores: int, maxcore_mb: int,
    ) -> dict[str, Any]:
        """Upload a unique validated job, stage privately, and request actual Actions."""
        from cochem_base.interfaces.actions_jobs import (
            decode_configuration,
            validate_configuration,
            validate_resources,
        )
        from scripts.private_engine_assets import load_staging_receipt, stage_private_asset

        project = self.project()
        ref = validate_ref(ref)
        validate_resources(cores, maxcore_mb)
        configuration = decode_configuration(payload)
        validate_configuration(payload, configuration)
        engine = configuration.get("engine", "orca")
        if engine not in WORKFLOWS:
            raise PrivateActionsError("Select a connected ORCA or CFOUR calculation.")
        if (
            not descriptor.is_file() or descriptor.is_symlink()
            or descriptor.stat().st_size > 1024 * 1024
            or re.fullmatch(r"[0-9a-f]{64}", descriptor_sha256) is None
            or hashlib.sha256(descriptor.read_bytes()).hexdigest() != descriptor_sha256
        ):
            raise PrivateActionsError("Select the actual independently reviewed distribution descriptor.")
        workflow = WORKFLOWS[engine]
        _gh(
            "repos/" + project.repository + "/contents/" + workflow + "?"
            + urlencode({"ref": ref})
        )
        job_file = "jobs/cochem-" + uuid.uuid4().hex + ".json"
        uploaded = _gh(
            "repos/" + project.repository + "/contents/" + job_file,
            method="PUT",
            document={
                "message": "Add validated CoChem calculation request",
                "content": base64.b64encode(payload).decode("ascii"),
                "branch": ref.removeprefix("refs/heads/"),
            },
        )
        source_sha = uploaded.get("commit", {}).get("sha")
        if not isinstance(source_sha, str) or SHA_PATTERN.fullmatch(source_sha) is None:
            raise PrivateActionsError("GitHub did not return the actual uploaded request commit.")
        receipt_path = self.runtime / ("stage-" + uuid.uuid4().hex + ".json")
        staged = stage_private_asset(
            engine=engine, descriptor=descriptor, descriptor_sha256=descriptor_sha256,
            repository=project.repository, ref=ref, source_sha=source_sha,
            workflow_path=workflow, receipt=receipt_path, expires_hours=24,
            calculation={
                "job_file": job_file, "input_sha256": hashlib.sha256(payload).hexdigest(),
                "cores": cores, "maxcore_mb": maxcore_mb,
            },
        )
        receipt = load_staging_receipt(receipt_path.read_bytes(), staged["receipt_sha256"])
        encoded = _canonical(receipt)
        state = {
            "schema_version": "cochem.private-actions-lifecycle/1",
            "task_id": receipt["task_id"], "repository": project.repository,
            "engine": engine,
            "receipt_path": str(receipt_path),
            "receipt_sha256": hashlib.sha256(encoded).hexdigest(),
            "job_file": job_file, "input_sha256": hashlib.sha256(payload).hexdigest(),
            "source_sha": source_sha, "workflow_path": workflow,
            "ref": ref, "submitted_at": datetime.now(timezone.utc).isoformat(),
            "run_id": None, "status": "staged_not_dispatched", "history": [],
        }
        self._save(state)
        current = _gh(
            "repos/" + project.repository + "/git/ref/"
            + quote(ref.removeprefix("refs/"), safe="/")
        )
        if current.get("object", {}).get("sha") != source_sha:
            raise PrivateActionsError(
                "The project branch changed after staging; retain the receipt for review."
            )
        _gh(
            "repos/" + project.repository + "/actions/workflows/"
            + Path(workflow).name + "/dispatches",
            method="POST",
            document={
                "ref": ref,
                "inputs": {
                    "job_file": job_file, "cores": str(cores), "maxcore_mb": str(maxcore_mb),
                    "asset_receipt": encoded.decode("utf-8"),
                    "asset_receipt_sha256": state["receipt_sha256"],
                    "asset_task_id": receipt["task_id"],
                },
            },
        )
        state["status"] = "dispatched_pending_observed_run"
        state["history"].append({"event": "dispatch_accepted", "at": state["submitted_at"]})
        self._save(state)
        return state

    def _status(self, task_id: str) -> dict[str, Any]:
        state = self.load(task_id)
        receipt = self._receipt(state)
        if state["run_id"] is None:
            runs: list[dict[str, Any]] = []
            rejected: list[dict[str, Any]] = []
            for page in range(1, 11):
                result = _gh(
                    "repos/" + self.repository + "/actions/workflows/"
                    + Path(receipt["project"]["workflow_path"]).name + "/runs?"
                    + urlencode({"event": "workflow_dispatch", "per_page": 100,
                                 "page": page})
                )
                if result.get("total_count", 0) > 1000:
                    raise PrivateActionsError("Run inventory exceeds the bounded task query; select its run ID.")
                runs.extend(
                    run for run in result["workflow_runs"]
                    if run_belongs_to_task(run, receipt, self.repository)
                    and datetime.fromisoformat(run["created_at"])
                    >= datetime.fromisoformat(state["submitted_at"]).replace(microsecond=0)
                )
                for actual in result["workflow_runs"]:
                    title = actual.get("display_title", "")
                    repository = actual.get("repository") or {}
                    if (
                        isinstance(title, str)
                        and receipt["task_id"] in re.findall(
                            r"(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])", title
                        )
                        and repository.get("full_name") == self.repository
                        and repository.get("id") == receipt["destination"]["repository_id"]
                        and not run_belongs_to_task(actual, receipt, self.repository)
                    ):
                        rejected.append({
                            "run_id": actual["id"], "head_sha": actual.get("head_sha"),
                            "head_branch": actual.get("head_branch"), "status": actual.get("status"),
                            "conclusion": actual.get("conclusion"),
                            "reason": "Observed task run differs from approved source/ref/identity.",
                            "scientific_execution_authorized_by_this_observation": False,
                        })
                if len(result["workflow_runs"]) < 100:
                    break
            if len(runs) > 1:
                raise PrivateActionsError("More than one actual run matches this task; select it explicitly.")
            if not runs:
                if rejected:
                    state["status"] = "dispatch_observed_with_rejected_identity"
                    state["rejected_run_observations"] = rejected
                    state["recovery"] = "Retain the private receipt and review staged-asset repair."
                    self._save(state)
                return state
            state["run_id"] = runs[0]["id"]
        run = _gh("repos/" + self.repository + "/actions/runs/" + str(state["run_id"]))
        if not run_belongs_to_task(run, receipt, self.repository):
            raise PrivateActionsError("The actual Actions run differs from its task/source/project.")
        previous_attempt = state.get("run_attempt")
        state.update(
            status=run["status"], conclusion=run.get("conclusion"),
            run_attempt=run["run_attempt"], run_url=run["html_url"],
        )
        if previous_attempt is not None and previous_attempt != run["run_attempt"]:
            state.pop("results_directory", None)
            state.pop("downloaded_run_attempt", None)
        state["history"].append(
            {"event": "observed_run", "at": datetime.now(timezone.utc).isoformat(),
             "status": run["status"], "conclusion": run.get("conclusion")}
        )
        self._save(state)
        return state

    def _cancel(self, task_id: str) -> dict[str, Any]:
        state = self._status(task_id)
        if state["run_id"] is None or state["status"] == "completed":
            raise PrivateActionsError("Only an observed, nonterminal owned run can be cancelled.")
        _gh(
            "repos/" + self.repository + "/actions/runs/" + str(state["run_id"]) + "/cancel",
            method="POST",
        )
        state["history"].append(
            {"event": "cancellation_requested", "at": datetime.now(timezone.utc).isoformat()}
        )
        self._save(state)
        return state

    def _download(self, task_id: str) -> dict[str, Any]:
        state = self._status(task_id)
        if state["run_id"] is None or state["status"] != "completed":
            raise PrivateActionsError("Wait for the observed owned run to complete before downloading.")
        attempt = state["run_attempt"]
        destination = self.runtime / (task_id + "-attempt-" + str(attempt) + "-results")
        if destination.exists():
            raise PrivateActionsError("A result download must not overwrite existing evidence.")
        name = f"{state['engine']}-calculation-{state['run_id']}-{state['run_attempt']}"
        artifacts = _gh("repos/" + self.repository + "/actions/runs/" + str(state["run_id"]) + "/artifacts?per_page=100")
        if artifacts.get("total_count", 0) > 100:
            raise PrivateActionsError("Artifact inventory exceeds the bounded run query.")
        matches = [artifact for artifact in artifacts["artifacts"] if artifact.get("name") == name]
        if len(matches) != 1 or matches[0].get("expired") is not False:
            raise PrivateActionsError("The exact run-attempt evidence artifact is unavailable.")
        artifact = matches[0]
        result = subprocess.run(
            ["gh", "run", "download", str(state["run_id"]), "--repo", self.repository,
             "--name", name, "--dir", str(destination)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=60,
        )
        if result.returncode or not destination.is_dir() or not any(destination.rglob("*")):
            raise PrivateActionsError("GitHub returned no completed calculation evidence artifact.")
        observed = _gh("repos/" + self.repository + "/actions/runs/" + str(state["run_id"]))
        if (
            observed.get("status") != "completed" or observed.get("run_attempt") != attempt
            or not run_belongs_to_task(observed, self._receipt(state), self.repository)
        ):
            raise PrivateActionsError("Run authority changed during download; evidence remains unclaimed.")
        supplied = list(destination.rglob("submitted-job.json"))
        verified_input = False
        if supplied:
            if len(supplied) != 1 or supplied[0].is_symlink():
                raise PrivateActionsError("The artifact contains ambiguous calculation inputs.")
            if hashlib.sha256(supplied[0].read_bytes()).hexdigest() != state["input_sha256"]:
                raise PrivateActionsError("The downloaded actual submitted input differs from this task.")
            verified_input = True
        state["results_directory"] = str(destination)
        state["downloaded_run_attempt"] = attempt
        state.setdefault("downloads", []).append({
            "run_id": state["run_id"], "run_attempt": attempt,
            "artifact_id": artifact["id"], "artifact_name": name,
            "directory": str(destination), "expected_input_sha256": state["input_sha256"],
            "submitted_input_bytes_verified": verified_input,
            "scientific_acceptance_established_by_download": False,
        })
        state["history"].append(
            {"event": "evidence_downloaded", "at": datetime.now(timezone.utc).isoformat(),
             "artifact_name": name}
        )
        self._save(state)
        return state

    def _cleanup(self, task_id: str) -> dict[str, Any]:
        from scripts.private_engine_assets import cleanup_staged_asset

        state = self._status(task_id)
        if state["run_id"] is None or state["status"] != "completed":
            raise PrivateActionsError("Private staged assets remain until the exact owned run is terminal.")
        self._receipt(state)
        cleanup_staged_asset(
            receipt_path=Path(state["receipt_path"]),
            receipt_sha256=state["receipt_sha256"], run_id=state["run_id"],
        )
        state["history"].append(
            {"event": "owned_staged_release_cleanup", "at": datetime.now(timezone.utc).isoformat()}
        )
        self._save(state)
        return state
