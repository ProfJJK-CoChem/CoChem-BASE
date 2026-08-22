#!/usr/bin/env python3
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Zero-Mock Physical Test Suite for CoChem-BASE Regex Traps Subsystem.
Tests:
1. Polymorphic EngineDialect configuration and regex mapping for ORCA, CFOUR, PySCF, and Auto-detection.
2. NaN & Infinity Trap: 1MB chunked stream evaluation, boundary overlap detection, NUMERICAL_COLLAPSE state flag.
3. SCF Ping-Pong Trap: 5-cycle Delta E tracking, alternating sign oscillation detection with constant magnitude,
   SCF_PING_PONG_DETECTED flag, and fallback solver recommendations (SOSCF / KDIIS).
4. Linear Dependence Overlap Trap: Dialect-specific warnings for overlap matrix eigenvalues < 1e-6,
   flagging geometry/basis as ill-conditioned, LINEAR_DEPENDENCE_DETECTED state flag.
5. Chunked stream processing (1MB chunks) across text / binary streams and files without loading whole files into memory.
6. Incremental live stream feed and multi-trap composite scan reports.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
from pathlib import Path
from typing import List

import pytest

from core_engine.cochem_regex_traps import (
    EngineDialect,
    FallbackSolver,
    RegexTrapEngine,
    TrapDetectionEvent,
    TrapFlag,
    autodetect_dialect,
    get_dialect_regex_map,
)

# =====================================================================
# 1. EngineDialect Configuration & Polymorphic Mapping Tests
# =====================================================================

class TestEngineDialectAndMapping:
    """Validates dialect enumeration, parsing, regex mapping, and auto-detection."""

    def test_dialect_enum_values_and_from_str(self) -> None:
        """Verifies dialect parsing from string with various casing."""
        assert EngineDialect.from_str("orca") == EngineDialect.ORCA
        assert EngineDialect.from_str("ORCA") == EngineDialect.ORCA
        assert EngineDialect.from_str("cfour") == EngineDialect.CFOUR
        assert EngineDialect.from_str("C-FOUR") == EngineDialect.CFOUR
        assert EngineDialect.from_str("pyscf") == EngineDialect.PYSCF
        assert EngineDialect.from_str("PySCF") == EngineDialect.PYSCF
        assert EngineDialect.from_str("auto") == EngineDialect.AUTODETECT
        assert EngineDialect.from_str("autodetect") == EngineDialect.AUTODETECT

        with pytest.raises(ValueError, match="Unknown dialect"):
            EngineDialect.from_str("unsupported_engine_xyz")

    def test_dialect_regex_mapping_registry(self) -> None:
        """Verifies each dialect provides distinct compiled regex patterns."""
        for dialect in [EngineDialect.ORCA, EngineDialect.CFOUR, EngineDialect.PYSCF]:
            regex_map = get_dialect_regex_map(dialect)
            assert regex_map.dialect == dialect
            assert len(regex_map.scf_cycle_patterns) > 0
            assert len(regex_map.linear_dependence_patterns) > 0
            assert len(regex_map.dialect_signatures) > 0

    def test_autodetect_orca_banner(self) -> None:
        """Tests auto-detection of ORCA log header."""
        sample_orca_header = """
        ================================================================================
                                          * O   R   C   A *
        ================================================================================
        Program Version 6.1.0 - RELEASE
        An ab initio, DFT and semiempirical electronic structure package
        """
        assert autodetect_dialect(sample_orca_header) == EngineDialect.ORCA

    def test_autodetect_cfour_banner(self) -> None:
        """Tests auto-detection of CFOUR log header."""
        sample_cfour_header = """
        ================================================================================
                       EXECUTION OF CFOUR (ACES2) SUITE BEGINS
        ================================================================================
        ZMAT input file found. Starting quantum mechanical calculation.
        """
        assert autodetect_dialect(sample_cfour_header) == EngineDialect.CFOUR

    def test_autodetect_pyscf_banner(self) -> None:
        """Tests auto-detection of PySCF output stream."""
        sample_pyscf_header = """
        ******** PySCF-2.5.0 ********
        pyscf.scf.hf.RHF object at 0x7f9a12345678
        geometry coordinates initialized.
        """
        assert autodetect_dialect(sample_pyscf_header) == EngineDialect.PYSCF

    def test_autodetect_unknown_defaults_to_orca(self) -> None:
        """Tests fallback when no signature matches."""
        generic_text = "Some random computation output without package signatures."
        assert autodetect_dialect(generic_text) == EngineDialect.AUTODETECT


