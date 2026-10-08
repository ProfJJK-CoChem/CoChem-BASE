"""Codespaces interface for calculation jobs in the student's private project.

Every remote operation uses the already authorized GitHub CLI identity. Licensed
assets are staged privately by the shared asset module; calculations execute in
the owning repository's Actions runner. No tokens are read or displayed.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
REPO_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9._-]*")
TASK_PATTERN = re.compile(r"[0-9a-f]{32}")
SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
WORKFLOWS = {
    "orca": ".github/workflows/orca_calculation.yml",
    "cfour": ".github/workflows/cfour_provisioning.yml",
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
    try:
        result = subprocess.run(
            command,
            input=_canonical(document) if document is not None else None,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PrivateActionsError("The authorized GitHub CLI operation could not complete.") from exc
    if result.returncode:
        raise PrivateActionsError(
            "GitHub refused the project operation. Review Codespaces repository permissions."
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
    task = receipt["task_id"]
    project = receipt["project"]
    own = run.get("repository")
    return bool(
        isinstance(title, str)
        and TASK_PATTERN.fullmatch(task) is not None
        and task in re.findall(r"(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])", title)
        and run.get("event") == "workflow_dispatch"
        and run.get("head_sha") == project["source_sha"]
        and run.get("path", "").split("@", 1)[0] == project["workflow_path"]
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
        if state.get("task_id") != task_id or state.get("repository") != self.repository:
            raise PrivateActionsError("The lifecycle record belongs to another task/project.")
        return state

    def _receipt(self, state: dict[str, Any]) -> dict[str, Any]:
        from scripts.private_engine_assets import load_staging_receipt

        project = self.project()
        receipt_path = Path(state["receipt_path"])
        if receipt_path.is_symlink() or not receipt_path.is_file():
            raise PrivateActionsError("The original private staging receipt is unavailable.")
        receipt = load_staging_receipt(receipt_path.read_bytes(), state["receipt_sha256"])
        if (
            receipt["task_id"] != state["task_id"]
            or receipt["destination"]["repository"] != project.repository
            or receipt["destination"]["repository_id"] != project.repository_id
            or receipt["destination"]["owner_id"] != project.owner_id
        ):
            raise PrivateActionsError("Task staging does not belong to the current personal project.")
        return receipt

    def stage_and_dispatch_orca(
        self, payload: bytes, descriptor: Path, descriptor_sha256: str, *,
        ref: str, cores: int, maxcore_mb: int,
    ) -> dict[str, Any]:
        """Upload a unique validated job, stage privately, and request actual Actions."""
        from cochem_base.interfaces.actions_jobs import (
            decode_configuration,
            validate_configuration,
            validate_resources,
        )
        from scripts.private_engine_assets import stage_asset

        project = self.project()
        ref = validate_ref(ref)
        validate_resources(cores, maxcore_mb)
        configuration = decode_configuration(payload)
        validate_configuration(payload, configuration)
        workflow = WORKFLOWS["orca"]
        _gh("repos/" + project.repository + "/contents/" + workflow + "?ref=" + ref)
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
        receipt = stage_asset(
            engine="orca", descriptor=descriptor, descriptor_sha256=descriptor_sha256,
            repository=project.repository, ref=ref, source_sha=source_sha,
            workflow_path=workflow, receipt_path=receipt_path, expires_hours=24,
        )
        encoded = _canonical(receipt)
        state = {
            "schema_version": "cochem.private-actions-lifecycle/1",
            "task_id": receipt["task_id"], "repository": project.repository,
            "receipt_path": str(receipt_path),
            "receipt_sha256": hashlib.sha256(encoded).hexdigest(),
            "job_file": job_file, "input_sha256": hashlib.sha256(payload).hexdigest(),
            "source_sha": source_sha, "workflow_path": workflow,
            "ref": ref, "submitted_at": datetime.now(timezone.utc).isoformat(),
            "run_id": None, "status": "staged_not_dispatched", "history": [],
        }
        self._save(state)
        _gh(
            "repos/" + project.repository + "/actions/workflows/orca_calculation.yml/dispatches",
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

    def status(self, task_id: str) -> dict[str, Any]:
        state = self.load(task_id)
        receipt = self._receipt(state)
        if state["run_id"] is None:
            result = _gh(
                "repos/" + self.repository +
                "/actions/workflows/orca_calculation.yml/runs?event=workflow_dispatch&per_page=100"
            )
            runs = [
                run for run in result["workflow_runs"]
                if run_belongs_to_task(run, receipt, self.repository)
                and run.get("created_at", "") >= state["submitted_at"].split(".", 1)[0]
            ]
            if len(runs) > 1:
                raise PrivateActionsError("More than one actual run matches this task; select it explicitly.")
            if not runs:
                return state
            state["run_id"] = runs[0]["id"]
        run = _gh("repos/" + self.repository + "/actions/runs/" + str(state["run_id"]))
        if not run_belongs_to_task(run, receipt, self.repository):
            raise PrivateActionsError("The actual Actions run differs from its task/source/project.")
        state.update(
            status=run["status"], conclusion=run.get("conclusion"),
            run_attempt=run["run_attempt"], run_url=run["html_url"],
        )
        state["history"].append(
            {"event": "observed_run", "at": datetime.now(timezone.utc).isoformat(),
             "status": run["status"], "conclusion": run.get("conclusion")}
        )
        self._save(state)
        return state

    def cancel(self, task_id: str) -> dict[str, Any]:
        state = self.status(task_id)
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

    def download(self, task_id: str) -> dict[str, Any]:
        state = self.status(task_id)
        if state["run_id"] is None or state["status"] != "completed":
            raise PrivateActionsError("Wait for the observed owned run to complete before downloading.")
        destination = self.runtime / (task_id + "-results")
        if destination.exists():
            raise PrivateActionsError("A result download must not overwrite existing evidence.")
        name = f"orca-calculation-{state['run_id']}-{state['run_attempt']}"
        result = subprocess.run(
            ["gh", "run", "download", str(state["run_id"]), "--repo", self.repository,
             "--name", name, "--dir", str(destination)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=60,
        )
        if result.returncode or not destination.is_dir() or not any(destination.rglob("*")):
            raise PrivateActionsError("GitHub returned no completed calculation evidence artifact.")
        state["results_directory"] = str(destination)
        state["history"].append(
            {"event": "evidence_downloaded", "at": datetime.now(timezone.utc).isoformat(),
             "artifact_name": name}
        )
        self._save(state)
        return state

    def cleanup(self, task_id: str) -> dict[str, Any]:
        from scripts.private_engine_assets import cleanup_staging

        state = self.status(task_id)
        if state["run_id"] is None or state["status"] != "completed":
            raise PrivateActionsError("Private staged assets remain until the exact owned run is terminal.")
        receipt = self._receipt(state)
        cleanup_staging(receipt, run_id=state["run_id"])
        state["history"].append(
            {"event": "owned_staged_release_cleanup", "at": datetime.now(timezone.utc).isoformat()}
        )
        self._save(state)
        return state
