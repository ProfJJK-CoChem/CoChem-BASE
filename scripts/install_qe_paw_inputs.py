#!/usr/bin/env python3
"""Provision authenticated free Ga/As PBE PAW inputs outside the BASE checkout.

These official Quantum ESPRESSO example files are pinned to an immutable QEF
commit and exact bytes. This installs input data, not a QE executable, and makes
no band-gap, lattice-accuracy, spin-orbit, or native-execution claim.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import tempfile
import time
import urllib.request
import xml.etree.ElementTree as ET


REPOSITORY = Path(__file__).resolve().parents[1]
QE_COMMIT = "7fd60c9bc9fe7a7d1fe6f1049f4afba0eab9aeef"
SOURCE_BASE = f"https://raw.githubusercontent.com/QEF/q-e/{QE_COMMIT}/PP/simple_transport/examples/scf"
PSEUDOPOTENTIALS = {
    "Ga": {"filename": "Ga.pbe-dn-kjpaw_psl.0.2.upf", "size_bytes": 1977993,
           "sha256": "9047f9f8a661f4e271fbfd1bb6b0adabbdaa6ac51218ede1db080de951584465"},
    "As": {"filename": "As.pbe-n-kjpaw_psl.0.2.upf", "size_bytes": 1184298,
           "sha256": "b98e3faf0777acc7a579e08ad4a77885c3e742fc4aa7455b56ff1f0abd4994f1"},
}
DOWNLOAD_TIMEOUT_SECONDS = 30
DOWNLOAD_DEADLINE_SECONDS = 90


def external_path(value: str | Path) -> Path:
    """Reject source writes and redirected runtime paths before creating files."""
    raw = Path(value).expanduser()
    if ".." in raw.parts:
        raise ValueError("PAW runtime paths may not contain parent-directory traversal")
    path = raw.absolute()
    for component in (*reversed(path.parents), path):
        if component.is_symlink():
            raise ValueError("PAW runtime paths may not contain symbolic links")
    resolved = path.resolve()
    if resolved == REPOSITORY or resolved.is_relative_to(REPOSITORY) or REPOSITORY.is_relative_to(resolved):
        raise ValueError("PAW inputs and receipts require an owned directory outside the source checkout")
    return resolved


def _header(data: bytes, symbol: str) -> dict:
    text = data.decode("utf-8")
    # UPF PP_INFO contains unescaped Fortran '&': parse the structured header,
    # as the actual periodic adapter does, instead of treating PP_INFO as XML.
    headers = re.findall(r"<PP_HEADER\b[^>]*?/>", text, re.DOTALL)
    if len(headers) != 1 or not re.search(r"<PP_PAW\b", text):
        raise ValueError("Official UPF2 PAW header and augmentation data are required")
    attributes = ET.fromstring(headers[0]).attrib
    functional = " ".join(attributes.get("functional", "").upper().split())
    if (attributes.get("element", "").strip() != symbol
            or attributes.get("pseudo_type", "").strip().upper() != "PAW"
            or attributes.get("is_paw", "").strip().upper() not in {"T", "TRUE", ".TRUE."}
            or attributes.get("has_so", "").strip().upper() not in {"F", "FALSE", ".FALSE."}
            or attributes.get("relativistic", "").strip().lower() != "scalar"
            or functional not in {"PBE", "SLA PW PBX PBC"}):
        raise ValueError(f"Official {symbol} input must declare scalar PBE PAW with its matching element")
    valence = float(attributes["z_valence"])
    cutoffs = {key: float(attributes[key]) for key in ("wfc_cutoff", "rho_cutoff")}
    if (not math.isfinite(valence) or valence <= 0 or not valence.is_integer()
            or any(not math.isfinite(value) or value <= 0 for value in cutoffs.values())):
        raise ValueError("PAW valence and recommended cutoffs must be finite and positive")
    return {"element": symbol, "pseudo_type": "PAW", "functional": functional,
            "relativistic": attributes.get("relativistic", ""), "has_so": False,
            "valence_electrons": int(valence), "recommended_cutoffs_ry": cutoffs,
            "author": attributes.get("author", ""), "generation_date": attributes.get("date", "")}


def verify_input(path: Path, symbol: str) -> dict:
    """Authenticate bounded regular bytes and the actual structured UPF header."""
    path = external_path(path)
    pin = PSEUDOPOTENTIALS[symbol]
    if path.name != pin["filename"]:
        raise ValueError("PAW input filename differs from its pinned species")
    observed = path.lstat()
    if not stat.S_ISREG(observed.st_mode) or observed.st_size != pin["size_bytes"]:
        raise ValueError(f"Pinned {symbol} PAW input must be a regular file of exactly {pin['size_bytes']} bytes")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(descriptor, "rb") as source:
        metadata = os.fstat(source.fileno())
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_size != pin["size_bytes"]
                or (metadata.st_dev, metadata.st_ino) != (observed.st_dev, observed.st_ino)):
            raise ValueError(f"Pinned {symbol} PAW input must be a regular file of exactly {pin['size_bytes']} bytes")
        data = source.read(pin["size_bytes"] + 1)
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != pin["size_bytes"] or digest != pin["sha256"]:
        raise ValueError(f"Pinned {symbol} PAW SHA-256 authentication failed")
    return {**pin, "path": str(path), "source_url": f"{SOURCE_BASE}/{pin['filename']}",
            "source_commit": QE_COMMIT, "upf_header": _header(data, symbol)}


def verify_inputs(directory: Path) -> dict[str, dict]:
    directory = external_path(directory)
    return {symbol: verify_input(directory / pin["filename"], symbol)
            for symbol, pin in PSEUDOPOTENTIALS.items()}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Pinned official PAW source must not redirect to another URL")


def _download(directory: Path, symbol: str) -> dict:
    pin = PSEUDOPOTENTIALS[symbol]
    target = directory / pin["filename"]
    if target.exists() or target.is_symlink():
        return {**verify_input(target, symbol), "acquisition": "existing_bytes_reverified"}
    url = f"{SOURCE_BASE}/{pin['filename']}"
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{symbol}-", suffix=".partial", dir=directory)
    temporary = Path(temporary_name)
    observed_headers = {}
    try:
        started = time.monotonic()
        # Default HTTPS validation and environment proxies remain enabled.
        opener = urllib.request.build_opener(_NoRedirect())
        with os.fdopen(descriptor, "wb") as destination, opener.open(url, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            if response.status != 200 or response.geturl() != url:
                raise ValueError("Official PAW download did not return the exact pinned HTTPS source")
            length = response.headers.get("Content-Length")
            if length is not None and int(length) != pin["size_bytes"]:
                raise ValueError("Official PAW response Content-Length differs from the bounded pinned size")
            observed_headers = {name: response.headers[name][:1024]
                                for name in ("Content-Type", "Content-Length", "ETag", "Last-Modified")
                                if name in response.headers}
            total = 0
            digest = hashlib.sha256()
            while True:
                chunk = response.read(64 * 1024)
                total += len(chunk)
                if total > pin["size_bytes"] or time.monotonic() - started > DOWNLOAD_DEADLINE_SECONDS:
                    raise ValueError("Official PAW download exceeded its fixed byte/time budget")
                if not chunk:
                    break
                destination.write(chunk)
                digest.update(chunk)
            if total != pin["size_bytes"] or digest.hexdigest() != pin["sha256"]:
                raise ValueError(f"Official {symbol} download failed exact size/SHA-256 authentication")
            destination.flush()
            os.fsync(destination.fileno())
        external_path(directory)
        if target.exists() or target.is_symlink():
            raise ValueError("PAW destination changed during its authenticated download")
        temporary.replace(target)
        return {**verify_input(target, symbol), "acquisition": "official_https_download",
                "response_headers": observed_headers}
    finally:
        temporary.unlink(missing_ok=True)


def _write_receipt(path: Path, receipt: dict) -> None:
    path = external_path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    descriptor, name = tempfile.mkstemp(prefix=".paw-receipt-", suffix=".partial", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as destination:
            json.dump(receipt, destination, indent=2)
            destination.write("\n")
        external_path(path)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def install_inputs(directory: Path, output: Path) -> dict:
    directory, output = external_path(directory), external_path(output)
    if output.name in {pin["filename"] for pin in PSEUDOPOTENTIALS.values()}:
        raise ValueError("PAW receipt may not overwrite a pinned input filename")
    directory.mkdir(parents=True, exist_ok=True, mode=0o750)
    receipt = {"schema_version": "cochem.qe-paw-inputs/1", "status": "failed",
               "directory": str(directory), "source_repository": "QEF/q-e", "source_commit": QE_COMMIT,
               "timestamp_utc": datetime.now(timezone.utc).isoformat(), "pseudopotentials": {},
               "scientific_accuracy_established": False, "native_execution_verified": False,
               "scope": "Authenticated scalar PBE PAW input data for Ga/As; no scientific result or QE binary provisioned"}
    try:
        for symbol in PSEUDOPOTENTIALS:
            receipt["pseudopotentials"][symbol] = _download(directory, symbol)
        receipt["status"] = "verified"
        return receipt
    except (OSError, ValueError, ET.ParseError) as error:
        receipt["error"] = str(error)[:2000]
        raise
    finally:
        _write_receipt(output, receipt)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pseudo-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(install_inputs(arguments.pseudo_dir, arguments.output), indent=2))


if __name__ == "__main__":
    main()
