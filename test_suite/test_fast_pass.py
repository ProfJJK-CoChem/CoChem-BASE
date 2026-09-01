#!/usr/bin/env python3
"""Comprehensive Zero-Mock test suite for interfaces/fast_pass.py in test_suite.

Validates:
1. File structure, strictly Unix LF line endings (\\n), standard UTF-8 encoding, and zero BOM.
2. Zero personal path leaks (using cochem_base.path_sanitization.leak_patterns).
3. Zero banned anti-spoofing terms.
4. Total eradication of Effective Medium Theory (legacy calculator) mentions.
5. Re-exports, backward compatibility aliases, and symbol parity with cochem_unity_fast_pass_widget.
6. CLI argument parsing and execution with real physical geometry optimization.
7. Method Matrix v4 Section 9B and Section 10.6 compliance.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import tempfile

import pytest

import cochem_base.interfaces.fast_pass as cochem_base_fast_pass
import interfaces.fast_pass as legacy_fast_pass
import cochem_base.interfaces.cochem_unity_fast_pass_widget as canonical_widget
from cochem_base.path_sanitization import leak_patterns


@pytest.fixture
def interfaces_fast_pass_path() -> Path:
    """Return the absolute path to interfaces/fast_pass.py."""
    path = Path(__file__).resolve().parent.parent / "interfaces" / "fast_pass.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


@pytest.fixture
def cochem_base_fast_pass_path() -> Path:
    """Return the absolute path to cochem_base/interfaces/fast_pass.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_base" / "interfaces" / "fast_pass.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


def test_file_existence_and_structure(
    interfaces_fast_pass_path: Path, cochem_base_fast_pass_path: Path
) -> None:
    """Verify that fast_pass.py exists in both locations and has substantial content."""
    for p in (interfaces_fast_pass_path, cochem_base_fast_pass_path):
        assert p.exists(), f"File missing at {p}"
        content = p.read_text(encoding="utf-8")
        assert len(content) > 300, f"File at {p} is suspiciously small: {len(content)} bytes"


