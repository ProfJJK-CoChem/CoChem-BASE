#!/usr/bin/env python3
"""Download, verify, build and accept the pinned JPL Pickett programs.

SPFIT, SPCAT, DPFIT and DPCAT are built from the calpgm source files that JPL
publishes, every byte checked against ``pickett-distribution.json`` before the
compiler runs. Downloads, the build and the acceptance runs stay outside the
checkout; nothing downloaded or built is committed, bundled or added to PATH.

The receipt ``pickett-installation.json`` (schema ``cochem.pickett-installation/1``)
records the source inventory, the build recipe and platform, each program's
SHA-256 and status (``accepted`` when its library's shipped example is
reproduced byte for byte, otherwise ``built``), the rights notices and the
acceptance results with every listed difference. Consumers locate the programs
through the receipt (environment variable ``COCHEM_PICKETT_RECEIPT``) and check
each program's SHA-256 against it. A missing or failed program is reported as
missing; no other program or in-process model stands in for it
(CoChem-SpycFit D-SPYC-17, D-SPYC-26).
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_MANIFEST = Path(__file__).with_name("pickett-distribution.json")
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RECEIPT_NAME = "pickett-installation.json"
RECEIPT_SCHEMA = "cochem.pickett-installation/1"
RECEIPT_ENVIRONMENT = "COCHEM_PICKETT_RECEIPT"
PROGRAMS = ("spfit", "spcat", "dpfit", "dpcat")
OWNED_ENTRIES = {RECEIPT_NAME, "source", "examples", "bin", "acceptance", "logs"}
_FETCH_ATTEMPTS = 4
_FETCH_BACKOFF_SECONDS = 2.0
_FETCH_TIMEOUT_SECONDS = 60
_FETCH_DEADLINE_SECONDS = 300.0
_BUILD_TIMEOUT_SECONDS = 600
_PROGRAM_TIMEOUT_SECONDS = 120
_HEX64 = re.compile(r"[0-9a-f]{64}")
_FIT_SUMMARY = re.compile(r"MICROWAVE RMS|END OF ITERATION")


class PickettProvisioningError(RuntimeError):
    """A pinned Pickett download, build, acceptance run or receipt check failed."""


class _RefuseRedirect(urllib.request.HTTPRedirectHandler):
    """Every 3xx surfaces as an HTTPError; no Location target is requested."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _file_record(value: Any, context: str) -> tuple[str, str, int]:
    if not isinstance(value, dict):
        raise PickettProvisioningError(f"{context}: each file record must be an object.")
    name, digest, size = value.get("path"), value.get("sha256"), value.get("size")
    if (not isinstance(name, str) or not name or Path(name).name != name
            or any(character in name for character in "\\/\r\n\x00")):
        raise PickettProvisioningError(f"{context}: file names must be bare names without separators.")
    if not isinstance(digest, str) or not _HEX64.fullmatch(digest):
        raise PickettProvisioningError(f"{context}: {name} needs a lowercase SHA-256.")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise PickettProvisioningError(f"{context}: {name} needs a positive byte size.")
    return name, digest, size


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict:
    """Read and validate the pin manifest; the manifest, not the network, is the authority."""
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise PickettProvisioningError(f"Pickett distribution manifest is unreadable: {error}") from error
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise PickettProvisioningError("Pickett distribution manifest requires schema_version 1.")
    upstream = manifest.get("upstream_url")
    if upstream != "https://spec.jpl.nasa.gov/ftp/pub/calpgm/":
        raise PickettProvisioningError("Pickett sources are pinned to the JPL calpgm directory only.")
    if tuple(manifest.get("programs", ())) != PROGRAMS:
        raise PickettProvisioningError(f"Pickett manifest must name the programs {', '.join(PROGRAMS)}.")
    command = manifest.get("build_command")
    if (not isinstance(command, list) or not command or command[0] != "make"
            or any(not isinstance(part, str) or not re.fullmatch(r"[A-Za-z0-9_.=-]+", part) for part in command)
            or set(PROGRAMS) - set(command)):
        raise PickettProvisioningError("Pickett build command must be a make invocation naming every program.")
    for section in ("sources", "examples"):
        records = manifest.get(section)
        if not isinstance(records, list) or not records:
            raise PickettProvisioningError(f"Pickett manifest needs a nonempty {section} list.")
        names = [_file_record(record, section)[0] for record in records]
        if len(set(names)) != len(names):
            raise PickettProvisioningError(f"Pickett manifest {section} list repeats a file name.")
    source_names = {record["path"] for record in manifest["sources"]}
    if "Makefile" not in source_names or "dpi.c" not in source_names or "spinv.c" not in source_names:
        raise PickettProvisioningError("Pickett manifest sources must include Makefile, spinv.c and dpi.c.")
    acceptance = manifest.get("acceptance")
    if not isinstance(acceptance, dict) or set(acceptance) != {"hco", "no"}:
        raise PickettProvisioningError("Pickett manifest must define the hco and no acceptance runs.")
    example_names = {record["path"] for record in manifest["examples"]}
    for library, case in acceptance.items():
        required = ("library", "programs", "parameter_file", "line_file", "intensity_file",
                    "reference_catalog", "reference_fit", "listed_difference")
        if not isinstance(case, dict) or any(not isinstance(case.get(key), (str, list)) or not case[key] for key in required):
            raise PickettProvisioningError(f"Pickett acceptance case {library} is incomplete.")
        if tuple(case["programs"]) not in (("spfit", "spcat"), ("dpfit", "dpcat")):
            raise PickettProvisioningError(f"Pickett acceptance case {library} names an unknown program pair.")
        for key in ("parameter_file", "line_file", "intensity_file", "reference_catalog", "reference_fit"):
            if case[key] not in example_names:
                raise PickettProvisioningError(f"Pickett acceptance case {library} needs example {case[key]}.")
    rights = manifest.get("rights")
    if (not isinstance(rights, dict) or rights.get("redistribution_permitted") is not False
            or rights.get("bundled") is not False
            or not isinstance(rights.get("source_notice"), str) or not isinstance(rights.get("site_statement"), str)
            or not isinstance(rights.get("pi_use_rights"), str) or not rights["pi_use_rights"]):
        raise PickettProvisioningError("Pickett manifest rights must record the notices and deny redistribution and bundling.")
    if manifest.get("upstream_prebuilt_files_retrieved") is not False:
        raise PickettProvisioningError("Pickett manifest must state that no prebuilt upstream file is retrieved.")
    return manifest


