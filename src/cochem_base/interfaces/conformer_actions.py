"""Submit a student conformer workflow and retrieve its verified portable handoff."""

import base64
import hashlib
import io
import re
import zipfile
from urllib.parse import quote

from student.handoff import frames, verify_contents
from .student_actions import CANONICAL_BASE, StudentActionsClient, StudentActionsError

WORKFLOW = "student_conformers.yml"
MAX_ZIP = 32 * 1024**2
FILE = re.compile(r"[A-Za-z0-9_-]{1,64}\.xyz")


def input_geometry(data):
    if len(data) > 8192:
        raise ValueError("Choose one XYZ file smaller than 8 KiB.")
    if len(frames(data.decode("ascii"))) != 1:
        raise ValueError("Choose a file containing exactly one starting structure.")


def unpack_handoff(blob, artifact, run, repository, expected=None):
    """Verify GitHub's ZIP digest, the two named files and scientific provenance."""
    if artifact.get("digest") != "sha256:" + hashlib.sha256(blob).hexdigest():
        raise ValueError(
            "The download differs from GitHub's checksum. Refresh the run and try again."
        )
    with zipfile.ZipFile(io.BytesIO(blob)) as outer:
        items = outer.infolist()
        if len(items) != 2 or sum(i.file_size for i in items) > MAX_ZIP + 256:
            raise ValueError("The download must contain one result ZIP and one checksum.")
        zips = [
            i.filename
            for i in items
            if re.fullmatch(r"CoChem-[A-Za-z0-9_-]+-\d+-\d+\.zip", i.filename)
        ]
        if len(zips) != 1 or zips[0] + ".sha256" not in outer.namelist():
            raise ValueError("The names of the downloaded files do not match the CoChem handoff.")
        name = zips[0]
        result = outer.read(name)
        sidecar = outer.read(name + ".sha256")
    digest = hashlib.sha256(result).hexdigest()
    if sidecar.decode("ascii").split() != [digest, name] or len(result) > MAX_ZIP:
        raise ValueError("The result ZIP and checksum disagree. Download the original run again.")
    with zipfile.ZipFile(io.BytesIO(result)) as inner:
        receipt = verify_contents(inner, None, digest)
    if (
        receipt["repository"].lower() != repository.lower()
        or receipt["commit"] != run["head_sha"]
        or receipt["run_id"] != str(run["id"])
        or receipt["attempt"] != str(run["run_attempt"])
        or not FILE.fullmatch(receipt["input_name"])
        or name != f"CoChem-{receipt['input_name'][:-4]}-{run['id']}-{run['run_attempt']}.zip"
    ):
        raise ValueError("This bundle belongs to a different project, run or input.")
    if expected and (
        receipt["files_sha256"]["input.xyz"] != expected["input_sha256"]
        or receipt["input_name"] != expected["input_name"]
    ):
        raise ValueError(
            "The calculation used a different starting file. Check the original run before submitting."
        )
    return name, result, sidecar, receipt


class ConformerActions(StudentActionsClient):
    def _course_project(self):
        project = self._request("/repos/" + self.repository)
        if (
            project.get("private") is not False
            or project.get("fork") is not True
            or project.get("source", {}).get("full_name", "").lower() != CANONICAL_BASE.lower()
        ):
            raise ValueError(
                "Enter your public fork of CoChem-BASE. Use the copy under your own GitHub account."
            )
        return project

    def submit_conformer(self, upload=None):
        base = "/repos/" + self.repository
        project = self._course_project()
        if not project.get("permissions", {}).get("push"):
            raise ValueError(
                "This GitHub account needs write access to the fork. Check the account and project name."
            )
        branch = project["default_branch"]
        flow = self._request(f"{base}/actions/workflows/{WORKFLOW}")
        if flow.get("state") != "active":
            raise ValueError("Open Actions in your fork and enable workflows. Then return here.")
        name = "ethanol.xyz"
        if upload is not None:
            input_geometry(upload)
            name = "molecule-" + hashlib.sha256(upload).hexdigest()[:20] + ".xyz"
        path = f"{base}/contents/examples/student_inputs/{name}"
        try:
            remote = self._request(path + "?ref=" + quote(branch, safe=""))
        except StudentActionsError as error:
            if error.http_status != 404 or upload is None:
                raise
            try:
                self._request(
                    path,
                    method="PUT",
                    body={
                        "message": "Add a student-approved XYZ starting structure",
                        "branch": branch,
                        "content": base64.b64encode(upload).decode("ascii"),
                    },
                )
            except StudentActionsError as conflict:
                if conflict.http_status not in (409, 422):
                    raise
            remote = self._request(path + "?ref=" + quote(branch, safe=""))
        if (
            remote.get("type") != "file"
            or remote.get("encoding") != "base64"
            or remote.get("size", 8193) > 8192
        ):
            raise ValueError("The fork must contain a small, regular XYZ file.")
        data = base64.b64decode(remote["content"])
        input_geometry(data)
        if upload is not None and data != upload:
            raise ValueError(
                "A different file already has the same name. No calculation was submitted."
            )
        response = self._request(
            f"{base}/actions/workflows/{WORKFLOW}/dispatches",
            method="POST",
            body={"ref": branch, "inputs": {"xyz": name}},
            api_version="2026-03-10",
        )
        run_id = response.get("workflow_run_id")
        if type(run_id) is not int or run_id <= 0:
            raise StudentActionsError(
                "GitHub did not return a run number. Open Actions and recover the run link before submitting again.",
                uncertain=True,
            )
        return {
            "repository": self.repository,
            "id": run_id,
            "input_name": name,
            "input_sha256": hashlib.sha256(data).hexdigest(),
        }

    def read_run(self, run_id, expected=None):
        if type(run_id) is not int or run_id <= 0:
            raise ValueError("Paste the GitHub link for one completed calculation.")
        self._course_project()
        base = "/repos/" + self.repository
        run = self._request(f"{base}/actions/runs/{run_id}")
        if (
            run.get("id") != run_id
            or run.get("repository", {}).get("full_name", "").lower() != self.repository.lower()
            or run.get("path") != ".github/workflows/" + WORKFLOW
        ):
            raise ValueError(
                "This is a different workflow. Open Student conformers in the selected fork."
            )
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            return run, None
        wanted = f"CoChem-student-handoff-{run_id}-{run['run_attempt']}"
        inventory = self._request(f"{base}/actions/runs/{run_id}/artifacts?name={wanted}")
        matches = [a for a in inventory["artifacts"] if a["name"] == wanted and not a["expired"]]
        if len(matches) != 1:
            raise ValueError(
                "The original results are unavailable or expired. Check the instructor Drive folder for your saved ZIP and checksum."
            )
        artifact = matches[0]
        if artifact["size_in_bytes"] > MAX_ZIP + 65536:
            raise ValueError("This artifact exceeds the teaching download limit.")
        blob = self._request(
            f"{base}/actions/artifacts/{artifact['id']}/zip",
            binary=True,
            maximum_bytes=MAX_ZIP + 65536,
        )
        return run, unpack_handoff(blob, artifact, run, self.repository, expected)
