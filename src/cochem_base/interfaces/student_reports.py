"""Student tables and diagrams from hash-bound computed observations.

This module performs analysis and presentation, never a quantum calculation.
Every displayed number is tied to an existing source artifact. Electronic-energy
Boltzmann weights are explicitly a model and are not Gibbs equilibrium fractions.
"""
from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import math
from pathlib import Path
from typing import Any

from cochem_base.core.cochem_constants import (
    AVOGADRO_CONSTANT, BOLTZMANN_CONSTANT_J_K, HARTREE_TO_JOULE,
)

HARTREE_KJ_MOL = HARTREE_TO_JOULE * AVOGADRO_CONSTANT / 1000
GAS_CONSTANT_KJ_MOL_K = BOLTZMANN_CONSTANT_J_K * AVOGADRO_CONSTANT / 1000
_SCHEMA = "cochem.student-report/1"
_MAX_RECORDS = 2000


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number.")
    return float(value)


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 500:
        raise ValueError(f"{name} must be a nonempty, bounded label.")
    return value


def _pointer(data: Any, pointer: str) -> Any:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("A source value requires an explicit JSON pointer.")
    for part in pointer[1:].split("/"):
        key = part.replace("~1", "/").replace("~0", "~")
        data = data[int(key)] if isinstance(data, list) else data[key]
    return data


def verify_source(source: dict, *, expected: Any = None) -> tuple[dict, Any]:
    """Verify retained bytes and, when specified, the exact observed JSON value."""
    if not isinstance(source, dict):
        raise ValueError("A retained source receipt is required.")
    path = Path(source.get("path", "")).expanduser()
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("The source must be a regular retained artifact below 32 MiB.")
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if source.get("sha256") != digest:
        raise ValueError("The source artifact checksum does not match its receipt.")
    receipt = {"filename": path.name, "sha256": digest, "size_bytes": len(raw)}
    value = None
    if "pointer" in source:
        try:
            data = json.loads(raw)
            value = _pointer(data, source["pointer"])
            json.dumps(data, allow_nan=False)
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            raise ValueError("The source does not contain the requested strict JSON observation.") from exc
        receipt["pointer"] = source["pointer"]
        if expected is not None and value != expected:
            raise ValueError("The observation differs from its retained source artifact.")
    elif expected is not None:
        raise ValueError("An observation requires a source JSON pointer.")
    return receipt, value


def _records(records: list[dict]) -> None:
    if not isinstance(records, list) or not 1 <= len(records) <= _MAX_RECORDS:
        raise ValueError(f"Supply between 1 and {_MAX_RECORDS} computed observations.")
    if not all(isinstance(item, dict) for item in records):
        raise ValueError("Every observation must be an object.")


def _comparison_key(record: dict, energy_kind: str) -> str:
    method = record.get("method")
    state = record.get("electronic_state")
    composition = record.get("composition")
    parameterized = (isinstance(method, dict) and method.get("engine") == "xtb"
                     and method.get("basis") is None
                     and method.get("basis_convention") == "native parameterized model; no Gaussian AO basis")
    if not isinstance(method, dict) or not method.get("engine") or not method.get("method") or (not method.get("basis") and not parameterized):
        raise ValueError("Comparable observations require complete engine, method and basis definitions.")
    if (not isinstance(state, dict) or type(state.get("charge")) is not int
            or type(state.get("multiplicity")) is not int or state["multiplicity"] < 1):
        raise ValueError("Comparable observations require explicit charge and multiplicity.")
    _text(composition, "composition")
    key = {"method": method, "electronic_state": state, "composition": composition, "energy_kind": energy_kind}
    if energy_kind == "gibbs_free_energy":
        key["temperature_kelvin"] = _finite(record.get("temperature_kelvin"), "free-energy temperature")
        key["standard_state"] = _text(record.get("standard_state"), "standard state")
    return json.dumps(key, sort_keys=True, allow_nan=False)