def _safe_root(root: Path) -> Path:
    root = Path(root).expanduser().absolute()
    if ".." in root.parts or any(character in str(root) for character in "\r\n\x00"):
        raise PickettProvisioningError("Pickett root must be an absolute path without traversal or control characters.")
    checkouts = [REPOSITORY_ROOT]
    workspace = os.environ.get("GITHUB_WORKSPACE")
    if workspace:
        checkouts.append(Path(workspace).absolute())
    for checkout in checkouts:
        if root == checkout or checkout in root.parents:
            raise PickettProvisioningError("Pickett programs are provisioned outside the source checkout.")
    if any((parent / ".git").exists() for parent in (root, *root.parents)):
        raise PickettProvisioningError("Pickett programs are provisioned outside any Git checkout.")
    if any(component.is_symlink() for component in (root, *root.parents)):
        raise PickettProvisioningError("Pickett root cannot traverse symlinks.")
    return root


def _log_json(log: Path, record: dict[str, Any]) -> None:
    with log.open("ab") as stream:
        stream.write(json.dumps(record, sort_keys=True).encode() + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def _read_within(response: http.client.HTTPResponse, limit: int, deadline_seconds: float) -> bytes:
    deadline = time.monotonic() + deadline_seconds
    content = b""
    while len(content) < limit:
        if time.monotonic() > deadline:
            raise TimeoutError("Download exceeded its time limit.")
        chunk = response.read1(limit - len(content))
        if not chunk:
            break
        content += chunk
    return content


def fetch_pinned(name: str, expected_sha256: str, size: int, log: Path, *, upstream: str,
                 attempts: int = _FETCH_ATTEMPTS, backoff_seconds: float = _FETCH_BACKOFF_SECONDS,
                 deadline_seconds: float = _FETCH_DEADLINE_SECONDS) -> bytes:
    """Retrieve one pinned file. Redirects and 4xx stop at once; 5xx and transport failures retry."""
    url = upstream + name
    last_error: BaseException | None = None
    for attempt in range(1, attempts + 1):
        opener = urllib.request.build_opener(_RefuseRedirect)
        request = urllib.request.Request(url, headers={"User-Agent": "cochem-base-pickett-provisioning"})
        try:
            with opener.open(request, timeout=_FETCH_TIMEOUT_SECONDS) as response:
                if response.geturl() != url:
                    raise PickettProvisioningError(f"Pinned upstream {name} redirected; no other source is used.")
                if response.length is not None and response.length != size:
                    raise PickettProvisioningError(f"Retrieved {name} differs from the pinned upstream bytes.")
                content = _read_within(response, size + 1, deadline_seconds)
                if response.length:
                    # http.client counts down the bytes still owed by Content-Length:
                    # a body cut short of its declared length is a transport failure.
                    raise http.client.IncompleteRead(content, response.length)
        except urllib.error.HTTPError as error:
            record: dict[str, Any] = {"url": url, "attempt": attempt, "http": error.code}
            if 300 <= error.code < 400:
                record["location"] = str(error.headers.get("Location", ""))[:500]
                _log_json(log, record)
                raise PickettProvisioningError(
                    f"Pinned upstream {name} redirected (HTTP {error.code}); no other source is used.") from error
            _log_json(log, record)
            if error.code < 500:
                raise PickettProvisioningError(f"Pinned upstream {name} is unavailable (HTTP {error.code}).") from error
            last_error = error
        except (OSError, http.client.HTTPException) as error:
            _log_json(log, {"url": url, "attempt": attempt, "error": type(error).__name__,
                            "reason": str(getattr(error, "reason", error))[:500]})
            last_error = error
        else:
            actual = hashlib.sha256(content).hexdigest()
            _log_json(log, {"url": url, "attempt": attempt, "bytes": len(content), "sha256": actual})
            if len(content) != size or actual != expected_sha256:
                raise PickettProvisioningError(f"Retrieved {name} differs from the pinned upstream bytes.")
            return content
        if attempt < attempts:
            time.sleep(backoff_seconds * 2 ** (attempt - 1))
    raise PickettProvisioningError(
        f"Pinned upstream {name} could not be retrieved after {attempts} attempts; see {log}.") from last_error


def _write_new(path: Path, content: bytes, mode: int = 0o600) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def _retrieve(records: list[dict], destination: Path, log: Path, *, upstream: str) -> list[dict[str, Any]]:
    inventory = []
    for record in records:
        name, digest, size = _file_record(record, "manifest")
        content = fetch_pinned(name, digest, size, log, upstream=upstream)
        _write_new(destination / name, content)
        inventory.append({"path": name, "sha256": hashlib.sha256(content).hexdigest(), "size": len(content)})
    inventory.sort(key=lambda entry: entry["path"])
    return inventory


def _build_environment() -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(("LD_", "DYLD_", "GIT_", "PYTHON"))
                   and key not in {"CC", "CXX", "CFLAGS", "CPPFLAGS", "LDFLAGS", "LDLIBS", "MAKEFLAGS", "MFLAGS",
                                   "MAKELEVEL", "MAKEOVERRIDES", "BLASLIB"}
                   and not any(marker in key.upper() for marker in ("TOKEN", "SECRET", "PASSWORD", "CREDENTIAL",
                                                                     "AUTHORIZATION"))}
    environment.update({"LC_ALL": "C", "LANG": "C"})
    return environment


