"""
Unit tests for CoChem-TOPOS Graph Cleavage and Pipeline Routing Engine (cochem_topos_graph.py).
Strictly adheres to the Zero-Mock mandate using authentic physical molecular coordinates.
Validates:
1. Dynamic Mendeleev elemental lookup & transition metal identification.
2. Distance matrix & Resonance Protection Trap (1.15x breathing tolerance).
3. Monomer routing to MONOMER_GOAT.
4. The 4-Atom Mathematical Bypass (<4 atoms flagged with BYPASS_GOAT).
5. Weak Complex Triage & Cleavage into independent MonomerSeeds.
6. Strong Complex Triage Protocol (transition metal coordination aborts cleavage).
7. UI Telemetry & Air-Gapped State Export to stage_n_complete.json and user_seeds.
8. Subprocess Safety wrapper and Pydantic serialization.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from ase import Atoms

from cochem_topos.cochem_topos_graph import (
    COVALENT_RADII,
    TopologyAnalysisResult,
    TopologyGraphEngine,
    analyze_molecular_graph,
    get_atomic_mass,
    get_atomic_number,
    get_atomic_symbol,
    get_covalent_radius,
    is_transition_or_coordination_metal,
    parse_xyz_file,
    parse_xyz_string,
    run_crest_secondary_search,
)


class TestMendeleevDynamicProperties:
    """Verifies dynamic property lookups from mendeleev with zero hardcoding."""

    def test_atomic_number_and_symbol_resolution(self) -> None:
        """Confirms atomic number and symbol resolution for various inputs."""
        assert get_atomic_number("H") == 1
        assert get_atomic_number("h") == 1
        assert get_atomic_number(1) == 1
        assert get_atomic_number("C") == 6
        assert get_atomic_number("c") == 6
        assert get_atomic_number(6) == 6
        assert get_atomic_number("Fe") == 26
        assert get_atomic_number("fe") == 26
        assert get_atomic_number(26) == 26
        assert get_atomic_number("Pd") == 46
        assert get_atomic_number("Ru") == 44

        assert get_atomic_symbol(1) == "H"
        assert get_atomic_symbol(6) == "C"
        assert get_atomic_symbol(26) == "Fe"
        assert get_atomic_symbol("fe") == "Fe"

    def test_covalent_radii_dynamic_lookup(self) -> None:
        """Confirms covalent radii retrieved from mendeleev match physical standards."""
        assert pytest.approx(get_covalent_radius("H"), abs=0.02) == 0.31
        assert pytest.approx(get_covalent_radius(1), abs=0.02) == 0.31
        assert pytest.approx(get_covalent_radius("C"), abs=0.03) == 0.73
        assert pytest.approx(get_covalent_radius("N"), abs=0.02) == 0.71
        assert pytest.approx(get_covalent_radius("O"), abs=0.02) == 0.66
        assert pytest.approx(get_covalent_radius("F"), abs=0.02) == 0.57
        assert pytest.approx(get_covalent_radius("Ar"), abs=0.02) == 1.06

        # Check mapping proxy
        assert pytest.approx(COVALENT_RADII["H"], abs=0.02) == 0.31
        assert pytest.approx(COVALENT_RADII[6], abs=0.03) == 0.73

    def test_atomic_mass_dynamic_lookup(self) -> None:
        """Confirms dynamic mass lookup from mendeleev adheres to Mendeleev mandate."""
        assert pytest.approx(get_atomic_mass("H"), abs=0.01) == 1.008
        assert pytest.approx(get_atomic_mass("C"), abs=0.01) == 12.011
        assert pytest.approx(get_atomic_mass("O"), abs=0.01) == 15.999
        assert pytest.approx(get_atomic_mass("Fe"), abs=0.01) == 55.845

    def test_transition_metal_identification(self) -> None:
        """Confirms robust classification of transition and coordination metals."""
        assert is_transition_or_coordination_metal("Fe") is True
        assert is_transition_or_coordination_metal(26) is True
        assert is_transition_or_coordination_metal("Pd") is True
        assert is_transition_or_coordination_metal("Ru") is True
        assert is_transition_or_coordination_metal("Pt") is True
        assert is_transition_or_coordination_metal("Cu") is True
        assert is_transition_or_coordination_metal("La") is True
        assert is_transition_or_coordination_metal("U") is True

        assert is_transition_or_coordination_metal("H") is False
        assert is_transition_or_coordination_metal("C") is False
        assert is_transition_or_coordination_metal("N") is False
        assert is_transition_or_coordination_metal("O") is False
        assert is_transition_or_coordination_metal("Ar") is False

    def test_invalid_element_error(self) -> None:
        """Confirms invalid element inputs raise clean ValueError."""
        with pytest.raises(ValueError, match="Unrecognized chemical element"):
            get_atomic_number("InvalidElementXYZ")


class TestResonanceProtectionTrap:
    """Verifies that the 1.15x scaling factor preserves elongated transition state bonds."""

    def test_elongated_carbon_bond_scaling_protection(self) -> None:
        """
        Tests an elongated C-C bond at 1.65 Angstroms (e.g. transition state).
        With 1.15x breathing tolerance: remains 1 protected single monomer.
        With 1.00x unscaled: falsely fractures into 2 fragments.
        """
        symbols = ["C", "C", "H", "H", "H", "H", "H", "H"]
        coordinates = np.array([
            [-0.8250,  0.0000,  0.0000],
            [ 0.8250,  0.0000,  0.0000],
            [-1.1650,  0.9600,  0.0000],
            [-1.1650, -0.4800,  0.8314],
            [-1.1650, -0.4800, -0.8314],
            [ 1.1650,  0.9600,  0.0000],
            [ 1.1650, -0.4800,  0.8314],
            [ 1.1650, -0.4800, -0.8314],
        ])

        engine_scaled = TopologyGraphEngine(resonance_scale=1.15)
        result_scaled = engine_scaled.analyze_topology(symbols, coordinates)
        assert result_scaled.num_fragments == 1
        assert result_scaled.is_weak_complex is False
        assert result_scaled.classification == "Monomer"
        assert result_scaled.routing_target == "MONOMER_GOAT"

        engine_unscaled = TopologyGraphEngine(resonance_scale=1.00)
        result_unscaled = engine_unscaled.analyze_topology(symbols, coordinates)
        assert result_unscaled.num_fragments == 2
        assert result_unscaled.is_weak_complex is True
        assert result_unscaled.classification == "Weak Complex"
        assert result_unscaled.routing_target == "COUNTERPOISE_ASSEMBLY"


class TestMonomerIdentificationAndBypass:
    """Verifies single covalent molecules and the 4-atom mathematical bypass."""

    def test_water_monomer_with_bypass(self) -> None:
        """Evaluates single water molecule (3 atoms < 4 -> bypass_goat=True)."""
        symbols = ["O", "H", "H"]
        coordinates = np.array([
            [0.0000,  0.0000,  0.1173],
            [0.0000,  0.7572, -0.4692],
            [0.0000, -0.7572, -0.4692],
        ])

        engine = TopologyGraphEngine()
        result = engine.analyze_topology(symbols, coordinates)

        assert isinstance(result, TopologyAnalysisResult)
        assert result.num_atoms == 3
        assert result.num_fragments == 1
        assert result.is_weak_complex is False
        assert result.classification == "Monomer"
        assert result.complex_type == "MONOMER"
        assert result.routing_target == "MONOMER_GOAT"
        assert result.counterpoise_flag is False
        assert len(result.monomers) == 1

        monomer = result.monomers[0]
        assert monomer.num_atoms == 3
        assert monomer.formula == "H2O"
        assert monomer.bypass_goat is True
        assert result.bypass_goat_fragments == [0]

    def test_methane_monomer_no_bypass(self) -> None:
        """Evaluates methane molecule (5 atoms >= 4 -> bypass_goat=False)."""
        symbols = ["C", "H", "H", "H", "H"]
        coordinates = np.array([
            [0.0000,  0.0000,  0.0000],
            [0.6276,  0.6276,  0.6276],
            [0.6276, -0.6276, -0.6276],
            [-0.6276,  0.6276, -0.6276],
            [-0.6276, -0.6276,  0.6276],
        ])

        result = analyze_molecular_graph(symbols, coordinates)

        assert result.num_atoms == 5
        assert result.num_fragments == 1
        assert result.is_weak_complex is False
        assert result.classification == "Monomer"
        assert result.routing_target == "MONOMER_GOAT"
        assert result.monomers[0].bypass_goat is False
        assert result.bypass_goat_fragments == []

    def test_benzene_monomer(self) -> None:
        """Evaluates aromatic benzene ring (12 atoms)."""
        symbols = ["C", "C", "C", "C", "C", "C", "H", "H", "H", "H", "H", "H"]
        coordinates = np.array([
            [ 0.0000,  1.3970,  0.0000],
            [ 1.2098,  0.6985,  0.0000],
            [ 1.2098, -0.6985,  0.0000],
            [ 0.0000, -1.3970,  0.0000],
            [-1.2098, -0.6985,  0.0000],
            [-1.2098,  0.6985,  0.0000],
            [ 0.0000,  2.4790,  0.0000],
            [ 2.1469,  1.2395,  0.0000],
            [ 2.1469, -1.2395,  0.0000],
            [ 0.0000, -2.4790,  0.0000],
            [-2.1469, -1.2395,  0.0000],
            [-2.1469,  1.2395,  0.0000],
        ])

        result = analyze_molecular_graph(symbols, coordinates)
        assert result.num_atoms == 12
        assert result.num_fragments == 1
        assert result.classification == "Monomer"
        assert result.monomers[0].formula == "C6H6"
        assert result.monomers[0].bypass_goat is False


class TestWeakComplexDetectionAndCleavage:
    """Verifies Complex Triage Protocol on non-covalent Van der Waals complexes."""

    def test_water_dimer_cleavage_and_bypass(self) -> None:
        """Tests water dimer cleavage into 2 severed H2O seeds, both with BYPASS_GOAT."""
        symbols = ["O", "H", "H", "O", "H", "H"]
        coordinates = np.array([
            # Monomer A
            [-1.464, -0.019,  0.021],
            [-1.765,  0.888,  0.002],
            [-0.499, -0.008, -0.063],
            # Monomer B
            [ 1.442,  0.001, -0.004],
            [ 1.761, -0.457,  0.778],
            [ 1.745, -0.479, -0.771],
        ])

        engine = TopologyGraphEngine(resonance_scale=1.15)
        result = engine.analyze_topology(symbols, coordinates)

        assert result.num_atoms == 6
        assert result.num_fragments == 2
        assert result.is_weak_complex is True
        assert result.classification == "Weak Complex"
        assert result.complex_type == "WEAK_COMPLEX"
        assert result.routing_target == "COUNTERPOISE_ASSEMBLY"
        assert result.counterpoise_flag is True
        assert len(result.monomers) == 2

        assert result.monomers[0].formula == "H2O"
        assert result.monomers[0].bypass_goat is True
        assert result.monomers[1].formula == "H2O"
        assert result.monomers[1].bypass_goat is True
        assert set(result.bypass_goat_fragments) == {0, 1}

        # Telemetry check
        assert result.shortest_gap is not None
        assert result.shortest_gap.distance > 1.5
        assert result.shortest_gap.is_transition_metal_contact is False

    def test_benzene_water_hetero_complex(self) -> None:
        """Tests benzene...water complex where C6H6 has >=4 atoms and H2O has <4 atoms."""
        symbols = [
            # Benzene (0-11)
            "C", "C", "C", "C", "C", "C",
            "H", "H", "H", "H", "H", "H",
            # Water (12-14)
            "O", "H", "H"
        ]
        coordinates = np.array([
            # Benzene ring in XY plane at Z=0
            [ 0.0000,  1.3970,  0.0000],
            [ 1.2098,  0.6985,  0.0000],
            [ 1.2098, -0.6985,  0.0000],
            [ 0.0000, -1.3970,  0.0000],
            [-1.2098, -0.6985,  0.0000],
            [-1.2098,  0.6985,  0.0000],
            [ 0.0000,  2.4790,  0.0000],
            [ 2.1469,  1.2395,  0.0000],
            [ 2.1469, -1.2395,  0.0000],
            [ 0.0000, -2.4790,  0.0000],
            [-2.1469, -1.2395,  0.0000],
            [-2.1469,  1.2395,  0.0000],
            # Water above pi cloud at Z=3.3 A
            [ 0.0000,  0.0000,  3.3000],
            [ 0.0000,  0.7572,  3.8865],
            [ 0.0000, -0.7572,  3.8865],
        ])

        result = analyze_molecular_graph(symbols, coordinates)
        assert result.num_fragments == 2
        assert result.is_weak_complex is True
        assert result.classification == "Weak Complex"
        assert len(result.monomers) == 2

        m0 = result.monomers[0]
        assert m0.formula == "C6H6"
        assert m0.num_atoms == 12
        assert m0.bypass_goat is False

        m1 = result.monomers[1]
        assert m1.formula == "H2O"
        assert m1.num_atoms == 3
        assert m1.bypass_goat is True

        assert result.bypass_goat_fragments == [1]


class TestStrongComplexTriageProtocol:
    """Verifies Complex Triage Protocol on transition metal coordination complexes."""

    def test_iron_water_coordination_complex(self) -> None:
        """
        Tests Fe...H2O coordination complex at 2.40 A.
        Because shortest inter-fragment distance connects to transition metal Fe,
        it is tagged as STRONG_COMPLEX, cleavage is aborted, and routed to Stage 2.0 as a single unit.
        """
        symbols = ["Fe", "O", "H", "H"]
        coordinates = np.array([
            [0.0000, 0.0000, 0.0000],  # Fe (index 0)
            [0.0000, 0.0000, 2.4000],  # O of H2O (index 1) - coordinate interaction at 2.40 A
            [0.0000, 0.7572, 2.9865],  # H (index 2)
            [0.0000, -0.7572, 2.9865], # H (index 3)
        ])

        engine = TopologyGraphEngine(resonance_scale=1.15)
        result = engine.analyze_topology(symbols, coordinates)

        assert result.is_strong_complex is True
        assert result.is_weak_complex is False
        assert result.classification == "Strong Complex"
        assert result.complex_type == "STRONG_COMPLEX"
        assert result.routing_target == "STRONG_COMPLEX"
        assert result.counterpoise_flag is False

        # Cleavage is aborted: system retained as single unit
        assert len(result.monomers) == 1
        assert result.monomers[0].num_atoms == 4
        assert result.shortest_gap is not None
        assert result.shortest_gap.is_transition_metal_contact is True

    def test_palladium_complex_triage(self) -> None:
        """Tests Pd transition metal complex triage at 2.60 A."""
        symbols = ["Pd", "C", "O"]
        coordinates = np.array([
            [0.0000, 0.0000, 0.0000],  # Pd
            [0.0000, 0.0000, 2.6000],  # C of CO
            [0.0000, 0.0000, 3.7300],  # O of CO
        ])

        result = analyze_molecular_graph(symbols, coordinates)
        assert result.is_strong_complex is True
        assert result.classification == "Strong Complex"
        assert result.complex_type == "STRONG_COMPLEX"
        assert result.counterpoise_flag is False


class TestAirGappedStateAndTelemetryExport:
    """Verifies state serialization, XYZ user seeds export, and stage_n_complete.json tracking."""

    def test_air_gapped_state_export(self, tmp_path: Path) -> None:
        """Confirms isolated monomer coordinate arrays are exported to user_seeds and stage tracker is written."""
        symbols = ["O", "H", "H", "O", "H", "H"]
        coordinates = np.array([
            [-1.5, 0.0, 0.0],
            [-1.8, 0.7, 0.0],
            [-0.6, 0.0, 0.0],
            [ 1.5, 0.0, 0.0],
            [ 1.8, 0.7, 0.0],
            [ 1.8,-0.7, 0.0],
        ])

        engine = TopologyGraphEngine()
        result = engine.analyze_topology(symbols, coordinates)

        tracker_data = result.export_air_gapped_state(workspace=tmp_path)

        assert tracker_data["stage"] == "1.1"
        assert tracker_data["status"] == "COMPLETE"
        assert tracker_data["classification"] == "Weak Complex"
        assert tracker_data["monomer_seeds_stage"] == "Stage 2.0"
        assert tracker_data["parent_complex_stage"] == "Stage 3.0"
        assert len(tracker_data["monomer_seeds"]) == 2

        # Verify exported files on disk
        user_seeds_dir = tmp_path / "CoChem_Artifacts" / "Input_Files" / "user_seeds"
        assert user_seeds_dir.exists()
        xyz_files = list(user_seeds_dir.glob("*.xyz"))
        assert len(xyz_files) == 2

        stage_tracker = tmp_path / "CoChem_Artifacts" / "stage_n_complete.json"
        assert stage_tracker.exists()
        loaded_json = json.loads(stage_tracker.read_text(encoding="utf-8"))
        assert loaded_json["stage"] == "1.1"
        assert loaded_json["secondary_search"]["flags"] == ["--nci", "--nocross", "--noreftopo"]


class TestSubprocessSafety:
    """Verifies safe execution wrapper for external conformational searches."""

    def test_missing_xyz_file_raises_error(self, tmp_path: Path) -> None:
        """Confirms missing input file raises FileNotFoundError before spawning process."""
        missing_file = tmp_path / "non_existent.xyz"
        with pytest.raises(FileNotFoundError):
            run_crest_secondary_search(missing_file, tmp_path)


class TestPydanticSerializationAndParsers:
    """Verifies Pydantic model serialization, validation, and error traps."""

    def test_pydantic_serialization(self) -> None:
        """Verifies JSON round-trip serialization of TopologyAnalysisResult."""
        symbols = ["O", "H", "H"]
        coordinates = np.array([
            [0.0000,  0.0000,  0.1173],
            [0.0000,  0.7572, -0.4692],
            [0.0000, -0.7572, -0.4692],
        ])

        engine = TopologyGraphEngine()
        result = engine.analyze_topology(symbols, coordinates)

        json_str = result.to_json()
        data = json.loads(json_str)

        assert data["num_atoms"] == 3
        assert data["classification"] == "Monomer"
        assert data["routing_target"] == "MONOMER_GOAT"

        reconstructed = TopologyAnalysisResult.model_validate(data)
        assert reconstructed.num_atoms == result.num_atoms
        assert reconstructed.routing_target == result.routing_target

    def test_parse_xyz_string_and_file(self, tmp_path: Path) -> None:
        """Validates XYZ parser on both raw strings and disk files."""
        raw_xyz = """3
