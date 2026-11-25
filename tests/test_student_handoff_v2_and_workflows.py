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
        "bench": ("bench_provider", "cochem_bench.provider:bench_provider", "b903ca63713deba093edce57afd9ffd94d1e9564"),
        "topos": ("topos_provider", "topos.base_provider:provider", "4cd484ccd14fd6a9d001946732575664ea65778b"),
        "torq": ("torq_provider", "cochem_torq.ecosystem:module_provider", "f4c1000f2ad82d9403e85db50463ea06c8b42361"),
        "geom": ("geom_provider", "cochem_geom.provider:geom_provider", "9935c513a455ab1f3f9615162bc1671626ff15ce"),
        "spyfy": ("spyfy_provider", "cochem_spyfy.module_provider:spyfy_provider", "4372dbf448471d8bc7b51feb0bbf7d7a53f400d5"),
        "kinetic": ("kinetic_provider", "cochem_kinetic.provider:kinetic_provider", "90c0de02c89cc3ff8bbcc6dfa85e766a1e4a3b97"),
        "scribe": ("scribe_provider", "cochem_scribe.provider:scribe_provider", "5f9d4d2e9e5fa5abac9f029c2e41b1e820b13903"),
    }
    assert "spycfit" not in modules
    for mod_id, (adapter, ep, rev) in expected.items():
        spec = modules[mod_id]
        assert spec["adapter"] == adapter
        assert spec["entry_point"] == ep
        assert spec["revision"] == rev
    assert len(modules["bench"]["operations"]) == 4
    assert len(modules["topos"]["operations"]) == 9
    assert len(modules["torq"]["operations"]) == 5
    assert len(modules["spyfy"]["operations"]) == 6
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


def test_p8_student_qualification_fixes_devcontainer_workflows_and_examples() -> None:
    """Verify all 6 P8 student-qualification fixes cleanly without mocks."""
    # Fix 1: devcontainer enables sshd:1 alongside github-cli:1
    devcontainer = json.loads((REPO_ROOT / ".devcontainer" / "devcontainer.json").read_text(encoding="utf-8"))
    assert "ghcr.io/devcontainers/features/github-cli:1" in devcontainer["features"]
    assert "ghcr.io/devcontainers/features/sshd:1" in devcontainer["features"]

    # Fix 2: CPU PyTorch constraint file + --extra-index-url + assert torch.version.cuda is None
    for wf_name in ("student_conformers.yml", "06_aimnet2_neb_pyscf_rxn_profile.yml"):
        raw = (REPO_ROOT / ".github" / "workflows" / wf_name).read_text(encoding="utf-8")
        assert "cpu-constraints.txt" in raw
        assert "torch==2.8.0+cpu" in raw
        assert "--extra-index-url https://download.pytorch.org/whl/cpu" in raw
        assert "assert torch.version.cuda is None" in raw

    # Fix 3: CoChem-KINETIC pinned SHA + Team 4 balanced C4H7O4- example geometries
    wf06_raw = (REPO_ROOT / ".github" / "workflows" / "06_aimnet2_neb_pyscf_rxn_profile.yml").read_text(encoding="utf-8")
    wf06 = yaml.safe_load(wf06_raw)
    wf06_inputs = wf06.get("on", wf06.get(True))["workflow_dispatch"]["inputs"]
    assert "90c0de02c89cc3ff8bbcc6dfa85e766a1e4a3b97" in wf06_raw
    assert "6eade693af" not in wf06_raw
    assert wf06_inputs["input_dir"]["default"] == "examples/student_inputs/chem312_team4_rxn"
    assert wf06_inputs["dft_basis"]["default"] == "def2-TZVPP"
    assert wf06_inputs["stage"]["default"] == "all"
    assert wf06_inputs["target_continuation"]["default"] == "workstation"
    team4_dir = REPO_ROOT / "examples" / "student_inputs" / "chem312_team4_rxn"
    for fname in ("R.xyz", "Int_tet.xyz", "P.xyz", "TS1.xyz", "TS2.xyz", "reactant.xyz", "product.xyz"):
        parsed = handoff.read_input(team4_dir / fname, charge=-1, multiplicity=1)
        assert len(parsed["symbols"]) == 15
        assert parsed["formula"] == "C4H7O4-"

    # Fix 5: Real 6-atom hydrogen-bonded water dimer default for 04_crest_nci_dimer_bsse.yml
    wf04 = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "04_crest_nci_dimer_bsse.yml").read_text(encoding="utf-8"))
    wf04_inputs = wf04.get("on", wf04.get(True))["workflow_dispatch"]["inputs"]
    assert wf04_inputs["xyz"]["default"] == "water_dimer.xyz"
    assert wf04_inputs["monomer_a_atoms"]["default"] == "3"
    dimer = handoff.read_input(REPO_ROOT / "examples" / "student_inputs" / "water_dimer.xyz", charge=0, multiplicity=1)
    assert dimer["symbols"] == ["O", "H", "H", "O", "H", "H"]
    assert dimer["formula"] == "H4O2"


