"""Student-owned TOPOS Actions with a reviewed kit and separate engine receipts.

The scientific request is committed before staging. Staging receipts are separate
workflow controls, so they cannot create a request/receipt checksum cycle. Kit and
licensed distributions are read back through the real owning GitHub account.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import subprocess
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from .private_actions import PrivateActionsController, PrivateActionsError, _canonical, _gh

SCHEMA = "cochem.private-topos-staging/1"
WORKFLOW = ".github/workflows/topos_calculation.yml"
MAX_KIT_BYTES = 1024 * 1024 * 1024
MAX_BUNDLE_BYTES = 60000
_PROBE = """import json,sys
from topos.models import RunRequest
from topos.actions.hosted_requirements import required_calculation_engines
def unique(pairs):
    result = {}
    for key,value in pairs:
        if key in result:
            raise ValueError('Duplicate request key')
        result[key] = value
    return result
original = json.loads(sys.stdin.buffer.read(),object_pairs_hook=unique)
request = RunRequest.model_validate(original)
canonical = lambda value: json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
if canonical(original) != canonical(request.model_dump(mode='json')):
    raise ValueError('Export the complete typed request including all declared defaults')
if request.calculation_environment != 'local' or request.device != 'cpu':
    raise ValueError('Select local execution on the assigned CPU Actions runner')
engines = required_calculation_engines(request.model_dump(mode='json'))
if not engines <= {'xtb','crest','orca','cfour'}:
    raise ValueError('This runner does not provision the requested native engine/model allocation')
parsers = {}
if 'cfour' in engines:
    from topos.cfour_dependencies import require_cfour_parsers,PARSER_VERSIONS
    require_cfour_parsers()
    parsers = PARSER_VERSIONS
