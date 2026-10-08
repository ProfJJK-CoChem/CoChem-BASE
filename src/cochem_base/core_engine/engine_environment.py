"""Build per-process native engine environments without changing the host state."""

from __future__ import annotations

import os
import platform
import re
import shutil
from pathlib import Path
from typing import Mapping


def without_credentials(environment: Mapping[str, str]) -> dict[str, str]:
    """Keep GitHub and network authentication out of native calculation children.

    Authentication remains in the controller for authorized archive downloads.
    Native engines require local files and do not need proxy authentication,
    Git credential helpers, Codespaces tokens or Actions runtime credentials.
    """
    blocked_names = {"SSH_AUTH_SOCK", "GIT_ASKPASS", "SSH_ASKPASS", "GH_CONFIG_DIR",
                     "GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_GLOBAL",
                     "GIT_HTTP_EXTRAHEADER", "BASH_ENV", "ENV"}
    result = {}
    for key, value in environment.items():
        name = key.upper()
        if (name in blocked_names or name.startswith(("GH_", "ACTIONS_", "GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))
                or name.endswith("_PROXY")
                or any(marker in name for marker in ("TOKEN", "SECRET", "PASSWORD", "PASSWD",
                                                     "CREDENTIAL", "AUTHORIZATION", "PRIVATE_KEY",
                                                     "ACCESS_KEY", "API_KEY"))
                or re.search(r"(?:^|_)KEY(?:_|$)", name)):
            continue
        result[key] = value
    return result


def _append_paths(environment: dict[str, str], name: str, paths: list[Path]) -> None:
    """Preserve the site's search precedence; add only absent local directories."""
    current = environment.get(name, "")
    entries = current.split(os.pathsep) if current else []
    additions = [str(path) for path in paths if str(path) not in entries]
    if additions:
        environment[name] = os.pathsep.join([*entries, *dict.fromkeys(additions)])


def engine_runtime_environment(
    engine: str,
    base_env: Mapping[str, str] | None = None,
    *,
    executable: str | Path | None = None,
) -> dict[str, str]:
    """Resolve native libraries and ORCA's private MPI only for this child.

    Existing local/HPC library choices keep precedence over adjacent fallback
    directories. Explicit COCHEM_ORCA_* settings select ORCA's separate runtime;
    they never replace QE/CREST or other engines' system/site MPI libraries.
    No value is assigned to ``os.environ`` or to the supplied mapping.
    """
    environment = without_credentials(os.environ if base_env is None else base_env)
    name = engine.lower()
    binary = None
    if executable is not None:
        value = str(Path(executable).expanduser())
        resolved = shutil.which(value, path=environment.get("PATH"))
        binary = Path(resolved or value).resolve()
    selected_mpi = environment.get("COCHEM_ORCA_MPIRUN_BIN")
    orca_runtime = name == "orca" or name.startswith("orca_")
    cfour_runtime = name in {"cfour", "xcfour"}
    if name in {"mpirun", "mpiexec", "orterun"} and binary is not None and selected_mpi:
        orca_runtime = binary == Path(selected_mpi).expanduser().resolve()

    adjacent = []
    if binary is not None:
        adjacent = [directory for directory in (
            binary.parent / "lib", binary.parent.parent / "lib",
        ) if directory.is_dir()]
        if orca_runtime:
            adjacent.insert(0, binary.parent)

    system = platform.system()
    library_variable = {"Linux": "LD_LIBRARY_PATH", "Darwin": "DYLD_LIBRARY_PATH"}.get(system)
    if library_variable:
        _append_paths(environment, library_variable, adjacent)
    elif system == "Windows":
        _append_paths(environment, "PATH", adjacent)

    if orca_runtime:
        from .cpu_allocation import CPUAllocationPolicy, cpu_allocation_policy
        if cpu_allocation_policy(environment) is CPUAllocationPolicy.GITHUB_HOSTED_VCPUS:
            # A hosted virtual CPU is an allocated hardware thread. Match MPI
            # mapping to the audited unit and forbid oversubscription explicitly.
            environment.update(
                OMPI_MCA_hwloc_base_use_hwthreads_as_cpus="1",
                OMPI_MCA_rmaps_base_mapping_policy="hwthread:NOOVERSUBSCRIBE",
                OMPI_MCA_hwloc_base_binding_policy="hwthread",
                OMPI_MCA_rmaps_base_no_oversubscribe="1",
                OMPI_MCA_rmaps_base_oversubscribe="0",
            )
        # ORCA manages MPI ranks itself; math libraries remain serial per rank.
        for variable in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                         "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS"):
            environment[variable] = "1"
        for variable in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
            scoped = f"COCHEM_ORCA_{variable}"
            if scoped in environment:
                environment[variable] = environment[scoped]
        paths = []
        if binary is not None:
            paths.append(str(binary.parent))
        if selected_mpi:
            paths.append(str(Path(selected_mpi).expanduser().absolute().parent))
        if paths:
            environment["PATH"] = os.pathsep.join(
                [*dict.fromkeys(paths), environment.get("PATH", "")]
            ).rstrip(os.pathsep)
    if cfour_runtime:
        # CFOUR launches its companion programs by name. Keep their directory
        # within this child; its reviewed wrapper selects the private libraries.
        if binary is not None:
            environment["PATH"] = os.pathsep.join(
                [str(binary.parent), environment.get("PATH", "")]
            ).rstrip(os.pathsep)
        for variable in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
            scoped = f"COCHEM_CFOUR_{variable}"
            if scoped in environment:
                environment[variable] = environment[scoped]
        # The caller supplies the audited OpenMP allocation. Serial BLAS avoids
        # nesting another thread pool inside each CFOUR OpenMP thread.
        environment.setdefault("OMP_NUM_THREADS", "1")
        environment["OPENBLAS_NUM_THREADS"] = "1"
        environment["MKL_NUM_THREADS"] = "1"
        environment["OMP_DYNAMIC"] = "FALSE"
    return environment
