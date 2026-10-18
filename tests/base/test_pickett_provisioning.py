"""The pinned JPL Pickett build: manifest identity, hardened retrieval, receipts and setup recovery.

Every control here is a labelled text file; no test downloads from JPL, builds a program or
substitutes anything for SPFIT, SPCAT, DPFIT or DPCAT. The real build runs in the workflow
``pickett_build.yml`` and in the Codespaces setup (CoChem-SpycFit D-SPYC-17, D-SPYC-26).
"""

from __future__ import annotations

import http.server
import json
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from scripts.hosted_dashboard import prepare_pickett_programs, runtime_environment
from scripts.provision_pickett import (
    DEFAULT_MANIFEST,
    PROGRAMS,
    RECEIPT_ENVIRONMENT,
    RECEIPT_NAME,
    RECEIPT_SCHEMA,
    REPOSITORY_ROOT,
    PickettProvisioningError,
    fetch_pinned,
    load_manifest,
    load_receipt,
    locate_receipt,
    program_path,
    provision,
    run_acceptance,
    sha256_file,
    status,
    verify,
)

# Bytes pinned on 2026-10-17/18 and recorded in CoChem-SpycFit D-SPYC-17 and D-SPYC-26;
# TORQ pins the same Makefile and spinv.c (CoChem-TORQ pickett_backend.py).
PINNED = {
    "Makefile": ("2192f0ae5827a2c84fa1c2224651f054bb87d75c4e6601f2e4cce6b6d4530f26", 2006),
    "spinv.c": ("cd07e6b51f47bfa9939a4710ab0c4ae9629c7709362c15f886d9c65da3ce7e4a", 142846),
    "dpi.c": ("a0e7cccff1ff981313b57efcf4ff906f130f0957b82eb6ffd89bcf76df66fdde", 17133),
    "hcotst.par": ("76b4c910576009cefecf116b368177060195a067ac16554b2c5381123ecf441d", 1160),
    "hco.cat": ("795308ba421e4063d9f9eeb4429d4c53c1d653f2bfab6ad00cb39a724eb53c84", 60345),
    "no.cat": ("371e773ef873eef0bd5317bb845681e0670bb893eeb91ef8adfe8a19559a77ce", 90480),
}


def test_pin_manifest_identity_and_rights_are_recorded():
    manifest = load_manifest()
    assert manifest["upstream_url"] == "https://spec.jpl.nasa.gov/ftp/pub/calpgm/"
    assert tuple(manifest["programs"]) == PROGRAMS
    assert manifest["build_command"] == ["make", "-j1", "spfit", "spcat", "dpfit", "dpcat"]
    files = {record["path"]: (record["sha256"], record["size"]) for record in [*manifest["sources"], *manifest["examples"]]}
    for name, identity in PINNED.items():
        assert files[name] == identity, name
    assert len(manifest["sources"]) == 26 and len(manifest["examples"]) == 11
    assert {entry["path"] for entry in manifest["unavailable_upstream"]} == {"hco.var", "hcotst.var", "no.var"}
    assert manifest["acceptance"]["hco"]["parameter_file"] == "hcotst.par"
    assert manifest["acceptance"]["no"]["programs"] == ["dpfit", "dpcat"]
    rights = manifest["rights"]
    assert rights["redistribution_permitted"] is False and rights["bundled"] is False
    assert "California Institute of Technology" in rights["source_notice"]
    assert "freely available" in rights["site_statement"]
    assert rights["pi_use_rights"] == "unrecorded"
    assert manifest["upstream_prebuilt_files_retrieved"] is False


@pytest.mark.parametrize("mutate, message", [
    (lambda m: m.__setitem__("upstream_url", "https://example.org/calpgm/"), "JPL calpgm directory only"),
    (lambda m: m.__setitem__("programs", ["spfit", "spcat"]), "must name the programs"),
    (lambda m: m.__setitem__("build_command", ["sh", "-c", "make"]), "make invocation"),
    (lambda m: m.__setitem__("sources", [s for s in m["sources"] if s["path"] != "dpi.c"]), "dpi.c"),
    (lambda m: m["sources"][0].__setitem__("sha256", "NOT-A-CHECKSUM"), "lowercase SHA-256"),
    (lambda m: m["sources"][1].__setitem__("path", "../Makefile"), "bare names"),
    (lambda m: m["rights"].__setitem__("redistribution_permitted", True), "deny redistribution"),
    (lambda m: m.__setitem__("upstream_prebuilt_files_retrieved", True), "no prebuilt upstream file"),
    (lambda m: m["acceptance"].pop("no"), "hco and no acceptance"),
])
def test_manifest_changes_outside_the_pin_are_rejected(tmp_path, mutate, message):
    manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    mutate(manifest)
    path = tmp_path / "pickett-distribution.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(PickettProvisioningError, match=message):
        load_manifest(path)


