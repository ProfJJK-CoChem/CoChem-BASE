#!/usr/bin/env python3
"""
CoChem-CORE Stage 2.1: Input Scaffolder
Module: calc/cochem_calc_input_generator.py
Purpose: Pulls deduplicated coordinates from landscape.h5 and dynamically compiles
         engine-specific inputs with cryptographic provenance and rigorous grid overrides.
"""

import hashlib
import logging
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, Tuple, Union

from jinja2 import Template
from mendeleev import element
from numpy.typing import ArrayLike
import numpy as np
from pydantic import BaseModel, Field, field_validator, model_validator

from cochem.core.exceptions import RotationalGridInstabilityError
from cochem_base.exceptions import GridSpecificationError, RedundantDispersionError
from cochem_base.exceptions import HessianSpecificationError, FrozenMonomerViolationError
from cochem_base.exceptions import HardwareAllocationError
from cochem_base.analysis.electronic_sanitizer import ElectronicSanitizer
from cochem_base.mm.quadrature_manager import QuadratureManager
from cochem_base.geometry.fragment_partitioner import detect_molecular_fragments
from cochem_base.theory_matrix import validate_product_class_policy
from cochem_base.config_loader import get_artifact_dir, load_system_config_dict
from cochem_base.geometry.constraints import (
    FrozenConstraintPayload,
    build_reference_co2_h2o_complex,
    format_orca_frozen_monomer_constraints_block,
    formulate_recipe_r2_wilson_constraints,
    get_reference_monomer_geometry,
    get_dynamic_covalent_radius,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

ORCA_SCF_BLOCK = """%scf
 TolE 1.0e-10
 Thresh 1.0e-12
 ConvCheckMode 0
 ConvForced true
 MaxIter 200
end"""


@lru_cache(maxsize=128)
def _nuclear_charge(symbol: str) -> int:
    return int(element(symbol).atomic_number)


def _orca_method_keywords(theory_level: str) -> str:
    """Render supported presentation aliases without altering native composites.

    ORCA takes these displayed functionals and empirical corrections as
    separate keywords. Hyphens in native names such as wB97X-D4, wB97M-V,
    r2SCAN-3c and revDSD-PBEP86-D4 have different semantics and stay intact.
    RI-MP2, DLPNO coupled cluster and the displayed double hybrids require an
    auxiliary correlation basis. AutoAux supplies it when the user has not given
    one; an explicit /C basis or AutoAux choice takes precedence. The caller
    retains the original method string for result provenance.
    """
    rendered = re.sub(
        r"(?i)(?<!\S)(?:(?:B3LYP|PBE0)-(?:D3BJ|D4)|PBE-D4|PWPB95-D4|B2PLYP-D3)(?!\S)",
        lambda match: match[0].replace("-", " "),
        theory_level,
    )
    keywords = {keyword.upper() for keyword in rendered.split()}
    if keywords.intersection({"PWPB95", "B2PLYP", "RI-MP2", "DLPNO-CCSD(T)", "DLPNO-CCSD(T1)"}) and not any(
        keyword == "AUTOAUX" or keyword.endswith("/C") for keyword in keywords
    ):
        rendered += " AutoAux"
    return rendered


class MoleculeInput(BaseModel):
    basin_id: str = Field(..., description="Unique Basin ID")
    elements: List[str] = Field(..., description="List of elements")
    coordinates: List[Tuple[float, float, float]] = Field(..., description="XYZ coordinates")
    theory_level: str = Field(default="B3LYP D3BJ def2-SVP", description="Level of theory")
    charge: int = Field(default=0, strict=True, description="Molecular charge")
    multiplicity: int = Field(default=1, strict=True, description="Spin multiplicity")
    is_weak_complex: bool = Field(default=False, description="Is this a weak intermolecular complex?")
    is_opt: bool = Field(default=True, description="Is this a geometry optimization?")
    is_freq: bool = Field(default=False, description="Is this a harmonic frequency or Hessian calculation?")
    frozen_monomer_indices: Optional[List[int]] = Field(default=None, description="0-indexed atom indices to freeze")
    implicit_solvation: Optional[str] = Field(default=None, description="Implicit solvation model (e.g., CPCM(Water), SMD)")
    grid_stage: Optional[Literal[1, 2, 3]] = None
    recipe: Optional[Literal["R1", "R2"]] = None
    is_vpt2: bool = False
    initial_hessian: Literal["XTB2", "Lindh", "READ"] = "XTB2"
    hessian_file: Optional[Path] = None
    product_class: Optional[Literal["A", "B", "C"]] = None
    tier: Optional[int] = None
    geometry_source: str = "electronic_structure"
    ab_initio_relaxed: bool = False
    cbs_cardinal_pair: Optional[Tuple[int, int]] = None
    nprocs: Optional[int] = Field(default=None, ge=1, strict=True)
    maxcore_mb: Optional[int] = Field(default=None, ge=1, strict=True)

    @model_validator(mode="after")
    def validate_method_matrix(self) -> "MoleculeInput":
        coords = np.asarray(self.coordinates, dtype=float)
        if not self.elements or coords.shape != (len(self.elements), 3) or not np.all(np.isfinite(coords)):
            raise ValueError("Molecular coordinates must be a nonempty, finite N x 3 array matching elements.")
        electrons = sum(_nuclear_charge(symbol) for symbol in self.elements if not symbol.endswith(":")) - self.charge
        if electrons < 0 or self.multiplicity > electrons + 1 or (electrons + self.multiplicity) % 2 != 1:
            raise ValueError("Spin multiplicity is incompatible with the electron count and charge.")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", self.basin_id):
            raise ValueError("basin_id must be a safe filename component.")
        if any(char in self.theory_level for char in "\r\n%#!*"):
            raise ValueError("theory_level must contain only a single ORCA keyword line.")
        if self.implicit_solvation and any(char in self.implicit_solvation for char in "\r\n%#!*"):
            raise ValueError("implicit_solvation must contain a single keyword expression.")
        if "R2SCAN-3C" in self.theory_level.upper().split() and re.search(r"\b(?:DEF2[-_]|(?:AUG-)?CC-|STO-|[36]-\d|MINIX)", self.theory_level, re.I):
            raise ValueError("r2SCAN-3c requires its published built-in composite basis; do not append a different basis")
        if self.recipe:
            self.is_weak_complex = True
            if "theory_level" not in self.model_fields_set:
                self.theory_level = "r2SCAN-3c" if self.recipe == "R1" else "wB97M-V def2-QZVPP def2/J RIJCOSX"
            if self.recipe == "R1" and "R2SCAN-3C" not in self.theory_level.upper().split():
                raise ValueError("Recipe R1 requires r2SCAN-3c.")
            if self.recipe == "R2" and not {"WB97M-V", "DEF2-QZVPP"}.issubset(self.theory_level.upper().split()):
                raise ValueError("Recipe R2 requires wB97M-V/def2-QZVPP.")
            if self.frozen_monomer_indices is None:
                self.frozen_monomer_indices = list(range(len(self.elements)))
            elif set(self.frozen_monomer_indices) != set(range(len(self.elements))):
                raise FrozenMonomerViolationError("Recipes R1 and R2 must freeze every monomer's internal coordinates.")
        if self.frozen_monomer_indices is not None:
            indices = self.frozen_monomer_indices
            if len(set(indices)) != len(indices) or any(i < 0 or i >= len(self.elements) for i in indices):
                raise FrozenMonomerViolationError("Frozen atom indices must be unique and within the molecule.")
        ElectronicSanitizer.sanitize_dft_dispersion(self.theory_level, is_complex=self.is_weak_complex)
        self.resolved_grid()
        if re.search(r"(?i)\bcalc_?hess\s+(?:true|1)\b", self.theory_level):
            raise HessianSpecificationError()
        if re.search(r"(?i)\binhess\b", self.theory_level):
            raise HessianSpecificationError("Set initial_hessian and hessian_file explicitly; InHess belongs in %geom.")
        if self.initial_hessian == "READ":
            if self.hessian_file is None or not self.hessian_file.is_file() or self.hessian_file.stat().st_size == 0:
                raise HessianSpecificationError("InHess READ requires an existing, nonempty Hessian checkpoint.")
            if any(char in str(self.hessian_file) for char in '\r\n"'):
                raise HessianSpecificationError("Unsafe Hessian checkpoint filename.")
        elif self.hessian_file is not None:
            raise HessianSpecificationError("A Hessian checkpoint requires initial_hessian='READ'.")
        if self.product_class is not None:
            if self.tier is None:
                raise ValueError("A declared product class requires an explicit calculation tier.")
            if self.product_class == "B":
                raise ValueError("Product B materials require the periodic plane-wave/PAW engine, not an ORCA molecular XYZ deck.")
            validate_product_class_policy(
                self.product_class, tier=self.tier, solvation=self.implicit_solvation,
                geometry_source=self.geometry_source, ab_initio_relaxed=self.ab_initio_relaxed,
                cbs_cardinal_pair=self.cbs_cardinal_pair,
                method=self.theory_level,
            )
        return self

    def resolved_grid(self) -> str:
        """Resolve a single grid; explicit settings may tighten but never relax the stage."""
        upper = self.theory_level.upper()
        frequencies = self.is_freq or self.is_vpt2 or bool(re.search(r"\b(?:NUMFREQ|ANFREQ|FREQ|VPT2|HESSIAN)\b", upper))
        tier_minimum = 3 if self.tier is not None and self.tier >= 5 else 2 if self.tier == 4 else 1
        minimum = max(tier_minimum, 3 if frequencies or self.recipe == "R2" else self.grid_stage or 1)
        grids = re.findall(r"\bDEFGRID\d+\b", upper)
        if re.search(r"\b(?:GRID|FINALGRID)\d+\b", upper):
            raise GridSpecificationError("Use the DEFGRID1/2/3 lifecycle instead of legacy grid overrides.")
        if len(set(grids)) > 1:
            raise GridSpecificationError("Conflicting quadrature grids in the same calculation.")
        grid = grids[0] if grids else f"DEFGRID{minimum}"
        QuadratureManager.validate_coupled_grid_scf_invariant(grid, is_frequency_or_hessian=frequencies)
        if int(grid[-1]) < minimum or (frequencies or self.recipe == "R2") and self.grid_stage not in (None, 3):
            raise GridSpecificationError(f"This calculation requires DEFGRID{minimum} or tighter.")
        return grid

    @field_validator("multiplicity")
    @classmethod
    def validate_spin(cls, v: int) -> int:
        if v < 1:
            raise ValueError("[ERR_MISSING_DATA] Multiplicity must be >= 1.")
        return v

    @field_validator("frozen_monomer_indices", mode="before")
    @classmethod
    def validate_frozen_indices(cls, values):
        if values is not None and any(isinstance(value, bool) or not isinstance(value, (int, np.integer)) for value in values):
            raise ValueError("Frozen atom indices must be integers, not booleans or floats.")
        return values

def get_artifact_base() -> Path:
    """Enforces the strict air-gap to read-write user data tier."""
    artifact_dir = get_artifact_dir() / "Scratch"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir

def load_system_config(config_path: str | Path | None = None) -> Dict[str, Any]:
    """Loads authoritative hardware and execution parameters from cochem_system_config.json."""
    try:
        return load_system_config_dict(config_path)
    except Exception as e:
        raise RuntimeError(f"[MISSING DATA] Could not load system config: {e}")


def build_internal_coordinate_constraints(
    elements: List[str],
    coordinates: List[Tuple[float, float, float]],
    frozen_indices: List[int],
) -> List[str]:
    """
    Builds ORCA internal coordinate constraint lines ({B i j C}, {A i j k C}, {D i j k l C})
    for each monomer fragment in frozen_indices, locking intramolecular geometry while
    leaving intermolecular degrees of freedom fully unconstrained (Method Matrix §4.4, §9A.1).
    """
    if not frozen_indices:
        return []
    coords = np.asarray(coordinates, dtype=float)
    if coords.shape != (len(elements), 3) or not np.all(np.isfinite(coords)):
        raise ValueError("Internal constraints require finite coordinates matching the elements.")
    if len(frozen_indices) != len(set(frozen_indices)) or any(
        isinstance(i, bool) or not isinstance(i, (int, np.integer)) or i < 0 or i >= len(elements) for i in frozen_indices
    ):
        raise FrozenMonomerViolationError("Frozen atom indices must be valid, integral and unique.")

    # Dynamically retrieve covalent radii in Angstroms via Mendeleev Mandate
    cov_radii: Dict[str, float] = {}
    for el in set(elements):
        cov_radii[el] = get_dynamic_covalent_radius(el)

    # Find intramolecular covalent bonds within frozen atom set
    bonds: List[Tuple[int, int]] = []
    adj: Dict[int, List[int]] = {i: [] for i in frozen_indices}
    for idx_a, i in enumerate(frozen_indices):
        xi, yi, zi = coordinates[i]
        for j in frozen_indices[idx_a + 1:]:
            xj, yj, zj = coordinates[j]
            dist = math.sqrt((xi - xj)**2 + (yi - yj)**2 + (zi - zj)**2)
            cutoff = 1.30 * (cov_radii[elements[i]] + cov_radii[elements[j]])
            if dist <= cutoff:
                bonds.append((min(i, j), max(i, j)))
                adj[i].append(j)
                adj[j].append(i)

    # Connected components to isolate distinct monomer fragments
    visited = set()
    components: List[List[int]] = []
    for i in frozen_indices:
        if i not in visited:
            comp: List[int] = []
            queue = [i]
            visited.add(i)
            while queue:
                curr = queue.pop(0)
                comp.append(curr)
                for neighbor in adj[curr]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            components.append(comp)

    constraint_lines: List[str] = []

    for comp in components:
        comp_set = set(comp)
        comp_bonds = [(i, j) for (i, j) in bonds if i in comp_set and j in comp_set]

        # 1. Intramolecular bonds {B i j C}
        for i, j in sorted(comp_bonds):
            constraint_lines.append(f"{{B {i} {j} C}}")

        # 2. Intramolecular angles {A i j k C} (j is vertex)
        angles = set()
        for j in comp:
            neighbors = sorted(adj[j])
            for idx_a, i in enumerate(neighbors):
                for k in neighbors[idx_a + 1:]:
                    if i != k:
                        u, w = min(i, k), max(i, k)
                        angles.add((u, j, w))
        for i, j, k in sorted(angles):
            constraint_lines.append(f"{{A {i} {j} {k} C}}")

        # 3. Intramolecular dihedrals {D i j k l C}
        dihedrals = set()
        for j, k in comp_bonds:
            for i in adj[j]:
                if i == k:
                    continue
                for l in adj[k]:
                    if l == j or l == i:
                        continue
                    if (i, j) < (l, k):
                        dihedrals.add((i, j, k, l))
                    else:
                        dihedrals.add((l, k, j, i))
        for i, j, k, l in sorted(dihedrals):
            constraint_lines.append(f"{{D {i} {j} {k} {l} C}}")

    return constraint_lines


def generate_orca_input(
    data: MoleculeInput, output_dir: Optional[Path] = None, *, registry_path: str | Path | None = None,
) -> Path:
    """
    Compiles an ORCA 6.1.1 input file incorporating:
    - defgrid_tight enforcement for transition metals / diffuse functions
    - Ghost atom retention for BSSE
    - Cryptographic SHA-256 header stamping
    - Parameterized charge and spin multiplicity
    - Method Matrix Compliance (Grids, Dispersion, Hessians)
    """
    # Revalidate at the write boundary, including models built/copied without validation.
    data = MoleculeInput.model_validate(data.model_dump())
    config = load_system_config(registry_path)
    hw = config.get("hardware", {})
    if not hw or not any(key in hw for key in ("maxcore_mb", "ram_mb", "ram_gb")) or "physical_cpu_cores" not in hw:
        raise RuntimeError("[MISSING DATA] Hardware configuration missing maxcore_mb/ram_mb or physical_cpu_cores.")
    from cochem_base.core_engine.cpu_allocation import audited_cpu_capacity
    try:
        process_slots, _ = audited_cpu_capacity(hw, config.get("execution"))
    except (ValueError, TypeError, KeyError) as error:
        raise HardwareAllocationError(str(error)) from error
    nprocs = data.nprocs or process_slots
    if nprocs > process_slots:
        raise HardwareAllocationError("Requested CPU count exceeds audited allocation capacity.")
    ram_mb = hw.get("ram_mb", float(hw.get("ram_gb", 0)) * 1024)
    if "maxcore_mb" in hw:
        maxcore = int(hw["maxcore_mb"])
        memory_budget = maxcore * process_slots
        if ram_mb:
            memory_budget = min(memory_budget, int(0.75 * ram_mb))
    else:
        # Standard 75% memory ceiling divided among authorized MPI processes
        memory_budget = int(0.75 * ram_mb)
        maxcore = memory_budget // nprocs
    maxcore = data.maxcore_mb or maxcore
    if maxcore < 1 or maxcore * nprocs > memory_budget:
        raise HardwareAllocationError("Requested per-core memory exceeds the audited memory budget.")

    # Transition metal check for tight grid override
    transition_metals = {"Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn",
                         "Y", "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd",
                         "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg"}
    needs_tight_grid = any(el in data.elements for el in transition_metals)
    # 2. Dynamic Grid Tightening: defgrid3 mandated for frequency/Hessian tasks
    grid_keyword = "DEFGRID3" if needs_tight_grid else data.resolved_grid()
    theory_level = _orca_method_keywords(
        re.sub(r"(?i)\bDEFGRID\d+\b", "", data.theory_level).strip()
    )
    if data.is_freq and not re.search(r"(?i)\b(?:NUMFREQ|FREQ)\b", theory_level):
        theory_level += " Freq"
    if data.is_vpt2 and not re.search(r"(?i)\bVPT2\b", theory_level):
        theory_level += " VPT2"
    if data.is_weak_complex:
        fragments = detect_molecular_fragments(data.elements, data.coordinates)
        if data.recipe and len(fragments) < 2:
            raise FrozenMonomerViolationError("Frozen-monomer recipes require at least two distinct fragments.")
        dispersion = ElectronicSanitizer.sanitize_dft_dispersion(
            theory_level, is_complex=True, num_monomers=max(1, len(fragments))
        )
    else:
        dispersion = {}

    coord_block = []
    for el, (x, y, z) in zip(data.elements, data.coordinates, strict=True):
        coord_block.append(f"  {el:<4} {x:.17g} {y:.17g} {z:.17g}")
    coord_str = "\n".join(coord_block)

    hasher = hashlib.sha256()
    hasher.update(coord_str.encode('utf-8'))
    coord_hash = hasher.hexdigest()

    opt_keyword = "Opt" if data.is_opt else ""

    geom_block_lines = []
    if data.is_opt or data.frozen_monomer_indices:
        geom_block_lines.append("%geom")
        if data.is_opt:
            # ORCA can declare convergence with one table criterion slightly
            # unmet (observed for the two-process HF/STO-3G water Opt+Freq job).
            # Request a tenfold margin below all five Method Matrix §4.4
            # acceptance limits. The output parser independently enforces those
            # original limits; the engine's convergence banner is insufficient.
            geom_block_lines.append("  TolE 1e-8")
            geom_block_lines.append("  TolMaxG 1e-6")
            geom_block_lines.append("  TolRMSG 3e-7")
            geom_block_lines.append("  TolMaxD 1e-5")
            geom_block_lines.append("  TolRMSD 5e-6")
            geom_block_lines.append("  MaxIter 200")
        if data.is_opt:
            geom_block_lines.append(f"  InHess {data.initial_hessian}")
            if data.hessian_file is not None:
                geom_block_lines.append(f'  InHessName "{data.hessian_file.resolve()}"')

        # 3. Frozen-Monomer Protocol (Internal Coordinate Constraints - Task 9)
        if data.frozen_monomer_indices:
            constraints = build_internal_coordinate_constraints(
                elements=data.elements,
                coordinates=data.coordinates,
                frozen_indices=data.frozen_monomer_indices,
            )
            if constraints:
                geom_block_lines.append("  Constraints")
                for c_line in constraints:
                    geom_block_lines.append(f"    {c_line}")
                geom_block_lines.append("  end")

        geom_block_lines.append("end")
    geom_block = "\n".join(geom_block_lines)
    
    # 5. Implicit Solvation Injection
    solvation_keyword = data.implicit_solvation if data.implicit_solvation else ""

    template_str = """# =====================================================================
# CoChem-CORE Cryptographic Provenance Stamp: {{ sha256 }}
# Basin ID: {{ basin_id }} | Engine Target: ORCA 6.1.1
{% if automatic_auxiliary %}# Correlation fitting basis: generated AutoAux (no explicit /C basis supplied)
{% endif %}# =====================================================================
! {{ theory_level }} {{ opt_keyword }} {{ grid_keyword }} {{ solvation_keyword }} NoSym TightSCF

%pal
 nprocs {{ nprocs }}
end

%maxcore {{ maxcore }}

{{ scf_block }}

{{ geom_block }}
{% if requires_atm %}
%method
  D3S9 1.0
end
{% endif %}

* xyz {{ charge }} {{ multiplicity }}
{{ coord_block }}
*
"""

    template = Template(template_str)
    rendered_inp = template.render(
        sha256=coord_hash,
        basin_id=data.basin_id,
        theory_level=theory_level,
        automatic_auxiliary="AUTOAUX" in theory_level.upper().split() and "AUTOAUX" not in data.theory_level.upper().split(),
        opt_keyword=opt_keyword,
        grid_keyword=grid_keyword,
        solvation_keyword=solvation_keyword,
        nprocs=nprocs,
        maxcore=maxcore,
        scf_block=ORCA_SCF_BLOCK,
        charge=data.charge,
        multiplicity=data.multiplicity,
        coord_block=coord_str,
        geom_block=geom_block,
        requires_atm=dispersion.get("requires_atm_3body", False)
        and "D3" in dispersion.get("dispersion", ""),
    )

    out_base = output_dir if output_dir else get_artifact_base()
    out_base.mkdir(parents=True, exist_ok=True)
    output_path = out_base / f"{data.basin_id}_job.inp"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered_inp)

    logger.info(f"Generated secure ORCA input for Basin: {data.basin_id} with PROVENANCE: [E]")
    return output_path


