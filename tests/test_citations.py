import sys
from pathlib import Path

# Ensure repository root is in sys.path for direct import resilience across all execution environments
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cochem_base.provenance.citations import (
    CitationTracker,
    get_bibtex_catalog,
)


def test_core_engine_citations_present() -> None:
    catalog = get_bibtex_catalog()
    assert "orca" in catalog
    assert "cfour" in catalog
    assert "crest" in catalog
    assert "xtb" in catalog
    assert "pyscf" in catalog
    assert "gpu4pyscf" in catalog
    assert "psi4" in catalog
    assert "mace_off23" in catalog
    assert "aimnet2" in catalog
    assert "r2scan_3c" in catalog
    assert "wb97m_v" in catalog
    assert "dlpno_ccsd_t" in catalog


def test_deduplicated_file_write(tmp_path: Path) -> None:
    tracker = CitationTracker(default_output_dir=tmp_path)
    tracker.register_engine("orca")
    tracker.register_engine("orca")
    tracker.register_engine("crest")

    bib_path = tracker.write_bibtex_file()
    assert bib_path.exists()
    content = bib_path.read_text(encoding="utf-8")
    assert content.count("@article{Neese2022ORCA") == 1
    assert content.count("@article{Pracht2020CREST") == 1
