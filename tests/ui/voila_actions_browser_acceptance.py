"""Exercise real Voilà widgets and downloaded classroom JSON through Chromium.

Run in the browser test environment against a running Start_Here.ipynb server.
This proves preparation/download and local execution isolation, not hosted engine
acceptance: the downloaded request still requires its real GitHub workflow run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile

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
    args = parser.parse_args()
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
            environment = page.get_by_label("Calculation Environment:", exact=True)
            expect(environment).to_be_visible(timeout=90000)
            select_label(environment, "GitHub Actions")
            page.get_by_label("Course repository:", exact=True).fill("course-organization/student-water")
            page.get_by_label("Approved branch:", exact=True).fill("main")
            expect(page.get_by_text("GitHub Actions: Classroom50 course setup", exact=True)).to_be_visible()
            assert page.locator('input[type="password"]').count() == 0
            for name, anchor in (("Student quick start", "student-quick-start"),
                                 ("Instructor setup", "instructor-setup"), ("Troubleshooting", "troubleshooting")):
                expect(page.get_by_role("link", name=name, exact=True)).to_have_attribute(
                    "href", "https://github.com/course-organization/student-water/blob/main/"
                    f".docs/GitHub_Classroom_ORCA_Setup.md#{anchor}")
            expect(page.get_by_label("Scientific data:", exact=True)).to_be_hidden()
            review = page.get_by_role("button", name="Review Actions setup", exact=True)
            expect(review).to_be_enabled()
            review.click()
            expect(page.get_by_text("[System: Actions setup instructions]", exact=True)).to_be_visible()
            page.screenshot(path=str(artifact / "classroom50-instructions.png"), full_page=True)
            page.get_by_role("button", name="No Code Matrix", exact=True).click()
            page.get_by_label("Geometry (XYZ):", exact=True).fill("O 0 0 0\nH 0 0 0.96\nH 0.92 0 -0.24")
            page.get_by_label("Screening (no product accuracy claim)", exact=True).check()
            page.get_by_text("Base Config", exact=True).click()
            select_label(page.get_by_label("Theory Tier:", exact=True), "T2")
            select_label(page.get_by_label("Method:", exact=True), "HF/STO-3G")
            select_label(page.get_by_label("Basis Set:", exact=True), "STO-3G")
            select_label(page.get_by_label("Solvation:", exact=True), "None")
            page.get_by_label("Project Name:", exact=True).fill("water-browser")
            select_label(page.get_by_label("Actions operation:", exact=True), "Single point")
            expect(page.get_by_label("Output Dir:", exact=True)).to_be_hidden()
            prepare = page.get_by_role("button", name="Prepare GitHub Actions job", exact=True)
            expect(prepare).to_be_enabled()
            prepare.click()
            expect(page.get_by_text("[System: Actions job prepared]", exact=True)).to_be_visible()
            expect(page.get_by_text("No calculation has been submitted or run.", exact=False)).to_be_visible()
            with page.expect_download() as download:
                page.get_by_role("link", name="Download ORCA job JSON", exact=True).click()
            assert download.value.suggested_filename == "water-browser-orca-job.json"
            target = artifact / download.value.suggested_filename
            download.value.save_as(target)
            data = json.loads(target.read_bytes())
            assert data["engine"] == "orca" and data["method"] == "HF" and data["basis_set"] == "STO-3G"
            assert data["is_opt"] is False and data["is_freq"] is False and data["is_vpt2"] is False
            assert data["timeout_seconds"] == 300 and data["product_class"] is None
            assert all(data[field] is None for field in ("hessian_file", "r2_reference_manifest", "t9_fallback", "periodic"))
            expect(page.get_by_role("link", name="ORCA calculation", exact=True)).to_have_attribute(
                "href", "https://github.com/course-organization/student-water/actions/workflows/orca_calculation.yml")
            page.screenshot(path=str(artifact / "classroom-job-prepared.png"), full_page=True)
            select_label(page.get_by_label("Actions operation:", exact=True), "Optimize + harmonic frequencies")
            expect(page.get_by_role("link", name="Download ORCA job JSON", exact=True)).to_have_count(0)
            prepare.click()
            expect(page.get_by_text("[System: Actions job prepared]", exact=True)).to_be_visible()
            with page.expect_download() as frequency_download:
                page.get_by_role("link", name="Download ORCA job JSON", exact=True).click()
            frequency_target = artifact / "water-browser-harmonic-job.json"
            frequency_download.value.save_as(frequency_target)
            frequency_data = json.loads(frequency_target.read_bytes())
            assert frequency_data["is_opt"] is True and frequency_data["is_freq"] is True
            assert frequency_data["grid_stage"] == 3 and frequency_data["initial_hessian"] == "XTB2"
            page.screenshot(path=str(artifact / "classroom-harmonic-job-prepared.png"), full_page=True)
            select_label(page.get_by_label("Engine:", exact=True), "xTB")
            expect(prepare).to_be_disabled()
            expect(page.get_by_role("link", name="Download ORCA job JSON", exact=True)).to_have_count(0)
            expect(page.get_by_text("The course Actions workflow accepts ORCA jobs.", exact=False)).to_be_visible()
            page.get_by_role("button", name="Seamless Install", exact=True).click()
            select_label(environment, "Linux")
            expect(page.get_by_label("Scientific data:", exact=True)).to_be_visible()
            page.get_by_role("button", name="No Code Matrix", exact=True).click()
            expect(page.get_by_role("button", name="Run xTB optimization", exact=True)).to_be_visible()
            expect(page.get_by_label("Actions operation:", exact=True)).to_be_hidden()
            expect(page.get_by_label("Output Dir:", exact=True)).to_be_visible()
            assert not errors, errors
            assert not failures, failures
            report = {"status": "UI_EXPORT_VERIFIED", "hosted_execution_performed": False,
                      "job_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                      "harmonic_job_sha256": hashlib.sha256(frequency_target.read_bytes()).hexdigest(),
                      "harmonic_grid_stage": frequency_data["grid_stage"],
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
