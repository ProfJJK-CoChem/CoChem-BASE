"""Check licensed asset access without installing engines or claiming chemistry."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def probe_engine(engine: str) -> dict:
    if engine not in {"orca", "cfour"}:
        raise ValueError("Select the optional ORCA or CFOUR engine")
    if engine == "orca":
        from scripts.provision_orca import load_distribution_manifest
    else:
        from scripts.provision_cfour import load_distribution_manifest
    manifest_path = Path(__file__).resolve().parent / f"{engine}-distribution.json"
    distribution = load_distribution_manifest(manifest_path)
    token = os.environ.get(f"{engine.upper()}_ASSET_READ_TOKEN", "")
    result = {"engine": engine, "status": "unavailable", "provisionable": False,
              "installed": False, "scientific_execution_performed": False,
              "version": distribution[f"{engine}_version"], "archive_name": distribution["archive_name"],
              "expected_archive_sha256": distribution["sha256"],
              "distribution_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
              "verified_at": datetime.now(timezone.utc).isoformat()}
    if not token:
        return {**result, "reason": f"The instructor has not authorized this assignment for {engine.upper()} asset access."}
    location = ("https://api.github.com/repos/" + distribution["repository"]
                + "/releases/tags/" + urllib.parse.quote(distribution["release_tag"], safe=""))
    request = urllib.request.Request(location, headers={"Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "CoChem-BASE-optional-engine-readiness"})
    try:
        with urllib.request.build_opener(_NoRedirect()).open(request, timeout=30) as response:
            contents = response.read(4 * 1024 * 1024 + 1)
        if len(contents) > 4 * 1024 * 1024:
            raise ValueError("The approved release metadata exceeds its size limit")
        release = json.loads(contents)
        assets = [item for item in release.get("assets", []) if item.get("name") == distribution["archive_name"]]
        if release.get("draft") or release.get("prerelease") or len(assets) != 1:
            raise ValueError("The exact approved published archive is unavailable")
        asset = assets[0]
        if asset.get("state") != "uploaded" or type(asset.get("size")) is not int or asset["size"] <= 0:
            raise ValueError("The approved archive upload is incomplete")
        server_digest = asset.get("digest")
        if server_digest is not None and server_digest != "sha256:" + distribution["sha256"]:
            raise ValueError("GitHub's archive SHA-256 differs from the approved distribution")
        result.update(status="provisionable", provisionable=True, release_id=release["id"],
                      asset_id=asset["id"], archive_size_bytes=asset["size"], server_archive_digest=server_digest,
                      hash_verification="GitHub asset digest matched" if server_digest else "Approved SHA-256 will be verified on download",
                      reason="Approved archive access is available. Installation and native scientific acceptance occur in the calculation job.")
    except urllib.error.HTTPError as error:
        result["reason"] = f"The assignment's reader cannot access the approved {engine.upper()} archive (GitHub HTTP {error.code})."
    except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError):
        result["reason"] = "Approved archive metadata could not be verified. Retry the engine check or contact the instructor."
    return result


def probe_engines(engines: list[str]) -> dict:
    if not engines or len(engines) != len(set(engines)) or any(engine not in {"orca", "cfour"} for engine in engines):
        raise ValueError("Select each optional licensed engine at most once")
    return {"schema_version": "cochem.engine-readiness/1", "engines": {engine: probe_engine(engine) for engine in engines},
            "installed": False, "scientific_execution_performed": False}
