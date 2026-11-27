"""Zero-mock regression tests for QA490-R1 CHEM 490 & live Voilà GUI fixes (GUI-01..06, SB490-01..11)."""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Iterator, Optional

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def _scoped_env(**updates: Optional[str]) -> Iterator[None]:
    """Temporarily set or delete os.environ entries and restore on exit."""
    previous = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, old in previous.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old


# ---------------------------------------------------------------------------
# 1. GUI-01..GUI-06 (Live Voilà Dashboard Widgets, CSS, and Guidance)
# ---------------------------------------------------------------------------


def test_gui_01_to_06_voila_state_sync_contrast_preview_and_copy(tmp_path: Path) -> None:
    """Verify GUI-01..GUI-06 directly on real CoChemGUI + apply_workspace_layout widgets."""
    with _scoped_env(
        COCHEM_ARTIFACT_DIR=str(tmp_path / "artifacts"),
        COCHEM_CONFIG=str(tmp_path / "absent-registry.json"),
        COCHEM_STUDENT_AUTO_REMOTE_CHECK="0",
    ):
        from ui.voila_layout.cochem_gui import CoChemGUI
        from ui.voila_layout.learning import help_html
        from ui.voila_layout.workspace_layout import apply_workspace_layout
        from ui.voila_layout.workspace_style import WORKSPACE_CSS

        gui = CoChemGUI()
        apply_workspace_layout(gui)

        water_xyz = "3\nwater\nO 0.0 0.0 0.0\nH 0.0 0.757 0.586\nH 0.0 -0.757 0.586\n"
        gui.matrix_geometry.value = water_xyz

        # GUI-01: Selecting PySCF directly under default Product A cleanly configures RHF single point
        gui.matrix_engine.value = "PYSCF"
        assert gui.matrix_tier.value == "T2"
        assert gui.matrix_method.value == "HF/STO-3G"
        assert gui.matrix_basis.value == "STO-3G"
        assert not gui.matrix_basis.disabled
        assert gui.matrix_solvation.value is None
        assert gui.product_class_selector.value == "Screening (no product accuracy claim)"
        assert not gui.product_class_selector.disabled
        assert gui.dispersion_warning.value == ""
        assert gui.btn_execute.description == "Run PySCF single point"
        assert "program PYSCF; method HF/STO-3G; basis STO-3G" in gui.guided_draft_status.value

        # GUI-01: Switching XTB -> PYSCF updates basis & Current settings (never stuck on XTB/built-in)
        gui.matrix_engine.value = "XTB"
        assert gui.matrix_basis.value == "built-in"
        gui.matrix_engine.value = "PYSCF"
        assert gui.matrix_tier.value == "T2"
        assert gui.matrix_method.value == "HF/STO-3G"
        assert gui.matrix_basis.value == "STO-3G"
        assert not gui.matrix_basis.disabled
        assert "program PYSCF; method HF/STO-3G; basis STO-3G" in gui.guided_draft_status.value
        assert "program XTB" not in gui.guided_draft_status.value
        assert "built-in" not in gui.guided_draft_status.value

        # GUI-02: High-contrast hover/focus/active CSS rules for danger/primary buttons
        assert ".jupyter-button.mod-danger:hover:enabled" in WORKSPACE_CSS
        assert ".jupyter-button.mod-danger:focus:enabled" in WORKSPACE_CSS
        assert "#732125" in WORKSPACE_CSS

        # GUI-03: 3D preview mounted directly on 2 · Add your molecule without horizontal overflow
        assert hasattr(gui, "inputs_viewer_output")
        assert hasattr(gui, "inputs_preview_columns")
        assert gui.inputs_viewer_output.layout.overflow == "hidden"
        assert gui.viewer_output.layout.overflow == "hidden"
        assert ".cochem-molecule-preview" in WORKSPACE_CSS
        from cochem_base.interfaces.molecule_viewer import molecule_viewer_html
        rendered_html = molecule_viewer_html(water_xyz)
        assert "overflow:hidden" in rendered_html

        # GUI-04: Wider select controls, nowrap Status column CSS, and PySCF in CoChem components
        assert gui.matrix_engine.layout.width == "480px"
        assert gui.matrix_solvation.layout.width == "480px"
        assert "cochem-components-table" in WORKSPACE_CSS
        assert "white-space: nowrap" in WORKSPACE_CSS
        gui._render_student_setup_status(
            {
                "ready": True,
                "base": {"revision": "0b3af3e1e7ee"},
                "modules": {"topos": {"status": "installed", "revision": "abc", "message": "ok"}},
                "free_engines": {
                    "status": "ready",
                    "message": "Pinned free-engine installations verified.",
                    "engines": {"xtb": {"status": "installed", "version": "6.7.1", "message": "ok"}},
                },
            }
        )
        assert "class='cochem-components-table'" in gui.student_setup_status.value
        assert "<td>PySCF</td>" in gui.student_setup_status.value
        assert "<td>CoChem-SPYFY</td>" in gui.student_setup_status.value
        assert "optional add-on (not installed — run: bash scripts/install_optional_spyfy.sh)" in gui.student_setup_status.value

        # GUI-05: No Google Colab in workspace guidance; no raw DEGRADED_OPERATIONAL or registry path
        assert "Google Colab" not in help_html("workspace")
        assert "department research computers" in help_html("workspace")
        gui._on_environment_change({"new": "Codespaces [DEGRADED_OPERATIONAL]"})
        assert "DEGRADED_OPERATIONAL" not in gui.header_env.value
        assert "Codespaces · Open-source engines ready" in gui.header_env.value
        assert "cochem_system_config.json" not in gui.licensed_engine_status.value
        assert "ORCA is optional" in gui.licensed_engine_status.value

        # GUI-06: Upload counter sync & unambiguous canonical-frame SHA-256 vs original upload SHA-256
        from cochem_base.interfaces.student_ingestion import ingest_uploaded_file
        receipt = ingest_uploaded_file("h2o_start.xyz", water_xyz.encode("utf-8"), artifact_dir=tmp_path / "artifacts")
        gui._input_library = {receipt["input_id"]: receipt}
        gui.input_library_choice.options = [("Choose", ""), ("h2o_start.xyz", receipt["input_id"])]
        gui.input_library_choice.value = receipt["input_id"]
        gui._use_library_geometry()
        assert "1 structure loaded" in gui.xyz_upload.description
        assert "Canonical frame SHA-256" in gui.student_upload_status.value
        assert receipt["sha256"] in gui.student_upload_status.value
        assert "Original bytes preserved" in gui.student_upload_status.value