Water monomer test coordinate
O  0.0000  0.0000  0.1173
H  0.0000  0.7572 -0.4692
H  0.0000 -0.7572 -0.4692
"""
        parsed_symbols, parsed_coords, title = parse_xyz_string(raw_xyz)
        assert parsed_symbols == ["O", "H", "H"]
        assert parsed_coords.shape == (3, 3)

        file_path = tmp_path / "water.xyz"
        file_path.write_text(raw_xyz, encoding="utf-8")

        file_symbols, file_coords, _ = parse_xyz_file(file_path)
        assert file_symbols == parsed_symbols
        np.testing.assert_allclose(file_coords, parsed_coords)

    def test_ase_atoms_ingestion(self) -> None:
        """Validates ingestion from an ASE Atoms object."""
        atoms = Atoms(symbols=["O", "H", "H"], positions=[
            [0.0000,  0.0000,  0.1173],
            [0.0000,  0.7572, -0.4692],
            [0.0000, -0.7572, -0.4692],
        ])

        engine = TopologyGraphEngine()
        result = engine.analyze_atoms(atoms)
        assert result.classification == "Monomer"
        assert result.routing_target == "MONOMER_GOAT"
        assert result.num_atoms == 3

    def test_empty_coordinates_error(self) -> None:
        """Confirms empty inputs raise ValueError."""
        engine = TopologyGraphEngine()
        with pytest.raises(ValueError, match="At least one atom"):
            engine.analyze_topology([], np.empty((0, 3)))

    def test_dimension_mismatch_error(self) -> None:
        """Confirms symbol count and coordinate count mismatch raises ValueError."""
        symbols = ["O", "H"]
        coordinates = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],
        ])
        engine = TopologyGraphEngine()
        with pytest.raises(ValueError, match="Mismatch"):
            engine.analyze_topology(symbols, coordinates)
