"""Verify a private same-repository Actions artifact before mandatory-kit setup.

GitHub supplies transport identity; the reviewed BASE catalog independently owns
scientific code and kit trust. No archive is imported or executed here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

MAX_BYTES = 1024 * 1024 * 1024


class _Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        if parsed.scheme != "https":
            raise ValueError("Artifact redirect must use HTTPS")
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None and parsed.hostname != "api.github.com":
            redirected.remove_header("Authorization")
        return redirected


def _get(repository: str, suffix: str):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid current GitHub repository")
    token = os.environ.get("GH_TOKEN", "")
    if not token:
        raise ValueError("Same-repository Actions read token is required")
    request = urllib.request.Request(f"https://api.github.com/repos/{repository}/{suffix}", headers={
        "Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "CoChem-kit-transport"})
    return urllib.request.build_opener(_Redirect()).open(request, timeout=60)


def _json_api(repository: str, suffix: str) -> dict:
    with _get(repository, suffix) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError("GitHub metadata exceeds the bounded input limit")
    return json.loads(raw)


def identify(repository: str, run_id: str, name: str) -> dict:
    if not re.fullmatch(r"[1-9][0-9]{0,19}", run_id) or not name or len(name) > 255:
        raise ValueError("Explicit artifact run ID and name are required")
    run = _json_api(repository, f"actions/runs/{run_id}")
    if (run.get("id") != int(run_id) or run.get("status") != "completed"
            or run.get("conclusion") != "success"
            or run.get("repository", {}).get("private") is not True
            or run.get("repository", {}).get("full_name") != repository
            or run.get("head_repository", {}).get("full_name") != repository
            or not re.fullmatch(r"[a-f0-9]{40}", str(run.get("head_sha", "")))):
        raise ValueError("Kit requires a completed successful run from this private repository")
    matches = []
    for page in range(1, 101):
        document = _json_api(repository, f"actions/runs/{run_id}/artifacts?per_page=100&page={page}")
        values = document.get("artifacts", [])
        matches.extend(value for value in values if value.get("name") == name)
        if len(values) < 100:
            break
    else:
        raise ValueError("Artifact inventory exceeds the bounded selection limit")
    if len(matches) != 1:
        raise ValueError("Artifact selection must identify exactly one retained artifact")
    artifact = matches[0]
    digest = artifact.get("digest", "")
    if (artifact.get("expired") is not False or type(artifact.get("id")) is not int
            or not re.fullmatch(r"sha256:[a-f0-9]{64}", digest)
            or type(artifact.get("size_in_bytes")) is not int
            or not 0 < artifact["size_in_bytes"] <= MAX_BYTES
            or artifact.get("workflow_run", {}).get("id") != int(run_id)):
        raise ValueError("Artifact lacks current bounded SHA-256 transport identity")
    return {"schema_version": "cochem.hosted-kit-transport/1", "repository": repository,
            "run_id": int(run_id), "run_head_sha": run["head_sha"],
            "run_attempt": run.get("run_attempt"), "artifact_id": artifact["id"],
            "artifact_name": name, "archive_sha256": digest.removeprefix("sha256:"),
            "api_size_bytes": artifact["size_in_bytes"], "verified": False}


def verify_extracted_archive(archive: Path, extracted: Path, expected_sha256: str) -> dict:
    """Bind every extracted regular file to the actual API-hashed ZIP bytes."""
    with archive.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != expected_sha256:
            raise ValueError("Actual artifact archive SHA-256 differs from GitHub identity")
    root = extracted.resolve(strict=True)
    observed = {}
    total = 0
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            name = member.filename
            relative = PurePosixPath(name)
            if (not name or relative.is_absolute() or ".." in relative.parts or "\\" in name
                    or relative.as_posix() != name.rstrip("/") or stat.S_ISLNK(member.external_attr >> 16)):
                raise ValueError("Unsafe artifact member")
            target = root.joinpath(*relative.parts)
            cursor = root
            for component in relative.parts:
                cursor /= component
                if cursor.is_symlink():
                    raise ValueError("Extracted artifact contains a symbolic link")
            if member.is_dir():
                if not target.is_dir():
                    raise ValueError("Extracted artifact directory is missing")
                continue
            if name in observed:
                raise ValueError("Duplicate artifact member")
            total += member.file_size
            if total > MAX_BYTES or not target.is_file() or target.stat().st_size != member.file_size:
                raise ValueError("Extracted artifact is missing, changed or too large")
            with bundle.open(member) as raw, target.open("rb") as retained:
                expected = hashlib.file_digest(raw, "sha256").hexdigest()
                actual = hashlib.file_digest(retained, "sha256").hexdigest()
            if actual != expected:
                raise ValueError("Extracted artifact bytes differ from the verified archive")
            observed[name] = {"sha256": actual, "size_bytes": member.file_size}
    actual_files = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("Unexpected artifact symbolic link")
        if path.is_file():
            actual_files.add(path.relative_to(root).as_posix())
    if not observed or actual_files != set(observed):
        raise ValueError("Extracted artifact inventory differs from the verified archive")
    return observed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("identify", "verify"))
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--extracted", type=Path)
    args = parser.parse_args(argv)
    repository = os.environ["GITHUB_REPOSITORY"]
    if args.phase == "identify":
        receipt = identify(repository, os.environ["KIT_RUN_ID"], os.environ["KIT_ARTIFACT_NAME"])
    else:
        receipt = json.loads(args.receipt.read_text())
        if receipt != identify(repository, str(receipt["run_id"]), receipt["artifact_name"]):
            raise ValueError("Artifact identity changed after selection")
        if args.extracted is None:
            raise ValueError("Extraction directory is required")
        with tempfile.TemporaryDirectory(prefix="cochem-kit-verification-") as temporary:
            archive = Path(temporary) / "artifact.zip"
            with _get(repository, f"actions/artifacts/{receipt['artifact_id']}/zip") as response, archive.open("xb") as output:
                count = 0
                while chunk := response.read(1024 * 1024):
                    count += len(chunk)
                    if count > MAX_BYTES:
                        raise ValueError("Actual artifact archive exceeds the bounded limit")
                    output.write(chunk)
            receipt["files"] = verify_extracted_archive(archive, args.extracted, receipt["archive_sha256"])
            receipt["actual_archive_size_bytes"] = count
            receipt["verified"] = True
            receipt["scope"] = "Archive transport only; installed BASE must independently verify reviewed kit/catalog/source identities before setup"
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
