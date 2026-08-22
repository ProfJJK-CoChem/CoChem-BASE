"""Comprehensive physical Zero-Mock test suite for cochem_base.io.sequence_parsing.

Validates:
- Strictly Unix LF line endings (\n), standard UTF-8 encoding, and no BOM.
- Zero personal machine or local user path leakage.
- Backward compatibility and lazy resolution in cochem_base.io.
- Pydantic v2 data model SequenceRecord (properties, validation, serialization, transformation).
- EuropePMCFASTA-006 compliance and error invariants across protein, DNA, and RNA sequences.
- Strict residue validation and IUPAC extended ambiguity code handling.
- GC content calculation, reverse complementation, and codon translation.
- Isoelectric point (pI) estimation and molecular weight calculations.
- File I/O streaming, line wrapping, and multi-record roundtrip fidelity.
"""

from __future__ import annotations

import math
from pathlib import Path
import pytest

import cochem_base.io as io_pkg
from cochem_base.io.sequence_parsing import (
    EmptySequenceError,
    InvalidFastaFormatError,
    InvalidResidueError,
    SequenceBoundaryError,
    SequenceParser,
    SequenceParsingError,
    SequenceRecord,
    calculate_gc_content,
    calculate_sequence_molecular_weight,
    count_residues,
    estimate_isoelectric_point,
    format_fasta,
    parse_fasta,
    parse_fasta_file,
    parse_fasta_records,
    reverse_complement,
    translate_dna_to_protein,
    validate_sequence_residues,
    write_fasta,
)
from cochem_base.path_sanitization import leak_patterns


@pytest.fixture
def sequence_parsing_file_path() -> Path:
    """Return absolute path to cochem_base/io/sequence_parsing.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_base" / "io" / "sequence_parsing.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


def test_file_encoding_and_lf_line_endings(sequence_parsing_file_path: Path) -> None:
    """Verify strictly Unix LF line endings (\n), standard UTF-8 encoding, and no BOM."""
    raw = sequence_parsing_file_path.read_bytes()
    assert b"\r\n" not in raw, "Found Windows CRLF (\r\n) line endings in sequence_parsing.py"
    assert b"\n" in raw, "Missing newline characters in sequence_parsing.py"
    assert not raw.startswith(b"\xef\xbb\xbf"), "Found UTF-8 BOM marker in sequence_parsing.py"


def test_zero_personal_path_leaks(sequence_parsing_file_path: Path) -> None:
    """Verify zero personal machine or local user path leakage in sequence_parsing.py."""
    lines = sequence_parsing_file_path.read_text(encoding="utf-8").splitlines()
    patterns = leak_patterns()
    leaks = []
    for lineno, line in enumerate(lines, 1):
        for pattern, placeholder in patterns:
            if pattern.search(line):
                leaks.append((lineno, placeholder, line.strip()))

    assert len(leaks) == 0, f"Detected personal path leaks in sequence_parsing.py: {leaks}"


def test_io_package_lazy_resolution() -> None:
    """Verify that cochem_base.io exports all sequence parsing symbols."""
    assert io_pkg.SequenceParser is SequenceParser
    assert io_pkg.SequenceRecord is SequenceRecord
    assert io_pkg.SequenceParsingError is SequenceParsingError
    assert io_pkg.InvalidFastaFormatError is InvalidFastaFormatError
    assert io_pkg.InvalidResidueError is InvalidResidueError
    assert io_pkg.EmptySequenceError is EmptySequenceError
    assert io_pkg.SequenceBoundaryError is SequenceBoundaryError
    assert io_pkg.calculate_gc_content is calculate_gc_content
    assert io_pkg.reverse_complement is reverse_complement
    assert io_pkg.translate_dna_to_protein is translate_dna_to_protein
    assert io_pkg.estimate_isoelectric_point is estimate_isoelectric_point
    assert io_pkg.calculate_sequence_molecular_weight is calculate_sequence_molecular_weight
    assert io_pkg.count_residues is count_residues
    assert io_pkg.validate_sequence_residues is validate_sequence_residues
    assert io_pkg.parse_fasta is parse_fasta
    assert io_pkg.parse_fasta_records is parse_fasta_records
    assert io_pkg.parse_fasta_file is parse_fasta_file
    assert io_pkg.format_fasta is format_fasta
    assert io_pkg.write_fasta is write_fasta


def test_sequence_record_model() -> None:
    """Test SequenceRecord Pydantic model properties, methods, and validations."""
    # 1. Protein Sequence
    prot = SequenceRecord(
        id="sp|P04637|P53_HUMAN",
        description="sp|P04637|P53_HUMAN Cellular tumor antigen p53",
        sequence="MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGP",
        sequence_type="protein",
    )
    assert prot.length == 60
    assert prot.molecular_weight > 6000.0
    assert 2.0 < prot.isoelectric_point < 6.0
    assert prot.residue_counts["M"] == 3
    assert prot.residue_counts["E"] == 7

    with pytest.raises(ValueError, match="GC content is not applicable"):
        _ = prot.gc_content

    with pytest.raises(ValueError, match="Cannot reverse complement a protein sequence"):
        prot.reverse_complement()

    with pytest.raises(ValueError, match="Cannot translate a protein sequence"):
        prot.translate()

    # 2. DNA Sequence
    dna = SequenceRecord(
        id="seq_dna",
        description="Synthetic DNA construct",
        sequence="ATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG",
        sequence_type="dna",
    )
    assert dna.length == 39
    assert 40.0 < dna.gc_content < 70.0
    assert dna.molecular_weight > 10000.0

    with pytest.raises(ValueError, match="Isoelectric point is only applicable"):
        _ = dna.isoelectric_point

    # Reverse complement
    dna_rc = dna.reverse_complement()
    assert dna_rc.id == "seq_dna_rc"
    assert dna_rc.sequence.startswith("CTATCGGG")

    # Translation
    translated = dna.translate(stop_symbol="*")
    assert translated.sequence_type == "protein"
    assert translated.sequence.startswith("MAIVMGR")
    assert translated.sequence.endswith("*")

    # 3. FASTA Formatting
    fasta_out = prot.to_fasta(line_length=20)
    lines = fasta_out.splitlines()
    assert lines[0] == ">sp|P04637|P53_HUMAN Cellular tumor antigen p53"
    assert len(lines[1]) == 20
    assert len(lines[2]) == 20
    assert len(lines[3]) == 20

    fasta_unwrapped = prot.to_fasta(line_length=0)
    assert len(fasta_unwrapped.splitlines()) == 2


def test_legacy_sequence_parser_backward_compatibility() -> None:
    """Test exact backward compatibility with original SequenceParser API and EuropePMCFASTA-006 error invariants."""
    # Standard Protein Parser
    parser = SequenceParser(sequence_type="protein")
    assert parser.sequence_type == "protein"
    assert "A" in parser.valid_residues
    assert "C" in parser.valid_residues
    assert "W" in parser.valid_residues

    fasta_protein = """>sp|P01308|INS_HUMAN Insulin
