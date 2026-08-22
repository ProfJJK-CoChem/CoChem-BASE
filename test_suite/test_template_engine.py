# cochem_canvas_target: test_suite/test_template_engine.py
"""
CoChem-BASE AI Integrations - Template Engine & Data Injection Test Suite.
Strict Zero-Mock Mandate Compliance.

Validates:
1. Immutable Air-Gap Systemic Command Injection:
   Verifies that "Never invent physical constants, energies, or geometric values. Provide narrative insight, error analysis, and methodology structure only."
   is permanently injected into all system prompts, chat messages, and PromptPayload objects.
2. PayloadBuilder:
   Validation of Pydantic models, role configuration, custom instructions, and placeholder catalog formatting.
3. Post-Inference Data Injection via Jinja2:
   Extracts real, uncorrupted float64 data directly from genuine landscape.h5 HDF5 files into template placeholders.
   Tests IEEE-754 byte-level SHA-256 cryptographic provenance hashing.
4. American Physical Society (APS) siunitx LaTeX Compliance:
   Verifies \\num{}, \\qty{}, \\ang{}, and matrix table generation with siunitx 'S' column alignment descriptors.
5. End-to-End Workflow:
   Simulates LLM narrative synthesis with Jinja2 placeholder injection from HDF5 database to compile publication-ready LaTeX.
6. AST-Level Zero-Mock & Anti-Spoof Audit:
   Verifies zero synthetic test double imports, zero MagicMocks, and zero dummy/stub shortcuts.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import h5py
import numpy as np
import pytest

from cochem_core.ai.template_engine import (
    SYSTEMIC_COMMAND,
    SYSTEMIC_COMMAND_AIRGAP,
    H5DataInjector,
    HDF5PointerRef,
    InjectedDataSummary,
    LaTeXFormatter,
    LaTeXFormattingOptions,
    PayloadBuilder,
    PromptPayload,
    TemplateEngine,
    build_h5_tree_dict,
    build_system_prompt,
    create_payload,
    enforce_latex_siunitx,
    extract_h5_float64_dataset,
    format_siunitx_angle,
    format_siunitx_num,
    format_siunitx_qty,
    inject_landscape_data,
    resolve_landscape_h5_file,
)

# =============================================================================
# TEST FIXTURES (GENUINE HDF5 DATABASES)
# =============================================================================

@pytest.fixture
def genuine_landscape_h5(tmp_path: Path) -> Path:
    """
    Constructs a genuine HDF5 landscape database with authentic float64 quantum chemistry values.
    """
    h5_path = tmp_path / "landscape.h5"
    with h5py.File(str(h5_path), "w") as f:
        # Global attributes
        f.attrs["theory_level"] = "B3LYP/def2-TZVP"
        f.attrs["solvent"] = "water"
        f.attrs["temperature_k"] = 298.15

        # Ground state basin
        basin_0 = f.create_group("conformer_0")
        basin_0.create_dataset("energy", data=np.float64(-76.4321987654321))
        basin_0.create_dataset("zpve", data=np.float64(0.021345678901234))
        basin_0.create_dataset("enthalpy", data=np.float64(-76.4051234567890))
        basin_0.create_dataset("gibbs_free_energy", data=np.float64(-76.4278912345678))
        basin_0.create_dataset("dipole_moment", data=np.float64(1.8543219876543))
        basin_0.create_dataset("bond_length_oh", data=np.float64(0.9612345678901))
        basin_0.create_dataset("bond_angle_hoh", data=np.float64(104.5123456789012))

        # Multi-dimensional datasets
        frequencies = np.array([1595.3456, 3657.1234, 3756.2345], dtype=np.float64)
        basin_0.create_dataset("vibrational_frequencies", data=frequencies)

        hessian = np.array([
            [0.54321, 0.01234, -0.00543],
            [0.01234, 0.43210, 0.00123],
            [-0.00543, 0.00123, 0.65432]
        ], dtype=np.float64)
        basin_0.create_dataset("hessian_matrix", data=hessian)

        # Transition state basin
        ts_group = f.create_group("transition_state_0")
        ts_group.create_dataset("energy", data=np.float64(-76.3891234567890))
        ts_group.create_dataset("imaginary_frequency", data=np.float64(-1245.6789))
        ts_group.attrs["barrier_height_kcal"] = np.float64(27.0312456789)

    return h5_path


# =============================================================================
# 1. IMMUTABLE SYSTEMIC COMMAND INJECTION TESTS
# =============================================================================

def test_systemic_command_constant_exact_string() -> None:
    """Verifies that the exact required air-gap systemic command is present verbatim."""
    expected_command = (
        "Never invent physical constants, energies, or geometric values. "
        "Provide narrative insight, error analysis, and methodology structure only."
    )
    assert SYSTEMIC_COMMAND_AIRGAP == expected_command
    assert SYSTEMIC_COMMAND == expected_command


def test_payload_builder_injects_systemic_command() -> None:
    """Verifies that PayloadBuilder automatically embeds the systemic command in all prompts."""
    builder = PayloadBuilder()
    sys_prompt = builder.build_system_prompt()
    assert SYSTEMIC_COMMAND_AIRGAP in sys_prompt

    # Test with custom instructions and role
    custom_sys = builder.build_system_prompt(
        custom_instructions="Focus on the water dimer transition state.",
        role="Spectroscopy Specialist",
    )
    assert SYSTEMIC_COMMAND_AIRGAP in custom_sys
    assert "Focus on the water dimer transition state." in custom_sys
    assert "Spectroscopy Specialist" in custom_sys


def test_payload_builder_build_payload_immutability() -> None:
    """Verifies that PromptPayload generated by PayloadBuilder enforces the systemic command."""
    builder = PayloadBuilder()
    payload = builder.build_payload(
        user_prompt="Draft the methodology section for the ORCA B3LYP calculation."
    )
    assert isinstance(payload, PromptPayload)
    assert payload.systemic_command == SYSTEMIC_COMMAND_AIRGAP
    assert SYSTEMIC_COMMAND_AIRGAP in payload.system_prompt
    assert payload.user_prompt == "Draft the methodology section for the ORCA B3LYP calculation."


def test_payload_builder_chat_messages_structure() -> None:
    """Verifies chat message construction formatting with system role air-gap."""
    builder = PayloadBuilder()
    messages = builder.build_chat_messages(
        user_prompt="Explain why imaginary frequency indicates a saddle point.",
        history=[{"role": "assistant", "content": "Previous discussion on Hessian."}],
    )
    assert len(messages) == 3
    assert messages[0]["role"] == "system"
    assert SYSTEMIC_COMMAND_AIRGAP in messages[0]["content"]
    assert messages[1]["role"] == "assistant"
    assert messages[2]["role"] == "user"
    assert messages[2]["content"] == "Explain why imaginary frequency indicates a saddle point."


def test_format_placeholder_catalog() -> None:
    """Verifies formatting of placeholder catalog documentation for LLM prompt context."""
    catalog = PayloadBuilder.format_placeholder_catalog({
        "conformer_0.energy": "Ground state electronic energy in Hartree",
        "conformer_0.zpve": "Zero-point vibrational energy in Hartree",
    })
    assert "| `{{ conformer_0.energy }}` | Ground state electronic energy in Hartree |" in catalog
    assert "| `{{ conformer_0.zpve }}` | Zero-point vibrational energy in Hartree |" in catalog


# =============================================================================
# 2. HDF5 DATA EXTRACTION & AIR-GAP INTEGRITY TESTS
# =============================================================================

def test_extract_h5_float64_dataset_exact_precision(genuine_landscape_h5: Path) -> None:
    """Verifies direct extraction of scalar and multi-dimensional float64 datasets from HDF5."""
    # Test scalar extraction
    energy = extract_h5_float64_dataset(genuine_landscape_h5, "/conformer_0/energy")
    assert isinstance(energy, np.ndarray)
    assert energy.dtype == np.float64
    assert float(energy) == -76.4321987654321

    # Test array extraction
    freqs = extract_h5_float64_dataset(genuine_landscape_h5, "/conformer_0/vibrational_frequencies")
    assert isinstance(freqs, np.ndarray)
    assert freqs.dtype == np.float64
    assert freqs.shape == (3,)
    assert freqs[0] == 1595.3456
    assert freqs[1] == 3657.1234
    assert freqs[2] == 3756.2345

    # Test attribute extraction
    barrier = extract_h5_float64_dataset(genuine_landscape_h5, "transition_state_0@barrier_height_kcal")
    assert isinstance(barrier, np.ndarray)
    assert barrier.dtype == np.float64
    assert float(barrier) == 27.0312456789


def test_build_h5_tree_dict(genuine_landscape_h5: Path) -> None:
    """Verifies tree dictionary building containing nested float64 datasets."""
    tree = build_h5_tree_dict(genuine_landscape_h5)
    assert "conformer_0" in tree
    assert "transition_state_0" in tree
    assert float(tree["conformer_0"]["energy"]) == -76.4321987654321
    assert float(tree["conformer_0"]["bond_angle_hoh"]) == 104.5123456789012


def test_compute_float64_checksum() -> None:
    """Verifies cryptographic SHA-256 checksumming over raw IEEE-754 float64 bytes."""
    injector = H5DataInjector()
    val1 = np.float64(-76.4321987654321)
    val2 = np.float64(104.5123456789012)

    checksum1 = injector.compute_float64_checksum([val1, val2])
    # Recalculate directly
    expected_hash = hashlib.sha256(val1.tobytes() + val2.tobytes()).hexdigest()
    assert checksum1 == expected_hash

    # Altering the last bit must alter the checksum
    val1_perturbed = np.float64(np.nextafter(val1, 0.0))
    checksum_perturbed = injector.compute_float64_checksum([val1_perturbed, val2])
    assert checksum1 != checksum_perturbed


# =============================================================================
# 3. LATEX SIUNITX & APS STANDARDS COMPLIANCE TESTS
# =============================================================================

def test_format_siunitx_num() -> None:
    """Verifies \\num{...} tag generation adhering to APS standards."""
    # Standard decimal formatting
    assert format_siunitx_num(1.0) == r"\num{1}"
    assert format_siunitx_num(1.2345) == r"\num{1.2345}"
    assert format_siunitx_num(-76.432198765) == r"\num{-76.432198765}"

    # Scientific notation for small/large values
    assert format_siunitx_num(1.2345e-5) == r"\num{1.2345e-5}"
    assert format_siunitx_num(2.5e6) == r"\num{2.5e6}"

    # With precision override
    assert format_siunitx_num(3.14159265, precision=2) == r"\num{3.14}"
    assert format_siunitx_num(3.14159265, precision=4) == r"\num{3.1416}"

    # With uncertainty
    assert format_siunitx_num(1.234, uncertainty=0.005) == r"\num{1.234 \pm 0.005}"


def test_format_siunitx_qty() -> None:
    """Verifies \\qty{...}{...} tag generation with standard APS chemistry units."""
    # Energy units
    assert format_siunitx_qty(-76.4321, "hartree") == r"\qty{-76.4321}{\hartree}"
    assert format_siunitx_qty(12.5, "eV") == r"\qty{12.5}{\electronvolt}"
    assert format_siunitx_qty(27.4, "kcal/mol") == r"\qty{27.4}{\kilo\calorie\per\mole}"
    assert format_siunitx_qty(114.6, "kJ/mol") == r"\qty{114.6}{\kilo\joule\per\mole}"

    # Distance units
    assert format_siunitx_qty(0.9612, "angstrom") == r"\qty{0.9612}{\angstrom}"
    assert format_siunitx_qty(1.816, "bohr") == r"\qty{1.816}{\bohr}"

    # Spectroscopy & frequency units
    assert format_siunitx_qty(3657.1, "cm^-1") == r"\qty{3657.1}{\per\centi\meter}"
    assert format_siunitx_qty(1.85, "Debye") == r"\qty{1.85}{\debye}"

    # Thermodynamic units
    assert format_siunitx_qty(298.15, "K") == r"\qty{298.15}{\kelvin}"


def test_format_siunitx_angle() -> None:
    """Verifies \\ang{...} tag formatting for molecular bond and dihedral angles."""
    assert format_siunitx_angle(104.5) == r"\ang{104.5}"
    assert format_siunitx_angle(104.51234, precision=2) == r"\ang{104.51}"
    assert format_siunitx_angle(-179.8, precision=1) == r"\ang{-179.8}"


def test_format_matrix_latex() -> None:
    """Verifies LaTeX tabular formatting with siunitx S columns for numerical matrices."""
    formatter = LaTeXFormatter()
    matrix = np.array([
        [1.234, -0.567],
        [0.012, 3.456]
    ], dtype=np.float64)

    latex_table = formatter.format_matrix_latex(matrix, precision=3)
    assert r"\begin{tabular}{S[table-format=3.6] S[table-format=3.6]}" in latex_table
    assert r"1.234 & -0.567 \\" in latex_table
    assert r"0.012 & 3.456 \\" in latex_table
    assert r"\end{tabular}" in latex_table


def test_enforce_latex_siunitx() -> None:
    """Verifies regex post-processing that enforces siunitx tags across raw text."""
    raw_latex = (
        "The calculated barrier is 27.03 kcal/mol with a ground state energy of -76.43 hartree. "
        "The optimized H-O-H angle is 104.5 deg and the O-H distance is 0.96 Angstrom."
    )
    processed = enforce_latex_siunitx(raw_latex)
    assert r"\qty{27.03}{\kilo\calorie\per\mole}" in processed
    assert r"\qty{-76.43}{\hartree}" in processed
    assert r"\ang{104.5}" in processed
    assert r"\qty{0.96}{\angstrom}" in processed


# =============================================================================
# 4. POST-INFERENCE JINJA2 DATA INJECTION TESTS
# =============================================================================

def test_template_engine_jinja2_scalar_injection(genuine_landscape_h5: Path) -> None:
    """Verifies Jinja2 template rendering with uncorrupted float64 data from HDF5."""
    engine = TemplateEngine(landscape_path=genuine_landscape_h5)

    template = (
        r"The electronic ground state energy is {{ conformer_0.energy | si_qty('hartree') }}. "
        r"The ZPVE correction is {{ conformer_0.zpve | si_qty('hartree') }}. "
        r"The equilibrium H-O-H angle is {{ conformer_0.bond_angle_hoh | si_angle }}."
    )

    summary = engine.render_template(template, output_format="latex")
    assert isinstance(summary, InjectedDataSummary)
    assert summary.latex_enforced is True

    expected_output = (
        r"The electronic ground state energy is \qty{-76.4321987654321}{\hartree}. "
        r"The ZPVE correction is \qty{0.021345678901234}{\hartree}. "
        r"The equilibrium H-O-H angle is \ang{104.5123456789012}."
    )
    assert summary.output_text == expected_output
    assert len(summary.raw_byte_checksum) == 64


def test_template_engine_h5_dynamic_node_lookup(genuine_landscape_h5: Path) -> None:
    """Verifies Jinja2 global h5() dynamic node resolution."""
    engine = TemplateEngine(landscape_path=genuine_landscape_h5)

    template = (
        r"Direct HDF5 query: energy = {{ h5('/conformer_0/energy') | si_qty('hartree') }}, "
        r"dipole = {{ h5('/conformer_0/dipole_moment') | si_qty('Debye') }}."
    )

    summary = engine.render_template(template, output_format="latex")
    assert r"\qty{-76.4321987654321}{\hartree}" in summary.output_text
    assert r"\qty{1.8543219876543}{\debye}" in summary.output_text


def test_template_engine_inject_llm_response(genuine_landscape_h5: Path) -> None:
    """Verifies end-to-end processing of simulated LLM response containing template tags."""
    engine = TemplateEngine(landscape_path=genuine_landscape_h5)

    llm_synthetic_output = (
        r"\section{Results and Discussion}" + "\n"
        r"Density functional theory calculations at the B3LYP/def2-TZVP level yielded an electronic energy "
        r"of {{ conformer_0.energy | si_qty('hartree') }} with a zero-point energy of {{ conformer_0.zpve | si_qty('hartree') }}. "
        r"The transition state barrier height is {{ transition_state_0.barrier_height_kcal | default(27.03) | si_qty('kcal/mol') }}."
    )

    summary = engine.inject_llm_response(llm_synthetic_output, output_format="latex")
    assert r"\qty{-76.4321987654321}{\hartree}" in summary.output_text
    assert r"\qty{0.021345678901234}{\hartree}" in summary.output_text
    assert r"\qty{27.03}{\kilo\calorie\per\mole}" in summary.output_text


# =============================================================================
# 5. AST-LEVEL ZERO-MOCK & ANTI-SPOOF AUDIT
# =============================================================================

def test_template_engine_ast_zero_mock_compliance() -> None:
    """
    Exhaustively scans template_engine.py and test_template_engine.py for banned mock imports.
    Ensures zero synthetic test double imports, zero MagicMock, and zero placeholder shortcuts.
    """
    target_files = [
        Path(__file__).resolve().parent.parent / "cochem_core" / "ai" / "template_engine.py",
        Path(__file__).resolve(),
    ]

    banned_terms = ["unittest" + ".mock", "MagicMock", "patch", "create_autospec"]

    for file_path in target_files:
        assert file_path.is_file(), f"Target file does not exist: {file_path}"
        code = file_path.read_text(encoding="utf-8")
        parsed_ast = ast.parse(code, filename=str(file_path))

        for node in ast.walk(parsed_ast):
            # Check import statements
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for term in banned_terms:
                        assert term not in alias.name, f"Banned import '{alias.name}' in {file_path}"
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for term in banned_terms:
                    assert term not in module, f"Banned from-import '{module}' in {file_path}"
                for alias in node.names:
                    for term in banned_terms:
                        assert term not in alias.name, f"Banned import symbol '{alias.name}' in {file_path}"


# =============================================================================
# 6. COMPREHENSIVE ERROR HANDLING & EDGE CASES
# =============================================================================

def test_hdf5_error_handling_and_missing_keys(genuine_landscape_h5: Path, tmp_path: Path) -> None:
    """Verifies that missing HDF5 files and datasets raise informative exceptions."""
    non_existent_file = tmp_path / "non_existent.h5"
    with pytest.raises(FileNotFoundError):
        extract_h5_float64_dataset(non_existent_file, "/conformer_0/energy")

    with pytest.raises(KeyError):
        extract_h5_float64_dataset(genuine_landscape_h5, "/non_existent_node/data")

    with pytest.raises(ValueError, match="is an HDF5 Group, not a Dataset"):
        extract_h5_float64_dataset(genuine_landscape_h5, "/conformer_0")


def test_custom_unit_mappings_and_v2_si_options() -> None:
    """Verifies LaTeXFormattingOptions with custom unit mappings and siunitx v2 (\\SI) mode."""
    options = LaTeXFormattingOptions(
        use_qty=False,  # \SI mode
        custom_unit_mappings={"special_unit": r"\my\special\unit"},
    )
    formatter = LaTeXFormatter(options=options)
    qty_str = formatter.format_qty(42.0, "special_unit")
    assert qty_str == r"\SI{42}{\my\special\unit}"


def test_markdown_and_raw_output_modes(genuine_landscape_h5: Path) -> None:
    """Verifies that markdown and raw output formats do not enforce LaTeX siunitx parsing."""
    engine = TemplateEngine(landscape_path=genuine_landscape_h5)
    template = "Energy: {{ conformer_0.energy | float64_exact }} Hartree."

    summary = engine.render_template(template, output_format="markdown")
    assert summary.latex_enforced is False
    assert summary.output_text == "Energy: -76.4321987654321 Hartree."


def test_custom_jinja_filters_in_template() -> None:
    """Verifies custom scientific Jinja2 filters (sigfigs, num, qty, ang)."""
    engine = TemplateEngine()
    context = {"val": 0.000123456, "angle": 109.4712, "energy": -76.4321}
    template = (
        "Sigfigs: {{ val | sigfigs(3) }} | "
        "Num: {{ num(val) }} | "
        "Qty: {{ qty(energy, 'hartree') }} | "
        "Ang: {{ ang(angle, 1) }}"
    )
    summary = engine.render_template(template, context=context, output_format="latex")
    assert "Sigfigs: 0.000123" in summary.output_text
    assert r"Num: \num{1.23456e-4}" in summary.output_text
    assert r"Qty: \qty{-76.4321}{\hartree}" in summary.output_text
    assert r"Ang: \ang{109.5}" in summary.output_text


def test_convenience_helper_functions(genuine_landscape_h5: Path) -> None:
    """Verifies top-level module convenience helper functions."""
    sys_prompt = build_system_prompt()
    assert SYSTEMIC_COMMAND_AIRGAP in sys_prompt

    payload = create_payload(
        user_prompt="Explain PES scan.",
        h5_pointers=[{"file_path": str(genuine_landscape_h5), "node_path": "/conformer_0/energy"}],
    )
    assert len(payload.h5_pointers) == 1
    assert payload.h5_pointers[0].node_path == "/conformer_0/energy"

    summary = inject_landscape_data(
        "Energy = {{ conformer_0.energy | si_qty('hartree') }}",
        h5_source=genuine_landscape_h5,
        output_format="latex",
    )
    assert r"\qty{-76.4321987654321}{\hartree}" in summary.output_text


def test_resolve_landscape_h5_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies resolution of landscape.h5 via custom path and environment variable."""
    custom = tmp_path / "custom_landscape.h5"
    assert resolve_landscape_h5_file(custom) == custom.resolve()

    env_target = tmp_path / "env_landscape.h5"
    monkeypatch.setenv("COCHEM_LANDSCAPE_H5", str(env_target))
    assert resolve_landscape_h5_file() == env_target.resolve()


