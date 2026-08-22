"""Biological sequence parsing, FASTA format conversion, and sequence analysis.

Enforces EuropePMCFASTA-006 compliance across protein, DNA, and RNA sequences.
Provides physicochemical property estimations (molecular weight, isoelectric point,
GC content, residue frequencies, translation, and reverse complementation).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Union

from pydantic import BaseModel, Field

# Standard genetic code table 1
CODON_TABLE: Dict[str, str] = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
    "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}

# Monoisotopic residue weights (Da)
AMINO_ACID_MW: Dict[str, float] = {
    "A": 71.0788, "R": 156.1875, "N": 114.1038, "D": 115.0886, "C": 103.1388,
    "E": 129.1155, "Q": 128.1307, "G": 57.0519, "H": 137.1411, "I": 113.1594,
    "L": 113.1594, "K": 128.1741, "M": 131.1926, "F": 147.1766, "P": 97.1167,
    "S": 87.0782, "T": 101.1051, "W": 186.2132, "Y": 163.1760, "V": 99.1326,
}

# Average mononucleotide weights (Da)
DNA_NUC_MW: Dict[str, float] = {"A": 313.21, "C": 289.18, "G": 329.21, "T": 304.20}
RNA_NUC_MW: Dict[str, float] = {"A": 329.21, "C": 305.18, "G": 345.21, "U": 306.17}

# Standard pKa values for peptide termini and side chains (EMBOSS scale)
PKA_TERMINI = {"N_TERM": 9.6, "C_TERM": 2.34}
PKA_SIDECHAINS = {"D": 3.86, "E": 4.25, "C": 8.33, "Y": 10.0, "H": 6.0, "K": 10.5, "R": 12.4}


class SequenceParsingError(ValueError):
    """Base error for all sequence parsing failures."""


class EmptySequenceError(SequenceParsingError):
    """Raised when FASTA content or an individual sequence record is completely empty."""


class InvalidFastaFormatError(SequenceParsingError):
    """Raised when FASTA formatting rules are violated (e.g. sequence before header)."""


class InvalidResidueError(SequenceParsingError):
    """Raised when an invalid/unrecognized residue character is encountered."""


class SequenceBoundaryError(SequenceParsingError):
    """Raised when a header has no associated sequence residues."""


def count_residues(sequence: str) -> Dict[str, int]:
    """Counts occurrence of each unique character in sequence."""
    counts: Dict[str, int] = {}
    for char in sequence.upper():
        counts[char] = counts.get(char, 0) + 1
    return dict(sorted(counts.items()))


def validate_sequence_residues(
    sequence: str,
    sequence_type: str = "protein",
    allow_ambiguous: bool = False,
) -> bool:
    """Returns True if all residues in sequence conform to the requested alphabet."""
    if not sequence:
        return False
    seq_upper = sequence.upper()
    seq_type_lower = sequence_type.lower()

    if seq_type_lower == "protein":
        allowed = SequenceParser.AMBIGUOUS_AMINO_ACIDS if allow_ambiguous else SequenceParser.STANDARD_AMINO_ACIDS
    elif seq_type_lower in ("nucleotide", "dna", "rna"):
        allowed = SequenceParser.AMBIGUOUS_NUCLEOTIDES if allow_ambiguous else SequenceParser.STANDARD_NUCLEOTIDES
    else:
        return False

    return all(c in allowed for c in seq_upper)


def calculate_gc_content(sequence: str) -> float:
    """Calculates GC percentage for DNA or RNA sequence."""
    if not sequence:
        raise ValueError("Cannot calculate GC content for an empty sequence")
    seq_upper = sequence.upper()
    valid_bases = sum(1 for c in seq_upper if c in "ACGTU")
    if valid_bases == 0:
        raise ValueError(f"Sequence '{sequence}' contains no valid nucleotide residues (A, C, G, T, U)")
    gc_count = sum(1 for c in seq_upper if c in "GC")
    return float(gc_count / valid_bases * 100.0)


def reverse_complement(sequence: str, rna: bool = False) -> str:
    """Returns the reverse complement of a DNA or RNA sequence."""
    if not sequence:
        return ""
    seq_upper = sequence.upper()
    comp_map_dna = {
        "A": "T", "T": "A", "C": "G", "G": "C", "N": "N",
        "R": "Y", "Y": "R", "S": "S", "W": "W", "K": "M",
        "M": "K", "B": "V", "D": "H", "H": "D", "V": "B",
    }
    comp_map_rna = {
        "A": "U", "U": "A", "C": "G", "G": "C", "N": "N",
        "R": "Y", "Y": "R", "S": "S", "W": "W", "K": "M",
        "M": "K", "B": "V", "D": "H", "H": "D", "V": "B",
    }
    comp_map = comp_map_rna if rna else comp_map_dna

    result = []
    for c in reversed(seq_upper):
        if c not in comp_map:
            raise InvalidResidueError(f"Cannot compute complement: Invalid nucleotide residue '{c}' in sequence.")
        result.append(comp_map[c])
    return "".join(result)


def translate_dna_to_protein(
    sequence: str,
    table: int = 1,
    stop_symbol: str = "*",
    allow_partial: bool = True,
) -> str:
    """Translates a DNA/RNA sequence into an amino acid sequence using standard genetic code."""
    if table != 1:
        raise ValueError(f"Translation table {table} is not supported. Only standard table 1 is implemented.")
    if not sequence:
        return ""
    dna = sequence.upper().replace("U", "T")
    if not allow_partial and len(dna) % 3 != 0:
        raise ValueError(f"Sequence length ({len(dna)}) is not a multiple of 3 and allow_partial is False.")

    protein = []
    for i in range(0, len(dna) - len(dna) % 3, 3):
        codon = dna[i:i+3]
        aa = CODON_TABLE.get(codon, "X")
        if aa == "*":
            protein.append(stop_symbol)
        else:
            protein.append(aa)
    return "".join(protein)


def estimate_isoelectric_point(sequence: str) -> float:
    """Estimates the isoelectric point (pI) of a protein sequence using the EMBOSS algorithm."""
    if not sequence:
        raise ValueError("Cannot calculate isoelectric point for an empty sequence")
    counts = count_residues(sequence)

    def net_charge(ph: float) -> float:
        charge = 0.0
        # N-terminus
        charge += 1.0 / (1.0 + math.pow(10.0, ph - PKA_TERMINI["N_TERM"]))
        # C-terminus
        charge -= 1.0 / (1.0 + math.pow(10.0, PKA_TERMINI["C_TERM"] - ph))
        # Basic residues (+ when protonated)
        for aa, pka in [("K", PKA_SIDECHAINS["K"]), ("R", PKA_SIDECHAINS["R"]), ("H", PKA_SIDECHAINS["H"])]:
            cnt = counts.get(aa, 0)
            if cnt:
                charge += cnt / (1.0 + math.pow(10.0, ph - pka))
        # Acidic residues (- when deprotonated)
        for aa, pka in [("D", PKA_SIDECHAINS["D"]), ("E", PKA_SIDECHAINS["E"]), ("C", PKA_SIDECHAINS["C"]), ("Y", PKA_SIDECHAINS["Y"])]:
            cnt = counts.get(aa, 0)
            if cnt:
                charge -= cnt / (1.0 + math.pow(10.0, pka - ph))
        return charge

    # Bisection search
    low, high = 0.0, 14.0
    for _ in range(100):
        mid = (low + high) / 2.0
        c = net_charge(mid)
        if abs(c) < 1e-5 or (high - low) < 1e-4:
            return round(mid, 4)
        if c > 0:
            low = mid
        else:
            high = mid
    return round((low + high) / 2.0, 4)


def calculate_sequence_molecular_weight(
    sequence: str, sequence_type: str = "protein"
) -> float:
    """Calculates molecular weight in Daltons."""
    if not sequence:
        raise ValueError("Cannot calculate molecular weight for an empty sequence")
    seq_upper = sequence.upper()
    seq_type = sequence_type.lower()

    if seq_type == "protein":
        total_mw = sum(AMINO_ACID_MW.get(aa, 110.0) for aa in seq_upper)
        # Add water molecule mass for termini (18.01528 Da)
        return total_mw + 18.01528
    elif seq_type == "dna":
        total_mw = sum(DNA_NUC_MW.get(base, 308.0) for base in seq_upper)
        return total_mw + 61.96  # 5' triphosphate / 3' OH adjustment
    elif seq_type == "rna":
        total_mw = sum(RNA_NUC_MW.get(base, 320.0) for base in seq_upper)
        return total_mw + 61.96
    else:
        raise ValueError(f"Invalid sequence_type '{sequence_type}'. Expected 'protein', 'dna', or 'rna'.")


class SequenceRecord(BaseModel):
    """Pydantic v2 data model representing an annotated biological sequence."""

    id: str
    description: Optional[str] = None
    sequence: str
    sequence_type: str = "protein"

    model_config = {"arbitrary_types_allowed": True}

    @property
    def length(self) -> int:
        return len(self.sequence)

    @property
    def residue_counts(self) -> Dict[str, int]:
        return count_residues(self.sequence)

    @property
    def molecular_weight(self) -> float:
        return calculate_sequence_molecular_weight(self.sequence, self.sequence_type)

    @property
    def isoelectric_point(self) -> float:
        if self.sequence_type.lower() != "protein":
            raise ValueError(f"Isoelectric point is only applicable to protein sequences, not '{self.sequence_type}'.")
        return estimate_isoelectric_point(self.sequence)

    @property
    def gc_content(self) -> float:
        if self.sequence_type.lower() not in ("dna", "rna", "nucleotide"):
            raise ValueError(f"GC content is not applicable to '{self.sequence_type}' sequences.")
        return calculate_gc_content(self.sequence)

    def reverse_complement(self) -> SequenceRecord:
        if self.sequence_type.lower() not in ("dna", "rna", "nucleotide"):
            raise ValueError("Cannot reverse complement a protein sequence.")
        rc_seq = reverse_complement(self.sequence, rna=(self.sequence_type.lower() == "rna"))
        return SequenceRecord(
            id=f"{self.id}_rc",
            description=f"{self.description or self.id} [reverse complement]",
            sequence=rc_seq,
            sequence_type=self.sequence_type,
        )

    def translate(self, table: int = 1, stop_symbol: str = "*") -> SequenceRecord:
        if self.sequence_type.lower() not in ("dna", "rna", "nucleotide"):
            raise ValueError("Cannot translate a protein sequence.")
        prot_seq = translate_dna_to_protein(self.sequence, table=table, stop_symbol=stop_symbol)
        return SequenceRecord(
            id=f"{self.id}_trans",
            description=f"{self.description or self.id} [translated]",
            sequence=prot_seq,
            sequence_type="protein",
        )

    def to_fasta(self, line_length: int = 60) -> str:
        header = f">{self.description or self.id}"
        if line_length <= 0:
            return f"{header}\n{self.sequence}\n"
        wrapped_lines = [self.sequence[i:i+line_length] for i in range(0, len(self.sequence), line_length)]
        return f"{header}\n" + "\n".join(wrapped_lines) + "\n"


class SequenceParser:
    """Parses biological sequences from FASTA format and validates sequence boundaries and residues.

    Enforces EuropePMCFASTA-006 compliance.
    """

    STANDARD_AMINO_ACIDS: Set[str] = set("ACDEFGHIKLMNPQRSTVWY")
    AMBIGUOUS_AMINO_ACIDS: Set[str] = set("ACDEFGHIKLMNPQRSTVWYBZXJOU")
    STANDARD_NUCLEOTIDES: Set[str] = set("ACGTU")
    AMBIGUOUS_NUCLEOTIDES: Set[str] = set("ACGTUNRYWSKMBDHV")

    def __init__(self, sequence_type: str = "protein", allow_ambiguous: bool = False) -> None:
        if sequence_type not in ["protein", "nucleotide", "dna", "rna"]:
            raise ValueError("sequence_type must be 'protein' or 'nucleotide'")
        self.sequence_type: str = sequence_type
        self.allow_ambiguous: bool = allow_ambiguous

        if sequence_type == "protein":
            self.valid_residues: Set[str] = self.AMBIGUOUS_AMINO_ACIDS if allow_ambiguous else self.STANDARD_AMINO_ACIDS
        else:
            self.valid_residues = self.AMBIGUOUS_NUCLEOTIDES if allow_ambiguous else self.STANDARD_NUCLEOTIDES

    def parse_fasta(self, fasta_content: str) -> Dict[str, str]:
        if not fasta_content or not fasta_content.strip():
            raise EmptySequenceError("Empty FASTA content or no valid sequences found.")

        sequences: Dict[str, str] = {}
        current_header: Optional[str] = None
        current_sequence: List[str] = []

        for line_num, line in enumerate(fasta_content.splitlines(), 1):
            line_str = line.strip()
            if not line_str:
                continue

            if line_str.startswith(">"):
                if current_header is not None:
                    seq_str = "".join(current_sequence)
                    self._validate_sequence(seq_str, current_header)
                    sequences[current_header] = seq_str

                current_header = line_str[1:].strip()
                current_sequence = []
            else:
                if current_header is None:
                    raise InvalidFastaFormatError(
                        f"Invalid FASTA format: Sequence data found before header at line {line_num}"
                    )
                current_sequence.append(line_str.upper())

        if current_header is not None:
            seq_str = "".join(current_sequence)
            self._validate_sequence(seq_str, current_header)
            sequences[current_header] = seq_str

        if not sequences:
            raise EmptySequenceError("Empty FASTA content or no valid sequences found.")

        return sequences

    def parse_fasta_records(self, fasta_content: str) -> List[SequenceRecord]:
        seq_dict = self.parse_fasta(fasta_content)
        records = []
        for header, seq in seq_dict.items():
            record_id = header.split()[0]
            records.append(
                SequenceRecord(
                    id=record_id,
                    description=header,
                    sequence=seq,
                    sequence_type=self.sequence_type,
                )
            )
        return records

    def _validate_sequence(self, sequence: str, header: str) -> None:
        if not sequence:
            raise SequenceBoundaryError(
                f"Sequence boundary validation failed: Sequence for '{header}' is empty."
            )

        for idx, char in enumerate(sequence):
            if char not in self.valid_residues:
                raise InvalidResidueError(
                    f"Non-standard residue checking failed: Invalid residue '{char}' found at position {idx} in sequence '{header}'."
                )


def parse_fasta(
    fasta_content: str, sequence_type: str = "protein", allow_ambiguous: bool = False
) -> Dict[str, str]:
    """Functional helper to parse FASTA string into a dictionary."""
    parser = SequenceParser(sequence_type=sequence_type, allow_ambiguous=allow_ambiguous)
    return parser.parse_fasta(fasta_content)


def parse_fasta_records(
    fasta_content: str, sequence_type: str = "protein", allow_ambiguous: bool = False
) -> List[SequenceRecord]:
    """Functional helper to parse FASTA string into a list of SequenceRecords."""
    parser = SequenceParser(sequence_type=sequence_type, allow_ambiguous=allow_ambiguous)
    return parser.parse_fasta_records(fasta_content)


def parse_fasta_file(
    filepath: Union[str, Path], sequence_type: str = "protein", allow_ambiguous: bool = False
) -> List[SequenceRecord]:
    """Reads a FASTA file and returns SequenceRecords."""
    p = Path(filepath).resolve()
    content = p.read_text(encoding="utf-8")
    return parse_fasta_records(content, sequence_type=sequence_type, allow_ambiguous=allow_ambiguous)


def format_fasta(
    records: Union[SequenceRecord, Sequence[SequenceRecord], Dict[str, str]],
    line_length: int = 60,
) -> str:
    """Formats SequenceRecord, list of records, or header->sequence dict into FASTA string."""
    if isinstance(records, SequenceRecord):
        return records.to_fasta(line_length=line_length)
    if isinstance(records, dict):
        out = []
        for header, seq in records.items():
            rec = SequenceRecord(id=header.split()[0], description=header, sequence=seq)
            out.append(rec.to_fasta(line_length=line_length))
        return "".join(out)
    if isinstance(records, (list, tuple)):
        out = [r.to_fasta(line_length=line_length) for r in records]
        return "".join(out)
    raise TypeError(f"Unsupported records type '{type(records)}'. Expected SequenceRecord, list, or dict.")


def write_fasta(
    records: Union[SequenceRecord, Sequence[SequenceRecord], Dict[str, str]],
    filepath: Union[str, Path],
    line_length: int = 60,
) -> None:
    """Writes formatted FASTA records to a file with strict Unix LF line endings."""
    p = Path(filepath).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    content = format_fasta(records, line_length=line_length)
    p.write_bytes(content.replace("\r\n", "\n").encode("utf-8"))


__all__ = [
    "EmptySequenceError",
    "InvalidFastaFormatError",
    "InvalidResidueError",
    "SequenceBoundaryError",
    "SequenceParser",
    "SequenceParsingError",
    "SequenceRecord",
    "calculate_gc_content",
    "calculate_sequence_molecular_weight",
    "count_residues",
    "estimate_isoelectric_point",
    "format_fasta",
    "parse_fasta",
    "parse_fasta_file",
    "parse_fasta_records",
    "reverse_complement",
    "translate_dna_to_protein",
    "validate_sequence_residues",
    "write_fasta",
]