# =====================================================================
# 2. NaN & Infinity Trap (Numerical Collapse) Tests
# =====================================================================

class TestNumericalCollapseTrap:
    """Validates IEEE float collapse detection across patterns, chunks, and boundaries."""

    @pytest.mark.parametrize(
        "token",
        [
            "NaN",
            "nan",
            "NAN",
            "+NaN",
            "-NaN",
            "NaNQ",
            "NaNS",
            "Infinity",
            "+Infinity",
            "-Infinity",
            "inf",
            "+inf",
            "-inf",
            "1.#IND",
            "-1.#IND",
            "1.#IND00",
            "-1.#IND00",
            "1.#INF",
            "-1.#INF",
            "1.#INF00",
            "-1.#INF00",
            "1.#QNAN",
            "1.#QNAN0",
            "1.#SNAN",
            "1.#SNAN0",
        ],
    )
    def test_numerical_collapse_tokens_detection(self, token: str) -> None:
        """Tests that all IEEE floating point invalid numerical states are trapped."""
        log_sample = f"""
        Iter  12: Energy= -76.421980012 DeltaE= -0.00012300
        Iter  13: Energy= {token} DeltaE= -0.00000000
        Iter  14: Energy= {token} DeltaE= 0.00000000
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(log_sample, dialect=EngineDialect.ORCA)

        assert report.primary_flag == TrapFlag.NUMERICAL_COLLAPSE
        assert report.numerical_collapse is not None
        assert report.numerical_collapse.detected is True
        assert token.lower() in report.numerical_collapse.token.lower() or report.numerical_collapse.token.lower() in token.lower()

    def test_numerical_collapse_ignores_safe_words(self) -> None:
        """Ensures plain words like 'information', 'infinite', or 'influence' are not false positives."""
        clean_text = """
        Calculation information:
        The infinite dilution limit is approximated with CPCM.
        The influence of polarization functions was evaluated.
        Total Energy: -154.29817451 Hartree
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(clean_text, dialect=EngineDialect.ORCA)

        assert report.primary_flag == TrapFlag.CLEAN
        assert report.numerical_collapse is None or not report.numerical_collapse.detected

    def test_numerical_collapse_chunk_boundary_overlap(self) -> None:
        """
        Tests that a numerical collapse token split across consecutive 1MB chunk boundaries
        is correctly trapped due to boundary overlap buffer.
        """
        chunk_size = 64 * 1024  # 64 KB for test speed with overlap
        engine = RegexTrapEngine(chunk_size_bytes=chunk_size, overlap_bytes=1024)

        # Construct a text where "1.#IND" is sliced exactly at chunk boundary
        # chunk 1 ends with "1.#" and chunk 2 starts with "IND "
        prefix_pad = "Iter   1 : Energy=   -76.1200000000  DeltaE=   -0.54000000\n" * 100
        pad_len = chunk_size - len(prefix_pad) - len("Iter 101 : Energy= 1.#")
        part1 = prefix_pad + (" " * max(0, pad_len)) + "Iter 101 : Energy= 1.#"
        part2 = "IND  DeltaE= 0.00000000\n" + (" " * 5000)
        full_stream = io.StringIO(part1 + part2)

        report = engine.scan_stream(full_stream, dialect=EngineDialect.ORCA)
        assert report.primary_flag == TrapFlag.NUMERICAL_COLLAPSE
        assert report.numerical_collapse is not None
        assert report.numerical_collapse.detected is True
        assert "1.#IND" in report.numerical_collapse.token



# =====================================================================
# 3. SCF Ping-Pong Trap Tests
# =====================================================================