def test_roots_inside_a_checkout_are_refused_before_any_download(tmp_path):
    with pytest.raises(PickettProvisioningError, match="outside the source checkout"):
        provision(REPOSITORY_ROOT / "pickett-control")
    assert not (REPOSITORY_ROOT / "pickett-control").exists()
    checkout = tmp_path / "other-checkout"
    (checkout / ".git").mkdir(parents=True)
    with pytest.raises(PickettProvisioningError, match="outside any Git checkout"):
        provision(checkout / "pickett")
    assert not (checkout / "pickett").exists()


class _ControlHandler(http.server.BaseHTTPRequestHandler):
    """Serves labelled text controls; responses are chosen by path, never by JPL content."""

    def do_GET(self):  # noqa: N802 (http.server API)
        if self.path == "/wrong-bytes":
            body = b"Explicit text-only control with the wrong bytes; never a Pickett source.\n"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/redirected":
            self.send_response(302)
            self.send_header("Location", "/elsewhere")
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif self.path == "/absent":
            self.send_error(404)
        else:
            self.send_error(500)

    def log_message(self, *args):
        return None


def _control_server():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _ControlHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/"


def test_retrieval_stops_on_wrong_bytes_redirects_and_client_errors(tmp_path):
    server, upstream = _control_server()
    log = tmp_path / "fetch.jsonl"
    log.write_bytes(b"")
    expected = "0" * 64
    try:
        with pytest.raises(PickettProvisioningError, match="differs from the pinned upstream bytes"):
            fetch_pinned("wrong-bytes", expected, 73, log, upstream=upstream, backoff_seconds=0.0)
        with pytest.raises(PickettProvisioningError, match="redirected"):
            fetch_pinned("redirected", expected, 10, log, upstream=upstream, backoff_seconds=0.0)
        with pytest.raises(PickettProvisioningError, match=r"unavailable \(HTTP 404\)"):
            fetch_pinned("absent", expected, 10, log, upstream=upstream, backoff_seconds=0.0)
        with pytest.raises(PickettProvisioningError, match="after 2 attempts"):
            fetch_pinned("server-error", expected, 10, log, upstream=upstream, attempts=2, backoff_seconds=0.0)
    finally:
        server.shutdown()
        server.server_close()
    records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [record["url"].rsplit("/", 1)[1] for record in records] == [
        "wrong-bytes", "redirected", "absent", "server-error", "server-error"]
    assert records[1]["http"] == 302 and records[2]["http"] == 404
    assert all(record["http"] == 500 for record in records[3:])


def _control_receipt(tmp_path: Path, *, manifest_sha256: str | None = None) -> Path:
    bin_dir = tmp_path / "install" / "bin"
    bin_dir.mkdir(parents=True)
    programs = {}
    for name in PROGRAMS:
        program = bin_dir / name
        program.write_text(f"#!/bin/sh\n# Explicit text-only control named {name}; not a Pickett program.\nexit 0\n",
                           encoding="utf-8")
        program.chmod(0o700)
        programs[name] = {"path": str(program), "sha256": sha256_file(program), "size": program.stat().st_size,
                          "status": "built"}
    receipt = {
        "schema_version": RECEIPT_SCHEMA, "root": str(tmp_path / "install"),
        "manifest_sha256": manifest_sha256 or sha256_file(DEFAULT_MANIFEST),
        "programs": programs, "programs_on_path": False, "upstream_prebuilt_files_retrieved": False,
        "rights": {"redistribution_permitted": False, "bundled": False},
        "acceptance": {"hco": {"status": "built", "catalog_byte_equal": False,
                               "listed_differences": ["text-only control; no acceptance run"]}},
    }
    path = tmp_path / "install" / RECEIPT_NAME
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_receipt_binds_program_bytes_and_the_manifest(tmp_path):
    receipt_path = _control_receipt(tmp_path)
    loaded = load_receipt(receipt_path)
    assert set(loaded["programs"]) == set(PROGRAMS)
    assert program_path("spfit", receipt_path) == Path(loaded["programs"]["spfit"]["path"])
    report = verify(receipt=receipt_path)
    assert report["status"] == "ready" and report["programs"]["dpcat"]["status"] == "built"
    assert report["acceptance"]["hco"]["catalog_byte_equal"] is False

    Path(loaded["programs"]["spcat"]["path"]).write_text("changed control bytes\n", encoding="utf-8")
    with pytest.raises(PickettProvisioningError, match="no longer matches"):
        load_receipt(receipt_path)
    assert status(receipt=receipt_path)["status"] == "missing"

    stale = _control_receipt(tmp_path / "stale", manifest_sha256="1" * 64)
    with pytest.raises(PickettProvisioningError, match="different distribution manifest"):
        load_receipt(stale)
    assert load_receipt(stale, None)["schema_version"] == RECEIPT_SCHEMA

    assert status(receipt=tmp_path / "absent" / RECEIPT_NAME)["status"] == "missing"
    with pytest.raises(PickettProvisioningError, match="not a Pickett program"):
        program_path("pgopher", receipt_path)