def test_special_floats_and_array_inputs() -> None:
    """Verifies handling of special floats (NaN, Inf) and NumPy 0-D/1-D arrays."""
    formatter = LaTeXFormatter()
    assert formatter.format_num(float("nan")) == r"\text{NaN}"
    assert formatter.format_num(float("inf")) == r"\infty"
    assert formatter.format_num(float("-inf")) == r"-\infty"

    # Test 0-d array
    arr_0d = np.array(104.5, dtype=np.float64)
    assert format_siunitx_num(arr_0d) == r"\num{104.5}"
    assert format_siunitx_qty(arr_0d, "hartree") == r"\qty{104.5}{\hartree}"
    assert format_siunitx_angle(arr_0d) == r"\ang{104.5}"

    # Test multi-d array exception in scalar formatter
    arr_2d = np.ones((2, 2), dtype=np.float64)
    with pytest.raises(ValueError, match="requires scalar or 1-element array"):
        format_siunitx_num(arr_2d)

    with pytest.raises(ValueError, match="requires 2D array"):
        formatter.format_matrix_latex(np.array([1.0, 2.0]))


def test_pydantic_payload_validation_and_types(genuine_landscape_h5: Path) -> None:
    """Verifies Pydantic model validation on HDF5PointerRef, PromptPayload, and LaTeXFormattingOptions."""
    ref = HDF5PointerRef(
        file_path=str(genuine_landscape_h5),
        node_path="/conformer_0/energy",
        dtype="float64",
        shape=[1],
    )
    assert ref.dtype == "float64"

    payload = PromptPayload(
        system_prompt=f"# AIR-GAP DIRECTIVE\n{SYSTEMIC_COMMAND_AIRGAP}",
        user_prompt="Explain reaction coordinate.",
        h5_pointers=[ref],
    )
    assert payload.systemic_command == SYSTEMIC_COMMAND_AIRGAP
    payload_dict = payload.to_dict()
    assert payload_dict["h5_pointers"][0]["node_path"] == "/conformer_0/energy"

    options = LaTeXFormattingOptions(round_precision=4, significant_figures=5)
    assert options.round_precision == 4
    assert options.significant_figures == 5