def generate_pyscf_input(data: MoleculeInput, output_dir: Optional[Path] = None, *, expected_version: str = "2.14.0") -> Path:
    """Generate an explicit restricted-HF single-point deck without method substitution.

    MolecularInput currently describes ORCA directives. Those are not silently
    translated into unrelated PySCF DFT grids, dispersion models or optimizers.
    Configured CASSCF/NEVPT2 recovery uses the separate T9 micro-silo worker.
    """
    import json

    tokens = data.theory_level.split()
    if len(tokens) != 2 or tokens[0].upper() not in {"HF", "RHF"}:
        raise ValueError("PySCF deck generation requires explicit 'HF basis' or 'RHF basis'; ORCA DFT keywords cannot be silently translated")
    if data.multiplicity != 1 or data.is_opt or data.is_freq or data.is_vpt2 or data.recipe or data.implicit_solvation or data.frozen_monomer_indices or data.hessian_file or data.product_class or data.grid_stage is not None or data.tier not in (None, 2) or data.cbs_cardinal_pair or data.initial_hessian != "XTB2":
        raise ValueError("This PySCF adapter supports restricted closed-shell single-point energies only")
    if data.tier == 2 and tokens[1].upper() not in {"MINI", "STO-3G"}:
        raise ValueError("Canonical Tier T2 requires HF/MINI or HF/STO-3G")
    specification = {
        "atom": [[symbol, list(xyz)] for symbol, xyz in zip(data.elements, data.coordinates, strict=True)],
        "unit": "Angstrom", "basis": tokens[1], "charge": data.charge, "spin": 0,
        "max_memory": (data.maxcore_mb or 1024) * (data.nprocs or 1),
    }
    script = """# Explicit PySCF restricted-HF single-point calculation.
import hashlib
import json
import math
import sys
from pathlib import Path
import numpy as np
import pyscf
from pyscf import gto, scf

if sys.prefix == sys.base_prefix:
    raise RuntimeError("PySCF must execute in its isolated micro-silo")
if pyscf.__version__ != EXPECTED_VERSION:
    raise RuntimeError("PySCF version differs from the pinned requested version")
pyscf.lib.num_threads(PROCESS_THREADS)
specification = json.loads(SPECIFICATION_JSON)
molecule = gto.M(**specification)
calculation = scf.RHF(molecule)
calculation.conv_tol = 1e-10
calculation.max_cycle = 200
calculation.kernel()
if not calculation.converged or not math.isfinite(float(calculation.e_tot)):
    raise RuntimeError("Requested restricted-HF single point did not converge")
gradient = calculation.nuc_grad_method().kernel()
if gradient.shape != (molecule.natm, 3) or not np.isfinite(gradient).all():
    raise RuntimeError("PySCF returned invalid nuclear gradients")
Path(__file__).with_suffix('.result.json').write_text(json.dumps({
    'engine': 'PySCF', 'version': pyscf.__version__, 'method': 'RHF',
    'basis': specification['basis'], 'operation': 'single_point',
    'scf_converged': bool(calculation.converged), 'energy_hartree': float(calculation.e_tot),
    'gradients_hartree_per_bohr': gradient.tolist(),
    'input_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
}, indent=2, allow_nan=False), encoding='utf-8')
""".replace("EXPECTED_VERSION", repr(expected_version)).replace("PROCESS_THREADS", str(data.nprocs or 1)).replace("SPECIFICATION_JSON", repr(json.dumps(specification)))
    out_base = output_dir if output_dir else get_artifact_base()
    out_base.mkdir(parents=True, exist_ok=True)
    output_path = out_base / f"{data.basin_id}_pyscf.py"
    output_path.write_text(script, encoding="utf-8")
    return output_path


