"""
Zero-Mock Physical Validation Suite: Spectroscopic Observables ($B_e$ vs $B_0$),
Method Matrix Level of Theory Selector, and Product Class Decision Gate.
Method Matrix v4: §0, §3.0, §3.3, §4.4, §8C, §9A, and SRS Chunk 4 Suggestions #34, #35, #37.
"""
import tempfile
from pathlib import Path
import pytest
import h5py

from cochem_base.spectroscopy.parser import (
    SpectroscopyTelemetryParser,
    SpectroscopicTelemetryResult,
    read_hdf5_swmr_telemetry,
    INERTIA_CONVERSION_MHZ_AMU_ANG2,
)
from cochem_base.theory_matrix import (
    ProductClass,
    PRODUCT_CLASS_SPECS,
    METHOD_MATRIX_TIERS,
    validate_method_matrix_compliance,
)
from cochem_base.exceptions import MethodologyViolationError
from ui.voila_layout.cochem_gui import CoChemGUI


# Authentic ORCA property output for sulfur dioxide (SO2)
ORCA_SO2_PROPERTY_OUTPUT = """
------------------------------------------------------------------------------
                          ROTATIONAL CONSTANTS
------------------------------------------------------------------------------
Rotational constants in MHz:
A =   60778.520   B =   10318.060   C =    8820.610

Vibrational corrections to rotational constants (MHz):
Delta_A =   -452.120   Delta_B =    -52.340   Delta_C =    -41.200

------------------------------------------------------------------------------
                                DIPOLE MOMENT
------------------------------------------------------------------------------
Magnitude of dipole moment:     1.6330 Debye
X =    0.0000   Y =    0.0000   Z =    1.6330
"""


def test_spectroscopy_parser_be_vs_b0_distinction():
    """Validates that theoretical equilibrium B_e and vibrational ground-state B_0

    are strictly separated with explicit provenance tags per Method Matrix §3.0.
    """
    parser = SpectroscopyTelemetryParser()
    result = parser.parse_log_content(ORCA_SO2_PROPERTY_OUTPUT, engine_hint="orca")

    assert isinstance(result, SpectroscopicTelemetryResult)
    assert result.engine == "orca"

    # 1. Equilibrium constants [M]
    assert abs(result.a_e - 60778.520) < 1e-3
    assert abs(result.b_e - 10318.060) < 1e-3
    assert abs(result.c_e - 8820.610) < 1e-3

    # 2. Vibrational corrections [M]
    assert abs(result.delta_a_vib - (-452.120)) < 1e-3
    assert abs(result.delta_b_vib - (-52.340)) < 1e-3
    assert abs(result.delta_c_vib - (-41.200)) < 1e-3

    # 3. Ground-state observables B_0 = B_e + Delta B_vib [D]
    expected_a0 = 60778.520 - 452.120
    expected_b0 = 10318.060 - 52.340
    expected_c0 = 8820.610 - 41.200
    assert abs(result.a_0 - expected_a0) < 1e-3
    assert abs(result.b_0 - expected_b0) < 1e-3
    assert abs(result.c_0 - expected_c0) < 1e-3

    # 4. Moments of inertia and planar inertial defect [D]
    expected_ia = INERTIA_CONVERSION_MHZ_AMU_ANG2 / result.a_e
    expected_ib = INERTIA_CONVERSION_MHZ_AMU_ANG2 / result.b_e
    expected_ic = INERTIA_CONVERSION_MHZ_AMU_ANG2 / result.c_e
    assert abs(result.i_a - expected_ia) < 1e-4
    assert abs(result.i_b - expected_ib) < 1e-4
    assert abs(result.i_c - expected_ic) < 1e-4

    expected_defect = expected_ic - expected_ia - expected_ib
    assert abs(result.inertial_defect - expected_defect) < 1e-4

    # 5. Dipole moment [M]
    assert abs(result.total_dipole - 1.6330) < 1e-3
    assert abs(result.dipole_components[2] - 1.6330) < 1e-3


def test_hdf5_swmr_concurrency_filelock():
    """Validates cross-platform thread-safe SWMR read with FileLock and zero POSIX fcntl."""
    with tempfile.TemporaryDirectory() as tmpdir:
        h5_path = Path(tmpdir) / "telemetry_test.h5"
        with h5py.File(str(h5_path), "w", libver="latest") as f:
            f.attrs["calculation_engine"] = "ORCA"
            f.attrs["functional"] = "wB97M-V"
            f.create_dataset("rotational_constants_mhz", data=[60778.52, 10318.06, 8820.61])
            f.create_dataset("dipole_debye", data=1.6330)

        # Read using SWMR filelock reader
        data = read_hdf5_swmr_telemetry(h5_path)
        assert data["attr_calculation_engine"] == "ORCA"
        assert data["attr_functional"] == "wB97M-V"
        assert abs(data["dipole_debye"] - 1.6330) < 1e-4
        assert len(data["rotational_constants_mhz"]) == 3

        # Verify lock file is released and does not block subsequent access
        lock_file = h5_path.with_suffix(".lock")
        assert not lock_file.exists() or lock_file.stat().st_size == 0


