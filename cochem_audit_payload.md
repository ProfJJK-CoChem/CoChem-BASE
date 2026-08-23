Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-SpycFit\.in-progress\Task1_Prompt4_ci_workflow.md.
Original prompt:
# Task 1: Master Repository Map & Tripartite Topology - cochem_spycfit_ci.yml

**Objective:**
Create the `.github/workflows/cochem_spycfit_ci.yml` CI/CD file for the CoChem-SpycFit repository to physically enforce the Tripartite Air-Gap.

**Target File:**
`D:\__CoChem\GitHub-Repo\CoChem-SpycFit\.github\workflows\cochem_spycfit_ci.yml`

**Instructions:**
You are the `cochem-coder` agent. Implement the GitHub Actions workflow file. It MUST contain a mandatory step that fails the build if the Tripartite Air-Gap is breached, intentionally skipping the whitelisted test fixtures. No placeholders, mocks, or synthetic bypasses are allowed.

**Proposed Code Snippet:**
```yaml
name: CoChem-SpycFit CI
on: [push, pull_request]

jobs:
  air_gap_enforcement:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Tripartite Air-Gap Enforcement Scan
        run: |
          echo "Scanning for Tier 2/Tier 3 artifacts outside tests/ directory..."
          matches=$(find . -type d -name "test_fixtures" -prune -o \( -name "*.h5" -o -name "*.parquet" -o -name "*.fit" -o -name "*.lin" -o -name "*.lock" \) -print)
          if [ ! -z "$matches" ]; then
            echo "CRITICAL: Tripartite Air-Gap Breach. State (Tier 3) or Data (Tier 2) artifacts detected in the Immutable Execution Tier (Tier 1)."
            echo "$matches"
            exit 1
          fi
          echo "Air-Gap intact."
```

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_base\interfaces\cochem_vibspyc_snap.py ---
"""SpycFit Snapshot & Publication Export Interface.

Phase 4 / Task 10 Implementation:
- Authoritative fit provenance payload modeling and validation.
- Iterative cryptographic dataset hashing (SHA-256).
- Publication-ready AASTeX and LaTeX longtable rendering with siunitx and booktabs.
- Dynamic CrossRef JSON parsing to clean, deduplicated BibTeX entries.
- Active model to standard DOI resolution.
- Adaptive storage compression strategy evaluation (ZIP vs ZSTD).
- Archive creation (.zip and .tar.zst) and cross-platform read-only sealing.
"""

from __future__ import annotations

import datetime
import hashlib
import io
import json
import logging
import os
import stat
import tarfile
import zipfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import jinja2
from pydantic import BaseModel, Field, field_validator
import zstandard

logger = logging.getLogger(__name__)

# Standard model to DOI mappings across computational spectroscopy and quantum chemistry
_MODEL_DOI_MAP: dict[str, str] = {
    "watson_a_reduction": "10.1016/0022-2852(77)90184-7",
    "watson_a": "10.1016/0022-2852(77)90184-7",
    "watson_s_reduction": "10.1016/0022-2852(77)90184-7",
    "watson_s": "10.1016/0022-2852(77)90184-7",
    "iam_internal_rotation": "10.1016/0022-2852(66)90258-0",
    "iam": "10.1016/0022-2852(66)90258-0",
    "internal_axis_method": "10.1016/0022-2852(66)90258-0",
    "erham": "10.1006/jmsp.1997.7432",
    "erham_internal_rotation": "10.1006/jmsp.1997.7432",
    "jax_backend": "10.5281/zenodo.4766323",
    "jax": "10.5281/zenodo.4766323",
    "pyarrow_engine": "10.5281/zenodo.4006056",
    "pyarrow": "10.5281/zenodo.4006056",
    "arrow": "10.5281/zenodo.4006056",
    "spcat": "10.1016/0022-2852(91)90393-O",
    "spcat_bridge": "10.1016/0022-2852(91)90393-O",
    "pickett": "10.1016/0022-2852(91)90393-O",
    "orca": "10.1002/wcms.1606",
    "orca_v6": "10.1063/5.0004608",
    "cfour": "10.1063/5.0004837",
    "crest": "10.1039/C9CP06869D",
    "crest_metadynamics": "10.1021/acs.jctc.9b00143",
    "xtb": "10.1002/wcms.1493",
    "gfn2_xtb": "10.1021/acs.jctc.8b01176",
    "gfn1_xtb": "10.1021/acs.jctc.7b00118",
    "gfn_ff": "10.1002/anie.202004239",
    "pyscf": "10.1002/wcms.1340",
    "gpu4pyscf": "10.1063/5.0223707",
    "psi4": "10.1063/5.0006002",
    "molpro": "10.1063/5.0005081",
    "mace": "10.1021/jacs.4c07099",
    "mace_off23": "10.1021/jacs.4c07099",
    "aimnet2": "10.1021/acs.jcim.4c00445",
    "abcluster": "10.1039/C5CP04060D",
    "r2scan_3c": "10.1063/5.0040021",
    "b97_3c": "10.1063/1.5012601",
    "wb97m_v": "10.1063/1.4952647",
    "wb97x_v": "10.1039/C4CP00288E",
    "dlpno_ccsd_t": "10.1063/1.4773581",
    "dft_d3": "10.1063/1.3382344",
    "dft_d4": "10.1063/1.5090222",
    "sapt": "10.1021/cr00031a008",
    "qcxms": "10.1021/acsomega.1c00994",
    "ase": "10.1088/1361-648X/aa680e",
    "parsl": "10.1145/3307681.3325400",
    "rdkit": "10.5281/zenodo.10549474",
}


def get_spycfit_processed_dir() -> Path:
    """Resolves the default SpycFit processed output directory.

    Checks $COCHEM_STATE_DIR first; falls back to Path.home().
    """
    env_state = os.environ.get("COCHEM_STATE_DIR")
    if env_state:
        base_path = Path(env_state).expanduser().resolve()
    else:
        base_path = (Path.home() / ".cochem").resolve()
    return base_path / "SpycFit_Workspace" / "Processed"


def resolve_processed_workspace_dir(custom_dir: str | Path | None = None) -> Path:
    """Resolves and returns the canonical processed directory, accepting an optional custom path."""
    if custom_dir is not None:
        target = Path(custom_dir).expanduser().resolve()
    else:
        target = get_spycfit_processed_dir()
    return target


class FitProvenancePayload(BaseModel):
    """Pydantic model representing complete scientific provenance for a SpycFit spectroscopic session."""

    session_id: str = Field(..., description="Unique identifier of the spectroscopic fitting session")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp of the fitting completion")
    dataset_hashes: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of filename or dataset identifier to its SHA-256 cryptographic digest",
    )
    chi_squared: float = Field(..., description="Final reduced or unweighted chi-squared metric of the fit")
    huber_loss_delta: float | None = Field(default=None, description="Huber robust loss delta threshold if active")
    rms_mhz: float = Field(..., description="Root-mean-square error in Megahertz (MHz)")
    rms_cm_inv: float = Field(..., description="Root-mean-square error in wavenumbers (cm^-1)")
    jacobian_condition_number: float = Field(..., description="Condition number of the final Jacobian matrix")
    sobol_parameter_audit: dict[str, bool] = Field(
        default_factory=dict,
        description="Sobol sensitivity audit mapping parameter names to boolean active fit status",
    )
    semantic_git_history: list[str] = Field(
        default_factory=list,
        description="Relevant semantic Git commits capturing pipeline state",
    )
    active_models: list[str] = Field(
        default_factory=list,
        description="List of active physical models, Hamiltonians, and compute engines utilized",
    )
    additional_metadata: dict[str, Any] | None = Field(
        default=None,
        description="Optional extended metadata including instrument parameters and experimental conditions",
    )

    @field_validator("timestamp")
    @classmethod
    def validate_iso_timestamp(cls, v: str) -> str:
        """Ensures the timestamp is a strictly valid ISO-8601 string."""
        normalized = v.replace("Z", "+00:00")
        try:
            datetime.datetime.fromisoformat(normalized)
        except ValueError as err:
            raise ValueError(f"Timestamp '{v}' is not a valid ISO 8601 string: {err}") from err
        return v

    @field_validator("chi_squared", "rms_mhz", "rms_cm_inv", "jacobian_condition_number")
    @classmethod
    def validate_non_negative_floats(cls, v: float) -> float:
        """Ensures physical error metrics and condition numbers are non-negative."""
        if v < 0.0:
            raise ValueError(f"Metric must be non-negative, received {v}")
        return v

    def to_json_file(self, file_path: str | Path) -> Path:
        """Serializes the payload to a JSON file on physical disk."""
        target_path = Path(file_path).expanduser().resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        content = self.model_dump_json(indent=2)
        target_path.write_text(content, encoding="utf-8")
        return target_path

    @classmethod
    def from_json_file(cls, file_path: str | Path) -> FitProvenancePayload:
        """Deserializes a FitProvenancePayload from a JSON file on physical disk."""
        target_path = Path(file_path).expanduser().resolve()
        if not target_path.exists():
            raise FileNotFoundError(f"Provenance file not found at '{target_path}'")
        raw_text = target_path.read_text(encoding="utf-8")
        return cls.model_validate_json(raw_text)