def build_isomer_report(observations: list[dict], *, temperature_kelvin: float = 298.15,
                        energy_kind: str = "electronic_energy", populations: bool = True) -> dict:
    """Compare computed isomers and optionally their explicitly defined weights.

    A Gibbs report requires values evaluated at the selected temperature and a
    common standard state. Population use also requires retained minimum evidence;
    a starting structure or converged SCF alone does not establish an isomer minimum.
    """
    _records(observations)
    temperature = _finite(temperature_kelvin, "temperature")
    if temperature <= 0:
        raise ValueError("Temperature must be greater than zero kelvin.")
    if energy_kind not in {"electronic_energy", "gibbs_free_energy"}:
        raise ValueError("Select electronic_energy or gibbs_free_energy explicitly.")
    if type(populations) is not bool:
        raise ValueError("populations must be a boolean.")
    validated, keys, labels, sources = [], set(), set(), []
    for item in observations:
        label = _text(item.get("label"), "isomer label")
        if label in labels:
            raise ValueError("Isomer labels must be unique.")
        labels.add(label)
        if item.get("validation_status") != "computed" or item.get("energy_kind") != energy_kind:
            raise ValueError("Every isomer requires a computed observation of the selected energy kind.")
        energy = _finite(item.get("energy_hartree"), "energy_hartree")
        receipt, _ = verify_source(item.get("source"), expected=energy)
        keys.add(_comparison_key(item, energy_kind))
        degeneracy = item.get("degeneracy", 1)
        if type(degeneracy) is not int or not 1 <= degeneracy <= 1_000_000:
            raise ValueError("Isomer degeneracy must be a positive integer.")
        if populations:
            if item.get("minimum_verified") is not True:
                raise ValueError("Population analysis requires verified minimum structures, not starting geometries.")
            minimum, evidence = verify_source(item.get("minimum_source"))
            if not minimum.get("pointer") or not isinstance(evidence, list) or not evidence:
                raise ValueError("Minimum evidence must reference the complete retained vibrational-frequency array.")
            frequencies = [_finite(value, "minimum frequency") for value in evidence]
            if min(frequencies) <= 0:
                raise ValueError("An imaginary or zero vibrational frequency prevents minimum-based populations.")
            sources.append(minimum)
            if energy_kind == "gibbs_free_energy" and degeneracy > 1 and item.get("degeneracy_included_in_energy") is not False:
                raise ValueError("State explicitly that Gibbs energies do not already include the supplied degeneracy.")
        validated.append({"label": label, "energy_hartree": energy, "degeneracy": degeneracy})
        sources.append(receipt)
    if len(keys) != 1:
        raise ValueError("Isomer comparison requires identical composition, electronic state, method, basis and thermodynamic state.")
    if energy_kind == "gibbs_free_energy" and not math.isclose(observations[0]["temperature_kelvin"], temperature, rel_tol=0, abs_tol=1e-8):
        raise ValueError("The Gibbs energies were not evaluated at the selected population temperature.")
    minimum = min(item["energy_hartree"] for item in validated)
    for item in validated:
        item["relative_energy_kj_mol"] = (item["energy_hartree"] - minimum) * HARTREE_KJ_MOL
    if populations:
        # Log-sum-exp retains normalization for widely separated states and high
        # degeneracies. Every energy remains native; no clipping changes the data.
        logs = [math.log(item["degeneracy"]) - item["relative_energy_kj_mol"] / (GAS_CONSTANT_KJ_MOL_K * temperature)
                for item in validated]
        peak = max(logs)
        weights = [math.exp(value - peak) for value in logs]
        total = math.fsum(weights)
        for item, weight in zip(validated, weights, strict=True):
            item["population_fraction"] = weight / total
    columns = ["label", "energy_hartree", "relative_energy_kj_mol", "degeneracy"]
    if populations:
        columns.append("population_fraction")
    scope = ("Gibbs-energy Boltzmann fractions within the supplied minimum set and common standard state; "
             "completeness and equilibration are not established." if energy_kind == "gibbs_free_energy" else
             "Electronic-energy Boltzmann model weights within the supplied minimum set; vibrational, rotational, "
             "translational entropy and zero-point energy are absent. These are not thermodynamic equilibrium populations.")
    if not populations:
        scope = "Native energy differences for the supplied comparable structures. A converged electronic result alone " \
                "does not establish a minimum, a unique isomer, a complete search or thermodynamic populations."
    else:
        scope += " Entries are assumed to represent distinct states; duplicate or equivalent structures must be removed before interpreting isomer populations."
    report = {"schema_version": _SCHEMA, "report_type": "isomers", "title": "Isomer energy differences and populations" if populations else "Structure energy differences",
              "columns": columns, "rows": validated, "sources": sources, "energy_kind": energy_kind,
              "temperature_kelvin": temperature, "comparison": json.loads(next(iter(keys))), "scope": scope,
              "plot": {"kind": "bars", "x": "label", "y": "relative_energy_kj_mol", "y_label": "Relative energy (kJ mol⁻¹)"}}
    if populations:
        report["population_plot"] = {"kind": "bars", "x": "label", "y": "population_fraction", "y_label": "Population fraction"}
    return report


def build_pes_report(points: list[dict], *, coordinate_label: str = "Coordinate", coordinate_unit: str = "angstrom") -> dict:
    """Display measured scan points; absent/failed points stay visibly absent."""
    _records(points)
    coordinate_label = _text(coordinate_label, "coordinate label")
    if coordinate_unit not in {"angstrom", "degree", "bohr"}:
        raise ValueError("A scan coordinate requires an explicit supported unit.")
    rows, sources, keys, seen = [], [], set(), set()
    for item in points:
        coordinate = _finite(item.get("coordinate"), "scan coordinate")
        if coordinate in seen:
            raise ValueError("Scan coordinates must be unique.")
        seen.add(coordinate)
        status = item.get("status")
        if status not in {"computed", "failed", "not_run"}:
            raise ValueError("Each scan point must explicitly state computed, failed or not_run.")
        row = {"coordinate": coordinate, "status": status, "energy_hartree": None, "relative_energy_kj_mol": None}
        if status == "computed":
            energy = _finite(item.get("energy_hartree"), "scan energy")
            receipt, _ = verify_source(item.get("source"), expected=energy)
            sources.append(receipt)
            keys.add(_comparison_key(item, "electronic_energy"))
            row["energy_hartree"] = energy
        else:
            if item.get("energy_hartree") is not None:
                raise ValueError("A failed or unrun point cannot supply a measured energy.")
            row["reason"] = _text(item.get("reason"), "unavailable point reason")
        rows.append(row)
    if len(keys) > 1:
        raise ValueError("All measured PES points must have the same method, composition and electronic state.")
    energies = [row["energy_hartree"] for row in rows if row["status"] == "computed"]
    if not energies:
        raise ValueError("A PES diagram requires at least one actual computed point.")
    reference = min(energies)
    for row in rows:
        if row["status"] == "computed":
            row["relative_energy_kj_mol"] = (row["energy_hartree"] - reference) * HARTREE_KJ_MOL
    rows.sort(key=lambda item: item["coordinate"])
    return {"schema_version": _SCHEMA, "report_type": "pes", "title": "Measured potential-energy scan",
            "columns": ["coordinate", "status", "energy_hartree", "relative_energy_kj_mol", "reason"],
            "rows": rows, "sources": sources, "coordinate_label": coordinate_label, "coordinate_unit": coordinate_unit,
            "reference_energy_hartree": reference, "comparison": json.loads(next(iter(keys))),
            "scope": "Native electronic energies at the measured coordinates. Lines only guide the eye between adjacent "
                     "computed points; gaps are unmeasured. The lowest sampled energy is not proof of a minimum or barrier.",
            "plot": {"kind": "points", "x": "coordinate", "y": "relative_energy_kj_mol",
                     "x_label": f"{coordinate_label} ({coordinate_unit})", "y_label": "Relative electronic energy (kJ mol⁻¹)"}}