# ---------------------------------------------------------------------------
# 2. SB490-02: scripts/spcat_runner.py Decks, Parsing & Honest PENDING Gate
# ---------------------------------------------------------------------------


def test_spcat_runner_decks_cat_parsing_and_honest_pending_when_absent(tmp_path: Path) -> None:
    """Verify valid Pickett .var/.int decks, .cat parsing/filtering, and zero-crash PENDING fallback."""
    from scripts.spcat_runner import (
        SPCATDeckConfig,
        SPCATRunner,
        parse_cat_file,
        write_pickett_decks,
    )

    cfg = SPCATDeckConfig(
        a_mhz=410000.0,
        b_mhz=7260.0,
        c_mhz=7140.0,
        dj_khz=5.0,
        mu_a=4.07,
        temperature_k=2.0,
        constant_type="Be",
    )
    var_p, int_p = write_pickett_decks(cfg, tmp_path / "decks", stem="h2o_hf", freq_max_ghz=18.0)
    var_text = var_p.read_text(encoding="utf-8")
    int_text = int_p.read_text(encoding="utf-8")
    assert "a    1  1   0   30" in var_text
    assert "10000" in var_text and "410000.000000" in var_text
    assert "-0.005000000" in var_text  # -5.0 kHz converted to MHz
    assert "18.000  2.000" in int_text
    assert "4.0700" in int_text

    # Real Pickett .cat format parsing + 8-18 GHz band filtering
    sample_cat = tmp_path / "sample.cat"
    sample_cat.write_text(
        "   7200.0000  0.0001 -2.1000 3    0.0000  3     91 303 1 0 1       0 0 0      \n"
        "  14400.0000  0.0001 -1.5375 3    0.0000  3     91 303 1 0 1       0 0 0      \n"
        "  28800.0000  0.0001 -0.9500 3    0.4803  5     91 303 2 0 2       1 0 1      \n",
        encoding="utf-8",
    )
    in_band = parse_cat_file(sample_cat, constant_type="Be", freq_min_ghz=8.0, freq_max_ghz=18.0)
    assert len(in_band) == 1
    assert in_band[0]["frequency_mhz"] == pytest.approx(14400.0)
    assert (in_band[0]["j_upper"], in_band[0]["ka_upper"], in_band[0]["kc_upper"]) == (1, 0, 1)
    assert (in_band[0]["j_lower"], in_band[0]["ka_lower"], in_band[0]["kc_lower"]) == (0, 0, 0)

    # Absent spcat binary must fail closed honestly with PENDING (never ModuleNotFoundError)
    runner = SPCATRunner(spcat_bin_path=tmp_path / "nonexistent_spcat")
    runner.spcat_bin = None
    transitions = runner.generate_transitions(
        cfg,
        allow_unvibrated_be=True,
        scratch_dir=tmp_path / "pending_scr",
        freq_min_ghz=8.0,
        freq_max_ghz=18.0,
    )
    assert transitions == []
    assert runner.last_status == "PENDING"
    assert runner.last_engine == "PENDING"
    assert Path(runner.last_deck_paths["var"]).is_file()
    assert Path(runner.last_deck_paths["int"]).is_file()


