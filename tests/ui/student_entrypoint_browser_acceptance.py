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
import csv
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
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
OPEN_SHELL_START = b"3\nConnected H3 active-space admission starting example; no calculated energy claimed\nH 0 0 0\nH 0 0 0.5\nH 0 0 1.0\n"


def select_prefix(control, prefix: str) -> str:
    # ipywidgets renders dropdown spaces as NBSP; match equivalent display whitespace.
    prefix_pattern = "^" + r"\s+".join(re.escape(part) for part in prefix.split())
    expect(control.locator("option").filter(has_text=re.compile(prefix_pattern))).to_have_count(1, timeout=30000)
    options = control.locator("option").all_text_contents()
    normalized_prefix = " ".join(prefix.split())
    matches = [item for item in options if " ".join(item.split()).startswith(normalized_prefix)]
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


def reload_with_kernel_cleanup(page, report: dict) -> None:
    """Exercise the real unload beacon and verify the previous kernel retires."""
    before = json.loads(page.locator("#jupyter-config-data").text_content())
    previous = before["kernelId"]
    uuid.UUID(previous)
    cookie = next((entry for entry in page.context.cookies() if entry["name"] == "_xsrf"), None)
    assert cookie and cookie["value"], "Rendered Voilà never issued its standard XSRF cookie"
    assert cookie["httpOnly"] is False, "Shutdown beacon must be able to read the XSRF cookie"
    base = before.get("baseUrl", "/")
    kernel_url = page.url.split("/voila/", 1)[0].rstrip("/") + base.rstrip("/") + "/api/kernels/" + previous
    assert page.context.request.get(kernel_url).status == 200, "Current rendered kernel is absent"
    page.reload(wait_until="domcontentloaded", timeout=60000)
    expect(page.get_by_role("heading", name="CoChem setup and updates", exact=True)).to_be_visible(timeout=120000)
    current = json.loads(page.locator("#jupyter-config-data").text_content())["kernelId"]
    assert current != previous, "Reload reused the previous execution kernel"
    deadline = time.monotonic() + 30
    while True:
        response = page.context.request.get(kernel_url)
        if response.status == 404:
            break
        assert response.status == 200, f"Unexpected kernel retirement response: {response.status}"
        assert time.monotonic() < deadline, "Reload left the previous Voilà kernel alive"
        page.wait_for_timeout(250)
    report.setdefault("kernel_cleanup", []).append({"previous_kernel_id": previous,
        "current_kernel_id": current, "xsrf_cookie_present": True,
        "authenticated_shutdown_beacon": True, "previous_kernel_retired": True})