def _run(arguments: list[str], *, cwd: Path, log: Path, timeout: int) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(arguments, cwd=cwd, env=_build_environment(), stdin=subprocess.DEVNULL,
                                capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as error:
        _log_json(log, {"command": arguments, "timeout_seconds": timeout})
        raise PickettProvisioningError(f"{arguments[0]} exceeded its {timeout} s limit.") from error
    with log.open("ab") as stream:
        stream.write(json.dumps(arguments).encode() + b"\n")
        stream.write(result.stdout)
        stream.write(result.stderr)
        stream.write(f"\nexit_code={result.returncode}\n".encode())
        stream.flush()
        os.fsync(stream.fileno())
    return result


def _makefile_cflags(makefile: Path) -> str:
    for line in makefile.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("CFLAGS="):
            return line[len("CFLAGS="):].strip()
    raise PickettProvisioningError("The pinned Makefile defines no CFLAGS line.")


def _is_elf(path: Path) -> bool:
    with path.open("rb") as stream:
        return stream.read(4) == b"\x7fELF"


def _fit_summary_lines(path: Path) -> list[str]:
    return [" ".join(line.split()) for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if _FIT_SUMMARY.search(line)]


def run_acceptance(case: dict, bin_dir: Path, examples_dir: Path, work_dir: Path, log: Path) -> dict[str, Any]:
    """Run one shipped example on scratch copies and record byte equality or every listed difference."""
    fit_program, cat_program = case["programs"]
    stem = Path(case["line_file"]).stem
    work_dir.mkdir(mode=0o700)
    shutil.copyfile(examples_dir / case["parameter_file"], work_dir / f"{stem}.par")
    shutil.copyfile(examples_dir / case["line_file"], work_dir / f"{stem}.lin")
    shutil.copyfile(examples_dir / case["intensity_file"], work_dir / f"{stem}.int")
    record: dict[str, Any] = {
        "library": case["library"], "programs": list(case["programs"]),
        "inputs": {key: {"file": case[key], "sha256": sha256_file(examples_dir / case[key])}
                   for key in ("parameter_file", "line_file", "intensity_file")},
        "reference_catalog": {"file": case["reference_catalog"], "sha256": sha256_file(examples_dir / case["reference_catalog"])},
        "reference_fit": {"file": case["reference_fit"], "sha256": sha256_file(examples_dir / case["reference_fit"])},
        "listed_differences": [case["listed_difference"]],
    }
    runs = []
    for program in (fit_program, cat_program):
        result = _run([str(bin_dir / program), stem], cwd=work_dir, log=log, timeout=_PROGRAM_TIMEOUT_SECONDS)
        runs.append({"program": program, "exit_code": result.returncode,
                     "stdout_sha256": hashlib.sha256(result.stdout).hexdigest()})
        if result.returncode != 0:
            raise PickettProvisioningError(
                f"{program} exited with status {result.returncode} on the {case['library']} example; see {log}.")
    record["runs"] = runs
    produced_catalog = work_dir / f"{stem}.cat"
    produced_fit = work_dir / f"{stem}.fit"
    for produced in (produced_catalog, produced_fit):
        if not produced.is_file():
            raise PickettProvisioningError(f"{produced.name} was not produced on the {case['library']} example.")
    reference_catalog = examples_dir / case["reference_catalog"]
    catalog_equal = produced_catalog.read_bytes() == reference_catalog.read_bytes()
    produced_lines = produced_catalog.read_bytes().count(b"\n")
    reference_lines = reference_catalog.read_bytes().count(b"\n")
    produced_summary = _fit_summary_lines(produced_fit)
    reference_summary = _fit_summary_lines(examples_dir / case["reference_fit"])
    record.update({
        "produced_catalog_sha256": sha256_file(produced_catalog),
        "catalog_byte_equal": catalog_equal,
        "catalog_lines": {"produced": produced_lines, "reference": reference_lines},
        "fit_summary_lines_equal": produced_summary == reference_summary,
        "fit_summary": {"produced": produced_summary, "reference": reference_summary},
        "status": "accepted" if catalog_equal else "built",
    })
    if not catalog_equal:
        record["listed_differences"].append(
            f"{stem}.cat differs from the shipped file: {produced_lines} produced lines against {reference_lines}.")
    if produced_summary != reference_summary:
        record["listed_differences"].append(f"{stem}.fit iteration summary lines differ from the shipped file.")
    return record


def _remove_owned_root(root: Path) -> None:
    entries = {entry.name for entry in root.iterdir()}
    foreign = entries - OWNED_ENTRIES
    if foreign:
        raise PickettProvisioningError(
            f"Pickett root {root} holds entries this provisioner did not create: {sorted(foreign)}; not replaced.")
    shutil.rmtree(root)


def provision(root: Path, manifest_path: Path = DEFAULT_MANIFEST, *, replace: bool = False) -> dict[str, Any]:
    """Retrieve, hash, build and accept into a fresh external root; return the receipt."""
    manifest = load_manifest(manifest_path)
    root = _safe_root(root)
    if not sys.platform.startswith("linux"):
        raise PickettProvisioningError("This provisioner builds native Linux ELF programs only.")
    missing_tools = [tool for tool in manifest.get("required_tools", ("gcc", "make")) if shutil.which(tool) is None]
    if missing_tools:
        raise PickettProvisioningError(f"Required build tools are absent: {', '.join(missing_tools)}.")
    if root.exists() or root.is_symlink():
        if not replace:
            receipt_path = root / RECEIPT_NAME
            if receipt_path.is_file():
                return load_receipt(receipt_path, manifest_path)
            raise PickettProvisioningError(f"Pickett root {root} exists without a receipt; pass --replace to rebuild.")
        _remove_owned_root(root)
    if not root.parent.is_dir():
        raise PickettProvisioningError(f"Pickett root parent {root.parent} must already exist.")
    previous_umask = os.umask(0o077)
    try:
        root.mkdir(mode=0o700)
        logs, source, examples, bin_dir, acceptance_dir = (root / name for name in ("logs", "source", "examples", "bin", "acceptance"))
        for directory in (logs, source, examples, bin_dir, acceptance_dir):
            directory.mkdir(mode=0o700)
        fetch_log, build_log, acceptance_log = logs / "fetch.jsonl", logs / "build.log", logs / "acceptance.log"
        for log in (fetch_log, build_log, acceptance_log):
            _write_new(log, b"")
        upstream = manifest["upstream_url"]
        source_inventory = _retrieve(manifest["sources"], source, fetch_log, upstream=upstream)
        example_inventory = _retrieve(manifest["examples"], examples, fetch_log, upstream=upstream)
        for name in (*PROGRAMS, "splib.a"):
            if (source / name).exists():
                raise PickettProvisioningError("Fresh source unexpectedly contains a prebuilt file.")
        command = list(manifest["build_command"])
        build = _run(command, cwd=source, log=build_log, timeout=_BUILD_TIMEOUT_SECONDS)
        if build.returncode != 0:
            raise PickettProvisioningError(f"Pickett build exited with status {build.returncode}; see {build_log}.")
        compiler = _run(["gcc", "--version"], cwd=source, log=build_log, timeout=30)
        compiler_line = compiler.stdout.decode("utf-8", errors="replace").splitlines()[0] if compiler.stdout else "unrecorded"
        programs: dict[str, Any] = {}
        for program in PROGRAMS:
            built = source / program
            if not built.is_file() or built.is_symlink() or not _is_elf(built):
                raise PickettProvisioningError(f"{program} was not built as a native ELF program.")
            shutil.copyfile(built, bin_dir / program)
            os.chmod(bin_dir / program, 0o700)
            programs[program] = {"path": str(bin_dir / program), "sha256": sha256_file(bin_dir / program),
                                 "size": (bin_dir / program).stat().st_size, "status": "built"}
        acceptance = {}
        for library, case in manifest["acceptance"].items():
            acceptance[library] = run_acceptance(case, bin_dir, examples, acceptance_dir / library, acceptance_log)
            for program in case["programs"]:
                programs[program]["status"] = acceptance[library]["status"]
        try:
            libc = os.confstr("CS_GNU_LIBC_VERSION") or "unrecorded"
        except (AttributeError, OSError, ValueError):
            libc = "unrecorded"
        receipt = {
            "schema_version": RECEIPT_SCHEMA,
            "recorded_at": _utc_now(),
            "root": str(root),
            "manifest_path": str(Path(manifest_path).resolve()),
            "manifest_sha256": sha256_file(Path(manifest_path)),
            "upstream_url": upstream,
            "upstream_prebuilt_files_retrieved": False,
            "source": {"directory": str(source), "inventory": source_inventory,
                       "inventory_sha256": _digest(source_inventory), "fetch_log_sha256": sha256_file(fetch_log)},
            "examples": {"directory": str(examples), "inventory": example_inventory,
                         "inventory_sha256": _digest(example_inventory)},
            "build": {"command": command, "compiler": compiler_line, "cflags": _makefile_cflags(source / "Makefile"),
                      "exit_code": build.returncode, "log_sha256": sha256_file(build_log),
                      "os": platform.system(), "os_release": platform.release(), "architecture": platform.machine(),
                      "libc": libc},
            "programs": programs,
            "programs_on_path": False,
            "rights": dict(manifest["rights"]),
            "acceptance": acceptance,
            "acceptance_log_sha256": sha256_file(acceptance_log),
        }
        receipt_path = root / RECEIPT_NAME
        _write_new(receipt_path, (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode(), mode=0o644)
        os.chmod(root, 0o755)
        os.chmod(bin_dir, 0o755)
        for program in PROGRAMS:
            os.chmod(bin_dir / program, 0o755)
    except BaseException:
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
        raise
    finally:
        os.umask(previous_umask)
    return receipt


def load_receipt(path: Path, manifest_path: Path | None = DEFAULT_MANIFEST) -> dict[str, Any]:
    """Read a receipt and check that every program it names still has the recorded bytes."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise PickettProvisioningError(f"Pickett receipt {path} is missing or not a regular file.")
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise PickettProvisioningError(f"Pickett receipt {path} is unreadable: {error}") from error
    if not isinstance(receipt, dict) or receipt.get("schema_version") != RECEIPT_SCHEMA:
        raise PickettProvisioningError(f"Pickett receipt {path} does not carry schema {RECEIPT_SCHEMA}.")
    programs = receipt.get("programs")
    if not isinstance(programs, dict) or set(programs) != set(PROGRAMS):
        raise PickettProvisioningError(f"Pickett receipt {path} must record exactly {', '.join(PROGRAMS)}.")
    for name, entry in programs.items():
        if (not isinstance(entry, dict) or not isinstance(entry.get("path"), str)
                or not isinstance(entry.get("sha256"), str) or not _HEX64.fullmatch(entry["sha256"])
                or entry.get("status") not in ("accepted", "built")):
            raise PickettProvisioningError(f"Pickett receipt entry for {name} is incomplete.")
        program = Path(entry["path"])
        if program.is_symlink() or not program.is_file() or not os.access(program, os.X_OK):
            raise PickettProvisioningError(f"Pickett program {name} at {program} is missing or not executable.")
        if sha256_file(program) != entry["sha256"]:
            raise PickettProvisioningError(f"Pickett program {name} at {program} no longer matches its receipt.")
    if receipt.get("programs_on_path") is not False or receipt.get("upstream_prebuilt_files_retrieved") is not False:
        raise PickettProvisioningError(f"Pickett receipt {path} must deny PATH installation and prebuilt downloads.")
    rights = receipt.get("rights")
    if not isinstance(rights, dict) or rights.get("redistribution_permitted") is not False or rights.get("bundled") is not False:
        raise PickettProvisioningError(f"Pickett receipt {path} must deny redistribution and bundling.")
    if manifest_path is not None:
        manifest_path = Path(manifest_path)
        if manifest_path.is_file() and receipt.get("manifest_sha256") != sha256_file(manifest_path):
            raise PickettProvisioningError(
                f"Pickett receipt {path} was produced from a different distribution manifest; rebuild is required.")
    return receipt


def locate_receipt(explicit: Path | str | None = None) -> Path:
    """The receipt path from an argument, COCHEM_PICKETT_RECEIPT or the artifact directory."""
    if explicit:
        return Path(explicit).expanduser()
    environment = os.environ.get(RECEIPT_ENVIRONMENT)
    if environment:
        return Path(environment).expanduser()
    artifacts = os.environ.get("COCHEM_ARTIFACT_DIR")
    if artifacts:
        return Path(artifacts).expanduser() / "pickett" / "install" / RECEIPT_NAME
    raise PickettProvisioningError(
        f"No Pickett receipt: set {RECEIPT_ENVIRONMENT} or COCHEM_ARTIFACT_DIR, or run the build.")


def program_path(name: str, receipt_path: Path | str | None = None) -> Path:
    """The verified path of one program; raises when the program or its receipt is absent."""
    if name not in PROGRAMS:
        raise PickettProvisioningError(f"{name} is not a Pickett program this receipt covers.")
    receipt = load_receipt(locate_receipt(receipt_path), None)
    return Path(receipt["programs"][name]["path"])


def verify(root: Path | None = None, receipt: Path | None = None, manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    receipt_path = Path(receipt) if receipt else _safe_root(Path(root)) / RECEIPT_NAME if root else locate_receipt()
    record = load_receipt(receipt_path, manifest_path)
    return {"status": "ready", "receipt": str(receipt_path), "receipt_sha256": sha256_file(receipt_path),
            "programs": {name: {"path": entry["path"], "sha256": entry["sha256"], "status": entry["status"]}
                         for name, entry in record["programs"].items()},
            "acceptance": {library: {"status": case["status"], "catalog_byte_equal": case["catalog_byte_equal"],
                                     "listed_differences": case["listed_differences"]}
                           for library, case in record.get("acceptance", {}).items()}}


def status(root: Path | None = None, receipt: Path | None = None, manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    """Like verify, but a missing or invalid installation is reported, not raised."""
    try:
        return verify(root, receipt, manifest_path)
    except PickettProvisioningError as error:
        return {"status": "missing", "reason": str(error), "programs": {}}


def github_environment(receipt: dict[str, Any], env_path: Path) -> None:
    receipt_path = Path(receipt["root"]) / RECEIPT_NAME
    values = {RECEIPT_ENVIRONMENT: str(receipt_path)}
    values.update({f"COCHEM_{name.upper()}_BIN": entry["path"] for name, entry in receipt["programs"].items()})
    if any(any(character in value for character in "\r\n\x00") for value in values.values()):
        raise PickettProvisioningError("Paths with line breaks or NUL cannot be exported to Actions.")
    with Path(env_path).open("a", encoding="utf-8") as stream:
        stream.writelines(f"{key}={value}\n" for key, value in values.items())


def _default_root() -> Path | None:
    artifacts = os.environ.get("COCHEM_ARTIFACT_DIR")
    return Path(artifacts).expanduser() / "pickett" / "install" if artifacts else None


def _write_output(path: Path | None, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=f".{path.name}.", delete=False, encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(stream.name, path)
    sys.stdout.write(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="provision_pickett", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, text in (("build", "Download, verify, build and accept the four programs into --root."),
                       ("verify", "Check an existing installation against its receipt and the manifest."),
                       ("status", "Report the installation state without raising on a missing installation.")):
        sub = subparsers.add_parser(name, help=text)
        sub.add_argument("--root", type=Path, default=_default_root(),
                         help="installation root outside the checkout (default: $COCHEM_ARTIFACT_DIR/pickett/install)")
        sub.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
        sub.add_argument("--output", type=Path, help="also write the JSON result to this file")
        if name == "build":
            sub.add_argument("--replace", action="store_true", help="rebuild over a previous installation in --root")
            sub.add_argument("--github-env", type=Path, help="append COCHEM_PICKETT_RECEIPT and program paths to this file")
        else:
            sub.add_argument("--receipt", type=Path, help="receipt path (default: --root/pickett-installation.json)")
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            if args.root is None:
                parser.error("--root is required when COCHEM_ARTIFACT_DIR is unset")
            receipt = provision(args.root, args.manifest, replace=args.replace)
            if args.github_env:
                github_environment(receipt, args.github_env)
            payload = {"status": "ready", "receipt": str(Path(receipt["root"]) / RECEIPT_NAME),
                       "programs": receipt["programs"], "acceptance": {
                           library: {"status": case["status"], "catalog_byte_equal": case["catalog_byte_equal"],
                                     "listed_differences": case["listed_differences"]}
                           for library, case in receipt["acceptance"].items()},
                       "rights": receipt["rights"]}
        elif args.command == "verify":
            payload = verify(args.root, args.receipt, args.manifest)
        else:
            payload = status(args.root, args.receipt, args.manifest)
    except PickettProvisioningError as error:
        failure = {"status": "failed", "reason": str(error)}
        if args.output:
            _write_output(args.output, failure)
        parser.exit(1, f"Pickett provisioning failed: {error}\n")
    _write_output(args.output, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