# ---------------------------------------------------------------------------
# 3. SB490-06: scripts/kraitchman_rs.py --course-id CHEM490
# ---------------------------------------------------------------------------


def test_kraitchman_rs_supports_chem490_course_id(tmp_path: Path) -> None:
    """Verify --course-id CHEM490 tags JSON and Markdown while preserving honest imaginary flags."""
    out_json = tmp_path / "h2o_hdo.json"
    out_md = tmp_path / "h2o_hdo.md"
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            str(REPO_ROOT / "scripts" / "kraitchman_rs.py"),
            "--parent-abc", "835840.3", "435351.7", "278139.8",
            "--iso-abc", "701931.5", "272912.6", "192055.2",
            "--parent-mass-amu", "18.010565",
            "--delta-mass-amu", "1.006277",
            "--course-id", "CHEM490",
            "--label", "H2O_HDO",
            "--output-json", str(out_json),
            "--output-md", str(out_md),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["course_id"] == "CHEM490"
    assert payload["coordinates"]["c"]["imaginary"] is True
    assert payload["coordinates"]["c"]["abs_rs_angstrom"] is None
    md = out_md.read_text(encoding="utf-8")
    assert "# CHEM490 Kraitchman Single-Substitution Coordinates" in md


# ---------------------------------------------------------------------------
# 4. SB490-04: student_project_setup.yml Open-Engine Student Mode
# ---------------------------------------------------------------------------


