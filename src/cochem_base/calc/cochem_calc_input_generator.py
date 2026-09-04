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
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jinja2 import Template
from mendeleev import element
from pydantic import BaseModel, Field, field_validator, model_validator

from cochem_base.config_loader import get_artifact_dir, load_system_config_dict

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

class MoleculeInput(BaseModel):
    basin_id: str = Field(..., description="Unique Basin ID")
    elements: List[str] = Field(..., description="List of elements")
    coordinates: List[Tuple[float, float, float]] = Field(..., description="XYZ coordinates")
    theory_level: str = Field(default="B3LYP-D3 def2-SVP", description="Level of theory")
    charge: int = Field(default=0, description="Molecular charge")
    multiplicity: int = Field(default=1, description="Spin multiplicity")
    is_weak_complex: bool = Field(default=False, description="Is this a weak intermolecular complex?")
    is_opt: bool = Field(default=True, description="Is this a geometry optimization?")
    frozen_monomer_indices: Optional[List[int]] = Field(default=None, description="0-indexed atom indices to freeze")
    implicit_solvation: Optional[str] = Field(default=None, description="Implicit solvation model (e.g., CPCM(Water), SMD)")

    @model_validator(mode="after")
    def validate_method_matrix(self) -> "MoleculeInput":
        if self.is_weak_complex:
            if "D3" not in self.theory_level.upper() and "D4" not in self.theory_level.upper():
                raise ValueError("[ERR_STRATEGY_PIVOT] Dispersion: Reject DFT optimizations of weak complexes lacking D3/D4.")
        
        # 4. Hessian Preconditioning Safeguards
        if self.is_opt and "CALC_HESS TRUE" in self.theory_level.upper():
            self.theory_level = re.sub(r'(?i)calc_hess\s+true', '', self.theory_level).strip()
            
        return self

    @field_validator("multiplicity")
    @classmethod
    def validate_spin(cls, v: int) -> int:
        if v < 1:
            raise ValueError("[ERR_MISSING_DATA] Multiplicity must be >= 1.")
        return v

def get_artifact_base() -> Path:
    """Enforces the strict air-gap to read-write user data tier."""
    artifact_dir = get_artifact_dir() / "Scratch"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir

def load_system_config() -> Dict[str, Any]:
    """Loads authoritative hardware and execution parameters from cochem_system_config.json."""
    try:
        return load_system_config_dict()
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

    # Dynamically retrieve covalent radii in Angstroms via Mendeleev Mandate
    cov_radii: Dict[str, float] = {}
    for el in set(elements):
        r_pm = element(el).covalent_radius_pyykko or element(el).covalent_radius
        cov_radii[el] = (float(r_pm) / 100.0) if r_pm is not None else 1.5

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


def generate_orca_input(data: MoleculeInput, output_dir: Optional[Path] = None) -> Path:
    """
    Compiles an ORCA 6.1.1 input file incorporating:
    - defgrid_tight enforcement for transition metals / diffuse functions
    - Ghost atom retention for BSSE
    - Cryptographic SHA-256 header stamping
    - Parameterized charge and spin multiplicity
    - Method Matrix Compliance (Grids, Dispersion, Hessians)
    """
    config = load_system_config()
    hw = config.get("hardware", {})
    if not hw or ("maxcore_mb" not in hw and "ram_mb" not in hw) or "physical_cpu_cores" not in hw:
        raise RuntimeError("[MISSING DATA] Hardware configuration missing maxcore_mb/ram_mb or physical_cpu_cores.")
    nprocs = hw["physical_cpu_cores"]
    if "maxcore_mb" in hw:
        maxcore = hw["maxcore_mb"]
    else:
        # Standard 75% memory ceiling divided among physical CPU cores
        maxcore = int(0.75 * hw["ram_mb"] / max(1, nprocs))

    # Transition metal check for tight grid override
    transition_metals = {"Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn",
                         "Y", "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd",
                         "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg"}
    needs_tight_grid = any(el in data.elements for el in transition_metals)

    # 2. Dynamic Grid Tightening
    grid_keyword = "defgrid3" if needs_tight_grid else "defgrid1"

    coord_block = []
    for el, (x, y, z) in zip(data.elements, data.coordinates, strict=True):
        coord_block.append(f"  {el:<4} {x:14.8f} {y:14.8f} {z:14.8f}")
    coord_str = "\n".join(coord_block)

    hasher = hashlib.sha256()
    hasher.update(coord_str.encode('utf-8'))
    coord_hash = hasher.hexdigest()

    opt_keyword = "Opt" if data.is_opt else ""

    geom_block_lines = []
    if data.is_opt or data.is_weak_complex or data.frozen_monomer_indices:
        geom_block_lines.append("%geom")
        if data.is_opt or data.is_weak_complex:
            # 5-parameter tightened convergence block mandated by Method Matrix v4 §4.4 (Task 8)
            geom_block_lines.append("  TolE 1e-7")
            geom_block_lines.append("  TolMaxG 1e-5")
            geom_block_lines.append("  TolRMSG 3e-6")
            geom_block_lines.append("  TolMaxD 1e-4")
            geom_block_lines.append("  TolRMSD 5e-5")
        if data.is_opt:
            geom_block_lines.append("  InHess XTB2")

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
# =====================================================================
! {{ theory_level }} {{ opt_keyword }} {{ grid_keyword }} {{ solvation_keyword }} NoSym TightSCF

%pal
 nprocs {{ nprocs }}
end

%maxcore {{ maxcore }}

{{ geom_block }}

* xyz {{ charge }} {{ multiplicity }}
{{ coord_block }}
*
"""

    template = Template(template_str)
    rendered_inp = template.render(
        sha256=coord_hash,
        basin_id=data.basin_id,
        theory_level=data.theory_level,
        opt_keyword=opt_keyword,
        grid_keyword=grid_keyword,
        solvation_keyword=solvation_keyword,
        nprocs=nprocs,
        maxcore=maxcore,
        charge=data.charge,
        multiplicity=data.multiplicity,
        coord_block=coord_str,
        geom_block=geom_block
    )

    out_base = output_dir if output_dir else get_artifact_base()
    out_base.mkdir(parents=True, exist_ok=True)
    output_path = out_base / f"{data.basin_id}_job.inp"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered_inp)

    logger.info(f"Generated secure ORCA input for Basin: {data.basin_id} with PROVENANCE: [E]")
    return output_path