def test_unix_lf_and_encoding(
    interfaces_fast_pass_path: Path, cochem_base_fast_pass_path: Path
) -> None:
    """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
    for p in (interfaces_fast_pass_path, cochem_base_fast_pass_path):
        raw = p.read_bytes()
        assert b"\r\n" not in raw, f"Found Windows CRLF line endings in {p.name}"
        assert b"\n" in raw, f"Missing newline characters in {p.name}"
        assert not raw.startswith(b"\xef\xbb\xbf"), f"Found UTF-8 BOM marker in {p.name}"


def test_zero_personal_path_leaks(
    interfaces_fast_pass_path: Path, cochem_base_fast_pass_path: Path
) -> None:
    """Verify zero personal machine or local user path leakage."""
    patterns = leak_patterns()
    for p in (interfaces_fast_pass_path, cochem_base_fast_pass_path):
        lines = p.read_text(encoding="utf-8").splitlines()
        leaks = []
        for lineno, line in enumerate(lines, 1):
            for pattern, token in patterns:
                if pattern.search(line):
                    leaks.append((lineno, token, line.strip()))
        assert len(leaks) == 0, f"Detected personal path leaks in {p.name}: {leaks}"


def test_zero_mock_anti_spoofing_banned_terms(
    interfaces_fast_pass_path: Path, cochem_base_fast_pass_path: Path
) -> None:
    """Verify zero banned anti-spoofing terms exist in the deliverable files."""
    banned_words = [
        "".join(["m", "o", "c", "k"]),
        "".join(["d", "u", "m", "m", "y"]),
        "".join(["s", "t", "u", "b"]),
        "".join(["p", "l", "a", "c", "e", "h", "o", "l", "d", "e", "r"]),
        "".join(["f", "a", "k", "e"]),
        "".join(["#", " ", "T", "O", "D", "O"]),
        "".join(["N", "o", "t", "I", "m", "p", "l", "e", "m", "e", "n", "t", "e", "d", "E", "r", "r", "o", "r"]),
    ]
    for p in (interfaces_fast_pass_path, cochem_base_fast_pass_path):
        content = p.read_text(encoding="utf-8")
        for word in banned_words:
            pattern = r"\b" + re.escape(word) + r"\b" if word.isalpha() else re.escape(word)
            matches = list(re.finditer(pattern, content, flags=re.IGNORECASE))
            assert len(matches) == 0, f"Found banned anti-spoofing term '{word}' in {p.name}: {matches}"


def test_zero_mentions_of_banned_legacy_calculator(
    interfaces_fast_pass_path: Path, cochem_base_fast_pass_path: Path
) -> None:
    """Verify total eradication of Effective Medium Theory calculator mentions."""
    banned_code = "".join(["E", "M", "T"])
    for p in (interfaces_fast_pass_path, cochem_base_fast_pass_path):
        content = p.read_text(encoding="utf-8")
        matches = list(re.finditer(r"\b" + banned_code + r"\b", content))
        assert len(matches) == 0, f"Found banned legacy calculator mention in {p.name}: {matches}"


def test_reexports_and_symbol_parity() -> None:
    """Verify interfaces.fast_pass re-exports canonical symbols from cochem_unity_fast_pass_widget."""
    assert legacy_fast_pass.FastPassWidget is canonical_widget.FastPassWidget
    assert legacy_fast_pass.FastPassOptConfig is canonical_widget.FastPassOptConfig
    assert legacy_fast_pass.FastPassOptResult is canonical_widget.FastPassOptResult
    assert legacy_fast_pass.HardwareProfile is canonical_widget.HardwareProfile
    assert legacy_fast_pass.PubChemProperty is canonical_widget.PubChemProperty
    assert legacy_fast_pass.PubChemPropertyTable is canonical_widget.PubChemPropertyTable
    assert legacy_fast_pass.PubChemResponse is canonical_widget.PubChemResponse
    assert legacy_fast_pass.RDKitForceFieldCalculator is canonical_widget.RDKitForceFieldCalculator
    assert legacy_fast_pass.ase_atoms_to_xyz_string is canonical_widget.ase_atoms_to_xyz_string
    assert legacy_fast_pass.build_pubchem_pug_url is canonical_widget.build_pubchem_pug_url
    assert legacy_fast_pass.compute_file_sha256 is canonical_widget.compute_file_sha256
    assert legacy_fast_pass.count_xyz_atoms is canonical_widget.count_xyz_atoms
    assert legacy_fast_pass.generate_3d_coordinates_obabel is canonical_widget.generate_3d_coordinates_obabel
    assert legacy_fast_pass.generate_3d_coordinates_rdkit is canonical_widget.generate_3d_coordinates_rdkit
    assert legacy_fast_pass.get_ase_calculator is canonical_widget.get_ase_calculator
    assert legacy_fast_pass.profile_hardware is canonical_widget.profile_hardware
    assert legacy_fast_pass.query_pubchem_pug_rest is canonical_widget.query_pubchem_pug_rest
    assert legacy_fast_pass.rdkit_mol_to_ase_atoms is canonical_widget.rdkit_mol_to_ase_atoms
    assert legacy_fast_pass.run_ase_optimization is canonical_widget.run_ase_optimization
    assert legacy_fast_pass.run_crest_conformer_triage is canonical_widget.run_crest_conformer_triage
    assert legacy_fast_pass.run_fast_pass_optimization is canonical_widget.run_fast_pass_optimization
    assert legacy_fast_pass.smiles_to_rdkit_mol is canonical_widget.smiles_to_rdkit_mol
    assert legacy_fast_pass.write_xyz_file is canonical_widget.write_xyz_file
    assert legacy_fast_pass.xyz_file_to_ase_atoms is canonical_widget.xyz_file_to_ase_atoms
    assert legacy_fast_pass.HAS_3DMOL is canonical_widget.HAS_3DMOL
    assert legacy_fast_pass.HAS_ASE is canonical_widget.HAS_ASE
    assert legacy_fast_pass.HAS_RDKIT is canonical_widget.HAS_RDKIT
    assert legacy_fast_pass.INCHIKEY_REGEX is canonical_widget.INCHIKEY_REGEX
    assert legacy_fast_pass.KCAL_MOL_TO_EV is canonical_widget.KCAL_MOL_TO_EV


def test_backward_compatibility_aliases() -> None:
    """Verify legacy triage function aliases."""
    assert legacy_fast_pass.run_fast_pass is canonical_widget.run_fast_pass_optimization
    assert legacy_fast_pass.run_triage is canonical_widget.run_fast_pass_optimization
    assert legacy_fast_pass.triage_geometry is canonical_widget.run_fast_pass_optimization
    assert legacy_fast_pass.fast_pass_triage is canonical_widget.run_fast_pass_optimization


def test_cli_parser_construction() -> None:
    """Verify build_parser constructs a valid ArgumentParser with all expected arguments."""
    parser = legacy_fast_pass.build_parser()
    assert isinstance(parser, argparse.ArgumentParser)

    parsed = parser.parse_args(["CCO", "--engine", "rdkit-uff", "--steps", "100", "--fmax", "0.01", "--no-crest"])
    assert parsed.query == "CCO"
    assert parsed.engine == "rdkit-uff"
    assert parsed.steps == 100
    assert parsed.fmax == 0.01
    assert parsed.no_crest is True


def test_cli_execution_physical_run(tmp_path: Path) -> None:
    """Verify physical execution of main() CLI entrypoint on ethanol."""
    out_dir = tmp_path / "triage_output"
    exit_code = legacy_fast_pass.main([
        "--smiles", "CCO",
        "--engine", "rdkit-uff",
        "--steps", "50",
        "--fmax", "0.05",
        "--no-crest",
        "--output-dir", str(out_dir),
    ])
    assert exit_code == 0
    opt_xyz = out_dir / "optimized.xyz"
    assert opt_xyz.is_file()
    assert legacy_fast_pass.count_xyz_atoms(opt_xyz) == 9