def validate_rotational_mode_stability(
    geometry: np.ndarray,
    calc_engine: Callable[[np.ndarray], np.ndarray],
    threshold_cm1: float = 50.0,
    max_delta_cm1: float = 1.0,
) -> bool:
    """Validates that soft intermolecular vibrational modes (< 50 cm^-1) remain rotationally invariant.

    Rotates Cartesian geometry by 45 degrees around non-principal axis v = [1, 1, 1] / sqrt(3)
    using Rodrigues rotation matrix:
        R = I + (sin theta) K + (1 - cos theta) K^2

    Args:
        geometry: (N, 3) Cartesian coordinates.
        calc_engine: Callable taking (N, 3) coordinates and returning 1D array of harmonic frequencies (cm^-1).
        threshold_cm1: Cutoff below which modes are considered soft (default 50.0 cm^-1).
        max_delta_cm1: Maximum allowed variation in frequency after rotation (default 1.0 cm^-1).

    Raises:
        RotationalGridInstabilityError: If any mode < threshold_cm1 shifts by > max_delta_cm1 or flips imaginary.
    """
    coords = np.asarray(geometry, dtype=np.float64)
    orig_freqs = np.asarray(calc_engine(coords), dtype=np.float64)

    # Detect if any calculated vibrational mode satisfies omega < threshold_cm1
    soft_indices = [i for i, w in enumerate(orig_freqs) if w < threshold_cm1]
    if not soft_indices:
        return True

    # Rotate Cartesian geometry by 45 degrees around non-principal axis v = [1, 1, 1] / sqrt(3)
    theta = math.pi / 4.0  # 45 degrees
    v = np.array([1.0, 1.0, 1.0], dtype=np.float64) / math.sqrt(3.0)
    vx, vy, vz = v[0], v[1], v[2]

    # Skew-symmetric matrix K
    K = np.array([
        [0.0, -vz, vy],
        [vz, 0.0, -vx],
        [-vy, vx, 0.0],
    ], dtype=np.float64)

    # Orthogonal rotation matrix: R = I + sin(theta) * K + (1 - cos(theta)) * K^2
    I = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    R = I + math.sin(theta) * K + (1.0 - math.cos(theta)) * (K @ K)

    coords_rot = coords @ R.T
    rot_freqs = np.asarray(calc_engine(coords_rot), dtype=np.float64)

    # Assert that all low-frequency modes remain stable within max_delta_cm1 and do not flip to imaginary
    for idx in soft_indices:
        w_orig = orig_freqs[idx]
        w_rot = rot_freqs[idx]

        if w_orig >= 0.0 and w_rot < 0.0:
            raise RotationalGridInstabilityError(
                f"Rotational grid instability: mode {idx} flipped from {w_orig:.2f} cm^-1 to imaginary {w_rot:.2f} cm^-1 after rotation.",
                delta_cm1=abs(w_rot - w_orig),
            )

        delta = abs(w_rot - w_orig)
        if delta > max_delta_cm1:
            raise RotationalGridInstabilityError(
                f"Rotational grid instability: mode {idx} shifted by {delta:.2f} cm^-1 (exceeds tolerance {max_delta_cm1:.2f} cm^-1; {w_orig:.2f} vs {w_rot:.2f}).",
                delta_cm1=delta,
            )

    return True


