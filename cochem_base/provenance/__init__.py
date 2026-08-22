"""CoChem-BASE Cryptographic Provenance, Hashing, and Automated Citations Engine.

Provides immutable execution state tracking, physical environment hashing,
topological source code integrity locks, and automated publication-ready
BibTeX citations for computational engines and quantum chemical methodologies.
"""

from __future__ import annotations

from typing import List

from .citations import (
    CitationEntry,
    CitationTracker,
    EngineCitation,
    clear_tracked_citations,
    export_citations_bibtex,
    export_summary_markdown,
    generate_bibtex_string,
    get_bibtex_catalog,
    get_citation_entries,
    get_global_citation_tracker,
    lookup_bibtex,
    parse_and_validate_bibtex,
    track_engine,
    track_engines,
    track_method,
    write_citations_bib,
)
from .hashing import (
    EnvironmentHashRecord,
    SourceIntegrityError,
    TopologicalLockRecord,
    assert_topological_lock,
    compute_file_sha256,
    compute_repository_source_hash,
    generate_topological_source_lock,
    hash_environment,
    verify_source_code_integrity,
)

__all__: List[str] = [
    # Citations
    "CitationEntry",
    "EngineCitation",
    "CitationTracker",
    "get_global_citation_tracker",
    "track_engine",
    "track_engines",
    "track_method",
    "lookup_bibtex",
    "get_bibtex_catalog",
    "get_citation_entries",
    "generate_bibtex_string",
    "write_citations_bib",
    "export_citations_bibtex",
    "export_summary_markdown",
    "parse_and_validate_bibtex",
    "clear_tracked_citations",
    # Hashing
    "EnvironmentHashRecord",
    "TopologicalLockRecord",
    "SourceIntegrityError",
    "compute_file_sha256",
    "hash_environment",
    "compute_repository_source_hash",
    "generate_topological_source_lock",
    "verify_source_code_integrity",
    "assert_topological_lock",
]