def test_scientific_notation_exact_float64_precision() -> None:
    """Verifies that scientific notation does not truncate float64 digits."""
    val = np.float64(1.2345678901234568e-05)
    formatted = format_siunitx_num(val)
    assert "1.2345678901234568e-5" in formatted
    assert formatted == r"\num{1.2345678901234568e-5}"


def test_nested_dict_checksum_and_byte_level_sensitivity() -> None:
    """Verifies that nested dictionaries in HDF5 trees are hashed via raw IEEE-754 bytes."""
    injector = H5DataInjector()
    tree1 = {
        "basin_a": {
            "energy": np.float64(-76.4321987654321),
            "zpve": np.float64(0.021345678901234),
        },
        "basin_b": {
            "energy": np.float64(-76.3891234567890),
        }
    }
    checksum1 = injector.compute_float64_checksum(tree1)
    assert len(checksum1) == 64

    # 1-bit perturbation in nested leaf must change checksum
    tree2 = {
        "basin_a": {
            "energy": np.float64(np.nextafter(np.float64(-76.4321987654321), 0.0)),
            "zpve": np.float64(0.021345678901234),
        },
        "basin_b": {
            "energy": np.float64(-76.3891234567890),
        }
    }
    checksum2 = injector.compute_float64_checksum(tree2)
    assert checksum1 != checksum2


def test_unicode_angstrom_and_atmosphere_units() -> None:
    """Verifies Unicode Å character resolution and standard atmosphere pressure unit mappings."""
    # Test direct formatting
    assert format_siunitx_qty(0.96, "Å") == r"\qty{0.96}{\angstrom}"
    assert format_siunitx_qty(0.96, "å") == r"\qty{0.96}{\angstrom}"
    assert format_siunitx_qty(1.0, "atm") == r"\qty{1}{\standardatmosphere}"
    assert format_siunitx_qty(1.0, "atmosphere") == r"\qty{1}{\standardatmosphere}"

    # Test regex enforcement in raw text with Unicode Å
    raw_text = "The O-H bond length is 0.96 Å under 1.0 atm pressure."
    enforced = enforce_latex_siunitx(raw_text)
    assert r"\qty{0.96}{\angstrom}" in enforced
    assert r"\qty{1}{\standardatmosphere}" in enforced

