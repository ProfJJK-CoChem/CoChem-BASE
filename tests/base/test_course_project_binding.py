"""Actual JSON/Git/filesystem/loopback controls; no live App or chemistry proof."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from ci_tools import base_ci
from cochem_base.interfaces import course_access as access
from tests.base.test_course_project_access import (
    _blob_sha, config_for, peer, provision,
)


DEV = ".devcontainer/devcontainer.json"
RING = ".core_infrastructure_hashring.json"


def pair(peer, config):
    return access._project_codespaces_pair(
        access.GitHubAPI(api_url=peer.url, allow_loopback=True), config,
        _blob_sha(peer.devcontainer), _blob_sha(peer.infrastructure_ring), peer.project_repository)


def source(peer, config, *, migration=False):
    api = access.GitHubAPI(peer.controller_token, api_url=peer.url, allow_loopback=True)
    app = access.GitHubAPI(access.app_jwt(config.app_id, config.private_key), api_url=peer.url, allow_loopback=True)
    _, _, reader, project = access._project_context(config, access.EnrollmentRequest(peer.project_repository),
        author=peer.project_owner_login, controller_api=api, app_api=app)
    return access.verify_project_source(reader, access.GitHubAPI(api_url=peer.url, allow_loopback=True),
                                       config, project, allow_migration=migration)


def test_exact_pair_changes_only_project_map_and_one_ring_value(peer):
    generated = pair(peer, config_for(peer))
    document = json.loads(generated[DEV])
    original = json.loads(peer.devcontainer)
    assert document["customizations"]["codespaces"]["repositories"] == {
        peer.project_repository: {"permissions": {"actions": "write", "contents": "write"}}}
    document["customizations"]["codespaces"]["repositories"] = original["customizations"]["codespaces"]["repositories"]
    assert document == original
    ring = json.loads(generated[RING])
    assert ring["files"][DEV] == hashlib.sha256(generated[DEV]).hexdigest()
    ring["files"][DEV] = hashlib.sha256(peer.devcontainer).hexdigest()
    assert ring == json.loads(peer.infrastructure_ring)
    assert generated == pair(peer, config_for(peer))


@pytest.mark.parametrize("legacy", [False, True])
def test_migration_input_is_not_final_until_atomic_pair_readback(peer, legacy):
    config = config_for(peer)
    if legacy:
        peer.project_devcontainer = pair(peer, config)[DEV]
    before = source(peer, config, migration=True)
    assert before["source_state"] == ("legacy_migration" if legacy else "canonical_migration")
    with pytest.raises(access.CourseAccessError, match="starter"):
        source(peer, config)
    assert not peer.writes and not peer.controller_variables
    receipt = provision(peer, config)
    assert receipt["source_state"] == "paired" and source(peer, config)["source_state"] == "paired"
    assert len(peer.git_commits) == 1
    assert receipt["project_revision"] == peer.project_revision
    assert receipt["codespaces_binding_schema"] == "cochem.codespaces-project-binding/2"


@pytest.mark.parametrize("corruption", ["reverse", "wrong_project", "other_digest", "extra_entry", "formatting"])
def test_only_the_exact_paired_variant_is_final(peer, corruption):
    config = config_for(peer)
    generated = pair(peer, config)
    peer.project_devcontainer, peer.project_ring = generated[DEV], generated[RING]
    if corruption == "reverse":
        peer.project_devcontainer = peer.devcontainer
    elif corruption == "wrong_project":
        wrong = access._project_codespaces_pair(access.GitHubAPI(api_url=peer.url, allow_loopback=True),
            config, _blob_sha(peer.devcontainer), _blob_sha(peer.infrastructure_ring), "other/project")
        peer.project_devcontainer, peer.project_ring = wrong[DEV], wrong[RING]
    elif corruption == "formatting":
        peer.project_ring = json.dumps(json.loads(peer.project_ring)).encode() + b"\n"
    else:
        ring = json.loads(peer.project_ring)
        if corruption == "extra_entry":
            ring["files"]["scripts/not-approved.py"] = "a" * 64
        else:
            other = next(name for name in ring["files"] if name != DEV)
            ring["files"][other] = "a" * 64
        peer.project_ring = (json.dumps(ring, indent=2, sort_keys=True) + "\n").encode()
    with pytest.raises(access.CourseAccessError, match="starter"):
        source(peer, config, migration=True)
    assert not peer.writes and not peer.controller_variables


@pytest.mark.parametrize("corruption", ["schema", "digest", "missing_entry", "duplicate", "non_object"])
def test_invalid_approved_ring_refuses_before_project_mutation(peer, corruption):
    ring = json.loads(peer.infrastructure_ring)
    if corruption == "schema":
        ring["schema_version"] = True
    elif corruption == "digest":
        ring["files"][DEV] = "0" * 64
    elif corruption == "missing_entry":
        del ring["files"][DEV]
    if corruption == "duplicate":
        peer.infrastructure_ring = b'{"schema_version":1,"schema_version":1}'
    elif corruption == "non_object":
        peer.infrastructure_ring = b'[]'
    else:
        peer.infrastructure_ring = json.dumps(ring).encode()
    with pytest.raises(access.CourseAccessError, match="approved|ring"):
        pair(peer, config_for(peer))
    assert not peer.writes and not peer.controller_variables


@pytest.mark.parametrize("failure", ["blob2", "tree", "commit", "ref", "lost_ref_response"])
def test_partial_protocol_failure_never_stages_access(peer, failure):
    config = config_for(peer)
    before = peer.project_revision
    peer.binding_failure = failure
    with pytest.raises(access.CourseAccessError):
        provision(peer, config)
    assert not peer.controller_variables and not peer.secret_values and not peer.codespaces_values and not peer.variables
    assert all("/git/" in path for _, path in peer.writes)
    if failure == "lost_ref_response":
        assert peer.project_revision != before
        assert source(peer, config)["source_state"] == "paired"
        peer.binding_failure = ""
        receipt = provision(peer, config)
        assert receipt["status"] == "provisioned" and len(peer.git_commits) == 1
    else:
        assert peer.project_revision == before
        assert peer.project_devcontainer == peer.devcontainer and peer.project_ring == peer.infrastructure_ring


@pytest.mark.parametrize("corruption", ["wrong_id", "wrong_head", "missing_ring"])
def test_fresh_postcommit_identity_and_source_are_required_before_staging(peer, corruption):
    peer.binding_readback = corruption
    with pytest.raises(access.CourseAccessError, match="identity|source|starter"):
        provision(peer)
    assert peer.binding_committed and len(peer.git_commits) == 1
    assert not peer.controller_variables and not peer.secret_values and not peer.codespaces_values and not peer.variables
    assert all("/git/" in path for _, path in peer.writes)


def test_real_git_pair_preserves_student_files_and_passes_unchanged_ring(peer, tmp_path):
    """Use genuine committed approved files and real Git, not simulated object IDs."""
    approved = Path(__file__).resolve().parents[2]
    original_ring = base_ci._git(approved, ["show", "HEAD:" + RING])
    canonical = json.loads(original_ring)
    project = tmp_path / "personal-project"
    project.mkdir()
    base_ci._git(project, ["init", "--initial-branch=main"])
    for name in canonical["files"]:
        target = project / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(base_ci._git(approved, ["show", "HEAD:" + name]))
    (project / RING).write_bytes(original_ring)
    (project / "student-original.xyz").write_bytes(b"Retained original data, not a calculation result\n")
    base_ci._git(project, ["add", "."])
    commit = ["-c", "user.name=Local engineering control", "-c", "user.email=engineering@example.invalid",
              "commit", "-m"]
    base_ci._git(project, [*commit, "Approved template plus original student data"])
    before = base_ci._git(project, ["rev-parse", "HEAD"]).decode().strip()
    assert base_ci._verify_infrastructure_ring(project)["passed"]
    peer.devcontainer, peer.infrastructure_ring = (project / DEV).read_bytes(), original_ring
    generated = pair(peer, config_for(peer))
    (project / "student-unsaved.txt").write_bytes(b"Untracked original remains\n")
    (project / DEV).write_bytes(generated[DEV])
    with pytest.raises(base_ci.InfrastructureIntegrityError, match="ring"):
        base_ci._verify_infrastructure_ring(project)
    (project / RING).write_bytes(generated[RING])
    base_ci._git(project, ["add", "--", DEV, RING])
    base_ci._git(project, [*commit, "Exact paired personal project binding"])
    assert base_ci._verify_infrastructure_ring(project)["passed"]
    assert set(base_ci._git(project, ["diff", "--name-only", "HEAD^", "HEAD"]).decode().splitlines()) == {DEV, RING}
    assert base_ci._git(project, ["rev-parse", "HEAD^"]).decode().strip() == before
    assert (project / "student-original.xyz").read_bytes() == b"Retained original data, not a calculation result\n"
    assert (project / "student-unsaved.txt").read_bytes() == b"Untracked original remains\n"
    for name, content in generated.items():
        assert base_ci._git(project, ["rev-parse", "HEAD:" + name]).decode().strip() == _blob_sha(content)
    (tmp_path / "real-git-pair-evidence.json").write_text(json.dumps({
        "scope": "Local real Git/filesystem and unchanged strict ring check; not live GitHub/App acceptance",
        "template_parent": before, "paired_commit": base_ci._git(project, ["rev-parse", "HEAD"]).decode().strip(),
        "changed_paths": [DEV, RING], "file_sha256": {name: hashlib.sha256(raw).hexdigest()
                                                     for name, raw in generated.items()}}, indent=2) + "\n")
