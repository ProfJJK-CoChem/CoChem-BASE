"""Exercise the genuine renderer, actual HTTP failures and optional live GUI.

Maintainer acceptance only: no calculations, credentials or browser-session
reuse. An unavailable static URL, modified asset and delayed server response
exercise real browser failure boundaries; no network responses are fabricated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

from cochem_base.interfaces.molecule_viewer import molecule_viewer_html, verify_renderer_asset

WATER = "3\nDisplay acceptance starting geometry\nO 0 0 0\nH 0 -.757 .587\nH 0 .757 .587\n"
ISOTOPES = "2\nExplicit isotope display check\n13C 0 0 0\n18O 0 0 1.13\n"
ATOMS = [
    {"elem": "O", "x": 0, "y": 0, "z": 0},
    {"elem": "H", "x": 0, "y": -0.757, "z": 0.587},
    {"elem": "H", "x": 0, "y": 0.757, "z": 0.587},
]


def _atoms(container):
    return container.evaluate("""el => el._cochemMoleculeViewer.getModel().selectedAtoms({})
        .map(atom => ({elem:atom.elem,x:atom.x,y:atom.y,z:atom.z}))""")


def _visible_pixels(canvas, destination: Path) -> dict:
    from PIL import Image

    canvas.screenshot(path=str(destination))
    with Image.open(destination) as picture:
        pixels = picture.convert("RGB")
        colors = pixels.getcolors(pixels.width * pixels.height)
        nonwhite = sum(count for count, rgb in colors if min(rgb) < 230)
    assert len(colors) >= 8 and nonwhite > 100, "The canvas contains no visible molecule"
    return {
        "colors": len(colors),
        "nonwhite_pixels": nonwhite,
        "screenshot_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
    }


def accept(chromium: str, artifacts: Path, gui_url: str | None = None) -> dict:
    artifacts.mkdir(parents=True, exist_ok=False)
    asset = verify_renderer_asset()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            return

        def get_payload(self):
            path = urlsplit(self.path).path
            if path in {"/good/", "/missing/", "/integrity/", "/timeout/"}:
                return "text/html; charset=utf-8", molecule_viewer_html(
                    WATER, base_url=path
                ).encode()
            if path.endswith("/voila/static/cochem-base/molecule-viewer/3Dmol-2.5.5-min.js"):
                if path.startswith("/good/"):
                    return "text/javascript", asset
                if path.startswith("/integrity/"):
                    return "text/javascript", asset + b"\n/* deliberately changed test asset */"
                if path.startswith("/timeout/"):
                    time.sleep(12)
                    return "text/javascript", asset
            return None

        def do_GET(self):
            payload = self.get_payload()
            if payload is None:
                self.send_error(404)
                return
            content_type, data = payload
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass  # The actual finite-timeout client can close its connection.

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    report = {
        "scope": "Actual molecular-display and browser failure checks; no chemistry or student account qualification",
        "renderer_sha256": hashlib.sha256(asset).hexdigest(),
        "checks": {},
    }
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True, executable_path=chromium, args=["--disable-dev-shm-usage"]
            )
            try:
                for name in ("good", "missing", "integrity", "timeout", "offline"):
                    context = browser.new_context(
                        viewport={"width": 650, "height": 400}, offline=name == "offline"
                    )
                    try:
                        page = context.new_page()
                        observed = {"page_errors": [], "external_requests": []}
                        page.on(
                            "pageerror",
                            lambda error, record=observed: record["page_errors"].append(str(error)),
                        )
                        page.on(
                            "request",
                            lambda request, record=observed: (
                                record["external_requests"].append(request.url)
                                if urlsplit(request.url).scheme in {"http", "https"}
                                and urlsplit(request.url).hostname not in {"localhost", "127.0.0.1"}
                                else None
                            ),
                        )
                        if name == "offline":
                            page.set_content(
                                molecule_viewer_html(WATER, base_url=""), wait_until="load"
                            )
                        else:
                            page.goto(
                                f"http://127.0.0.1:{server.server_port}/{name}/",
                                wait_until="domcontentloaded",
                            )
                        container = page.locator("[data-cochem-viewer-state]")
                        if name in {"good", "offline"}:
                            expect(container).to_have_attribute(
                                "data-cochem-viewer-state", "rendered", timeout=15000
                            )
                            assert _atoms(container) == ATOMS
                            observed["atoms"] = _atoms(container)
                            observed["pixels"] = _visible_pixels(
                                container.locator("canvas"), artifacts / (name + ".png")
                            )
                        else:
                            if name == "timeout":
                                expect(page.get_by_role("status")).to_have_text(
                                    "Loading structure preview…"
                                )
                            expect(container).to_have_attribute(
                                "data-cochem-viewer-state", "error", timeout=15000
                            )
                            expect(page.get_by_role("alert")).to_contain_text(
                                "Your geometry is still available"
                            )
                            assert container.locator("canvas").count() == 0
                            page.screenshot(path=str(artifacts / (name + ".png")))
                        observed["state"] = container.get_attribute("data-cochem-viewer-state")
                        observed["status_text"] = page.locator(
                            '[aria-live="polite"]'
                        ).text_content()
                        assert observed["page_errors"] == []
                        assert observed["external_requests"] == []
                        report["checks"][name] = observed
                    finally:
                        context.close()
                from cochem.gui.widgets.touch_3d_viewer import Touch3DViewer

                touch = Touch3DViewer(
                    [atom["elem"] for atom in ATOMS],
                    [[atom[axis] for axis in ("x", "y", "z")] for atom in ATOMS],
                )
                context = browser.new_context(
                    viewport={"width": 650, "height": 500}, offline=True, has_touch=True
                )
                try:
                    page = context.new_page()
                    observed = {"page_errors": [], "network_requests": []}
                    page.on("pageerror", lambda error: observed["page_errors"].append(str(error)))
                    page.on(
                        "request", lambda request: observed["network_requests"].append(request.url)
                    )
                    page.set_content(touch.to_html_bundle(), wait_until="load")
                    expect(page.locator("canvas")).to_be_visible()
                    page.wait_for_timeout(250)
                    observed["initial_view"] = page.evaluate("cochemViewer.getView()")
                    observed["initial_pixels"] = _visible_pixels(
                        page.locator("canvas"), artifacts / "touch-initial.png"
                    )
                    session = context.new_cdp_session(page)
                    session.send(
                        "Input.dispatchTouchEvent",
                        {"type": "touchStart", "touchPoints": [{"x": 250, "y": 250, "id": 1}]},
                    )
                    session.send(
                        "Input.dispatchTouchEvent",
                        {"type": "touchMove", "touchPoints": [{"x": 330, "y": 290, "id": 1}]},
                    )
                    session.send(
                        "Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []}
                    )
                    page.wait_for_timeout(250)
                    observed["drag_view"] = page.evaluate("cochemViewer.getView()")
                    quaternion = page.evaluate("cochemTouchController.getCameraState().quaternion")
                    assert observed["drag_view"][4:8] != observed["initial_view"][4:8]
                    assert observed["drag_view"][4:8] == quaternion
                    observed["drag_pixels"] = _visible_pixels(
                        page.locator("canvas"), artifacts / "touch-drag.png"
                    )
                    assert (
                        observed["drag_pixels"]["screenshot_sha256"]
                        != observed["initial_pixels"]["screenshot_sha256"]
                    )
                    page.get_by_role("button", name="Reset", exact=True).click()
                    page.wait_for_timeout(250)
                    observed["reset_view"] = page.evaluate("cochemViewer.getView()")
                    assert observed["reset_view"][4:8] == [0, 0, 0, 1]
                    observed["atoms"] = page.evaluate(
                        "cochemViewer.getModel().selectedAtoms({}).map(a=>({elem:a.elem,x:a.x,y:a.y,z:a.z}))"
                    )
                    assert observed["atoms"] == ATOMS
                    assert observed["page_errors"] == []
                    assert observed["network_requests"] == []
                    observed["csp"] = page.locator(
                        'meta[http-equiv="Content-Security-Policy"]'
                    ).get_attribute("content")
                    report["checks"]["touch_offline"] = observed
                finally:
                    context.close()
                if gui_url:
                    context = browser.new_context(viewport={"width": 1300, "height": 900})
                    try:
                        page = context.new_page()
                        observed = {"page_errors": [], "renderer_responses": []}
                        page.on(
                            "pageerror", lambda error: observed["page_errors"].append(str(error))
                        )
                        page.on(
                            "response",
                            lambda response: (
                                observed["renderer_responses"].append(
                                    {"url": response.url, "status": response.status}
                                )
                                if "3Dmol-2.5.5-min.js" in response.url
                                else None
                            ),
                        )
                        response = page.goto(gui_url, wait_until="domcontentloaded", timeout=60000)
                        observed["csp"] = response.headers.get("content-security-policy")
                        container = page.locator("[data-cochem-viewer-state=rendered]")
                        expect(container).to_be_visible(timeout=120000)
                        assert _atoms(container) == ATOMS
                        observed["pixels"] = _visible_pixels(
                            container.locator("canvas"), artifacts / "actual-gui.png"
                        )
                        page.get_by_label("Geometry (XYZ):", exact=True).fill(ISOTOPES)
                        expect(
                            page.locator(
                                '[data-cochem-viewer-state=rendered][data-cochem-atom-count="2"]'
                            )
                        ).to_be_visible(timeout=15000)
                        observed["isotope_display_atoms"] = _atoms(
                            page.locator("[data-cochem-viewer-state=rendered]")
                        )
                        assert observed["isotope_display_atoms"] == [
                            {"elem": "C", "x": 0, "y": 0, "z": 0},
                            {"elem": "O", "x": 0, "y": 0, "z": 1.13},
                        ]
                        assert observed["page_errors"] == []
                        assert observed["renderer_responses"] and all(
                            item["status"] == 200 for item in observed["renderer_responses"]
                        )
                        report["checks"]["actual_gui"] = observed
                    finally:
                        context.close()
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    (artifacts / "acceptance.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chromium", default="/usr/bin/chromium")
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument(
        "--url", help="Optional own live GUI fixture with the actual geometry editor and viewer"
    )
    arguments = parser.parse_args()
    print(json.dumps(accept(arguments.chromium, arguments.artifacts, arguments.url), indent=2))
