"""Accept BASE's real student widgets and optional genuine hosted chemistry.

This is a maintainer harness, not student setup code. It drives a rendered Voilà
kernel through Chromium, including actual file-input uploads. A hosted check
uses the server's existing authenticated GitHub route; no token is entered in
browser controls and no backend is replaced with a simulated client.

Examples::

    python tests/ui/student_entrypoint_browser_acceptance.py --url http://127.0.0.1:8866 --artifacts /tmp/ui-proof
    python tests/ui/student_entrypoint_browser_acceptance.py --hosted --repository owner/repo --branch approved --execution-origin github-actions

UI-only success never claims Actions or actual Codespaces service acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
import time
import uuid
import zipfile

from playwright.sync_api import expect, sync_playwright


WATER = b"3\nStudent-made monomer starting geometry; coordinates in angstrom\nO 0 0 0\nH 0 -0.757 0.587\nH 0 0.757 0.587\n"
SECOND_WATER = b"3\nSecond student-made monomer\nO 0 0 0\nH 0 -0.758 0.588\nH 0 0.758 0.588\n"
DIMER = b"6\nStudent-made complex starting arrangement\nO 0 0 0\nH 0 -0.757 0.587\nH 0 0.757 0.587\nO 0 0 3.0\nH 0 -0.757 3.587\nH 0 0.757 3.587\n"
INVALID = b"4\nIncomplete uploaded geometry\nO 0 0 0\nH 0 0 1\nH 0 1 0\n"


def select_prefix(control, prefix: str) -> str:
    options = control.locator("option").all_text_contents()
    matches = [item for item in options if item.startswith(prefix)]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {prefix!r} choice, observed {matches!r}")
    control.select_option(label=matches[0])
    return matches[0]


def upload_files(page, paths: list[Path]) -> None:
    # ipywidgets uses a detached HTML file input. The browser chooser exercises
    # the actual widget event path instead of assigning its Python value.
    button = page.get_by_role("button", name=re.compile(r"Upload \.xyz(?:\s*\(\d+\))?$"))
    expect(button).to_be_enabled(timeout=15000)
    with page.expect_file_chooser(timeout=15000) as chooser:
        button.click()
    chooser.value.set_files([str(path) for path in paths])


def origin_record(args) -> dict:
    github = os.environ.get("GITHUB_ACTIONS", "").lower() == "true"
    codespace = os.environ.get("CODESPACES", "").lower() == "true"
    if args.execution_origin == "github-actions" and not github:
        raise AssertionError("GitHub Actions origin requires an actual GITHUB_ACTIONS worker")
    if args.execution_origin == "codespaces":
        if not codespace or not args.codespace_evidence:
            raise AssertionError("Codespaces origin requires actual service identity and API evidence")
        data = json.loads(args.codespace_evidence.read_bytes())
        if (data.get("name") != os.environ.get("CODESPACE_NAME")
                or not isinstance(data.get("owner"), dict)
                or not data["owner"].get("login") or not data.get("created_at")
                or not data.get("repository", {}).get("full_name")):
            raise AssertionError("Codespaces evidence does not identify this actual workspace")
    if args.execution_origin == "local" and (github or codespace):
        raise AssertionError("Use the actual worker origin instead of labeling it local")
    origin = args.execution_origin
    if origin == "auto":
        origin = "github-actions" if github else "codespaces-unverified-service" if codespace else "local"
    return {"origin": origin, "actual_codespaces_service_acceptance": args.execution_origin == "codespaces",
            "github_browser_acceptance_run_id": os.environ.get("GITHUB_RUN_ID") if github else None}


def archive_records(bundle: Path) -> dict[str, bytes]:
    records = {}
    total = 0
    with zipfile.ZipFile(bundle) as archive:
        for item in archive.infolist():
            if item.is_dir():
                continue
            name = PurePosixPath(item.filename)
            mode = item.external_attr >> 16
            if (name.is_absolute() or ".." in name.parts or "\\" in item.filename
                    or item.filename in records or stat.S_ISLNK(mode)
                    or item.file_size > 100 * 1024 * 1024):
                raise AssertionError("Downloaded bundle contains an unsafe or duplicate path")
            total += item.file_size
            if total > 100 * 1024 * 1024:
                raise AssertionError("Downloaded bundle exceeds bounded evidence size")
            contents = archive.read(item)
            if contents.startswith(b"\x7fELF") or contents[:2] == b"MZ":
                raise AssertionError("A native runtime executable leaked into student evidence")
            records[item.filename] = contents
    return records


def verify_bundle(bundle: Path, *, request_id: str, repository: str, engine: str) -> dict:
    records = archive_records(bundle)
    manifest = json.loads(records["publication-manifest.json"])
    result = json.loads(records["student-result.json"])
    request = json.loads(records["request.json"])
    assert manifest["schema_version"] == "cochem.student-publication/1"
    assert result["schema_version"] == "cochem.student-result/1"
    assert result["status"] == "completed" and result["operation_performed"] is True
    for field in ("request_id", "repository", "source_sha", "worker_source_sha", "payload_sha256", "run_id", "run_attempt"):
        assert manifest[field] == result[field], field
    assert result["request_id"] == request_id and result["repository"] == repository
    assert re.fullmatch(r"[0-9a-f]{40}", result["source_sha"])
    assert re.fullmatch(r"[0-9a-f]{40}", result["worker_source_sha"])
    assert request["worker_source_sha"] == result["worker_source_sha"]
    assert result["run_id"] > 0 and result["run_attempt"] > 0
    assert request["request_id"] == request_id and request["source_sha"] == result["source_sha"]
    assert request["calculation"]["engine"] == engine
    canonical = json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    assert hashlib.sha256(canonical).hexdigest() == result["payload_sha256"]
    files = manifest["files"]
    assert files and set(files).issubset(records)
    # The GUI adds this original-input receipt after the sealed worker evidence
    # was downloaded. Every native/scientific file remains in the sealed list.
    assert set(records) - set(files) <= {"publication-manifest.json", "student-original-input.json"}
    for name, identity in files.items():
        assert identity == {"sha256": hashlib.sha256(records[name]).hexdigest(), "size_bytes": len(records[name])}, name
    original_files = [raw for name, raw in records.items() if name.endswith("original-student-geometry.xyz")]
    assert original_files == [WATER], "The retrieved original differs from the browser-uploaded bytes"
    calculation = result["result"]
    assert calculation["status"] == "passed" and calculation["scientific_execution_performed"] is True
    energy = calculation["energy_hartree"]
    assert isinstance(energy, (float, int)) and not isinstance(energy, bool) and math.isfinite(energy) and energy < 0
    assert any(name.endswith(".h5") for name in files), "Authentic scientific archive missing"
    return {"request_id": request_id, "repository": repository, "source_sha": result["source_sha"],
            "worker_source_sha": result["worker_source_sha"],
            "run_id": result["run_id"], "run_attempt": result["run_attempt"],
            "payload_sha256": result["payload_sha256"], "energy_hartree": energy,
            "sealed_file_count": len(files), "bundle_sha256": hashlib.sha256(bundle.read_bytes()).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8866")
    parser.add_argument("--chromium", default="/usr/bin/chromium")
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--hosted", action="store_true", help="Actually dispatch and retrieve native chemistry")
    parser.add_argument("--repository", help="Authorized actual calculation repository; required with --hosted")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--engine", choices=("orca", "cfour"), default="orca")
    parser.add_argument("--calculation-timeout", type=int, default=600)
    parser.add_argument("--hosted-timeout", type=int, default=2700)
    parser.add_argument("--setup-timeout", type=int, default=1800)
    parser.add_argument("--allow-unavailable-modules", action="store_true", help="Record accurate capability absence in UI-only acceptance")
    parser.add_argument("--execution-origin", choices=("auto", "local", "github-actions", "codespaces"), default="auto")
    parser.add_argument("--codespace-evidence", type=Path)
    parser.add_argument("--scientific-input", type=Path, help="Authentic R2 ZIP or READ .hess for actual upload/reopen acceptance")
    parser.add_argument("--scientific-kind", choices=("r2_reference", "read_hessian"))
    parser.add_argument("--scientific-geometry", type=Path, help="The input's exact matching starting XYZ")
    args = parser.parse_args()
    if args.hosted and (not args.repository or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository)):
        parser.error("--hosted requires an authorized real --repository")
    if args.hosted and args.allow_unavailable_modules:
        parser.error("Full hosted entrypoint acceptance must require installed analysis components")
    if any((args.scientific_input, args.scientific_kind, args.scientific_geometry)) and not all(
            (args.scientific_input, args.scientific_kind, args.scientific_geometry)):
        parser.error("Scientific upload acceptance requires --scientific-input, --scientific-kind and --scientific-geometry")
    artifact = args.artifacts or Path(tempfile.mkdtemp(prefix="cochem-student-browser-"))
    artifact.mkdir(parents=True, exist_ok=True)
    for name, contents in (("student-water.xyz", WATER), ("student-water-b.xyz", SECOND_WATER),
                           ("student-complex.xyz", DIMER), ("student-invalid.xyz", INVALID)):
        (artifact / name).write_bytes(contents)
    report = {"schema_version": "cochem.student-browser-acceptance/1", **origin_record(args),
              "hosted_execution_performed": False, "student_account_acceptance": False,
              "interface_url": args.url, "input_sha256": {
                  name: hashlib.sha256(contents).hexdigest() for name, contents in
                  (("student-water.xyz", WATER), ("student-water-b.xyz", SECOND_WATER), ("student-complex.xyz", DIMER))}}
    page_errors, request_failures = [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.chromium, headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1600, "height": 1200}, accept_downloads=True)
        page.on("pageerror", lambda error: page_errors.append({"message": str(error), "stack": error.stack}))
        page.on("requestfailed", lambda request: request_failures.append({"url": request.url, "failure": request.failure}))
        try:
            page.goto(args.url, wait_until="domcontentloaded", timeout=60000)
            expect(page.get_by_role("heading", name="CoChem setup and updates", exact=True)).to_be_visible(timeout=120000)
            components = page.get_by_role("table", name="CoChem components", exact=True)
            expect(components).to_be_visible(timeout=120000)
            if not args.allow_unavailable_modules:
                expect(components.get_by_role("row").filter(has_text="TOPOS")).to_contain_text("installed", timeout=args.setup_timeout * 1000)
                expect(components.get_by_role("row").filter(has_text="TORQ")).to_contain_text("installed", timeout=args.setup_timeout * 1000)
            report["component_status"] = components.inner_text()
            for name in ("Retry setup", "Check for updates", "Apply compatible updates", "Roll back update", "Restart interface"):
                expect(page.get_by_role("button", name=name, exact=True)).to_be_visible()
            assert page.locator('input[type="password"]').count() == 0
            page.screenshot(path=str(artifact / "automatic-setup.png"), full_page=True)
            page.get_by_role("button", name="No Code Matrix", exact=True).click()
            upload_files(page, [artifact / "student-water.xyz", artifact / "student-water-b.xyz", artifact / "student-complex.xyz"])
            selection = page.get_by_label("Starting geometry:", exact=True)
            expect(selection.locator("option")).to_have_count(3, timeout=30000)
            expect(selection).to_have_value("student-complex.xyz")
            expect(page.get_by_label("Geometry (XYZ):", exact=True)).to_have_value(DIMER.decode())
            expect(page.get_by_text(report["input_sha256"]["student-complex.xyz"], exact=True)).to_be_visible()
            page.get_by_label("Fragment atom groups:", exact=True).fill("1,2,3;4,5,6")
            page.get_by_role("button", name="Save geometry details", exact=True).click()
            expect(page.get_by_text("Saved complex details:", exact=False)).to_be_visible(timeout=15000)
            selection.select_option(label="student-water.xyz")
            page.get_by_label("Input type:", exact=True).select_option(label="Monomer A")
            page.get_by_role("button", name="Save geometry details", exact=True).click()
            expect(page.get_by_text("Saved monomer_a details:", exact=False)).to_be_visible(timeout=15000)
            expect(page.get_by_label("Geometry (XYZ):", exact=True)).to_have_value(WATER.decode())
            upload_files(page, [artifact / "student-invalid.xyz"])
            expect(page.get_by_text("Rejected uploads:", exact=False)).to_be_visible(timeout=15000)
            expect(selection.locator("option")).to_have_count(3)
            expect(page.get_by_label("Geometry (XYZ):", exact=True)).to_have_value(WATER.decode())
            selection.select_option(label="student-complex.xyz")
            expect(page.get_by_label("Fragment atom groups:", exact=True)).to_have_value("1,2,3;4,5,6")
            selection.select_option(label="student-water.xyz")
            expect(page.get_by_label("Input type:", exact=True)).to_have_value("Monomer A")
            expect(page.get_by_text(report["input_sha256"]["student-water.xyz"], exact=True)).to_be_visible()
            selection.select_option(index=1)
            page.get_by_label("Input type:", exact=True).select_option(label="Monomer B")
            page.get_by_role("button", name="Save geometry details", exact=True).click()
            expect(page.get_by_text("Saved monomer_b details:", exact=False)).to_be_visible(timeout=15000)
            monomers = page.get_by_label("Your monomers:", exact=True)
            expect(monomers.locator("option")).to_have_count(2)
            monomers.select_option(label=["student-water", "student-water-b"])
            page.get_by_role("button", name="Prepare complex starting seed", exact=True).click()
            expect(page.get_by_text("Starting packing prepared by translation only.", exact=True)).to_be_visible(timeout=15000)
            expect(selection.locator("option")).to_have_count(4)
            seed = page.get_by_label("Geometry (XYZ):", exact=True).input_value()
            seed_lines = seed.strip().splitlines()
            assert int(seed_lines[0]) == 6 and len(seed_lines) == 8
            coordinates = [tuple(map(float, line.split()[1:])) for line in seed_lines[2:]]
            for offset, original in ((0, WATER), (3, SECOND_WATER)):
                original_coordinates = [tuple(map(float, line.split()[1:])) for line in original.decode().splitlines()[2:]]
                for left in range(3):
                    for right in range(left + 1, 3):
                        assert abs(math.dist(coordinates[offset + left], coordinates[offset + right]) - math.dist(original_coordinates[left], original_coordinates[right])) < 1e-10
            expect(page.get_by_label("Fragment atom groups:", exact=True)).to_have_value("1,2,3;4,5,6")
            selection.select_option(index=0)
            expect(page.get_by_label("Geometry (XYZ):", exact=True)).to_have_value(WATER.decode())
            expect(page.get_by_text(report["input_sha256"]["student-water.xyz"], exact=True)).to_be_visible()
            report["upload"] = {"actual_browser_file_input": True, "valid_structures": 3,
                                "monomer_and_complex_roles_preserved": True, "invalid_upload_rejected": True,
                                "own_monomers_assembled_as_seed": True, "monomer_internal_distances_preserved": True,
                                "seed_energy_or_stability_claimed": False, "seed_sha256": hashlib.sha256(seed.encode()).hexdigest()}
            page.screenshot(path=str(artifact / "uploaded-student-geometries.png"), full_page=True)
            # A reload starts a new real Voilà kernel. The student's workspace
            # must reopen from its retained manifests without another upload.
            page.reload(wait_until="domcontentloaded", timeout=60000)
            expect(page.get_by_role("heading", name="CoChem setup and updates", exact=True)).to_be_visible(timeout=120000)
            page.get_by_role("button", name="No Code Matrix", exact=True).click()
            selection = page.get_by_label("Starting geometry:", exact=True)
            expect(selection.locator("option")).to_have_count(4, timeout=30000)
            for label, original, role, groups in (
                ("student-water", WATER, "Monomer A", ""),
                ("student-water-b", SECOND_WATER, "Monomer B", ""),
                ("student-complex", DIMER, "Complex starting geometry", "1,2,3;4,5,6"),
                ("student-water + student-water-b", seed.encode(), "Complex starting geometry", "1,2,3;4,5,6"),
            ):
                selection.select_option(label=label)
                expect(page.get_by_label("Geometry (XYZ):", exact=True)).to_have_value(original.decode())
                expect(page.get_by_label("Input type:", exact=True)).to_have_value(role)
                expect(page.get_by_label("Fragment atom groups:", exact=True)).to_have_value(groups)
                expect(page.get_by_label("Charge:", exact=True)).to_have_value("0")
                expect(page.get_by_label("Multiplicity:", exact=True)).to_have_value("1")
                expect(page.get_by_text(hashlib.sha256(original).hexdigest(), exact=True)).to_be_visible()
            expect(page.get_by_label("Your monomers:", exact=True).locator("option")).to_have_count(2)
            selection.select_option(label="student-water")
            report["upload"]["fresh_kernel_recovery_without_reupload"] = True
            report["upload"]["recovered_original_bytes_roles_states_and_fragments"] = True
            page.screenshot(path=str(artifact / "restored-student-workspace.png"), full_page=True)
            if args.scientific_input:
                original_geometry = args.scientific_geometry.read_bytes()
                upload_files(page, [args.scientific_geometry])
                expect(selection.locator("option")).to_have_count(5, timeout=30000)
                expect(page.get_by_label("Geometry (XYZ):", exact=True)).to_have_value(original_geometry.decode("utf-8-sig"))
                page.get_by_text("Fragments / Frozen", exact=True).click()
                label = "Upload R2 references" if args.scientific_kind == "r2_reference" else "Upload READ Hessian"
                button = page.get_by_role("button", name=re.compile(re.escape(label) + r"(?:\s*\(\d+\))?$"))
                with page.expect_file_chooser(timeout=15000) as chooser:
                    button.click()
                chooser.value.set_files(str(args.scientific_input))
                expect(page.get_by_text(args.scientific_kind + " retained.", exact=True)).to_be_visible(timeout=120000)
                page.screenshot(path=str(artifact / "retained-scientific-input.png"), full_page=True)
                page.reload(wait_until="domcontentloaded", timeout=60000)
                expect(page.get_by_role("heading", name="CoChem setup and updates", exact=True)).to_be_visible(timeout=120000)
                page.get_by_role("button", name="No Code Matrix", exact=True).click()
                selection = page.get_by_label("Starting geometry:", exact=True)
                expect(selection.locator("option")).to_have_count(5, timeout=30000)
                selection.select_option(label=args.scientific_geometry.stem)
                expect(page.get_by_label("Geometry (XYZ):", exact=True)).to_have_value(original_geometry.decode("utf-8-sig"))
                expect(page.get_by_text(hashlib.sha256(original_geometry).hexdigest(), exact=True)).to_be_visible()
                page.get_by_text("Fragments / Frozen", exact=True).click()
                expect(page.get_by_text("Retained R2/READ evidence was reopened after verifying its original file hashes.", exact=False)).to_be_visible(timeout=120000)
                report["scientific_input"] = {"kind": args.scientific_kind,
                    "actual_browser_upload_and_fresh_kernel_recovery": True,
                    "original_input_sha256": hashlib.sha256(args.scientific_input.read_bytes()).hexdigest(),
                    "original_input_size_bytes": args.scientific_input.stat().st_size,
                    "geometry_sha256": hashlib.sha256(original_geometry).hexdigest(),
                    "scientific_execution_established_by_upload": False}
                page.screenshot(path=str(artifact / "restored-scientific-input.png"), full_page=True)
                selection.select_option(label="student-water")
            if args.hosted:
                page.get_by_role("button", name="Seamless Install", exact=True).click()
                select_prefix(page.get_by_label("Calculation Environment:", exact=True), "GitHub Actions")
                page.get_by_label("Course repository:", exact=True).fill(args.repository)
                page.get_by_label("Approved branch:", exact=True).fill(args.branch)
                remote_check = page.get_by_role("button", name="Retry remote engine check", exact=True)
                if remote_check.is_enabled():
                    remote_check.click()
                page.get_by_role("button", name="No Code Matrix", exact=True).click()
                page.get_by_text("Base Config", exact=True).click()
                engine = page.get_by_label("Engine:", exact=True)
                required_engine = "ORCA" if args.engine == "orca" else "CFOUR"
                expect(engine.locator("option").filter(has_text=re.compile(r"^" + required_engine + r"\b"))).to_have_count(
                    1, timeout=min(1200, args.hosted_timeout) * 1000)
                report["remote_engine_readiness"] = {"engine": args.engine,
                    "actual_archive_access_gated_choice": select_prefix(engine, required_engine),
                    "native_execution_established_by_readiness": False}
                if args.engine == "orca":
                    page.get_by_label("Screening (no product accuracy claim)", exact=True).check()
                select_prefix(page.get_by_label("Theory Tier:", exact=True), "T2")
                select_prefix(page.get_by_label("Method:", exact=True), "HF/STO-3G" if args.engine == "orca" else "HF")
                select_prefix(page.get_by_label("Basis Set:", exact=True), "STO-3G")
                select_prefix(page.get_by_label("Solvation:", exact=True), "None")
                select_prefix(page.get_by_label("Actions operation:", exact=True), "Single point")
                page.get_by_label("Calculation timeout (s):", exact=True).fill(str(args.calculation_timeout))
                page.get_by_label("Calculation timeout (s):", exact=True).press("Tab")
                page.get_by_label("Project Name:", exact=True).fill("student-browser-" + uuid.uuid4().hex[:8])
                run = page.get_by_role("button", name="Run on GitHub Actions", exact=True)
                expect(run).to_be_enabled(timeout=30000)
                run.click()
                deadline = time.monotonic() + args.hosted_timeout
                request_id = None
                run_url = None
                while time.monotonic() < deadline:
                    body = page.locator("body").inner_text()
                    if "Calculation was not submitted:" in body or "Actions submission failed" in body:
                        raise AssertionError("Actual GUI dispatch failed; see retained browser evidence")
                    match = re.search(r"Request:\s*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", body)
                    if match:
                        observed_id = str(uuid.UUID(match.group(1)))
                        assert request_id in {None, observed_id}, "The GUI changed request identity during monitoring"
                        request_id = observed_id
                    links = page.get_by_role("link", name="Calculation run details", exact=True)
                    if links.count():
                        observed_url = links.first.get_attribute("href")
                        assert observed_url.startswith(f"https://github.com/{args.repository}/actions/runs/")
                        assert run_url in {None, observed_url}, "The GUI switched to a different hosted run"
                        run_url = observed_url
                    if "Calculation: completed" in body:
                        assert "result: success" in body, "Hosted chemistry did not succeed"
                        break
                    refresh = page.get_by_role("button", name="Refresh calculation status", exact=True)
                    if refresh.is_enabled():
                        refresh.click()
                    page.wait_for_timeout(5000)
                else:
                    raise AssertionError("Actual hosted chemistry exceeded the bounded acceptance deadline")
                assert request_id and run_url
                page.screenshot(path=str(artifact / "hosted-completed.png"), full_page=True)
                retrieve = page.get_by_role("button", name="Retrieve and inspect results", exact=True)
                expect(retrieve).to_be_enabled(timeout=15000)
                retrieve.click()
                expect(page.get_by_text("Results verified and imported.", exact=True)).to_be_visible(timeout=120000)
                with page.expect_download(timeout=30000) as pending:
                    page.get_by_role("link", name="Download calculation bundle", exact=True).click()
                bundle = artifact / "verified-calculation-bundle.zip"
                pending.value.save_as(bundle)
                report["hosted"] = {**verify_bundle(bundle, request_id=request_id, repository=args.repository, engine=args.engine),
                                    "run_url": run_url, "actual_gui_dispatch": True,
                                    "actual_gui_monitoring": True, "actual_gui_result_retrieval": True}
                report["hosted_execution_performed"] = True
                page.screenshot(path=str(artifact / "verified-results-imported.png"), full_page=True)
            assert not page_errors, page_errors
            assert not request_failures, request_failures
            report.update(status="STUDENT_ENTRYPOINT_HOSTED_VERIFIED" if args.hosted else "STUDENT_ENTRYPOINT_UI_VERIFIED",
                          page_errors=page_errors, request_failures=request_failures)
            (artifact / "browser-summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(report, sort_keys=True))
        except Exception as error:
            report.update(status="FAILED", error_type=type(error).__name__, error=str(error),
                          page_errors=page_errors, request_failures=request_failures)
            (artifact / "browser-summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            (artifact / "failure.txt").write_text(page.locator("body").inner_text(), encoding="utf-8")
            page.screenshot(path=str(artifact / "failure.png"), full_page=True)
            raise
        finally:
            browser.close()


if __name__ == "__main__":
    main()
