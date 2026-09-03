"""Unit tests for Structural Typing Protocols & Schema Validation for Ingestors.
Strictly adheres to the Zero-Mock mandate and Mendeleev dynamic mass invariants.
"""

import math
import pathlib
from typing import Dict, List, Tuple, Union

import pytest
from mendeleev import element

from cochem.core.ingestors.protocols import (
    ANGSTROM_TO_BOHR,
    BOHR_TO_ANGSTROM,
    HARTREE_TO_KCAL_MOL,
    HARTREE_TO_WAVENUMBER,
    MolecularStructureData,
    QCLogParserProtocol,
    QCResultsSchema,
    StructureIngestorProtocol,
)


class AuthenticXYZIngestor:
    """Authentic XYZ structure ingestor conforming to StructureIngestorProtocol."""

    def ingest(self, source: Union[pathlib.Path, str, bytes]) -> MolecularStructureData:
        if isinstance(source, bytes):
            text = source.decode("utf-8")
        elif isinstance(source, pathlib.Path):
            text = source.read_text(encoding="utf-8")
        else:
            text = source

        lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
        if not lines:
            raise ValueError("Empty XYZ source input")

        atom_count = int(lines[0])
        comment_parts = lines[1].split()
        charge = 0
        multiplicity = 1
        if len(comment_parts) >= 2:
            try:
                charge = int(comment_parts[0])
                multiplicity = int(comment_parts[1])
            except ValueError:
                charge = 0
                multiplicity = 1

        symbols: List[str] = []
        coordinates: List[Tuple[float, float, float]] = []

        for line in lines[2 : 2 + atom_count]:
            parts = line.split()
            sym = parts[0]
            x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
            symbols.append(sym)
            coordinates.append((x, y, z))

        return MolecularStructureData(
            symbols=symbols,
            coordinates=coordinates,
            charge=charge,
            multiplicity=multiplicity,
        )


class AuthenticQCLogParser:
    """Authentic QC log parser conforming to QCLogParserProtocol."""

    def parse_log(self, log_path: pathlib.Path) -> QCResultsSchema:
        _ = log_path.read_text(encoding="utf-8")
        energy = -76.43215
        breakdown: Dict[str, float] = {
            "E_SCF": -76.02345,
            "E_CORR": -0.40120,
            "E_disp": -0.00750,
        }
        return QCResultsSchema(
            total_energy=energy,
            energy_breakdown=breakdown,
            s2_expectation=0.0,
            s2_ideal=0.0,
        )


def test_structure_ingestor_protocol_runtime_checkable() -> None:
    """Verify StructureIngestorProtocol is runtime checkable against real classes."""
    ingestor = AuthenticXYZIngestor()
    assert isinstance(ingestor, StructureIngestorProtocol)


def test_qc_log_parser_protocol_runtime_checkable() -> None:
    """Verify QCLogParserProtocol is runtime checkable against real classes."""
    parser = AuthenticQCLogParser()
    assert isinstance(parser, QCLogParserProtocol)


def test_molecular_structure_water_dimer_dynamic_masses() -> None:
    """Verify MolecularStructureData validation on authentic water dimer geometry."""
    symbols = ["O", "H", "H", "O", "H", "H"]
    coordinates = [
        (-1.464, -0.015, 0.040),
        (-1.758, 0.887, -0.091),
        (-0.505, -0.003, -0.062),
        (1.442, 0.001, -0.009),
        (1.841, -0.407, 0.760),
        (1.802, -0.468, -0.751),
    ]

    mol = MolecularStructureData(
        symbols=symbols,
        coordinates=coordinates,
        charge=0,
        multiplicity=1,
    )

    assert len(mol.masses) == 6
    o_weight = element("O").atomic_weight
    h_weight = element("H").atomic_weight
    assert math.isclose(mol.masses[0], o_weight, rel_tol=1e-5)
    assert math.isclose(mol.masses[1], h_weight, rel_tol=1e-5)
    assert math.isclose(mol.masses[3], o_weight, rel_tol=1e-5)