def build_bond_report(atoms: list[str], coordinates_angstrom: list[list[float]], bonds: list[dict], *,
                      analysis_kind: str, source: dict) -> dict:
    """Render an authentic named bond-index table without renaming its basis."""
    names = {"wiberg_nao": "Wiberg indices in the natural atomic orbital basis",
             "wiberg_lowdin": "Wiberg indices in the Löwdin orthogonalized AO basis",
             "mayer": "Mayer bond indices"}
    if analysis_kind not in names:
        raise ValueError("The exact bond analysis and atomic-orbital basis must be identified.")
    if not isinstance(atoms, list) or not 1 <= len(atoms) <= 2000:
        raise ValueError("Bond analysis requires the complete ordered atom labels.")
    labels = [_text(label, "atom label") for label in atoms]
    if len(coordinates_angstrom) != len(atoms) or any(len(position) != 3 for position in coordinates_angstrom):
        raise ValueError("Bond diagram requires one Cartesian position per atom.")
    coordinates = [[_finite(value, "coordinate") for value in row] for row in coordinates_angstrom]
    if not isinstance(bonds, list) or len(bonds) > 20000:
        raise ValueError("The bond table exceeds the bounded display size.")
    receipt, _ = verify_source(source, expected=bonds)
    pointer = source.get("pointer", "")
    if not pointer.endswith("/bonds"):
        raise ValueError("Bond evidence must reference its authentic named analysis block.")
    raw = Path(source["path"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
        raise ValueError("Bond evidence changed while its geometry binding was verified.")
    retained = json.loads(raw)
    block = _pointer(retained, pointer[:-6]) if pointer[:-6] else retained
    if (not isinstance(block, dict) or block.get("atoms") != labels
            or block.get("coordinates_angstrom") != coordinates
            or block.get("analysis_kind") != analysis_kind):
        raise ValueError("Atom labels, geometry or analysis basis differ from the retained bond evidence.")
    rows, seen = [], set()
    for item in bonds:
        a, b = item.get("atom_i"), item.get("atom_j")
        if type(a) is not int or type(b) is not int or not 0 <= a < len(atoms) or not 0 <= b < len(atoms) or a == b:
            raise ValueError("Bond atom indices must refer to distinct zero-based atoms.")
        pair = tuple(sorted((a, b)))
        if pair in seen:
            raise ValueError("Bond analysis contains duplicate atom pairs.")
        seen.add(pair)
        value = _finite(item.get("value"), "bond analysis value")
        if analysis_kind.startswith("wiberg_") and value < 0:
            raise ValueError("A Wiberg index from a squared orthogonal density cannot be negative.")
        rows.append({"atom_i": a, "atom_j": b, "atom_i_label": f"{a + 1} {labels[a]}",
                     "atom_j_label": f"{b + 1} {labels[b]}", "value": value,
                     "unit": "dimensionless"})
    return {"schema_version": _SCHEMA, "report_type": "bond_analysis", "title": names[analysis_kind],
            "analysis_kind": analysis_kind, "atoms": labels, "coordinates_angstrom": coordinates,
            "columns": ["atom_i_label", "atom_j_label", "value", "unit"], "rows": rows, "sources": [receipt],
            "scope": "Values retain their provider-defined analysis and basis. Atom-pair display does not reconstruct orbital "
                     "shapes or infer missing indices. Mayer, Löwdin Wiberg and NAO Wiberg are distinct quantities.",
            "plot": {"kind": "bonds"}}



def build_nbo_report(transitions: list[dict], *, source: dict) -> dict:
    """Render authentic NBO donor/acceptor data as orbital-labelled interactions.

    This is an import/presentation contract, not a licensed NBO implementation.
    Multi-center orbitals remain orbital nodes; they are not collapsed to guessed
    atom pairs or rendered as computed three-dimensional orbital surfaces.
    """
    _records(transitions)
    receipt, _ = verify_source(source, expected=transitions)
    rows = []
    for item in transitions:
        donor = _text(item.get("donor"), "NBO donor orbital")
        acceptor = _text(item.get("acceptor"), "NBO acceptor orbital")
        energy = _finite(item.get("stabilization_kcal_mol"), "NBO second-order stabilization")
        if energy < 0:
            raise ValueError("NBO second-order stabilization energy must be nonnegative.")
        rows.append({"donor": donor, "acceptor": acceptor, "stabilization_kcal_mol": energy})
    return {"schema_version": _SCHEMA, "report_type": "nbo", "title": "Natural Bond Orbital donor–acceptor analysis",
        "columns": ["donor", "acceptor", "stabilization_kcal_mol"], "rows": rows, "sources": [receipt],
        "scope": "Authentic retained NBO second-order perturbation entries, with their original donor and acceptor labels. "
                 "The diagram shows those reported interactions; it does not reconstruct orbital shapes or compute missing entries.",
        "plot": {"kind": "orbital_interactions"}}

def _escaped(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _table(report: dict) -> str:
    columns = report["columns"]
    header = "".join(f"<th>{_escaped(item)}</th>" for item in columns)
    rows = []
    for row in report["rows"]:
        cells = []
        for key in columns:
            value = row.get(key)
            cells.append(f"<td>{_escaped('Unavailable' if value is None else format(value, '.10g') if isinstance(value, float) else value)}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table>"



def _scientific_plot_svg(report: dict, plot: dict) -> str:
    """Use Matplotlib's scientific SVG renderer with genuine missing-data gaps."""
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_svg import FigureCanvasSVG
    import numpy as np

    figure = Figure(figsize=(9, 4.8), layout="constrained")
    FigureCanvasSVG(figure)
    axis = figure.subplots()
    rows = report["rows"]
    if plot["kind"] == "bars":
        positions = list(range(len(rows)))
        values = [row[plot["y"]] for row in rows]
        axis.bar(positions, values, color="#3569a0")
        axis.set_xticks(positions)
        axis.set_xticklabels([str(row[plot["x"]]) for row in rows], parse_math=False,
                            rotation=35 if len(rows) > 6 else 0, ha="right" if len(rows) > 6 else "center")
        axis.set_ylim(bottom=0)
    else:
        positions = [row[plot["x"]] for row in rows]
        # NaN means unavailable solely inside the plotting renderer. It is never
        # serialized into the scientific report or mistaken for a measured zero.
        values = [row[plot["y"]] if row.get(plot["y"]) is not None else np.nan for row in rows]
        axis.plot(positions, values, marker="o", color="#3569a0", linestyle="--")
        for position, row in zip(positions, rows, strict=True):
            if row.get(plot["y"]) is None:
                axis.annotate("Unmeasured", xy=(position, .03), xycoords=("data", "axes fraction"),
                              rotation=90, ha="center", va="bottom", fontsize=8, parse_math=False)
        axis.set_xlabel(plot["x_label"], parse_math=False)
    axis.set_ylabel(plot["y_label"], parse_math=False)
    axis.tick_params(labelsize=10)
    axis.grid(axis="y", alpha=.2)
    buffer = io.StringIO()
    figure.savefig(buffer, format="svg", metadata={"Date": None})
    rendered = buffer.getvalue()
    # Embed only the SVG element in the self-contained HTML page; the standalone
    # file uses the same complete element, containing internal glyph paths only.
    return rendered[rendered.index("<svg"):].strip()

def report_svg(report: dict, *, population: bool = False) -> str:
    """Standalone SVG uses escaped labels and contains no script or links."""
    if report.get("schema_version") != _SCHEMA:
        raise ValueError("Unsupported student report schema.")
    plot = report.get("population_plot") if population else report["plot"]
    if not plot:
        raise ValueError("This report has no population plot.")
    if plot["kind"] in {"bars", "points"}:
        return _scientific_plot_svg(report, plot)
    title = plot.get("y_label", report["title"])
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="480" viewBox="0 0 900 480" role="img">',
             f"<title>{_escaped(title)}</title>", '<rect width="900" height="480" fill="white"/>']
    if plot["kind"] == "orbital_interactions":
        donors = list(dict.fromkeys(row["donor"] for row in report["rows"]))
        acceptors = list(dict.fromkeys(row["acceptor"] for row in report["rows"]))
        donor_y = {label: 60 + (index+.5) * 350 / len(donors) for index, label in enumerate(donors)}
        acceptor_y = {label: 60 + (index+.5) * 350 / len(acceptors) for index, label in enumerate(acceptors)}
        for row in report["rows"]:
            y1, y2 = donor_y[row["donor"]], acceptor_y[row["acceptor"]]
            parts.append(f'<line x1="290" y1="{y1:.4f}" x2="610" y2="{y2:.4f}" stroke="#46739b"/>')
            parts.append(f'<text x="450" y="{(y1+y2)/2-7:.4f}" text-anchor="middle" font-size="12">{row["stabilization_kcal_mol"]:.5g} kcal/mol</text>')
        for label,y in donor_y.items():
            parts.append(f'<text x="280" y="{y+4:.4f}" text-anchor="end" font-size="12">{_escaped(label)}</text>')
        for label,y in acceptor_y.items():
            parts.append(f'<text x="620" y="{y+4:.4f}" font-size="12">{_escaped(label)}</text>')
        parts.append('<text x="200" y="30" text-anchor="middle">Donor orbitals</text><text x="720" y="30" text-anchor="middle">Acceptor orbitals</text>')
    elif plot["kind"] == "bonds":
        positions = report["coordinates_angstrom"]
        # Pick the pair of Cartesian axes with the greatest total span, so a
        # planar molecule in yz is not collapsed onto the x-axis.
        spans = [max(row[a] for row in positions) - min(row[a] for row in positions) for a in range(3)]
        axes = sorted(range(3), key=lambda a: spans[a], reverse=True)[:2]
        xy = [[row[a] for a in axes] for row in positions]
        limits = [(min(p[a] for p in xy), max(p[a] for p in xy)) for a in range(2)]
        scale = min(680 / max(limits[0][1] - limits[0][0], 1e-9), 320 / max(limits[1][1] - limits[1][0], 1e-9))
        screen = [(450 + (p[0] - sum(limits[0]) / 2) * scale,
                   230 - (p[1] - sum(limits[1]) / 2) * scale) for p in xy]
        for row in report["rows"]:
            a, b = screen[row["atom_i"]], screen[row["atom_j"]]
            parts.append(f'<line x1="{a[0]:.4f}" y1="{a[1]:.4f}" x2="{b[0]:.4f}" y2="{b[1]:.4f}" stroke="#46739b" stroke-width="2"/>')
            parts.append(f'<text x="{(a[0]+b[0])/2:.4f}" y="{(a[1]+b[1])/2-8:.4f}" text-anchor="middle" font-size="13">{row["value"]:.5g}</text>')
        for index, (x, y) in enumerate(screen):
            parts.extend([f'<circle cx="{x:.4f}" cy="{y:.4f}" r="18" fill="white" stroke="#253548"/>',
                          f'<text x="{x:.4f}" y="{y+5:.4f}" text-anchor="middle" font-size="12">{_escaped(str(index+1)+" "+report["atoms"][index])}</text>'])
        parts.append('<text x="450" y="460" text-anchor="middle" font-size="12">Cartesian projection; displayed edges are the supplied analysis entries</text>')
    else:
        raise ValueError("Unsupported report diagram kind.")
    parts.append("</svg>")
    return "".join(parts)


def report_html(report: dict) -> str:
    """Embed complete tables, standalone diagrams and exact provenance receipts."""
    json.dumps(report, allow_nan=False)
    if report.get("schema_version") != _SCHEMA:
        raise ValueError("Unsupported student report schema.")
    diagrams = report_svg(report)
    if "population_plot" in report:
        diagrams += report_svg(report, population=True)
    receipts = "".join(f'<li>{_escaped(source["filename"])}: <code>{_escaped(source["sha256"])}</code>'
                       f' {_escaped(source.get("pointer", ""))}</li>' for source in report["sources"])
    return ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<title>' + _escaped(report["title"]) + '</title><style>body{font-family:system-ui,sans-serif;margin:2rem;max-width:1100px}'
            'table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccd4dc;padding:.5rem;text-align:left}'
            'svg{max-width:100%;height:auto}code{overflow-wrap:anywhere}</style></head><body><h1>'
            + _escaped(report["title"]) + '</h1><p>' + _escaped(report["scope"]) + '</p>' + _table(report)
            + diagrams + '<h2>Retained source receipts</h2><ul>' + receipts + '</ul></body></html>')


def export_report(report: dict, directory: str | Path) -> dict[str, str]:
    """Create a fresh self-contained report package and exact source snapshots."""
    json.dumps(report, allow_nan=False)
    from cochem.core.context import assert_writable_path
    target = Path(directory).expanduser()
    if any(component.is_symlink() for component in (target, *target.parents)):
        raise ValueError("Report destination cannot traverse a symlink.")
    assert_writable_path(target.resolve())
    # Validate/render before creating output so malformed input leaves no partial
    # report. Provenance is included in JSON/HTML rather than external URL links.
    rendered = report_html(report)
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(report["columns"])
    for row in report["rows"]:
        values = []
        for key in report["columns"]:
            value = row.get(key, "")
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                value = "'" + value
            values.append(value)
        writer.writerow(values)
    target.mkdir(parents=True, exist_ok=False)
    documents = {"report.json": json.dumps(report, indent=2, allow_nan=False) + "\n",
                 "report.html": rendered, "table.csv": buffer.getvalue(), "diagram.svg": report_svg(report)}
    if "population_plot" in report:
        documents["populations.svg"] = report_svg(report, population=True)
    paths = {}
    for name, text in documents.items():
        path = target / name
        with path.open("x", encoding="utf-8", newline="") as stream:
            stream.write(text)
        paths[name] = str(path.resolve())
    manifest = {"schema_version": "cochem.student-report-artifacts/1", "files": [
        {"filename": name, "sha256": hashlib.sha256((target / name).read_bytes()).hexdigest(),
         "size_bytes": (target / name).stat().st_size} for name in documents]}
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    paths["manifest.json"] = str((target / "manifest.json").resolve())
    return paths


def discover_observations(root: str | Path) -> list[dict]:
    """Recover native energy records for GUI comparison, without invented defaults.

    Method, basis, charge, multiplicity and composition must be present in the
    result or its retained validated request. Missing context leaves the result
    available for inspection but excludes it from scientific comparison.
    """
    from collections import Counter
    directory = Path(root).resolve(strict=True)
    if not directory.is_dir():
        raise ValueError("Choose a retained calculation artifact directory.")
    paths = sorted(directory.rglob("result.json"))
    if len(paths) > _MAX_RECORDS:
        raise ValueError("Too many result files in the selected artifact directory.")
    observations = []
    for path in paths:
        if path.is_symlink() or path.stat().st_size > 32 * 1024 * 1024:
            continue
        try:
            raw = path.read_bytes()
            native = json.loads(raw)
            energy = _finite(native.get("energy_hartree"), "native energy")
            if native.get("converged") is not True and not (native.get("status") == "complete" and native.get("scf", {}).get("converged") is True):
                continue
            config = {}
            for parent in (path.parent, *path.parents):
                if not parent.is_relative_to(directory):
                    break
                candidates = [parent / "validated-job.json", parent / "request.json"]
                for candidate in candidates:
                    if candidate.is_file() and not candidate.is_symlink() and candidate.stat().st_size <= 2 * 1024 * 1024:
                        parsed = json.loads(candidate.read_bytes())
                        if isinstance(parsed, dict):
                            config = parsed.get("calculation", parsed)
                            if not isinstance(config, dict):
                                config = {}
                            break
                if config:
                    break
            molecule = native.get("molecule", config.get("molecule", {}))
            symbols = native.get("nuclides") or molecule.get("isotope_symbols") or native.get("elements", molecule.get("symbols"))
            isotopes = molecule.get("isotopes")
            if (symbols and not native.get("nuclides") and not molecule.get("isotope_symbols")
                    and isinstance(isotopes, list) and len(isotopes) == len(symbols)):
                symbols = [f"{mass}{symbol}" if mass is not None else symbol
                           for symbol, mass in zip(symbols, isotopes, strict=True)]
            if not symbols:
                from cochem_base.geometry.nuclide_geometry import parse_geometry_identity
                geometry = config.get("geometry_xyz", config.get("geometry"))
                if isinstance(geometry, str):
                    symbols = parse_geometry_identity(geometry).nuclides
            native_method = native.get("method", {})
            method = native_method.get("name") if isinstance(native_method, dict) else native_method
            basis = native_method.get("basis") if isinstance(native_method, dict) else config.get("basis_set")
            method = method or config.get("method")
            basis = basis or config.get("basis_set") or config.get("basis")
            charge = molecule.get("charge", config.get("charge"))
            multiplicity = molecule.get("multiplicity", config.get("multiplicity"))
            if not symbols or not method or not basis or type(charge) is not int or type(multiplicity) is not int:
                continue
            label = path.parent.relative_to(directory).as_posix()
            item = {"label": label if label != "." else directory.name, "energy_hartree": energy,
                    "energy_kind": "electronic_energy", "validation_status": "computed", "degeneracy": 1,
                    "minimum_verified": False,
                    "source": {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "pointer": "/energy_hartree"},
                    "method": {"engine": native.get("engine", config.get("engine")), "method": method, "basis": basis},
                    "electronic_state": {"charge": charge, "multiplicity": multiplicity},
                    "composition": json.dumps(dict(sorted(Counter(symbols).items())), sort_keys=True)}
            # Native ORCA/CFOUR spectra use harmonic_frequencies_cm1. A JSON
            # optimization flag plus positive numbers cannot establish minimum
            # provenance: recheck the actual retained force-Hessian and gradient.
            frequencies = native.get("harmonic_frequencies_cm1")
            if native.get("engine") in {"orca", "cfour"} and isinstance(frequencies, list) and frequencies:
                from cochem_base.spectroscopy.artifacts import load_hessian_artifact, _receipt_file
                receipt = native.get("hessian_bundle_artifact", native.get("hessian_artifact"))
                if isinstance(receipt, dict):
                    for base in (path.parent, path.parent.parent, path.parent.parent.parent):
                        if not base.is_relative_to(directory):
                            break
                        try:
                            tensor_path = _receipt_file(base, receipt)
                            tensor = load_hessian_artifact(tensor_path, native_result_path=path)
                            if tensor.qualification.get("minimum_verified") is True:
                                item["minimum_verified"] = True
                                item["minimum_source"] = {**item["source"], "pointer": "/harmonic_frequencies_cm1"}
                            break
                        except (ValueError, OSError, KeyError, TypeError):
                            continue
            _comparison_key(item, "electronic_energy")
            observations.append(item)
        except (ValueError, KeyError, TypeError, OSError):
            continue
    # TOPOS publishes one canonical parsed record with individual authentic
    # attempts/candidates. Import its exact immutable values, rather than using
    # a CSV's rounded display values or treating starting XYZ frames as minima.
    for path in sorted(directory.rglob("operation.json")):
        if path.is_symlink() or path.stat().st_size > 32 * 1024 * 1024:
            continue
        try:
            raw = path.read_bytes()
            wrapper = json.loads(raw)
            if wrapper.get("module_id") != "topos" or wrapper.get("status") != "completed":
                continue
            result = wrapper.get("result", {})
            record = result.get("record", {})
            if record.get("schema_version") != "topos/0.1.0":
                continue
            attempts = {item["attempt_id"]: item for item in record.get("attempts", [])}
            request = record.get("request", {})
            native_root = path.parent / "provider-runs" / record.get("run_id", "")
            if not native_root.is_dir() or native_root.is_symlink():
                continue
            verified_attempts = set()

            def verify_attempt_artifacts(current: dict) -> None:
                identifier = current.get("attempt_id")
                if identifier in verified_attempts:
                    return
                if (current.get("metadata", {}).get("execution_kind") != "real"
                        or not current.get("engine_version") or not current.get("metadata", {}).get("executable_sha256")
                        or not current.get("artifacts")):
                    raise ValueError("TOPOS native derivative source is incomplete.")
                for artifact in current["artifacts"]:
                    relative = Path(artifact["path"])
                    artifact_path = native_root / relative
                    if (relative.is_absolute() or ".." in relative.parts or artifact_path.is_symlink()
                            or not artifact_path.resolve().is_relative_to(native_root.resolve())
                            or not artifact_path.is_file() or artifact_path.stat().st_size != artifact["size_bytes"]
                            or hashlib.sha256(artifact_path.read_bytes()).hexdigest() != artifact["sha256"]):
                        raise ValueError("TOPOS native source artifact integrity failed.")
                verified_attempts.add(identifier)

            for index, candidate in enumerate(record.get("candidates", [])):
                attempt = attempts.get(candidate.get("attempt_id"), {})
                if (attempt.get("converged") is not True or attempt.get("metadata", {}).get("execution_kind") != "real"
                        or not attempt.get("engine_version") or not attempt.get("metadata", {}).get("executable_sha256")):
                    continue
                verify_attempt_artifacts(attempt)
                energy = _finite(candidate.get("energy_hartree"), "TOPOS candidate energy")
                quantities = attempt.get("quantities", [])
                if not any(q.get("name") == "electronic_energy" and q.get("units") == "hartree"
                           and q.get("value") == energy and q.get("attempt_id") == attempt["attempt_id"]
                           and q.get("validity") == "validated-for-protocol" for q in quantities):
                    continue
                molecule = candidate.get("molecule", request.get("molecule", {}))
                symbols = molecule.get("symbols")
                charge, multiplicity = molecule.get("charge"), molecule.get("multiplicity")
                method = request.get("method")
                basis = request.get("basis")
                if not symbols or not method or (not basis and request.get("engine") != "xtb") or type(charge) is not int or type(multiplicity) is not int:
                    continue
                isotopes = molecule.get("isotopes")
                if isinstance(isotopes, list) and len(isotopes) == len(symbols):
                    symbols = [f"{mass}{symbol}" if mass is not None else symbol
                               for symbol, mass in zip(symbols, isotopes, strict=True)]
                degeneracy = _finite(candidate.get("degeneracy", 1), "TOPOS degeneracy")
                if not degeneracy.is_integer() or not 1 <= degeneracy <= 1_000_000:
                    continue
                item = {"label": path.parent.relative_to(directory).as_posix() + ": " + str(candidate["candidate_id"]),
                    "energy_hartree": energy, "energy_kind": "electronic_energy", "validation_status": "computed",
                    "minimum_verified": False, "degeneracy": int(degeneracy),
                    "source": {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
                               "pointer": f"/result/record/candidates/{index}/energy_hartree"},
                    "method": {"engine": request.get("engine"), "method": method, "basis": basis,
                               "comparison_protocol": candidate.get("comparison_protocol")},
                    "electronic_state": {"charge": charge, "multiplicity": multiplicity},
                    "composition": json.dumps(dict(sorted(Counter(symbols).items())), sort_keys=True)}
                if basis is None and request.get("engine") == "xtb":
                    item["method"]["basis_convention"] = "native parameterized model; no Gaussian AO basis"
                analysis = candidate.get("metadata", {}).get("frequency_analysis", {})
                frequencies = analysis.get("frequencies_cm1")
                geometry_identity = {key: value for key, value in molecule.items() if key != "name"}
                geometry_digest = hashlib.sha256(json.dumps(geometry_identity, sort_keys=True,
                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()
                if (attempt.get("metadata", {}).get("result_kind") == "physical-hessian-thermochemistry"
                        and attempt.get("metadata", {}).get("analysis") == analysis
                        and analysis.get("validity") == "harmonic-minimum-within-thresholds"
                        and analysis.get("stationary") is True and not analysis.get("constraints")
                        and analysis.get("geometry_sha256") == geometry_digest
                        and analysis.get("subspace") == "full-cartesian"
                        and isinstance(frequencies, list) and frequencies
                        and len(frequencies) == analysis.get("vibrational_modes")
                        and len(frequencies) + analysis.get("removed_rigid_modes", 0) == 3 * len(symbols)
                        and all(_finite(value, "frequency") > 0 for value in frequencies)
                        and attempt.get("metadata", {}).get("derivative_attempt_ids")):
                    for derivative_id in attempt["metadata"]["derivative_attempt_ids"]:
                        derivative = attempts.get(derivative_id, {})
                        if (derivative.get("converged") is not True or derivative.get("engine") != attempt.get("engine")
                                or derivative.get("method") != attempt.get("method")
                                or derivative.get("engine_version") != attempt.get("engine_version")
                                or derivative.get("metadata", {}).get("executable_sha256") != attempt["metadata"]["executable_sha256"]):
                            raise ValueError("TOPOS Hessian derivative method or execution provenance changed.")
                        verify_attempt_artifacts(derivative)
                    item["minimum_verified"] = True
                    item["minimum_source"] = {**item["source"],
                        "pointer": f"/result/record/candidates/{index}/metadata/frequency_analysis/frequencies_cm1"}
                _comparison_key(item, "electronic_energy")
                observations.append(item)
                thermal = candidate.get("metadata", {}).get("thermochemistry", {})
                if (item["minimum_verified"] and thermal.get("status") == "completed"
                        and attempt.get("metadata", {}).get("thermochemistry") == thermal
                        and thermal.get("gibbs_hartree") == candidate.get("gibbs_hartree")
                        and thermal.get("electronic_energy_hartree") == energy
                        and thermal.get("geometry_sha256") == analysis.get("geometry_sha256")
                        and isinstance(thermal.get("standard_state"), dict) and thermal["standard_state"]):
                    gibbs = _finite(candidate["gibbs_hartree"], "TOPOS Gibbs energy")
                    temperature = _finite(thermal.get("temperature_k"), "TOPOS temperature")
                    standard_state = json.dumps(thermal["standard_state"], sort_keys=True, allow_nan=False)
                    free = {**item, "label": item["label"] + " (Gibbs)", "energy_kind": "gibbs_free_energy",
                        "energy_hartree": gibbs, "temperature_kelvin": temperature,
                        "standard_state": standard_state, "degeneracy_included_in_energy": False,
                        "source": {**item["source"], "pointer": f"/result/record/candidates/{index}/gibbs_hartree"}}
                    _comparison_key(free, "gibbs_free_energy")
                    observations.append(free)
        except (ValueError, KeyError, TypeError, OSError):
            continue
    return observations


def load_reports(root: str | Path) -> list[dict]:
    """Collect verified exported reports and genuine TORQ scan receipts for GUI."""
    directory = Path(root).resolve(strict=True)
    reports = []
    paths = sorted(directory.rglob("report.json"))
    if len(paths) > _MAX_RECORDS:
        raise ValueError("Too many report files in the selected artifact directory.")
    for path in paths:
        if path.is_symlink() or path.stat().st_size > 32 * 1024 * 1024:
            continue
        try:
            manifest_path = path.parent / "manifest.json"
            manifest = json.loads(manifest_path.read_bytes())
            records = {item["filename"]: item for item in manifest["files"]}
            if manifest.get("schema_version") != "cochem.student-report-artifacts/1":
                continue
            for name, item in records.items():
                artifact = path.parent / name
                if Path(name).name != name or artifact.is_symlink() or not artifact.is_file():
                    raise ValueError("Unsafe or absent report artifact.")
                if artifact.stat().st_size != item["size_bytes"] or hashlib.sha256(artifact.read_bytes()).hexdigest() != item["sha256"]:
                    raise ValueError("Report artifact integrity failed.")
            report = json.loads(path.read_bytes())
            report_html(report)
            reports.append(report)
        except (ValueError, KeyError, TypeError, OSError):
            continue
    operation_paths = {path.parent: path for path in directory.rglob("operation.json")}
    progress = {}
    for path in sorted(directory.rglob("scan-progress-*.json")):
        if path.parent not in operation_paths:
            progress[path.parent] = path
    operation_paths.update(progress)
    if len(operation_paths) > _MAX_RECORDS:
        raise ValueError("Too many scientific operations in the selected artifact directory.")
    for path in sorted(operation_paths.values()):
        if path.is_symlink() or path.stat().st_size > 32 * 1024 * 1024:
            continue
        try:
            operation = json.loads(path.read_bytes())
            if operation.get("module_id") == "torq" and operation.get("operation") == "research_scan":
                from .torq_research import report_from_scan
                reports.append(report_from_scan(operation, path.parent))
            elif operation.get("module_id") == "torq" and operation.get("operation") == "wiberg_lowdin":
                native = operation["result"]
                source_path = path.parent / native["analysis_path"]
                if source_path.parent != path.parent or source_path.is_symlink():
                    raise ValueError("Unsafe bond analysis receipt path.")
                reports.append(build_bond_report(native["atoms"], native["coordinates_angstrom"], native["bonds"],
                    analysis_kind="wiberg_lowdin", source={"path": str(source_path),
                    "sha256": native["analysis_sha256"], "pointer": "/bonds"}))
            elif operation.get("module_id") == "torq" and operation.get("operation") in {"nbo_analysis", "wiberg_nao"}:
                native = operation["result"]
                if operation.get("status") not in {"completed", "partial"} or native.get("analysis_performed") is not True:
                    continue
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                if operation["operation"] == "nbo_analysis":
                    if native.get("analysis_kind") != "nbo" or native.get("units", {}).get("stabilization") != "kcal/mol":
                        raise ValueError("NBO receipt must identify its actual analysis and native stabilization units.")
                    reports.append(build_nbo_report(native["transitions"], source={"path": str(path), "sha256": digest,
                        "pointer": "/result/transitions"}))
                else:
                    if native.get("analysis_kind") != "wiberg_nao" or native.get("units", {}).get("bond_index") != "dimensionless":
                        raise ValueError("NAO Wiberg receipt must identify its actual analysis basis and units.")
                    reports.append(build_bond_report(native["atoms"], native["coordinates_angstrom"], native["bonds"],
                        analysis_kind="wiberg_nao", source={"path": str(path), "sha256": digest, "pointer": "/result/bonds"}))
        except (ValueError, KeyError, TypeError, OSError):
            continue
    # Native results should be useful immediately after the authenticated result
    # package is retrieved. Group only identical scientific comparison protocols;
    # unmatched methods, isotopes, states and thermal references remain separate.
    groups = {}
    for observation in discover_observations(directory):
        if Path(observation["source"]["path"]).name != "operation.json":
            continue
        try:
            key = _comparison_key(observation, observation["energy_kind"])
            groups.setdefault(key, []).append(observation)
        except (ValueError, KeyError, TypeError):
            continue
    for values in groups.values():
        try:
            kind = values[0]["energy_kind"]
            temperature = values[0].get("temperature_kelvin", 298.15)
            qualified = all(item.get("minimum_verified") is True for item in values)
            reports.append(build_isomer_report(values, energy_kind=kind,
                temperature_kelvin=temperature, populations=qualified))
        except (ValueError, KeyError, TypeError, OSError):
            continue
    unique = {}
    for report in reports:
        key = hashlib.sha256(json.dumps(report, sort_keys=True, allow_nan=False).encode()).hexdigest()
        unique.setdefault(key, report)
    return list(unique.values())
