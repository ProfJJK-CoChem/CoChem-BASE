"""Display supplied geometry with the genuine, pinned local 3Dmol renderer.

Drawn bonds aid visual inspection; they are not calculated bond orders. This
module does not optimize coordinates or derive electronic observables.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import uuid
from pathlib import Path
from urllib.parse import urlsplit

_ASSET = "cochem-base/molecule-viewer/3Dmol-2.5.5-min.js"
_SHA256 = "f7cc78921ae72e7623e89cdd111434f58c2efddd2ffda1cd212644b406fb8016"
_SRI = "sha256-" + base64.b64encode(bytes.fromhex(_SHA256)).decode("ascii")


def static_asset_root() -> Path:
    """BASE-owned files exposed by Voilà's existing static-file handler."""
    return Path(__file__).resolve().parent / "static"


def verify_renderer_asset(path: Path | None = None) -> bytes:
    """Reject missing or changed renderer bytes against the reviewed source pin."""
    source = path if path is not None else static_asset_root() / _ASSET
    if source.is_symlink() or not source.is_file():
        raise ValueError("The verified molecular renderer is unavailable.")
    payload = source.read_bytes()
    if hashlib.sha256(payload).hexdigest() != _SHA256:
        raise ValueError("The molecular renderer differs from its reviewed source.")
    return payload


def renderer_url(base_url: str, *, asset: bytes) -> str:
    """Honor Voilà's supported client prefix; ordinary notebooks work offline."""
    if not base_url:
        return "data:text/javascript;base64," + base64.b64encode(asset).decode("ascii")
    parsed = urlsplit(base_url)
    if (
        not base_url.startswith("/")
        or base_url.startswith("//")
        or parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or "\\" in base_url
        or any(ord(char) < 32 for char in base_url)
        or any(char in base_url for char in "<>\"'")
        or ".." in base_url.split("/")
    ):
        raise ValueError("The dashboard URL prefix must be a local absolute path.")
    return base_url.rstrip("/") + "/voila/static/" + _ASSET


def molecule_viewer_html(xyz_data: str, *, base_url: str | None = None) -> str:
    """Return an accessible preview with bounded loading and explicit failures."""
    from cochem_base.geometry.nuclide_geometry import parse_geometry_identity

    identity = parse_geometry_identity(xyz_data)
    xyz = (
        str(len(identity.elements))
        + "\nBASE display geometry; nuclear labels retained in input\n"
        + "\n".join(
            element + " " + " ".join(format(value, ".17g") for value in row)
            for element, row in zip(identity.elements, identity.coordinates_angstrom, strict=True)
        )
        + "\n"
    )
    prefix = os.environ.get("VOILA_BASE_URL", "") if base_url is None else base_url
    source_url = renderer_url(prefix, asset=verify_renderer_asset())
    identifier = "cochem-molecule-" + uuid.uuid4().hex
    config = json.dumps(
        {"id": identifier, "xyz": xyz, "url": source_url, "integrity": _SRI, "digest": _SHA256},
        allow_nan=False,
    )
    return f"""<div class="cochem-molecule-preview">
<p id="{identifier}-status" role="status" aria-live="polite">Loading structure preview…</p>
<div id="{identifier}" data-cochem-viewer-state="loading" role="img"
 aria-label="Molecular structure preview of {len(identity.elements)} atoms; visual bonds are not calculated bond orders."
 style="position:relative;width:100%;height:260px;"></div>
</div><script>
(function() {{
  const config = {config};
  const container = document.getElementById(config.id);
  const status = document.getElementById(config.id + '-status');
  if (!container || !status) return;
  const cache = window._cochemMoleculeRenderers || (window._cochemMoleculeRenderers = Object.create(null));
  function unavailable() {{
    if (!container.isConnected) return;
    container.replaceChildren();
    container.dataset.cochemViewerState = 'error';
    status.setAttribute('role', 'alert');
    status.textContent = 'Structure preview could not load. Your geometry is still available. Choose the geometry again to retry.';
  }}
  function load() {{
    if (cache[config.digest]) return cache[config.digest];
    const promise = new Promise(function(resolve, reject) {{
      const script = document.createElement('script');
      let settled = false;
      function finish(error) {{
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        script.onload = script.onerror = null;
        if (error) {{ script.remove(); reject(error); }}
        else if (window.$3Dmol && typeof window.$3Dmol.createViewer === 'function') resolve(window.$3Dmol);
        else {{ script.remove(); reject(new Error('Renderer API is absent.')); }}
      }}
      const timer = setTimeout(function() {{ finish(new Error('Renderer load timed out.')); }}, 10000);
      script.async = true;
      script.src = config.url;
      script.integrity = config.integrity;
      script.crossOrigin = 'anonymous';
      script.onload = function() {{ finish(null); }};
      script.onerror = function() {{ finish(new Error('Renderer could not load.')); }};
      document.head.appendChild(script);
    }});
    cache[config.digest] = promise;
    promise.catch(function() {{ if (cache[config.digest] === promise) delete cache[config.digest]; }});
    return promise;
  }}
  load().then(function(library) {{
    if (!container.isConnected) return;
    const viewer = library.createViewer(container, {{backgroundColor:'white'}});
    const model = viewer.addModel(config.xyz, 'xyz');
    viewer.setStyle({{}}, {{stick:{{}},sphere:{{radius:0.4}}}});
    viewer.zoomTo();
    viewer.rotate(25, 'y');
    viewer.rotate(15, 'x');
    viewer.render();
    if (!container.querySelector('canvas')) throw new Error('Renderer created no canvas.');
    container._cochemMoleculeViewer = viewer;
    container.dataset.cochemAtomCount = String(model.selectedAtoms({{}}).length);
    container.dataset.cochemViewerState = 'rendered';
    status.textContent = 'Structure preview ready.';
  }}).catch(unavailable);
}})();
</script>"""