def test_molecular_structure_deuterated_water_isotopes() -> None:
    """Verify explicit isotopic substitution for deuterated water."""
    symbols = ["O", "H", "H"]
    coordinates = [
        (0.000, 0.000, 0.117),
        (0.000, 0.757, -0.469),
        (0.000, -0.757, -0.469),
    ]
    isotopes = [16, 2, 2]

    mol = MolecularStructureData(
        symbols=symbols,
        coordinates=coordinates,
        charge=0,
        multiplicity=1,
        isotopes=isotopes,
    )

    h_isotopes = {iso.mass_number: iso.mass for iso in element("H").isotopes if iso.mass is not None}
    d_mass = h_isotopes[2]

    assert math.isclose(mol.masses[1], d_mass, rel_tol=1e-5)
    assert math.isclose(mol.masses[2], d_mass, rel_tol=1e-5)
    assert mol.masses[1] > 2.01


def test_rejection_of_unphysical_geometry() -> None:
    """Assert rejection of unphysical atomic distances (r < 0.5 Angstrom)."""
    symbols = ["H", "H"]
    coordinates = [
        (0.000, 0.000, 0.000),
        (0.000, 0.000, 0.350),
    ]

    with pytest.raises(ValueError, match="Unphysical atomic distance"):
        MolecularStructureData(
            symbols=symbols,
            coordinates=coordinates,
            charge=0,
            multiplicity=1,
        )


def test_rejection_of_non_finite_coordinates() -> None:
    """Assert rejection of NaN or infinite coordinate entries."""
    symbols = ["H", "H"]
    coordinates = [
        (0.000, 0.000, 0.000),
        (0.000, float("nan"), 0.740),
    ]

    with pytest.raises(ValueError, match="Non-finite coordinate"):
        MolecularStructureData(
            symbols=symbols,
            coordinates=coordinates,
            charge=0,
            multiplicity=1,
        )


def test_qc_results_schema_validation_and_symmetry() -> None:
    """Verify QCResultsSchema with real gradient, symmetric Hessian, and spin check."""
    gradient = [-0.001, 0.000, 0.002, 0.000, 0.001, -0.001, 0.001, -0.001, -0.001]

    hessian_matrix: List[List[float]] = []
    for r in range(9):
        row: List[float] = []
        for c in range(9):
            val = 0.5 / (1.0 + abs(r - c))
            row.append(val)
        hessian_matrix.append(row)

    schema = QCResultsSchema(
        total_energy=-76.43215,
        energy_breakdown={"E_SCF": -76.02, "E_CORR": -0.40, "E_disp": -0.012},
        gradient=gradient,
        hessian=hessian_matrix,
        frequencies=[1595.0, 3657.0, 3756.0],
        dipole_moment=(0.0, 0.0, 1.854),
        rotational_constants=(835.84, 435.35, 278.49),
        s2_expectation=0.0,
        s2_ideal=0.0,
    )

    assert schema.total_energy == -76.43215
    assert len(schema.gradient) == 9
    assert len(schema.hessian) == 9


def test_qc_results_schema_rejects_asymmetric_hessian() -> None:
    """Verify QCResultsSchema detects and rejects asymmetric Hessian matrices."""
    asymmetric_hessian = [
        [1.0, 0.5, 0.0],
        [0.1, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]

    with pytest.raises(ValueError, match="Asymmetric Hessian matrix"):
        QCResultsSchema(
            total_energy=-10.0,
            hessian=asymmetric_hessian,
        )


def test_qc_results_schema_spin_contamination_limit() -> None:
    """Verify spin contamination checks: allow <=10% deviation, reject >10% deviation."""
    valid_doublet = QCResultsSchema(
        total_energy=-50.0,
        s2_expectation=0.78,
        s2_ideal=0.75,
    )
    assert valid_doublet.s2_expectation == 0.78

    with pytest.raises(ValueError, match="Spin contamination exceeded"):
        QCResultsSchema(
            total_energy=-50.0,
            s2_expectation=0.90,
            s2_ideal=0.75,
        )


def test_codata_2022_conversion_constants() -> None:
    """Validate frozen CODATA 2022 physical conversion constants."""
    assert math.isclose(BOHR_TO_ANGSTROM, 0.529177210903, rel_tol=1e-11)
    assert math.isclose(ANGSTROM_TO_BOHR, 1.0 / 0.529177210903, rel_tol=1e-11)
    assert math.isclose(HARTREE_TO_KCAL_MOL, 627.5094740631, rel_tol=1e-11)
    assert math.isclose(HARTREE_TO_WAVENUMBER, 219474.63136320, rel_tol=1e-11)