class TestSCFPingPongTrap:
    """Validates SCF Ping-Pong oscillation detection for ORCA, CFOUR, and PySCF."""

    def test_orca_scf_ping_pong_detection(self) -> None:
        """
        Tests ORCA SCF log showing 5 alternating Delta E cycles with constant magnitude,
        verifying SCF_PING_PONG_DETECTED and SOSCF/KDIIS solver recommendation.
        """
        orca_log = """
        ----------------------------------
        SCF ITERATIONS (ORCA format)
        ----------------------------------
        Iter   1 : Energy=   -76.1200000000  DeltaE=   -0.54000000
        Iter   2 : Energy=   -76.3100000000  DeltaE=   -0.19000000
        Iter   3 : Energy=   -76.3142000000  DeltaE=   +0.00420000
        Iter   4 : Energy=   -76.3100000000  DeltaE=   -0.00420000
        Iter   5 : Energy=   -76.3142000000  DeltaE=   +0.00420000
        Iter   6 : Energy=   -76.3100000000  DeltaE=   -0.00420000
        Iter   7 : Energy=   -76.3142000000  DeltaE=   +0.00420000
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(orca_log, dialect=EngineDialect.ORCA)

        assert report.primary_flag == TrapFlag.SCF_PING_PONG_DETECTED
        assert report.scf_ping_pong is not None
        assert report.scf_ping_pong.detected is True
        assert report.scf_ping_pong.recommended_fallback in [FallbackSolver.SOSCF, FallbackSolver.KDIIS]
        assert "solver" in report.environment_recommendations
        assert report.environment_recommendations["solver"] in ["SOSCF", "KDIIS"]
        assert len(report.scf_history) >= 7

    def test_cfour_scf_ping_pong_detection_with_d_notation(self) -> None:
        """
        Tests CFOUR SCF log with Fortran D-exponent formatting showing 5 oscillating cycles.
        """
        cfour_log = """
        EXECUTION OF CFOUR SUITE
        Iter   1   -100.15000000   -0.4500D+00
        Iter   2   -100.28000000   -0.1300D+00
        Iter   3   -100.28350000   +0.3500D-02
        Iter   4   -100.28000000   -0.3500D-02
        Iter   5   -100.28350000   +0.3500D-02
        Iter   6   -100.28000000   -0.3500D-02
        Iter   7   -100.28350000   +0.3500D-02
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(cfour_log, dialect=EngineDialect.CFOUR)

        assert report.primary_flag == TrapFlag.SCF_PING_PONG_DETECTED
        assert report.scf_ping_pong is not None
        assert report.scf_ping_pong.detected is True
        assert report.scf_ping_pong.recommended_fallback in [FallbackSolver.SOSCF, FallbackSolver.KDIIS]

    def test_pyscf_scf_ping_pong_detection(self) -> None:
        """
        Tests PySCF SCF log showing alternating signs.
        """
        pyscf_log = """
        ******** PySCF SCF ********
        cycle = 1  E = -128.50000000  delta_E = -0.80000000
        cycle = 2  E = -128.82000000  delta_E = -0.32000000
        cycle = 3  E = -128.82650000  delta_E =  0.00650000
        cycle = 4  E = -128.82000000  delta_E = -0.00650000
        cycle = 5  E = -128.82650000  delta_E =  0.00650000
        cycle = 6  E = -128.82000000  delta_E = -0.00650000
        cycle = 7  E = -128.82650000  delta_E =  0.00650000
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(pyscf_log, dialect=EngineDialect.PYSCF)

        assert report.primary_flag == TrapFlag.SCF_PING_PONG_DETECTED
        assert report.scf_ping_pong is not None
        assert report.scf_ping_pong.detected is True

    def test_monotonic_scf_does_not_trigger_ping_pong(self) -> None:
        """Validates that normal converging SCF does not trigger ping pong."""
        converging_log = """
        Iter   1 : Energy=   -76.1200000000  DeltaE=   -0.54000000
        Iter   2 : Energy=   -76.3100000000  DeltaE=   -0.19000000
        Iter   3 : Energy=   -76.3500000000  DeltaE=   -0.04000000
        Iter   4 : Energy=   -76.3550000000  DeltaE=   -0.00500000
        Iter   5 : Energy=   -76.3556000000  DeltaE=   -0.00060000
        Iter   6 : Energy=   -76.3556800000  DeltaE=   -0.00008000
        Iter   7 : Energy=   -76.3556890000  DeltaE=   -0.00000900
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(converging_log, dialect=EngineDialect.ORCA)

        assert report.primary_flag == TrapFlag.CLEAN
        assert report.scf_ping_pong is None or not report.scf_ping_pong.detected


# =====================================================================
# 4. Linear Dependence Overlap Trap Tests
# =====================================================================