GIVEQCCTSICSLYQLENYCN
>sp|P01308|CHAIN_B
FVNQHLCGSHLVEALYLVCGERGFFYTPKT
"""
    result = parser.parse_fasta(fasta_protein)
    assert len(result) == 2
    assert "sp|P01308|INS_HUMAN Insulin" in result
    assert result["sp|P01308|INS_HUMAN Insulin"] == "GIVEQCCTSICSLYQLENYCN"
    assert result["sp|P01308|CHAIN_B"] == "FVNQHLCGSHLVEALYLVCGERGFFYTPKT"

    # Nucleotide Parser
    nuc_parser = SequenceParser(sequence_type="nucleotide")
    fasta_nuc = ">dna_seq\nATGCGATCGATCGATCG\n"
    res_nuc = nuc_parser.parse_fasta(fasta_nuc)
    assert res_nuc["dna_seq"] == "ATGCGATCGATCGATCG"


def test_europe_pmc_fasta_006_error_invariants() -> None:
    """Verify exact compliance with EuropePMCFASTA-006 validation errors."""
    parser = SequenceParser(sequence_type="protein")

    # 1. Invalid sequence_type parameter
    with pytest.raises(ValueError, match="sequence_type must be 'protein' or 'nucleotide'"):
        SequenceParser(sequence_type="invalid_type")

    # 2. Empty FASTA content
    with pytest.raises(EmptySequenceError, match="Empty FASTA content or no valid sequences found.") as exc_info:
        parser.parse_fasta("")
    assert isinstance(exc_info.value, ValueError)

    with pytest.raises(EmptySequenceError, match="Empty FASTA content or no valid sequences found."):
        parser.parse_fasta("   \n\n  ")

    # 3. Data before header line
    with pytest.raises(InvalidFastaFormatError, match="Invalid FASTA format: Sequence data found before header at line 1"):
        parser.parse_fasta("GIVEQCCTSICSLYQLENYCN\n>header\nACDEF")

    # 4. Empty sequence for a header (boundary validation)
    with pytest.raises(SequenceBoundaryError, match="Sequence boundary validation failed: Sequence for 'empty_header' is empty."):
        parser.parse_fasta(">empty_header\n>next_header\nACDEF")

    with pytest.raises(SequenceBoundaryError, match="Sequence boundary validation failed: Sequence for 'last_empty' is empty."):
        parser.parse_fasta(">last_empty\n")

    # 5. Non-standard residue in strict mode
    with pytest.raises(InvalidResidueError, match="Non-standard residue checking failed: Invalid residue 'X' found at position 3 in sequence 'bad_residue'."):
        parser.parse_fasta(">bad_residue\nACDXEF")


def test_ambiguous_and_iupac_modes() -> None:
    """Test non-standard / extended IUPAC ambiguity codes under lenient parser settings."""
    # Protein with X, B, Z, J, U, O
    lenient_prot_parser = SequenceParser(sequence_type="protein", allow_ambiguous=True)
    fasta_ambig_prot = ">ambig_prot\nACDEFGHIKLMNPQRSTVWYBZXJOU"
    res = lenient_prot_parser.parse_fasta(fasta_ambig_prot)
    assert res["ambig_prot"] == "ACDEFGHIKLMNPQRSTVWYBZXJOU"

    # Nucleotide with N, R, Y, S, W, K, M
    lenient_nuc_parser = SequenceParser(sequence_type="nucleotide", allow_ambiguous=True)
    fasta_ambig_nuc = ">ambig_nuc\nACGTUNRYWSKMBDHV"
    res_nuc = lenient_nuc_parser.parse_fasta(fasta_ambig_nuc)
    assert res_nuc["ambig_nuc"] == "ACGTUNRYWSKMBDHV"


def test_gc_content_calculation() -> None:
    """Test calculation of GC content for DNA and RNA sequences."""
    # 50% GC
    assert calculate_gc_content("ATGC") == 50.0
    # 100% GC
    assert calculate_gc_content("GGCC") == 100.0
    # 0% GC
    assert calculate_gc_content("AATT") == 0.0
    # RNA with U
    assert calculate_gc_content("AUGC") == 50.0

    with pytest.raises(ValueError, match="Cannot calculate GC content for an empty sequence"):
        calculate_gc_content("")

    with pytest.raises(ValueError, match="contains no valid nucleotide residues"):
        calculate_gc_content("ZZZZ")


def test_reverse_complement() -> None:
    """Test reverse complementation of DNA and RNA sequences."""
    assert reverse_complement("ATGC") == "GCAT"
    assert reverse_complement("AAAA") == "TTTT"
    assert reverse_complement("AUGCAUGC", rna=True) == "GCAUGCAU"
    assert reverse_complement("ATNGRY") == "RYCNAT"
    assert reverse_complement("") == ""

    with pytest.raises(InvalidResidueError, match="Cannot compute complement"):
        reverse_complement("ATGCP")


def test_translate_dna_to_protein() -> None:
    """Test genetic code translation into amino acids."""
    # Standard start & codons: ATG GCT GAA TAA -> M A E *
    assert translate_dna_to_protein("ATGGCTGAATAA") == "MAE*"
    assert translate_dna_to_protein("AUGGCUGAAUAA") == "MAE*"
    assert translate_dna_to_protein("") == ""

    # Partial codons with allow_partial
    assert translate_dna_to_protein("ATGGCTGAATAAC", allow_partial=True) == "MAE*"
    with pytest.raises(ValueError, match="length .* is not a multiple of 3"):
        translate_dna_to_protein("ATGGCTGAATAAC", allow_partial=False)

    with pytest.raises(ValueError, match="Translation table 2 is not supported"):
        translate_dna_to_protein("ATG", table=2)


def test_estimate_isoelectric_point() -> None:
    """Test isoelectric point (pI) estimation with basic, acidic, and neutral sequences."""
    # Poly-Lysine: very basic (pI > 10.0)
    pi_polyk = estimate_isoelectric_point("KKKKKKKKKK")
    assert pi_polyk > 10.0

    # Poly-Aspartate: very acidic (pI < 4.0)
    pi_polyd = estimate_isoelectric_point("DDDDDDDDDD")
    assert pi_polyd < 4.0

    # Neutral peptide: Glycine-Alanine-Valine
    pi_neutral = estimate_isoelectric_point("GAVLGAVL")
    assert 5.0 <= pi_neutral <= 6.5

    with pytest.raises(ValueError, match="Cannot calculate isoelectric point for an empty sequence"):
        estimate_isoelectric_point("")


def test_molecular_weight_calculations() -> None:
    """Test molecular weight calculations across protein, DNA, and RNA."""
    # Alanine single residue: 71.0788 + 18.01528 = ~89.09 Da
    mw_a = calculate_sequence_molecular_weight("A", sequence_type="protein")
    assert math.isclose(mw_a, 89.09, rel_tol=1e-2)

    # DNA mw
    mw_dna = calculate_sequence_molecular_weight("ACGT", sequence_type="dna")
    assert mw_dna > 1200.0

    # RNA mw
    mw_rna = calculate_sequence_molecular_weight("ACGU", sequence_type="rna")
    assert mw_rna > 1200.0

    with pytest.raises(ValueError, match="Cannot calculate molecular weight for an empty sequence"):
        calculate_sequence_molecular_weight("")

    with pytest.raises(ValueError, match="Invalid sequence_type"):
        calculate_sequence_molecular_weight("ACGT", sequence_type="invalid")


def test_count_residues_and_validate_residues() -> None:
    """Test residue frequency counting and validity predicates."""
    counts = count_residues("AACCCTGGGG")
    assert counts == {"A": 2, "C": 3, "G": 4, "T": 1}

    assert validate_sequence_residues("ACDEFGHIKLMNPQRSTVWY", sequence_type="protein") is True
    assert validate_sequence_residues("ACDEFGHIKLMNPQRSTVWYX", sequence_type="protein", allow_ambiguous=False) is False
    assert validate_sequence_residues("ACDEFGHIKLMNPQRSTVWYX", sequence_type="protein", allow_ambiguous=True) is True

    assert validate_sequence_residues("ACGT", sequence_type="dna") is True
    assert validate_sequence_residues("ACGU", sequence_type="rna") is True
    assert validate_sequence_residues("ACGTN", sequence_type="dna", allow_ambiguous=False) is False
    assert validate_sequence_residues("ACGTN", sequence_type="dna", allow_ambiguous=True) is True
    assert validate_sequence_residues("", sequence_type="dna") is False


def test_file_io_roundtrip(tmp_path: Path) -> None:
    """Test physical file reading, writing, and parsing roundtrip."""
    fasta_data = """>seq1 First sequence