def get_dynamic_atomic_mass(symbol: str) -> float:
    """Retrieve dynamic atomic mass in amu via Mendeleev library [M].

    Dynamic Mendeleev Invariant: Static mass and radii dictionaries are strictly forbidden [M].
    """
    clean_sym = symbol.rstrip(":").strip().capitalize()
    el = element(clean_sym)
    mass = getattr(el, "mass", None) or getattr(el, "atomic_weight", None)
    if mass is None:
        raise ValueError(f"Dynamic Mendeleev query failed: no mass found for '{symbol}' [M].")
    return float(mass)


def generate_recipe_r2_orca_deck(
    basin_id: str = "cochem_dimer_recipe_r2",
    symbols: Optional[Sequence[str]] = None,
    coordinates: Optional[Union[Sequence[Sequence[float]], np.ndarray]] = None,
    atoms_co2: Sequence[int] = (0, 1, 2),
    atoms_h2o: Sequence[int] = (3, 4, 5),
    r_com: float = 2.8361,
    charge: int = 0,
    multiplicity: int = 1,
    nprocs: Optional[int] = None,
    maxcore_mb: Optional[int] = None,
    counterpoise: bool = False,
    cp_leg: Optional[str] = None,
    output_dir: Optional[Path] = None,
    filename: Optional[str] = None,
) -> Path:
    """Generate publication-grade ORCA Recipe R2 input deck adhering to Method Matrix v4.1 and SRS Chunk 17 §6.1.

    Adheres strictly to Method Matrix v4.1, Anti-Spoofing Protocol v4, and WBS Task 5.3.2 specifications:
    1. Electronic structure keywords:
       ! wB97M-V def2-QZVPP def2/J RIJCOSX TightOpt TightSCF DEFGRID3
    2. SCF convergence block:
       %scf
         TolE 1.0e-08
         Thresh 1.0e-11
         MaxIter 150
       end
    3. Geometry optimization & Hessian preconditioning:
       %geom
         InHess XTB2
         TolE 1.0e-07
         TolRMSG 3.0e-06
         TolMaxG 1.0e-05
         TolRMSD 5.0e-05
         TolMaxD 1.0e-04
         MaxIter 200
         Constraints
           # Monomer A (CO2) Internal Covalent Coordinates Frozen
           { B 0 1 C }
           { B 0 2 C }
           { A 1 0 2 C }
           # Monomer B (H2O) Internal Covalent Coordinates Frozen
           { B 3 4 C }
           { B 3 5 C }
           { A 4 3 5 C }
         end
       end
    4. Integration with Task 5.3.1 (Wilson Internal Coordinate Locking):
       Ingests reference monomer geometries and Wilson internal coordinate constraints from
       cochem_base.geometry.constraints. Ensures exactly 6 intramolecular constraints and
       zero cross-monomer constraints.
    5. Counterpoise (CP) distance bracketing flags:
       Supports CP keyword and atom fragment indices (1)/(2) or 3-leg ghost atom (':') representations.
    6. Dynamic Mendeleev Invariant:
       Dynamically queries masses and radii using mendeleev.element. Zero static mass dictionaries.

    Returns:
        Path to the generated production .inp file.
    """
    # 1. Geometry Ingestion & Monomer Distortion Verification
    if (symbols is None) != (coordinates is None):
        raise ValueError("Provide both symbols and coordinates, or neither for the reference geometry.")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", basin_id):
        raise ValueError("basin_id must be a safe filename component.")
    if cp_leg not in (None, "dimer", "monomer_a_ghosts", "monomer_b_ghosts"):
        raise ValueError(f"Unknown counterpoise leg: {cp_leg}")
    if symbols is None:
        syms_list, coords_arr, a_co2, a_h2o = build_reference_co2_h2o_complex(r_com=r_com)
        eff_symbols = list(syms_list)
        eff_coords = np.asarray(coords_arr, dtype=np.float64)
        eff_atoms_co2 = tuple(a_co2)
        eff_atoms_h2o = tuple(a_h2o)

        # Verify reference monomer geometry integrity (distortion < 1e-12 A against NIST/CCCBDB)
        r_co1 = float(np.linalg.norm(eff_coords[1] - eff_coords[0]))
        r_co2 = float(np.linalg.norm(eff_coords[2] - eff_coords[0]))
        assert abs(r_co1 - 1.1621) < 1e-12, f"CO2 bond 1 distortion {abs(r_co1 - 1.1621):.2e} A exceeds 1e-12 [M]."
        assert abs(r_co2 - 1.1621) < 1e-12, f"CO2 bond 2 distortion {abs(r_co2 - 1.1621):.2e} A exceeds 1e-12 [M]."
        r_oh1 = float(np.linalg.norm(eff_coords[4] - eff_coords[3]))
        r_oh2 = float(np.linalg.norm(eff_coords[5] - eff_coords[3]))
        assert abs(r_oh1 - 0.9572) < 1e-12, f"H2O bond 1 distortion {abs(r_oh1 - 0.9572):.2e} A exceeds 1e-12 [M]."
        assert abs(r_oh2 - 0.9572) < 1e-12, f"H2O bond 2 distortion {abs(r_oh2 - 0.9572):.2e} A exceeds 1e-12 [M]."
    else:
        eff_symbols = list(symbols)
        eff_coords = np.asarray(coordinates, dtype=np.float64)
        eff_atoms_co2 = tuple(atoms_co2)
        eff_atoms_h2o = tuple(atoms_h2o)

    set_co2 = set(eff_atoms_co2)
    set_h2o = set(eff_atoms_h2o)
    if not set_co2.isdisjoint(set_h2o) or set_co2 | set_h2o != set(range(len(eff_symbols))):
        raise FrozenMonomerViolationError("CO2 and H2O monomers must be disjoint and cover all atoms.")
    if eff_coords.shape != (len(eff_symbols), 3) or not np.all(np.isfinite(eff_coords)):
        raise ValueError("Coordinates must be finite N x 3 values matching the atom symbols.")
    if [eff_symbols[i] for i in eff_atoms_co2] != ["C", "O", "O"] or [eff_symbols[i] for i in eff_atoms_h2o] != ["O", "H", "H"]:
        raise FrozenMonomerViolationError("This Recipe R2 reference helper requires CO2 and H2O atom ordering.")

    # 2. Dynamic Mendeleev Invariant [M]
    total_mass = sum(get_dynamic_atomic_mass(s) for s in eff_symbols)

    # 3. Formulate Wilson Constraints via Task 5.3.1
    constraints = formulate_recipe_r2_wilson_constraints(
        atoms_co2=eff_atoms_co2,
        atoms_h2o=eff_atoms_h2o,
        symbols=eff_symbols,
        coordinates=eff_coords,
    )

    total_constraints = len(constraints.bonds) + len(constraints.angles) + len(constraints.dihedrals)
    assert total_constraints == 6, (
        f"Physical Acceptance Threshold Failure: expected exactly 6 constraints, got {total_constraints} [M]."
    )
    assert len(constraints.bonds) == 4, f"Expected 4 bonds, got {len(constraints.bonds)}"
    assert len(constraints.angles) == 2, f"Expected 2 angles, got {len(constraints.angles)}"
    assert len(constraints.dihedrals) == 0, f"Expected 0 dihedrals, got {len(constraints.dihedrals)}"

    # Check that constraints are purely intramolecular (zero cross-monomer locks)
    for u, v in constraints.bonds:
        assert (u in set_co2 and v in set_co2) or (u in set_h2o and v in set_h2o), (
            f"Cross-monomer bond constraint detected between {u} and {v} [M]."
        )
    for i, j, k in constraints.angles:
        assert ({i, j, k}.issubset(set_co2) or {i, j, k}.issubset(set_h2o)), (
            f"Cross-monomer angle constraint detected across ({i}, {j}, {k}) [M]."
        )

    # 4. Hardware Parameters
    if nprocs is None or maxcore_mb is None:
        hw = load_system_config().get("hardware", {})
        if nprocs is None:
            nprocs = int(hw["physical_cpu_cores"])
        if maxcore_mb is None:
            if "maxcore_mb" in hw:
                maxcore_mb = int(hw["maxcore_mb"])
            else:
                ram_mb = hw.get("ram_mb", float(hw.get("ram_gb", 0)) * 1024)
                maxcore_mb = int(0.75 * ram_mb / max(1, nprocs))
    if nprocs < 1 or maxcore_mb < 1 or multiplicity < 1:
        raise ValueError("CPU count, per-core memory and spin multiplicity must be positive.")

    # 5. Format Electronic Structure Keywords
    if counterpoise and cp_leg is None:
        keywords = "! wB97M-V def2-QZVPP def2/J RIJCOSX TightOpt TightSCF DEFGRID3 CP"
    elif cp_leg in ("monomer_a_ghosts", "monomer_b_ghosts"):
        keywords = "! wB97M-V def2-QZVPP def2/J RIJCOSX TightSCF DEFGRID3"
    else:
        keywords = "! wB97M-V def2-QZVPP def2/J RIJCOSX TightOpt TightSCF DEFGRID3"

    # 6. Format Coordinate Block
    coord_lines: List[str] = []
    for idx, (sym, (x, y, z)) in enumerate(zip(eff_symbols, eff_coords)):
        if counterpoise and cp_leg is None:
            frag = "1" if idx in set_co2 else "2"
            label = f"{sym}({frag})"
        elif cp_leg == "monomer_a_ghosts":
            label = sym if idx in set_co2 else f"{sym}:"
        elif cp_leg == "monomer_b_ghosts":
            label = f"{sym}:" if idx in set_co2 else sym
        else:
            label = sym
        coord_lines.append(f"  {label:<8} {x:.17g} {y:.17g} {z:.17g}")
    coord_str = "\n".join(coord_lines)

    hasher = hashlib.sha256()
    hasher.update(coord_str.encode("utf-8"))
    coord_hash = hasher.hexdigest()

    # 7. Format Geometry Block
    geom_lines = [
        "%geom",
        "  InHess XTB2",
        "  TolE 1.0e-07",
        "  TolRMSG 3.0e-06",
        "  TolMaxG 1.0e-05",
        "  TolRMSD 5.0e-05",
        "  TolMaxD 1.0e-04",
        "  MaxIter 200",
        "  Constraints",
        "    # Monomer A (CO2) Internal Covalent Coordinates Frozen",
    ]
    co2_bonds = sorted([(min(u, v), max(u, v)) for u, v in constraints.bonds if u in set_co2 and v in set_co2])
    for u, v in co2_bonds:
        geom_lines.append(f"    {{ B {u} {v} C }}")

    co2_angles = sorted([a for a in constraints.angles if set(a).issubset(set_co2)])
    for i, j, k in co2_angles:
        geom_lines.append(f"    {{ A {i} {j} {k} C }}")

    geom_lines.append("    # Monomer B (H2O) Internal Covalent Coordinates Frozen")
    h2o_bonds = sorted([(min(u, v), max(u, v)) for u, v in constraints.bonds if u in set_h2o and v in set_h2o])
    for u, v in h2o_bonds:
        geom_lines.append(f"    {{ B {u} {v} C }}")

    h2o_angles = sorted([a for a in constraints.angles if set(a).issubset(set_h2o)])
    for i, j, k in h2o_angles:
        geom_lines.append(f"    {{ A {i} {j} {k} C }}")

    geom_lines.append("  end")
    geom_lines.append("end")
    geom_block = "\n".join(geom_lines)

    # 8. Assemble Full Deck
    deck_content = f"""# =====================================================================
# CoChem-CORE Cryptographic Provenance Stamp: {coord_hash}
# Basin ID: {basin_id} | Engine Target: ORCA 6.1.1 | Recipe: R2 [M]
# Molecular Weight: {total_mass:.4f} g/mol (Mendeleev Dynamic Invariant)
# =====================================================================
{keywords}
%base "{basin_id}"

%pal
  nprocs {nprocs}
end

%maxcore {maxcore_mb}

%scf
  TolE 1.0e-08
  Thresh 1.0e-11
  MaxIter 150
end

{geom_block}

* xyz {charge} {multiplicity}
{coord_str}
*
"""

    out_base = output_dir if output_dir else get_artifact_base()
    out_base.mkdir(parents=True, exist_ok=True)
    target_filename = filename if filename else f"{basin_id}.inp"
    if Path(target_filename).name != target_filename or any(char in target_filename for char in '\r\n\\'):
        raise ValueError("Deck filename must be a single filename component.")
    target_path = out_base / target_filename
    target_path.write_text(deck_content, encoding="utf-8")

    logger.info(f"Generated publication-grade ORCA Recipe R2 input deck at: {target_path} [M]")
    return target_path


