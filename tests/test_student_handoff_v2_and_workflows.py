"""Zero-mock tests for CoChem-BASE generalized student workflow, v1/v2 handoff interop,
course workflows, SCRIBE QCSchema integrity, module manifest, and repo hygiene.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
import zipfile

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER_SRC = REPO_ROOT.parent / "cochem_workstation_job_runner" / "src"
PILOT_V1_ETHANOL_ZIP = Path(
    r"C:\Users\ansac\Documents\Codex\2026-11-20\in\outputs\CoChem-ethanol-44929944530-1.zip"
)
PILOT_V1_ETHANOL_SHA256 = "089fca78acec2545cb672608e428a4c16db819ba03edccd67c63e829c919aa95"

from scripts import manage_modules
from student import conformers, handoff
from ui.voila_layout.scribe_gui_dashboard import ScribeDashboardGUI


def _import_runner_intake():
    if str(RUNNER_SRC) not in sys.path:
        sys.path.insert(0, str(RUNNER_SRC))
    from cochem_runner import student_handoff_intake

    return student_handoff_intake


# ---------------------------------------------------------------------------
# 1. Real v1 ethanol pilot ZIP verification via pure-stdlib student/handoff.py CLI
# ---------------------------------------------------------------------------


def test_real_v1_ethanol_pilot_zip_passes_handoff_cli(tmp_path: Path) -> None:
    assert PILOT_V1_ETHANOL_ZIP.is_file(), f"Missing real v1 pilot ZIP at {PILOT_V1_ETHANOL_ZIP}"
    assert handoff.sha256_file(PILOT_V1_ETHANOL_ZIP) == PILOT_V1_ETHANOL_SHA256

    stage_root = tmp_path / "received"
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "student" / "handoff.py"),
            str(PILOT_V1_ETHANOL_ZIP),
            "--expected-sha256",
            PILOT_V1_ETHANOL_SHA256,
            "--stage",
            str(stage_root),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0, f"handoff.py CLI failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    receipt = json.loads(proc.stdout)
    assert receipt["schema"] == handoff.SCHEMA_V1
    assert receipt["candidate_count"] == 4
    assert receipt["selected"] == "isomers/crest-003.xyz"
    staged_dir = stage_root / PILOT_V1_ETHANOL_SHA256
    assert (staged_dir / "handoff.json").is_file()
    assert (staged_dir / "refined.xyz").is_file()


# ---------------------------------------------------------------------------
# 2. Round-trip v2 cross-repo interop: CoChem-BASE -> cochem_workstation_job_runner
# ---------------------------------------------------------------------------


def test_v2_roundtrip_interop_chem312_team2_team4_and_chem490(tmp_path: Path) -> None:
    intake = _import_runner_intake()
    commit_sha = "74e2811a4d3747468e6ea195e2000fa0d0c8deac"

    # Case A: CHEM 312 Team 2 fluorinated neutral species (HF + CH3F -> fluoroformate-like CHFO2, 18e + 16e = 34e even)
    f_xyz = (
        "5\n"
        "-213.4567890000 AIMNet2 + B3LYP-D3BJ/def2-TZVP\n"
        "C  0.000000  0.000000  0.000000\n"
        "O  1.200000  0.000000  0.000000\n"
        "O -0.650000  1.150000  0.000000\n"
        "F -0.680000 -1.120000  0.000000\n"
        "H -1.610000  1.020000  0.000000\n"
    )
    team2_manifest = handoff.StudentHandoffV2Manifest(
        workflow_type="conformer",
        input_name="team2_fluoroformic_acid.xyz",
        charge=0,
        multiplicity=1,
        method="AIMNet2 + B3LYP-D3BJ",
        basis="def2-TZVP",
        solvation="pcm",
        solvent_name="water",
        hessian_calculated=True,
        n_imaginary_modes=0,
        course_id="CHEM312",
        collaborator_institution="Tennessee Tech University",
        target_continuation="workstation",
        starting_xyz="input.xyz",
        primary_xyz="refined.xyz",
        ensemble_xyz="crest_conformers.xyz",
        candidate_count=2,
        selected="isomers/crest-001.xyz",
        student_id="chem312_team2",
        repository="ProfJJK-CoChem/CoChem-BASE",
        commit=commit_sha,
        run_id="51002001",
        attempt="1",
        metadata={"energy_hartree": -213.456789, "team": "Team 2"},
    )
    z2, s2, sha2, _ = handoff.build_student_handoff_v2_zip(
        {
            "input.xyz": f_xyz,
            "refined.xyz": f_xyz,
            "crest_conformers.xyz": f_xyz + f_xyz,
            "isomers/crest-001.xyz": f_xyz,
            "isomers/crest-002.xyz": f_xyz,
        },
        team2_manifest,
        tmp_path / "team2",
    )
    verified_runner_2 = intake.verify_handoff_zip(z2, sidecar_path=s2, destination=tmp_path / "runner_stage")
    assert verified_runner_2.schema == "cochem.student-handoff/2"
    assert verified_runner_2.archive_sha256 == sha2
    assert verified_runner_2.course_id == "CHEM312"
    assert verified_runner_2.collaborator_institution == "Tennessee Tech University"
    assert "F" in verified_runner_2.elements
    assert verified_runner_2.hessian_calculated is True
    assert verified_runner_2.n_imaginary_modes == 0

    # Case B: CHEM 312 Team 4 anionic bicarbonate/carbonate reaction profile (HCO3-, Q=-1, 32e even)
    anionic_xyz = (
        "5\n"
        "-264.1234560000 AIMNet2 + DF-wB97X-D3/def2-TZVPP\n"
        "C  0.000000  0.000000  0.000000\n"
        "O  1.260000  0.000000  0.000000\n"
        "O -0.630000  1.090000  0.000000\n"
        "O -0.680000 -1.160000  0.000000\n"
        "H -1.620000 -0.950000  0.000000\n"
    )
    team4_manifest = handoff.StudentHandoffV2Manifest(
        workflow_type="rxn_profile",
        input_name="team4_anionic_carbonate.xyz",
        charge=-1,
        multiplicity=1,
        method="AIMNet2 + DF-wB97X-D3",
        basis="def2-TZVPP",
        solvation="pcm",
        solvent_name="water",
        hessian_calculated=True,
        n_imaginary_modes=1,
        course_id="CHEM312",
        collaborator_institution="Tennessee Tech University",
        target_continuation="colab_gpu",
        starting_xyz="input.xyz",
        primary_xyz="ts_guess.xyz",
        ensemble_xyz="rxn_profile.xyz",
        candidate_count=3,
        selected="ts_guess.xyz",
        student_id="chem312_team4",
        repository="ProfJJK-CoChem/CoChem-BASE",
        commit=commit_sha,
        run_id="51002004",
        attempt="1",
        metadata={"energy_hartree": -264.123456, "imag_freq_cm1": -385.4, "team": "Team 4"},
    )
    z4, s4, sha4, _ = handoff.build_student_handoff_v2_zip(
        {
            "input.xyz": anionic_xyz,
            "ts_guess.xyz": anionic_xyz,
            "rxn_profile.xyz": anionic_xyz + anionic_xyz + anionic_xyz,
            "rxn_energies.json": json.dumps({"barrier_kcal_mol": 14.2}),
        },
        team4_manifest,
        tmp_path / "team4",
    )
    verified_runner_4 = intake.verify_handoff_zip(z4, sidecar_path=s4, destination=tmp_path / "runner_stage")
    assert verified_runner_4.archive_sha256 == sha4
    assert verified_runner_4.workflow_type == "rxn_profile"
    assert verified_runner_4.charge == -1
    assert verified_runner_4.n_imaginary_modes == 1
    assert verified_runner_4.target_continuation == "colab_gpu"

    # Case C: CHEM 490 rotational geometry comparison (SO2, neutral singlet, 32e)
    so2_xyz = (
        "3\n"
        "-548.123456 CCSD/cc-pVTZ\n"
        "S  0.000000  0.000000  0.362100\n"
        "O  0.000000  1.240700 -0.362100\n"
        "O  0.000000 -1.240700 -0.362100\n"
    )
    chem490_manifest = handoff.StudentHandoffV2Manifest(
        workflow_type="geom_comparison",
        input_name="chem490_so2_rotational.xyz",
        charge=0,
        multiplicity=1,
        method="CCSD",
        basis="cc-pVTZ",
        solvation="gas",
        solvent_name=None,
        hessian_calculated=False,
        n_imaginary_modes=None,
        course_id="CHEM490",
        collaborator_institution="Tennessee Tech University",
        target_continuation="workstation",
        starting_xyz="input.xyz",
        primary_xyz="optimized.xyz",
        ensemble_xyz=None,
        candidate_count=1,
        selected="optimized.xyz",
        student_id="chem490_student1",
        repository="ProfJJK-CoChem/CoChem-BASE",
        commit=commit_sha,
        run_id="51004901",
        attempt="1",
        metadata={"rotational_constants_mhz": [60778.52, 10318.06, 8820.61]},
    )
    z490, s490, sha490, _ = handoff.build_student_handoff_v2_zip(
        {
            "input.xyz": so2_xyz,
            "optimized.xyz": so2_xyz,
        },
        chem490_manifest,
        tmp_path / "chem490",
    )
    verified_runner_490 = intake.verify_handoff_zip(z490, sidecar_path=s490, destination=tmp_path / "runner_stage")
    assert verified_runner_490.archive_sha256 == sha490
    assert verified_runner_490.course_id == "CHEM490"
    assert verified_runner_490.workflow_type == "geom_comparison"
    assert verified_runner_490.hessian_calculated is False
    assert verified_runner_490.n_imaginary_modes is None
    assert "S" in verified_runner_490.elements


def test_v2_handoff_rejects_texas_tech_bad_spin_and_zip_slip(tmp_path: Path) -> None:
    with pytest.raises(handoff.HandoffValidationError, match="Tennessee Tech University"):
        handoff.validate_collaborator_institution("Texas Tech University")
    with pytest.raises(handoff.HandoffValidationError, match="Tennessee Tech University"):
        handoff.validate_collaborator_institution("TTU")

    # Bad electron parity: H2O (10e) with charge=-1 -> 11e cannot be singlet (mult=1)
    h2o = "3\nwater\nO 0 0 0\nH 0 0.75 0.58\nH 0 -0.75 0.58\n"
    with pytest.raises(handoff.HandoffValidationError):
        handoff.parse_xyz_frames(h2o, charge=-1, multiplicity=1)

    # Zip-slip archive rejected before reading handoff.json
    bad_zip = tmp_path / "zipslip.zip"
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("../escape.txt", "pwned")
    with pytest.raises(handoff.HandoffSecurityError):
        handoff.verify(bad_zip)


# ---------------------------------------------------------------------------
# 3. student/conformers.py MLFF charge/heteroatom routing & CREST 3.0.2 flags
# ---------------------------------------------------------------------------


def test_conformers_rejects_neutral_mace_on_charged_or_f_s_and_routes_to_aimnet2() -> None:
    # Anion Q=-1 with H/C/O -> must reject MACE and auto-route to AIMNet2
    assert conformers.requires_charge_aware_aimnet2(["C", "O", "O", "O", "H"], charge=-1, multiplicity=1) is True
    assert conformers.select_mlff_backend(["C", "O", "O", "O", "H"], charge=-1, multiplicity=1, requested="auto") == "aimnet2"
    with pytest.raises(ValueError, match="Neutral-only MACE-OFF24 is forbidden"):
        conformers.select_mlff_backend(["C", "O", "O", "O", "H"], charge=-1, multiplicity=1, requested="mace")

    # Neutral fluorinated molecule (F) -> must reject MACE and auto-route to AIMNet2
    assert conformers.requires_charge_aware_aimnet2(["C", "H", "H", "H", "F"], charge=0, multiplicity=1) is True
    assert conformers.select_mlff_backend(["C", "H", "H", "H", "F"], charge=0, multiplicity=1, requested="auto") == "aimnet2"
    with pytest.raises(ValueError, match="Neutral-only MACE-OFF24 is forbidden"):
        conformers.select_mlff_backend(["C", "H", "H", "H", "F"], charge=0, multiplicity=1, requested="mace")

    # Neutral sulfur-containing molecule (S) -> must reject MACE and auto-route to AIMNet2
    assert conformers.requires_charge_aware_aimnet2(["S", "O", "O"], charge=0, multiplicity=1) is True
    assert conformers.select_mlff_backend(["S", "O", "O"], charge=0, multiplicity=1, requested="auto") == "aimnet2"
    with pytest.raises(ValueError, match="Neutral-only MACE-OFF24 is forbidden"):
        conformers.select_mlff_backend(["S", "O", "O"], charge=0, multiplicity=1, requested="mace")

    # Neutral singlet H/C/N/O -> allows explicit MACE or AIMNet2
    assert conformers.requires_charge_aware_aimnet2(["C", "C", "O", "H"], charge=0, multiplicity=1) is False
    assert conformers.select_mlff_backend(["C", "C", "O", "H"], charge=0, multiplicity=1, requested="mace") == "mace"
    assert conformers.select_mlff_backend(["C", "C", "O", "H"], charge=0, multiplicity=1, requested="aimnet2") == "aimnet2"

    # CREST 3.0.2 command preserves --legacy --xnam --nocross and propagates --chrg/--uhf
    argv = conformers.build_crest_argv("/opt/crest", "/opt/xtb", charge=-1, multiplicity=2, cores=2, nci=True)
    assert "--legacy" in argv
    assert "--xnam" in argv and argv[argv.index("--xnam") + 1] == "/opt/xtb"
    assert "--nocross" in argv
    assert "--nci" in argv
    assert argv[argv.index("--chrg") + 1] == "-1"
    assert argv[argv.index("--uhf") + 1] == "1"


# ---------------------------------------------------------------------------
# 4. scribe_gui_dashboard.py::export_qcschema() zero-fabrication integrity
# ---------------------------------------------------------------------------


def test_scribe_export_qcschema_refuses_fabrication_and_marks_pending(tmp_path: Path) -> None:
    empty_dashboard = ScribeDashboardGUI(telemetry_data={})
    empty_out = empty_dashboard.export_qcschema(tmp_path / "empty_qcschema.json")
    empty_rec = json.loads(empty_out.read_text(encoding="utf-8"))

    assert empty_rec["model"]["method"] is None
    assert empty_rec["model"]["basis"] is None
    assert empty_rec["model"]["method"] != "wB97M-V"
    assert empty_rec["model"]["basis"] != "def2-TZVP"
    assert empty_rec["properties"]["rotational_constants"] is None
    assert empty_rec["properties"]["rotational_constants_effective"] is None
    assert empty_rec["properties"]["vibrational_corrections"] is None
    assert empty_rec["properties"]["scf_dipole_moment"] is None
    assert empty_rec["properties"]["scf_dipole_moment_magnitude"] is None
    assert empty_rec["success"] is False
    assert empty_rec["status"] == "PENDING"
    assert set(empty_rec["missing_fields"]) == {"molecule.geometry", "model.method", "model.basis"}

    # Complete authentic telemetry succeeds honestly without fabricating missing dipole vector components
    complete_dashboard = ScribeDashboardGUI(
        telemetry_data={
            "geometry": "O 0.0 0.0 0.1178\nH 0.0 0.7555 -0.4712\nH 0.0 -0.7555 -0.4712",
            "method": "CCSD(T)",
            "basis_set": "cc-pVTZ",
            "a_e": 27858.123,
            "b_e": 14520.456,
            "c_e": 9540.789,
            "total_dipole": 1.8546,
        }
    )
    full_out = complete_dashboard.export_qcschema(tmp_path / "full_qcschema.json")
    full_rec = json.loads(full_out.read_text(encoding="utf-8"))
    assert full_rec["success"] is True
    assert full_rec["status"] == "COMPLETE"
    assert full_rec["model"] == {"method": "CCSD(T)", "basis": "cc-pVTZ"}
    assert full_rec["properties"]["rotational_constants"] == [27858.123, 14520.456, 9540.789]
    assert full_rec["properties"]["scf_dipole_moment"] is None
    assert full_rec["properties"]["scf_dipole_moment_magnitude"] == pytest.approx(1.8546)


# ---------------------------------------------------------------------------
# 5. Course & controller workflow YAML validity and zero push/cron hygiene
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "workflow_name",
    [
        "student_conformers.yml",
        "06_aimnet2_neb_pyscf_rxn_profile.yml",
        "04_crest_nci_dimer_bsse.yml",
        "course_project_access.yml",
    ],
)
def test_course_and_controller_workflows_have_zero_push_and_zero_cron(workflow_name: str) -> None:
    wf_path = REPO_ROOT / ".github" / "workflows" / workflow_name
    assert wf_path.is_file(), f"Missing workflow: {wf_path}"
    data = yaml.safe_load(wf_path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    # PyYAML parses unquoted `on:` as boolean True
    triggers = data.get("on", data.get(True))
    assert isinstance(triggers, dict), f"Workflow {workflow_name} missing `on:` mapping"
    assert "workflow_dispatch" in triggers, f"Workflow {workflow_name} must allow workflow_dispatch"
    assert "push" not in triggers, f"Workflow {workflow_name} must NOT trigger on push"
    assert "schedule" not in triggers, f"Workflow {workflow_name} must NOT have a schedule/cron trigger"
    if workflow_name != "course_project_access.yml":
        assert set(triggers.keys()) == {"workflow_dispatch"}, f"{workflow_name} must be workflow_dispatch-only"


def test_zero_schedule_crons_anywhere_in_github_workflows() -> None:
    for wf in sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml")):
        data = yaml.safe_load(wf.read_text(encoding="utf-8"))
        triggers = data.get("on", data.get(True)) if isinstance(data, dict) else {}
        if isinstance(triggers, dict):
            assert "schedule" not in triggers, f"Active schedule cron found in {wf.name}"


# ---------------------------------------------------------------------------
# 6. Zero Texas Tech / .trash / FarIR leaks & verified module-distribution.json
# ---------------------------------------------------------------------------


def test_zero_texas_tech_and_zero_trash_or_private_leaks() -> None:
    assert not (REPO_ROOT / ".trash").exists(), ".trash directory must be completely removed"

    scan_paths: list[Path] = [REPO_ROOT / "README.md"]
    for folder in (".docs", "student", ".github/workflows"):
        root = REPO_ROOT / folder
        if root.is_dir():
            scan_paths.extend(p for p in root.rglob("*") if p.is_file())

    for path in scan_paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert "texas tech" not in text.lower(), f"Forbidden 'Texas Tech' reference in {path.relative_to(REPO_ROOT)}"
        for leak in ("FarIR_v16", "MRW_Permission"):
            assert leak not in text, f"Forbidden leak {leak!r} in {path.relative_to(REPO_ROOT)}"


def test_module_distribution_manifest_has_verified_adapters_and_passes_loader() -> None:
    manifest = manage_modules.load_manifest()
    modules = manifest["modules"]
    expected = {
        "bench": ("bench_provider", "cochem_bench.provider:bench_provider", "cb874d8f20723c70b26b805329cb873ebe1c463f"),
        "topos": ("topos_provider", "topos.base_provider:provider", "734aae0a1ef1f08e0faa2912780aefe25d576eb0"),
        "torq": ("torq_provider", "cochem_torq.ecosystem:module_provider", "1f4359d125a7951dc36e62fb6476a9a002205ed3"),
        "geom": ("geom_provider", "cochem_geom.provider:geom_provider", "ae8f1e7d56a4030e377d36ca7c9516cd0da16851"),
        "spycfit": ("spycfit_provider", "cochem_spycfit.module_provider:spycfit_provider", "aebe6fd8d5939ed617dad72e1392230e3979faf9"),
        "kinetic": ("kinetic_provider", "cochem_kinetic.provider:kinetic_provider", "bd83c8c530a4241ada9fc02229bc19d7c46095c8"),
        "scribe": ("scribe_provider", "cochem_scribe.provider:scribe_provider", "85216dd12c998c1f879b6bb73ab74a44fc98f4bc"),
    }
    for mod_id, (adapter, ep, rev) in expected.items():
        spec = modules[mod_id]
        assert spec["adapter"] == adapter
        assert spec["entry_point"] == ep
        assert spec["revision"] == rev
    assert len(modules["bench"]["operations"]) == 4
    assert len(modules["topos"]["operations"]) == 9
    assert len(modules["torq"]["operations"]) == 5
    assert len(modules["spycfit"]["operations"]) == 4
    assert len(modules["kinetic"]["operations"]) == 5


def test_readme_preserves_nov8_onboarding_and_adds_public_fork_cure_route() -> None:
    raw = (REPO_ROOT / "README.md").read_bytes()
    assert b"\r\n" not in raw, "README.md must use Unix LF line endings"
    text = raw.decode("utf-8")
    assert "4 clicks" in text
    assert "Codespaces" in text
    assert "ORCA" in text
    assert "Public-Fork CURE Route" in text
    assert "Tennessee Tech University" in text
    assert "student_conformers.yml" in text
    assert "cochem.student-handoff/2" in text