ACDEFGHIKLMNPQRSTVWY
>seq2 Second sequence
GIVEQCCTSICSLYQLENYCN
"""
    file_path = tmp_path / "test_sequences.fasta"
    file_path.write_bytes(fasta_data.replace("\r\n", "\n").encode("utf-8"))

    # Parse file via functional API
    records = parse_fasta_file(file_path, sequence_type="protein")
    assert len(records) == 2
    assert records[0].id == "seq1"
    assert records[0].sequence == "ACDEFGHIKLMNPQRSTVWY"
    assert records[1].id == "seq2"
    assert records[1].sequence == "GIVEQCCTSICSLYQLENYCN"

    # Write records to new file
    out_path = tmp_path / "output_sequences.fasta"
    write_fasta(records, out_path, line_length=10)

    assert out_path.is_file()
    out_raw = out_path.read_bytes()
    assert b"\r\n" not in out_raw, "CRLF detected in written FASTA file"

    # Re-read and verify roundtrip equivalence
    reloaded_records = parse_fasta_file(out_path, sequence_type="protein")
    assert len(reloaded_records) == 2
    assert reloaded_records[0].sequence == records[0].sequence
    assert reloaded_records[1].sequence == records[1].sequence


def test_format_fasta_variants() -> None:
    """Test format_fasta with SequenceRecord, list of records, and dictionary inputs."""
    rec = SequenceRecord(id="r1", sequence="ACDEF", sequence_type="protein")
    dict_input = {"h1": "ACDEF", "h2": "GHIKL"}

    assert ">r1" in format_fasta(rec)
    assert ">h1" in format_fasta(dict_input)
    assert ">h2" in format_fasta(dict_input)

    with pytest.raises(TypeError, match="Unsupported records type"):
        format_fasta(12345)  # type: ignore
