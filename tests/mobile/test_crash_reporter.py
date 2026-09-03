"""Physical Unit Verification Suite for Chemical Crash Reporter & Traceback Translator.

Module: tests.mobile.test_crash_reporter
Authoritative Reference: SRS Chunk 02 BASE UI & Web (Part 2), Prompt 3.

Invariants:
- Zero-Mock Protocol: Authentic exception instances, genuine regex pattern parsing.
- Path sanitization verification stripping user directory paths while preserving frames.
- Pedagogical remediation matching for SCF convergence, singular overlap, and gradient explosion.
"""

from __future__ import annotations

import sys
from typing import List

from src.cochem.mobile.crash_reporter import (
    ChemicalCrashTranslator,
    ChemicalDiagnosticReport,
    ChemicalFaultCategory,
    GeometryGradientCrash,
    SCFConvergenceError,
    SingularBasisError,
    WavefunctionInstabilityError,
    sanitize_traceback_text,
)


class TestChemicalCrashReporter:
    """Test suite validating chemical crash diagnosis and pedagogical remediation mapping."""

    def test_translate_scf_convergence_error(self) -> None:
        """Verify pedagogical translation of SCFConvergenceError."""
        translator = ChemicalCrashTranslator()
        exc = SCFConvergenceError(
            "Max iterations (100) reached without achieving energy threshold 1e-6 au",
            engine="ORCA",
            cycles_completed=100,
            energy_delta=0.0034,
        )

        report = translator.translate_exception(exc)
        assert isinstance(report, ChemicalDiagnosticReport)
        assert report.category == ChemicalFaultCategory.SCF_CONVERGENCE
        assert report.engine == "ORCA"
        assert "Electronic SCF Iterations Did Not Converge" in report.headline
        assert any("UHF" in item or "Unrestricted" in item for item in report.actionable_remediation)
        assert report.input_adjustment_suggestions.get("level_shift_au") == 0.25

    def test_translate_singular_basis_error(self) -> None:
        """Verify translation of SingularBasisError with smallest eigenvalue logging."""
        translator = ChemicalCrashTranslator()
        exc = SingularBasisError(
            "Linear dependence in basis set aug-cc-pVTZ",
            engine="PySCF",
            smallest_eigenvalue=3.4e-9,
        )

        report = translator.translate_exception(exc)
        assert report.category == ChemicalFaultCategory.SINGULAR_BASIS
        assert report.engine == "PySCF"
        assert "Linear Dependency" in report.headline
        assert any("diffuse" in item.lower() for item in report.actionable_remediation)
        assert report.input_adjustment_suggestions.get("drop_diffuse_hydrogens") is True

    def test_translate_geometry_gradient_crash(self) -> None:
        """Verify translation of geometry optimization gradient explosion."""
        translator = ChemicalCrashTranslator()
        exc = GeometryGradientCrash(
            "Nuclear gradient exceeded 2.5 au in Cartesian coordinate step",
            engine="ORCA",
            max_gradient_au=4.82,
        )

        report = translator.translate_exception(exc)
        assert report.category == ChemicalFaultCategory.GRADIENT_EXPLOSION
        assert report.engine == "ORCA"
        assert "Nuclear Force Explosion" in report.headline
        assert any("xTB" in item for item in report.actionable_remediation)
        assert report.input_adjustment_suggestions.get("pre_opt_engine") == "GFN2-xTB"

    def test_translate_wavefunction_instability(self) -> None:
        """Verify translation of wavefunction instability error."""
        translator = ChemicalCrashTranslator()
        exc = WavefunctionInstabilityError(
            "Electronic Hessian has 1 negative eigenvalue",
            engine="PySCF",
        )

        report = translator.translate_exception(exc)
        assert report.category == ChemicalFaultCategory.WAVEFUNCTION_INSTABILITY
        assert "Instability" in report.headline
        assert report.input_adjustment_suggestions.get("broken_symmetry") is True

    def test_sanitize_traceback_paths(self) -> None:
        """Verify stripping of workstation usernames and ephemeral execution directories."""
        raw_windows_path = r'File "C:\Users\johndoe\projects\cochem\engine\scf.py", line 42, in solve_scf'
        raw_linux_path = 'File "/home/researcher/code/cochem/solver.py", line 105, in run_opt'
        raw_scratch_path = 'Temporary scratch at "/tmp/cochem_exec_12345678-abcd-ef01-2345-6789abcdef01/run.out"'

        sanitized_win = sanitize_traceback_text(raw_windows_path)
        assert "johndoe" not in sanitized_win
        assert "<USER_HOME>" in sanitized_win
        assert "line 42" in sanitized_win

        sanitized_lin = sanitize_traceback_text(raw_linux_path)
        assert "researcher" not in sanitized_lin
        assert "<USER_HOME>" in sanitized_lin
        assert "line 105" in sanitized_lin

        sanitized_scratch = sanitize_traceback_text(raw_scratch_path)
        assert "12345678-abcd" not in sanitized_scratch
        assert "<SCRATCH>" in sanitized_scratch

    def test_translate_raw_log_output(self) -> None:
        """Verify regex signature matching on raw terminal / engine log dumps."""
        translator = ChemicalCrashTranslator()
        orca_log_snippet = (
            "--------------------\n"
            "SCF CONVERGENCE TEST\n"
            "--------------------\n"
            "Iteration  50: Energy = -76.43201844 Delta-E = 0.000123\n"
            "SCF NOT CONVERGED AFTER 50 CYCLES\n"
            "ORCA finished by error termination in SCF\n"
        )

        report = translator.translate_log_output(orca_log_snippet, engine_hint="ORCA")
        assert report.category == ChemicalFaultCategory.SCF_CONVERGENCE
        assert report.engine == "ORCA"
        assert len(report.actionable_remediation) > 0

    def test_custom_signature_registration(self) -> None:
        """Verify dynamic registration of custom chemical error signatures."""
        translator = ChemicalCrashTranslator()
        translator.register_custom_pattern(
            regex_pattern=r"SOLVENT_CAVITY_PUNCTURE",
            category=ChemicalFaultCategory.UNKNOWN_CHEMICAL_FAULT,
            headline="CPCM Solvent Cavity Self-Intersection",
            explanation="The dielectric continuum cavity self-intersected.",
            remediation=["Increase solvent cavity sphere radius."],
            adjustments={"solvation_radius_scale": 1.2},
        )

        log = "FATAL: SOLVENT_CAVITY_PUNCTURE on sphere 4 of solute."
        report = translator.translate_log_output(log, engine_hint="ORCA-CPCM")
        assert report.headline == "CPCM Solvent Cavity Self-Intersection"
        assert report.input_adjustment_suggestions.get("solvation_radius_scale") == 1.2

    def test_sys_excepthook_lifecycle(self) -> None:
        """Verify excepthook installation and clean restoration."""
        translator = ChemicalCrashTranslator()
        captured_reports: List[ChemicalDiagnosticReport] = []

        def custom_collector(rep: ChemicalDiagnosticReport) -> None:
            captured_reports.append(rep)

        orig_hook = sys.excepthook
        try:
            translator.install_sys_excepthook(handler_callback=custom_collector)
            assert sys.excepthook != orig_hook

            # Trigger hook invocation with authentic exception
            exc = SCFConvergenceError("Electronic energy convergence ceiling exceeded", engine="TestEngine")
            sys.excepthook(type(exc), exc, exc.__traceback__)

            assert len(captured_reports) == 1
            assert captured_reports[0].category == ChemicalFaultCategory.SCF_CONVERGENCE
        finally:
            translator.restore_sys_excepthook()
            assert sys.excepthook == orig_hook