def accept_full_intake(page, manifest_path: Path, report: dict, artifacts: Path) -> None:
    """Exercise genuine files through every public scientific intake panel."""
    manifest = json.loads(manifest_path.read_bytes())
    assert manifest["schema_version"] == "cochem.actual-browser-intake-fixtures/1"
    assert 1 <= len(manifest["files"]) <= 32
    kind_labels = {"molecular": "Molecular coordinates / multi-frame ensemble", "hessian": "Geometry-bound Hessian",
        "spectroscopy": "Native spectroscopy output", "periodic": "Periodic structure", "pseudopotential": "PAW pseudopotential",
        "native_result": "Native calculation result", "physical_data": "Physical HDF5 / NPZ data"}
    admitted = []
    for entry in manifest["files"]:
        raw = Path(entry["path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == entry["sha256"], "Actual fixture changed before upload"
        page.get_by_role("button", name="Input library", exact=True).click()
        page.get_by_label("Scientific input type:", exact=True).select_option(label=kind_labels[entry["kind"]])
        button = page.get_by_role("button", name=re.compile(r"Upload scientific inputs(?:\s*\(\d+\))?$"))
        expect(button).to_be_enabled(timeout=120000)
        with page.expect_file_chooser(timeout=15000) as chooser:
            button.click()
        chooser.value.set_files(entry["path"])
        table = page.get_by_role("table", name="Verified retained scientific inputs", exact=True)
        expect(table).to_contain_text(entry["sha256"], timeout=120000)
        select_prefix(page.get_by_label("Retained input:", exact=True), entry["filename"])
        frames = page.get_by_label("Structure / frame:", exact=True)
        expect(frames.locator("option")).to_have_count(entry["record_count"])
        for index in range(entry["record_count"]):
            frames.select_option(index=index)
            page.get_by_role("button", name="Use selected starting geometry", exact=True).click()
            expect(page.get_by_role("heading", name="No Code Matrix Configuration", exact=True)).to_be_visible(timeout=30000)
            page.get_by_text("Molecule Builder", exact=True).click()
            geometry = page.get_by_label("Geometry (XYZ):", exact=True).input_value()
            assert geometry.splitlines()[0] == "3"
            assert len(geometry.splitlines()) == 5
            if "qcschema" in entry["filename"]:
                assert [line.split()[0] for line in geometry.splitlines()[2:]] == ["18O", "2H", "2H"]
                page.get_by_text("Base Config", exact=True).click()
                expect(page.get_by_label("Charge:", exact=True)).to_have_value("0")
                expect(page.get_by_label("Multiplicity:", exact=True)).to_have_value("1")
            page.get_by_role("button", name="Input library", exact=True).click()
            select_prefix(page.get_by_label("Retained input:", exact=True), entry["filename"])
        admitted.append({"filename": entry["filename"], "kind": entry["kind"], "original_sha256": entry["sha256"],
                         "all_frames_selected": entry["record_count"], "actual_file_upload": True})
    page.get_by_role("button", name="Data Inspector (Ab-Initio)", exact=True).click()
    select_prefix(page.get_by_label("Native output:", exact=True), "actual-water.out.txt")
    page.get_by_role("button", name="Parse Observables", exact=True).click()
    expect(page.get_by_text("436210", exact=False)).to_be_visible(timeout=30000)
    # Missing ground-state/vibrational data stays visible; native output
    # structure alone does not establish stationary-equilibrium provenance.
    expect(page.get_by_text("[MISSING DATA]", exact=False).first).to_be_visible()
    page.get_by_text("Isotopic Re-analysis", exact=True).click()
    for filename in ("actual-water.hess", "actual-water-hessian.npz", "actual-water-hessian.h5"):
        source_hash = next(entry["sha256"] for entry in manifest["files"] if entry["filename"] == filename)
        select_prefix(page.get_by_label("Retained Hessian:", exact=True), filename)
        page.get_by_role("button", name="Load geometry and Hessian", exact=True).click()
        loaded = page.get_by_role("status").filter(has_text="Geometry and Cartesian Hessian loaded.")
        expect(loaded).to_contain_text(source_hash, timeout=30000)
        reanalyze = page.get_by_role("button", name="Re-analyze Isotopologue", exact=True)
        expect(reanalyze).to_be_enabled(timeout=30000)
        reanalyze.click()
        frequencies = page.get_by_role("table", name="Mass-weighted Cartesian Hessian frequencies", exact=True)
        expect(frequencies).to_be_visible(timeout=30000)
        expect(frequencies.locator("xpath=following-sibling::p[1]")).to_contain_text(source_hash, timeout=30000)
        expect(reanalyze).to_be_enabled(timeout=30000)
        expect(page.get_by_text("Physical force-Hessian origin and stationary geometry are not established", exact=False).first).to_be_visible()
    page.get_by_text("HDF5 SWMR Store", exact=True).click()
    for filename in ("actual-water-hessian.npz", "actual-water-hessian.h5"):
        select_prefix(page.get_by_label("Physical data:", exact=True), filename)
        page.get_by_role("button", name="Inspect HDF5 / NPZ data", exact=True).click()
        expect(page.get_by_text("hessian_hartree_bohr2", exact=False).first).to_be_visible(timeout=30000)
        expect(page.get_by_role("button", name="Inspect HDF5 / NPZ data", exact=True)).to_be_enabled(timeout=30000)
    page.get_by_role("button", name="Periodic structures", exact=True).click()
    select_prefix(page.get_by_label("Periodic structure:", exact=True), "gaas_ordered.cif")
    page.get_by_role("button", name="Validate periodic structure", exact=True).click()
    expect(page.get_by_text("Validated periodic structure: 2 atoms", exact=False)).to_be_visible(timeout=30000)
    for symbol in ("Ga", "As"):
        control = page.get_by_label(symbol + " PAW file:", exact=True)
        expect(control.locator("option")).to_have_count(1)
        control.select_option(index=0)
    page.get_by_label("Wavefunction cutoff (Ry):", exact=True).fill("45")
    page.get_by_label("Density cutoff (Ry):", exact=True).fill("360")
    page.get_by_role("button", name="Save periodic calculation request", exact=True).click()
    expect(page.get_by_text("Saved periodic calculation request", exact=False)).to_be_visible(timeout=30000)
    page.screenshot(path=str(artifacts / "typed-periodic-request.png"), full_page=True)
    page.get_by_role("button", name="No Code Matrix", exact=True).click()
    page.get_by_text("Molecule Builder", exact=True).click()
    page.get_by_label("Name or SMILES:", exact=True).fill("O")
    page.get_by_role("button", name="Build starting geometry", exact=True).click()
    expect(page.get_by_text("Generated starting geometry only.", exact=False)).to_be_visible(timeout=120000)
    expect(page.get_by_text("No quantum minimum or energy is claimed.", exact=False)).to_be_visible()
    generated = page.get_by_label("Geometry (XYZ):", exact=True).input_value()
    assert generated.splitlines()[0] == "3"
    reload_with_kernel_cleanup(page, report)
    page.get_by_role("button", name="Input library", exact=True).click()
    table = page.get_by_role("table", name="Verified retained scientific inputs", exact=True)
    for entry in admitted:
        expect(table).to_contain_text(entry["original_sha256"])
    page.screenshot(path=str(artifacts / "full-retained-scientific-inputs.png"), full_page=True)
    report["full_intake"] = {"files": admitted, "all_sources_recovered_after_reload": True,
        "native_spectroscopy_parsed": True, "supplied_hessian_isotope_reanalysis": True,
        "npz_hdf5_bounded_preview": True, "typed_periodic_request_saved": True,
        "smiles_builder_starting_guess_only": True, "native_engine_execution_performed": False,
        "isotope_tensor_reanalysis_performed": True,
        "physical_or_equilibrium_accuracy_claimed": False}
    page.get_by_role("button", name="No Code Matrix", exact=True).click()
    page.get_by_text("Molecule Builder", exact=True).click()
    page.get_by_label("Starting geometry:", exact=True).select_option(label="student-water")


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


def accept_admission_guards(page, report: dict, artifacts: Path) -> None:
    """Exercise real incomplete-active-space and absent-scheduler admission."""
    if shutil.which("sbatch") or shutil.which("qsub"):
        raise AssertionError("Absent-scheduler acceptance requires genuinely missing scheduler commands")
    page.get_by_role("button", name="No Code Matrix", exact=True).click()
    page.get_by_text("Molecule Builder", exact=True).click()
    geometry = artifacts / "student-open-shell.xyz"
    geometry.write_bytes(OPEN_SHELL_START)
    upload_files(page, [geometry])
    page.get_by_text("Fragments / Frozen", exact=True).click()
    page.get_by_label("Freeze all monomer internals (bonds/angles/dihedrals)", exact=True).uncheck()
    page.get_by_text("Base Config", exact=True).click()
    page.get_by_label("Multiplicity:", exact=True).fill("2")
    page.get_by_label("Multiplicity:", exact=True).press("Tab")
    select_prefix(page.get_by_label("Engine:", exact=True), "ORCA")
    page.get_by_label("Screening (no product accuracy claim)", exact=True).check()
    select_prefix(page.get_by_label("Theory Tier:", exact=True), "T2")
    select_prefix(page.get_by_label("Method:", exact=True), "HF/STO-3G")
    select_prefix(page.get_by_label("Basis Set:", exact=True), "STO-3G")
    select_prefix(page.get_by_label("Solvation:", exact=True), "None")
    run = page.get_by_role("button", name="Run ORCA optimization", exact=True)
    expect(run).to_be_disabled(timeout=30000)
    recovery = page.get_by_label("Enable explicit T9 spin-contamination recovery", exact=True)
    expect(recovery).to_be_enabled(timeout=30000)
    # Verify the actual backend before checking the explicit recovery intent gate.
    recovery.check()
    expect(page.get_by_text("T9 requires distinct nonnegative MO indices", exact=False).first).to_be_visible(timeout=30000)
    expect(run).to_be_disabled()
    recovery.uncheck()
    expect(page.get_by_text("Open-shell ORCA requires explicit T9 recovery before starting", exact=False).first).to_be_visible()
    expect(run).to_be_disabled()
    recovery.check()
    page.get_by_label("Active electrons:", exact=True).fill("3")
    page.get_by_label("Active MO indices:", exact=True).fill("0,1,2")
    page.get_by_label("Active-space rationale:", exact=True).fill("Three singly occupied hydrogen 1s-derived orbitals for this explicit H3 doublet starting geometry.")
    page.get_by_label("Active-space rationale:", exact=True).press("Tab")
    expect(run).to_be_enabled(timeout=30000)
    page.get_by_label("Active MO indices:", exact=True).fill("0,0,2")
    page.get_by_label("Active MO indices:", exact=True).press("Tab")
    expect(run).to_be_disabled(timeout=30000)
    expect(page.get_by_text("T9 requires distinct nonnegative MO indices", exact=False).first).to_be_visible()
    page.screenshot(path=str(artifacts / "incomplete-active-space-disabled.png"), full_page=True)
    recovery.uncheck()
    page.get_by_text("Molecule Builder", exact=True).click()
    page.get_by_label("Starting geometry:", exact=True).select_option(label="student-water")
    page.get_by_text("Base Config", exact=True).click()
    page.get_by_label("Multiplicity:", exact=True).fill("1")
    page.get_by_label("Multiplicity:", exact=True).press("Tab")
    page.get_by_role("button", name="Seamless Install", exact=True).click()
    select_prefix(page.get_by_label("Calculation Environment:", exact=True), "HPC Cluster")
    page.get_by_role("button", name="No Code Matrix", exact=True).click()
    page.get_by_text("Base Config", exact=True).click()
    select_prefix(page.get_by_label("Engine:", exact=True), "xTB")
    submit = page.get_by_role("button", name="Submit HPC calculation", exact=True)
    expect(submit).to_be_disabled(timeout=30000)
    connection = page.get_by_role("button", name="Check HPC connection", exact=True)
    expect(connection).to_be_enabled(timeout=30000)
    connection.click()
    expect(page.get_by_text("No interface-host scientific fallback is performed", exact=False).first).to_be_visible(timeout=60000)
    expect(page.get_by_text(re.compile(r"scheduler access is unavailable|Complete BASE setup on a connected Slurm/OpenPBS login host"), exact=False).first).to_be_visible()
    expect(submit).to_be_disabled(timeout=30000)
    expect(page.get_by_role("button", name="Retrieve HPC results", exact=True)).to_be_disabled()
    expect(page.get_by_role("button", name="Cancel HPC job", exact=True)).to_be_disabled()
    page.screenshot(path=str(artifacts / "missing-scheduler-refused.png"), full_page=True)
    report["admission_guards"] = {"actual_incomplete_t9_run_disabled": True,
        "explicit_valid_active_space_admitted_without_execution": True,
        "duplicate_orbitals_disable_execution": True,
        "actual_scheduler_commands_absent": True, "actual_hpc_connection_retry": True,
        "hpc_submission_disabled_by_actual_preflight": True, "hpc_submission_refused_without_local_fallback": True,
        "scientific_execution_performed": False}
    page.get_by_role("button", name="Seamless Install", exact=True).click()
    select_prefix(page.get_by_label("Calculation Environment:", exact=True), "Linux")


def accept_native_hessian_calculation(page, report: dict, artifacts: Path, timeout: int) -> None:
    """Run genuine native chemistry through widgets, then reweight its Hessian."""
    page.get_by_role("button", name="No Code Matrix", exact=True).click()
    page.get_by_text("Molecule Builder", exact=True).click()
    page.get_by_label("Starting geometry:", exact=True).select_option(label="student-water")
    expect(page.get_by_label("Geometry (XYZ):", exact=True)).to_have_value(WATER.decode())
    page.get_by_text("Base Config", exact=True).click()
    select_prefix(page.get_by_label("Engine:", exact=True), "ORCA")
    page.get_by_label("Screening (no product accuracy claim)", exact=True).check()
    select_prefix(page.get_by_label("Theory Tier:", exact=True), "T2")
    select_prefix(page.get_by_label("Method:", exact=True), "HF/STO-3G")
    select_prefix(page.get_by_label("Basis Set:", exact=True), "STO-3G")
    select_prefix(page.get_by_label("Solvation:", exact=True), "None")
    select_prefix(page.get_by_label("Calculation operation:", exact=True), "Optimize + harmonic frequencies")
    page.get_by_label("Native timeout (s):", exact=True).fill(str(timeout))
    page.get_by_label("Native timeout (s):", exact=True).press("Tab")
    page.get_by_label("Project Name:", exact=True).fill("browser-native-hessian-" + uuid.uuid4().hex[:12])
    run = page.get_by_role("button", name="Run ORCA optimize + frequencies", exact=True)
    expect(run).to_be_enabled(timeout=30000)
    run.click()
    completed = page.get_by_text("execution and scientific output checks passed", exact=False).first
    expect(completed).to_be_visible(timeout=timeout * 1000)
    directories = re.findall(r"ORCA execution and scientific output checks passed\. Results: ([^\r\n]+)",
                             completed.inner_text())
    assert len(directories) == 1, "Native completion must name its exact retained Results directory"
    result_root = Path(directories[0].strip())
    assert result_root.is_dir() and not result_root.is_symlink()
    result_root = result_root.resolve(strict=True)
    page.get_by_role("button", name="Data Inspector (Ab-Initio)", exact=True).click()
    page.get_by_text("Isotopic Re-analysis", exact=True).click()
    selector = page.get_by_label("Calculation Hessian:", exact=True)
    candidates = selector.locator("option").filter(has_text=re.compile(r"\.hess$"))
    expect(candidates.first).to_be_attached(timeout=30000)
    label = None
    for candidate in candidates.all_text_contents():
        selector.select_option(label=candidate)
        selected = page.get_by_role("status").filter(has_text="Retained Hessian selected:")
        expect(selected).to_contain_text(candidate, timeout=30000)
        if "Retained native force-Hessian, mass and spectrum receipts agree" in selected.inner_text():
            selected_text = selected.text_content()
            prefix = "Retained Hessian selected: "
            assert selected_text is not None and selected_text.startswith(prefix)
            label, terminator, _ = selected_text[len(prefix):].partition(". Choose Load geometry and Hessian.")
            assert terminator, "Selected Hessian receipt lacks its canonical public label boundary"
            break
    assert label, "No generated Hessian has matching actual native derivative receipts"
    root_label, separator, relative = label.partition(" · ")
    member = PurePosixPath(relative)
    assert separator and root_label == result_root.name and not member.is_absolute()
    assert member.as_posix() == relative and ".." not in member.parts
    path = result_root.joinpath(*member.parts)
    assert not path.is_symlink() and path.resolve(strict=True).is_relative_to(result_root)
    assert path.is_file() and path.suffix == ".hess", "The selector must resolve an actual native Hessian"
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    assert re.findall(r"SHA-256:\s*([a-f0-9]{64})", selected.inner_text()) == [before], \
        "The selected public Hessian receipt must match the actual retained native file"
    page.get_by_role("button", name="Load geometry and Hessian", exact=True).click()
    loaded = page.get_by_role("status").filter(has_text="Geometry and Cartesian Hessian loaded.")
    expect(loaded).to_contain_text(before, timeout=60000)
    select_prefix(page.get_by_label("Atom 1 (O):", exact=True), "18O")
    reanalyze = page.get_by_role("button", name="Re-analyze Isotopologue", exact=True)
    expect(reanalyze).to_be_enabled(timeout=30000)
    reanalyze.click()
    table = page.get_by_role("table", name="Mass-weighted Cartesian Hessian frequencies", exact=True)
    expect(table.locator("tbody tr")).to_have_count(3, timeout=60000)
    expect(table.locator("xpath=following-sibling::p[1]")).to_contain_text(before)
    expect(reanalyze).to_be_enabled(timeout=30000)
    for title, filename in (("Download frequency data (CSV)", "native-harmonic-modes.csv"),
                            ("Download SVG figure", "native-harmonic-modes.svg")):
        with page.expect_download(timeout=30000) as pending:
            page.get_by_role("link", name=title, exact=True).click()
        pending.value.save_as(artifacts / filename)
    rows = list(csv.DictReader((artifacts / "native-harmonic-modes.csv").read_text().splitlines()))
    assert len(rows) == 3 and all(row["sha256"] == before for row in rows)
    assert all(row["physical_hessian_verified"] == "True" and row["minimum_verified"] == "True" for row in rows)
    parent = [float(row["parent_cm-1"]) for row in rows]
    isotope = [float(row["substituted_cm-1"]) for row in rows]
    assert all(math.isfinite(value) and value > 0 for value in parent + isotope)
    assert any(abs(left - right) > 1e-6 for left, right in zip(parent, isotope, strict=True))
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before, "Isotope analysis modified its native force Hessian"
    svg = (artifacts / "native-harmonic-modes.svg").read_text()
    assert before in svg and "<svg" in svg
    page.screenshot(path=str(artifacts / "native-hessian-isotope-result.png"), full_page=True)
    report["native_hessian_result"] = {"actual_browser_native_calculation": True,
        "engine": "orca", "method": "HF", "basis": "STO-3G",
        "operation": "optimization_frequencies", "native_hessian_path": str(path),
        "native_hessian_sha256": before, "source_unchanged_after_isotope_reweighting": True,
        "actual_calculation_result_selector": True, "actual_csv_and_svg_download": True,
        "parent_frequencies_cm1": parent, "substituted_frequencies_cm1": isotope,
        "physical_hessian_verified": rows[0]["physical_hessian_verified"],
        "minimum_verified": rows[0]["minimum_verified"], "validation_scope": rows[0]["validation_scope"],
        "electronic_recalculation_for_isotope": False}


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
    parser.add_argument("--reload-count", type=int, default=1, help="Actual fresh-kernel reload/retirement cycles")
    parser.add_argument("--intake-manifest", type=Path, help="Verified genuine full-format fixture inventory for all public intake controls")
    parser.add_argument("--library-input", type=Path, help="An actual supported molecular input for library upload/frame/reopen proof")
    parser.add_argument("--scientific-input", type=Path, help="Authentic R2 ZIP or READ .hess for actual upload/reopen acceptance")
    parser.add_argument("--scientific-kind", choices=("r2_reference", "read_hessian"))
    parser.add_argument("--scientific-geometry", type=Path, help="The input's exact matching starting XYZ")
    parser.add_argument("--admission-guards", action="store_true", help="Exercise actual incomplete T9 and genuinely missing HPC scheduler admission")
    parser.add_argument("--native-hessian-calculation", action="store_true", help="Run actual local ORCA optimization/frequencies and inspect its generated Hessian")
    parser.add_argument("--require-stable-source", action="store_true", help="Reject source changes during a final frozen-source browser acceptance")
    args = parser.parse_args()
    if args.hosted and (not args.repository or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository)):
        parser.error("--hosted requires an authorized real --repository")
    if args.hosted and args.allow_unavailable_modules:
        parser.error("Full hosted entrypoint acceptance must require installed analysis components")
    if args.hosted and (args.admission_guards or args.native_hessian_calculation):
        parser.error("Native admission/Hessian acceptance is a separate local execution scope")
    if any((args.scientific_input, args.scientific_kind, args.scientific_geometry)) and not all(
            (args.scientific_input, args.scientific_kind, args.scientific_geometry)):
        parser.error("Scientific upload acceptance requires --scientific-input, --scientific-kind and --scientific-geometry")
    if not 1 <= args.reload_count <= 12:
        parser.error("--reload-count must be between 1 and 12")
    artifact = args.artifacts or Path(tempfile.mkdtemp(prefix="cochem-student-browser-"))
    artifact.mkdir(parents=True, exist_ok=True)
    for name, contents in (("student-water.xyz", WATER), ("student-water-b.xyz", SECOND_WATER),
                           ("student-complex.xyz", DIMER), ("student-invalid.xyz", INVALID)):
        (artifact / name).write_bytes(contents)
    source_paths = sorted(Path("src/cochem_base").rglob("*.py")) + [
        Path("tests/ui/student_entrypoint_browser_acceptance.py"), Path("ui/voila_layout/cochem_gui.py"),
        Path("scripts/student_voila.py"), Path("scripts/bootstrap_environment.py"),
    ]
    report = {"schema_version": "cochem.student-browser-acceptance/1", **origin_record(args),
              "hosted_execution_performed": False, "student_account_acceptance": False,
              "source_sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths},
              "interface_url": args.url, "input_sha256": {
                  name: hashlib.sha256(contents).hexdigest() for name, contents in
                  (("student-water.xyz", WATER), ("student-water-b.xyz", SECOND_WATER), ("student-complex.xyz", DIMER))}}
    page_errors, request_failures = [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.chromium, headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1600, "height": 1200}, accept_downloads=True)
        page.on("pageerror", lambda error: page_errors.append({"message": str(error), "stack": error.stack}))
        page.on("requestfailed", lambda request: request_failures.append({"url": request.url, "failure": request.failure}))
        page.on("response", lambda response: request_failures.append({"url": response.url, "http_status": response.status}) if response.status >= 400 else None)
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
            expect(selection).to_have_value("student-complex")
            expect(page.get_by_label("Geometry (XYZ):", exact=True)).to_have_value(DIMER.decode())
            expect(page.get_by_text(report["input_sha256"]["student-complex.xyz"], exact=True)).to_be_visible()
            page.get_by_label("Fragment atom groups:", exact=True).fill("1,2,3;4,5,6")
            page.get_by_role("button", name="Save geometry details", exact=True).click()
            expect(page.get_by_text("Saved complex details:", exact=False)).to_be_visible(timeout=15000)
            selected_status = page.locator("[data-cochem-input-id]")
            expect(selected_status).to_have_count(1)
            selected_identity = selected_status.get_attribute("data-cochem-input-id")
            assert uuid.UUID(selected_identity).hex == selected_identity
            original_input_ids = {"student-complex": selected_identity}
            custom_label = "student-complex-custom-label"
            page.get_by_label("Geometry label:", exact=True).fill(custom_label)
            page.get_by_role("button", name="Save geometry details", exact=True).click()
            expect(selection).to_have_value(custom_label)
            expect(selected_status).to_have_attribute("data-cochem-input-id", selected_identity)
            expect(page.get_by_label("Geometry (XYZ):", exact=True)).to_have_value(DIMER.decode())
            expect(page.get_by_label("Input type:", exact=True)).to_have_value("Complex starting geometry")
            expect(page.get_by_label("Charge:", exact=True)).to_have_value("0")
            expect(page.get_by_label("Multiplicity:", exact=True)).to_have_value("1")
            expect(page.get_by_label("Fragment atom groups:", exact=True)).to_have_value("1,2,3;4,5,6")
            expect(page.get_by_text(report["input_sha256"]["student-complex.xyz"], exact=True)).to_be_visible()
            upload_files(page, [artifact / "student-complex.xyz"])
            expect(selected_status).to_contain_text("Original bytes, atom order and isotope labels preserved.")
            expect(selection.locator("option")).to_have_count(3)
            expect(selection).to_have_value(custom_label)
            expect(selected_status).to_have_attribute("data-cochem-input-id", selected_identity)
            expect(page.get_by_label("Geometry label:", exact=True)).to_have_value(custom_label)
            expect(page.get_by_label("Geometry (XYZ):", exact=True)).to_have_value(DIMER.decode())
            expect(page.get_by_label("Input type:", exact=True)).to_have_value("Complex starting geometry")
            expect(page.get_by_label("Charge:", exact=True)).to_have_value("0")
            expect(page.get_by_label("Multiplicity:", exact=True)).to_have_value("1")
            expect(page.get_by_label("Fragment atom groups:", exact=True)).to_have_value("1,2,3;4,5,6")
            expect(page.get_by_text(report["input_sha256"]["student-complex.xyz"], exact=True)).to_be_visible()
            report["geometry_label_identity"] = {"selected_input_id": selected_identity,
                "custom_label": custom_label, "saved_label_displayed_immediately": True,
                "deduplicated_actual_upload_retained_same_id_and_label": True,
                "original_geometry_hash": report["input_sha256"]["student-complex.xyz"],
                "original_coordinates_roles_and_fragments_preserved": True}
            page.get_by_label("Geometry label:", exact=True).fill("student-complex")
            page.get_by_role("button", name="Save geometry details", exact=True).click()
            expect(selection).to_have_value("student-complex")
            expect(selected_status).to_have_attribute("data-cochem-input-id", selected_identity)
            selection.select_option(label="student-water")
            page.get_by_label("Input type:", exact=True).select_option(label="Monomer A")
            page.get_by_role("button", name="Save geometry details", exact=True).click()
            expect(page.get_by_text("Saved monomer_a details:", exact=False)).to_be_visible(timeout=15000)
            expect(page.get_by_label("Geometry (XYZ):", exact=True)).to_have_value(WATER.decode())
            original_input_ids["student-water"] = selected_status.get_attribute("data-cochem-input-id")
            assert uuid.UUID(original_input_ids["student-water"]).hex == original_input_ids["student-water"]
            upload_files(page, [artifact / "student-invalid.xyz"])
            expect(page.get_by_text("Rejected uploads:", exact=False)).to_be_visible(timeout=15000)
            expect(selection.locator("option")).to_have_count(3)
            expect(page.get_by_label("Geometry (XYZ):", exact=True)).to_have_value(WATER.decode())
            selection.select_option(label="student-complex")
            expect(page.get_by_label("Fragment atom groups:", exact=True)).to_have_value("1,2,3;4,5,6")
            selection.select_option(label="student-water")
            expect(page.get_by_label("Input type:", exact=True)).to_have_value("Monomer A")
            expect(page.get_by_text(report["input_sha256"]["student-water.xyz"], exact=True)).to_be_visible()
            selection.select_option(index=1)
            page.get_by_label("Input type:", exact=True).select_option(label="Monomer B")
            page.get_by_role("button", name="Save geometry details", exact=True).click()
            expect(page.get_by_text("Saved monomer_b details:", exact=False)).to_be_visible(timeout=15000)
            original_input_ids["student-water-b"] = selected_status.get_attribute("data-cochem-input-id")
            assert uuid.UUID(original_input_ids["student-water-b"]).hex == original_input_ids["student-water-b"]
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
            original_input_ids["student-water + student-water-b"] = selected_status.get_attribute("data-cochem-input-id")
            assert uuid.UUID(original_input_ids["student-water + student-water-b"]).hex == original_input_ids["student-water + student-water-b"]
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
            for _ in range(args.reload_count):
                reload_with_kernel_cleanup(page, report)
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
                # The public acknowledgement is published after all selected fields.
                # Bind it to the original UUID and bytes before observing the fields.
                expect(selected_status).to_have_count(1)
                expect(selected_status).to_have_attribute("data-cochem-input-id", original_input_ids[label])
                expect(selected_status.locator("code")).to_have_text(hashlib.sha256(original).hexdigest())
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
                page.get_by_text("Base Config", exact=True).click()
                select_prefix(page.get_by_label("Engine:", exact=True), "ORCA")
                page.get_by_text("Fragments / Frozen", exact=True).click()
                label = "Upload R2 references" if args.scientific_kind == "r2_reference" else "Upload READ Hessian"
                button = page.get_by_role("button", name=re.compile(re.escape(label) + r"(?:\s*\(\d+\))?$"))
                with page.expect_file_chooser(timeout=15000) as chooser:
                    button.click()
                chooser.value.set_files(str(args.scientific_input))
                expect(page.get_by_text(args.scientific_kind + " retained.", exact=True)).to_be_visible(timeout=120000)
                page.screenshot(path=str(artifact / "retained-scientific-input.png"), full_page=True)
                reload_with_kernel_cleanup(page, report)
                page.get_by_role("button", name="No Code Matrix", exact=True).click()
                selection = page.get_by_label("Starting geometry:", exact=True)
                expect(selection.locator("option")).to_have_count(5, timeout=30000)
                selection.select_option(label=args.scientific_geometry.stem)
                expect(page.get_by_label("Geometry (XYZ):", exact=True)).to_have_value(original_geometry.decode("utf-8-sig"))
                expect(page.get_by_text(hashlib.sha256(original_geometry).hexdigest(), exact=True)).to_be_visible()
                page.get_by_text("Fragments / Frozen", exact=True).click()
                expect(page.get_by_text("Retained R2/READ evidence was reopened after verifying its original file hashes.", exact=False)).to_be_visible(timeout=120000)
                if args.admission_guards and args.scientific_kind == "r2_reference":
                    page.get_by_text("Base Config", exact=True).click()
                    page.get_by_label("Screening (no product accuracy claim)", exact=True).check()
                    select_prefix(page.get_by_label("Theory Tier:", exact=True), "T5")
                    select_prefix(page.get_by_label("Method:", exact=True), "wB97M-V")
                    page.get_by_label("Basis Set:", exact=True).select_option(label="def2-QZVPP")
                    select_prefix(page.get_by_label("Solvation:", exact=True), "None")
                    page.get_by_text("Fragments / Frozen", exact=True).click()
                    r2 = page.get_by_label("Recipe R2: reference monomers and intermolecular relaxation", exact=True)
                    r2.check()
                    select_prefix(page.get_by_label("Calculation operation:", exact=True), "Single point")
                    page.get_by_text("Base Config", exact=True).click()
                    expect(page.get_by_text("Recipe R2 requires intermolecular optimization", exact=False).first).to_be_visible(timeout=30000)
                    expect(page.get_by_role("button", name="Run ORCA single point", exact=True)).to_be_disabled()
                    page.screenshot(path=str(artifact / "r2-singlepoint-disabled.png"), full_page=True)
                    select_prefix(page.get_by_label("Calculation operation:", exact=True), "Optimization")
                    page.get_by_text("Fragments / Frozen", exact=True).click()
                    r2.uncheck()
                    report["r2_operation_guard"] = {"genuine_reference_package_retained": True,
                        "single_point_disabled": True, "scientific_execution_performed": False}
                report["scientific_input"] = {"kind": args.scientific_kind,
                    "actual_browser_upload_and_fresh_kernel_recovery": True,
                    "original_input_sha256": hashlib.sha256(args.scientific_input.read_bytes()).hexdigest(),
                    "original_input_size_bytes": args.scientific_input.stat().st_size,
                    "geometry_sha256": hashlib.sha256(original_geometry).hexdigest(),
                    "scientific_execution_established_by_upload": False}
                page.screenshot(path=str(artifact / "restored-scientific-input.png"), full_page=True)
                page.get_by_text("Molecule Builder", exact=True).click()
                selection.select_option(label="student-water")
            if args.library_input:
                raw_library = args.library_input.read_bytes()
                library_sha = hashlib.sha256(raw_library).hexdigest()
                page.get_by_role("button", name="Input library", exact=True).click()
                library_upload = page.get_by_role("button", name=re.compile(r"Upload scientific inputs(?:\s*\(\d+\))?$"))
                expect(library_upload).to_be_enabled(timeout=15000)
                with page.expect_file_chooser(timeout=15000) as chooser:
                    library_upload.click()
                chooser.value.set_files(str(args.library_input))
                expect(page.get_by_text("Validated and retained 1 input(s).", exact=True)).to_be_visible(timeout=120000)
                retained = page.get_by_label("Retained input:", exact=True)
                select_prefix(retained, args.library_input.name)
                expect(page.get_by_label("Structure / frame:", exact=True).locator("option")).to_have_count(1)
                table = page.get_by_role("table", name="Verified retained scientific inputs", exact=True)
                expect(table).to_contain_text(library_sha)
                page.get_by_role("button", name="Use selected starting geometry", exact=True).click()
                expect(page.get_by_role("heading", name="No Code Matrix Configuration", exact=True)).to_be_visible(timeout=30000)
                page.get_by_text("Molecule Builder", exact=True).click()
                selection = page.get_by_label("Starting geometry:", exact=True)
                expect(selection).to_have_value(args.library_input.stem)
                normalized_geometry = page.get_by_label("Geometry (XYZ):", exact=True).input_value()
                assert normalized_geometry.splitlines()[0] == "3"
                reload_with_kernel_cleanup(page, report)
                page.get_by_role("button", name="Input library", exact=True).click()
                retained = page.get_by_label("Retained input:", exact=True)
                select_prefix(retained, args.library_input.name)
                expect(page.get_by_role("table", name="Verified retained scientific inputs", exact=True)).to_contain_text(library_sha)
                report["scientific_library"] = {"actual_browser_upload": True, "filename": args.library_input.name,
                    "original_sha256": library_sha, "canonical_frame_selected_without_code": True,
                    "original_and_frame_reopened_without_reupload": True,
                    "normalized_geometry_sha256": hashlib.sha256(normalized_geometry.encode()).hexdigest()}
                page.screenshot(path=str(artifact / "restored-scientific-library.png"), full_page=True)
                page.get_by_role("button", name="No Code Matrix", exact=True).click()
                page.get_by_text("Molecule Builder", exact=True).click()
                page.get_by_label("Starting geometry:", exact=True).select_option(label="student-water")
            if args.intake_manifest:
                accept_full_intake(page, args.intake_manifest, report, artifact)
            if args.admission_guards:
                accept_admission_guards(page, report, artifact)
            if args.native_hessian_calculation:
                accept_native_hessian_calculation(page, report, artifact, args.calculation_timeout)
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
            final_paths = sorted(Path("src/cochem_base").rglob("*.py")) + [
                Path("tests/ui/student_entrypoint_browser_acceptance.py"), Path("ui/voila_layout/cochem_gui.py"),
                Path("scripts/student_voila.py"), Path("scripts/bootstrap_environment.py"),
            ]
            report["source_after_sha256"] = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                                             for path in final_paths}
            report["source_unchanged_during_acceptance"] = report["source_after_sha256"] == report["source_sha256"]
            if args.require_stable_source:
                assert report["source_unchanged_during_acceptance"], "Scientific/interface source changed during frozen-source acceptance"
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
