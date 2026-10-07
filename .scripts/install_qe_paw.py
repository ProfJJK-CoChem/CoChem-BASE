#!/usr/bin/env python3
"""Install pinned free native QE and official example PAW files outside checkout.

Debian 13 x86_64 CPU host, with its MPI/BLAS/LAPACK/FFTW runtime libraries.
Hashes below pin the downloaded bytes for reproducibility; they are not invented
publisher signatures. No root permission, shell wrapper, or scientific result
substitution is used. Runtime dependency checks fail before announcing readiness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import urllib.request


PACKAGES = (
    ("https://deb.debian.org/debian/pool/main/e/espresso/quantum-espresso_6.7-3+b1_amd64.deb",
     "44f9f38afc08fa53148cdddf8936464ba992b894a0843cc4aaf8749809b54bca"),
    ("https://deb.debian.org/debian/pool/main/s/scalapack/libscalapack-openmpi2.2_2.2.2-1_amd64.deb",
     "19edff3e0d4d27b350965246ac93de8bc0328fa3c42f1b9a93048873ec2aeb7d"),
    ("https://deb.debian.org/debian/pool/main/p/patchelf/patchelf_0.18.0-1.4_amd64.deb",
     "1d39a7973504a4a5eb4101293cca142b83055a5a0f94e1d4286ded2563289b92"),
)
QE_COMMIT = "7fd60c9bc9fe7a7d1fe6f1049f4afba0eab9aeef"
PSEUDOS = {
    "Ga": ("Ga.pbe-dn-kjpaw_psl.0.2.upf", "9047f9f8a661f4e271fbfd1bb6b0adabbdaa6ac51218ede1db080de951584465"),
    "As": ("As.pbe-n-kjpaw_psl.0.2.upf", "b98e3faf0777acc7a579e08ad4a77885c3e742fc4aa7455b56ff1f0abd4994f1"),
}


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def fetch(url: str, expected: str, target: Path) -> None:
    if target.is_file() and digest(target) == expected:
        return
    temporary = target.with_suffix(target.suffix + ".download")
    # urllib uses the environment proxy and configured system CA trust.
    with urllib.request.urlopen(url, timeout=60) as response, temporary.open("wb") as handle:
        while chunk := response.read(1024 * 1024):
            handle.write(chunk)
    if digest(temporary) != expected:
        temporary.unlink()
        raise ValueError(f"Downloaded file failed pinned SHA-256 validation: {url}")
    temporary.replace(target)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--pseudo-dir", type=Path, required=True)
    arguments = parser.parse_args()
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise SystemExit("This pinned native package set requires Linux x86_64")
    checkout = Path(__file__).resolve().parents[1]
    prefix, pseudo_dir = arguments.prefix.expanduser().resolve(), arguments.pseudo_dir.expanduser().resolve()
    for path in (prefix, pseudo_dir):
        if path == checkout or checkout in path.parents:
            raise ValueError("Runtime engine and pseudopotential locations must be outside the checkout")
        path.mkdir(parents=True, exist_ok=True)
    cache = prefix / "downloads"
    cache.mkdir(exist_ok=True)
    for url, expected in PACKAGES:
        package = cache / url.rsplit("/", 1)[1]
        fetch(url, expected, package)
        subprocess.run(["dpkg-deb", "-x", str(package), str(prefix)], check=True)
    binary = prefix / "usr/bin/pw.x"
    subprocess.run([str(prefix / "usr/bin/patchelf"), "--set-rpath", "$ORIGIN/../lib/x86_64-linux-gnu", str(binary)], check=True)
    libraries = subprocess.run(["ldd", str(binary)], text=True, capture_output=True, check=True)
    if "not found" in libraries.stdout:
        raise RuntimeError("QE host dependency libraries are missing:\n" + libraries.stdout)
    pseudopotentials = {}
    for symbol, (filename, expected) in PSEUDOS.items():
        url = f"https://raw.githubusercontent.com/QEF/q-e/{QE_COMMIT}/PP/simple_transport/examples/scf/{filename}"
        destination = pseudo_dir / filename
        fetch(url, expected, destination)
        pseudopotentials[symbol] = {"path": str(destination), "sha256": expected, "source_url": url}
    manifest = {"engine": "Quantum ESPRESSO", "version": "6.7MaX", "path": str(binary), "sha256": digest(binary),
                "packages": [{"url": url, "sha256": sha} for url, sha in PACKAGES],
                "rpath": "$ORIGIN/../lib/x86_64-linux-gnu", "dependencies": libraries.stdout,
                "pseudopotentials": pseudopotentials, "accuracy_validated": False,
                "next_step": "Export COCHEM_QE_BIN and rerun all Stage0 phases to audit native executable"}
    (prefix / "installation-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"COCHEM_QE_BIN": str(binary), "manifest": str(prefix / "installation-manifest.json"),
                      "pseudopotentials": pseudopotentials}, indent=2))


if __name__ == "__main__":
    main()
