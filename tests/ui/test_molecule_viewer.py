"""Real pinned-asset integrity and molecular-display input boundaries."""

import base64
import hashlib
import json
import re

import pytest

from cochem_base.interfaces.molecule_viewer import (
    molecule_viewer_html,
    renderer_url,
    static_asset_root,
    verify_renderer_asset,
)


def test_renderer_matches_reviewed_upstream_bytes_and_retains_licenses():
    asset = verify_renderer_asset()
    assert len(asset) == 537792
    assert (
        hashlib.sha256(asset).hexdigest()
        == "f7cc78921ae72e7623e89cdd111434f58c2efddd2ffda1cd212644b406fb8016"
    )
    directory = static_asset_root() / "cochem-base/molecule-viewer"
    manifest = json.loads((directory / "provenance.json").read_bytes())
    assert manifest["version"] == "2.5.5"
    assert manifest["archive_integrity"].startswith("sha512-")
    for name, record in manifest["files"].items():
        assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == record["sha256"]
    assert "BSD-3-Clause" in (directory / "LICENSE").read_text()
    assert "3dmol v2.5.5" in (directory / "3Dmol-min.js.LICENSE.txt").read_text()


def test_changed_missing_or_symlink_renderer_is_never_executed(tmp_path):
    source = tmp_path / "changed.js"
    source.write_bytes(verify_renderer_asset() + b"\n")
    with pytest.raises(ValueError, match="reviewed source"):
        verify_renderer_asset(source)
    with pytest.raises(ValueError, match="unavailable"):
        verify_renderer_asset(tmp_path / "missing.js")
    alias = tmp_path / "alias.js"
    alias.symlink_to(static_asset_root() / "cochem-base/molecule-viewer/3Dmol-2.5.5-min.js")
    with pytest.raises(ValueError, match="unavailable"):
        verify_renderer_asset(alias)


@pytest.mark.parametrize("prefix", ["/", "/chemistry/", "/user/student/proxy/8866/"])
def test_renderer_uses_the_actual_voila_client_prefix(prefix):
    url = renderer_url(prefix, asset=verify_renderer_asset())
    assert (
        url == prefix.rstrip("/") + "/voila/static/cochem-base/molecule-viewer/3Dmol-2.5.5-min.js"
    )


@pytest.mark.parametrize(
    "prefix",
    ["https://example.org/", "//example.org/", "../", "/../", "/?q=x", "/#x", "/</script>"],
)
def test_renderer_rejects_external_or_ambiguous_prefixes(prefix):
    with pytest.raises(ValueError, match="local absolute path"):
        renderer_url(prefix, asset=verify_renderer_asset())


def test_notebook_renderer_embeds_the_same_verified_asset_without_remote_network():
    payload = verify_renderer_asset()
    url = renderer_url("", asset=payload)
    assert url.startswith("data:text/javascript;base64,")
    assert base64.b64decode(url.split(",", 1)[1], validate=True) == payload


def test_geometry_comment_cannot_inject_html_or_rewrite_coordinates():
    original = "2\n</script><script>untrusted comment</script>\n13C 0 0 0\n18O 0 0 1.13\n"
    rendered = molecule_viewer_html(original)
    assert "untrusted comment" not in rendered
    config = json.loads(re.search(r"const config = (.*);", rendered).group(1))
    atoms = [row.split() for row in config["xyz"].splitlines()[2:]]
    assert [row[0] for row in atoms] == ["C", "O"]
    assert [[float(number) for number in row[1:]] for row in atoms] == [[0, 0, 0], [0, 0, 1.13]]
    assert 'role="status"' in rendered