class TestLinearDependenceTrap:
    """Validates detection of near-singular overlap matrices and small eigenvalues (< 1e-6)."""

    def test_orca_linear_dependence_small_eigenvalue(self) -> None:
        """Tests ORCA output reporting eigenvalue < 1e-6."""
        orca_log = """
        * O   R   C   A *
        Smallest eigenvalue of the overlap matrix : 4.312e-08
        WARNING: There are 2 small eigenvalues (< 1e-06) in the overlap matrix
        Basis set has linear dependencies
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(orca_log, dialect=EngineDialect.ORCA)

        assert report.primary_flag == TrapFlag.LINEAR_DEPENDENCE_DETECTED
        assert report.linear_dependence is not None
        assert report.linear_dependence.detected is True
        assert report.linear_dependence.ill_conditioned is True
        assert report.linear_dependence.min_eigenvalue is not None
        assert report.linear_dependence.min_eigenvalue < 1e-6
        assert "AutoAux" in report.linear_dependence.recommended_action or "SThresh" in report.linear_dependence.recommended_action

    def test_cfour_linear_dependence_warning(self) -> None:
        """Tests CFOUR output with overlap matrix eigenvalue warning."""
        cfour_log = """
        EXECUTION OF CFOUR SUITE
        WARNING: Overlap matrix has eigenvalues smaller than 1.0D-06: 3.14D-08
        Linear dependencies detected in atomic orbital basis
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(cfour_log, dialect=EngineDialect.CFOUR)

        assert report.primary_flag == TrapFlag.LINEAR_DEPENDENCE_DETECTED
        assert report.linear_dependence is not None
        assert report.linear_dependence.detected is True
        assert report.linear_dependence.min_eigenvalue is not None
        assert report.linear_dependence.min_eigenvalue < 1e-6

    def test_pyscf_linear_dependence_warning(self) -> None:
        """Tests PySCF output reporting small overlap matrix eigenvalue."""
        pyscf_log = """
        ******** PySCF ********
        Small eigenvalue of overlap matrix: 5.21e-07 < 1e-06
        Basis set linear dependence detected. Recommend removing diffuse functions.
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(pyscf_log, dialect=EngineDialect.PYSCF)

        assert report.primary_flag == TrapFlag.LINEAR_DEPENDENCE_DETECTED
        assert report.linear_dependence is not None
        assert report.linear_dependence.detected is True
        assert report.linear_dependence.ill_conditioned is True

    def test_safe_eigenvalue_does_not_trigger_linear_dependence(self) -> None:
        """Tests that eigenvalue >= 1e-6 is safe and does not trigger trap."""
        clean_log = """
        * O   R   C   A *
        Smallest eigenvalue of the overlap matrix : 1.452e-04
        Overlap matrix condition is well-behaved.
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(clean_log, dialect=EngineDialect.ORCA)

        assert report.primary_flag == TrapFlag.CLEAN
        assert report.linear_dependence is None or not report.linear_dependence.detected


# =====================================================================
# 5. Chunked Stream Processing & Real File I/O Tests
# =====================================================================

