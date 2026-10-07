#!/usr/bin/env python3
"""Build the pinned Linux Open MPI runtime used by the ORCA Actions pathway.

This explicit provisioning command never changes a workstation/HPC installation
or accepts an existing prefix on the strength of a provenance JSON file. It
verifies the source archive before extraction, builds into a fresh external
prefix, and exercises the installed launcher and C++ bindings with two ranks.
That runtime check is not scientific ORCA acceptance.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile
import urllib.request

if __package__:
    from .provision_orca import extract_verified_archive, sha256_file
else:
    from provision_orca import extract_verified_archive, sha256_file


VERSION = "4.1.8"
SOURCE_URL = "https://download.open-mpi.org/release/open-mpi/v4.1/openmpi-4.1.8.tar.bz2"
SOURCE_SHA256 = "466f68e3132a1dc02710cc2011fafced8336d98359fa2dae4dddcfd5719f12a9"
SOURCE_DIGEST_REFERENCE = (
    "https://github.com/spack/spack-packages/blob/"
    "8cdc2a7498bce56e996ba19e32703f61ee0e071f/"
    "repos/spack_repo/builtin/packages/openmpi/package.py"
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONFIGURE_OPTIONS = [
    "--enable-shared", "--disable-static", "--enable-mpi-cxx",
    "--disable-mpi-fortran", "--disable-oshmem", "--with-hwloc=internal",
    "--with-libevent=internal", "--without-ucx", "--without-verbs",
    "--without-libfabric", "--disable-man-pages", "--disable-dependency-tracking",
]
MPI_SMOKE_SOURCE = r"""#include <mpi.h>
#include <cstdio>
int main(int argc, char **argv) {
    MPI::Init(argc, argv);
    int rank = MPI::COMM_WORLD.Get_rank();
    int size = MPI::COMM_WORLD.Get_size();
    int value = rank + 1, sum = 0;
    MPI::COMM_WORLD.Allreduce(&value, &sum, 1, MPI::INT, MPI::SUM);
    std::printf("COCHEM_MPI rank=%d size=%d sum=%d\n", rank, size, sum);
    MPI::Finalize();
    return size == 2 && sum == 3 ? 0 : 1;
}
"""


def external_path(value: str | Path) -> Path:
    path = Path(value).expanduser().resolve()
    if path.is_relative_to(REPOSITORY_ROOT):
        raise ValueError("Open MPI installation, builds and evidence must be outside the source checkout.")
    return path


def bounded_jobs(value: str) -> int:
    jobs = int(value)
    if not 1 <= jobs <= 32:
        raise argparse.ArgumentTypeError("Build jobs must be between 1 and 32.")
    return jobs


def exact_openmpi_version(output: str) -> str:
    # Open MPI 4.1.8's mpiexec identifies its bundled launcher as OpenRTE;
    # mpirun and ompi_info identify the same build as Open MPI. Accept only
    # these complete native banner forms, retaining exact-version checks.
    pattern = (
        r"^(?:(?:mpirun|mpiexec) \(Open MPI\)|mpiexec \(OpenRTE\)|Open MPI:?)"
        r"[ \t]+v?(\d+\.\d+\.\d+)[ \t]*$"
    )
    versions = set(re.findall(pattern, output, flags=re.MULTILINE))
    if versions != {VERSION}:
        raise ValueError(f"Expected Open MPI {VERSION}, observed {sorted(versions)}.")
    return VERSION


def checked_command(argv: list[str], cwd: Path, environment: dict[str, str],
                    log: Path, timeout: int = 1800) -> None:
    """Stream potentially large build output to external evidence, never memory."""
    with log.open("w") as stream:
        result = subprocess.run(argv, cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
                                stdout=stream, stderr=subprocess.STDOUT,
                                timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError(f"{Path(argv[0]).name} failed with exit {result.returncode}; see {log}")


def download_source(build_root: Path) -> Path:
    archive = build_root / SOURCE_URL.rsplit("/", 1)[-1]
    if archive.exists() or archive.is_symlink():
        if not archive.is_file() or archive.is_symlink() or sha256_file(archive) != SOURCE_SHA256:
            raise ValueError("Cached Open MPI source differs from the pinned archive; remove it explicitly.")
        return archive
    descriptor, temporary_name = tempfile.mkstemp(prefix=archive.name + ".", suffix=".partial", dir=build_root)
    partial = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output, urllib.request.urlopen(SOURCE_URL, timeout=120) as response:
            if not response.geturl().startswith("https://"):
                raise ValueError("Open MPI source download redirected away from verified HTTPS.")
            shutil.copyfileobj(response, output)
        if sha256_file(partial) != SOURCE_SHA256:
            raise ValueError("Downloaded Open MPI source does not match its pinned SHA-256.")
        partial.replace(archive)
    finally:
        partial.unlink(missing_ok=True)
    return archive


def file_inventory(prefix: Path) -> dict:
    files = {}
    for path in sorted(prefix.rglob("*")):
        if path.is_symlink():
            if not path.resolve(strict=True).is_relative_to(prefix):
                raise ValueError(f"Installed Open MPI link escapes its prefix: {path}")
            files[str(path.relative_to(prefix))] = {"symlink": os.readlink(path)}
        elif path.is_file():
            files[str(path.relative_to(prefix))] = {
                "sha256": sha256_file(path), "bytes": path.stat().st_size,
            }
    return files


def validate_runtime(prefix: Path, evidence: Path, environment: dict[str, str]) -> dict:
    versions = {}
    for name in ("mpirun", "mpiexec", "ompi_info", "mpicxx"):
        path = prefix / "bin" / name
        if not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError(f"Missing installed MPI executable: {path}")
        if not path.resolve().is_relative_to(prefix):
            raise ValueError(f"Installed MPI executable escapes its prefix: {path}")
        if name != "mpicxx":
            log = evidence / f"{name}-version.log"
            checked_command([str(path), "--version"], evidence, environment, log, timeout=30)
            versions[name] = exact_openmpi_version(log.read_text())
    libraries = []
    for name in ("libmpi.so.40", "libmpi_cxx.so.40"):
        matches = [prefix / part / name for part in ("lib", "lib64")
                   if (prefix / part / name).is_file()]
        if len(matches) != 1 or not matches[0].resolve().is_relative_to(prefix):
            raise ValueError(f"Expected one installed Open MPI shared library {name}.")
        library = matches[0]
        with library.open("rb") as stream:
            header = stream.read(20)
        if header[:6] != b"\x7fELF\x02\x01" or header[18:20] != b"\x3e\x00":
            raise ValueError(f"Expected Linux x86-64 ELF shared library: {library}")
        libraries.append({"path": str(library), "sha256": sha256_file(library)})
    source = evidence / "mpi-smoke.cpp"
    executable = evidence / "mpi-smoke"
    source.write_text(MPI_SMOKE_SOURCE)
    checked_command([str(prefix / "bin/mpicxx"), str(source), "-o", str(executable)],
                    evidence, environment, evidence / "mpi-smoke-build.log", timeout=60)
    launch_environment = environment.copy()
    if os.geteuid() == 0:
        launch_environment["OMPI_ALLOW_RUN_AS_ROOT"] = "1"
        launch_environment["OMPI_ALLOW_RUN_AS_ROOT_CONFIRM"] = "1"
    log = evidence / "mpi-smoke-two-rank.log"
    checked_command([str(prefix / "bin/mpirun"), "--oversubscribe", "--bind-to", "none",
                     "-np", "2", str(executable)], evidence, launch_environment, log, timeout=60)
    records = re.findall(r"^COCHEM_MPI rank=(\d+) size=(\d+) sum=(\d+)$", log.read_text(), re.MULTILINE)
    if sorted(records) != [("0", "2", "3"), ("1", "2", "3")]:
        raise ValueError(f"Installed MPI two-rank collective check failed; see {log}")
    return {"versions": versions, "shared_libraries": libraries,
            "runtime_check": {"ranks": 2, "collective_sum": 3, "passed": True,
                              "log": str(log), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}}


def install(prefix: Path, build_root: Path, jobs: int) -> dict:
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise ValueError("This ORCA Actions runtime build requires Linux x86_64; use the site/local MPI on other routes.")
    prefix, build_root = external_path(prefix), external_path(build_root)
    if prefix.exists():
        raise ValueError("Open MPI prefix already exists; select a fresh path instead of trusting stale installation metadata.")
    if prefix == build_root or build_root.is_relative_to(prefix):
        raise ValueError("Build/evidence directory must not be inside the installation prefix.")
    if not 1 <= jobs <= 32:
        raise ValueError("Build jobs must be between 1 and 32.")
    compilers = {name: shutil.which(name) for name in ("gcc", "g++", "make")}
    if not all(compilers.values()):
        raise ValueError("Install gcc, g++ and make before building Open MPI.")
    build_root.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix="openmpi-4.1.8-build-", dir=build_root))
    archive = download_source(build_root)
    extraction = evidence / "source"
    extract_verified_archive(archive, extraction, SOURCE_SHA256)
    source = extraction / f"openmpi-{VERSION}"
    if not (source / "configure").is_file():
        raise ValueError("Pinned source archive is missing its expected configure script.")
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(("OMPI_", "OPAL_", "PMIX_"))
                   and key not in {"CFLAGS", "CXXFLAGS", "CPPFLAGS", "LDFLAGS", "LIBS",
                                   "CC", "CXX", "FC", "F77", "LD_PRELOAD"}}
    environment.update({"CC": str(compilers["gcc"]), "CXX": str(compilers["g++"]), "LC_ALL": "C"})
    configure = [str(source / "configure"), f"--prefix={prefix}", *CONFIGURE_OPTIONS]
    print(f"Building verified Open MPI {VERSION}; logs: {evidence}", flush=True)
    checked_command(configure, source, environment, evidence / "configure.log")
    checked_command([str(compilers["make"]), f"-j{jobs}"], source, environment, evidence / "make.log")
    prefix.parent.mkdir(parents=True, exist_ok=True)
    # Claim the previously absent prefix atomically; only this command's new
    # installation may be removed on failure. Never overwrite a user's prefix.
    prefix.mkdir()
    try:
        checked_command([str(compilers["make"]), "install"], source, environment,
                        evidence / "make-install.log")
        library_paths = [str(prefix / part) for part in ("lib", "lib64") if (prefix / part).is_dir()]
        environment["PATH"] = os.pathsep.join([str(prefix / "bin"), environment.get("PATH", "")])
        environment["LD_LIBRARY_PATH"] = os.pathsep.join(library_paths)
        validation = validate_runtime(prefix, evidence, environment)
        report = {"schema_version": 1, "version": VERSION, "prefix": str(prefix),
                  "recorded_at": datetime.now(timezone.utc).isoformat(),
                  "scope": "source integrity, fresh runtime build and two-rank MPI; no scientific ORCA acceptance",
                  "source_url": SOURCE_URL, "source_sha256": SOURCE_SHA256,
                  "source_digest_reference": SOURCE_DIGEST_REFERENCE,
                  "configure_argv": configure, "build_jobs": jobs,
                  "compilers": compilers, "installer_sha256": sha256_file(Path(__file__)),
                  "platform": platform.platform(), "evidence": str(evidence),
                  "path_entries": [str(prefix / "bin")],
                  "ld_library_path": environment["LD_LIBRARY_PATH"],
                  **validation, "files": file_inventory(prefix)}
        (prefix / "cochem-openmpi-provenance.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
    except BaseException:
        shutil.rmtree(prefix)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--build-root", type=Path, required=True)
    parser.add_argument("--jobs", type=bounded_jobs, default=2)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = external_path(args.output or args.build_root / "openmpi-installation.json")
    if output.is_relative_to(external_path(args.prefix)):
        parser.error("The output report must be outside the fresh installation prefix.")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        report = install(args.prefix, args.build_root, args.jobs)
    except Exception as exc:
        output.write_text(json.dumps({"passed": False, "error": str(exc)}, indent=2) + "\n")
        raise
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"prefix": report["prefix"], "version": report["version"],
                      "runtime_check": report["runtime_check"], "report": str(output)}, indent=2))


if __name__ == "__main__":
    main()
