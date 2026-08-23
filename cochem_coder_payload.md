Cycle 3: Implement code for prompt at D:\__CoChem\__agentic\.prompts\.SRS\CoChem-SpycFit\.in-progress\Task1_Prompt1_gitignore.md strictly adhering to Zero-Mock mandate. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE. Generate unit tests first. IMPORTANT: You MUST update/create `pytest.ini` to restrict `testpaths` to ONLY the tests you are writing for this prompt, otherwise the global 1500+ test suite will run and crash your context. 
Test Failures from previous run:
Output: ============================= test session starts =============================
platform win32 -- Python 3.13.9, pytest-8.4.2, pluggy-1.5.0
rootdir: D:\__CoChem\GitHub-Repo\CoChem-BASE
configfile: pytest.ini
plugins: anyio-4.10.0, typeguard-4.6.0
collected 69 items

test_suite\test_cochem_torq_master_context.py .F                         [  2%]
test_suite\test_cochem_torq_phases_6_to_10.py ...................        [ 30%]
test_suite\test_spycfit_gitignore.py ................................... [ 81%]
.............                                                            [100%]

================================== FAILURES ===================================
______ TestTorqMasterContextAnchor.test_full_10_phase_funnel_end_to_end _______

self = <test_suite.test_cochem_torq_master_context.TestTorqMasterContextAnchor object at 0x0000022945E77ED0>
tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-7874/test_full_10_phase_funnel_end_0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x000002293C9062C0>

    def test_full_10_phase_funnel_end_to_end(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Executes full 10-Phase pipeline funnel sequentially on real molecular inputs."""
    
        # -------------------------------------------------------------
        # Phase 1: Environment, Registry & SWMR Lock Guards (Stage 0.0)
        # -------------------------------------------------------------
        art_dir = tmp_path / "artifacts"
        scratch_dir = tmp_path / "scratch"
        lib_dir = tmp_path / "lib"
        art_dir.mkdir()
        scratch_dir.mkdir()
        lib_dir.mkdir()
    
        # Air-Gap Check
        assert verify_airgap(str(art_dir), str(scratch_dir)) is True
    
        # Pydantic Hardware Schema Validation
        hw_config = {
            "mpi_threads": 4,
            "gpu_vram_gb": 8.0,
            "maxcore_mb": 4000,
            "scratch_dir": scratch_dir,
            "artifacts_dir": art_dir,
            "torq_lib_dir": lib_dir,
        }
        schema = TorqHardwareSchema(**hw_config)
        assert schema.mpi_threads == 4
        assert schema.gpu_vram_gb == 8.0
    
        # SWMR Lock Guard
        h5_file = art_dir / "landscape.h5"
        lock_file = create_swmr_lock(h5_file)
        assert lock_file.exists()
        remove_swmr_lock(h5_file)
        assert not lock_file.exists()
    
        # -------------------------------------------------------------
        # Phase 2: Dual-Intake Gateway & Topology (Stage 1.0 - 2.0)
        # -------------------------------------------------------------
        xyz_file = tmp_path / "methanol.xyz"
        xyz_file.write_text(METHANOL_XYZ, encoding="utf-8")
        xyz_data = parse_external_xyz(xyz_file)
        symbols = xyz_data["symbols"]
        raw_coords = xyz_data["coordinates"]
        assert len(symbols) == 6
        assert raw_coords.shape == (6, 3)
    
        # Dihedrals via graph-cleaving
        dihedrals = detect_5_option_dihedrals(symbols, raw_coords)
        assert isinstance(dihedrals, list)
        active_dihedral = dihedrals[0]["dihedral"] if dihedrals else (5, 1, 0, 2)
    
        # Eckart Frame Alignment
        aligned_coords = align_eckart_frame(raw_coords, symbols)
        assert aligned_coords.shape == (6, 3)
    
        # -------------------------------------------------------------
        # Phase 3: ML Pre-Flight & Triage [MACE-OFF23] (Stage 2.0 - 2.1)
        # -------------------------------------------------------------
        grid_angles = np.linspace(0, 360, 12, endpoint=False)
        energies = []
        for ang in grid_angles:
            rot_coords = rotate_dihedral_angle(aligned_coords, active_dihedral, float(ang))
            clashes = detect_covalent_clashes(symbols, rot_coords)
            if clashes:
                quench_res = execute_soft_quench(symbols, rot_coords)
                rot_coords = quench_res["relaxed_coordinates"]
            e = evaluate_pes_point(symbols, rot_coords)
            energies.append(e)
    
        energies_arr = np.array(energies)
        assert len(energies_arr) == 12
    
        # -------------------------------------------------------------
        # Phase 4: Multi-Fidelity Spline Routing & WKB (Stage 3.0 / 6.0)
        # -------------------------------------------------------------
        spline_model = fit_continuous_splines(grid_angles, energies_arr)
        assert spline_model is not None
    
        barrier_kcal = (np.max(energies_arr) - np.min(energies_arr)) * 627.509
        barrier_cm1 = barrier_kcal * 349.755
        wkb_res = wkb_tunneling_estimator(rotor_type="CH3", barrier_height_cm1=barrier_cm1, reduced_moment_inertia_amu_ang2=1.0)
        assert wkb_res["tunneling_splitting_mhz"] >= 0.0
    
        # -------------------------------------------------------------
        # Phase 5: Ab Initio Quantum Engine & Cascade Matrix (Stage 4.0)
        # -------------------------------------------------------------
>       routed_job = route_method_matrix(
            calculation_tier="conformer_refinement",
            functional="wB97X-D4",
            basis_set="def2-TZVP",
            num_atoms=len(symbols),
        )
E       TypeError: route_method_matrix() got an unexpected keyword argument 'calculation_tier'

test_suite\test_cochem_torq_master_context.py:253: TypeError
---------------------------- Captured stderr call -----------------------------
[2026-08-23 09:27:41 | CoChem-TORQ | INFO] Airgap verified: exec=C:\Users\ansac\AppData\Local\Temp\pytest-of-ansac\pytest-7874\test_full_10_phase_funnel_end_0\artifacts <-> artifact=C:\Users\ansac\AppData\Local\Temp\pytest-of-ansac\pytest-7874\test_full_10_phase_funnel_end_0\scratch
[2026-08-23 09:27:41 | CoChem-TORQ.Vault | INFO] Successfully parsed XYZ geometry (6 atoms, SHA256=56327002...)
[2026-08-23 09:27:41 | CoChem-TORQ.Topology | INFO] Detected 1 candidate dihedrals, returning top 1
[2026-08-23 09:27:41 | CoChem-TORQ.Alignment | INFO] Diagonalized inertia tensor: I_a=3.9548, I_b=20.4073, I_c=21.1452 (A=127787.50, B=24764.64, C=23900.41 MHz, kappa=-0.9834)
[2026-08-23 09:27:41 | CoChem-TORQ.Slicer | INFO] Spline fitted: 10 stationary points found (5 minima, 5 maxima, max barrier = 0.00 kcal/mol)
[2026-08-23 09:27:41 | CoChem-TORQ.Slicer | INFO] WKB tunneling estimate for CH3: barrier=0.0 cm^-1, P_tunnel=9.55e-01, Splitting=1.2596 MHz, QuantumRequired=True
------------------------------ Captured log call ------------------------------
INFO     CoChem-TORQ:cochem_torq_init.py:150 Airgap verified: exec=C:\Users\ansac\AppData\Local\Temp\pytest-of-ansac\pytest-7874\test_full_10_phase_funnel_end_0\artifacts <-> artifact=C:\Users\ansac\AppData\Local\Temp\pytest-of-ansac\pytest-7874\test_full_10_phase_funnel_end_0\scratch
INFO     CoChem-TORQ.Vault:cochem_torq_vault.py:273 Successfully parsed XYZ geometry (6 atoms, SHA256=56327002...)
INFO     CoChem-TORQ.Topology:cochem_torq_topology.py:183 Detected 1 candidate dihedrals, returning top 1
INFO     CoChem-TORQ.Alignment:cochem_torq_alignment.py:154 Diagonalized inertia tensor: I_a=3.9548, I_b=20.4073, I_c=21.1452 (A=127787.50, B=24764.64, C=23900.41 MHz, kappa=-0.9834)
INFO     CoChem-TORQ.Slicer:cochem_torq_slicer.py:148 Spline fitted: 10 stationary points found (5 minima, 5 maxima, max barrier = 0.00 kcal/mol)
INFO     CoChem-TORQ.Slicer:cochem_torq_slicer.py:214 WKB tunneling estimate for CH3: barrier=0.0 cm^-1, P_tunnel=9.55e-01, Splitting=1.2596 MHz, QuantumRequired=True
=========================== short test summary info ===========================
FAILED test_suite/test_cochem_torq_master_context.py::TestTorqMasterContextAnchor::test_full_10_phase_funnel_end_to_end
======================== 1 failed, 68 passed in 9.70s =========================

Error: 