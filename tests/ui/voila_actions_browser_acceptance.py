"""Exercise real Voilà widgets and downloaded classroom JSON through Chromium.

Run in the browser test environment against a running Start_Here.ipynb server.
This requires an authorized real project and verifies ORCA archive access through
its real Actions check before testing request exports. It does not run chemistry
or establish physical engine acceptance. No credentials are entered in the page.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import expect, sync_playwright


def select_label(control, prefix):
    option = control.locator("option").filter(has_text=re.compile("^" + re.escape(prefix).replace(r"\ ", r"\s"))).first
    expect(option).to_be_attached(timeout=20000)
    label = option.text_content()
    control.select_option(label=label)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8867")
    parser.add_argument("--chromium", default="/usr/bin/chromium")
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--repository", help="Authorized project; otherwise use the project's discovered identity")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--readiness-timeout", type=int, default=1200)
    args = parser.parse_args()
    if not 30 <= args.readiness_timeout <= 3600:
        parser.error("--readiness-timeout must be between 30 and 3600 seconds")
    artifact = args.artifacts or Path(tempfile.mkdtemp(prefix="cochem-actions-browser-"))
    artifact.mkdir(parents=True, exist_ok=True)
    errors, failures = [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.chromium, headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1500, "height": 1100})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("requestfailed", lambda request: failures.append({"url": request.url, "failure": request.failure}))
        try:
            page.goto(args.url, wait_until="domcontentloaded", timeout=60000)
            environment = page.get_by_label("Run calculations on:", exact=True)
            expect(environment).to_be_visible(timeout=90000)
            select_label(environment, "GitHub Actions")
            page.get_by_role("button", name="Show Project details (normally filled in automatically)", exact=True).click()
            project = page.get_by_label("GitHub project:", exact=True)
            if args.repository:
                project.fill(args.repository)
            repository = project.input_value()
            assert re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository), "An actual authorized project is required"
            page.get_by_label("Project branch:", exact=True).fill(args.branch)
            expect(page.get_by_role("heading", name="Check calculation access", exact=True)).to_be_visible()
            assert page.locator('input[type="password"]').count() == 0
            expect(page.get_by_role("link", name="Setup help: ORCA, CFOUR and project access", exact=True)).to_have_attribute(
                "href", f"https://github.com/{repository}/blob/{quote(args.branch, safe='')}/.docs/GET_STARTED.md")
            expect(page.get_by_label("Scientific data:", exact=True)).to_be_hidden()
            readiness = page.get_by_role("button", name="Check ORCA & CFOUR", exact=True)
            if readiness.is_enabled():
                readiness.click()
            page.screenshot(path=str(artifact / "classroom50-instructions.png"), full_page=True)
            page.get_by_role("button", name="Calculations", exact=True).click()
            page.get_by_role("tab", name="Starting structure", exact=True).click()
            page.get_by_role("button", name="Show Edit XYZ coordinates directly", exact=True).click()
            page.get_by_label("Geometry (XYZ):", exact=True).fill("O 0 0 0\nH 0 0 0.96\nH 0.92 0 -0.24")
            page.get_by_role("tab", name="Method and settings", exact=True).click()
            engine = page.get_by_label("Engine:", exact=True)
            expect(engine.locator("option").filter(has_text=re.compile(r"^ORCA\b"))).to_have_count(
                1, timeout=args.readiness_timeout * 1000)
            select_label(engine, "ORCA")
            page.get_by_role("radio", name="Exploratory calculation — no accuracy certification", exact=True).check()
            select_label(page.get_by_label("Theory family:", exact=True), "T2")
            select_label(page.get_by_role("combobox", name="Method:", exact=True), "HF/STO-3G")
            select_label(page.get_by_label("Basis Set:", exact=True), "STO-3G")
            select_label(page.get_by_label("Surroundings:", exact=True), "Gas phase (no solvent model)")
            page.get_by_label("Calculation label:", exact=True).fill("water-browser")
            actions_operation = page.get_by_role("combobox", name="Calculate:", exact=True)
            select_label(actions_operation, "Single point")
            expect(page.get_by_label("Output Dir:", exact=True)).to_be_hidden()
            page.get_by_role("button", name="Show Calculation resources and frequency guidance", exact=True).click()
            expect(page.get_by_label("Calculation timeout (s):", exact=True)).to_have_value("300")
            page.get_by_role("button", name="Show Optional reproducibility export", exact=True).click()
            prepare = page.get_by_role("button", name="Save configuration", exact=True)
            expect(prepare).to_be_enabled()
            prepare.click()
            expect(page.get_by_text("[System: Actions job prepared]", exact=True)).to_be_visible()
            expect(page.get_by_text("No calculation has been submitted or run.", exact=False)).to_be_visible()
            with page.expect_download() as download:
                page.get_by_role("link", name="Download ORCA request JSON", exact=True).click()
            assert download.value.suggested_filename == "water-browser-orca-job.json"
            target = artifact / download.value.suggested_filename
            download.value.save_as(target)
            data = json.loads(target.read_bytes())
            assert data["engine"] == "orca" and data["method"] == "HF" and data["basis_set"] == "STO-3G"
            assert data["is_opt"] is False and data["is_freq"] is False and data["is_vpt2"] is False
            assert data["timeout_seconds"] == 300 and data["product_class"] is None
            assert all(data[field] is None for field in ("hessian_file", "r2_reference_manifest", "t9_fallback", "periodic"))
            expect(page.get_by_role("button", name="Run on GitHub Actions", exact=True)).to_be_enabled()
            page.screenshot(path=str(artifact / "classroom-job-prepared.png"), full_page=True)
            select_label(actions_operation, "Optimize + harmonic frequencies")
            expect(page.get_by_role("link", name="Download ORCA request JSON", exact=True)).to_have_count(0)
            prepare.click()
            expect(page.get_by_text("[System: Actions job prepared]", exact=True)).to_be_visible()
            with page.expect_download() as frequency_download:
                page.get_by_role("link", name="Download ORCA request JSON", exact=True).click()
            frequency_target = artifact / "water-browser-harmonic-job.json"
            frequency_download.value.save_as(frequency_target)
            frequency_data = json.loads(frequency_target.read_bytes())
            assert frequency_data["is_opt"] is True and frequency_data["is_freq"] is True
            assert frequency_data["grid_stage"] == 3 and frequency_data["initial_hessian"] == "XTB2"
            page.screenshot(path=str(artifact / "classroom-harmonic-job-prepared.png"), full_page=True)
            select_label(page.get_by_label("Engine:", exact=True), "xTB")
            expect(page.get_by_role("link", name="Download ORCA request JSON", exact=True)).to_have_count(0)
            select_label(actions_operation, "Geometry optimization")
            prepare.click()
            with page.expect_download() as free_download:
                page.get_by_role("link", name="Download XTB request JSON", exact=True).click()
            free_target = artifact / "water-browser-xtb-job.json"
            free_download.value.save_as(free_target)
            free_data = json.loads(free_target.read_bytes())
            assert free_data["engine"] == "xtb" and free_data["is_opt"] is True
            assert free_data["is_freq"] is False and free_data["method"] == "GFN2-xTB"
            page.get_by_role("button", name="Start here", exact=True).click()
            select_label(environment, "Linux")
            expect(page.get_by_role("button", name="Show Advanced local setup", exact=True)).to_be_visible()
            page.get_by_role("button", name="Calculations", exact=True).click()
            expect(page.get_by_role("button", name="Run xTB optimization", exact=True)).to_be_visible()
            # Native xTB has one fixed operation; neither operation selector is
            # exposed after leaving the hosted calculation route.
            expect(actions_operation).to_be_hidden()
            expect(page.get_by_label("Output Dir:", exact=True)).to_be_hidden()
            assert not errors, errors
            assert not failures, failures
            report = {"status": "UI_EXPORT_VERIFIED", "hosted_execution_performed": False,
                      "repository": repository, "branch": args.branch,
                      "orca_choice_enabled_by_actual_archive_check": True,
                      "job_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                      "harmonic_job_sha256": hashlib.sha256(frequency_target.read_bytes()).hexdigest(),
                      "harmonic_grid_stage": frequency_data["grid_stage"],
                      "free_xtb_job_sha256": hashlib.sha256(free_target.read_bytes()).hexdigest(),
                      "job_file": "jobs/water-browser-orca-job.json", "page_errors": errors,
                      "request_failures": failures}
            (artifact / "browser-summary.json").write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report))
        except Exception:
            (artifact / "failure.txt").write_text(page.locator("body").inner_text())
            page.screenshot(path=str(artifact / "failure.png"), full_page=True)
            raise
        finally:
            browser.close()


if __name__ == "__main__":
    main()