def test_receipt_is_located_from_argument_environment_or_artifact_directory(tmp_path):
    explicit = tmp_path / "explicit" / RECEIPT_NAME
    assert locate_receipt(explicit) == explicit
    code = f"""import os, sys
from pathlib import Path
from scripts.provision_pickett import locate_receipt, RECEIPT_ENVIRONMENT, PickettProvisioningError
os.environ.pop(RECEIPT_ENVIRONMENT, None); os.environ.pop("COCHEM_ARTIFACT_DIR", None)
try:
    locate_receipt()
except PickettProvisioningError:
    pass
else:
    raise SystemExit("an unset environment must not locate a receipt")
os.environ["COCHEM_ARTIFACT_DIR"] = sys.argv[1]
assert locate_receipt() == Path(sys.argv[1]) / "pickett" / "install" / "{RECEIPT_NAME}"
os.environ[RECEIPT_ENVIRONMENT] = sys.argv[2]
assert locate_receipt() == Path(sys.argv[2])
"""
    subprocess.run([sys.executable, "-B", "-c", code, str(tmp_path), str(explicit)], cwd=REPOSITORY_ROOT,
                   env={**os.environ, "PYTHONPATH": str(REPOSITORY_ROOT)}, check=True, timeout=60)


def test_acceptance_records_byte_equality_or_every_listed_difference(tmp_path):
    if not sys.platform.startswith("linux"):
        return
    examples = tmp_path / "examples"
    examples.mkdir()
    for name, text in {"hcotst.par": "control parameters\n", "hco.lin": "control lines\n", "hco.int": "control intensities\n",
                       "hco.cat": "control catalog line 1\ncontrol catalog line 2\n",
                       "hco.fit": "MICROWAVE RMS = 0.1 MHz\nEND OF ITERATION 1 OLD, NEW RMS ERROR= 1.0 0.5\n"}.items():
        (examples / name).write_text(f"Explicit text-only control, not JPL data: {text}", encoding="utf-8")
    case = {"library": "spinv", "programs": ["spfit", "spcat"], "parameter_file": "hcotst.par", "line_file": "hco.lin",
            "intensity_file": "hco.int", "reference_catalog": "hco.cat", "reference_fit": "hco.fit",
            "listed_difference": "control case"}

    def control_programs(directory: Path, catalog_source: str) -> Path:
        directory.mkdir()
        (directory / "spfit").write_text(f"#!/bin/sh\n# control fit program\ncp {examples}/hco.fit \"$1.fit\"\n", encoding="utf-8")
        (directory / "spcat").write_text(f"#!/bin/sh\n# control catalog program\n{catalog_source}\n", encoding="utf-8")
        for program in ("spfit", "spcat"):
            (directory / program).chmod(0o700)
        return directory

    log = tmp_path / "acceptance.log"
    log.write_bytes(b"")
    same = run_acceptance(case, control_programs(tmp_path / "same", f"cp {examples}/hco.cat \"$1.cat\""),
                          examples, tmp_path / "work-same", log)
    assert same["status"] == "accepted" and same["catalog_byte_equal"] is True
    assert same["fit_summary_lines_equal"] is True and same["listed_differences"] == ["control case"]
    assert same["catalog_lines"] == {"produced": 2, "reference": 2}

    differs = run_acceptance(case, control_programs(tmp_path / "differs", "printf 'one line only\\n' > \"$1.cat\""),
                             examples, tmp_path / "work-differs", log)
    assert differs["status"] == "built" and differs["catalog_byte_equal"] is False
    assert differs["listed_differences"][1].startswith("hco.cat differs from the shipped file: 1 produced lines against 2")

    failing = control_programs(tmp_path / "failing", "exit 3")
    with pytest.raises(PickettProvisioningError, match="exited with status 3"):
        run_acceptance(case, failing, examples, tmp_path / "work-failing", log)