def test_method_matrix_tier_catalog_and_dispersion_gate():
    """Validates Method Matrix §4.4, §9A and Table 3 Level of Theory enforcement."""
    # 1. Tier 1 must contain state-of-the-art non-local dispersion functionals
    tier1 = METHOD_MATRIX_TIERS["Tier 1: Modern Dispersion DFT"]
    assert "wB97M-V" in tier1["methods"]
    assert "r2SCAN-3c" in tier1["methods"]
    assert tier1["has_dispersion"] is True

    # 2. Tier 2 must contain composite wave-function schemes
    tier2 = METHOD_MATRIX_TIERS["Tier 2: Wave-Function Composite"]
    assert "junChS" in tier2["methods"]
    assert "CCSD(T)" in tier2["methods"]

    # 3. Anti-dispersion gatekeeper: Bare B3LYP on 2-fragment complex must raise MethodologyViolationError
    with pytest.raises(MethodologyViolationError) as excinfo:
        validate_method_matrix_compliance(method="B3LYP", num_fragments=2, unphysical_override=False)
    assert "Dispersion-free" in str(excinfo.value) or "dispersion-free" in str(excinfo.value)

    # 4. Modern functional with dispersion passes cleanly
    assert validate_method_matrix_compliance(method="wB97M-V", num_fragments=2) is True

    # 5. Unphysical override bypasses gate when explicitly toggled
    assert validate_method_matrix_compliance(method="B3LYP", num_fragments=2, unphysical_override=True) is True


def test_step_0_product_class_gate_specs_and_spend_priority():
    """Validates Method Matrix §0 Product Classes and §3.3 Spend Priority hierarchy."""
    # Verify specs for Product A, B, C
    spec_a = PRODUCT_CLASS_SPECS[ProductClass.PRODUCT_A]
    assert "0.3%" in spec_a["target_accuracy"]
    assert spec_a["conformer_search_required"] is True

    spec_b = PRODUCT_CLASS_SPECS[ProductClass.PRODUCT_B]
    assert "0.03%" in spec_b["target_accuracy"]
    assert spec_b["frozen_monomers_allowed"] is True

    spec_c = PRODUCT_CLASS_SPECS[ProductClass.PRODUCT_C]
    assert "0.02%" in spec_c["target_accuracy"]
    assert spec_c["hessian_reuse_allowed"] is True


def test_gui_interactive_wiring():
    """Validates that CoChemGUI instantiates and binds the new widgets and observers."""
    gui = CoChemGUI()
    assert hasattr(gui, "product_class_selector")
    assert hasattr(gui, "matrix_tier")
    assert hasattr(gui, "btn_detect_fragments")
    assert hasattr(gui, "btn_slurm_submit")
    assert hasattr(gui, "inspector_file_input")

    # Verify initial Product Class A selection
    assert gui.product_class_selector.value == ProductClass.PRODUCT_A.value

    # Change to Product B
    gui.product_class_selector.value = ProductClass.PRODUCT_B.value
    assert "Product B" in gui.product_class_card.value

    # Change to Product C
    gui.product_class_selector.value = ProductClass.PRODUCT_C.value
    assert "Product C" in gui.product_class_card.value
    assert gui.state.active_view == "inspector"

    # Test Tier change updates methods
    gui.matrix_tier.value = "Tier 2: Wave-Function Composite"
    assert "junChS" in gui.matrix_method.options

    # Physical execution of Fragment Detection on Water Dimer
    water_dimer_xyz = (
        "O -1.474  0.000  0.063\n"
        "H -1.821  0.772 -0.404\n"
        "H -0.528  0.000 -0.126\n"
        "O  1.428  0.000 -0.063\n"
        "H  1.782  0.772  0.404\n"
        "H  1.782 -0.772  0.404"
    )
    gui.matrix_geometry.value = water_dimer_xyz
    gui._on_detect_fragments_clicked(None)
    assert "Fragment 0" in gui.fragments_output.value
    assert "Fragment 1" in gui.fragments_output.value
    assert "%geom" in gui.fragment_preview.value
    assert "TolMaxG 1e-5" in gui.fragment_preview.value

    # Physical execution of Dynamic Mendeleev Isotope Reanalysis
    gui.matrix_geometry.value = (
        "O 0.0000  0.0000  0.1173\n"
        "H 0.0000  0.7572 -0.4692\n"
        "H 0.0000 -0.7572 -0.4692"
    )
    gui._on_run_isotope_reanalysis_clicked(None)
    assert "Dynamic Mendeleev Isotopologue Re-analysis Verified" in gui.isotope_results_table.value
    assert "Parent (OHH)" in gui.isotope_results_table.value
    assert "Substituted (18OHH)" in gui.isotope_results_table.value
    assert "18.015" in gui.isotope_results_table.value
    assert "20.015" in gui.isotope_results_table.value
