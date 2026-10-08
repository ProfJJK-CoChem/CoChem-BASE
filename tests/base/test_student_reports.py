"""Analytical presentation contracts; these tests do not simulate engine acceptance."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

from cochem_base.interfaces.student_reports import (
    GAS_CONSTANT_KJ_MOL_K, HARTREE_KJ_MOL, build_bond_report, build_isomer_report,
    build_pes_report, export_report, load_reports, report_html, report_svg,
)
from cochem_base.interfaces.torq_research import scan_points_request, validate_scan_options


def observation(tmp_path, label, energy=0., *, kind="electronic_energy", degeneracy=1):
    # Explicit mathematical observations test normalization/unit conversion only.
    # Real provider acceptance is a separate genuine-engine execution.
    source = tmp_path / f"{len(list(tmp_path.glob('*.json')))}.json"
    data = {"energy_hartree": energy, "frequencies_cm1": [100., 200., 300.]}
    source.write_text(json.dumps(data))
    receipt = {"path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    result = {"label": label, "energy_hartree": energy, "energy_kind": kind,
        "validation_status": "computed", "minimum_verified": True, "degeneracy": degeneracy,
        "method": {"engine": "analytical-test", "method": "mathematical normalization", "basis": "none"},
        "electronic_state": {"charge": 0, "multiplicity": 1}, "composition": "same-test-system",
        "source": {**receipt, "pointer": "/energy_hartree"},
        "minimum_source": {**receipt, "pointer": "/frequencies_cm1"}}
    if kind == "gibbs_free_energy":
        result.update(temperature_kelvin=298.15, standard_state="1 bar", degeneracy_included_in_energy=False)
    return result


def test_equal_energy_degeneracy_normalization(tmp_path):
    report = build_isomer_report([observation(tmp_path, "a"), observation(tmp_path, "b", degeneracy=3)])
    assert [row["population_fraction"] for row in report["rows"]] == pytest.approx([.25, .75])
    assert "not thermodynamic equilibrium" in report["scope"]


def test_exact_boltzmann_ratio_and_unit_conversion(tmp_path):
    delta = GAS_CONSTANT_KJ_MOL_K * 298.15 * math.log(2) / HARTREE_KJ_MOL
    report = build_isomer_report([observation(tmp_path, "a"), observation(tmp_path, "b", delta)])
    assert report["rows"][1]["relative_energy_kj_mol"] == pytest.approx(GAS_CONSTANT_KJ_MOL_K * 298.15 * math.log(2))
    assert [row["population_fraction"] for row in report["rows"]] == pytest.approx([2/3, 1/3])


def test_large_separation_normalization_is_finite(tmp_path):
    report = build_isomer_report([observation(tmp_path, "a", -100.), observation(tmp_path, "b", 100.)])
    assert report["rows"][0]["population_fraction"] == 1.
    assert report["rows"][1]["population_fraction"] == 0.


@pytest.mark.parametrize("mutation", ["energy", "method", "state", "minimum", "negative_frequency", "degeneracy", "temperature"])
def test_invalid_or_incomparable_populations_rejected(tmp_path, mutation):
    first, second = observation(tmp_path, "a"), observation(tmp_path, "b")
    temperature = 298.15
    if mutation == "energy": second["energy_hartree"] = .5
    if mutation == "method": second["method"]["basis"] = "different"
    if mutation == "state": second["electronic_state"]["charge"] = 1
    if mutation == "minimum": second["minimum_verified"] = False
    if mutation == "degeneracy": second["degeneracy"] = True
    if mutation == "temperature": temperature = 0
    if mutation == "negative_frequency":
        path = Path(second["source"]["path"])
        data = json.loads(path.read_text()); data["frequencies_cm1"][0] = -10
        path.write_text(json.dumps(data)); digest = hashlib.sha256(path.read_bytes()).hexdigest()
        second["source"]["sha256"] = second["minimum_source"]["sha256"] = digest
    with pytest.raises(ValueError):
        build_isomer_report([first, second], temperature_kelvin=temperature)


def test_gibbs_temperature_and_state_are_explicit(tmp_path):
    first, second = observation(tmp_path, "a", kind="gibbs_free_energy"), observation(tmp_path, "b", kind="gibbs_free_energy")
    report = build_isomer_report([first, second], energy_kind="gibbs_free_energy")
    assert "Gibbs-energy" in report["scope"]
    with pytest.raises(ValueError, match="temperature"):
        build_isomer_report([first, second], energy_kind="gibbs_free_energy", temperature_kelvin=300.)
    second["standard_state"] = "1 mol/L"
    with pytest.raises(ValueError, match="identical"):
        build_isomer_report([first, second], energy_kind="gibbs_free_energy")


def test_source_mutation_is_not_accepted(tmp_path):
    record = observation(tmp_path, "a")
    Path(record["source"]["path"]).write_text('{"energy_hartree": 100}')
    with pytest.raises(ValueError, match="checksum"):
        build_isomer_report([record], populations=False)


def test_unknown_scan_gap_does_not_join_computed_points(tmp_path):
    points = []
    for coordinate, energy in [(2., 0.), (4., .001)]:
        record = observation(tmp_path, str(coordinate), energy)
        record.update(coordinate=coordinate, status="computed")
        points.append(record)
    points.insert(1, {"coordinate": 3., "status": "not_run", "reason": "No calculation submitted."})
    report = build_pes_report(points)
    assert report["rows"][1]["energy_hartree"] is None
    assert '<line ' not in report_svg(report)
    assert "not proof of a minimum" in report["scope"]


def test_safe_labels_and_csv_formula_escaping(tmp_path):
    report = build_isomer_report([observation(tmp_path, '<script>alert("x")</script>'), observation(tmp_path, '=1+1')], populations=False)
    rendered = report_html(report)
    assert '<script>' not in rendered
    assert '&lt;script&gt;' in rendered
    output = tmp_path / "export"
    paths = export_report(report, output)
    assert "'=1+1" in Path(paths["table.csv"]).read_text()
    assert load_reports(output) == [report]
    with pytest.raises(FileExistsError): export_report(report, output)
    Path(paths["table.csv"]).write_text("altered")
    assert load_reports(output) == []


def test_bond_indices_keep_basis_and_exact_receipt(tmp_path):
    bonds = [{"atom_i": 0, "atom_j": 1, "value": .9}]
    path = tmp_path / "analysis.json"; path.write_text(json.dumps({"bonds": bonds,
        "atoms": ["H", "H"], "coordinates_angstrom": [[0,0,0], [0,0,.74]], "analysis_kind": "wiberg_lowdin"}))
    report = build_bond_report(["H", "H"], [[0,0,0], [0,0,.74]], bonds, analysis_kind="wiberg_lowdin",
        source={"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "pointer": "/bonds"})
    assert "Löwdin" in report["title"] and "NAO Wiberg" in report["scope"]
    assert '<line ' in report_svg(report)
    with pytest.raises(ValueError):
        build_bond_report(["H", "H"], [[0,0,0], [0,0,.74]], bonds, analysis_kind="NBO-Wiberg", source={})
    with pytest.raises(ValueError, match="geometry"):
        build_bond_report(["H", "H"], [[0,0,0], [0,0,.8]], bonds, analysis_kind="wiberg_lowdin",
            source={"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "pointer": "/bonds"})


def scan_options():
    return {"method": {"name":"hf", "basis":"sto-3g"}, "charge":0, "multiplicity":1,
        "fragments":[[0,1],[2,3]], "distances_angstrom":[3., 4.]}


def test_scan_exact_rigid_translation_preserves_monomer(tmp_path):
    geometry = [[0,0,0],[0,0,.74],[3,0,0],[3,0,.74]]
    points = scan_points_request(["H"]*4, geometry, scan_options())
    assert points[1]["geometry_angstrom"] == [[0.,0.,0.],[0.,0.,.74],[4.,0.,0.],[4.,0.,.74]]
    assert points[1]["request"]["properties"] == ["energy"]
    assert points[1]["request"]["settings"]["check_stability"] is True


@pytest.mark.parametrize("field,value", [("fragments",[[0,1],[1,2,3]]), ("distances_angstrom",[3.,3.]),
    ("multiplicity",3), ("cores",3), ("memory_mb",8192)])
def test_scan_rejects_unsafe_or_unimplemented_requests(field, value):
    options = scan_options(); options[field] = value
    with pytest.raises(ValueError): validate_scan_options(options, 4)


def test_authentic_nbo_uses_orbital_nodes_and_preserves_units(tmp_path):
    from cochem_base.interfaces.student_reports import build_nbo_report
    transitions = [{"donor": "LP (1) O 1", "acceptor": "BD* (1) O 2-H 3", "stabilization_kcal_mol": 1.2}]
    path=tmp_path/'nbo-analysis.json'; path.write_text(json.dumps({"transitions": transitions}))
    report=build_nbo_report(transitions, source={"path":str(path),"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"pointer":"/transitions"})
    assert report['rows'][0]['stabilization_kcal_mol']==1.2
    assert 'Donor orbitals' in report_svg(report)
    assert 'not reconstruct orbital shapes' in report['scope']
