"""CoChem-BASE Cryptographic Provenance, Hashing, and Automated Citations Engine."""
from __future__ import annotations

from typing import Any

from cochem_base.provenance.citations import (
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

_HASHING_EXPORTS = frozenset({
    "EnvironmentHashRecord",
    "SourceIntegrityError",
    "TopologicalLockRecord",
    "assert_topological_lock",
    "compute_file_sha256",
    "compute_repository_source_hash",
    "generate_topological_source_lock",
    "hash_environment",
    "verify_source_code_integrity",
})


def __getattr__(name: str) -> Any:
    if name in _HASHING_EXPORTS:
        from cochem_base.provenance import hashing

        return getattr(hashing, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))


__all__ = [
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