def test_student_project_setup_open_engine_fallback_and_strict_licensed_mode(tmp_path: Path) -> None:
    """Verify optional request_id, green open-engine mode, and preserved strict licensed checks."""
    wf = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "student_project_setup.yml").read_text(encoding="utf-8"))
    on_block = wf.get("on") or wf[True]
    req_input = on_block["workflow_dispatch"]["inputs"]["request_id"]
    assert req_input["required"] is False
    assert req_input["default"] == "self-check"

    base_env = {
        **os.environ,
        "GITHUB_REPOSITORY": "student/CoChem-h2o-hf",
        "GITHUB_SHA": "a" * 40,
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "DEFAULT_BRANCH": "main",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_RUN_ID": "901",
        "GITHUB_RUN_ATTEMPT": "1",
        "COCHEM_APPROVED_BASE_SHA": "",
        "COCHEM_COURSE_CHANNEL": "",
        "COCHEM_SOURCE_AVAILABLE": "false",
        "COCHEM_ORCA_AVAILABLE": "false",
        "COCHEM_CFOUR_AVAILABLE": "false",
    }

    # Open-engine personal template repo with default self-check or custom label succeeds
    for req_id in ("self-check", "chem490-qa-r1"):
        out = tmp_path / f"open_{req_id}.json"
        res = subprocess.run(
            [sys.executable, "-B", "-I", "-S", str(REPO_ROOT / "scripts" / "check_student_project_setup.py"), "--output", str(out)],
            env={**base_env, "SETUP_REQUEST_ID": req_id},
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
        assert res.returncode == 0, res.stderr
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["mode"] == "open_engine_student"
        assert data["open_engine_ready"] is True
        assert "Dr. Klaassen" in data["student_summary"]
        assert "Open-source Codespace research setup ready" in res.stdout

    # Licensed/approved mode MUST still reject non-UUID request_id
    out_strict = tmp_path / "strict_fail.json"
    res_fail = subprocess.run(
        [sys.executable, "-B", "-I", "-S", str(REPO_ROOT / "scripts" / "check_student_project_setup.py"), "--output", str(out_strict)],
        env={**base_env, "SETUP_REQUEST_ID": "not-a-uuid", "COCHEM_APPROVED_BASE_SHA": "b" * 40},
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert res_fail.returncode != 0
    assert not out_strict.exists()

    # Licensed/approved mode with valid UUID passes cleanly
    out_ok = tmp_path / "strict_ok.json"
    res_ok = subprocess.run(
        [sys.executable, "-B", "-I", "-S", str(REPO_ROOT / "scripts" / "check_student_project_setup.py"), "--output", str(out_ok)],
        env={**base_env, "SETUP_REQUEST_ID": str(uuid.uuid4()), "COCHEM_APPROVED_BASE_SHA": "b" * 40, "COCHEM_ORCA_AVAILABLE": "true"},
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert res_ok.returncode == 0, res_ok.stderr
    assert json.loads(out_ok.read_text(encoding="utf-8"))["mode"] == "licensed_course_project"


# ---------------------------------------------------------------------------
# 5. SB490-11, SB490-08, SB490-01..03, SB490-06..10: CLI Audit, Setup & Docs
# ---------------------------------------------------------------------------


def test_cli_audit_meminfo_and_engine_probe(tmp_path: Path) -> None:
    """Verify Linux /proc/meminfo RAM parsing and artifact_dir/bin engine probing."""
    from cochem_base.cli import _probe_additional_engines, _read_linux_meminfo_gb

    sample_meminfo = tmp_path / "meminfo"
    sample_meminfo.write_text("MemTotal:        8136940 kB\nMemFree:         4000000 kB\n", encoding="utf-8")
    assert _read_linux_meminfo_gb(sample_meminfo) == pytest.approx(7.76, abs=0.01)

    art = tmp_path / "CoChem_Artifacts"
    (art / "bin").mkdir(parents=True)
    (art / "Silos" / "cochem_calc_silo" / "bin").mkdir(parents=True)
    for name in ("xtb", "crest", "spfit", "spcat"):
        (art / "bin" / name).write_text("#!/bin/sh\n", encoding="utf-8")
    (art / "Silos" / "cochem_calc_silo" / "bin" / "python").write_text("#!/bin/sh\n", encoding="utf-8")

    probed = _probe_additional_engines(art)
    for name in ("xtb", "crest", "spfit", "spcat", "pyscf"):
        assert probed[name]["is_available"] is True
        assert probed[name]["path"]


def test_codespace_setup_voila_hygiene_and_chem490_guide() -> None:
    """Verify Codespace PATH/pins, Voilà idle culling, CHEM 490 guide, and doc hygiene."""
    dev = json.loads((REPO_ROOT / ".devcontainer" / "devcontainer.json").read_text(encoding="utf-8"))
    assert dev["remoteEnv"]["PATH"].startswith("/home/vscode/CoChem_Artifacts/bin:/home/vscode/CoChem_Artifacts/ui-env/bin:")

    setup_sh = (REPO_ROOT / "scripts" / "setup_devcontainer.sh").read_text(encoding="utf-8")
    for token in (
        "f5af2ff0f1acb1eb11ecffe7ef3b55d457801f7b",
        "b903ca63713deba093edce57afd9ffd94d1e9564",
        "5f9d4d2e9e5fa5abac9f029c2e41b1e820b13903",
        "9935c513a455ab1f3f9615162bc1671626ff15ce",
        "pyscf==2.14.0",
        "geometric==1.1.1",
        "cochem-geom",
        "cochem-bench",
        "cochem-scribe",
        "cochem-torq",
        "$artifact_bin/topos",
        "$artifact_bin/spfit",
        "$artifact_bin/spcat",
        "COCHEM_INSTALL_SPYFY",
        "install_optional_spyfy.sh",
    ):
        assert token in setup_sh, f"Missing expected Codespace setup token: {token}"
    assert "CoChem-SpycFit" not in setup_sh
    assert "cochem-spycfit" not in setup_sh
    assert "jax[cpu]" not in setup_sh

    from scripts.hosted_dashboard import server_command
    cmd = server_command(Path("/usr/bin/python3"), 8866)
    assert "--MappingKernelManager.cull_idle_timeout=300" in cmd

    guide = (REPO_ROOT / "student" / "CHEM490_STEP_BY_STEP_GUIDE.md").read_text(encoding="utf-8")
    for cmd_tok in (
        "cochem-bench",
        "cochem-geom",
        "CoChem-SPYFY",
        "install_optional_spyfy.sh",
        "cochem-spyfy",
        "cochem-scribe",
        "cochem-torq",
        "topos",
        "spfit",
        "spcat",
        "scripts/spcat_runner.py",
        "scripts/kraitchman_rs.py",
        "--course-id CHEM490",
        "professor_orca_return_h2o_ccsd.out",
        "Tennessee Tech University",
        "~10–15 minutes",
    ):
        assert cmd_tok in guide, f"CHEM490 guide missing {cmd_tok}"
    assert "SpycFit" not in guide and "spycfit" not in guide

    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "student/CHEM490_STEP_BY_STEP_GUIDE.md" in readme

    for doc_name in ("ORCA_Actions_Setup.md", "Ecosystem_Modules_Setup.md"):
        doc_text = (REPO_ROOT / ".docs" / doc_name).read_text(encoding="utf-8")
        assert "Classroom50" not in doc_text
        assert "Google_Colab" not in doc_text

    first_lab = (REPO_ROOT / ".docs" / "FIRST_LAB.md").read_text(encoding="utf-8")
    assert "November 2026" not in first_lab
    assert "BEGINNER_FIRE_TEST_2026-11-03.md" not in first_lab


# ---------------------------------------------------------------------------
# 6. QA490-R2 Fixes: SB490-R2-01..05, GUI-R2-01, GUI-R2-02
# ---------------------------------------------------------------------------


def test_qa490_r2_setup_devcontainer_isolation_depth_and_optional_spyfy_addon(tmp_path: Path) -> None:
    """Verify isolated pip installs, -maxdepth 8, optional CoChem-SPYFY add-on script, and cochem-spyfy CLI."""
    import ast
    import re

    setup_path = REPO_ROOT / "scripts" / "setup_devcontainer.sh"
    raw_bytes = setup_path.read_bytes()
    assert b"\r\n" not in raw_bytes, "setup_devcontainer.sh must use pure LF line endings"
    setup_sh = raw_bytes.decode("utf-8")

    # Separate pip installs for CoChem-BENCH and CoChem-SCRIBE; CoChem-SPYFY must NOT be installed by default
    pip_blocks = re.findall(r'"\$ui_python"\s+-m\s+pip\s+install[\s\S]*?\|\|[^\n]+', setup_sh)
    bench_blocks = [b for b in pip_blocks if "CoChem-BENCH.git@b903ca63713deba093edce57afd9ffd94d1e9564" in b]
    scribe_blocks = [b for b in pip_blocks if "CoChem-SCRIBE.git@5f9d4d2e9e5fa5abac9f029c2e41b1e820b13903" in b]
    assert len(bench_blocks) == 1
    assert len(scribe_blocks) == 1
    assert "CoChem-SCRIBE" not in bench_blocks[0]
    assert "CoChem-BENCH" not in scribe_blocks[0]
    assert "CoChem-SPYFY" not in setup_sh or 'COCHEM_INSTALL_SPYFY' in setup_sh
    assert "jax[cpu]" not in setup_sh
    assert "CoChem-GEOM.git@9935c513a455ab1f3f9615162bc1671626ff15ce" in setup_sh

    # SB490-R2-02: -maxdepth 8 (never -maxdepth 4) and clean fallback wrappers for topos and torq
    assert "-maxdepth 4" not in setup_sh
    assert setup_sh.count("-maxdepth 8") >= 4
    assert "*/bin/cochem-topos" in setup_sh and "*/bin/topos" in setup_sh
    assert "*/bin/cochem-torq" in setup_sh and "*/bin/torq" in setup_sh
    assert "from topos.cli import main" in setup_sh
    assert "from cochem_torq.cli import main" in setup_sh

    # Optional add-on installer script scripts/install_optional_spyfy.sh
    addon_path = REPO_ROOT / "scripts" / "install_optional_spyfy.sh"
    assert addon_path.is_file()
    addon_bytes = addon_path.read_bytes()
    assert b"\r\n" not in addon_bytes, "install_optional_spyfy.sh must use pure LF line endings"
    addon_sh = addon_bytes.decode("utf-8")
    assert "4372dbf448471d8bc7b51feb0bbf7d7a53f400d5" in addon_sh
    assert "CoChem-SPYFY.git" in addon_sh
    assert "jax[cpu]" in addon_sh
    assert "grulab_surf" in addon_sh
    match = re.search(r"cat <<'PY'\n([\s\S]*?)\nPY\n\} > \"\$artifact_bin/cochem-spyfy\"", addon_sh)
    assert match is not None, "Embedded cochem-spyfy Python wrapper not found"
    wrapper_src = match.group(1)
    ast.parse(wrapper_src)
    wrapper_file = tmp_path / "cochem_spyfy_wrapper.py"
    wrapper_file.write_text(wrapper_src, encoding="utf-8")

    help_res = subprocess.run(
        [sys.executable, "-B", str(wrapper_file), "--help"],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert help_res.returncode == 0, help_res.stderr
    for subcmd in ("info", "parse", "predict", "fit", "plan-surf", "ingest-surf"):
        assert subcmd in help_res.stdout


def test_cli_addons_and_emt_rejection(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Verify cochem-cli addons / install-addon --dry-run and hard EMT rejection in Parsl worker cache."""
    from cochem_base import cli as base_cli
    from cochem_base.core_engine.cochem_core_parsl_executors import get_cached_mlff_calculator

    art = tmp_path / "artifacts"
    art.mkdir()
    assert base_cli.main(["addons", "--artifact-dir", str(art), "--json"]) == 0
    addons_payload = json.loads(capsys.readouterr().out)
    assert addons_payload["addons"]["spyfy"]["revision"] == "4372dbf448471d8bc7b51feb0bbf7d7a53f400d5"
    assert addons_payload["addons"]["spyfy"]["installed"] is False

    assert base_cli.main(["install-addon", "spyfy", "--dry-run", "--json"]) == 0
    dry_payload = json.loads(capsys.readouterr().out)
    assert dry_payload["dry_run"] is True
    assert dry_payload["addon"] == "spyfy"
    assert dry_payload["installer_script"].endswith("install_optional_spyfy.sh")

    with pytest.raises(ValueError, match="permanently retired"):
        get_cached_mlff_calculator("emt")


def test_qa490_r2_cli_status_json_and_human_default(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Verify SB490-R2-04: cochem-cli status --json and --json status emit valid JSON while preserving human default."""
    from cochem_base import cli as base_cli

    art = tmp_path / "artifacts"
    art.mkdir()

    # Subcommand --json form
    rc = base_cli.main(["status", "--artifact-dir", str(art), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["artifact_directory"] == str(art.resolve())
    assert payload["registry_exists"] is False
    assert "phase_1" in payload["phase_artifacts"]

    # Global --json before subcommand form
    rc_global = base_cli.main(["--json", "status", "--artifact-dir", str(art)])
    assert rc_global == 0
    payload_global = json.loads(capsys.readouterr().out)
    assert payload_global["artifact_directory"] == str(art.resolve())

    # Default human-readable form preserved
    rc_human = base_cli.main(["status", "--artifact-dir", str(art)])
    assert rc_human == 0
    human_out = capsys.readouterr().out
    assert "Golden Master Registry & Ecosystem Status" in human_out


def test_qa490_r2_fact_ledger_chem490_default_label_and_readme_footer(tmp_path: Path) -> None:
    """Verify SB490-R2-05: fact_ledger defaults project_label to '<course_id>_Dossier' and README Colab footer."""
    sample = tmp_path / "h2o_hf.xyz"
    sample.write_text("3\nwater\nO 0 0 0\nH 0 0.757 0.586\nH 0 -0.757 0.586\n", encoding="utf-8")

    # CHEM490 default project_label -> CHEM490_Dossier
    out_json_490 = tmp_path / "FactLedger_490.json"
    out_md_490 = tmp_path / "FactLedger_490.md"
    res_490 = subprocess.run(
        [
            sys.executable, "-B", str(REPO_ROOT / "scripts" / "fact_ledger.py"),
            "--artifacts", str(sample),
            "--base-dir", str(tmp_path),
            "--course-id", "CHEM490",
            "--output-json", str(out_json_490),
            "--output-md", str(out_md_490),
        ],
        capture_output=True, text=True, check=False, timeout=20,
    )
    assert res_490.returncode == 0, res_490.stderr
    ledger_490 = json.loads(out_json_490.read_text(encoding="utf-8"))
    assert ledger_490["course_id"] == "CHEM490"
    assert ledger_490["project_label"] == "CHEM490_Dossier"
    md_490 = out_md_490.read_text(encoding="utf-8")
    assert "CHEM490_Dossier" in md_490
    assert "CHEM312_Dossier" not in md_490

    # Fail-closed --verify still passes
    verify_490 = subprocess.run(
        [sys.executable, "-B", str(REPO_ROOT / "scripts" / "fact_ledger.py"), "--verify", str(out_json_490)],
        capture_output=True, text=True, check=False, timeout=20,
    )
    assert verify_490.returncode == 0, verify_490.stderr
    assert json.loads(verify_490.stdout)["verified"] is True

    # Default CHEM312 keeps CHEM312_Dossier; explicit --project-label still overrides
    from scripts.fact_ledger import build_fact_ledger
    ledger_312 = build_fact_ledger(artifact_paths=[sample], base_dir=tmp_path)
    assert ledger_312["course_id"] == "CHEM312"
    assert ledger_312["project_label"] == "CHEM312_Dossier"
    ledger_custom = build_fact_ledger(artifact_paths=[sample], base_dir=tmp_path, course_id="CHEM490", project_label="H2O_HF_Capstone")
    assert ledger_custom["project_label"] == "H2O_HF_Capstone"

    # README footer wording updated
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "(CHEM 490 / instructor only)" not in readme
    assert "(Instructor backend only — never used directly by students)" in readme


def test_qa490_r2_gui_pyscf_local_registration_and_3d_viewer_overflow(
    tmp_path: Path,
) -> None:
    """Verify GUI-R2-01 (PySCF Step 4 registration & Prepare calculation download) and GUI-R2-02 (zero 3D scrollbar)."""
    import hashlib
    import io
    import zipfile

    from cochem_base.calc.calculation_service import CalculationMatrixConfig
    from cochem_base.calc.local_publication import _role, sidecar
    from cochem_base.geometry.nuclide_geometry import parse_geometry_identity
    from cochem_base.interfaces.local_calculations import SavedLocalCalculation, _saved_label
    from cochem_base.interfaces.molecule_viewer import molecule_viewer_html
    from cochem_base.interfaces.student_reports import observation_from_completed_local_calculation

    run_id = "job_" + "a" * 32
    assert _role("pyscf.out", set(), set()) == "native-output"
    assert _role(f"{run_id}_pyscf.py", set(), set()) == "native-input"
    assert _role(f"{run_id}_pyscf.result.json", set(), set()) == "native-scientific-data"
    assert _saved_label(1, {"engine": "xtb", "operation": "optimization"}) == "Saved calculation 1 · GFN2-xTB · Geometry optimization"
    assert _saved_label(2, {"engine": "pyscf", "operation": "single_point"}) == "Saved calculation 2 · PySCF · RHF single point"

    # Construct a complete checksummed PySCF Results/ directory and verify real observation + HTML rendering
    art = tmp_path / "artifacts"
    run_dir = art / "GUI" / ("run_" + "b" * 32)
    res_dir = run_dir / "Results"
    res_dir.mkdir(parents=True)

    water_xyz = "3\nwater\nO 0.0 0.0 0.0\nH 0.0 0.757 0.586\nH 0.0 -0.757 0.586\n"
    identity = parse_geometry_identity(water_xyz)
    coords = [list(row) for row in identity.coordinates_angstrom]
    config = CalculationMatrixConfig(
        engine="pyscf",
        method="HF/STO-3G",
        basis_set="STO-3G",
        charge=0,
        multiplicity=1,
        geometry=water_xyz,
        is_opt=False,
        is_freq=False,
        is_vpt2=False,
    )
    config_bytes = config.model_dump_json(indent=2).encode("utf-8")
    (run_dir / "matrix_config.json").write_bytes(config_bytes)

    def _write_checked(name: str, data: bytes) -> None:
        (res_dir / name).write_bytes(data)
        (res_dir / f"{name}.sha256").write_bytes(sidecar(name, data))

    deck_bytes = b"# PySCF RHF STO-3G deck\n"
    deck_sha = hashlib.sha256(deck_bytes).hexdigest()
    worker_result = {
        "engine": "PySCF",
        "version": "2.14.0",
        "method": "RHF",
        "basis": "STO-3G",
        "scf_converged": True,
        "energy_hartree": -74.963905001272,
        "gradients_hartree_per_bohr": [[0.0, 0.0, 0.0]] * 3,
        "input_sha256": deck_sha,
    }
    final_result = {
        **worker_result,
        "engine": "pyscf",
        "elements": list(identity.elements),
        "coordinates_angstrom": coords,
        "charge": 0,
        "multiplicity": 1,
        "converged": True,
        "nuclides": list(identity.nuclides),
        "nuclear_identity": identity.metadata,
    }
    receipt = {
        "status": "EXECUTION_VERIFIED",
        "config_file": str(run_dir / "matrix_config.json"),
        "engine": "pyscf",
        "method": "HF/STO-3G",
        "basis_set": "STO-3G",
        "dry_run": False,
        "scratch_dir": str(run_dir / "Scratch" / run_id),
        "operation": "single_point",
        "output_dir": str(res_dir),
        "run_id": run_id,
        "timestamp": "2026-11-23T20:00:00",
    }
    _write_checked("matrix_config.validated.json", config_bytes)
    _write_checked("ingress_alignment.json", json.dumps({
        "method": "mass_weighted_COM_and_Eckart_SVD",
        "elements": list(identity.elements),
        "nuclear_identity": identity.metadata,
        "original_coordinates_angstrom": coords,
        "coordinates_angstrom": coords,
    }).encode("utf-8"))
    _write_checked("execution_authority.json", json.dumps({
        "engine": "pyscf",
        "binary_sha256": "c" * 64,
    }).encode("utf-8"))
    _write_checked(f"{run_id}_pyscf.py", deck_bytes)
    _write_checked(f"{run_id}_pyscf.result.json", json.dumps(worker_result).encode("utf-8"))
    _write_checked("pyscf.out", b"converged SCF energy = -74.963905001272\n")
    _write_checked("stderr.log", b"")
    _write_checked("result.json", json.dumps(final_result).encode("utf-8"))
    _write_checked("execution.json", json.dumps(receipt).encode("utf-8"))

    obs = observation_from_completed_local_calculation(receipt, results_directory=res_dir)
    assert obs["method"]["engine"] == "pyscf"
    assert obs["method"]["method"] == "RHF"
    assert obs["method"]["basis"] == "STO-3G"
    assert obs["energy_hartree"] == pytest.approx(-74.963905001272)

    with _scoped_env(
        COCHEM_ARTIFACT_DIR=str(art),
        COCHEM_CONFIG=str(tmp_path / "absent-registry.json"),
        COCHEM_STUDENT_AUTO_REMOTE_CHECK="0",
    ):
        from ui.voila_layout.cochem_gui import CoChemGUI, completed_xtb_result_html
        from ui.voila_layout.workspace_layout import apply_workspace_layout
        from ui.voila_layout.workspace_style import WORKSPACE_CSS

        card_html = completed_xtb_result_html(receipt, res_dir)
        assert "Saved PySCF RHF single-point result" in card_html
        assert "RHF / STO-3G" in card_html
        assert "-74.963905001272 Hartree" in card_html

        gui = CoChemGUI()
        apply_workspace_layout(gui)
        gui._local_file_operation = None
        view_gen = gui._local_view_generation
        gui._publish_completed_xtb_result(receipt, res_dir, view_gen)
        assert "Saved PySCF RHF single-point result" in gui.calculation_result.value

        xtb_summary = SavedLocalCalculation("job_" + "1" * 32, "Saved calculation 1 · GFN2-xTB · Geometry optimization", "retained-native-files-and-submission-context", ())
        pyscf_summary = SavedLocalCalculation(run_id, "Saved calculation 2 · PySCF · RHF single point", "retained-native-files-and-submission-context", ())
        gui._apply_saved_local_catalog((xtb_summary, pyscf_summary))
        gui._viewed_local_record_id = pyscf_summary.record_id
        gui.viewed_local_calculation.value = f"<p><b>Viewing:</b> {pyscf_summary.label}</p>"
        gui._refresh_local_file_controls()

        option_labels = [label for label, _ in gui.saved_local_calculation.options]
        assert "Saved calculation 1 · GFN2-xTB · Geometry optimization" in option_labels
        assert "Saved calculation 2 · PySCF · RHF single point" in option_labels
        assert "No registered local result is being viewed" not in gui.viewed_local_calculation.value
        assert gui.btn_save_local_files.disabled is False

        # On POSIX (Linux/Codespaces/WSL2), also exercise full LocalCalculationStore + retained_files_zip end-to-end
        if os.name == "posix" and hasattr(os, "O_NOFOLLOW"):
            from cochem_base.calc.local_publication import finalize_publication
            from cochem_base.core.managed_files import open_directory_chain
            from cochem_base.interfaces.local_calculations import LocalCalculationStore

            sandbox_dir = run_dir / "Scratch" / run_id
            sandbox_dir.mkdir(parents=True)
            native_members = {p.name for p in res_dir.iterdir() if p.name not in {"execution.json", "execution.json.sha256"}}
            with open_directory_chain(res_dir) as stage_b, open_directory_chain(sandbox_dir) as sb_b:
                published_receipt = finalize_publication(
                    staging=res_dir, sandbox=sandbox_dir, native_members=native_members,
                    receipt=receipt, submitted_config=config_bytes, input_snapshot=None,
                    stage_binding=stage_b, sandbox_binding=sb_b,
                )
            assert published_receipt["retained_files"]["available"] is True
            store = LocalCalculationStore(art)
            saved = store.register_completed(published_receipt, results_directory=res_dir)
            assert saved.label == "Saved calculation 1 · PySCF · RHF single point"
            archive = store.retained_files_zip(saved.record_id)
            with zipfile.ZipFile(io.BytesIO(archive.content), "r") as zf:
                names = set(zf.namelist())
                assert "manifest.json" in names
                assert "native/result.json" in names
                assert f"native/{run_id}_pyscf.py" in names

        # GUI-R2-02: Zero horizontal scrollbar on 2 · Add your molecule 3D Structure preview
        assert gui.inputs_viewer_output.layout.overflow == "hidden"
        assert gui.viewer_output.layout.overflow == "hidden"
        assert gui.inputs_preview_columns.layout.overflow == "hidden"
        assert ".jp-OutputArea-output" in WORKSPACE_CSS
        assert "overflow-x: hidden !important" in WORKSPACE_CSS
        viewer_html = molecule_viewer_html(water_xyz)
        assert "box-sizing:border-box" in viewer_html
        assert "overflow-x:hidden !important" in viewer_html
        assert "canvas.style.maxWidth = '100%'" in viewer_html
        assert "ResizeObserver" in viewer_html