def test_cli_refuses_a_root_inside_the_checkout_and_reports_missing_installations(tmp_path):
    script = DEFAULT_MANIFEST.with_name("provision_pickett.py")
    result = subprocess.run([sys.executable, "-B", "-I", str(script), "build", "--root", str(REPOSITORY_ROOT / "pickett-control")],
                            capture_output=True, text=True, check=False, timeout=60)
    assert result.returncode == 1
    assert "Pickett provisioning failed:" in result.stderr and "outside the source checkout" in result.stderr
    assert not (REPOSITORY_ROOT / "pickett-control").exists()
    reported = subprocess.run([sys.executable, "-B", "-I", str(script), "status", "--root", str(tmp_path / "never-built"),
                               "--output", str(tmp_path / "status.json")], capture_output=True, text=True, check=True, timeout=60)
    assert json.loads(reported.stdout)["status"] == "missing"
    assert json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))["status"] == "missing"


def test_failed_pickett_build_keeps_setup_usable_and_exports_no_receipt(tmp_path):
    if not sys.platform.startswith("linux"):
        return
    with socket.socket() as refused:
        refused.bind(("127.0.0.1", 0))
        proxy = f"http://127.0.0.1:{refused.getsockname()[1]}"
        # The bound socket has no listener: every JPL request through this proxy is
        # refused before any byte could be accepted, so the build fails genuinely.
        result = prepare_pickett_programs(Path(sys.executable), tmp_path,
            environment={"https_proxy": proxy, "HTTPS_PROXY": proxy, "http_proxy": proxy,
                         "HTTP_PROXY": proxy, "no_proxy": "", "NO_PROXY": ""})
    assert result["status"] == "failed" and result["receipt"] is None
    assert set(result["programs"]) == set(PROGRAMS)
    assert all(record["status"] == "failed" and len(record["message"]) <= 2000 for record in result["programs"].values())
    assert "Retry setup" in result["message"]
    assert json.loads((tmp_path / "pickett/setup-status.json").read_text(encoding="utf-8")) == result
    assert not (tmp_path / "pickett/install").exists()
    assert RECEIPT_ENVIRONMENT not in runtime_environment(tmp_path)


def test_runtime_exports_the_receipt_only_for_a_ready_build_inside_the_profile(tmp_path):
    receipt_path = _control_receipt(tmp_path / "pickett")
    status_path = tmp_path / "pickett" / "setup-status.json"
    status_path.write_text(json.dumps({"schema_version": "cochem.pickett-setup/1", "status": "ready",
                                       "receipt": str(receipt_path)}), encoding="utf-8")
    assert runtime_environment(tmp_path)[RECEIPT_ENVIRONMENT] == str(receipt_path)
    code = f"""import os, sys
from pathlib import Path
from scripts.hosted_dashboard import runtime_environment
result = runtime_environment(Path(sys.argv[1]))
assert "{RECEIPT_ENVIRONMENT}" not in result, result.get("{RECEIPT_ENVIRONMENT}")
"""
    status_path.write_text(json.dumps({"schema_version": "cochem.pickett-setup/1", "status": "failed", "receipt": None}),
                           encoding="utf-8")
    subprocess.run([sys.executable, "-B", "-c", code, str(tmp_path)], cwd=REPOSITORY_ROOT,
                   env={**os.environ, RECEIPT_ENVIRONMENT: str(receipt_path), "PYTHONPATH": str(REPOSITORY_ROOT)},
                   check=True, timeout=60)
    outside = tmp_path / "outside" / RECEIPT_NAME
    outside.parent.mkdir()
    outside.write_text("{}", encoding="utf-8")
    status_path.write_text(json.dumps({"schema_version": "cochem.pickett-setup/1", "status": "ready",
                                       "receipt": str(outside)}), encoding="utf-8")
    with pytest.raises(ValueError, match="inside its external profile"):
        runtime_environment(tmp_path)
