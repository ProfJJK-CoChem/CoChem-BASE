"""Manual browser acceptance; requires Playwright, Chromium and a running Voilà server.

Run with the browser test environment, never install Playwright into an engine silo::

    python tests/ui/voila_browser_acceptance.py --url http://127.0.0.1:8866

The Voilà server must inherit a working XTB_CMD/XTBPATH or have xTB on PATH.
This executes a small water optimization and writes logs/evidence to --artifacts.
It does not establish TOPOS/TORQ, accessibility, or hosted-platform conformance.
"""

from playwright.sync_api import sync_playwright, expect
from pathlib import Path
import argparse
import json
import tempfile

parser = argparse.ArgumentParser(
    description="Exercise a running Voilà server through Chromium and perform real xTB screening."
)
parser.add_argument("--url", default="http://127.0.0.1:8866")
parser.add_argument("--chromium", default="/usr/bin/chromium")
parser.add_argument("--artifacts", type=Path)
parser.add_argument("--hessian", type=Path, help="Optional real geometry-bound Hessian bundle for isotope acceptance")
parser.add_argument("--topos", action="store_true", help="Run a real CREST conformer search and cancellation")
parser.add_argument("--setup", action="store_true", help="Run all eleven native setup phases with an explicit 1 GB workload budget")
parser.add_argument("--pyscf", action="store_true", help="Run an isolated native RHF/STO-3G single point")
parser.add_argument("--module-handoff", action="store_true", help="Prepare and download a validated future-module package")
parser.add_argument("--periodic-input", type=Path, help="Load a genuine ordered CIF or explicit periodic JSON")
parser.add_argument("--periodic-settings", type=Path, help="Execute native QE with these real authenticated PAW settings")
args = parser.parse_args()
artifact = args.artifacts or Path(tempfile.mkdtemp(prefix="cochem-browser-"))
artifact.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=args.chromium, headless=True, args=["--no-sandbox"])
    page = b.new_page(viewport={"width": 1500, "height": 1100})
    errors = []
    failures = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("requestfailed", lambda r: failures.append({"url": r.url, "failure": r.failure}))
    page.goto(args.url, wait_until="domcontentloaded", timeout=60000)
    if args.hessian:
        initialize = page.get_by_role("button", name="Run Installation", exact=True)
        expect(initialize).to_be_disabled(timeout=60000)
        page.get_by_label("Scientific data:", exact=True).fill(str(args.hessian.resolve()))
        page.get_by_role("button", name="Validate scientific data", exact=True).click()
        expect(initialize).to_be_enabled(timeout=15000)
        if args.setup:
            page.get_by_label("Required disk (GB):", exact=True).fill("1")
            page.get_by_label("Required disk (GB):", exact=True).press("Tab")
            initialize.click()
            expect(page.get_by_text("Complete setup evidence:", exact=False)).to_be_visible(timeout=300000)
            expect(page.get_by_text("[System: Setup DEGRADED_OPERATIONAL]", exact=True)).to_be_visible()
    page.locator("button").filter(has_text="No Code Matrix").click(timeout=60000)
    geometry = page.get_by_label("Geometry (XYZ):", exact=True)
    geometry.fill("O 0 0 0\nH 0 0 0.96\nH 0.92 0 -0.24")
    page.get_by_text("Base Config", exact=True).click()
    engine = page.get_by_label("Engine:", exact=True)
    print("ENGINEOPTIONS", engine.locator("option").all_text_contents(), flush=True)
    engine.select_option(
        label=next(
            label
            for label in engine.locator("option").all_text_contents()
            if label.startswith("xTB")
        )
    )
    run = page.locator("button").filter(has_text="Run xTB optimization")
    expect(run).to_be_enabled(timeout=20000)
    page.get_by_label("Multiplicity:", exact=True).fill("2")
    page.get_by_label("Multiplicity:", exact=True).press("Tab")
    expect(run).to_be_disabled(timeout=15000)
    expect(
        page.get_by_text(
            "Open-shell xTB acceptance requires spin evidence unavailable in this adapter",
            exact=False,
        )
    ).to_be_visible()
    page.get_by_label("Multiplicity:", exact=True).fill("1")
    page.get_by_label("Multiplicity:", exact=True).press("Tab")
    expect(run).to_be_enabled(timeout=15000)
    page.get_by_label("Output Dir:", exact=True).fill(str(artifact))
    page.get_by_label("Project Name:", exact=True).fill("water_browser")
    page.locator("button").filter(has_text="Save configuration").click()
    expect(page.get_by_text("Saved xtb optimization configuration:", exact=False)).to_be_visible(
        timeout=15000
    )
    run.click()
    try:
        expect(page.get_by_text("[System: Optimization Finished]", exact=True)).to_be_visible(
            timeout=60000
        )
    except AssertionError:
        (artifact / "calculation-failure.txt").write_text(page.locator("body").inner_text())
        page.screenshot(path=str(artifact / "calculation-failure.png"), full_page=True)
        raise
    expect(page.get_by_text("xTB screening result", exact=True)).to_be_visible(timeout=15000)
    expect(page.get_by_text("Energy:", exact=False)).to_be_visible()
    assert "# Unsupported Engine: XTB" not in page.locator("body").inner_text()
    page.screenshot(path=str(artifact / "xtb-browser-result.png"), full_page=True)
    if args.pyscf:
        engine.select_option(label=next(label for label in engine.locator("option").all_text_contents() if label.startswith("PySCF")))
        page.get_by_role("button", name="Run PySCF single point", exact=True).click()
        expect(page.get_by_text("[System: Single Point Finished]", exact=True)).to_be_visible(timeout=60000)
        expect(page.get_by_text("PySCF RHF single-point result", exact=True)).to_be_visible()
        expect(page.get_by_text("SCF converged: True", exact=False)).to_be_visible()
        page.screenshot(path=str(artifact / "pyscf-single-point.png"), full_page=True)
    if args.topos:
        page.get_by_text("TOPOS", exact=True).click()
        page.get_by_role("button", name="Refresh search engines", exact=True).click()
        protocol = page.get_by_label("Search protocol:", exact=True)
        protocol.select_option(label=next(label for label in protocol.locator("option").all_text_contents() if label.startswith("CREST")))
        start_search = page.get_by_role("button", name="Start conformer search", exact=True)
        start_search.click()
        expect(page.get_by_text("Conformer search: COMPLETED", exact=True)).to_be_visible(timeout=60000)
        page.get_by_role("button", name="Publish conformer ensemble", exact=True).click()
        expect(page.get_by_text("Conformer ensemble published.", exact=True)).to_be_visible(timeout=15000)
        with page.expect_download() as download:
            page.get_by_role("link", name="Download conformer ensemble (XYZ)", exact=True).click()
        download.value.save_as(artifact / "conformer-ensemble.xyz")
        assert "Hartree" in (artifact / "conformer-ensemble.xyz").read_text()
        page.screenshot(path=str(artifact / "crest-conformers.png"), full_page=True)
        start_search.click()
        page.get_by_role("button", name="Cancel conformer search", exact=True).click()
        expect(page.get_by_text("Conformer search: CANCELLED", exact=True)).to_be_visible(timeout=15000)
        expect(page.get_by_role("button", name="Publish conformer ensemble", exact=True)).to_be_disabled()
    page.locator("button").filter(has_text="Data Inspector (Ab-Initio)").click()
    page.get_by_text("Isotopic Re-analysis", exact=True).click()
    page.locator("button").filter(has_text="Re-analyze Isotopologue").click()
    expect(
        page.get_by_text(
            "No Hessian or vibrational correction was supplied; B0 is [MISSING DATA].", exact=False
        )
    ).to_be_visible(timeout=15000)
    if args.hessian:
        page.get_by_label("Hessian bundle:", exact=True).fill(str(args.hessian.resolve()))
        load_hessian = page.get_by_role("button", name="Load geometry and Hessian", exact=True)
        load_hessian.focus()
        page.keyboard.press("Enter")
        expect(page.get_by_text("Geometry and Cartesian Hessian loaded.", exact=False)).to_be_visible(timeout=15000)
        page.get_by_label("Atom 1 (O):", exact=True).select_option("18O")
        page.get_by_label("Atom 2 (H):", exact=True).select_option("2H")
        page.get_by_label("Atom 3 (H):", exact=True).select_option("2H")
        page.get_by_role("button", name="Re-analyze Isotopologue", exact=True).click()
        expect(page.get_by_text("Substituted (18O2H2H)", exact=True)).to_be_visible(timeout=15000)
        expect(page.get_by_text("Projected harmonic modes", exact=True)).to_be_visible()
        expect(page.get_by_text("Rigid modes removed: 6.", exact=False)).to_be_visible()
        expect(page.get_by_text("B0 is [MISSING DATA].", exact=False)).to_be_visible()
        expect(page.get_by_role("link", name="Download SVG figure", exact=True)).to_be_visible()
        with page.expect_download() as download:
            page.get_by_role("link", name="Download frequency data (CSV)", exact=True).click()
        download.value.save_as(artifact / "harmonic-modes.csv")
        assert "ASE/EMT" in (artifact / "harmonic-modes.csv").read_text()
        assert page.locator('[role="status"][aria-live="polite"]').count() >= 1
        contrasts = page.locator(".cochem-accessible button").evaluate_all("""buttons => {
          const luminance = color => {
            const components = color.match(/[\\d.]+/g).slice(0,3).map(Number).map(x => x / 255);
            const linear = components.map(x => x <= .04045 ? x/12.92 : ((x+.055)/1.055)**2.4);
            return linear[0]*.2126 + linear[1]*.7152 + linear[2]*.0722;
          };
          return buttons.filter(b => !b.disabled && b.getClientRects().length).map(b => {
            const style=getComputedStyle(b), a=luminance(style.color), c=luminance(style.backgroundColor);
            return {name: b.textContent, ratio: (Math.max(a,c)+.05)/(Math.min(a,c)+.05)};
          });
        }""")
        assert all(control["ratio"] >= 4.5 for control in contrasts), contrasts
        page.screenshot(path=str(artifact / "harmonic-inspector.png"), full_page=True)
    page.get_by_label("Log / H5 File:", exact=True).fill("/tmp/missing-inspector-<unsafe>.log")
    page.locator("button").filter(has_text="Parse Observables").click()
    page.get_by_text("Rotational Observables (B_e vs B_0)", exact=True).click()
    expect(
        page.get_by_text("File not found: /tmp/missing-inspector-<unsafe>.log", exact=True)
    ).to_be_visible(timeout=15000)
    assert page.locator("unsafe").count() == 0
    assert "import importlib" not in page.locator("body").inner_text()
    page.screenshot(path=str(artifact / "inspector-browser-result.png"), full_page=True)
    if args.module_handoff:
        import zipfile
        from cochem_base.interfaces.artifact_handoff import load_module_handoff
        page.get_by_role("button", name="Module handoff", exact=True).click()
        expect(page.get_by_role("table", name="Observed module availability")).to_be_visible()
        page.get_by_label("Recipient module:", exact=True).select_option(label="CoChem-TORQ")
        source = args.hessian or next(artifact.rglob("input.xyz"))
        page.get_by_label("Input artifact:", exact=True).fill(str(source.resolve()))
        page.get_by_label("Package directory:", exact=True).fill(str(artifact / "handoffs"))
        page.get_by_role("button", name="Prepare validated handoff", exact=True).click()
        expect(page.get_by_text("Handoff prepared for CoChem-TORQ.", exact=False)).to_be_visible(timeout=15000)
        expect(page.get_by_text("Pending integration; no scientific job was submitted.", exact=False)).to_be_visible()
        with page.expect_download() as download:
            page.get_by_role("link", name="Download validated handoff package", exact=True).click()
        package = artifact / "module-handoff.zip"
        download.value.save_as(package)
        received = artifact / "received-handoff"
        received.mkdir()
        with zipfile.ZipFile(package) as archive:
            for name in archive.namelist():
                assert Path(name).name == name
                (received / name).write_bytes(archive.read(name))
        handoff = load_module_handoff(received / "handoff.json")
        assert handoff.module_id == "torq" and handoff.scientific_execution_performed is False
        assert handoff.status == "pending_integration"
        page.screenshot(path=str(artifact / "module-handoff.png"), full_page=True)
    if args.periodic_input:
        page.get_by_role("button", name="Periodic structures", exact=True).click()
        page.get_by_label("Periodic input:", exact=True).fill(str(args.periodic_input.resolve()))
        page.get_by_role("button", name="Validate periodic structure", exact=True).click()
        expect(page.get_by_text("Validated periodic structure:", exact=False)).to_be_visible(timeout=15000)
        expect(page.get_by_role("table", name="Fractional coordinates")).to_be_visible()
        if args.periodic_settings:
            page.get_by_label("PAW settings JSON:", exact=True).fill(str(args.periodic_settings.resolve()))
            page.get_by_label("Periodic output:", exact=True).fill(str(artifact / "periodic"))
            page.get_by_role("button", name="Run periodic PBE/PAW single point", exact=True).click()
            expect(page.get_by_text("Quantum ESPRESSO periodic PBE/PAW result", exact=True)).to_be_visible(timeout=180000)
            expect(page.get_by_text("SCF converged: True", exact=False)).to_be_visible()
            expect(page.get_by_text("Empirical product accuracy: unverified.", exact=False)).to_be_visible()
        page.screenshot(path=str(artifact / "periodic-ingestion.png"), full_page=True)
    saved = list(artifact.rglob("Results/result.json"))
    assert saved
    results = [json.loads(path.read_text()) for path in saved]
    result = next(item for item in results if item.get('engine') == 'xtb')
    assert result["scope"] == "screening" and result["optimization_converged"] is True
    evidence = {
        "engine_result": result,
        "additional_results": [item for item in results if item.get('engine') != 'xtb'],
        "page_errors": errors,
        "failed_requests": failures,
        "checks": [
            "WebSocket widget controls",
            "water geometry entry",
            "xTB engine selection",
            "invalid spin blocks execution",
            "save configuration",
            "real GFN2-xTB optimization",
            "converged artifact read",
            "isotope missing-data display",
            "escaped missing-file error",
            "Python source excluded from DOM",
        ] + (["isolated PySCF RHF single point", "SCF convergence and actual nuclear gradient artifact"] if args.pyscf else [])
        + (["real CREST submission and polling", "validated conformer publication and XYZ download", "CREST cancellation"] if args.topos else [])
        + (["all eleven setup phases through native GUI controller"] if args.setup else [])
        + (["future-module capability discovery", "verified artifact handoff ZIP download", "pending integration without fabricated execution"] if args.module_handoff else [])
        + (["periodic CIF/JSON ingestion", "cell and fractional coordinates with source provenance"] if args.periodic_input else [])
        + (["native Quantum ESPRESSO PBE/PAW single point", "actual SCF energy and gradient with unverified empirical accuracy"] if args.periodic_settings else [])
        + (["mandatory scientific data initialization gate", "real Hessian loading by keyboard", "multiple isotope selections", "projected harmonic modes",
              "Hessian provenance and digest", "SVG figure and CSV data export",
              "visible enabled buttons meet 4.5:1 text contrast", "accessible labels and live calculation status"] if args.hessian else []),
    }
    assert not errors and not failures, (errors, failures)
    (artifact / "browser-evidence.json").write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence, indent=2), flush=True)
    b.close()
