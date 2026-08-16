class SequenceParser:
    """
    Parses biological sequences from FASTA format and validates sequence boundaries and residues.
    Enforces EuropePMCFASTA-006 compliance.
    """
    
    STANDARD_AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWY")
    STANDARD_NUCLEOTIDES = set("ACGTU")
    
    def __init__(self, sequence_type: str = "protein"):
        """
        sequence_type: 'protein' or 'nucleotide'
        """
        if sequence_type not in ["protein", "nucleotide"]:
            raise ValueError("sequence_type must be 'protein' or 'nucleotide'")
        self.sequence_type = sequence_type
        self.valid_residues = self.STANDARD_AMINO_ACIDS if sequence_type == "protein" else self.STANDARD_NUCLEOTIDES

    def parse_fasta(self, fasta_content: str) -> dict:
        """
        Parses a FASTA string into a dictionary mapping headers to sequences.
        Authentically validates non-standard residues and sequence boundaries.
        """
        sequences = {}
        current_header = None
        current_sequence = []
        
        for line_num, line in enumerate(fasta_content.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
                
            if line.startswith(">"):
                if current_header is not None:
                    # Finalize previous sequence
                    seq_str = "".join(current_sequence)
                    self._validate_sequence(seq_str, current_header)
                    sequences[current_header] = seq_str
                    
                current_header = line[1:].strip()
                current_sequence = []
            else:
                if current_header is None:
                    raise ValueError(f"Invalid FASTA format: Sequence data found before header at line {line_num}")
                current_sequence.append(line.upper())
                
        # Finalize last sequence
        if current_header is not None:
            seq_str = "".join(current_sequence)
            self._validate_sequence(seq_str, current_header)
            sequences[current_header] = seq_str
            
        if not sequences:
            raise ValueError("Empty FASTA content or no valid sequences found.")
            
        return sequences

    def _validate_sequence(self, sequence: str, header: str):
        if not sequence:
            raise ValueError(f"Sequence boundary validation failed: Sequence for '{header}' is empty.")
            
        for idx, char in enumerate(sequence):
            if char not in self.valid_residues:
                raise ValueError(f"Non-standard residue checking failed: Invalid residue '{char}' found at position {idx} in sequence '{header}'.")
