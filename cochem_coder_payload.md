Cycle 2: Implement code for prompt at D:\__CoChem\__agentic\.prompts\.SRS\20260903-061002-brainstorm\.in-progress\Perfected_SRS_Chunk_01_Core_Part_1_prompts.md strictly adhering to Zero-Mock mandate. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE. Generate unit tests first. IMPORTANT: You MUST update/create `pytest.ini` to restrict `testpaths` to ONLY the tests you are writing for this prompt, otherwise the global 1500+ test suite will run and crash your context. 
Test Failures from previous run:
Output: ============================= test session starts =============================
platform win32 -- Python 3.13.9, pytest-8.4.2, pluggy-1.5.0 -- C:\Users\ansac\anaconda3\python.exe
cachedir: .pytest_cache
rootdir: D:\__CoChem\GitHub-Repo\CoChem-BASE
configfile: pytest.ini
plugins: anyio-4.10.0, hydra-core-1.3.5, typeguard-4.6.0, zarr-3.3.0
collecting ... collected 19 items

test_suite/test_cochem_core_auto_pes.py::test_mendeleev_dynamic_mass_and_atomic_numbers PASSED [  5%]
test_suite/test_cochem_core_auto_pes.py::test_geometry_featurizer_morse_and_jacobian FAILED [ 10%]
test_suite/test_cochem_core_auto_pes.py::test_committee_uncertainty_and_g5_gate PASSED [ 15%]
test_suite/test_cochem_core_auto_pes.py::test_active_learning_selection_execution PASSED [ 21%]
test_suite/test_cochem_core_auto_pes.py::test_delta_pes_fitting_and_spectroscopic_validation PASSED [ 26%]
test_suite/test_cochem_core_auto_pes.py::test_autopes_pesstore_integration PASSED [ 31%]
tests/core/test_cfour_vpt2_and_projection.py::test_diagonalize_projected_hessian_mode_count_and_soft_modes FAILED [ 36%]
tests/core/test_cfour_vpt2_and_projection.py::test_isomass_vpt2_non_linear_alpha_scaling PASSED [ 42%]
tests/core/test_constants_provenance.py::test_fundamental_constants_provenance PASSED [ 47%]
tests/core/test_constants_provenance.py::test_derived_rotational_constant_provenance PASSED [ 52%]
tests/core/test_dvr_nan_handling.py::test_dvr_nan_watchdog_1d_interior_resolved PASSED [ 57%]
tests/core/test_dvr_nan_handling.py::test_dvr_nan_watchdog_1d_boundary_raises PASSED [ 63%]
tests/core/test_dvr_nan_handling.py::test_dvr_nan_watchdog_2d_interior_resolved PASSED [ 68%]
tests/core/test_dvr_nan_handling.py::test_dvr_nan_watchdog_2d_boundary_raises PASSED [ 73%]
tests/core/test_frozen_monomer_forces.py::test_frozen_monomer_rigid_body_force_decoupling_and_strain PASSED [ 78%]
tests/core/test_pes_pip_and_asymptote.py::test_pes_pip_feature_and_energy_invariance PASSED [ 84%]
tests/core/test_pes_pip_and_asymptote.py::test_pes_asymptotic_dissociation_baseline PASSED [ 89%]
tests/core/test_rotational_constants_unification.py::test_rotational_constants_unification_water_monomer PASSED [ 94%]
tests/core/test_rotational_constants_unification.py::test_rotational_constants_unification_water_dimer PASSED [100%]

================================== FAILURES ===================================
_________________ test_geometry_featurizer_morse_and_jacobian _________________

    def test_geometry_featurizer_morse_and_jacobian() -> None:
        """Validates Morse coordinates and analytical Jacobian derivatives."""
        symbols = ["Ar", "H", "Cl"]
        feat = GeometryFeaturizer(symbols=symbols, morse_lambda=2.0)
    
        assert feat.n_atoms == 3
        assert feat.n_pairs == 3  # (0,1), (0,2), (1,2)
    
        # Test geometry configuration
        geom = np.array([
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 3.8],
            [1.0, 0.0, 3.8],
        ], dtype=np.float64)
    
        morse_feats = feat.compute_morse_features(geom)