print(json.dumps({'request':request.model_dump(mode='json'),'native_engines':sorted(engines),'cfour_parser_versions':parsers}))
"""


def _digest(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value) or value == "0" * 64:
        raise ValueError("A genuine nonzero SHA-256 is required")
    return value


def load_bundle(raw: bytes, expected: str, *, allow_expired: bool = False) -> dict[str, Any]:
    from scripts.private_engine_assets import load_staging_receipt
    from scripts.private_topos_job import validate_intent

    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_BUNDLE_BYTES or hashlib.sha256(raw).hexdigest() != _digest(expected):
        raise ValueError("TOPOS staging bundle differs from its exact bounded byte identity")
    from scripts.private_engine_assets import _json
    bundle = _json(raw)
    if (not isinstance(bundle, dict) or set(bundle) != {
        "schema_version", "task_id", "repository", "repository_id", "owner_id", "ref", "source_sha",
        "intent", "kit", "engines", "required_engines", "created_at", "expires_at"
    } or bundle.get("schema_version") != SCHEMA):
        raise ValueError("An exact TOPOS kit/engine staging bundle is required")
    if (not isinstance(bundle["task_id"], str) or not re.fullmatch(r"[0-9a-f]{32}", bundle["task_id"])
            or bundle["task_id"] == "0" * 32):
        raise ValueError("The TOPOS dispatch task must be an actual task UUID")
    from .private_actions import REPO_PATTERN, validate_ref
    if (not isinstance(bundle["repository"], str) or not REPO_PATTERN.fullmatch(bundle["repository"])
            or type(bundle["repository_id"]) is not int or bundle["repository_id"] < 1
            or type(bundle["owner_id"]) is not int or bundle["owner_id"] < 1
            or not isinstance(bundle["source_sha"], str)
            or not re.fullmatch(r"[0-9a-f]{40}", bundle["source_sha"]) or bundle["source_sha"] == "0" * 40):
        raise ValueError("The private project needs its exact provider/source identity")
    validate_ref(bundle["ref"])
    intent = validate_intent(bundle["intent"])
    kit = bundle["kit"]
    if (not isinstance(kit, dict) or set(kit) != {"release_tag", "release_id", "asset_id", "asset_name", "sha256", "size_bytes"}
            or kit["release_tag"] != "cochem-topos-kit-" + bundle["task_id"]
            or kit["asset_name"] != "mandatory-kit.zip" or kit["sha256"] != intent["kit_sha256"]
            or any(type(kit[key]) is not int or kit[key] < 1 for key in ("release_id", "asset_id", "size_bytes"))
            or kit["size_bytes"] > MAX_KIT_BYTES):
        raise ValueError("The staged mandatory kit has an ambiguous identity")
    required = bundle["required_engines"]
    if (not isinstance(required, list) or any(not isinstance(engine, str) for engine in required)
            or required != sorted(set(required))
            or not set(required) <= {"xtb", "crest", "orca", "cfour"}
            or not isinstance(bundle["engines"], dict)
            or set(bundle["engines"]) != set(required) & {"orca", "cfour"}):
        raise ValueError("The exact zero, one or two licensed engine receipts are required")
    for engine, item in bundle["engines"].items():
        if not isinstance(item, dict) or set(item) != {"receipt", "sha256", "task_id"}:
            raise ValueError("Each engine must retain its original receipt/task/checksum")
        receipt = load_staging_receipt(_canonical(item["receipt"]), item["sha256"], allow_expired=allow_expired)
        target, project = receipt["destination"], receipt["project"]
        if (receipt["engine"] != engine or receipt["task_id"] != item["task_id"]
                or target["repository"] != bundle["repository"] or target["repository_id"] != bundle["repository_id"]
                or target["owner_id"] != bundle["owner_id"] or project["ref"] != bundle["ref"]
                or project["source_sha"] != bundle["source_sha"] or project["workflow_path"] != WORKFLOW
                or project["calculation"] != intent):
            raise ValueError("Engine staging differs from the same exact TOPOS request/source/kit")
    tasks = [item["task_id"] for item in bundle["engines"].values()]
    if len(set(tasks)) != len(tasks) or bundle["task_id"] in tasks:
        raise ValueError("Each separate engine and TOPOS dispatch must retain a distinct task identity")
    if any(not isinstance(bundle[key], str) for key in ("created_at", "expires_at")):
        raise ValueError("Staging timestamps must be explicit timezone-aware strings")
    created = datetime.fromisoformat(bundle["created_at"])
    expires = datetime.fromisoformat(bundle["expires_at"])
    now = datetime.now(timezone.utc)
    if (created.tzinfo is None or expires.tzinfo is None or created > now
            or not timedelta(0) < expires - created <= timedelta(hours=24)
            or not allow_expired and expires <= now):
        raise ValueError("The TOPOS staging lifetime must be genuine and at most 24 hours")
    if _canonical(bundle) != raw:
        raise ValueError("The TOPOS bundle must use its exact canonical representation")
    return bundle


def pack_reviewed_kit(kit: Path, spec: dict, output: Path) -> dict:
    from scripts.mandatory_ecosystem import inspect_kit, verify_kit_checksums
    from scripts.private_engine_assets import _private_output

    output = _private_output(output)
    inspected = inspect_kit(kit, spec)
    inventory = verify_kit_checksums(kit)
    sums = (kit / "SHA256SUMS").read_bytes()
    if output.exists() or output.is_symlink():
        raise ValueError("Kit packaging must retain a new external archive")
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted([*inventory, "SHA256SUMS"]):
            source = kit / name
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            raw = source.read_bytes()
            expected = hashlib.sha256(sums).hexdigest() if name == "SHA256SUMS" else inventory[name]
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError("Reviewed kit bytes changed before their exact archive snapshot")
            archive.writestr(info, raw)
    if verify_kit_checksums(kit) != inventory:
        raise ValueError("Reviewed kit changed while being packaged")
    size = output.stat().st_size
    if not 0 < size <= MAX_KIT_BYTES:
        raise ValueError("The complete kit exceeds its bounded transport allocation")
    return {"source_pins": inspected["pins"], "sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "size_bytes": size}


def kit_marker(bundle: dict, *, closing: bool = False) -> str:
    value = {"schema_version": SCHEMA, "task_id": bundle["task_id"],
        "repository_id": bundle["repository_id"], "owner_id": bundle["owner_id"],
        "source_sha": bundle["source_sha"], "intent": bundle["intent"],
        "required_engines": bundle["required_engines"],
        "expires_at": bundle["expires_at"]}
    if closing:
        value["lifecycle"] = "closing"
    return _canonical(value).decode("utf-8")


def verify_kit_release(bundle: dict, *, allow_closing: bool = False) -> dict:
    from scripts.private_engine_assets import _api, _asset_identity, _personal_private

    project = _personal_private(bundle["repository"], owner=False)
    if project["id"] != bundle["repository_id"] or project["owner"]["id"] != bundle["owner_id"]:
        raise PrivateActionsError("The actual private project differs from the staged kit")
    kit = bundle["kit"]
    release = _api(f"repos/{bundle['repository']}/releases/{kit['release_id']}")
    if (release.get("id") != kit["release_id"] or release.get("tag_name") != kit["release_tag"]
            or release.get("target_commitish") != bundle["source_sha"] or release.get("draft") is not True
            or release.get("prerelease") is not False
            or release.get("body") not in ({kit_marker(bundle), kit_marker(bundle, closing=True)} if allow_closing else {kit_marker(bundle)})
            or len(release.get("assets", [])) != 1):
        raise PrivateActionsError("The private kit release differs from its exact task ownership marker")
    _asset_identity(release["assets"][0], kit)
    return release


class PrivateToposActionsController(PrivateActionsController):
    def stage_and_dispatch_topos(self, payload: bytes, kit: Path, modules: Path, descriptors: dict[str, tuple[Path, str]],
                                 *, ref: str, receiver_timeout: float) -> dict:
        with self._locked():
            return self._stage_topos(payload, kit, modules, descriptors, ref=ref, receiver_timeout=receiver_timeout)

    def _stage_topos(self, payload, kit, modules, descriptors, *, ref, receiver_timeout):
        from scripts import manage_modules as manager
        from scripts.mandatory_ecosystem import _setup_environment
        from scripts.private_engine_assets import (
            _asset_identity,
            _distribution,
            _download,
            _file_sha,
            _json,
            _safe_path,
            _upload,
            load_staging_receipt,
            stage_private_asset,
        )
        from scripts.private_topos_job import validate_intent

        from .private_actions import validate_ref

        if not isinstance(payload, bytes) or not 0 < len(payload) <= 256 * 1024:
            raise ValueError("Select a bounded canonical TOPOS request")
        ref = validate_ref(ref)
        spec = manager.load_manifest()["modules"]["topos"]
        installed = manager.verify_installation("topos", spec, modules)
        validated = subprocess.run([installed["python_path"], "-I", "-B", "-c", _PROBE], input=payload,
            cwd=self.runtime, env=_setup_environment(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=False)
        if validated.returncode:
            raise PrivateActionsError("The installed TOPOS provider rejected the request or its hosted engine/resource route")
        selected = json.loads(validated.stdout)
        request, required = selected["request"], selected["native_engines"]
        licensed = set(required) & {"orca", "cfour"}
        if set(descriptors) != licensed:
            raise ValueError("Provide the exact reviewed descriptor/checksum for each required licensed engine")
        for engine, (descriptor, descriptor_sha) in descriptors.items():
            path = _safe_path(descriptor)
            if not path.is_file() or not 0 < path.stat().st_size <= 1024 * 1024:
                raise ValueError("Select the actual bounded reviewed engine descriptor")
            raw_descriptor = path.read_bytes()
            if hashlib.sha256(raw_descriptor).hexdigest() != _digest(descriptor_sha):
                raise ValueError("The engine descriptor differs from its independently retained checksum")
            _distribution(engine, _json(raw_descriptor))
        task = uuid.uuid4().hex
        state = {"task_id": task, "engine": "topos", "repository": self.repository,
                 "input_sha256": hashlib.sha256(payload).hexdigest(), "run_id": None,
                 "status": "preparing", "history": [], "engine_staging": {}}
        self.last_task_id = task
        self._save(state)
        archive = self.runtime / (task + "-mandatory-kit.zip")
        packaged = pack_reviewed_kit(kit, spec, archive)
        if packaged["source_pins"] != installed["source_pins"]:
            raise ValueError("The provided kit differs from the verified installed mandatory source pins")
        job_file = "jobs/topos-" + task + ".json"
        intent = validate_intent({"kind": "topos/1", "job_file": job_file,
            "input_sha256": state["input_sha256"], "cores": request["threads"],
            "maxcore_mb": math.ceil(request["memory_mb"] / request["threads"]),
            "memory_mb": request["memory_mb"], "budget_seconds": request["budget_seconds"],
            "receiver_timeout": receiver_timeout, "source_pins": packaged["source_pins"], "kit_sha256": packaged["sha256"]})
        project = self.project()
        _gh("repos/" + self.repository + "/contents/" + WORKFLOW + "?" + urlencode({"ref": ref}))
        uploaded = _gh("repos/" + self.repository + "/contents/" + job_file, method="PUT", document={
            "message": "Add canonical TOPOS calculation request", "content": base64.b64encode(payload).decode("ascii"),
            "branch": ref.removeprefix("refs/heads/")})
        source = uploaded.get("commit", {}).get("sha", "")
        if not re.fullmatch(r"[0-9a-f]{40}", source):
            raise PrivateActionsError("GitHub did not return the exact committed TOPOS request source")
        now = datetime.now(timezone.utc).replace(microsecond=0)
        bundle = {"schema_version": SCHEMA, "task_id": task, "repository": self.repository,
            "repository_id": project.repository_id, "owner_id": project.owner_id, "ref": ref, "source_sha": source,
            "intent": intent, "kit": {"release_tag": "cochem-topos-kit-" + task,
                "asset_name": "mandatory-kit.zip", "sha256": packaged["sha256"], "size_bytes": packaged["size_bytes"]},
            "engines": {}, "required_engines": required, "created_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=24)).isoformat()}
        state["bundle"] = bundle
        state["submitted_at"] = now.isoformat()
        self._save(state)
        release = _gh(f"repos/{self.repository}/releases", method="POST", document={
            "tag_name": bundle["kit"]["release_tag"], "target_commitish": source,
            "name": "Private mandatory TOPOS kit " + task, "body": kit_marker(bundle), "draft": True, "prerelease": False})
        if type(release.get("id")) is not int or release["id"] < 1:
            raise PrivateActionsError("GitHub returned no actual private kit release ID")
        bundle["kit"]["release_id"] = release["id"]
        self._save(state)
        asset = _upload(self.repository, release["id"], "mandatory-kit.zip", archive)
        bundle["kit"]["asset_id"] = asset["id"]
        _asset_identity(asset, bundle["kit"])
        verify_kit_release(bundle)
        readback = self.runtime / (task + "-kit-readback.zip")
        _download(self.repository, bundle["kit"], readback)
        if _file_sha(readback) != _file_sha(archive):
            raise PrivateActionsError("The privately staged kit readback differs from reviewed bytes")
        self._save(state)
        for engine in sorted(licensed):
            descriptor, descriptor_sha = descriptors[engine]
            path = self.runtime / (task + "-" + engine + "-receipt.json")
            state["engine_staging"][engine] = {"receipt_path": str(path)}
            self._save(state)
            staged = stage_private_asset(engine=engine, descriptor=descriptor, descriptor_sha256=descriptor_sha,
                repository=self.repository, ref=ref, source_sha=source, workflow_path=WORKFLOW,
                receipt=path, expires_hours=24, calculation=intent)
            receipt = load_staging_receipt(path.read_bytes(), staged["receipt_sha256"])
            bundle["engines"][engine] = {"receipt": receipt, "sha256": staged["receipt_sha256"], "task_id": staged["task_id"]}
            state["engine_staging"][engine].update(receipt_sha256=staged["receipt_sha256"])
            self._save(state)
        raw = _canonical(bundle)
        digest = hashlib.sha256(raw).hexdigest()
        load_bundle(raw, digest)
        bundle_path = self.runtime / (task + "-topos-bundle.json")
        bundle_path.write_bytes(raw)
        bundle_path.chmod(0o600)
        state.update(receipt_path=str(bundle_path), receipt_sha256=digest, status="staged_pending_dispatch")
        self._save(state)
        current = _gh("repos/" + self.repository + "/git/ref/" + ref.removeprefix("refs/"))
        if current.get("object", {}).get("sha") != source:
            raise PrivateActionsError("The project branch changed after TOPOS staging; retain the private repair journal")
        title_tasks = " ".join(item["task_id"] for item in bundle["engines"].values())
        _gh(f"repos/{self.repository}/actions/workflows/topos_calculation.yml/dispatches", method="POST", document={
            "ref": ref, "inputs": {"dispatch_id": task, "job_file": job_file, "request_sha256": intent["input_sha256"],
                "staging_bundle": raw.decode("utf-8"), "staging_bundle_sha256": digest, "engine_task_ids": title_tasks}})
        state.update(status="dispatched_pending_observed_run")
        state["history"].append({"event": "dispatch_accepted", "at": now.isoformat()})
        self._save(state)
        return state

    def _receipt(self, state: dict) -> dict:
        project = self.project()
        path = Path(state["receipt_path"])
        if path.is_symlink() or not path.is_file():
            raise PrivateActionsError("The original TOPOS bundle is unavailable")
        bundle = load_bundle(path.read_bytes(), state["receipt_sha256"], allow_expired=True)
        if (bundle["task_id"] != state["task_id"] or bundle["repository"] != self.repository
                or bundle["repository_id"] != project.repository_id or bundle["owner_id"] != project.owner_id):
            raise PrivateActionsError("TOPOS staging belongs to a different real project/task")
        return {"schema_version": SCHEMA, "task_id": bundle["task_id"],
            "destination": {"repository": self.repository, "repository_id": project.repository_id, "owner_id": project.owner_id},
            "project": {"source_sha": bundle["source_sha"], "ref": bundle["ref"], "workflow_path": WORKFLOW},
            "bundle": bundle}

    def _cleanup(self, task_id: str) -> dict:
        from scripts.private_engine_assets import _audit_no_active_runs, cleanup_staged_asset
        state = self._status(task_id)
        if state["run_id"] is None or state["status"] != "completed":
            raise PrivateActionsError("Retain the TOPOS kit/engines until the exact owned run is terminal")
        identity = self._receipt(state)
        bundle = identity["bundle"]
        if state.get("kit_cleaned"):
            return state
        _audit_no_active_runs(identity)
        release = verify_kit_release(bundle, allow_closing=True)
        if release["body"] != kit_marker(bundle, closing=True):
            _gh(f"repos/{self.repository}/releases/{bundle['kit']['release_id']}", method="PATCH",
                document={"body": kit_marker(bundle, closing=True)})
        if verify_kit_release(bundle, allow_closing=True)["body"] != kit_marker(bundle, closing=True):
            raise PrivateActionsError("The actual kit admission marker did not close")
        state["kit_admission_closed"] = True
        self._save(state)
        _audit_no_active_runs(identity)
        for item in state["engine_staging"].values():
            if item.get("cleaned"):
                continue
            cleanup_staged_asset(receipt_path=Path(item["receipt_path"]),
                                 receipt_sha256=item["receipt_sha256"], run_id=state["run_id"])
            item["cleaned"] = True
            self._save(state)
        _audit_no_active_runs(identity)
        verify_kit_release(bundle, allow_closing=True)
        _gh(f"repos/{self.repository}/releases/{bundle['kit']['release_id']}", method="DELETE")
        state["kit_cleaned"] = True
        state["history"].append({"event": "owned_topos_kit_engine_cleanup", "at": datetime.now(timezone.utc).isoformat()})
        self._save(state)
        return state

    def repair(self, task_id: str) -> dict:
        from scripts.private_engine_assets import (
            _asset_identity,
            _download,
            _provider_inventory,
            load_staging_receipt,
            repair_staging,
        )
        with self._locked():
            state = self.load(task_id)
            project = self.project()
            bundle = state.get("bundle")
            if not bundle:
                state["kit_repair_observation"] = "No private kit was staged; retain the original preparation failure"
                self._save(state)
                return state
            if bundle["repository_id"] != project.repository_id or bundle["owner_id"] != project.owner_id:
                raise PrivateActionsError("The retained TOPOS intent belongs to a different project identity")
            if state.get("kit_cleaned"):
                return state
            matches = [release for release in _provider_inventory(f"repos/{self.repository}/releases")
                if release.get("tag_name") == bundle["kit"]["release_tag"]]
            if (len(matches) != 1 or matches[0].get("target_commitish") != bundle["source_sha"]
                    or matches[0].get("draft") is not True or matches[0].get("prerelease") is not False
                    or matches[0].get("body") not in {kit_marker(bundle), kit_marker(bundle, closing=True)}):
                raise PrivateActionsError("No unique real kit release matches the retained exact ownership marker")
            release = matches[0]
            if bundle["kit"].get("release_id", release["id"]) != release["id"]:
                raise PrivateActionsError("The recovered actual release differs from the retained provider ID")
            bundle["kit"]["release_id"] = release["id"]
            self._save(state)
            assets = release.get("assets", [])
            if len(assets) != 1 or assets[0].get("name") != "mandatory-kit.zip":
                raise PrivateActionsError("The exact owned kit upload remains incomplete; retain its journal and release")
            if bundle["kit"].get("asset_id", assets[0]["id"]) != assets[0]["id"]:
                raise PrivateActionsError("Recovered kit asset differs from its original provider ID")
            bundle["kit"]["asset_id"] = assets[0]["id"]
            _asset_identity(assets[0], bundle["kit"])
            _download(self.repository, bundle["kit"], self.runtime / (task_id + "-repair-" + uuid.uuid4().hex + ".zip"))
            observations = {}
            for engine, item in state["engine_staging"].items():
                observed = repair_staging(receipt_path=Path(item["receipt_path"]))
                observations[engine] = observed
                if observed.get("status") == "ready":
                    item["receipt_sha256"] = observed["receipt_sha256"]
                    parsed = load_staging_receipt(Path(item["receipt_path"]).read_bytes(), observed["receipt_sha256"])
                    bundle["engines"][engine] = {"receipt": parsed, "sha256": observed["receipt_sha256"], "task_id": parsed["task_id"]}
            state["repair_observations"] = observations
            state["kit_repair_observation"] = "Actual owned kit identity and downloaded byte checksum verified; retained for explicit lifecycle review"
            self._save(state)
            return state
