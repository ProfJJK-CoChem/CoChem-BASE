"""Build per-process native engine environments without changing the host state."""

from __future__ import annotations

import os
from pathlib import Path
import platform
import shutil
from typing import Mapping


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
    environment = dict(os.environ if base_env is None else base_env)
    name = engine.lower()
    binary = None
    if executable is not None:
        value = str(Path(executable).expanduser())
        resolved = shutil.which(value, path=environment.get("PATH"))
        binary = Path(resolved or value).resolve()
    selected_mpi = environment.get("COCHEM_ORCA_MPIRUN_BIN")
    orca_runtime = name == "orca" or name.startswith("orca_")
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
    return environment