>       assert morse_feats.shape == (3,)
E       AssertionError: assert (9,) == (3,)
E         
E         At index 0 diff: 9 != 3
E         
E         Full diff:
E           (
E         -     3,
E         ?     ^...
E         
E         ...Full output truncated (3 lines hidden), use '-vv' to show

test_suite\test_cochem_core_auto_pes.py:81: AssertionError
________ test_diagonalize_projected_hessian_mode_count_and_soft_modes _________

    def test_diagonalize_projected_hessian_mode_count_and_soft_modes() -> None:
        """Verify that a 6-atom molecular Hessian generates exactly 3N-6 = 12 physical modes with 0 negative modes.
    
        Tests that soft intermolecular modes down to < 10 cm^-1 are authentically preserved
        without scalar cutoff drops.
        """
        symbols = ["O", "H", "H", "O", "H", "H"]
        n_atoms = len(symbols)
        assert n_atoms == 6
    
        # Physical water dimer benchmark geometry
        coordinates = np.array([
            [-1.455, 0.0, -0.076],
            [-1.838, -0.781, 0.325],
            [-0.518, 0.0, 0.147],
            [1.455, 0.0, 0.076],
            [1.772, 0.758, -0.412],
            [1.772, -0.758, -0.412],
        ], dtype=np.float64)
    
        masses = [float(element(sym).mass) for sym in symbols]
    
        # Construct physical Cartesian force constant matrix (intramolecular + weak intermolecular)
        # in Hartree / bohr^2
        hessian = np.full((3 * n_atoms, 3 * n_atoms), 0.0, dtype=np.float64)
        interactions = [
            (0, 1, 0.52),    # O1-H1 covalent bond
            (0, 2, 0.52),    # O1-H2 covalent bond
            (3, 4, 0.52),    # O2-H3 covalent bond
            (3, 5, 0.52),    # O2-H4 covalent bond
            (1, 2, 0.08),    # H1-O1-H2 valence angle
            (4, 5, 0.08),    # H3-O2-H4 valence angle
            (2, 3, 0.002),   # H2...O2 hydrogen bond
            (0, 3, 0.0006),  # O1...O2 dipole coupling
            (1, 3, 0.0003),  # Intermolecular angle stabilization
            (2, 4, 0.0003),
            (2, 5, 0.0003),
        ]
    
        for i, j, k_const in interactions:
            rij = coordinates[j] - coordinates[i]
            dist = float(np.linalg.norm(rij))
            u_vec = rij / dist
            k_tensor = np.outer(u_vec, u_vec) * k_const
            hessian[3 * i : 3 * i + 3, 3 * i : 3 * i + 3] += k_tensor
            hessian[3 * j : 3 * j + 3, 3 * j : 3 * j + 3] += k_tensor
            hessian[3 * i : 3 * i + 3, 3 * j : 3 * j + 3] -= k_tensor
            hessian[3 * j : 3 * j + 3, 3 * i : 3 * i + 3] -= k_tensor
    
        frequencies, zpe = _diagonalize_projected_hessian(
            hessian=hessian,
            symbols=symbols,
            coordinates=coordinates,
            masses=masses,
        )
    
        # 1. Verify mode count: exactly 3N - 6 = 12 modes
        expected_modes = 3 * n_atoms - 6
        assert len(frequencies) == expected_modes, f"Expected {expected_modes} modes, got {len(frequencies)}"
    
        # 2. Verify zero negative (imaginary) modes on minimum
        for f in frequencies:
>           assert f >= 0.0, f"Found negative mode {f} cm^-1 on stable minimum"
E           AssertionError: Found negative mode -2.7385596386631556e-05 cm^-1 on stable minimum
E           assert -2.7385596386631556e-05 >= 0.0

tests\core\test_cfour_vpt2_and_projection.py:81: AssertionError
=========================== short test summary info ===========================
FAILED test_suite/test_cochem_core_auto_pes.py::test_geometry_featurizer_morse_and_jacobian
FAILED tests/core/test_cfour_vpt2_and_projection.py::test_diagonalize_projected_hessian_mode_count_and_soft_modes
======================== 2 failed, 17 passed in 22.76s ========================

Error: 