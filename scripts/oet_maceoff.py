#!/usr/bin/env python3
"""CoChem-TOPOS: ORCA ExtOpt External Optimizer Server/Client Interface for MACE-OFF via mace-torch / ASE.

Mandated by Method Matrix v4 Section 10.7, Section 9B.4, Section 8A.2, and Sections 10.1-10.8.
Implements the external tool file contract and persistent IPC socket daemon for energy and gradient
communication with ORCA 6.1, GOAT, and CREST.

Contract Specifications (Method Matrix v4 §10.1-10.8):
- Input: ORCA writes `<basename>_EXT.extinp.tmp` containing:
    Line 1: `<basename>_EXT.xyz` (standard XYZ in Angstroms)
    Line 2: Charge (integer; must be 0 for MACE-OFF)
    Line 3: Multiplicity (integer >= 1; must be 1 for MACE-OFF)
    Line 4: NCores (integer >= 1)
    Line 5: do_gradient (0 or 1)
    Line 6: (Optional) point charges file path (MACE-OFF has no point-charge embedding)
- Output: `<basename>_EXT.engrad` containing:
    Number of atoms
    Total energy in Eh (Hartree)
    Energy gradient in Eh/bohr (Hartree/bohr) (atom1_x, atom1_y, atom1_z, atom2_x, ...)
- Units & Sign (Method Matrix §10.3):
    Input coordinates: Angstrom
    Output energy: Hartree (Eh) = E_eV / HARTREE_TO_EV
    Output gradient: Eh/bohr = (-Force_eV_per_Angstrom) * BOHR_TO_ANGSTROM / HARTREE_TO_EV
    Both factors come from the installed BASE CODATA 2022 registry.
    Sign flip is mandatory: ASE returns forces F, ORCA requires energy gradients (nabla E = -F).
- Model & Precision (Method Matrix §10.7 & §4.4):
    Default model: 'off24-medium' (official MACE-OFF24 release v0.2, pinned checkpoint)
    Default device: 'cuda' (falls back to 'cpu' or 'mps' if specified)
    Default dtype: 'float64' for geometry optimizations (TightOpt / GOAT), 'float32' for MD
- Physical Domain Constraints (Method Matrix §10.7):
    MACE-OFF is parameterized and trained on neutral, closed-shell organic molecules (charge=0, multiplicity=1).
    Point charges are not supported as MACE-OFF has no point-charge embedding architecture.
- Persistent Daemon Architecture (Method Matrix §8A.2 & §9B.4):
    Supports standalone execution and persistent `MACEOFFServer` / `MACEOFFClient` IPC socket daemon
    to avoid ~30s model reloading overhead during multi-step GOAT exploration (~100*N_atoms calls).
- Committee Uncertainty Quantification (Method Matrix §10.8):
    Supports committee ensemble predictions, calculating mean energy E_bar, mean gradient g_bar,
    normalized energy uncertainty sigma_E, and max atomic force uncertainty U_F.
- Physical Mass Mandate: Dynamic atomic mass resolution strictly via `mendeleev` library.
- Runtime dependency: The verified installed CoChem-BASE package supplies constants
  and nuclear identity. A copied script alone is not a supported calculation runtime.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import socket
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mendeleev
from cochem_base.core import cochem_constants as _physical_constants
from cochem_base.physics.isotopes import get_isotope_mass

# Physical conversion constants (Method Matrix v4 §10.3 & NIST CODATA 2022)
BOHR_TO_ANGSTROM: float = _physical_constants.BOHR_TO_ANGSTROM
ANGSTROM_TO_BOHR: float = _physical_constants.ANGSTROM_TO_BOHR
HARTREE_TO_EV: float = _physical_constants.HARTREE_TO_EV
EV_TO_HARTREE: float = 1.0 / HARTREE_TO_EV
EH_PER_EV: float = EV_TO_HARTREE
BOHR_PER_A: float = ANGSTROM_TO_BOHR
HARTREE_TO_KCAL_MOL: float = _physical_constants.HARTREE_TO_KCAL_MOL
HARTREE_TO_KJ_MOL: float = HARTREE_TO_KCAL_MOL * 4.184
EV_PER_ANG_TO_EH_PER_BOHR: float = EH_PER_EV / BOHR_PER_A
MACE_OFF24_MEDIUM_URL = (
    "https://raw.githubusercontent.com/ACEsuit/mace-off/"
    "91a78c5a9c300d1104700d9352c8bfe449227737/mace_off24/MACE-OFF24_medium.model"
)

logger = logging.getLogger("cochem.topos.oet_maceoff")


@dataclass(frozen=True)
class ExtInpData:
    """Parsed data from ORCA `<base>_EXT.extinp.tmp` file."""

    xyz_file: Path
    charge: int
    multiplicity: int
    ncores: int
    dograd: bool
    pointcharges_file: Path | None = None


@dataclass(frozen=True)
class EngradResult:
    """Calculated energy and gradient results written to `<base>_EXT.engrad`."""

    num_atoms: int
    energy_Eh: float
    gradient_Eh_bohr: list[float]
    atom_symbols: list[str]
    coordinates_angstrom: list[tuple[float, float, float]]
    engrad_file: Path
    uncertainty_energy_Eh: float | None = None
    uncertainty_force_max: float | None = None
    provenance_tag: str = "[M]"


@dataclass
class MACEOFFConfig:
    """Configuration options for MACE-OFF calculation execution."""

    model: str = "off24-medium"
    device: str = "cuda"
    default_dtype: str = "float64"
    model_path: str | None = None
    enable_ensemble: bool = False
    ensemble_models: list[str] | None = None
    eps_energy: float | None = None
    eps_force: float | None = None
    uncertainty_marker_file: str | None = None
    server_mode: bool = False
    server_host: str = "localhost"
    server_port: int = 8890
    scf_tole: float = 1e-5
    verbose: bool = False


def get_element_atomic_mass(symbol: str) -> float:
    """Resolve the assigned or principal measured isotope through Mendeleev."""
    return get_isotope_mass(symbol)


def get_element_atomic_number(symbol: str) -> int:
    """Retrieve atomic number for an element symbol using Mendeleev."""
    clean_sym = symbol.strip().capitalize()
    elem = mendeleev.element(clean_sym)
    atomic_num = elem.atomic_number
    if atomic_num is None:
        raise ValueError(f"Unknown atomic number for element symbol '{symbol}' via Mendeleev.")
    return int(atomic_num)


def get_element_symbol(atomic_number: int) -> str:
    """Retrieve element symbol from atomic number using Mendeleev."""
    elem = mendeleev.element(int(atomic_number))
    sym = elem.symbol
    if sym is None:
        raise ValueError(f"Unknown element symbol for atomic number {atomic_number} via Mendeleev.")
    return str(sym)


def read_extinp(path: str | Path) -> ExtInpData:
    """Parse an ORCA `<base>_EXT.extinp.tmp` external input file.

    Parameters
    ----------
    path : str | Path
        Path to the `.extinp.tmp` file written by ORCA.

    Returns
    -------
    ExtInpData
        Parsed parameters including XYZ path, charge, multiplicity, ncores, dograd.
    """
    p = Path(path).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"ORCA extinp file does not exist: {p}")

    content = p.read_text(encoding="utf-8")
    clean_lines: list[str] = []
    for line in content.splitlines():
        no_comment = line.split("#")[0].strip()
        if no_comment:
            clean_lines.append(no_comment)

    if len(clean_lines) < 5:
        raise ValueError(
            f"Invalid ORCA extinp file {p}: expected at least 5 lines (xyz, charge, mult, ncores, dograd), "
            f"found {len(clean_lines)}"
        )

    xyz_str = clean_lines[0]
    xyz_path = Path(xyz_str)
    if not xyz_path.is_absolute():
        xyz_path = p.parent / xyz_str

    charge = int(clean_lines[1])
    mult = int(clean_lines[2])
    if mult < 1:
        raise ValueError(f"Multiplicity must be >= 1, got {mult}")

    ncores = int(clean_lines[3])
    if ncores < 1:
        ncores = 1

    dograd_int = int(clean_lines[4])
    dograd = bool(dograd_int)

    pcfile: Path | None = None
    if len(clean_lines) > 5:
        pc_str = clean_lines[5]
        pc_candidate = Path(pc_str)
        if not pc_candidate.is_absolute():
            pc_candidate = p.parent / pc_str
        if pc_candidate.is_file():
            pcfile = pc_candidate

    return ExtInpData(
        xyz_file=xyz_path,
        charge=charge,
        multiplicity=mult,
        ncores=ncores,
        dograd=dograd,
        pointcharges_file=pcfile,
    )


def read_xyz(xyz_path: str | Path) -> tuple[list[str], list[tuple[float, float, float]]]:
    """Parse standard XYZ file into element symbols and Cartesian coordinates (Angstrom).

    Parameters
    ----------
    xyz_path : str | Path
        Path to the XYZ file.

    Returns
    -------
    tuple[list[str], list[tuple[float, float, float]]]
        List of atomic symbols and list of (x, y, z) coordinate tuples in Angstroms.
    """
    p = Path(xyz_path).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"XYZ file not found: {p}")

    lines = p.read_text(encoding="utf-8").strip().splitlines()
    if not lines:
        raise ValueError(f"Empty XYZ file: {p}")

    try:
        num_atoms = int(lines[0].strip())
    except ValueError as err:
        raise ValueError(f"Invalid XYZ header in {p}: first line is not an integer atom count: '{lines[0]}'") from err

    symbols: list[str] = []
    coords: list[tuple[float, float, float]] = []

    atom_lines = lines[2 : 2 + num_atoms]
    if len(atom_lines) < num_atoms:
        raise ValueError(
            f"XYZ file {p} declares {num_atoms} atoms but only contains {len(atom_lines)} coordinate lines."
        )

    for idx, line in enumerate(atom_lines, 1):
        parts = line.split()
        if len(parts) < 4:
            raise ValueError(f"Malformed coordinate line {idx} in {p}: '{line}'")
        sym = parts[0].strip().capitalize()
        # Verify valid element with Mendeleev
        _ = get_element_atomic_mass(sym)
        x = float(parts[1])
        y = float(parts[2])
        z = float(parts[3])
        symbols.append(sym)
        coords.append((x, y, z))

    return symbols, coords


def write_xyz(
    xyz_path: str | Path,
    symbols: Sequence[str],
    coords: Sequence[Sequence[float]],
    comment: str = "Generated by CoChem oet_maceoff",
) -> None:
    """Write standard XYZ file with atomic coordinates in Angstroms.

    Parameters
    ----------
    xyz_path : str | Path
        Destination XYZ path.
    symbols : Sequence[str]
        Atomic element symbols.
    coords : Sequence[Sequence[float]]
        Atomic Cartesian coordinates in Angstroms.
    comment : str
        Comment line (line 2 of XYZ).
    """
    p = Path(xyz_path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    num_atoms = len(symbols)
    if num_atoms != len(coords):
        raise ValueError(f"Mismatch between symbol count ({num_atoms}) and coordinate count ({len(coords)})")

    lines = [str(num_atoms), comment]
    for sym, (x, y, z) in zip(symbols, coords, strict=False):
        lines.append(f"{sym:<3} {x:18.10f} {y:18.10f} {z:18.10f}")

    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_engrad(
    engrad_path: str | Path,
    num_atoms: int,
    energy_Eh: float,
    gradient_Eh_bohr: Sequence[float],
    dograd: bool = True,
) -> None:
    """Write ORCA `<basename>_EXT.engrad` file.

    Format strictly matches Method Matrix Section 10.2:
    #
    # Number of atoms: must match the XYZ
    #
    <num_atoms>
    #
    # The current total energy in Eh
    #
    <energy_Eh:.12f>
    #
    # The current gradient in Eh/bohr: Atom1X, Atom1Y, Atom1Z, Atom2X, etc.
    #
    <g1x>
    <g1y>
    ...
    """
    if isinstance(num_atoms, bool) or not isinstance(num_atoms, int) or num_atoms <= 0:
        raise ValueError("The engrad atom count must be a positive integer.")
    if not math.isfinite(float(energy_Eh)):
        raise ValueError("Cannot write a non-finite MACE energy.")
    if dograd and (
        len(gradient_Eh_bohr) != 3 * num_atoms
        or not all(math.isfinite(float(value)) for value in gradient_Eh_bohr)
    ):
        raise ValueError("Cannot write incomplete or non-finite MACE gradients.")
    p = Path(engrad_path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "#",
        "# Number of atoms: must match the XYZ",
        "#",
        f"{num_atoms}",
        "#",
        "# The current total energy in Eh",
        "#",
        f"{energy_Eh:18.12f}",
        "#",
        "# The current gradient in Eh/bohr: Atom1X, Atom1Y, Atom1Z, Atom2X, etc.",
        "#",
    ]

    if dograd:
        for g in gradient_Eh_bohr:
            lines.append(f"{g:18.12f}")
    else:
        for _ in range(num_atoms * 3):
            lines.append(f"{0.0:18.12f}")

    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate_maceoff_constraints(inp_data: ExtInpData) -> None:
    """Enforce physical and model domain constraints mandated in Section 10.7.

    Raises
    ------
    ValueError
        If point charges are specified, or if system is non-neutral / open-shell.
    """
    if inp_data.pointcharges_file is not None:
        raise ValueError(
            "Point charges not supported by MACE-OFF wrapper (no point-charge embedding in MACE-OFF architecture)."
        )
    if inp_data.charge != 0 or inp_data.multiplicity != 1:
        raise ValueError(
            f"MACE-OFF is trained on neutral, closed-shell systems only (got charge={inp_data.charge}, "
            f"multiplicity={inp_data.multiplicity})."
        )


class MACEBackendUnavailableError(RuntimeError):
    """The requested pretrained MACE model cannot produce scientific evidence."""


class PhysicalMACEOFFFallbackCalculator:
    """Retired compatibility name; an untrained pair potential is not MACE evidence."""

    def __init__(self, charge: int = 0, multiplicity: int = 1) -> None:
        raise MACEBackendUnavailableError(
            "The untrained physical MACE fallback was removed. Install mace-torch "
            "in the ML silo and supply the requested pretrained checkpoint."
        )


def create_maceoff_calculator(config: MACEOFFConfig) -> Any:
    """Load the requested pretrained MACE model, or fail without substitution.

    ``off24-medium`` selects the pinned official release v0.2 checkpoint.
    The upstream factory's small/medium/large aliases identify MACE-OFF23;
    these aliases must not be presented as MACE-OFF24.
    """
    if config.model_path and not Path(config.model_path).is_file():
        raise FileNotFoundError(f"Requested MACE checkpoint does not exist: {config.model_path}")
    try:
        import torch
        from mace.calculators import MACECalculator, mace_off
    except ImportError as exc:
        raise MACEBackendUnavailableError(
            "PyTorch and mace-torch are required in the selected ML silo."
        ) from exc

    effective_device = config.device
    if str(effective_device).lower().startswith("cuda") and not torch.cuda.is_available():
        logger.info("CUDA unavailable; evaluating the requested MACE model on CPU.")
        effective_device = "cpu"

    try:
        if config.model_path:
            return MACECalculator(
                model_paths=config.model_path,
                device=effective_device,
                default_dtype=config.default_dtype,
            )
        return mace_off(
            model=MACE_OFF24_MEDIUM_URL if config.model == "off24-medium" else config.model,
            device=effective_device,
            default_dtype=config.default_dtype,
        )
    except Exception as exc:
        raise MACEBackendUnavailableError(
            f"Unable to load requested MACE checkpoint {config.model_path or config.model!r}: {exc}"
        ) from exc


def compute_maceoff_energy_gradient(
    atoms: Any,
    calculator: Any,
    dograd: bool = True,
) -> tuple[float, list[float]]:
    """Convert real ASE energy/forces to Eh and Eh/bohr without surrogate results."""
    import numpy as np
    from ase import Atoms

    if calculator is None:
        raise MACEBackendUnavailableError("A loaded calculator is required for MACE evaluation.")
    if not isinstance(atoms, Atoms):
        symbols, coords = atoms
        atoms = Atoms(symbols=symbols, positions=coords)
    if len(atoms) == 0 or not np.isfinite(atoms.get_positions()).all():
        raise ValueError("MACE evaluation requires nonempty finite atomic coordinates.")
    atoms.calc = calculator
    # Backend errors must reach the caller; no alternate potential is scientifically equivalent.
    energy_ev = float(atoms.get_potential_energy())
    if not math.isfinite(energy_ev):
        raise ValueError("MACE calculator returned a non-finite energy.")
    if not dograd:
        return energy_ev * EH_PER_EV, [0.0] * (len(atoms) * 3)
    forces = np.asarray(atoms.get_forces(), dtype=float)
    if forces.shape != (len(atoms), 3) or not np.isfinite(forces).all():
        raise ValueError("MACE calculator returned incomplete or non-finite forces.")
    gradient = -forces * EH_PER_EV / BOHR_PER_A
    return energy_ev * EH_PER_EV, gradient.reshape(-1).tolist()


def compute_committee_uncertainty(
    atoms: Any,
    calculators: Sequence[Any],
    dograd: bool = True,
) -> tuple[float, list[float], float, float]:
    """Evaluate committee / ensemble predictions and calculate uncertainty metrics.

    Implements Method Matrix Section 10.8:
    - Mean energy: E_bar = mean(E_m)
    - Mean gradient: g_bar = mean(g_m)
    - Normalized energy uncertainty: sigma_E = std(E_m) / sqrt(natoms)
    - Force uncertainty: U_F = max over atoms of max over m |g_m,i - g_bar,i|

    Parameters
    ----------
    atoms : Any
        ASE Atoms object or (symbols, coords) tuple.
    calculators : Sequence[Any]
        List of MACE calculators.
    dograd : bool
        Whether to calculate gradients.

    Returns
    -------
    tuple[float, list[float], float, float]
        Mean energy in Eh, mean gradient in Eh/bohr, sigma_E in Eh, and U_F in Eh/bohr.
    """
    m_count = len(calculators)
    if m_count == 0:
        raise ValueError("No calculators provided for committee uncertainty evaluation.")

    energies: list[float] = []
    gradients_list: list[list[float]] = []

    for calc in calculators:
        e_m, g_m = compute_maceoff_energy_gradient(atoms, calc, dograd=dograd)
        energies.append(e_m)
        gradients_list.append(g_m)

    e_bar = sum(energies) / float(m_count)
    var_e = sum((e - e_bar) ** 2 for e in energies) / float(m_count)
    std_e = math.sqrt(var_e)

    num_atoms = len(atoms) if hasattr(atoms, "__len__") and not isinstance(atoms, tuple) else len(atoms[0])
    sigma_e = std_e / math.sqrt(float(max(1, num_atoms)))

    dim = len(gradients_list[0])
    g_bar = [sum(gradients_list[m][k] for m in range(m_count)) / float(m_count) for k in range(dim)]

    u_f = 0.0
    if dograd:
        for m in range(m_count):
            for k in range(dim):
                diff = abs(gradients_list[m][k] - g_bar[k])
                if diff > u_f:
                    u_f = diff

    return e_bar, g_bar, sigma_e, u_f


class MACEOFFServer:
    """Persistent socket daemon server holding MACE-OFF neural potential in memory.

    Eliminates ~30s model reloading overhead during large-scale GOAT conformer searches (§8A.2, §9B.4).
    """

    def __init__(self, config: MACEOFFConfig) -> None:
        self.config = config
        self.calculator = create_maceoff_calculator(config)
        self.running = False

    def handle_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Process calculation request dictionary and return energy/gradient response."""
        command = payload.get("command", "calculate")
        if command == "ping":
            return {"status": "SUCCESS", "message": "pong", "model": self.config.model}

        symbols = payload.get("symbols", [])
        coords = payload.get("coordinates", [])
        charge = int(payload.get("charge", 0))
        multiplicity = int(payload.get("multiplicity", 1))
        dograd = bool(payload.get("dograd", True))

        if not symbols or not coords:
            return {"status": "ERROR", "error": "Empty symbols or coordinates in request"}

        if charge != 0 or multiplicity != 1:
            return {
                "status": "ERROR",
                "error": f"MACE-OFF requires neutral closed-shell system (charge={charge}, multiplicity={multiplicity})",
            }

        try:
            try:
                from ase import Atoms

                atoms = Atoms(symbols=symbols, positions=coords)
                e_Eh, grad_Eh_bohr = compute_maceoff_energy_gradient(
                    atoms=atoms,
                    calculator=self.calculator,
                    dograd=dograd,
                )
            except Exception:
                e_Eh, grad_Eh_bohr = compute_maceoff_energy_gradient(
                    atoms=(symbols, coords),
                    calculator=self.calculator,
                    dograd=dograd,
                )

            # Reconstruct forces in eV/A for client compatibility
            forces: list[list[float]] = []
            if dograd and len(grad_Eh_bohr) == len(symbols) * 3:
                for i in range(len(symbols)):
                    fx = -grad_Eh_bohr[3 * i] * BOHR_PER_A / EH_PER_EV
                    fy = -grad_Eh_bohr[3 * i + 1] * BOHR_PER_A / EH_PER_EV
                    fz = -grad_Eh_bohr[3 * i + 2] * BOHR_PER_A / EH_PER_EV
                    forces.append([fx, fy, fz])

            return {
                "status": "SUCCESS",
                "energy": e_Eh,
                "energy_hartree": e_Eh,
                "gradients": grad_Eh_bohr,
                "gradients_hartree_bohr": grad_Eh_bohr,
                "forces": forces,
                "scf_threshold": self.config.scf_tole,
                "warnings": [],
            }
        except Exception as exc:
            logger.exception("Error processing calculation in server daemon: %s", exc)
            return {"status": "ERROR", "error": str(exc)}

    def run_server(self, host: str | None = None, port: int | None = None) -> None:
        """Bind and listen for client IPC socket connections."""
        s_host = host or self.config.server_host
        s_port = port or self.config.server_port
        self.running = True

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((s_host, s_port))
            s.listen(5)
            logger.info("MACEOFFServer listening on %s:%d", s_host, s_port)

            while self.running:
                try:
                    conn, addr = s.accept()
                    with conn:
                        data = conn.recv(65536)
                        if not data:
                            continue
                        req = json.loads(data.decode("utf-8"))
                        resp = self.handle_request(req)
                        conn.sendall(json.dumps(resp).encode("utf-8"))
                except KeyboardInterrupt:
                    logger.info("Stopping MACEOFFServer...")
                    self.running = False
                    break
                except Exception as exc:
                    logger.error("Server connection error: %s", exc)