def hash_dataset_iteratively(file_path: str | Path, chunk_size: int = 65536) -> str:
    """Computes the SHA-256 cryptographic digest of a file iteratively.

    Uses hashlib.file_digest if available in the standard library; falls back to chunked reading.
    """
    target = Path(file_path).expanduser().resolve()
    if not target.is_file():
        raise FileNotFoundError(f"Dataset file not found: '{target}'")

    if hasattr(hashlib, "file_digest"):
        with open(target, "rb") as f:
            return hashlib.file_digest(f, "sha256").hexdigest()

    hasher = hashlib.sha256()
    with open(target, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


_AASTEX_PARAMETERS_TEMPLATE = """\\begin{table}[htbp]
\\centering
\\caption{Optimized Spectroscopic Parameters for {{ title_prefix }}}
\\label{tab:optimized_params}
\\begin{tabular}{l c S[table-format=6.4] l l}
\\toprule
Parameter & LaTeX Symbol & {Value (MHz)} & Uncertainty & Description \\\\
\\midrule
{% for p in parameters %}
{{ p.name }} & ${{ p.latex_name }}$ & {{ p.formatted_value }} & {{ p.formatted_uncertainty }} & {{ p.description }} \\\\
{% endfor %}
\\bottomrule
\\end{tabular}
\\end{table}"""

_AASTEX_TRANSITIONS_TEMPLATE = """\\begin{longtable}{c c S[table-format=6.4] S[table-format=6.4] S[table-format=3.4] S[table-format=2.4] S[table-format=3.2]}
\\caption{Observed and Calculated Transitions for {{ title_prefix }} (Truncated to Top {{ transitions|length }})} \\label{tab:transitions} \\\\
\\toprule
Upper ($J'_{K_a' K_c'}$) & Lower ($J''_{K_a'' K_c''}$) & {$\\nu_{\\text{obs}}$ (MHz)} & {$\\nu_{\\text{calc}}$ (MHz)} & {Residual (MHz)} & {$\\sigma$ (MHz)} & {Intensity} \\\\
\\midrule
\\endfirsthead
\\toprule
Upper ($J'_{K_a' K_c'}$) & Lower ($J''_{K_a'' K_c''}$) & {$\\nu_{\\text{obs}}$ (MHz)} & {$\\nu_{\\text{calc}}$ (MHz)} & {Residual (MHz)} & {$\\sigma$ (MHz)} & {Intensity} \\\\
\\midrule
\\endhead
\\bottomrule
\\endfoot
\\bottomrule
\\endlastfoot
{% for t in transitions %}
{{ t.upper_state }} & {{ t.lower_state }} & {{ t.formatted_obs }} & {{ t.formatted_calc }} & {{ t.formatted_res }} & {{ t.formatted_unc }} & {{ t.formatted_int }} \\\\
{% endfor %}
\\end{longtable}"""

_AASTEX_COMBINED_TEMPLATE = """\\documentclass[twocolumn]{aastex631}
\\usepackage{amsmath}
\\usepackage{booktabs}
\\usepackage{longtable}
\\usepackage{siunitx}

\\shorttitle{Spectroscopic Fit: {{ title_prefix }}}
\\shortauthors{CoChem Ecosystem}

\\begin{document}

\\title{High-Precision Rotational Spectroscopic Fit and Transition Assignments: {{ title_prefix }}}

\\begin{abstract}
We present the high-precision spectroscopic fit, molecular parameters, and assigned rotational-vibrational transitions generated by the CoChem-SpycFit autonomous analysis engine.
\\end{abstract}

\\section{Molecular Parameters}
{{ parameters_table }}

\\section{Assigned Transitions}
{{ transitions_table }}

\\end{document}
"""


def generate_aastex_longtables(
    optimized_params: Sequence[dict[str, Any]],
    transitions: Sequence[dict[str, Any]],
    title_prefix: str = "CoChem-SpycFit",
) -> dict[str, str]:
    """Renders in-memory publication-ready AASTeX and LaTeX longtables with siunitx and booktabs.

    Parameters:
        optimized_params: List of parameter dictionaries.
        transitions: List of transition records. Truncated to top 200 by intensity/Einstein A.
        title_prefix: Title header for captions and document metadata.

    Returns:
        Dictionary containing {"parameters_table": str, "transitions_table": str, "combined_document": str}.
    """
    processed_params: list[dict[str, Any]] = []
    for param in optimized_params:
        name = str(param.get("name", "Param"))
        latex_name = str(param.get("latex_name", name))
        val = param.get("value", 0.0)
        formatted_val = f"{float(val):.6f}" if isinstance(val, (int, float)) else str(val)

        is_frozen = param.get("is_frozen", False)
        sobol_active = param.get("sobol_audit", True)
        unc = param.get("uncertainty")
        status = str(param.get("status", "")).lower()

        if is_frozen or (unc is None) or (not sobol_active) or status in ["fixed", "set", "frozen"]:
            formatted_unc = "Fixed"
        else:
            try:
                formatted_unc = f"{float(unc):.6f}"
            except (ValueError, TypeError):
                formatted_unc = str(unc)

        description = str(param.get("description", f"Parameter {name}"))
        processed_params.append(
            {
                "name": name,
                "latex_name": latex_name,
                "formatted_value": formatted_val,
                "formatted_uncertainty": formatted_unc,
                "description": description,
            }
        )

    # Sort transitions descending by intensity or Einstein A and truncate to top 200
    sorted_transitions = sorted(
        transitions,
        key=lambda item: float(
            item.get("intensity", item.get("einstein_a", item.get("a_coeff", item.get("int", 0.0)))) or 0.0
        ),
        reverse=True,
    )[:200]

    processed_trans: list[dict[str, Any]] = []
    for t in sorted_transitions:
        upper = str(t.get("upper_state", "Upper"))
        lower = str(t.get("lower_state", "Lower"))
        obs = t.get("observed_mhz", t.get("obs_mhz", 0.0))
        calc = t.get("calculated_mhz", t.get("calc_mhz", 0.0))
        res = t.get("residual_mhz", t.get("res_mhz", float(obs) - float(calc)))
        unc = t.get("uncertainty_mhz", t.get("unc_mhz", 0.01))
        intensity = t.get("intensity", t.get("einstein_a", 1.0))

        processed_trans.append(
            {
                "upper_state": upper,
                "lower_state": lower,
                "formatted_obs": f"{float(obs):.4f}",
                "formatted_calc": f"{float(calc):.4f}",
                "formatted_res": f"{float(res):.4f}",
                "formatted_unc": f"{float(unc):.4f}",
                "formatted_int": f"{float(intensity):.2f}",
            }
        )

    param_tmpl = jinja2.Template(_AASTEX_PARAMETERS_TEMPLATE)
    trans_tmpl = jinja2.Template(_AASTEX_TRANSITIONS_TEMPLATE)
    doc_tmpl = jinja2.Template(_AASTEX_COMBINED_TEMPLATE)

    rendered_params = param_tmpl.render(parameters=processed_params, title_prefix=title_prefix)
    rendered_trans = trans_tmpl.render(transitions=processed_trans, title_prefix=title_prefix)
    rendered_doc = doc_tmpl.render(
        title_prefix=title_prefix,
        parameters_table=rendered_params,
        transitions_table=rendered_trans,
    )

    return {
        "parameters_table": rendered_params,
        "transitions_table": rendered_trans,
        "combined_document": rendered_doc,
    }


def get_required_dois(active_models: Sequence[str]) -> list[str]:
    """Resolves standard DOIs for all specified active physical models and quantum engines.

    Preserves unique entries without duplicates.
    """
    resolved_dois: list[str] = []
    seen: set[str] = set()

    for model_name in active_models:
        normalized_key = model_name.strip().lower().replace(" ", "_").replace("-", "_")
        doi = _MODEL_DOI_MAP.get(normalized_key)
        if doi and doi not in seen:
            seen.add(doi)
            resolved_dois.append(doi)

    return resolved_dois


def format_citations_to_bib(crossref_json_responses: Sequence[dict[str, Any]]) -> str:
    """Parses CrossRef JSON records into clean, validated, deduplicated BibTeX entries."""
    bib_entries: list[str] = []
    seen_dois: set[str] = set()
    seen_keys: set[str] = set()

    for record in crossref_json_responses:
        # CrossRef response might wrap work in a 'message' field
        work = record.get("message", record)

        doi_raw = work.get("DOI") or work.get("doi")
        if not doi_raw:
            continue
        doi_clean = str(doi_raw).strip()
        if doi_clean.lower() in seen_dois:
            continue
        seen_dois.add(doi_clean.lower())

        # Title
        title_val = work.get("title", "")
        if isinstance(title_val, list) and title_val:
            title = str(title_val[0]).strip()
        else:
            title = str(title_val).strip()

        # Authors
        authors_raw = work.get("author", [])
        author_names: list[str] = []
        first_author_family = "Author"
        if isinstance(authors_raw, list):
            for idx, a in enumerate(authors_raw):
                if isinstance(a, dict):
                    family = a.get("family", a.get("name", ""))
                    given = a.get("given", "")
                    if idx == 0 and family:
                        first_author_family = "".join(filter(str.isalnum, str(family)))
                    if family and given:
                        author_names.append(f"{family}, {given}")
                    elif family:
                        author_names.append(str(family))
                elif isinstance(a, str):
                    if idx == 0:
                        first_author_family = "".join(filter(str.isalnum, a.split()[-1]))
                    author_names.append(a)
        author_str = " and ".join(author_names) if author_names else "CoChem Spectroscopy Consortium"

        # Journal / Container Title
        journal_raw = work.get("container-title") or work.get("container_title") or work.get("journal", "")
        if isinstance(journal_raw, list) and journal_raw:
            journal = str(journal_raw[0]).strip()
        else:
            journal = str(journal_raw).strip()

        # Volume, Issue, Pages
        volume = str(work.get("volume", "")).strip()
        number = str(work.get("issue", work.get("number", ""))).strip()
        pages = str(work.get("page", work.get("pages", ""))).strip()

        # Year
        year_str = "2026"
        issued = work.get("issued") or work.get("published-print") or work.get("published-online")
        if isinstance(issued, dict):
            date_parts = issued.get("date-parts", [])
            if date_parts and isinstance(date_parts[0], list) and date_parts[0]:
                year_str = str(date_parts[0][0])
        elif "year" in work:
            year_str = str(work["year"])

        # Entry Key Generation
        first_title_word = "".join(filter(str.isalnum, (title.split()[0] if title else "Work")))
        base_key = f"{first_author_family}{year_str}{first_title_word}"
        key = base_key
        counter = 1
        while key in seen_keys:
            key = f"{base_key}_{counter}"
            counter += 1
        seen_keys.add(key)

        entry_lines = [f"@article{{{key},"]
        entry_lines.append(f"  author = {{{author_str}}},")
        if title:
            entry_lines.append(f"  title = {{{{{title}}}}},")
        if journal:
            entry_lines.append(f"  journal = {{{journal}}},")
        if volume:
            entry_lines.append(f"  volume = {{{volume}}},")
        if number:
            entry_lines.append(f"  number = {{{number}}},")
        if pages:
            entry_lines.append(f"  pages = {{{pages}}},")
        entry_lines.append(f"  year = {{{year_str}}},")
        entry_lines.append(f"  doi = {{{doi_clean}}}")
        entry_lines.append("}")

        bib_entries.append("\n".join(entry_lines))

    return "\n\n".join(bib_entries)


def evaluate_compression_strategy(total_size_bytes: int, threshold_bytes: int = 104857600) -> str:
    """Evaluates whether to package artifacts as standard ZIP or high-ratio Zstandard tarball.

    Threshold defaults to 100 MiB (104,857,600 bytes).
    """
    if total_size_bytes >= threshold_bytes:
        return "ZSTD"
    return "ZIP"


def package_fit_artifacts(
    source_dir: str | Path,
    output_archive_base: str | Path,
    strategy: str | None = None,
) -> Path:
    """Bundles all directory artifacts into a consolidated ZIP or TAR.ZST archive.

    If strategy is None, evaluates compression strategy automatically based on file volume.
    """
    src = Path(source_dir).expanduser().resolve()
    if not src.is_dir():
        raise NotADirectoryError(f"Source directory not found: '{src}'")

    total_bytes = sum(f.stat().st_size for f in src.rglob("*") if f.is_file())

    if strategy is None:
        chosen_strategy = evaluate_compression_strategy(total_bytes)
    else:
        chosen_strategy = strategy.upper().strip()

    base_str = str(Path(output_archive_base).expanduser().resolve())

    if chosen_strategy in ["ZIP", ".ZIP"]:
        archive_path = Path(base_str if base_str.endswith(".zip") else f"{base_str}.zip")
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for item in sorted(src.rglob("*")):
                if item.is_file():
                    arcname = str(item.relative_to(src)).replace("\\", "/")
                    zf.write(item, arcname=arcname)
        return archive_path

    if chosen_strategy in ["ZSTD", "TAR_ZSTD", "TAR.ZST", ".TAR.ZST", "ZST"]:
        if base_str.endswith(".tar.zst"):
            archive_path = Path(base_str)
        elif base_str.endswith(".tar"):
            archive_path = Path(f"{base_str}.zst")
        else:
            archive_path = Path(f"{base_str}.tar.zst")

        archive_path.parent.mkdir(parents=True, exist_ok=True)
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
            for item in sorted(src.rglob("*")):
                if item.is_file():
                    arcname = str(item.relative_to(src)).replace("\\", "/")
                    tar.add(str(item), arcname=arcname)
        tar_bytes = tar_buffer.getvalue()

        cctx = zstandard.ZstdCompressor(level=10)
        compressed_payload = cctx.compress(tar_bytes)
        archive_path.write_bytes(compressed_payload)
        return archive_path

    raise ValueError(f"Unsupported packaging strategy '{strategy}'")


def seal_artifact_read_only(file_path: str | Path) -> bool:
    """Sets cross-platform read-only permissions on a file to ensure non-repudiation."""
    target = Path(file_path).expanduser().resolve()
    if not target.exists():
        raise FileNotFoundError(f"Cannot seal non-existent file: '{target}'")

    current_mode = target.stat().st_mode
    readonly_mode = current_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
    os.chmod(target, readonly_mode)

    # Windows read-only attribute fallback
    if os.name == "nt":
        os.chmod(target, stat.S_IREAD)

    return True


def export_spycfit_snapshot(
    payload: FitProvenancePayload,
    source_dir: str | Path,
    output_dir: str | Path | None = None,
    active_models: Sequence[str] | None = None,
    crossref_records: Sequence[dict[str, Any]] | None = None,
    optimized_params: Sequence[dict[str, Any]] | None = None,
    transitions: Sequence[dict[str, Any]] | None = None,
    title_prefix: str = "CoChem-SpycFit",
    strategy: str | None = None,
) -> dict[str, Any]:
    """Full orchestration pipeline for generating and sealing a SpycFit snapshot export package."""
    dest_dir = resolve_processed_workspace_dir(output_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    # 1. Write Provenance JSON
    prov_file = dest_dir / "fit_provenance.json"
    payload.to_json_file(prov_file)

    # 2. Render LaTeX/AASTeX Tables
    params_to_render = list(optimized_params or [])
    trans_to_render = list(transitions or [])
    tables = generate_aastex_longtables(params_to_render, trans_to_render, title_prefix=title_prefix)

    param_tex_path = dest_dir / "parameters_table.tex"
    param_tex_path.write_text(tables["parameters_table"], encoding="utf-8")

    trans_tex_path = dest_dir / "transitions_table.tex"
    trans_tex_path.write_text(tables["transitions_table"], encoding="utf-8")

    doc_tex_path = dest_dir / "spectroscopic_document.tex"
    doc_tex_path.write_text(tables["combined_document"], encoding="utf-8")

    # 3. Generate BibTeX Citations
    models_to_cite = list(active_models or payload.active_models)
    dois = get_required_dois(models_to_cite)

    records: list[dict[str, Any]] = list(crossref_records or [])
    for d in dois:
        records.append({"DOI": d, "title": f"Attributed Spectroscopic Engine ({d})"})

    bibtex_content = format_citations_to_bib(records)
    bib_path = dest_dir / "cochem_citations.bib"
    bib_path.write_text(bibtex_content, encoding="utf-8")

    # 4. Package Artifacts
    archive_base = dest_dir.parent / f"{dest_dir.name}_archive"
    archive_path = package_fit_artifacts(dest_dir, archive_base, strategy=strategy)

    # 5. Seal Artifacts Read-Only
    for item in dest_dir.rglob("*"):
        if item.is_file():
            seal_artifact_read_only(item)
    seal_artifact_read_only(archive_path)

    return {
        "status": "SUCCESS",
        "archive_path": str(archive_path),
        "provenance_path": str(prov_file),
        "parameters_table_path": str(param_tex_path),
        "transitions_table_path": str(trans_tex_path),
        "document_path": str(doc_tex_path),
        "citations_bib_path": str(bib_path),
        "session_id": payload.session_id,
        "dois_cited": dois,
    }


__all__ = [
    "FitProvenancePayload",
    "get_spycfit_processed_dir",
    "resolve_processed_workspace_dir",
    "hash_dataset_iteratively",
    "generate_aastex_longtables",
    "get_required_dois",
    "format_citations_to_bib",
    "evaluate_compression_strategy",
    "package_fit_artifacts",
    "seal_artifact_read_only",
    "export_spycfit_snapshot",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_cochem_vibspyc_snap.py ---
"""Zero-Mock Unit and Integration Tests for SpycFit Snapshot & Publication Export.

Validates:
- Strict Zero-Mock compliance (all tests run on physical disks using tmp_path).
- Target directory resolution with state dir environment variable and platformdirs fallback.
- FitProvenancePayload schema validation, bounds checks, and JSON file roundtrips.
- Iterative SHA-256 hashing across empty, small, and multi-chunk files.
- AASTeX and LaTeX longtable generation with siunitx, booktabs, frozen parameter replacement, and top-200 truncation.
- Model-to-DOI mapping for Watson reduction, IAM, ERHAM, JAX, PyArrow, and quantum engines.
- CrossRef JSON parsing and clean BibTeX generation with deduplication.
- Dynamic compression strategy evaluation (ZIP vs ZSTD).
- Archive bundling (.zip and .tar.zst) and integrity verification.
- Cross-platform read-only artifact sealing.
- End-to-end snapshot orchestration pipeline.
- Module re-exports and interface consistency.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import stat
import tarfile
import zipfile
from pathlib import Path
from typing import Any

import pytest
import zstandard

from cochem_base.interfaces.cochem_vibspyc_snap import (
    FitProvenancePayload,
    evaluate_compression_strategy,
    export_spycfit_snapshot,
    format_citations_to_bib,
    generate_aastex_longtables,
    get_required_dois,
    get_spycfit_processed_dir,
    hash_dataset_iteratively,
    package_fit_artifacts,
    resolve_processed_workspace_dir,
    seal_artifact_read_only,
)


def test_target_directory_resolution(tmp_path: Path) -> None:
    """Verifies target directory resolution via custom path, environment variable, and fallback."""
    # 1. Custom directory argument
    custom_target = tmp_path / "custom_processed"
    resolved_custom = resolve_processed_workspace_dir(custom_target)
    assert resolved_custom == custom_target.resolve()

    # 2. Environment variable override
    env_dir = tmp_path / "cochem_state"
    original_env = os.environ.get("COCHEM_STATE_DIR")
    try:
        os.environ["COCHEM_STATE_DIR"] = str(env_dir)
        resolved_env = get_spycfit_processed_dir()
        expected_env = env_dir / "SpycFit_Workspace" / "Processed"
        assert resolved_env == expected_env.resolve()

        # 3. Fallback when environment variable is unset
        if "COCHEM_STATE_DIR" in os.environ:
            del os.environ["COCHEM_STATE_DIR"]
        resolved_fallback = get_spycfit_processed_dir()
        assert "SpycFit_Workspace" in str(resolved_fallback)
        assert str(resolved_fallback).endswith("Processed")
    finally:
        if original_env is not None:
            os.environ["COCHEM_STATE_DIR"] = original_env
        elif "COCHEM_STATE_DIR" in os.environ:
            del os.environ["COCHEM_STATE_DIR"]


def test_fit_provenance_payload_validation(tmp_path: Path) -> None:
    """Verifies schema validation, ISO timestamp verification, and disk roundtrips."""
    valid_timestamp = "2026-08-23T09:15:00+00:00"
    payload_dict: dict[str, Any] = {
        "session_id": "spycfit_session_alpha_001",
        "timestamp": valid_timestamp,
        "dataset_hashes": {
            "spectrum_raw.ftm": "a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0",
            "assignment_linelist.dat": "b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef01",
        },
        "chi_squared": 1.0428,
        "huber_loss_delta": 0.0035,
        "rms_mhz": 0.0125,
        "rms_cm_inv": 0.000417,
        "jacobian_condition_number": 42.15,
        "sobol_parameter_audit": {
            "A_rot": True,
            "B_rot": True,
            "C_rot": True,
            "DJ": True,
            "DJK": True,
            "DK": False,
            "V3_barrier": True,
        },
        "semantic_git_history": [
            "commit 9fa410b: Initialize IAM rotational hamiltonian",
            "commit 3bc289d: Converge Levenberg-Marquardt fit with Huber loss",
        ],
        "active_models": ["Watson_A_Reduction", "IAM_Internal_Rotation", "JAX_Backend"],
        "additional_metadata": {
            "temperature_kelvin": 1.5,
            "pulse_duration_us": 1.0,
        },
    }

    payload = FitProvenancePayload.model_validate(payload_dict)
    assert payload.session_id == "spycfit_session_alpha_001"
    assert payload.chi_squared == 1.0428
    assert payload.huber_loss_delta == 0.0035
    assert payload.sobol_parameter_audit["DK"] is False

    # Save to disk and re-load
    json_path = tmp_path / "fit_provenance.json"
    written_path = payload.to_json_file(json_path)
    assert written_path.exists()

    loaded_payload = FitProvenancePayload.from_json_file(json_path)
    assert loaded_payload.session_id == payload.session_id
    assert loaded_payload.dataset_hashes == payload.dataset_hashes
    assert loaded_payload.rms_mhz == payload.rms_mhz

    # Invalid timestamp test
    invalid_dict = dict(payload_dict)
    invalid_dict["timestamp"] = "not-an-iso-date"
    with pytest.raises(ValueError):
        FitProvenancePayload.model_validate(invalid_dict)

    # Negative chi squared test
    invalid_dict_chi = dict(payload_dict)
    invalid_dict_chi["chi_squared"] = -0.5
    with pytest.raises(ValueError):
        FitProvenancePayload.model_validate(invalid_dict_chi)

    # Negative rms_mhz test
    invalid_dict_rms = dict(payload_dict)
    invalid_dict_rms["rms_mhz"] = -0.01
    with pytest.raises(ValueError):
        FitProvenancePayload.model_validate(invalid_dict_rms)

    # Missing file for from_json_file
    missing_json = tmp_path / "missing_provenance.json"
    with pytest.raises(FileNotFoundError):
        FitProvenancePayload.from_json_file(missing_json)


def test_hash_dataset_iteratively(tmp_path: Path) -> None:
    """Verifies iterative SHA-256 calculation for empty, single-chunk, and multi-chunk files."""
    # 1. Multi-chunk data file
    data_content = b"CoChem Spectroscopic Linelist Data\nLine 1: 12450.32 MHz\nLine 2: 14890.11 MHz\n"
    file_path = tmp_path / "linelist.dat"
    file_path.write_bytes(data_content)

    expected_hash = hashlib.sha256(data_content).hexdigest()
    computed_hash = hash_dataset_iteratively(file_path, chunk_size=16)

    assert computed_hash == expected_hash
    assert len(computed_hash) == 64

    # 2. Empty file
    empty_path = tmp_path / "empty.dat"
    empty_path.write_bytes(b"")
    empty_hash = hash_dataset_iteratively(empty_path)
    assert empty_hash == hashlib.sha256(b"").hexdigest()

    # 3. Non-existent file error
    missing_file = tmp_path / "non_existent.bin"
    with pytest.raises(FileNotFoundError):
        hash_dataset_iteratively(missing_file)


def test_generate_aastex_longtables() -> None:
    """Verifies AASTeX and LaTeX table generation, siunitx formatting, frozen handling, and truncation."""
    parameters: list[dict[str, Any]] = [
        {
            "name": "A",
            "latex_name": r"A_0",
            "value": 5420.3182,
            "uncertainty": 0.0014,
            "unit": "MHz",
            "is_frozen": False,
            "description": "Principal rotational constant A",
        },
        {
            "name": "B",
            "latex_name": r"B_0",
            "value": 2314.1592,
            "uncertainty": 0.0008,
            "unit": "MHz",
            "is_frozen": False,
            "description": "Principal rotational constant B",
        },
        {
            "name": "C",
            "latex_name": r"C_0",
            "value": 1823.4567,
            "uncertainty": 0.0009,
            "unit": "MHz",
            "is_frozen": False,
            "description": "Principal rotational constant C",
        },
        {
            "name": "D_J",
            "latex_name": r"\Delta_J",
            "value": 0.00345,
            "uncertainty": None,
            "is_frozen": True,
            "description": "Quartic distortion DJ",
        },
        {
            "name": "D_JK",
            "latex_name": r"\Delta_{JK}",
            "value": -0.01234,
            "uncertainty": 0.0005,
            "unit": "MHz",
            "is_frozen": False,
            "sobol_audit": False,
            "description": "Quartic distortion DJK frozen by sobol audit",
        },
        {
            "name": "V3",
            "latex_name": r"V_3",
            "value": 350.5,
            "uncertainty": 0.1,
            "unit": "cm-1",
            "status": "fixed",
            "description": "Internal rotation barrier set fixed",
        },
    ]

    # Create 250 transition records to verify truncation to top 200
    transitions: list[dict[str, Any]] = []
    for idx in range(250):
        intensity_val = float(idx + 1) * 0.1
        transitions.append(
            {
                "upper_state": f"{idx+2}_1_{idx+2}",
                "lower_state": f"{idx+1}_0_{idx+1}",
                "observed_mhz": 10000.0 + idx * 25.5,
                "calculated_mhz": 10000.0 + idx * 25.5 + 0.004,
                "residual_mhz": -0.004,
                "uncertainty_mhz": 0.010,
                "intensity": intensity_val,
                "einstein_a": intensity_val * 1e-4,
            }
        )

    tables = generate_aastex_longtables(parameters, transitions, title_prefix="Ar-Furonitrile Fit")

    assert "parameters_table" in tables
    assert "transitions_table" in tables
    assert "combined_document" in tables

    param_table = tables["parameters_table"]
    trans_table = tables["transitions_table"]
    doc = tables["combined_document"]

    # Verify siunitx & booktabs markers
    assert r"\toprule" in param_table
    assert r"\midrule" in param_table
    assert r"\bottomrule" in param_table
    assert "siunitx" in doc or "S[" in param_table or r"\num{" in param_table

    # Verify frozen parameter handling: uncertainties replaced with Fixed or Set
    assert "Fixed" in param_table or "Set" in param_table

    # Verify transition truncation: only 200 rows rendered
    transition_row_markers = trans_table.count(r"\\")
    assert transition_row_markers <= 205
    assert transition_row_markers >= 190


def test_get_required_dois() -> None:
    """Verifies DOI extraction for standard spectroscopic and quantum chemistry models."""
    models = [
        "Watson_A_Reduction",
        "watson-s-reduction",
        "IAM_Internal_Rotation",
        "ERHAM",
        "JAX_Backend",
        "PyArrow_Engine",
        "SPCAT",
        "ORCA",
        "CFOUR",
        "CREST",
        "xTB",
        "MACE",
        "AIMNet2",
        "unknown_custom_model",
    ]

    dois = get_required_dois(models)
    assert len(dois) >= 6
    # Watson reduction DOI
    assert any("10.1016/0022-2852(77)90184-7" in d or "10.1063" in d for d in dois)
    # JAX DOI
    assert any("10.5281/zenodo" in d for d in dois)
    # SPCAT DOI
    assert any("10.1016/0022-2852(91)90393-O" in d for d in dois)
    # ERHAM DOI
    assert any("10.1006/jmsp.1997.7432" in d for d in dois)
    # No duplicate DOIs
    assert len(dois) == len(set(dois))


def test_format_citations_to_bib() -> None:
    """Verifies parsing of CrossRef JSON metadata into clean, deduplicated BibTeX records."""
    crossref_items: list[dict[str, Any]] = [
        {
            "DOI": "10.1016/0022-2852(77)90184-7",
            "title": ["The determination of centrifugal distortion constants of asymmetric-top molecules"],
            "author": [{"given": "J. K. G.", "family": "Watson"}],
            "container-title": ["Journal of Molecular Spectroscopy"],
            "volume": "65",
            "issue": "1",
            "page": "123-133",
            "issued": {"date-parts": [[1977, 4, 1]]},
            "type": "journal-article",
            "publisher": "Elsevier BV",
        },
        {
            "DOI": "10.1016/0022-2852(91)90393-O",
            "title": ["The fitting and prediction of vibration-rotation spectra with spin interactions"],
            "author": [{"given": "Herbert M.", "family": "Pickett"}],
            "container-title": ["Journal of Molecular Spectroscopy"],
            "volume": "148",
            "issue": "2",
            "page": "371-377",
            "issued": {"date-parts": [[1991, 8, 1]]},
            "type": "journal-article",
            "publisher": "Elsevier BV",
        },
        # Duplicate entry with lowercase doi key
        {
            "doi": "10.1016/0022-2852(91)90393-O",
            "title": "The fitting and prediction of vibration-rotation spectra with spin interactions",
            "author": [{"given": "Herbert M.", "family": "Pickett"}],
            "container_title": "Journal of Molecular Spectroscopy",
            "volume": "148",
            "issued": {"date-parts": [[1991]]},
        },
    ]

    bib_str = format_citations_to_bib(crossref_items)
    assert "@article" in bib_str
    assert "Watson" in bib_str
    assert "Pickett" in bib_str
    assert "10.1016/0022-2852(77)90184-7" in bib_str
    assert "10.1016/0022-2852(91)90393-O" in bib_str

    # Ensure deduplicated: Pickett appears exactly once
    assert bib_str.count("10.1016/0022-2852(91)90393-O") == 1

    # Empty list handling
    assert format_citations_to_bib([]) == ""


def test_evaluate_compression_strategy() -> None:
    """Verifies compression threshold logic."""
    threshold = 104857600  # 100 MiB
    assert evaluate_compression_strategy(50000000, threshold_bytes=threshold) == "ZIP"
    assert evaluate_compression_strategy(104857600, threshold_bytes=threshold) == "ZSTD"
    assert evaluate_compression_strategy(200000000, threshold_bytes=threshold) == "ZSTD"


def test_package_fit_artifacts_zip_and_zstd(tmp_path: Path) -> None:
    """Verifies packaging artifacts into ZIP and TAR.ZST archives and integrity testing."""
    source_dir = tmp_path / "artifacts_source"
    source_dir.mkdir()

    (source_dir / "fit_provenance.json").write_text('{"session": "alpha"}', encoding="utf-8")
    (source_dir / "parameters.tex").write_text(r"\begin{tabular} ... \end{tabular}", encoding="utf-8")
    (source_dir / "binary_data.dat").write_bytes(b"\x00\x01\x02\x03" * 1024)

    # 1. Package as ZIP
    zip_out = tmp_path / "package_output_zip"
    created_zip = package_fit_artifacts(source_dir, zip_out, strategy="ZIP")
    assert created_zip.exists()
    assert created_zip.suffix == ".zip"

    with zipfile.ZipFile(created_zip, "r") as zf:
        namelist = zf.namelist()
        assert "fit_provenance.json" in namelist
        assert "parameters.tex" in namelist
        assert "binary_data.dat" in namelist
        assert zf.read("fit_provenance.json").decode("utf-8") == '{"session": "alpha"}'

    # 2. Package as ZSTD
    zstd_out = tmp_path / "package_output_zstd"
    created_zstd = package_fit_artifacts(source_dir, zstd_out, strategy="ZSTD")
    assert created_zstd.exists()
    assert str(created_zstd).endswith(".tar.zst")

    # Decompress and verify tar contents
    dctx = zstandard.ZstdDecompressor()
    decompressed_tar_bytes = dctx.decompress(created_zstd.read_bytes())
    tar_dest = tmp_path / "decompressed.tar"
    tar_dest.write_bytes(decompressed_tar_bytes)

    with tarfile.open(tar_dest, "r") as tf:
        names = tf.getnames()
        assert any("fit_provenance.json" in n for n in names)
        assert any("parameters.tex" in n for n in names)
        assert any("binary_data.dat" in n for n in names)

    # 3. Invalid strategy
    with pytest.raises(ValueError):
        package_fit_artifacts(source_dir, zip_out, strategy="UNSUPPORTED_FORMAT")

    # 4. Non-existent source dir
    missing_dir = tmp_path / "missing_source_directory"
    with pytest.raises(NotADirectoryError):
        package_fit_artifacts(missing_dir, zip_out)


def test_seal_artifact_read_only(tmp_path: Path) -> None:
    """Verifies setting cross-platform read-only permissions."""
    sealed_file = tmp_path / "locked_provenance.json"
    sealed_file.write_text('{"locked": true}', encoding="utf-8")

    success = seal_artifact_read_only(sealed_file)
    assert success is True

    # Verification: check permissions
    file_stat = sealed_file.stat()
    assert not (file_stat.st_mode & stat.S_IWUSR)

    # Attempting write in write mode should raise PermissionError
    with pytest.raises(PermissionError):
        with open(sealed_file, "w", encoding="utf-8") as f:
            f.write('{"locked": false}')

    # Cleanup permissions so pytest temp directory cleaner won't fail
    os.chmod(sealed_file, stat.S_IWRITE | stat.S_IREAD)

    # Non-existent file sealing test
    missing_file = tmp_path / "not_there.json"
    with pytest.raises(FileNotFoundError):
        seal_artifact_read_only(missing_file)


def test_export_spycfit_snapshot_pipeline(tmp_path: Path) -> None:
    """Verifies the complete end-to-end snapshot generation and export workflow."""
    source_dir = tmp_path / "session_raw"
    source_dir.mkdir()

    raw_spectrum = source_dir / "chirp_spectrum.ftm"
    raw_spectrum.write_bytes(b"FTMW RAW DATA CHIRP 2-18 GHz" * 500)

    dataset_hash = hash_dataset_iteratively(raw_spectrum)

    payload = FitProvenancePayload(
        session_id="spycfit_full_pipeline_test",
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        dataset_hashes={"chirp_spectrum.ftm": dataset_hash},
        chi_squared=1.002,
        huber_loss_delta=0.001,
        rms_mhz=0.0084,
        rms_cm_inv=0.00028,
        jacobian_condition_number=18.4,
        sobol_parameter_audit={"A": True, "B": True, "C": True},
        semantic_git_history=["commit a1b2c3d: Pipeline validation"],
        active_models=["Watson_A_Reduction", "JAX_Backend", "SPCAT"],
    )

    parameters = [
        {"name": "A", "latex_name": "A_0", "value": 4500.12, "uncertainty": 0.01, "unit": "MHz", "is_frozen": False},
        {"name": "B", "latex_name": "B_0", "value": 2200.34, "uncertainty": 0.005, "unit": "MHz", "is_frozen": False},
    ]
    transitions = [
        {
            "upper_state": "1_1_1",
            "lower_state": "0_0_0",
            "observed_mhz": 6700.46,
            "calculated_mhz": 6700.458,
            "residual_mhz": 0.002,
            "uncertainty_mhz": 0.01,
            "intensity": 10.5,
        }
    ]

    export_dest = tmp_path / "snapshot_processed"

    result = export_spycfit_snapshot(
        payload=payload,
        source_dir=source_dir,
        output_dir=export_dest,
        optimized_params=parameters,
        transitions=transitions,
        title_prefix="CO2-H2O Complex Fit",
        strategy="ZSTD",
    )

    assert result["status"] == "SUCCESS"
    assert "archive_path" in result
    assert "provenance_path" in result
    assert "parameters_table_path" in result
    assert "transitions_table_path" in result
    assert "citations_bib_path" in result

    archive_path = Path(result["archive_path"])
    assert archive_path.exists()
    assert str(archive_path).endswith(".tar.zst")

    # Verify provenance file exists and is valid
    prov_path = Path(result["provenance_path"])
    assert prov_path.exists()
    loaded_prov = FitProvenancePayload.from_json_file(prov_path)
    assert loaded_prov.session_id == payload.session_id


def test_reexport_consistency() -> None:
    """Verifies that the top-level interfaces re-export matches canonical cochem_base module."""
    import cochem_base.interfaces.cochem_vibspyc_snap as canonical
    import interfaces.cochem_vibspyc_snap as reexported

    symbols = [
        "FitProvenancePayload",
        "get_spycfit_processed_dir",
        "resolve_processed_workspace_dir",
        "hash_dataset_iteratively",
        "generate_aastex_longtables",
        "get_required_dois",
        "format_citations_to_bib",
        "evaluate_compression_strategy",
        "package_fit_artifacts",
        "seal_artifact_read_only",
        "export_spycfit_snapshot",
    ]

    for sym in symbols:
        assert hasattr(canonical, sym), f"Canonical module missing symbol '{sym}'"
        assert hasattr(reexported, sym), f"Re-exported module missing symbol '{sym}'"
        assert getattr(canonical, sym) is getattr(reexported, sym)

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_gitignore_comprehensive.py ---
"""Comprehensive Zero-Mock Test Suite for CoChem-BASE .gitignore Air-Gap Specifications.

Defends the Tripartite Workspace Air-Gap and repository hygiene by validating:
- Physical existence of .gitignore at repository root.
- Strict UTF-8 encoding (no byte order mark) and Unix LF line endings.
- Exact compliance with SRS Document 1 specifications across all 6 sections.
- Comprehensive physical pattern matching covering all blocked and allowed file types.
- Deep nested directory traversal and execution scratch boundary enforcement.
- Absence of mock objects, dummy stubs, or synthetic bypass mechanisms.
"""

from __future__ import annotations

import ast
import fnmatch
import subprocess
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GITIGNORE_PATH = REPO_ROOT / ".gitignore"

SECTION_1_PATTERNS = [
    "__pycache__/",
    "*.pyc",
    ".ipynb_checkpoints/",
    ".cochem_env/",
]

SECTION_2_PATTERNS = [
    "CoChem_Artifacts/",
    "*/CoChem_Artifacts/*",
    "cochem_exec_*/",
]

SECTION_3_PATTERNS = [
    "*.h5",
    "*.hdf5",
    "*.parquet",
    "*.npy",
    "*.npz",
    "*.db",
    "*.sqlite",
]

SECTION_4_PATTERNS = [
    "*.gbw",
    "*.tmp",
    "*.chk",
    "*.opt",
    "*.lock",
    "*.log",
    "*.out",
    "*.err",
    "core.*",
    "slurm-*.out",
    "runinfo/",
    "*.parsl",
]

SECTION_5_PATTERNS = [
    "*.xyz",
    "*.mol",
    "*.smi",
    "*.pdb",
    "*.cif",
]

SECTION_6_PATTERNS = [
    "*config.json",
    "cochem_system_config.json",
    "cochem_audit_log.json",
    "TOPOS_Runtime_State.json",
]

ALL_EXPECTED_PATTERNS = (
    SECTION_1_PATTERNS
    + SECTION_2_PATTERNS
    + SECTION_3_PATTERNS
    + SECTION_4_PATTERNS
    + SECTION_5_PATTERNS
    + SECTION_6_PATTERNS
)

EXPECTED_SECTION_HEADERS = [
    "# 1. Python Cache & Virtual Environments",
    "# 2. Absolute blocking of the Artifacts Workspace & Local Compute Overlap",
    "# 3. Heavy Databases & Quantum Arrays (Prevents repository bloat)",
    "# 4. Execution Scratch, Telemetry Logs, & HPC Residue",
    "# 5. User Chemical Inputs (Protects proprietary user data)",
    "# 6. Local Registries & States (Prevents cross-machine configuration poisoning)",
]


@pytest.fixture(scope="module")
def gitignore_content() -> str:
    """Fixture providing the text content of .gitignore."""
    assert GITIGNORE_PATH.exists(), f"Missing .gitignore at {GITIGNORE_PATH}"
    return GITIGNORE_PATH.read_text(encoding="utf-8")


def test_gitignore_file_attributes() -> None:
    """Validate .gitignore file existence, type, and size bounds."""
    assert GITIGNORE_PATH.exists(), f".gitignore file must exist at {GITIGNORE_PATH}"
    assert GITIGNORE_PATH.is_file(), f"{GITIGNORE_PATH} must be a regular file"
    size = GITIGNORE_PATH.stat().st_size
    assert size > 200, f".gitignore size too small ({size} bytes)"
    assert size < 10000, f".gitignore size unexpectedly large ({size} bytes)"


def test_gitignore_no_bom_and_strict_lf() -> None:
    """Validate UTF-8 encoding without BOM and strict Unix LF line endings."""
    raw_bytes = GITIGNORE_PATH.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), ".gitignore must not contain UTF-8 BOM"
    assert b"\r\n" not in raw_bytes, ".gitignore contains Windows CRLF line endings"
    assert b"\r" not in raw_bytes, ".gitignore contains CR line endings"
    assert b"\n" in raw_bytes, ".gitignore must contain Unix LF line endings"


def test_gitignore_header_and_sections(gitignore_content: str) -> None:
    """Validate top banner and all 6 SRS Document 1 section headers."""
    assert "# ==============================================================================" in gitignore_content
    assert "# CoChem-BASE Strict Air-Gap Constraints" in gitignore_content
    for header in EXPECTED_SECTION_HEADERS:
        assert header in gitignore_content, f"Missing section header in .gitignore: {header}"


def test_gitignore_all_patterns_present(gitignore_content: str) -> None:
    """Validate that every expected pattern is defined in .gitignore."""
    lines = [
        line.strip()
        for line in gitignore_content.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    for pattern in ALL_EXPECTED_PATTERNS:
        assert pattern in lines, f"Pattern '{pattern}' missing from .gitignore"


def test_zero_mock_policy_enforcement() -> None:
    """Ensure zero-mock policy across this test file via AST inspection."""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "mock" not in alias.name.lower(), f"Forbidden mock import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert "mock" not in module.lower(), f"Forbidden mock import: {module}"


# Parameterized test for physical git check-ignore evaluation in a real git environment
@pytest.mark.parametrize(
    "file_rel_path, should_be_ignored, section_label",
    [
        # Section 1
        ("__pycache__/engine.pyc", True, "Sec1: Python Cache"),
        ("src/pkg/__pycache__/sub.pyc", True, "Sec1: Python Cache Nested"),
        ("app.pyc", True, "Sec1: Bytecode"),
        ("deep/pkg/module.pyc", True, "Sec1: Bytecode Nested"),
        (".ipynb_checkpoints/calc-checkpoint.ipynb", True, "Sec1: Notebook Checkpoints"),
        (".cochem_env/pyvenv.cfg", True, "Sec1: Virtual Environment"),
        (".cochem_env/lib/site-packages/test.py", True, "Sec1: Virtual Environment Libs"),
        # Section 2
        ("CoChem_Artifacts/run01/output.txt", True, "Sec2: Artifacts Root"),
        ("nested/dir/CoChem_Artifacts/job1/output.bin", True, "Sec2: Artifacts Subdir"),
        ("cochem_exec_482910/scratch.dat", True, "Sec2: Execution Scratch"),
        ("nested/cochem_exec_gamma/stdout.log", True, "Sec2: Execution Scratch Nested"),
        # Section 3
        ("dataset_01.h5", True, "Sec3: HDF5 (.h5)"),
        ("data/sub/quantum_states.hdf5", True, "Sec3: HDF5 (.hdf5)"),
        ("table.parquet", True, "Sec3: Parquet"),
        ("vectors.npy", True, "Sec3: NumPy Array (.npy)"),
        ("arrays.npz", True, "Sec3: NumPy Archive (.npz)"),
        ("local_cache.db", True, "Sec3: Database (.db)"),
        ("state.sqlite", True, "Sec3: SQLite (.sqlite)"),
        # Section 4
        ("orca_wf.gbw", True, "Sec4: ORCA wavefunction (.gbw)"),
        ("temp_calc.tmp", True, "Sec4: Temp (.tmp)"),
        ("gaussian.chk", True, "Sec4: Checkpoint (.chk)"),
        ("geometry.opt", True, "Sec4: Optimization (.opt)"),
        ("lockfile.lock", True, "Sec4: Lockfile (.lock)"),
        ("server.log", True, "Sec4: Log (.log)"),
        ("output.out", True, "Sec4: Out (.out)"),
        ("stderr.err", True, "Sec4: Err (.err)"),
        ("core.9812", True, "Sec4: Core dump (core.*)"),
        ("slurm-1234567.out", True, "Sec4: Slurm log (slurm-*.out)"),
        ("runinfo/parsl_exec.log", True, "Sec4: Parsl runinfo/"),
        ("pipeline.parsl", True, "Sec4: Parsl state (.parsl)"),
        # Section 5
        ("water_dimer.xyz", True, "Sec5: Chemical XYZ (.xyz)"),
        ("aspirin.mol", True, "Sec5: Chemical MOL (.mol)"),
        ("smiles_library.smi", True, "Sec5: SMILES (.smi)"),
        ("ribosome.pdb", True, "Sec5: Protein PDB (.pdb)"),
        ("zeolite.cif", True, "Sec5: Crystallography CIF (.cif)"),
        ("deep/path/benzene.xyz", True, "Sec5: Chemical XYZ Nested"),
        # Section 6
        ("app_config.json", True, "Sec6: Wildcard config (*config.json)"),
        ("server_config.json", True, "Sec6: Wildcard config (*config.json)"),
        ("cochem_system_config.json", True, "Sec6: Exact cochem_system_config.json"),
        ("cochem_audit_log.json", True, "Sec6: Exact cochem_audit_log.json"),
        ("TOPOS_Runtime_State.json", True, "Sec6: Exact TOPOS_Runtime_State.json"),
        ("sub/folder/local_config.json", True, "Sec6: Nested *config.json"),
        # Standard Allowed Files
        ("main.py", False, "Allowed: Python Main"),
        ("cochem_base/engine.py", False, "Allowed: Python Package"),
        ("tests/test_airgap.py", False, "Allowed: Test File"),
        ("README.md", False, "Allowed: Markdown"),
        ("Method_Matrix.md", False, "Allowed: Method Matrix"),
        ("CoChem_User_Manual.md", False, "Allowed: User Manual"),
        ("pyproject.toml", False, "Allowed: TOML Config"),
        ("pytest.ini", False, "Allowed: Pytest Config"),
        (".pre-commit-config.yaml", False, "Allowed: YAML Config"),
        ("package.json", False, "Allowed: Non-matching JSON"),
        ("manifest.json", False, "Allowed: Non-matching JSON"),
        ("schema.json", False, "Allowed: Non-matching JSON"),
        ("setup.cfg", False, "Allowed: Setup Config"),
        ("Dockerfile", False, "Allowed: Dockerfile"),
    ],
)
def test_git_check_ignore_matrix(
    tmp_path: Path, file_rel_path: str, should_be_ignored: bool, section_label: str
) -> None:
    """Physically test git ignore behavior using git CLI in an isolated sandbox repository."""
    # Copy raw .gitignore directly without mutation
    (tmp_path / ".gitignore").write_bytes(GITIGNORE_PATH.read_bytes())

    # Initialize physical git repository
    try:
        subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True, timeout=15)
        subprocess.run(
            ["git", "-C", str(tmp_path), "config", "user.name", "Tester"],
            check=True,
            capture_output=True,
            timeout=15,
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "config", "user.email", "test@domain.com"],
            check=True,
            capture_output=True,
            timeout=15,
        )

        # Create dummy target file
        target_path = tmp_path / file_rel_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text("airgap validation physical file content", encoding="utf-8")

        # Run git check-ignore
        proc = subprocess.run(
            ["git", "-C", str(tmp_path), "check-ignore", "-q", file_rel_path],
            capture_output=True,
            timeout=15,
        )
        actual_ignored = proc.returncode == 0
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        pytest.fail(f"Git check-ignore command failed: {e}")

    assert actual_ignored == should_be_ignored, (
        f"[{section_label}] Failed for path '{file_rel_path}': "
        f"expected ignored={should_be_ignored}, got {actual_ignored}."
    )


def test_special_characters_and_whitespace_paths(tmp_path: Path) -> None:
    """Validate gitignore rules with spaces, Unicode, and complex path names."""
    # Copy raw .gitignore directly without mutation
    (tmp_path / ".gitignore").write_bytes(GITIGNORE_PATH.read_bytes())
    try:
        subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True, timeout=15)
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Tester"], check=True, capture_output=True, timeout=15)
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@domain.com"], check=True, capture_output=True, timeout=15)

        test_paths = [
            ("Calculation Folder With Spaces/result.log", True),
            ("Квантовые_Данные/matrix.h5", True),
            ("Chemical Structures (2026)/complex_molecule.xyz", True),
            ("Allowed Code/script_01.py", False),
            ("Documentation & Notes/Architecture.md", False),
        ]

        for rel_p, expect_ign in test_paths:
            p = tmp_path / rel_p
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("data", encoding="utf-8")

            proc = subprocess.run(
                ["git", "-C", str(tmp_path), "check-ignore", "-q", rel_p],
                capture_output=True,
                timeout=15,
            )
            assert (proc.returncode == 0) == expect_ign, f"Failed for path '{rel_p}'"
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        pytest.fail(f"Git check-ignore command failed: {e}")

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_spycfit_pyproject.py ---
"""Zero-Mock Production Test Suite for CoChem-SpycFit pyproject.toml Specifications.

Defends the Execution Tier build system and Tripartite Architecture metadata by validating:
- Physical existence of pyproject.toml at CoChem-SpycFit repository root.
- Strict UTF-8 encoding (no byte order mark) and Unix LF line endings.
- Exact compliance with SRS Document specifications for build system and project metadata.
- TOML syntax validity and schema parsing using tomllib / tomli.
- Build system table: requires = ["setuptools>=61.0", "wheel"], build-backend = "setuptools.build_meta".
- Project table: name = "CoChem-SpycFit", version = "0.1.0", description, authors.
- Exact presence and canonical ordering of all 12 required dependencies:
  jax, jaxlib, cupy-cuda12x, h5py, zarr, pyarrow, plotly, ipywidgets, mendeleev, platformdirs, filelock, pyzmq.
- Optional dependencies: dev = ["pytest", "flake8"].
- Strict exclusion of legacy Fortran binaries, unapproved dependencies, and mock/placeholder tokens.
- Verification of zero forbidden testing constructs via AST analysis.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Any, Dict

import pytest
from packaging.requirements import Requirement

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

# Repository paths with strict environmental configuration and Path.home() fallback
COCHEM_HOME = Path(os.environ.get("COCHEM_HOME", Path.home() / "cochem"))
BASE_REPO_ROOT = Path(
    os.environ.get("COCHEM_BASE_ROOT", str(Path(__file__).resolve().parent.parent))
)
SPYCFIT_REPO_ROOT = Path(
    os.environ.get("COCHEM_SPYCFIT_ROOT", str(BASE_REPO_ROOT.parent / "CoChem-SpycFit"))
)
SPYCFIT_PYPROJECT_PATH = SPYCFIT_REPO_ROOT / "pyproject.toml"

# Canonical SRS pyproject.toml content
CANONICAL_PYPROJECT_CONTENT = (
    "[build-system]\n"
    'requires = ["setuptools>=61.0", "wheel"]\n'
    'build-backend = "setuptools.build_meta"\n'
    "\n"
    "[project]\n"
    'name = "CoChem-SpycFit"\n'
    'version = "0.1.0"\n'
    'description = "Tripartite Workspace Air-Gap enabled computational spectroscopy fitter."\n'
    'authors = [{name = "CoChem Swarm"}]\n'
    "dependencies = [\n"
    '    "jax",\n'
    '    "jaxlib",\n'
    '    "cupy-cuda12x",\n'
    '    "h5py",\n'
    '    "zarr",\n'
    '    "pyarrow",\n'
    '    "plotly",\n'
    '    "ipywidgets",\n'
    '    "mendeleev",\n'
    '    "platformdirs",\n'
    '    "filelock",\n'
    '    "pyzmq"\n'
    "]\n"
    "\n"
    "[project.optional-dependencies]\n"
    'dev = ["pytest", "flake8"]\n'
)

EXPECTED_BUILD_SYSTEM_REQUIRES = ["setuptools>=61.0", "wheel"]
EXPECTED_BUILD_BACKEND = "setuptools.build_meta"

EXPECTED_PROJECT_NAME = "CoChem-SpycFit"
EXPECTED_PROJECT_VERSION = "0.1.0"
EXPECTED_PROJECT_DESCRIPTION = (
    "Tripartite Workspace Air-Gap enabled computational spectroscopy fitter."
)
EXPECTED_PROJECT_AUTHORS = [{"name": "CoChem Swarm"}]

EXPECTED_DEPENDENCIES = [
    "jax",
    "jaxlib",
    "cupy-cuda12x",
    "h5py",
    "zarr",
    "pyarrow",
    "plotly",
    "ipywidgets",
    "mendeleev",
    "platformdirs",
    "filelock",
    "pyzmq",
]

EXPECTED_DEV_DEPENDENCIES = ["pytest", "flake8"]

FORBIDDEN_LEGACY_TOKENS = [
    "fortran",
    "spcat",
    "spfit",
    "calpgm",
    "f2py",
    "weave",
    "mock",
    "dummy",
    "fake",
    "synthetic",
    "stub",
    "placeholder",
]


@pytest.fixture(scope="module")
def pyproject_raw_bytes() -> bytes:
    """Fixture providing raw bytes of CoChem-SpycFit pyproject.toml."""
    assert (
        SPYCFIT_PYPROJECT_PATH.exists()
    ), f"Missing pyproject.toml at {SPYCFIT_PYPROJECT_PATH}"
    return SPYCFIT_PYPROJECT_PATH.read_bytes()


@pytest.fixture(scope="module")
def pyproject_content(pyproject_raw_bytes: bytes) -> str:
    """Fixture providing decoded text content of CoChem-SpycFit pyproject.toml."""
    return pyproject_raw_bytes.decode("utf-8")


@pytest.fixture(scope="module")
def pyproject_data(pyproject_content: str) -> Dict[str, Any]:
    """Fixture providing parsed TOML dictionary."""
    data = tomllib.loads(pyproject_content)
    assert isinstance(data, dict), "Parsed TOML root must be a dictionary"
    return data


# ==============================================================================
# 1. Physical File Integrity & Line Endings
# ==============================================================================


def test_spycfit_pyproject_existence_and_size() -> None:
    """Validate that pyproject.toml physically exists in CoChem-SpycFit root with valid size bounds."""
    assert (
        SPYCFIT_PYPROJECT_PATH.exists()
    ), f"Target file must exist: {SPYCFIT_PYPROJECT_PATH}"
    assert (
        SPYCFIT_PYPROJECT_PATH.is_file()
    ), f"Target path must be a regular file: {SPYCFIT_PYPROJECT_PATH}"
    size = SPYCFIT_PYPROJECT_PATH.stat().st_size
    assert (
        100 < size < 5000
    ), f"pyproject.toml size ({size} bytes) outside expected range (100, 5000)"


def test_spycfit_pyproject_encoding_and_lf_line_endings(
    pyproject_raw_bytes: bytes,
) -> None:
    """Validate strict UTF-8 encoding without BOM and Unix LF line endings."""
    assert not pyproject_raw_bytes.startswith(
        b"\xef\xbb\xbf"
    ), "Target file must not contain a UTF-8 BOM"
    assert (
        b"\r\n" not in pyproject_raw_bytes
    ), "Target file contains Windows CRLF line endings"
    assert (
        b"\r" not in pyproject_raw_bytes
    ), "Target file contains carriage return line endings"
    assert b"\n" in pyproject_raw_bytes, "Target file must contain Unix LF line endings"
    assert pyproject_raw_bytes.endswith(
        b"\n"
    ), "Target file must terminate with a Unix LF newline"
    decoded = pyproject_raw_bytes.decode("utf-8")
    assert len(decoded) > 0, "Target file content cannot be empty"


def test_spycfit_pyproject_canonical_content(pyproject_content: str) -> None:
    """Validate that pyproject.toml strictly matches the canonical SRS specification."""
    assert pyproject_content == CANONICAL_PYPROJECT_CONTENT, (
        f"pyproject.toml content differs from canonical SRS specification:\n"
        f"--- Got ---\n{pyproject_content}\n"
        f"--- Expected ---\n{CANONICAL_PYPROJECT_CONTENT}"
    )


# ==============================================================================
# 2. TOML Schema & [build-system] Table
# ==============================================================================


def test_spycfit_pyproject_top_level_tables(pyproject_data: Dict[str, Any]) -> None:
    """Validate required top-level tables exist in pyproject.toml."""
    assert "build-system" in pyproject_data, "Missing [build-system] table"
    assert "project" in pyproject_data, "Missing [project] table"
    assert isinstance(
        pyproject_data["build-system"], dict
    ), "[build-system] must be a table"
    assert isinstance(pyproject_data["project"], dict), "[project] must be a table"


def test_spycfit_pyproject_build_system(pyproject_data: Dict[str, Any]) -> None:
    """Validate [build-system] requires setuptools>=61.0, wheel, and setuptools.build_meta backend."""
    build_sys = pyproject_data["build-system"]
    assert "requires" in build_sys, "Missing 'requires' in [build-system]"
    assert "build-backend" in build_sys, "Missing 'build-backend' in [build-system]"

    assert (
        build_sys["requires"] == EXPECTED_BUILD_SYSTEM_REQUIRES
    ), f"Expected build-system requires {EXPECTED_BUILD_SYSTEM_REQUIRES}, got {build_sys['requires']}"
    assert (
        build_sys["build-backend"] == EXPECTED_BUILD_BACKEND
    ), f"Expected build-backend '{EXPECTED_BUILD_BACKEND}', got '{build_sys['build-backend']}'"


# ==============================================================================
# 3. [project] Metadata Table
# ==============================================================================


def test_spycfit_pyproject_metadata(pyproject_data: Dict[str, Any]) -> None:
    """Validate name, version, description, and authors in [project]."""
    proj = pyproject_data["project"]
    assert (
        proj.get("name") == EXPECTED_PROJECT_NAME
    ), f"Expected project.name '{EXPECTED_PROJECT_NAME}', got '{proj.get('name')}'"
    assert (
        proj.get("version") == EXPECTED_PROJECT_VERSION
    ), f"Expected project.version '{EXPECTED_PROJECT_VERSION}', got '{proj.get('version')}'"
    assert (
        proj.get("description") == EXPECTED_PROJECT_DESCRIPTION
    ), f"Expected project.description '{EXPECTED_PROJECT_DESCRIPTION}', got '{proj.get('description')}'"
    assert (
        proj.get("authors") == EXPECTED_PROJECT_AUTHORS
    ), f"Expected project.authors {EXPECTED_PROJECT_AUTHORS}, got {proj.get('authors')}"


# ==============================================================================
# 4. [project.dependencies] Table
# ==============================================================================


def test_spycfit_pyproject_dependencies_presence_and_count(
    pyproject_data: Dict[str, Any],
) -> None:
    """Validate exactly 12 required dependencies are present in [project.dependencies]."""
    proj = pyproject_data["project"]
    assert "dependencies" in proj, "Missing 'dependencies' list in [project]"
    deps = proj["dependencies"]
    assert isinstance(deps, list), "'dependencies' must be a list"
    assert (
        len(deps) == 12
    ), f"Expected exactly 12 dependencies, found {len(deps)}: {deps}"
    assert (
        deps == EXPECTED_DEPENDENCIES
    ), f"Dependencies list mismatch.\nExpected: {EXPECTED_DEPENDENCIES}\nGot: {deps}"


@pytest.mark.parametrize("expected_pkg", EXPECTED_DEPENDENCIES)
def test_spycfit_pyproject_individual_dependency(
    pyproject_data: Dict[str, Any], expected_pkg: str
) -> None:
    """Validate each individual dependency parses cleanly under packaging standards."""
    deps = pyproject_data["project"]["dependencies"]
    assert (
        expected_pkg in deps
    ), f"Required dependency '{expected_pkg}' missing from dependencies"
    req = Requirement(expected_pkg)
    assert req.name.lower() == expected_pkg.lower()


def test_spycfit_pyproject_no_duplicate_dependencies(
    pyproject_data: Dict[str, Any],
) -> None:
    """Validate zero duplicate dependency declarations."""
    deps = pyproject_data["project"]["dependencies"]
    normalized = [Requirement(d).name.lower() for d in deps]
    assert len(normalized) == len(
        set(normalized)
    ), f"Duplicate dependencies detected in: {deps}"


def test_spycfit_pyproject_exclusion_of_forbidden_dependencies(
    pyproject_data: Dict[str, Any],
) -> None:
    """Validate exclusion of legacy Fortran binaries or unapproved packages."""
    deps = pyproject_data["project"]["dependencies"]
    allowed_names = {Requirement(d).name.lower() for d in EXPECTED_DEPENDENCIES}

    for dep in deps:
        req = Requirement(dep)
        assert (
            req.name.lower() in allowed_names
        ), f"Unapproved dependency found in project.dependencies: '{dep}'"
        for forbidden in FORBIDDEN_LEGACY_TOKENS:
            assert (
                forbidden not in dep.lower()
            ), f"Forbidden token '{forbidden}' found in dependency declaration: '{dep}'"


# ==============================================================================
# 5. [project.optional-dependencies] Table
# ==============================================================================


def test_spycfit_pyproject_optional_dependencies(
    pyproject_data: Dict[str, Any],
) -> None:
    """Validate [project.optional-dependencies] defines dev dependencies."""
    proj = pyproject_data["project"]
    assert (
        "optional-dependencies" in proj
    ), "Missing [project.optional-dependencies] table"
    opt_deps = proj["optional-dependencies"]
    assert isinstance(
        opt_deps, dict
    ), "[project.optional-dependencies] must be a dictionary"
    assert "dev" in opt_deps, "Missing 'dev' group in [project.optional-dependencies]"
    dev_deps = opt_deps["dev"]
    assert isinstance(dev_deps, list), "'dev' optional dependencies must be a list"
    assert (
        dev_deps == EXPECTED_DEV_DEPENDENCIES
    ), f"Expected dev dependencies {EXPECTED_DEV_DEPENDENCIES}, got {dev_deps}"

    for dep in dev_deps:
        req = Requirement(dep)
        assert req.name, f"Invalid optional dependency: '{dep}'"


# ==============================================================================
# 6. Zero-Mock & Anti-Spoofing Validations
# ==============================================================================


def test_spycfit_pyproject_zero_mock_and_no_stubs(pyproject_content: str) -> None:
    """Validate that pyproject.toml contains no mock, stub, or placeholder tokens."""
    forbidden_tokens = [
        "TODO",
        "FIXME",
        "placeholder",
        "dummy",
        "fake",
        "synthetic",
        "stub",
        "mock",
        "TEMPORARY",
    ]
    for token in forbidden_tokens:
        assert (
            token.lower() not in pyproject_content.lower()
        ), f"pyproject.toml contains forbidden placeholder token '{token}'"


def test_test_suite_zero_mock_ast_inspection() -> None:
    """Validate zero-mock compliance across this test suite via AST analysis."""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert (
                    "mock" not in alias.name.lower()
                ), f"Forbidden mock import in test suite: '{alias.name}'"
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert (
                "mock" not in mod.lower()
            ), f"Forbidden mock import in test suite from module: '{mod}'"

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_spycfit_ci_workflow.py ---
"""Zero-Mock Production Test Suite for CoChem-SpycFit CI Workflow (cochem_spycfit_ci.yml).

Defends the Execution Tier build system and Tripartite Architecture air-gap by validating:
- Physical existence of cochem_spycfit_ci.yml at CoChem-SpycFit/.github/workflows/cochem_spycfit_ci.yml.
- Strict UTF-8 encoding (no byte order mark) and Unix LF line endings.
- Exact compliance with SRS Document specifications for CI workflow configuration.
- YAML syntax validity and schema parsing using yaml.safe_load.
- Workflow name: "CoChem-SpycFit CI".
- Trigger conditions: push, pull_request.
- Job matrix and runner: air_gap_enforcement on ubuntu-latest.
- Steps structure: actions/checkout@v4 and Tripartite Air-Gap Enforcement Scan.
- Exact shell scan command logic for detecting *.h5, *.parquet, *.fit, *.lin, *.lock while pruning test_fixtures.
- Physical execution and simulation of the air-gap scan logic against real temporary directory structures.
- Strict exclusion of mock/placeholder tokens and AST inspection for zero-mock compliance.
"""

from __future__ import annotations

import ast
import datetime
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Dict, List, Set

import pytest
import yaml

# Repository paths
BASE_REPO_ROOT = Path(__file__).resolve().parent.parent
SPYCFIT_REPO_ROOT = BASE_REPO_ROOT.parent / "CoChem-SpycFit"
SPYCFIT_WORKFLOWS_DIR = SPYCFIT_REPO_ROOT / ".github" / "workflows"
SPYCFIT_CI_WORKFLOW_PATH = SPYCFIT_WORKFLOWS_DIR / "cochem_spycfit_ci.yml"

# Canonical SRS workflow content
CANONICAL_CI_WORKFLOW_CONTENT = (
    "name: CoChem-SpycFit CI\n"
    "on: [push, pull_request]\n"
    "\n"
    "jobs:\n"
    "  air_gap_enforcement:\n"
    "    runs-on: ubuntu-latest\n"
    "    steps:\n"
    "      - uses: actions/checkout@v4\n"
    "      - name: Tripartite Air-Gap Enforcement Scan\n"
    "        run: |\n"
    '          echo "Scanning for Tier 2/Tier 3 artifacts outside tests/ directory..."\n'
    '          matches=$(find . -type d -name "test_fixtures" -prune -o \\( -name "*.h5" -o -name "*.parquet" -o -name "*.fit" -o -name "*.lin" -o -name "*.lock" \\) -print)\n'
    '          if [ ! -z "$matches" ]; then\n'
    '            echo "CRITICAL: Tripartite Air-Gap Breach. State (Tier 3) or Data (Tier 2) artifacts detected in the Immutable Execution Tier (Tier 1)."\n'
    '            echo "$matches"\n'
    "            exit 1\n"
    "          fi\n"
    '          echo "Air-Gap intact."\n'
)

EXPECTED_WORKFLOW_NAME = "CoChem-SpycFit CI"
EXPECTED_ON_TRIGGERS = ["push", "pull_request"]
EXPECTED_JOB_NAME = "air_gap_enforcement"
EXPECTED_RUNS_ON = "ubuntu-latest"
EXPECTED_CHECKOUT_ACTION = "actions/checkout@v4"
EXPECTED_SCAN_STEP_NAME = "Tripartite Air-Gap Enforcement Scan"

RESTRICTED_EXTENSIONS = [".h5", ".parquet", ".fit", ".lin", ".lock"]
ALLOWED_CODE_EXTENSIONS = [".py", ".md", ".toml", ".yml", ".yaml", ".json", ".txt", ".sh", ".rs", ".cpp", ".c", ".h"]
WHITELISTED_FIXTURE_DIRNAME = "test_fixtures"

CRITICAL_BREACH_MESSAGE = (
    "CRITICAL: Tripartite Air-Gap Breach. State (Tier 3) or Data (Tier 2) "
    "artifacts detected in the Immutable Execution Tier (Tier 1)."
)
AIR_GAP_INTACT_MESSAGE = "Air-Gap intact."


def find_bash_executable() -> str | None:
    """Locate a valid bash binary on Windows or Unix for physical script execution."""
    git_bash = Path(r"C:\Program Files\Git\bin\bash.exe")
    if git_bash.exists():
        return str(git_bash)
    git_usr_bash = Path(r"C:\Program Files\Git\usr\bin\bash.exe")
    if git_usr_bash.exists():
        return str(git_usr_bash)
    which_bash = shutil.which("bash")
    if which_bash:
        return which_bash
    which_sh = shutil.which("sh")
    if which_sh:
        return which_sh
    return None


@pytest.fixture(scope="module")
def workflow_raw_bytes() -> bytes:
    """Fixture providing raw bytes of cochem_spycfit_ci.yml."""
    assert SPYCFIT_CI_WORKFLOW_PATH.exists(), (
        f"Missing workflow file at {SPYCFIT_CI_WORKFLOW_PATH}"
    )
    return SPYCFIT_CI_WORKFLOW_PATH.read_bytes()


@pytest.fixture(scope="module")
def workflow_content(workflow_raw_bytes: bytes) -> str:
    """Fixture providing decoded text content of cochem_spycfit_ci.yml."""
    return workflow_raw_bytes.decode("utf-8")


@pytest.fixture(scope="module")
def workflow_data(workflow_content: str) -> Dict[str, Any]:
    """Fixture providing parsed YAML dictionary."""
    data = yaml.safe_load(workflow_content)
    assert isinstance(data, dict), "Parsed YAML root must be a dictionary"
    return data


# ==============================================================================
# 1. Physical File Integrity & Line Endings
# ==============================================================================


def test_spycfit_ci_workflow_directory_exists() -> None:
    """Validate that .github/workflows directory exists in CoChem-SpycFit."""
    assert SPYCFIT_WORKFLOWS_DIR.exists(), f"Workflows directory missing: {SPYCFIT_WORKFLOWS_DIR}"
    assert SPYCFIT_WORKFLOWS_DIR.is_dir(), f"Workflows path must be a directory: {SPYCFIT_WORKFLOWS_DIR}"


def test_spycfit_ci_workflow_existence_and_size() -> None:
    """Validate that cochem_spycfit_ci.yml physically exists with valid size bounds."""
    assert SPYCFIT_CI_WORKFLOW_PATH.exists(), (
        f"Target file must exist: {SPYCFIT_CI_WORKFLOW_PATH}"
    )
    assert SPYCFIT_CI_WORKFLOW_PATH.is_file(), (
        f"Target path must be a regular file: {SPYCFIT_CI_WORKFLOW_PATH}"
    )
    size = SPYCFIT_CI_WORKFLOW_PATH.stat().st_size
    assert 200 < size < 5000, (
        f"cochem_spycfit_ci.yml size ({size} bytes) outside expected range (200, 5000)"
    )


def test_spycfit_ci_workflow_encoding_and_lf_line_endings(workflow_raw_bytes: bytes) -> None:
    """Validate strict UTF-8 encoding without BOM and Unix LF line endings."""
    assert not workflow_raw_bytes.startswith(b"\xef\xbb\xbf"), (
        "Target file must not contain a UTF-8 BOM"
    )
    assert b"\r\n" not in workflow_raw_bytes, "Target file contains Windows CRLF line endings"
    assert b"\r" not in workflow_raw_bytes, "Target file contains carriage return line endings"
    assert b"\n" in workflow_raw_bytes, "Target file must contain Unix LF line endings"
    assert workflow_raw_bytes.endswith(b"\n"), "Target file must terminate with a Unix LF newline"
    decoded = workflow_raw_bytes.decode("utf-8")
    assert len(decoded) > 0, "Target file content cannot be empty"


def test_spycfit_ci_workflow_canonical_content(workflow_content: str) -> None:
    """Validate that cochem_spycfit_ci.yml strictly matches the canonical SRS specification."""
    assert workflow_content == CANONICAL_CI_WORKFLOW_CONTENT, (
        f"cochem_spycfit_ci.yml content differs from canonical SRS specification:\n"
        f"--- Got ---\n{workflow_content}\n"
        f"--- Expected ---\n{CANONICAL_CI_WORKFLOW_CONTENT}"
    )


# ==============================================================================
# 2. YAML Schema & Workflow Structure
# ==============================================================================


def test_spycfit_ci_workflow_name(workflow_data: Dict[str, Any]) -> None:
    """Validate the workflow name is 'CoChem-SpycFit CI'."""
    assert "name" in workflow_data, "Missing 'name' field in workflow YAML"
    assert workflow_data["name"] == EXPECTED_WORKFLOW_NAME, (
        f"Expected workflow name '{EXPECTED_WORKFLOW_NAME}', got '{workflow_data['name']}'"
    )


def test_spycfit_ci_workflow_triggers(workflow_data: Dict[str, Any]) -> None:
    """Validate workflow trigger conditions contain push and pull_request."""
    # YAML parses `on: [push, pull_request]` as either key True/on or "on"
    trigger_key = "on" if "on" in workflow_data else True
    assert trigger_key in workflow_data, "Missing 'on' trigger specification in workflow YAML"
    triggers = workflow_data[trigger_key]
    assert isinstance(triggers, list), "Trigger specification must be a list"
    assert triggers == EXPECTED_ON_TRIGGERS, (
        f"Expected triggers {EXPECTED_ON_TRIGGERS}, got {triggers}"
    )


def test_spycfit_ci_workflow_jobs_structure(workflow_data: Dict[str, Any]) -> None:
    """Validate jobs dictionary structure and air_gap_enforcement job."""
    assert "jobs" in workflow_data, "Missing 'jobs' section in workflow YAML"
    jobs = workflow_data["jobs"]
    assert isinstance(jobs, dict), "'jobs' section must be a dictionary"
    assert EXPECTED_JOB_NAME in jobs, f"Missing '{EXPECTED_JOB_NAME}' job in jobs"

    job = jobs[EXPECTED_JOB_NAME]
    assert isinstance(job, dict), f"Job '{EXPECTED_JOB_NAME}' must be a dictionary"
    assert "runs-on" in job, f"Missing 'runs-on' in job '{EXPECTED_JOB_NAME}'"
    assert job["runs-on"] == EXPECTED_RUNS_ON, (
        f"Expected runs-on '{EXPECTED_RUNS_ON}', got '{job['runs-on']}'"
    )
    assert "steps" in job, f"Missing 'steps' in job '{EXPECTED_JOB_NAME}'"
    assert isinstance(job["steps"], list), "'steps' must be a list"
    assert len(job["steps"]) == 2, f"Expected exactly 2 steps, found {len(job['steps'])}"


def test_spycfit_ci_workflow_steps_detail(workflow_data: Dict[str, Any]) -> None:
    """Validate individual steps in air_gap_enforcement job."""
    steps = workflow_data["jobs"][EXPECTED_JOB_NAME]["steps"]

    # Step 1: Checkout
    step1 = steps[0]
    assert isinstance(step1, dict), "Step 1 must be a dictionary"
    assert "uses" in step1, "Step 1 must define 'uses'"
    assert step1["uses"] == EXPECTED_CHECKOUT_ACTION, (
        f"Expected Step 1 uses '{EXPECTED_CHECKOUT_ACTION}', got '{step1['uses']}'"
    )

    # Step 2: Tripartite Air-Gap Enforcement Scan
    step2 = steps[1]
    assert isinstance(step2, dict), "Step 2 must be a dictionary"
    assert "name" in step2, "Step 2 must define 'name'"
    assert step2["name"] == EXPECTED_SCAN_STEP_NAME, (
        f"Expected Step 2 name '{EXPECTED_SCAN_STEP_NAME}', got '{step2['name']}'"
    )
    assert "run" in step2, "Step 2 must define 'run' script"
    assert isinstance(step2["run"], str), "Step 2 'run' must be a string"


# ==============================================================================
# 3. Air-Gap Scan Script Logic & Token Verification
# ==============================================================================


def test_spycfit_ci_workflow_scan_script_syntax_and_commands(workflow_data: Dict[str, Any]) -> None:
    """Validate that the scan script contains exact required commands and syntax."""
    run_script = workflow_data["jobs"][EXPECTED_JOB_NAME]["steps"][1]["run"]

    assert "find ." in run_script, "Scan script must invoke 'find .'"
    assert '-type d -name "test_fixtures" -prune' in run_script, (
        "Scan script must prune directories named 'test_fixtures'"
    )

    # Check all 5 restricted extensions in find expression
    for ext in RESTRICTED_EXTENSIONS:
        assert f'"{ext}"' in run_script or f'"*{ext}"' in run_script, (
            f"Scan script missing filter for restricted extension '{ext}'"
        )

    # Check conditional failure and messages
    assert 'if [ ! -z "$matches" ]; then' in run_script, "Scan script missing match non-empty test"
    assert "CRITICAL: Tripartite Air-Gap Breach" in run_script, "Missing air-gap breach alert"
    assert "exit 1" in run_script, "Scan script must exit 1 on air-gap breach"
    assert "Air-Gap intact." in run_script, "Scan script must confirm 'Air-Gap intact.'"


def test_spycfit_ci_workflow_no_forbidden_tokens(workflow_content: str) -> None:
    """Validate that cochem_spycfit_ci.yml contains no mock, dummy, or synthetic tokens."""
    forbidden_tokens = [
        "TODO",
        "FIXME",
        "mock",
        "dummy",
        "fake",
        "synthetic",
        "stub",
        "placeholder",
        "TEMPORARY",
    ]
    for token in forbidden_tokens:
        assert token.lower() not in workflow_content.lower(), (
            f"cochem_spycfit_ci.yml contains forbidden placeholder token '{token}'"
        )


# ==============================================================================
# 4. Physical Simulation & Execution of Air-Gap Scan
# ==============================================================================


def execute_python_airgap_scan(root_dir: Path) -> List[Path]:
    """Pure Python implementation replicating the exact semantics of the find command.

    find . -type d -name "test_fixtures" -prune -o \\( -name "*.h5" -o -name "*.parquet" -o -name "*.fit" -o -name "*.lin" -o -name "*.lock" \\) -print
    """
    matches: List[Path] = []
    restricted_suffixes = {ext.lower() for ext in RESTRICTED_EXTENSIONS}

    for dirpath_str, dirnames, filenames in os.walk(root_dir):
        # Prune test_fixtures directory subtrees
        dirnames[:] = [d for d in dirnames if d != WHITELISTED_FIXTURE_DIRNAME]

        for fname in filenames:
            ext = Path(fname).suffix.lower()
            if ext in restricted_suffixes:
                full_path = Path(dirpath_str) / fname
                rel_path = full_path.relative_to(root_dir)
                matches.append(rel_path)

    return sorted(matches)


def test_python_airgap_scan_clean_workspace(tmp_path: Path) -> None:
    """Test Python airgap scanner on clean workspace with whitelisted fixtures."""
    src_dir = tmp_path / "src" / "cochem_spycfit"
    src_dir.mkdir(parents=True)
    (src_dir / "core.py").write_text("print('core')", encoding="utf-8")
    (src_dir / "pyproject.toml").write_text("[project]", encoding="utf-8")

    fixtures_dir = tmp_path / "tests" / "test_fixtures"
    fixtures_dir.mkdir(parents=True)
    (fixtures_dir / "reference.h5").write_bytes(b"DATA")
    (fixtures_dir / "table.parquet").write_bytes(b"DATA")
    (fixtures_dir / "fit_result.fit").write_bytes(b"DATA")
    (fixtures_dir / "lines.lin").write_bytes(b"DATA")
    (fixtures_dir / "build.lock").write_bytes(b"DATA")

    matches = execute_python_airgap_scan(tmp_path)
    assert len(matches) == 0, f"Expected 0 matches in clean workspace, got {matches}"


@pytest.mark.parametrize("allowed_ext", ALLOWED_CODE_EXTENSIONS)
def test_python_airgap_scan_ignores_allowed_extensions(tmp_path: Path, allowed_ext: str) -> None:
    """Test Python airgap scanner ignores standard source code and config files."""
    code_dir = tmp_path / "allowed_test"
    code_dir.mkdir(parents=True, exist_ok=True)
    (code_dir / f"test_module{allowed_ext}").write_text("allowed content", encoding="utf-8")

    matches = execute_python_airgap_scan(code_dir)
    assert len(matches) == 0, f"Expected 0 matches for allowed file '{allowed_ext}', got {matches}"


@pytest.mark.parametrize("restricted_ext", RESTRICTED_EXTENSIONS)
def test_python_airgap_scan_detects_breach(tmp_path: Path, restricted_ext: str) -> None:
    """Test Python airgap scanner detects each restricted extension outside test_fixtures."""
    test_dir = tmp_path / f"test_{restricted_ext.replace('.', '')}"
    test_dir.mkdir(parents=True, exist_ok=True)

    # Valid file in test_fixtures
    fixtures_dir = test_dir / "test_fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    (fixtures_dir / f"allowed{restricted_ext}").write_bytes(b"ALLOWED")

    # Breach file outside test_fixtures
    breach_file = test_dir / "src" / f"unauthorized{restricted_ext}"
    breach_file.parent.mkdir(parents=True, exist_ok=True)
    breach_file.write_bytes(b"BREACH")

    matches = execute_python_airgap_scan(test_dir)
    assert len(matches) == 1, f"Expected exactly 1 breach match for {restricted_ext}, got {matches}"
    assert matches[0] == Path("src") / f"unauthorized{restricted_ext}"


def test_python_airgap_scan_deeply_nested_fixtures_pruned(tmp_path: Path) -> None:
    """Test nested directories inside test_fixtures are properly pruned."""
    test_dir = tmp_path / "nested_fixtures"
    nested_fixture = test_dir / "tests" / "unit" / "test_fixtures" / "deep_sub" / "data"
    nested_fixture.mkdir(parents=True, exist_ok=True)
    (nested_fixture / "sample.h5").write_bytes(b"H5")
    (nested_fixture / "sample.parquet").write_bytes(b"PARQUET")
    (nested_fixture / "sample.fit").write_bytes(b"FIT")
    (nested_fixture / "sample.lin").write_bytes(b"LIN")
    (nested_fixture / "sample.lock").write_bytes(b"LOCK")

    matches = execute_python_airgap_scan(test_dir)
    assert len(matches) == 0, f"Expected 0 matches in nested test_fixtures, got {matches}"


def test_python_airgap_scan_multiple_breaches(tmp_path: Path) -> None:
    """Test Python airgap scanner detects multiple simultaneous breaches across directories."""
    test_dir = tmp_path / "multi_breach"
    test_dir.mkdir(parents=True, exist_ok=True)
    (test_dir / "root.h5").write_bytes(b"H5")
    (test_dir / "src").mkdir(parents=True, exist_ok=True)
    (test_dir / "src" / "state.parquet").write_bytes(b"PARQUET")
    (test_dir / "data").mkdir(parents=True, exist_ok=True)
    (test_dir / "data" / "output.fit").write_bytes(b"FIT")
    (test_dir / "data" / "lines.lin").write_bytes(b"LIN")
    (test_dir / "state.lock").write_bytes(b"LOCK")

    matches = execute_python_airgap_scan(test_dir)
    assert len(matches) == 5, f"Expected 5 breach matches, got {len(matches)}: {matches}"


def test_physical_bash_airgap_scan_execution(tmp_path: Path, workflow_data: Dict[str, Any]) -> None:
    """Physical execution of the exact shell script extracted from the YAML workflow."""
    bash_exec = find_bash_executable()
    if bash_exec is None:
        pytest.skip("Bash executable not available on host system for direct shell invocation")

    run_script = workflow_data["jobs"][EXPECTED_JOB_NAME]["steps"][1]["run"]

    # 1. Clean workspace test
    clean_workspace = tmp_path / "clean_ws"
    clean_workspace.mkdir(parents=True)
    (clean_workspace / "main.py").write_text("print('hello')", encoding="utf-8")
    (clean_workspace / "README.md").write_text("# Readme", encoding="utf-8")
    fixtures = clean_workspace / "tests" / "test_fixtures"
    fixtures.mkdir(parents=True)
    (fixtures / "allowed.h5").write_bytes(b"HDF5_DATA")
    (fixtures / "allowed.parquet").write_bytes(b"PARQUET_DATA")
    (fixtures / "allowed.fit").write_bytes(b"FIT_DATA")
    (fixtures / "allowed.lin").write_bytes(b"LIN_DATA")
    (fixtures / "allowed.lock").write_bytes(b"LOCK_DATA")

    clean_res = subprocess.run(
        [bash_exec, "-c", run_script],
        cwd=str(clean_workspace),
        capture_output=True,
        text=True,
    )
    assert clean_res.returncode == 0, (
        f"Clean workspace scan failed unexpectedly with exit code {clean_res.returncode}:\n"
        f"stdout: {clean_res.stdout}\nstderr: {clean_res.stderr}"
    )
    assert AIR_GAP_INTACT_MESSAGE in clean_res.stdout
    assert "CRITICAL: Tripartite Air-Gap Breach" not in clean_res.stdout

    # 2. Breach workspace test
    breach_workspace = tmp_path / "breach_ws"
    breach_workspace.mkdir(parents=True)
    (breach_workspace / "module.py").write_text("print('module')", encoding="utf-8")
    (breach_workspace / "rogue_state.h5").write_bytes(b"BREACH_HDF5")
    (breach_workspace / "data.parquet").write_bytes(b"BREACH_PARQUET")

    breach_res = subprocess.run(
        [bash_exec, "-c", run_script],
        cwd=str(breach_workspace),
        capture_output=True,
        text=True,
    )
    assert breach_res.returncode == 1, (
        f"Breached workspace scan should exit 1, got {breach_res.returncode}:\n"
        f"stdout: {breach_res.stdout}\nstderr: {breach_res.stderr}"
    )
    assert "CRITICAL: Tripartite Air-Gap Breach" in breach_res.stdout
    assert "rogue_state.h5" in breach_res.stdout
    assert "data.parquet" in breach_res.stdout
    assert AIR_GAP_INTACT_MESSAGE not in breach_res.stdout


# ==============================================================================
# 5. AST Zero-Mock Audit
# ==============================================================================


def test_test_suite_zero_mock_ast_inspection() -> None:
    """Validate zero-mock compliance across this test suite via AST analysis."""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "mock" not in alias.name.lower(), (
                    f"Forbidden mock import in test suite: '{alias.name}'"
                )
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert "mock" not in mod.lower(), (
                f"Forbidden mock import in test suite from module: '{mod}'"
            )

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.