generate_recipe_r2_orca_input = generate_recipe_r2_orca_deck


def generate_recipe_r2_counterpoise_bracketing_decks(
    basin_id: str = "cochem_dimer_recipe_r2",
    symbols: Optional[Sequence[str]] = None,
    coordinates: Optional[Union[Sequence[Sequence[float]], np.ndarray]] = None,
    atoms_co2: Sequence[int] = (0, 1, 2),
    atoms_h2o: Sequence[int] = (3, 4, 5),
    r_com: float = 2.8361,
    charge: int = 0,
    multiplicity: int = 1,
    nprocs: Optional[int] = None,
    maxcore_mb: Optional[int] = None,
    output_dir: Optional[Path] = None,
) -> Dict[str, Path]:
    """Generate 3-leg distance bracketing input decks for Boys-Bernardi Counterpoise correction.

    Leg 1 ('dimer'): Supermolecular dimer (AB at dimer geometry, full basis)
    Leg 2 ('monomer_a_ghosts'): Monomer A at dimer geometry with Monomer B ghost atoms (':')
    Leg 3 ('monomer_b_ghosts'): Monomer B at dimer geometry with Monomer A ghost atoms (':')

    Returns:
        Dict[str, Path] mapping leg name to file path.
    """
    out_dir = output_dir or get_artifact_base()
    out_dir.mkdir(parents=True, exist_ok=True)

    decks: Dict[str, Path] = {
        "dimer": generate_recipe_r2_orca_deck(
            basin_id=f"{basin_id}_leg1_dimer",
            symbols=symbols,
            coordinates=coordinates,
            atoms_co2=atoms_co2,
            atoms_h2o=atoms_h2o,
            r_com=r_com,
            charge=charge,
            multiplicity=multiplicity,
            nprocs=nprocs,
            maxcore_mb=maxcore_mb,
            cp_leg="dimer",
            output_dir=out_dir,
            filename=f"{basin_id}_leg1_dimer.inp",
        ),
        "monomer_a_ghosts": generate_recipe_r2_orca_deck(
            basin_id=f"{basin_id}_leg2_monomer_a_ghosts",
            symbols=symbols,
            coordinates=coordinates,
            atoms_co2=atoms_co2,
            atoms_h2o=atoms_h2o,
            r_com=r_com,
            charge=charge,
            multiplicity=multiplicity,
            nprocs=nprocs,
            maxcore_mb=maxcore_mb,
            cp_leg="monomer_a_ghosts",
            output_dir=out_dir,
            filename=f"{basin_id}_leg2_monomer_a_ghosts.inp",
        ),
        "monomer_b_ghosts": generate_recipe_r2_orca_deck(
            basin_id=f"{basin_id}_leg3_monomer_b_ghosts",
            symbols=symbols,
            coordinates=coordinates,
            atoms_co2=atoms_co2,
            atoms_h2o=atoms_h2o,
            r_com=r_com,
            charge=charge,
            multiplicity=multiplicity,
            nprocs=nprocs,
            maxcore_mb=maxcore_mb,
            cp_leg="monomer_b_ghosts",
            output_dir=out_dir,
            filename=f"{basin_id}_leg3_monomer_b_ghosts.inp",
        ),
    }
    return decks


__all__ = [
    "MoleculeInput",
    "get_artifact_base",
    "load_system_config",
    "build_internal_coordinate_constraints",
    "generate_orca_input",
    "generate_pyscf_input",
    "validate_rotational_mode_stability",
    "get_dynamic_atomic_mass",
    "generate_recipe_r2_orca_deck",
    "generate_recipe_r2_orca_input",
    "generate_recipe_r2_counterpoise_bracketing_decks",
]