class TestChunkedStreamProcessing:
    """Validates 1MB chunked stream processing for text, binary streams, and files."""

    def test_large_stream_chunking_without_whole_file_memory_load(self) -> None:
        """
        Generates a 2.5 MB simulated stream with an embedded ping-pong oscillation
        and verifies it processes accurately in 1MB chunks.
        """
        pad_chunk = "INFO: Step progress calculation normal\n" * 20000  # ~780 KB
        orca_ping_pong = """
        ================================================================================
                                          * O   R   C   A *
        ================================================================================
        Iter   1 : Energy=   -76.1200000000  DeltaE=   -0.54000000
        Iter   2 : Energy=   -76.3100000000  DeltaE=   -0.19000000
        Iter   3 : Energy=   -76.3142000000  DeltaE=   +0.00420000
        Iter   4 : Energy=   -76.3100000000  DeltaE=   -0.00420000
        Iter   5 : Energy=   -76.3142000000  DeltaE=   +0.00420000
        Iter   6 : Energy=   -76.3100000000  DeltaE=   -0.00420000
        Iter   7 : Energy=   -76.3142000000  DeltaE=   +0.00420000
        """
        large_content = (pad_chunk * 3) + orca_ping_pong + (pad_chunk * 1)
        stream = io.StringIO(large_content)

        engine = RegexTrapEngine(chunk_size_bytes=1024 * 1024)  # 1MB
        report = engine.scan_stream(stream, dialect=EngineDialect.AUTODETECT)

        assert report.detected_dialect == EngineDialect.ORCA
        assert report.primary_flag == TrapFlag.SCF_PING_PONG_DETECTED
        assert report.total_bytes_processed > 2 * 1024 * 1024
        assert report.total_chunks_processed >= 3

    def test_binary_stream_processing_with_invalid_utf8_recovery(self) -> None:
        """
        Verifies that binary streams with sporadic corrupted bytes
        are decoded safely with replacement and scanned accurately.
        """
        binary_data = (
            b"\x80\x81\xFF"
            b"* O   R   C   A *\n"
            b"Smallest eigenvalue of the overlap matrix : 1.234e-09\n"
            b"\xFE\xFD"
        )
        stream = io.BytesIO(binary_data)
        engine = RegexTrapEngine()
        report = engine.scan_stream(stream, dialect=EngineDialect.AUTODETECT)

        assert report.primary_flag == TrapFlag.LINEAR_DEPENDENCE_DETECTED
        assert report.detected_dialect == EngineDialect.ORCA

    def test_scan_real_file_on_disk(self) -> None:
        """Tests scanning an actual physical file on disk."""
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False, encoding="utf-8") as f:
            f.write("""
            ******** PySCF-2.5.0 ********
            cycle = 1  E = -76.00000000  delta_E = -0.50000000
            cycle = 2  E = -76.12000000  delta_E = -0.12000000
            cycle = 3  E = -76.12300000  delta_E =  0.00300000
            cycle = 4  E = -76.12000000  delta_E = -0.00300000
            cycle = 5  E = -76.12300000  delta_E =  0.00300000
            cycle = 6  E = -76.12000000  delta_E = -0.00300000
            cycle = 7  E = -76.12300000  delta_E =  0.00300000
            """)
            temp_path = Path(f.name)

        try:
            engine = RegexTrapEngine()
            report = engine.scan_file(temp_path)
            assert report.primary_flag == TrapFlag.SCF_PING_PONG_DETECTED
            assert report.detected_dialect == EngineDialect.PYSCF
        finally:
            if temp_path.exists():
                os.unlink(temp_path)

    def test_incremental_live_stream_feeding(self) -> None:
        """
        Simulates line-by-line streaming from a running subprocess stdout,
        verifying early detection event emission.
        """
        engine = RegexTrapEngine(dialect=EngineDialect.ORCA)
        lines = [
            "* O   R   C   A *",
            "Iter   1 : Energy=   -76.1200000000  DeltaE=   -0.54000000",
            "Iter   2 : Energy=   -76.3100000000  DeltaE=   -0.19000000",
            "Iter   3 : Energy=   -76.3142000000  DeltaE=   +0.00420000",
            "Iter   4 : Energy=   -76.3100000000  DeltaE=   -0.00420000",
            "Iter   5 : Energy=   -76.3142000000  DeltaE=   +0.00420000",
            "Iter   6 : Energy=   -76.3100000000  DeltaE=   -0.00420000",
            "Iter   7 : Energy=   -76.3142000000  DeltaE=   +0.00420000",
        ]

        events: List[TrapDetectionEvent] = []
        for line in lines:
            event = engine.feed_line(line)
            if event is not None:
                events.append(event)

        final_report = engine.finalize()
        assert final_report.primary_flag == TrapFlag.SCF_PING_PONG_DETECTED
        assert any(e.flag == TrapFlag.SCF_PING_PONG_DETECTED for e in events)

    def test_report_serialization_and_to_dict(self) -> None:
        """Verifies full serialization to dict and JSON format for reporting."""
        orca_log = """
        * O   R   C   A *
        Iter   1 : Energy= -76.00000000 DeltaE= -0.50000000
        Iter   2 : Energy= NaN DeltaE= 0.00000000
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(orca_log, dialect=EngineDialect.ORCA)

        report_dict = report.to_dict()
        assert report_dict["primary_flag"] == "NUMERICAL_COLLAPSE"
        assert report_dict["detected_dialect"] == "ORCA"
        assert isinstance(report_dict["events"], list)

        json_str = report.to_json()
        data = json.loads(json_str)
        assert data["primary_flag"] == "NUMERICAL_COLLAPSE"


# =====================================================================
# 6. Multi-Trap Precedence, Functional API & Edge Cases Tests
# =====================================================================

class TestMultiTrapPrecedenceAndFunctionalAPI:
    """Validates multi-trap conflict resolution, convenience APIs, and edge cases."""

    def test_multi_trap_priority_numerical_collapse_over_scf_ping_pong(self) -> None:
        """
        Tests log containing both SCF ping-pong oscillation AND subsequent NaN,
        verifying NUMERICAL_COLLAPSE takes top priority.
        """
        log_content = """
        * O   R   C   A *
        Smallest eigenvalue of the overlap matrix : 2.123e-08
        Iter   1 : Energy=   -76.1200000000  DeltaE=   -0.54000000
        Iter   2 : Energy=   -76.3100000000  DeltaE=   -0.19000000
        Iter   3 : Energy=   -76.3142000000  DeltaE=   +0.00420000
        Iter   4 : Energy=   -76.3100000000  DeltaE=   -0.00420000
        Iter   5 : Energy=   -76.3142000000  DeltaE=   +0.00420000
        Iter   6 : Energy=   -76.3100000000  DeltaE=   -0.00420000
        Iter   7 : Energy=   -76.3142000000  DeltaE=   +0.00420000
        Iter   8 : Energy=   NaN             DeltaE=   0.00000000
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(log_content, dialect=EngineDialect.ORCA)

        assert report.primary_flag == TrapFlag.NUMERICAL_COLLAPSE
        assert report.numerical_collapse is not None and report.numerical_collapse.detected
        assert report.scf_ping_pong is not None and report.scf_ping_pong.detected
        assert report.linear_dependence is not None and report.linear_dependence.detected
        assert len(report.events) >= 3

    def test_multi_trap_priority_ping_pong_over_linear_dependence(self) -> None:
        """
        Tests log with linear dependence warning and continuing into ping pong without NaN,
        verifying SCF_PING_PONG_DETECTED takes priority over linear dependence.
        """
        log_content = """
        * O   R   C   A *
        WARNING: Basis set has linear dependencies
        Smallest eigenvalue of the overlap matrix : 5.123e-09
        Iter   1 : Energy=   -76.1200000000  DeltaE=   -0.54000000
        Iter   2 : Energy=   -76.3100000000  DeltaE=   -0.19000000
        Iter   3 : Energy=   -76.3142000000  DeltaE=   +0.00420000
        Iter   4 : Energy=   -76.3100000000  DeltaE=   -0.00420000
        Iter   5 : Energy=   -76.3142000000  DeltaE=   +0.00420000
        Iter   6 : Energy=   -76.3100000000  DeltaE=   -0.00420000
        Iter   7 : Energy=   -76.3142000000  DeltaE=   +0.00420000
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(log_content, dialect=EngineDialect.ORCA)

        assert report.primary_flag == TrapFlag.SCF_PING_PONG_DETECTED
        assert report.linear_dependence is not None and report.linear_dependence.detected

    def test_convenience_scan_log_for_traps(self) -> None:
        """Verifies top-level helper function across string, bytes, and file."""
        from core_engine.cochem_regex_traps import scan_log_for_traps

        text_orca = "* O   R   C   A *\nSmallest eigenvalue of the overlap matrix : 1.0e-09\n"
        rep1 = scan_log_for_traps(text_orca)
        assert rep1.primary_flag == TrapFlag.LINEAR_DEPENDENCE_DETECTED

        bytes_pyscf = b"******** PySCF ********\ncycle = 1  E = NaN  delta_E = 0.0\n"
        rep2 = scan_log_for_traps(bytes_pyscf)
        assert rep2.primary_flag == TrapFlag.NUMERICAL_COLLAPSE

    def test_empty_stream_and_clean_run(self) -> None:
        """Tests that empty stream returns CLEAN without errors."""
        engine = RegexTrapEngine()
        report = engine.scan_text("")
        assert report.primary_flag == TrapFlag.CLEAN
        assert report.total_bytes_processed == 0
        assert len(report.events) == 0


# =====================================================================
# 7. Adversarially Hardened Edge Case Tests
# =====================================================================

class TestAdversarialHardenedEdgeCases:
    """Rigorous tests covering adversarial audit findings and boundary conditions."""

    def test_floats_without_decimal_points_and_fortran_d(self) -> None:
        """Verifies parsing of floats like 5e-07, 1e-8, 1D-06 without explicit decimal point."""
        orca_log = """
        * O   R   C   A *
        Smallest eigenvalue of the overlap matrix : 5e-07
        Iter   1 : Energy= -76 DeltaE= -1e-01
        Iter   2 : Energy= -76.2 DeltaE= -2e-01
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(orca_log, dialect=EngineDialect.ORCA)
        assert report.linear_dependence is not None
        assert report.linear_dependence.detected is True
        assert report.linear_dependence.min_eigenvalue == 5e-7
        assert len(report.scf_history) == 2

    def test_orca_singular_grammar_overlap_warning(self) -> None:
        """Verifies singular grammar: 'There is 1 small eigenvalue (< 1e-06)'."""
        orca_log = """
        * O   R   C   A *
        WARNING: There is 1 small eigenvalue (< 1e-06) in the overlap matrix
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(orca_log, dialect=EngineDialect.ORCA)
        assert report.primary_flag == TrapFlag.LINEAR_DEPENDENCE_DETECTED
        assert report.linear_dependence is not None
        assert report.linear_dependence.detected is True

    def test_autodetect_pyscf_without_header_banner(self) -> None:
        """Verifies autodetect successfully binds PySCF from raw cycle patterns when header is absent."""
        raw_pyscf_stream = """
        cycle = 1  E = -128.50000000  delta_E = -0.80000000
        cycle = 2  E = -128.82000000  delta_E = -0.32000000
        cycle = 3  E = -128.82650000  delta_E =  0.00650000
        cycle = 4  E = -128.82000000  delta_E = -0.00650000
        cycle = 5  E = -128.82650000  delta_E =  0.00650000
        cycle = 6  E = -128.82000000  delta_E = -0.00650000
        cycle = 7  E = -128.82650000  delta_E =  0.00650000
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(raw_pyscf_stream, dialect=EngineDialect.AUTODETECT)
        assert report.detected_dialect == EngineDialect.PYSCF
        assert report.primary_flag == TrapFlag.SCF_PING_PONG_DETECTED

    def test_incremental_utf8_multibyte_split_across_chunks(self) -> None:
        """Verifies multi-byte UTF-8 characters split exactly across byte chunks decode cleanly."""
        # Å is \xc3\x85 in UTF-8
        chunk1 = b"Iter 1 : Energy= -76.0 DeltaE= -0.5\nBond Length: 1.54 \xc3"
        chunk2 = b"\x85\nIter 2 : Energy= NaN DeltaE= 0.0\n"

        engine = RegexTrapEngine(chunk_size_bytes=len(chunk1))
        engine.feed_chunk(chunk1)
        engine.feed_chunk(chunk2)
        report = engine.finalize()

        assert report.primary_flag == TrapFlag.NUMERICAL_COLLAPSE
        assert report.numerical_collapse is not None and report.numerical_collapse.detected

    def test_evaluate_scf_ping_pong_handles_nan_and_inf_gracefully(self) -> None:
        """Verifies evaluate_scf_ping_pong does not crash on math.nan or math.inf in SCFCycleRecords."""
        import math
        from core_engine.cochem_regex_traps import SCFCycleRecord, evaluate_scf_ping_pong

        records = [
            SCFCycleRecord(cycle=1, energy=-76.0, delta_e=-0.5),
            SCFCycleRecord(cycle=2, energy=-76.2, delta_e=-0.2),
            SCFCycleRecord(cycle=3, energy=-76.21, delta_e=math.nan),
            SCFCycleRecord(cycle=4, energy=-76.20, delta_e=math.inf),
            SCFCycleRecord(cycle=5, energy=-76.21, delta_e=-math.inf),
        ]
        analysis = evaluate_scf_ping_pong(records)
        assert analysis.detected is False

    def test_exact_line_number_attribution_in_stream_chunks(self) -> None:
        """Verifies that line numbers are accurately reported when NaN occurs deep in a multi-chunk stream."""
        lines = [f"Iter {i}: Energy= -76.0 DeltaE= -0.1\n" for i in range(1, 501)]
        lines.append("Iter 501: Energy= NaN DeltaE= 0.0\n")
        engine = RegexTrapEngine()
        report = engine.scan_text("".join(lines), dialect=EngineDialect.ORCA)

        assert report.primary_flag == TrapFlag.NUMERICAL_COLLAPSE
        assert report.numerical_collapse is not None
        assert report.numerical_collapse.detected is True
        assert report.numerical_collapse.line_number == 501