class MACEOFFClient:
    """IPC client communicating with a persistent MACEOFFServer daemon."""

    def __init__(self, host: str = "localhost", port: int = 8890, scf_tole: float = 1e-5) -> None:
        self.host = host
        self.port = port
        self.scf_tole = scf_tole

    def calculate_remote(
        self,
        symbols: Sequence[str],
        coordinates: Sequence[Sequence[float]],
        charge: int = 0,
        multiplicity: int = 1,
        dograd: bool = True,
    ) -> dict[str, Any]:
        """Send coordinates to daemon socket and return calculated energy and gradients."""
        req = {
            "command": "calculate",
            "symbols": list(symbols),
            "coordinates": [list(c) for c in coordinates],
            "charge": charge,
            "multiplicity": multiplicity,
            "dograd": dograd,
        }
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.host, self.port))
            s.sendall(json.dumps(req).encode("utf-8"))
            data = s.recv(65536)
            resp = json.loads(data.decode("utf-8"))
            if isinstance(resp, dict):
                return resp
            return {"status": "ERROR", "error": f"Invalid server response type: {type(resp)}"}


def run_oet_maceoff(
    extinp_path: str | Path,
    config: MACEOFFConfig | None = None,
    calculator: Any | None = None,
) -> EngradResult:
    """Master entrypoint to execute ORCA ExtOpt calculation via MACE-OFF.

    Parameters
    ----------
    extinp_path : str | Path
        Path to `<basename>_EXT.extinp.tmp`.
    config : MACEOFFConfig | None
        Optional custom calculation configuration.
    calculator : Any | None
        Optional pre-instantiated ASE calculator instance (for server reuse).

    Returns
    -------
    EngradResult
        Object containing parsed geometry, energy in Eh, gradients in Eh/bohr,
        and path to the generated `.engrad` file.
    """
    cfg = config or MACEOFFConfig()
    inp_data = read_extinp(extinp_path)
    validate_maceoff_constraints(inp_data)

    symbols, coords = read_xyz(inp_data.xyz_file)
    num_atoms = len(symbols)

    uncertainty_energy: float | None = None
    uncertainty_force: float | None = None

    # Check if client daemon mode requested
    if cfg.server_mode and not calculator:
        client = MACEOFFClient(host=cfg.server_host, port=cfg.server_port, scf_tole=cfg.scf_tole)
        resp = client.calculate_remote(
            symbols=symbols,
            coordinates=coords,
            charge=inp_data.charge,
            multiplicity=inp_data.multiplicity,
            dograd=inp_data.dograd,
        )
        if resp.get("status") != "SUCCESS":
            raise RuntimeError(f"Remote daemon calculation failed: {resp.get('error')}")

        energy_Eh = float(resp["energy_hartree"])
        gradient_Eh_bohr = list(resp.get("gradients_hartree_bohr", []))
    else:
        # Local model / ensemble evaluation
        try:
            from ase.io import read as ase_read

            atoms = ase_read(str(inp_data.xyz_file.resolve()))
        except Exception:
            atoms = (symbols, coords)

        if cfg.enable_ensemble and cfg.ensemble_models:
            calculators = []
            for ens_model in cfg.ensemble_models:
                sub_cfg = MACEOFFConfig(
                    model=ens_model,
                    device=cfg.device,
                    default_dtype=cfg.default_dtype,
                    model_path=cfg.model_path,
                )
                calculators.append(create_maceoff_calculator(sub_cfg))
            energy_Eh, gradient_Eh_bohr, uncertainty_energy, uncertainty_force = compute_committee_uncertainty(
                atoms=atoms,
                calculators=calculators,
                dograd=inp_data.dograd,
            )
        else:
            calc = calculator or create_maceoff_calculator(cfg)
            energy_Eh, gradient_Eh_bohr = compute_maceoff_energy_gradient(
                atoms=atoms,
                calculator=calc,
                dograd=inp_data.dograd,
            )

    # Uncertainty threshold checking (Method Matrix Section 10.8)
    if cfg.eps_energy is not None and uncertainty_energy is not None and uncertainty_energy > cfg.eps_energy:
        logger.warning(
            "MACE-OFF energy uncertainty %.6e Eh exceeds threshold eps_energy %.6e Eh",
            uncertainty_energy,
            cfg.eps_energy,
        )
        if cfg.uncertainty_marker_file:
            Path(cfg.uncertainty_marker_file).write_text(
                f"UNCERTAINTY_EXCEEDED: sigma_E={uncertainty_energy} > {cfg.eps_energy}\n",
                encoding="utf-8",
            )

    if cfg.eps_force is not None and uncertainty_force is not None and uncertainty_force > cfg.eps_force:
        logger.warning(
            "MACE-OFF force uncertainty %.6e Eh/bohr exceeds threshold eps_force %.6e Eh/bohr",
            uncertainty_force,
            cfg.eps_force,
        )
        if cfg.uncertainty_marker_file:
            with open(cfg.uncertainty_marker_file, "a", encoding="utf-8") as mf:
                mf.write(f"UNCERTAINTY_EXCEEDED: U_F={uncertainty_force} > {cfg.eps_force}\n")

    extinp_p = Path(extinp_path).resolve()
    base_name = extinp_p.name
    if base_name.endswith(".extinp.tmp"):
        base_stem = base_name[: -len(".extinp.tmp")]
    elif base_name.endswith(".tmp"):
        base_stem = base_name[: -len(".tmp")]
    else:
        base_stem = extinp_p.stem

    engrad_file = extinp_p.parent / f"{base_stem}.engrad"
    write_engrad(
        engrad_path=engrad_file,
        num_atoms=num_atoms,
        energy_Eh=energy_Eh,
        gradient_Eh_bohr=gradient_Eh_bohr,
        dograd=inp_data.dograd,
    )

    return EngradResult(
        num_atoms=num_atoms,
        energy_Eh=energy_Eh,
        gradient_Eh_bohr=gradient_Eh_bohr,
        atom_symbols=symbols,
        coordinates_angstrom=coords,
        engrad_file=engrad_file,
        uncertainty_energy_Eh=uncertainty_energy,
        uncertainty_force_max=uncertainty_force,
        provenance_tag="[M]",
    )


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point for ORCA external tool execution."""
    parser = argparse.ArgumentParser(
        description="ORCA ExtOpt External Optimizer Wrapper for MACE-OFF (Method Matrix Section 10.7)"
    )
    parser.add_argument("extinp", nargs="?", default=None, help="Path to ORCA external input file (<basename>_EXT.extinp.tmp)")
    parser.add_argument(
        "--model",
        "-m",
        default="off24-medium",
        help="MACE-OFF model: off24-medium (default); small/medium/large select OFF23",
    )
    parser.add_argument(
        "--device",
        "-d",
        default="cuda",
        help="Device to run inference on ('cuda', 'cpu', 'mps', default: 'cuda')",
    )
    parser.add_argument(
        "--dtype",
        "--default-dtype",
        default="float64",
        choices=["float64", "float32"],
        help="Floating point precision for MACE calculator ('float64' for Opt, 'float32' for MD, default: 'float64')",
    )
    parser.add_argument(
        "--model-path",
        default=None,
        help="Path to custom MACE-OFF checkpoint file (.model / .pt)",
    )
    parser.add_argument(
        "--server",
        action="store_true",
        help="Run as persistent background daemon server listening on socket",
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Socket host address for daemon server/client (default: 'localhost')",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=8890,
        help="Socket port for daemon server/client (default: 8890)",
    )
    parser.add_argument(
        "-b",
        "--server-address",
        default=None,
        help="Connect to running daemon server at address 'host:port' (e.g. 'localhost:8890')",
    )
    parser.add_argument(
        "--ensemble",
        action="store_true",
        help="Enable committee ensemble prediction for uncertainty quantification",
    )
    parser.add_argument(
        "--ensemble-models",
        nargs="+",
        default=None,
        help="List of model variants for committee ensemble (e.g. 'small' 'medium' 'large')",
    )
    parser.add_argument(
        "--eps-e",
        type=float,
        default=None,
        help="Energy uncertainty threshold sigma_E in Hartree (Eh)",
    )
    parser.add_argument(
        "--eps-f",
        type=float,
        default=None,
        help="Force uncertainty threshold U_F in Hartree/bohr (Eh/bohr)",
    )
    parser.add_argument(
        "--marker-file",
        default=None,
        help="Path to write uncertainty marker file if thresholds are exceeded",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging output",
    )

    args, _ = parser.parse_known_args(argv)

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Server daemon mode
    if args.server:
        config = MACEOFFConfig(
            model=args.model,
            device=args.device,
            default_dtype=args.dtype,
            model_path=args.model_path,
            server_host=args.host,
            server_port=args.port,
            verbose=args.verbose,
        )
        server = MACEOFFServer(config)
        server.run_server()
        return 0

    if not args.extinp:
        parser.print_help()
        return 1

    server_mode = False
    s_host = args.host
    s_port = args.port
    if args.server_address:
        server_mode = True
        if ":" in args.server_address:
            parts = args.server_address.split(":")
            s_host = parts[0]
            s_port = int(parts[1])
        else:
            s_host = args.server_address

    config = MACEOFFConfig(
        model=args.model,
        device=args.device,
        default_dtype=args.dtype,
        model_path=args.model_path,
        enable_ensemble=args.ensemble,
        ensemble_models=args.ensemble_models or (["small", "medium", "large"] if args.ensemble else None),
        eps_energy=args.eps_e,
        eps_force=args.eps_f,
        uncertainty_marker_file=args.marker_file,
        server_mode=server_mode,
        server_host=s_host,
        server_port=s_port,
        verbose=args.verbose,
    )

    try:
        res = run_oet_maceoff(args.extinp, config=config)
        if args.verbose:
            print(f"[OET_MACEOFF] Successfully generated {res.engrad_file} (Energy: {res.energy_Eh:.10f} Eh)")
        return 0
    except Exception as exc:
        sys.stderr.write(f"[OET_MACEOFF ERROR] {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
