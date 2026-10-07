"""One pure molecular input contract for execution, GUI export and scheduling."""
from __future__ import annotations

from typing import Any


def canonical_theory_tier(value: str | None) -> int | None:
    if not value:
        return None
    text = value.strip().upper().removeprefix("T")
    if text not in {str(index) for index in range(10)}:
        raise ValueError("theory_tier must identify a canonical T0--T9 tier")
    return int(text)


def build_molecular_input(
    config: Any, *, basin_id: str = "input_validation", coordinates: Any = None,
    nprocs: int | None = None, maxcore_mb: int | None = None,
) -> Any:
    """Validate native ORCA/PySCF input without writing a deck or authorizing it.

    Execution may provide its aligned coordinates. Preparation uses the input
    frame. Both paths enforce the same method, recipe, grid, Hessian and product
    requirements. Hardware allocation and engine authority remain later gates.
    """
    from cochem_base.calc.calculation_service import parse_run_geometry
    from cochem_base.calc.cochem_calc_input_generator import MoleculeInput
    from cochem_base.geometry.fragment_partitioner import detect_molecular_fragments
    from cochem_base.theory_matrix import ProductClass

    if config.engine not in {"orca", "pyscf"}:
        raise ValueError("The molecular input builder accepts ORCA and PySCF configurations")
    elements, supplied_coordinates = parse_run_geometry(config.geometry)
    coordinates = supplied_coordinates if coordinates is None else coordinates
    product = None
    if config.product_class:
        product = (config.product_class.upper() if config.product_class.upper() in {"A", "B", "C"}
                   else ProductClass(config.product_class).name.rsplit("_", 1)[1])
    tier = canonical_theory_tier(config.theory_tier)
    data = config.model_dump(include=set(MoleculeInput.model_fields))
    data.update(
        basin_id=basin_id, elements=elements, coordinates=coordinates,
        theory_level=" ".join(part for part in (config.method, config.basis_set)
                              if part and part.lower() not in {"built-in", "default"}),
        product_class=product, tier=tier,
        is_weak_complex=len(detect_molecular_fragments(elements, coordinates)) > 1,
    )
    if nprocs is not None:
        data["nprocs"] = nprocs
    if maxcore_mb is not None:
        data["maxcore_mb"] = maxcore_mb
    return MoleculeInput.model_validate(data)
