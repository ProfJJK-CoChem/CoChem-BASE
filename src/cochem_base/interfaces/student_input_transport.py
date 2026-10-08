"""Preserve larger scientific input data without editing student source code."""
from __future__ import annotations

import base64
import hashlib


def upload_scientific_inputs(client, intake: dict, *, request_id: str,
                             geometry_xyz: str, assignment_sha: str) -> dict:
    from .scientific_inputs import build_bundle
    if not isinstance(intake, dict) or not {"kind", "entrypoint", "files"}.issubset(intake):
        raise ValueError("Scientific inputs require their verified intake record")
    geometry_sha = hashlib.sha256(geometry_xyz.encode("utf-8")).hexdigest()
    contents, descriptor = build_bundle(intake["files"], kind=intake["kind"],
                                        entrypoint=intake["entrypoint"], request_id=request_id,
                                        geometry_sha256=geometry_sha)
    return upload_blob_bundle(client, contents, descriptor, request_id=request_id,
                              assignment_sha=assignment_sha, filename="scientific-inputs.zip",
                              schema_version="cochem.scientific-input-transport/1")


def upload_blob_bundle(client, contents: bytes, descriptor: dict, *, request_id: str,
                       assignment_sha: str, filename: str, schema_version: str) -> dict:
    if filename not in {"scientific-inputs.zip", "data-inputs.zip"}:
        raise ValueError("Select one reviewed data-only bundle name")
    path = f".cochem/submissions/{request_id}/{filename}"
    blob = client._request(f"/repos/{client.repository}/git/blobs", method="POST",
                           body={"encoding": "base64", "content": base64.b64encode(contents).decode("ascii")})
    expected_blob = hashlib.sha1(b"blob " + str(len(contents)).encode("ascii") + b"\0" + contents).hexdigest()
    if blob.get("sha") != expected_blob:
        raise ValueError("GitHub did not preserve the exact sealed scientific input bytes")
    parent = client._request(f"/repos/{client.repository}/git/commits/{assignment_sha}")
    tree = client._request(f"/repos/{client.repository}/git/trees", method="POST", body={
        "base_tree": parent["tree"]["sha"],
        "tree": [{"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]}]})
    commit = client._request(f"/repos/{client.repository}/git/commits", method="POST", body={
        "message": "CoChem scientific input data " + request_id, "tree": tree["sha"],
        "parents": [assignment_sha]})
    branch = ("cochem-input-" if filename == "scientific-inputs.zip" else "cochem-data-") + request_id
    client._request(f"/repos/{client.repository}/git/refs", method="POST", body={
        "ref": "refs/heads/" + branch, "sha": commit["sha"]})
    return {**descriptor, "schema_version": schema_version,
            "blob_sha": blob["sha"], "commit_sha": commit["sha"], "branch": branch, "path": path}