def _extract_heredoc_py(step_run: str) -> str:
    marker = "python - <<'PY'\n"
    assert marker in step_run
    body = step_run.split(marker, 1)[1]
    assert "\nPY" in body
    return body.split("\nPY", 1)[0] + "\n"


def test_qa_r2_rxn_profile_2endpoint_workstation_default_seal_and_vdw_guide(tmp_path: Path) -> None:
    """Verify SB-R2-01 (2-endpoint rxn staging + 3pt/5pt seal), SB-R2-02 (workstation default), and SB-R2-03 (--dimer-json note)."""
    import os

    wf06_path = REPO_ROOT / ".github" / "workflows" / "06_aimnet2_neb_pyscf_rxn_profile.yml"
    wf06_raw = wf06_path.read_text(encoding="utf-8")
    wf06 = yaml.safe_load(wf06_raw)
    wf06_inputs = wf06.get("on", wf06.get(True))["workflow_dispatch"]["inputs"]
    assert wf06_inputs["target_continuation"]["default"] == "workstation"
    assert "90c0de02c89cc3ff8bbcc6dfa85e766a1e4a3b97" in wf06_raw
    assert 'for required in ("R.xyz", "Int_tet.xyz", "P.xyz")' not in wf06_raw

    steps = {step.get("name"): step.get("run", "") for step in wf06["jobs"]["rxn_profile"]["steps"]}
    stage_script = _extract_heredoc_py(steps["Stage normalized reaction-profile inputs"])
    seal_script = _extract_heredoc_py(steps["Seal and verify cochem.student-handoff/2 reaction profile bundle"])

    # Real 5-atom anionic CHF2O- (HCOF + F-, Q=-1, M=1, 34e even) 2-endpoint folder (NO Int_tet.xyz)
    chf2o_r = (
        "5\n"
        "HCOF + F- reactant\n"
        "C  0.000000  0.000000  0.000000\n"
        "O  1.180000  0.000000  0.000000\n"
        "H -0.600000  0.920000  0.000000\n"
        "F -0.650000 -1.120000  0.000000\n"
        "F  0.000000  0.000000  2.650000\n"
    )
    chf2o_ts = (
        "5\n"
        "CHF2O- TS\n"
        "C  0.000000  0.000000  0.000000\n"
        "O  1.220000  0.000000  0.000000\n"
        "H -0.580000  0.940000  0.000000\n"
        "F -0.620000 -1.140000 -0.400000\n"
        "F -0.620000 -1.140000  1.450000\n"
    )
    chf2o_p = (
        "5\n"
        "HCOF + F- product\n"
        "C  0.000000  0.000000  0.000000\n"
        "O  1.180000  0.000000  0.000000\n"
        "H -0.600000  0.920000  0.000000\n"
        "F  0.000000  0.000000 -2.650000\n"
        "F -0.650000 -1.120000  0.000000\n"
    )

    two_pt_dir = tmp_path / "hcof_fluoride_rxn"
    two_pt_dir.mkdir()
    (two_pt_dir / "reactant.xyz").write_text(chf2o_r, encoding="utf-8")
    (two_pt_dir / "product.xyz").write_text(chf2o_p, encoding="utf-8")

    # 1. Stage step succeeds on 2-endpoint folder without Int_tet.xyz
    rt_2pt = tmp_path / "runner_2pt"
    env_stage = dict(os.environ, INPUT_DIR=str(two_pt_dir), RUNNER_TEMP=str(rt_2pt))
    proc_stage = subprocess.run([sys.executable, "-B", "-c", stage_script], env=env_stage, capture_output=True, text=True, check=False)
    assert proc_stage.returncode == 0, proc_stage.stderr
    staged_names = sorted(p.name for p in (rt_2pt / "rxn_input").glob("*.xyz"))
    assert staged_names == ["P.xyz", "R.xyz"]

    # 2. Seal step handles elementary_3pt cleanly (TS.xyz, ts_polished.xyz, int ts_n_imaginary_modes, neb/irc)
    out_3pt = rt_2pt / "rxn_out"
    (out_3pt / "geometries").mkdir(parents=True)
    (out_3pt / "geometries" / "R.xyz").write_text(chf2o_r, encoding="utf-8")
    (out_3pt / "geometries" / "TS.xyz").write_text(chf2o_ts, encoding="utf-8")
    (out_3pt / "geometries" / "P.xyz").write_text(chf2o_p, encoding="utf-8")
    (out_3pt / "ts_polished.xyz").write_text(chf2o_ts, encoding="utf-8")
    (out_3pt / "neb_path.xyz").write_text(chf2o_r + chf2o_ts + chf2o_p, encoding="utf-8")
    (out_3pt / "irc_path.xyz").write_text(chf2o_r + chf2o_ts + chf2o_p, encoding="utf-8")
    (out_3pt / "stationary_table.md").write_text("# 3-pt table\n", encoding="utf-8")
    (out_3pt / "manifest_sha256.json").write_text('{"schema_version":"cochem.provenance-manifest/1","files_sha256":{}}\n', encoding="utf-8")
    (out_3pt / "results.json").write_text(
        json.dumps(
            {
                "pathway_mode": "elementary_3pt",
                "input_mode": "2pt_elementary",
                "stationary_points": ["R", "TS", "P"],
                "primary_ts_state": "TS",
                "ts_n_imaginary_modes": 1,
                "states": {"TS": {"hessian": {"thermo": {"n_imag": 1}}}},
            }
        ),
        encoding="utf-8",
    )
    env_seal_3pt = dict(
        os.environ,
        RUNNER_TEMP=str(rt_2pt),
        STAGE="all",
        CHARGE="-1",
        MULTIPLICITY="1",
        DFT_BASIS="def2-SVP",
        SOLVENT_NAME="acetonitrile",
        TEMP_K="298.15",
        INPUT_NAME="hcof_fluoride_rxn.xyz",
        COURSE_ID="CHEM312",
        TARGET_CONTINUATION="workstation",
        GITHUB_REPOSITORY="ProfJJK-CoChem/CoChem-BASE",
        GITHUB_SHA="24ff8360d27233f0153541987ec310f4c1b41b7c",
        GITHUB_RUN_ID="990001",
        GITHUB_RUN_ATTEMPT="1",
    )
    proc_seal_3pt = subprocess.run(
        [sys.executable, "-B", "-c", seal_script],
        cwd=str(REPO_ROOT),
        env=env_seal_3pt,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_seal_3pt.returncode == 0, proc_seal_3pt.stderr
    zips_3pt = list((rt_2pt / "handoff").glob("*.zip"))
    assert len(zips_3pt) == 1
    rec_3pt = handoff.verify(zips_3pt[0], sidecar_path=zips_3pt[0].with_suffix(".zip.sha256"))
    assert rec_3pt["target_continuation"] == "workstation"
    assert rec_3pt["hessian_calculated"] is True
    assert rec_3pt["n_imaginary_modes"] == 1
    assert rec_3pt["candidate_count"] == 3
    assert rec_3pt["metadata"]["pathway_mode"] == "elementary_3pt"
    assert rec_3pt["metadata"]["kinetic_revision"] == "90c0de02c89cc3ff8bbcc6dfa85e766a1e4a3b97"
    for member in ("ts_polished.xyz", "results.json", "stationary_table.md", "neb_path.xyz", "irc_path.xyz", "manifest_sha256.json"):
        assert member in rec_3pt["files_sha256"]

    # 3. Seal step handles stepwise_5pt + long (>256-frame) irc_path.xyz cleanly
    rt_5pt = tmp_path / "runner_5pt"
    (rt_5pt / "rxn_input").mkdir(parents=True)
    (rt_5pt / "rxn_input" / "R.xyz").write_text(chf2o_r, encoding="utf-8")
    out_5pt = rt_5pt / "rxn_out"
    (out_5pt / "geometries").mkdir(parents=True)
    for st, txt in (("R", chf2o_r), ("TS1", chf2o_ts), ("Int_tet", chf2o_ts), ("TS2", chf2o_ts), ("P", chf2o_p)):
        (out_5pt / "geometries" / f"{st}.xyz").write_text(txt, encoding="utf-8")
    (out_5pt / "ts_polished.xyz").write_text(chf2o_ts, encoding="utf-8")
    (out_5pt / "neb_path.xyz").write_text(chf2o_r * 11 + chf2o_p * 11, encoding="utf-8")
    (out_5pt / "irc_path.xyz").write_text(chf2o_ts * 400, encoding="utf-8")
    (out_5pt / "stationary_table.md").write_text("# 5-pt table\n", encoding="utf-8")
    (out_5pt / "manifest_sha256.json").write_text('{"schema_version":"cochem.provenance-manifest/1","files_sha256":{}}\n', encoding="utf-8")
    (out_5pt / "results.json").write_text(
        json.dumps(
            {
                "pathway_mode": "stepwise_5pt",
                "input_mode": "2pt_auto_discovered_intermediate",
                "stationary_points": ["R", "TS1", "Int_tet", "TS2", "P"],
                "primary_ts_state": "TS1",
                "ts_n_imaginary_modes": {"TS1": 1, "TS2": 1},
                "states": {"TS1": {"hessian": {"thermo": {"n_imag": 1}}}, "TS2": {"hessian": {"thermo": {"n_imag": 1}}}},
            }
        ),
        encoding="utf-8",
    )
    env_seal_5pt = dict(env_seal_3pt, RUNNER_TEMP=str(rt_5pt), GITHUB_RUN_ID="990002")
    proc_seal_5pt = subprocess.run(
        [sys.executable, "-B", "-c", seal_script],
        cwd=str(REPO_ROOT),
        env=env_seal_5pt,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_seal_5pt.returncode == 0, proc_seal_5pt.stderr
    zips_5pt = list((rt_5pt / "handoff").glob("*.zip"))
    assert len(zips_5pt) == 1
    rec_5pt = handoff.verify(zips_5pt[0], sidecar_path=zips_5pt[0].with_suffix(".zip.sha256"))
    assert rec_5pt["candidate_count"] == 5
    assert rec_5pt["n_imaginary_modes"] == 1
    assert rec_5pt["metadata"]["pathway_mode"] == "stepwise_5pt"
    assert rec_5pt["metadata"]["irc_path_total_frames"] == 400
    assert rec_5pt["metadata"]["irc_path_staged_frames"] <= handoff.V2_MAX_FRAMES

    # 4. SB-R2-03: Guide omits --dimer-json from default copy-paste command and notes it is optional
    guide = (REPO_ROOT / "student" / "CHEM312L_STEP_BY_STEP_GUIDE.md").read_text(encoding="utf-8")
    sec3 = guide.split("### 3. M3", 1)[1].split("### 4. M3", 1)[0]
    code_block = sec3.split("```bash", 1)[1].split("```", 1)[0]
    assert "--dimer-json" not in code_block
    assert "--bsse-json results/bsse_counterpoise.json" in code_block
    assert "--dimer-json" in sec3 and "optional" in sec3.lower()


def test_qa_r3_rxn_profile_auto_input_name_derivation_and_override(tmp_path: Path) -> None:
    """Verify SB-R3-01: 06_aimnet2 auto-derives input_name from input_dir basename and honors explicit override."""
    import os

    wf06_path = REPO_ROOT / ".github" / "workflows" / "06_aimnet2_neb_pyscf_rxn_profile.yml"
    wf06 = yaml.safe_load(wf06_path.read_text(encoding="utf-8"))
    triggers = wf06.get("on", wf06.get(True))
    assert set(triggers.keys()) == {"workflow_dispatch"}
    wf06_inputs = triggers["workflow_dispatch"]["inputs"]
    assert wf06_inputs["input_name"]["default"] == "auto"
    assert wf06_inputs["input_name"]["required"] is False
    assert wf06_inputs["target_continuation"]["default"] == "workstation"

    steps = {step.get("name"): step.get("run", "") for step in wf06["jobs"]["rxn_profile"]["steps"]}
    seal_script = _extract_heredoc_py(steps["Seal and verify cochem.student-handoff/2 reaction profile bundle"])

    chf2o_r = (
        "5\n"
        "HCOF + F- reactant\n"
        "C  0.000000  0.000000  0.000000\n"
        "O  1.180000  0.000000  0.000000\n"
        "H -0.600000  0.920000  0.000000\n"
        "F -0.650000 -1.120000  0.000000\n"
        "F  0.000000  0.000000  2.650000\n"
    )
    chf2o_ts = (
        "5\n"
        "CHF2O- TS\n"
        "C  0.000000  0.000000  0.000000\n"
        "O  1.220000  0.000000  0.000000\n"
        "H -0.580000  0.940000  0.000000\n"
        "F -0.620000 -1.140000 -0.400000\n"
        "F -0.620000 -1.140000  1.450000\n"
    )
    chf2o_p = (
        "5\n"
        "HCOF + F- product\n"
        "C  0.000000  0.000000  0.000000\n"
        "O  1.180000  0.000000  0.000000\n"
        "H -0.600000  0.920000  0.000000\n"
        "F  0.000000  0.000000 -2.650000\n"
        "F -0.650000 -1.120000  0.000000\n"
    )

    cases = [
        ("auto", "990101", "hcof_fluoride_rxn.xyz", "CoChem-chem312-hcof_fluoride_rxn-990101-1.zip"),
        ("", "990102", "hcof_fluoride_rxn.xyz", "CoChem-chem312-hcof_fluoride_rxn-990102-1.zip"),
        ("chem312_team4_rxn.xyz", "990103", "hcof_fluoride_rxn.xyz", "CoChem-chem312-hcof_fluoride_rxn-990103-1.zip"),
        ("my_custom_nas_ts.xyz", "990104", "my_custom_nas_ts.xyz", "CoChem-chem312-my_custom_nas_ts-990104-1.zip"),
    ]
    for raw_input_name, run_id, expected_input_name, expected_zip_name in cases:
        rt = tmp_path / f"rt_{run_id}"
        (rt / "rxn_input").mkdir(parents=True)
        (rt / "rxn_input" / "R.xyz").write_text(chf2o_r, encoding="utf-8")
        out_dir = rt / "rxn_out"
        (out_dir / "geometries").mkdir(parents=True)
        (out_dir / "geometries" / "R.xyz").write_text(chf2o_r, encoding="utf-8")
        (out_dir / "geometries" / "TS.xyz").write_text(chf2o_ts, encoding="utf-8")
        (out_dir / "geometries" / "P.xyz").write_text(chf2o_p, encoding="utf-8")
        (out_dir / "ts_polished.xyz").write_text(chf2o_ts, encoding="utf-8")
        (out_dir / "results.json").write_text(
            json.dumps(
                {
                    "pathway_mode": "elementary_3pt",
                    "input_mode": "2pt_elementary",
                    "stationary_points": ["R", "TS", "P"],
                    "primary_ts_state": "TS",
                    "ts_n_imaginary_modes": 1,
                }
            ),
            encoding="utf-8",
        )
        env = dict(
            os.environ,
            RUNNER_TEMP=str(rt),
            INPUT_DIR="examples/student_inputs/hcof_fluoride_rxn",
            INPUT_NAME=raw_input_name,
            STAGE="all",
            CHARGE="-1",
            MULTIPLICITY="1",
            DFT_BASIS="def2-SVP",
            SOLVENT_NAME="acetonitrile",
            TEMP_K="298.15",
            COURSE_ID="CHEM312",
            TARGET_CONTINUATION="workstation",
            GITHUB_REPOSITORY="ProfJJK-CoChem/CoChem-BASE",
            GITHUB_SHA="3dccd6c9f4bd0000000000000000000000000000",
            GITHUB_RUN_ID=run_id,
            GITHUB_RUN_ATTEMPT="1",
        )
        proc = subprocess.run(
            [sys.executable, "-B", "-c", seal_script],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        zips = list((rt / "handoff").glob("*.zip"))
        assert len(zips) == 1
        assert zips[0].name == expected_zip_name
        rec = handoff.verify(zips[0], sidecar_path=zips[0].with_suffix(".zip.sha256"))
        assert rec["input_name"] == expected_input_name
