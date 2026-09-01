"""CoChem Mobile Inorganic Coordination Complex Test Suite (SRS Chunk 06).

Zero-Mock unit and integration tests covering:
- Mendeleev dynamic atomic weight retrieval for transition metals, lanthanides, and actinides.
- Electronic d-electron and net charge validation: [Fe(CN)6]4- (d6) vs [Fe(CN)6]3- (d5).
- [PtCl4]2- (d8 square planar) vs [PtCl6]2- (d6 octahedral).
- [Ru(bpy)3]2+ (kappa=6, CN=6, Q=+2, Delta/Lambda enantiomers).
- [Co(NH3)3Cl3] (fac and mer isomers, Q=0).
- Real-time denticity budget exhaustion and over-allocation rejection.
- 3D coordinate assembly non-overlap and valid bond distances.
- Atomic file-locked JSON, SQLite, and HDF5 serialization and deserialization.
- UI widget state synchronization and budget tracking.
- Tripartite air-gap RPC boundary enforcement.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, List

import mendeleev
import numpy as np
import pytest

from cochem.mobile.inorganic import (
    ChelateAssembler,
    ComplexSummaryCard,
    CoordinateAssembler,
    CoordinationGeometry,
    CoordinationPolyhedron,
    DonorAtom,
    HDF5InorganicSerializer,
    InorganicAirGapClient,
    InorganicAssemblyEngine,
    InorganicAtom3D,
    InorganicBondRecord,
    InorganicBuilderScreen,
    InorganicBuilderWidget,
    InorganicComplex,
    InorganicComplexSchema,
    IsomerPickerWidget,
    IsomerResolver,
    JSONInorganicSerializer,
    Ligand,
    LigandBudgetWidget,
    LigandLibrary,
    LigandSelectorDialog,
    MetalCategory,
    MetalCenter,
    PolyhedronTemplateRegistry,
    SQLiteInorganicStore,
    calculate_formula_weight,
    complex_to_schema,
    get_polyhedron_coordination_number,
)


class TestMendeleevDynamicParameters:
    """Verifies authentic dynamic retrieval of physical masses and radii from Mendeleev."""

    def test_transition_metal_properties(self) -> None:
        """Verify dynamic elemental parameters for transition metals."""
        fe_center = MetalCenter(symbol="Fe", oxidation_state=2, spin_state="low")
        fe_elem = mendeleev.element("Fe")
        assert fe_center.atomic_number == 26
        assert fe_center.atomic_weight == float(fe_elem.atomic_weight)
        assert fe_center.covalent_radius_angstrom == float(fe_elem.covalent_radius) / 100.0
        assert fe_center.category == MetalCategory.TRANSITION_METAL
        assert fe_center.d_electrons == 6  # Group 8 - 2 = 6

        pt_center = MetalCenter(symbol="Pt", oxidation_state=2)
        pt_elem = mendeleev.element("Pt")
        assert pt_center.atomic_number == 78
        assert pt_center.atomic_weight == float(pt_elem.atomic_weight)
        assert pt_center.category == MetalCategory.TRANSITION_METAL
        assert pt_center.d_electrons == 8  # Group 10 - 2 = 8

        ru_center = MetalCenter(symbol="Ru", oxidation_state=2)
        ru_elem = mendeleev.element("Ru")
        assert ru_center.atomic_number == 44
        assert ru_center.atomic_weight == float(ru_elem.atomic_weight)
        assert ru_center.d_electrons == 6  # Group 8 - 2 = 6

    def test_lanthanide_and_actinide_classification(self) -> None:
        """Verify category classification and f-electron calculation for f-block metals."""
        nd_center = MetalCenter(symbol="Nd", oxidation_state=3)
        nd_elem = mendeleev.element("Nd")
        assert nd_center.atomic_number == 60
        assert nd_center.atomic_weight == float(nd_elem.atomic_weight)
        assert nd_center.category == MetalCategory.LANTHANIDE
        assert nd_center.f_electrons == 3  # (60 - 54) - 3 = 3

        u_center = MetalCenter(symbol="U", oxidation_state=4)
        u_elem = mendeleev.element("U")
        assert u_center.atomic_number == 92
        assert u_center.atomic_weight == float(u_elem.atomic_weight)
        assert u_center.category == MetalCategory.ACTINIDE
        assert u_center.f_electrons == 2  # (92 - 86) - 4 = 2

    def test_donor_atom_dynamic_weight(self) -> None:
        """Verify dynamic mass computation for ligand donor atoms."""
        donor_n = DonorAtom(symbol="N", index=0)
        n_elem = mendeleev.element("N")
        assert donor_n.atomic_weight == float(n_elem.atomic_weight)
        assert donor_n.covalent_radius_angstrom == float(n_elem.covalent_radius) / 100.0

        donor_cl = DonorAtom(symbol="Cl", index=1, formal_charge=-1)
        cl_elem = mendeleev.element("Cl")
        assert donor_cl.atomic_weight == float(cl_elem.atomic_weight)
        assert donor_cl.covalent_radius_angstrom == float(cl_elem.covalent_radius) / 100.0


class TestInorganicComplexElectronicValidation:
    """Verifies electronic configurations, d-electron counting, and net charge balancing."""

    def test_iron_hexacyanide_series(self) -> None:
        """Test [Fe(CN)6]4- (d6, Fe(II), Q=-4) vs [Fe(CN)6]3- (d5, Fe(III), Q=-3)."""
        engine = InorganicAssemblyEngine(max_workers=2)
        cn_ligand = LigandLibrary.get("CN")

        # 1. Ferrocyanide [Fe(CN)6]4-
        fe2 = MetalCenter(symbol="Fe", oxidation_state=2, spin_state="low")
        assert fe2.d_electrons == 6
        assert fe2.determine_spin_multiplicity(CoordinationPolyhedron.OCTAHEDRAL) == 1  # Low spin d6 -> singlet

        comp_fe2 = engine.generate_complex(
            metal=fe2,
            polyhedron=CoordinationPolyhedron.OCTAHEDRAL,
            ligands=[cn_ligand] * 6,
        )
        assert comp_fe2.net_charge == -4
        assert comp_fe2.chemical_formula == "[Fe(CN)6]4-"
        assert comp_fe2.spin_multiplicity == 1
        assert comp_fe2.total_denticity == 6
        assert comp_fe2.vacant_sites == 0

        # Dynamic weight validation: Fe mass + 6 * (C + N) mass
        fe_wt = float(mendeleev.element("Fe").atomic_weight)
        cn_wt = calculate_formula_weight("CN")
        expected_wt = fe_wt + 6.0 * cn_wt
        assert pytest.approx(comp_fe2.molecular_weight, rel=1e-5) == expected_wt

        # 2. Ferricyanide [Fe(CN)6]3-
        fe3 = MetalCenter(symbol="Fe", oxidation_state=3, spin_state="low")
        assert fe3.d_electrons == 5
        assert fe3.determine_spin_multiplicity(CoordinationPolyhedron.OCTAHEDRAL) == 2  # Low spin d5 -> doublet

        comp_fe3 = engine.generate_complex(
            metal=fe3,
            polyhedron=CoordinationPolyhedron.OCTAHEDRAL,
            ligands=[cn_ligand] * 6,
        )
        assert comp_fe3.net_charge == -3
        assert comp_fe3.chemical_formula == "[Fe(CN)6]3-"
        assert comp_fe3.spin_multiplicity == 2
        engine.shutdown()

    def test_platinum_chloride_series(self) -> None:
        """Test [PtCl4]2- (d8 square planar, Q=-2) vs [PtCl6]2- (d6 octahedral, Q=-2)."""
        engine = InorganicAssemblyEngine(max_workers=2)
        cl_ligand = LigandLibrary.get("Cl")

        # 1. Tetrachloroplatinate(II) [PtCl4]2- (Square Planar, d8)
        pt2 = MetalCenter(symbol="Pt", oxidation_state=2, spin_state="low")
        assert pt2.d_electrons == 8
        is_compat, msg = pt2.check_geometry_compatibility(CoordinationPolyhedron.SQUARE_PLANAR)
        assert is_compat is True
        assert "strongly favors square planar" in msg

        comp_pt2 = engine.generate_complex(
            metal=pt2,
            polyhedron=CoordinationPolyhedron.SQUARE_PLANAR,
            ligands=[cl_ligand] * 4,
        )
        assert comp_pt2.net_charge == -2
        assert comp_pt2.chemical_formula == "[Pt(Cl)4]2-"
        assert comp_pt2.coordination_number == 4
        assert comp_pt2.spin_multiplicity == 1  # Square planar d8 is diamagnetic singlet

        # 2. Hexachloroplatinate(IV) [PtCl6]2- (Octahedral, d6)
        pt4 = MetalCenter(symbol="Pt", oxidation_state=4, spin_state="low")
        assert pt4.d_electrons == 6
        is_compat4, msg4 = pt4.check_geometry_compatibility(CoordinationPolyhedron.OCTAHEDRAL)
        assert is_compat4 is True
        assert "strongly favors low-spin octahedral" in msg4

        comp_pt4 = engine.generate_complex(
            metal=pt4,
            polyhedron=CoordinationPolyhedron.OCTAHEDRAL,
            ligands=[cl_ligand] * 6,
        )
        assert comp_pt4.net_charge == -2
        assert comp_pt4.chemical_formula == "[Pt(Cl)6]2-"
        assert comp_pt4.coordination_number == 6
        assert comp_pt4.spin_multiplicity == 1  # Low spin d6 is singlet
        engine.shutdown()

    def test_ruthenium_tris_bipyridine_enantiomers(self) -> None:
        """Test [Ru(bpy)3]2+ (kappa=6, CN=6, Q=+2, Delta and Lambda stereoisomers)."""
        engine = InorganicAssemblyEngine(max_workers=2)
        ru2 = MetalCenter(symbol="Ru", oxidation_state=2, spin_state="low")
        bpy = LigandLibrary.get("bpy")
        assert bpy.denticity == 2
        assert bpy.charge == 0

        # Build Delta isomer
        comp_delta = engine.generate_complex(
            metal=ru2,
            polyhedron=CoordinationPolyhedron.OCTAHEDRAL,
            ligands=[bpy, bpy, bpy],
            isomer_state="Delta",
        )
        assert comp_delta.total_denticity == 6
        assert comp_delta.vacant_sites == 0
        assert comp_delta.net_charge == 2
        assert comp_delta.chemical_formula == "[Ru(C10H8N2)3]2+"
        assert comp_delta.spin_multiplicity == 1  # 4d d6 Ru(II) is low spin singlet

        # Build Lambda isomer
        comp_lambda = engine.generate_complex(
            metal=ru2,
            polyhedron=CoordinationPolyhedron.OCTAHEDRAL,
            ligands=[bpy, bpy, bpy],
            isomer_state="Lambda",
        )
        assert comp_lambda.isomer_state == "Lambda"
        assert len(comp_lambda.coordinates_3d) == len(comp_delta.coordinates_3d)

        # Delta and Lambda coordinates should differ in 3D configuration
        delta_coords = np.array([c[1:] for c in comp_delta.coordinates_3d])
        lambda_coords = np.array([c[1:] for c in comp_lambda.coordinates_3d])
        assert not np.allclose(delta_coords, lambda_coords)
        engine.shutdown()

    def test_cobalt_triammine_trichloride_fac_mer(self) -> None:
        """Test [Co(NH3)3Cl3] (fac and mer isomers, Q=0)."""
        engine = InorganicAssemblyEngine(max_workers=2)
        co3 = MetalCenter(symbol="Co", oxidation_state=3, spin_state="low")
        nh3 = LigandLibrary.get("NH3")
        cl = LigandLibrary.get("Cl")

        # Facial isomer
        comp_fac = engine.generate_complex(
            metal=co3,
            polyhedron=CoordinationPolyhedron.OCTAHEDRAL,
            ligands=[nh3, nh3, nh3, cl, cl, cl],
            isomer_state="fac",
        )
        assert comp_fac.net_charge == 0
        assert comp_fac.chemical_formula == "[Co(NH3)3(Cl)3]"
        assert comp_fac.isomer_state == "fac"

        # Meridional isomer
        comp_mer = engine.generate_complex(
            metal=co3,
            polyhedron=CoordinationPolyhedron.OCTAHEDRAL,
            ligands=[nh3, nh3, nh3, cl, cl, cl],
            isomer_state="mer",
        )
        assert comp_mer.net_charge == 0
        assert comp_mer.chemical_formula == "[Co(NH3)3(Cl)3]"
        assert comp_mer.isomer_state == "mer"

        # The two isomers should have different spatial coordinates
        fac_coords = np.array([c[1:] for c in comp_fac.coordinates_3d])
        mer_coords = np.array([c[1:] for c in comp_mer.coordinates_3d])
        assert not np.allclose(fac_coords, mer_coords)
        engine.shutdown()


class TestBudgetingAndOverAllocation:
    """Verifies denticity budgeting, capacity tracking, and rejection of over-allocation."""

    def test_dynamic_budget_tracking(self) -> None:
        """Verify real-time vacant site calculation as ligands are appended."""
        budget = LigandBudgetWidget(coordination_number=6)
        assert budget.vacant_sites == 6
        assert budget.used_denticity == 0
        assert budget.is_full is False

        # Add bidentate en (kappa=2)
        assert budget.can_fit(2) is True
        budget.update_budget(6, 2)
        assert budget.vacant_sites == 4
        assert budget.used_denticity == 2

        # Add tridentate terpy (kappa=3)
        assert budget.can_fit(3) is True
        budget.update_budget(6, 5)
        assert budget.vacant_sites == 1
        assert budget.used_denticity == 5

        # Attempting to add bidentate (kappa=2) when only 1 vacant site remains
        assert budget.can_fit(2) is False

        # Add monodentate aqua (kappa=1) -> fully saturated
        assert budget.can_fit(1) is True
        budget.update_budget(6, 6)
        assert budget.vacant_sites == 0
        assert budget.is_full is True
        assert budget.utilization_percentage == 100.0

    def test_inorganic_complex_over_allocation_rejection(self) -> None:
        """Verify that InorganicComplex raises ValueError when adding ligands beyond CN."""
        metal = MetalCenter(symbol="Ni", oxidation_state=2)
        geometry = PolyhedronTemplateRegistry.get_geometry(CoordinationPolyhedron.SQUARE_PLANAR)
        assert geometry.coordination_number == 4

        comp = InorganicComplex(metal_center=metal, geometry=geometry)
        bpy = LigandLibrary.get("bpy")  # kappa=2
        comp.add_ligand(bpy)
        assert comp.total_denticity == 2
        assert comp.vacant_sites == 2

        comp.add_ligand(bpy)
        assert comp.total_denticity == 4
        assert comp.vacant_sites == 0

        # Attempting to add any additional ligand must raise ValueError
        cl = LigandLibrary.get("Cl")
        with pytest.raises(ValueError, match="Cannot add ligand"):
            comp.add_ligand(cl)

        # Attempting to add EDTA (kappa=6) to octahedral complex with only 4 vacant sites
        oct_geom = PolyhedronTemplateRegistry.get_geometry(CoordinationPolyhedron.OCTAHEDRAL)
        comp_oct = InorganicComplex(metal_center=metal, geometry=oct_geom)
        comp_oct.add_ligand(bpy)  # 2 used, 4 vacant
        edta = LigandLibrary.get("EDTA")  # kappa=6
        with pytest.raises(ValueError, match="Cannot add ligand"):
            comp_oct.add_ligand(edta)


class TestCoordinateAssemblyAndGeometry:
    """Verifies polyhedral unit templates, 3D coordinate generation, and non-overlap."""

    def test_all_polyhedra_templates(self) -> None:
        """Verify that all 11 polyhedral templates have valid unit vectors and vertex counts."""
        polyhedra = list(CoordinationPolyhedron)
        assert len(polyhedra) == 11

        for poly in polyhedra:
            cn = get_polyhedron_coordination_number(poly)
            vectors = PolyhedronTemplateRegistry.get_template(poly)
            assert len(vectors) == cn, f"Polyhedron {poly.value} expected {cn} vertices, got {len(vectors)}"

            # Verify that all vectors have Euclidean norm == 1.0
            for vec in vectors:
                norm = math.sqrt(vec[0] ** 2 + vec[1] ** 2 + vec[2] ** 2)
                assert pytest.approx(norm, rel=1e-5) == 1.0

    def test_coordinate_assembly_non_overlap_and_bond_lengths(self) -> None:
        """Verify that synthesized atoms do not overlap (min distance > 0.8 A) and bond lengths are valid."""
        engine = InorganicAssemblyEngine(max_workers=2)
        fe = MetalCenter(symbol="Fe", oxidation_state=2)
        h2o = LigandLibrary.get("H2O")

        # Synthesize [Fe(H2O)6]2+
        comp = engine.generate_complex(
            metal=fe,
            polyhedron=CoordinationPolyhedron.OCTAHEDRAL,
            ligands=[h2o] * 6,
        )
        assert len(comp.coordinates_3d) == 1 + 6 * 3  # 1 Fe + 6 * (1 O + 2 H) = 19 atoms
        assert len(comp.bonds_graph) == 6 + 6 * 2  # 6 Fe-O coordination + 12 O-H covalent = 18 bonds

        # Check pairwise non-bonded distances
        coords = np.array([c[1:] for c in comp.coordinates_3d])
        n_atoms = len(coords)
        for i in range(n_atoms):
            for j in range(i + 1, n_atoms):
                dist = np.linalg.norm(coords[i] - coords[j])
                assert dist >= 0.8, f"Steric clash detected between atom {i} and {j}: distance={dist:.3f} A"

        # Check Fe-O coordination distance for all Oxygen donor atoms
        fe_radius = fe.covalent_radius_angstrom
        o_radius = DonorAtom(symbol="O", index=0).covalent_radius_angstrom
        expected_feo_dist = fe_radius + o_radius
        oxygen_count = 0
        for sym, x, y, z in comp.coordinates_3d:
            if sym == "O":
                dist_to_fe = math.sqrt(x**2 + y**2 + z**2)
                assert pytest.approx(dist_to_fe, rel=1e-4) == expected_feo_dist
                oxygen_count += 1
        assert oxygen_count == 6
        engine.shutdown()


class TestStorageAndAirGapSerialization:
    """Verifies atomic file-locked JSON, SQLite, and HDF5 persistence and Air-Gap RPC boundary."""

    def test_json_serialization(self) -> None:
        """Verify JSON serialization and schema roundtrip."""
        engine = InorganicAssemblyEngine(max_workers=2)
        comp = engine.generate_complex(
            metal=MetalCenter(symbol="Co", oxidation_state=3),
            polyhedron=CoordinationPolyhedron.OCTAHEDRAL,
            ligands=[LigandLibrary.get("NH3")] * 6,
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "hexaamminecobalt.json"
            saved_path = JSONInorganicSerializer.save_to_file(comp, file_path)
            assert saved_path.exists()

            loaded_schema = JSONInorganicSerializer.load_from_file(saved_path)
            assert loaded_schema.formula == "[Co(NH3)6]3+"
            assert loaded_schema.metal_symbol == "Co"
            assert loaded_schema.oxidation_state == 3
            assert loaded_schema.coordination_number == 6
            assert len(loaded_schema.atoms) == 1 + 6 * 4  # 1 Co + 6 * (1 N + 3 H) = 25
            assert len(loaded_schema.bonds) == 6 + 6 * 3  # 6 Co-N + 18 N-H = 24
        engine.shutdown()

    def test_hdf5_serialization(self) -> None:
        """Verify HDF5 binary serialization and schema reconstruction."""
        engine = InorganicAssemblyEngine(max_workers=2)
        comp = engine.generate_complex(
            metal=MetalCenter(symbol="Pt", oxidation_state=2),
            polyhedron=CoordinationPolyhedron.SQUARE_PLANAR,
            ligands=[LigandLibrary.get("Cl")] * 4,
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            h5_path = Path(tmp_dir) / "platinum_complex.h5"
            HDF5InorganicSerializer.save(comp, h5_path, group_name="ptcl4")
            assert h5_path.exists()

            loaded = HDF5InorganicSerializer.load(h5_path, group_name="ptcl4")
            assert loaded.formula == "[Pt(Cl)4]2-"
            assert loaded.metal_symbol == "Pt"
            assert loaded.polyhedron == "SQUARE_PLANAR"
            assert loaded.net_charge == -2
            assert len(loaded.atoms) == 5
            assert len(loaded.bonds) == 4
        engine.shutdown()

    def test_sqlite_store_crud(self) -> None:
        """Verify thread-safe SQLite CRUD operations with file locking."""
        engine = InorganicAssemblyEngine(max_workers=2)
        comp = engine.generate_complex(
            metal=MetalCenter(symbol="Fe", oxidation_state=2),
            polyhedron=CoordinationPolyhedron.OCTAHEDRAL,
            ligands=[LigandLibrary.get("CN")] * 6,
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "inorganic.db"
            store = SQLiteInorganicStore(db_path)

            # 1. Save
            cid = store.save(comp)
            assert isinstance(cid, str) and len(cid) > 0

            # 2. Get
            retrieved = store.get(cid)
            assert retrieved.formula == "[Fe(CN)6]4-"
            assert retrieved.net_charge == -4

            # 3. Find by formula
            matches = store.find_by_formula("[Fe(CN)6]4-")
            assert len(matches) == 1
            assert matches[0].formula == "[Fe(CN)6]4-"

            # 4. List all
            all_records = store.list_all()
            assert len(all_records) == 1
            assert all_records[0]["id"] == cid

            # 5. Delete
            deleted = store.delete(cid)
            assert deleted is True
            with pytest.raises(KeyError):
                store.get(cid)
        engine.shutdown()

    def test_airgap_rpc_boundary(self) -> None:
        """Verify that heavy quantum optimization requests are safely packaged for RPC queue."""
        engine = InorganicAssemblyEngine(max_workers=2)
        comp = engine.generate_complex(
            metal=MetalCenter(symbol="Ru", oxidation_state=2),
            polyhedron=CoordinationPolyhedron.OCTAHEDRAL,
            ligands=[LigandLibrary.get("bpy")] * 3,
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            client = InorganicAirGapClient(artifact_queue_dir=tmp_dir)
            task = client.package_quantum_rpc_task(
                comp, method="DFT/B3LYP/def2-SVP", task_id="rubpy3_opt_001"
            )
            assert task["task_id"] == "rubpy3_opt_001"
            assert task["status"] == "QUEUED_AIRGAP_RPC"
            assert task["target_partition"] == "T_art"
            assert task["read_only_isolation"] is True
            assert "sha256" in task

            # Check that file was written to queue directory
            task_file = Path(tmp_dir) / "rubpy3_opt_001.json"
            assert task_file.exists()
            content = json.loads(task_file.read_text(encoding="utf-8"))
            assert content["task_id"] == "rubpy3_opt_001"
            assert content["complex"]["formula"] == "[Ru(C10H8N2)3]2+"

            # Unsupported method must raise ValueError
            with pytest.raises(ValueError, match="Quantum method"):
                client.package_quantum_rpc_task(comp, method="UNSUPPORTED_METHOD")
        engine.shutdown()


class TestUIWidgetsAndScreenController:
    """Verifies AnyWidget reactivity, selector dialog filtering, and summary cards."""

    def test_ligand_selector_dialog_filtering(self) -> None:
        """Verify capacity-aware filtering in LigandSelectorDialog."""
        options = LigandSelectorDialog.get_selectable_ligands(vacant_sites=2)
        for opt in options:
            if opt["denticity"] <= 2:
                assert opt["enabled"] is True
            else:
                assert opt["enabled"] is False
                assert "Exceeds capacity" in opt["status_reason"]

        # Select valid ligand
        selected = LigandSelectorDialog.select_ligand("bpy", vacant_sites=2)
        assert selected.name == "2,2'-Bipyridine"
        assert selected.denticity == 2

        # Selecting ligand exceeding capacity raises ValueError
        with pytest.raises(ValueError, match="Cannot select ligand"):
            LigandSelectorDialog.select_ligand("terpy", vacant_sites=2)

    def test_custom_ligand_builder(self) -> None:
        """Verify construction of custom ligands with dynamic Mendeleev donor validation."""
        custom_lig = LigandSelectorDialog.create_and_add_custom(
            name="CustomPhosphineAmine",
            formula="C7H10NP",
            smiles="NCCCP(C)C",
            charge=0,
            denticity=2,
            donor_atom_types=["N", "P"],
            bite_angle=88.0,
        )
        assert custom_lig.name == "CustomPhosphineAmine"
        assert custom_lig.denticity == 2
        assert len(custom_lig.donor_atoms) == 2
        assert custom_lig.donor_atoms[0].symbol == "N"
        assert custom_lig.donor_atoms[1].symbol == "P"

        # Invalid donor atom symbol raises Mendeleev error / exception
        with pytest.raises(Exception):
            LigandSelectorDialog.create_and_add_custom(
                name="InvalidLigand",
                formula="Xx2",
                smiles="[Xx]",
                charge=0,
                denticity=1,
                donor_atom_types=["Xx"],
            )

    def test_summary_card_rendering(self) -> None:
        """Verify chemical summary card dictionary and markdown formatting."""
        engine = InorganicAssemblyEngine(max_workers=2)
        comp = engine.generate_complex(
            metal=MetalCenter(symbol="Fe", oxidation_state=2, spin_state="low"),
            polyhedron=CoordinationPolyhedron.OCTAHEDRAL,
            ligands=[LigandLibrary.get("CN")] * 6,
        )
        summary = ComplexSummaryCard.format_summary(comp)
        assert summary["formula"] == "[Fe(CN)6]4-"
        assert summary["metal"] == "Fe"
        assert summary["d_electrons"] == 6
        assert summary["net_charge"] == -4
        assert summary["spin_multiplicity"] == 1
        assert summary["geometry"] == "Octahedral"

        md = ComplexSummaryCard.render_markdown(comp)
        assert "[Fe(CN)6]4-" in md
        assert "Mendeleev Dynamic" in md
        engine.shutdown()

    def test_inorganic_builder_widget_reactivity(self) -> None:
        """Verify InorganicBuilderWidget state transitions, synchronous build, and async build."""
        widget = InorganicBuilderWidget()
        widget.set_metal("Fe", oxidation_state=2, spin_state="low")
        widget.set_polyhedron(CoordinationPolyhedron.OCTAHEDRAL)

        assert widget.vacant_sites == 6
        assert widget.net_charge == 2

        # Add 6 CN ligands
        cn = LigandLibrary.get("CN")
        for _ in range(6):
            widget.add_ligand(cn)

        assert widget.vacant_sites == 0
        assert widget.net_charge == -4
        assert widget.formula == "[Fe(CN)6]4-"

        # Synchronous build
        schema = widget.build_complex()
        assert schema.formula == "[Fe(CN)6]4-"
        assert schema.net_charge == -4
        assert len(schema.atoms) == 13
        assert len(schema.bonds) == 12

        # Remove a ligand
        removed = widget.remove_ligand(0)
        assert removed.name == "Cyanido"
        assert widget.vacant_sites == 1
        assert widget.net_charge == -3

        # Async build
        future_schema = widget.build_complex_async()
        async_result = future_schema.result(timeout=5.0)
        assert async_result.coordination_number == 6
        assert len(async_result.atoms) == 11

        widget.close()

    def test_screen_controller(self) -> None:
        """Verify InorganicBuilderScreen high-level orchestration."""
        screen = InorganicBuilderScreen(default_metal="Pt", default_oxidation=2)
        screen.widget.set_polyhedron(CoordinationPolyhedron.SQUARE_PLANAR)
        screen.widget.add_ligand("Cl")
        screen.widget.add_ligand("Cl")
        screen.widget.add_ligand("Cl")
        screen.widget.add_ligand("Cl")

        summary = screen.get_summary()
        assert summary["formula"] == "[Pt(Cl)4]2-"
        assert summary["metal"] == "Pt"
        assert summary["oxidation_state"] == 2
        assert summary["polyhedron"] == "SQUARE_PLANAR"
        assert summary["coordination_number"] == 4
        assert summary["vacant_sites"] == 0
        assert summary["net_charge"] == -2
        screen.widget.close()
