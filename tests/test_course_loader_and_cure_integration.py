"""Zero-mock tests for CoChem-BASE 'Is this a course?' prompt, CoChem-CURE dynamic loader,
Voilà GUI course-mode toggle, and student/handoff.py dynamic course ID resolution."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import venv

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ci_tools.source_quarantine import source_paths
from cochem_base import course_loader


_PEP517_BACKEND_SOURCE = '''"""Minimal pure-stdlib PEP 517 backend for test CoChem-CURE package."""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path
import zipfile


def build_wheel(wheel_directory: str, config_settings=None, metadata_directory=None) -> str:
    root = Path(__file__).resolve().parent
    src_pkg = root / "src" / "cochem_cure"
    dist_info = "cochem_cure-0.1.0.dist-info"
    wheel_name = "cochem_cure-0.1.0-py3-none-any.whl"
    wheel_path = Path(wheel_directory) / wheel_name
    records: list[str] = []

    def _add(zf: zipfile.ZipFile, arcname: str, data: bytes) -> None:
        zf.writestr(arcname, data)
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode("ascii")
        records.append(f"{arcname},sha256={digest},{len(data)}")

    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(src_pkg.rglob("*.py")):
            rel = file_path.relative_to(root / "src").as_posix()
            _add(zf, rel, file_path.read_bytes())
        _add(
            zf,
            f"{dist_info}/METADATA",
            b"Metadata-Version: 2.1\\nName: cochem-cure\\nVersion: 0.1.0\\n",
        )
        _add(
            zf,
            f"{dist_info}/WHEEL",
            b"Wheel-Version: 1.0\\nGenerator: cochem-test-backend\\nRoot-Is-Purelib: true\\nTag: py3-none-any\\n",
        )
        records.append(f"{dist_info}/RECORD,,")
        zf.writestr(f"{dist_info}/RECORD", ("\\n".join(records) + "\\n").encode("utf-8"))
    return wheel_name
'''

_CURE_PYPROJECT_TOML = '''[build-system]
requires = []
build-backend = "_pep517_backend"
backend-path = ["."]

[project]
name = "cochem-cure"
version = "0.1.0"
description = "CoChem-CURE canonical course provider fixture for zero-mock testing"
'''

_CURE_PROVIDER_SOURCE = '''"""Canonical cochem.course-provider/1 test fixture package."""
from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "cochem.course-provider/1"

_COURSES: dict[str, dict[str, Any]] = {
    "CHEM311": {
        "course_id": "CHEM311",
        "aliases": ["CHEM 311", "CoChem-QUEST"],
        "title": "Organic Chemistry I (CoChem-QUEST)",
        "institution": "Cumberland University",
        "summary": "Local WSL2 isomerism, conformers, and rotational spectroscopy.",
        "execution_stack": "Local WSL2 (activate_cochem_wsl.sh) + RDKit/xTB/CREST/PySCF/SPCAT",
        "milestones": [
            {"id": "M0", "title": "Local WSL2 Setup", "summary": "Verify workstation engines."},
            {"id": "M1", "title": "Constitutional Isomers", "summary": "Compare C3H6O structures."},
        ],
        "modules": [
            {"id": "mod0", "title": "Environment verification"},
            {"id": "mod1", "title": "Acetone vs propanal"},
        ],
        "guide_markdown": "# CHEM 311 Pathway\\nActivate WSL2 and run Modules 0-5.",
    },
    "CHEM495": {
        "course_id": "CHEM495",
        "aliases": ["CHEM 495", "CAPSTONE"],
        "title": "Advanced Computational Spectroscopy Capstone",
        "institution": "Cumberland University",
        "summary": "Dynamic course ID supplied exclusively by CoChem-CURE.",
        "execution_stack": "Local WSL2 ORCA 6.1.1 + cochem_workstation_job_runner CCSD(T) handoff",
        "milestones": [
            {"id": "C1", "title": "Anharmonic VPT2", "summary": "Compute B0 constants."},
        ],
        "modules": [
            {"id": "cap1", "title": "VPT2 calibration"},
        ],
        "guide_markdown": "# CHEM 495 Capstone\\nSubmit cochem.student-handoff/2 bundles.",
    },
}


def get_allowed_course_ids() -> tuple[str, ...]:
    return tuple(_COURSES.keys())


def validate_course_id(course_id: str) -> str:
    cleaned = str(course_id or "").strip().upper()
    if cleaned in _COURSES:
        return cleaned
    for cid, entry in _COURSES.items():
        if cleaned in {a.upper() for a in entry.get("aliases", [])}:
            return cid
    raise ValueError(f"Unknown course_id {course_id!r}; allowed: {get_allowed_course_ids()}")


def list_courses() -> list[dict[str, Any]]:
    return [dict(entry) for entry in _COURSES.values()]


def get_course_profile(course_id: str) -> dict[str, Any]:
    cid = validate_course_id(course_id)
    entry = _COURSES[cid]
    return {
        "course_id": entry["course_id"],
        "aliases": list(entry["aliases"]),
        "title": entry["title"],
        "institution": entry["institution"],
        "summary": entry["summary"],
        "execution_stack": entry["execution_stack"],
        "milestones": list(entry["milestones"]),
    }


def get_course_milestones(course_id: str) -> list[dict[str, Any]]:
    cid = validate_course_id(course_id)
    return [dict(item) for item in _COURSES[cid]["milestones"]]


def get_course_pathway(course_id: str) -> dict[str, Any]:
    cid = validate_course_id(course_id)
    entry = _COURSES[cid]
    return {
        "course_id": cid,
        "profile": get_course_profile(cid),
        "modules": list(entry["modules"]),
        "steps": list(entry["modules"]),
        "milestones": get_course_milestones(cid),
        "execution_stack": entry["execution_stack"],
        "guide_markdown": entry["guide_markdown"],
    }
'''


def _create_temp_cure_git_repo(root: Path) -> Path:
    repo = root / "CoChem-CURE"
    pkg = repo / "src" / "cochem_cure"
    pkg.mkdir(parents=True, exist_ok=True)
    (repo / "_pep517_backend.py").write_text(_PEP517_BACKEND_SOURCE, encoding="utf-8", newline="\n")
    (repo / "pyproject.toml").write_text(_CURE_PYPROJECT_TOML, encoding="utf-8", newline="\n")
    (pkg / "__init__.py").write_text(
        '"""Test CoChem-CURE package."""\nfrom cochem_cure import provider\n__all__ = ["provider"]\n',
        encoding="utf-8",
        newline="\n",
    )
    (pkg / "provider.py").write_text(_CURE_PROVIDER_SOURCE, encoding="utf-8", newline="\n")

    git_env = dict(
        os.environ,
        GIT_AUTHOR_NAME="CoChem Test",
        GIT_AUTHOR_EMAIL="cochem-test@example.invalid",
        GIT_COMMITTER_NAME="CoChem Test",
        GIT_COMMITTER_EMAIL="cochem-test@example.invalid",
    )
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "init test cure provider"],
        check=True,
        capture_output=True,
        text=True,
        env=git_env,
    )
    return repo


def _clean_python_env(*, extra_pythonpath: list[Path] | None = None, artifact_dir: Path | None = None) -> dict[str, str]:
    entries: list[str] = []
    if extra_pythonpath:
        entries.extend(str(p) for p in extra_pythonpath)
    entries.extend(source_paths(REPO_ROOT))
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(entries)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["COCHEM_STUDENT_AUTO_SETUP"] = "0"
    env["COCHEM_STUDENT_AUTO_REMOTE_CHECK"] = "0"
    if artifact_dir is not None:
        env["COCHEM_ARTIFACT_DIR"] = str(artifact_dir)
    return env


def test_research_mode_no_cure_and_state_persistence(tmp_path: Path) -> None:
    """Answering No saves course-mode.json in research mode without requiring CoChem-CURE."""
    art_dir = tmp_path / "artifacts"
    env = _clean_python_env(artifact_dir=art_dir)

    # Non-interactive --is-course no
    proc = subprocess.run(
        [sys.executable, "-B", "-m", "cochem_base.course_loader", "--is-course", "no", "--json"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["state"]["is_course"] is False
    assert payload["state"]["mode"] == "research"
    assert payload["state"]["selected_course_id"] is None

    state_file = art_dir / "StudentSetup" / "course-mode.json"
    assert state_file.is_file()
    saved = json.loads(state_file.read_text(encoding="utf-8"))
    assert saved["is_course"] is False
    assert saved["mode"] == "research"
    assert saved["selected_course_id"] is None

    # Interactive prompt defaulting to No
    art_interactive = tmp_path / "artifacts_interactive"
    env_int = _clean_python_env(artifact_dir=art_interactive)
    proc_int = subprocess.run(
        [sys.executable, "-B", "-m", "cochem_base.course_loader"],
        input="n\n",
        env=env_int,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert proc_int.returncode == 0, proc_int.stdout + proc_int.stderr
    assert "Is this a course? [y/N]:" in proc_int.stdout
    assert "Standalone research mode saved" in proc_int.stdout
    loaded = course_loader.load_course_mode_state(artifact_dir=art_interactive)
    assert loaded["is_course"] is False
    assert loaded["mode"] == "research"


def test_course_mode_fail_closed_when_cure_absent_and_traversal_rejected(tmp_path: Path) -> None:
    """Course queries fail closed when CoChem-CURE is absent, and path traversal is rejected."""
    art_dir = tmp_path / "artifacts"
    # Isolated interpreter without site-packages (-S is too bare; use isolated venv without cochem_cure)
    probe_code = (
        "import sys\n"
        f"sys.path.insert(0, {str(SRC_ROOT)!r})\n"
        "from cochem_base import course_loader\n"
        "assert course_loader.is_cure_installed() is False\n"
        "assert course_loader.get_allowed_course_ids() == course_loader.DEFAULT_FALLBACK_COURSE_IDS\n"
        "try:\n"
        "    course_loader.list_cure_courses()\n"
        "    raise AssertionError('Expected RuntimeError when CURE absent')\n"
        "except RuntimeError as exc:\n"
        "    assert 'CoChem-CURE is not installed' in str(exc)\n"
        "print('FAIL_CLOSED_OK')\n"
    )
    venv_dir = tmp_path / "bare_venv"
    venv.create(venv_dir, with_pip=False, system_site_packages=False)
    venv_py = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    proc = subprocess.run(
        [str(venv_py), "-B", "-c", probe_code],
        env={"PATH": os.environ.get("PATH", ""), "COCHEM_ARTIFACT_DIR": str(art_dir)},
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "FAIL_CLOSED_OK" in proc.stdout

    # Traversal rejection on artifact_dir and selected_course_id
    with pytest.raises(ValueError):
        course_loader.save_course_mode_state(True, "../escape", artifact_dir=art_dir)
    with pytest.raises(ValueError):
        course_loader.save_course_mode_state(False, None, artifact_dir=Path("relative/../escape"))


def test_obtain_cure_from_local_git_archive_readonly_and_cli_pathway(tmp_path: Path) -> None:
    """obtain_cure_repository installs read-only via git archive HEAD with zero writes to source repo."""
    cure_repo = _create_temp_cure_git_repo(tmp_path)
    before_files = sorted(p.relative_to(cure_repo).as_posix() for p in cure_repo.rglob("*") if ".git" not in p.parts)

    venv_dir = tmp_path / "cure_venv"
    venv.create(venv_dir, with_pip=True, system_site_packages=False)
    venv_py = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

    # Install read-only from temp local CoChem-CURE git repo into isolated venv
    install_receipt = course_loader.obtain_cure_repository(
        python_executable=str(venv_py),
        local_repo_dir=cure_repo,
        timeout=120.0,
    )
    assert install_receipt["status"] == "installed"
    assert install_receipt["source"] == "local_git_archive"
    assert install_receipt["schema_version"] == "cochem.course-provider/1"

    # Second call short-circuits cleanly without pip/network
    second_receipt = course_loader.obtain_cure_repository(
        python_executable=str(venv_py),
        local_repo_dir=cure_repo,
        timeout=120.0,
    )
    assert second_receipt["status"] == "already_installed"
    assert second_receipt["source"] == "installed"

    # Zero writes to the source CoChem-CURE checkout
    after_files = sorted(p.relative_to(cure_repo).as_posix() for p in cure_repo.rglob("*") if ".git" not in p.parts)
    assert after_files == before_files
    git_status = subprocess.run(
        ["git", "-C", str(cure_repo), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert git_status.stdout.strip() == ""

    # Run course_loader CLI inside that venv with CURE installed
    art_dir = tmp_path / "cure_artifacts"
    venv_env = dict(
        os.environ,
        PYTHONPATH=str(SRC_ROOT),
        PYTHONDONTWRITEBYTECODE="1",
        COCHEM_ARTIFACT_DIR=str(art_dir),
    )
    cli_proc = subprocess.run(
        [
            str(venv_py),
            "-B",
            "-m",
            "cochem_base.course_loader",
            "--is-course",
            "yes",
            "--list-courses",
            "--course",
            "CHEM311",
            "--show-pathway",
            "--json",
        ],
        env=venv_env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert cli_proc.returncode == 0, cli_proc.stdout + cli_proc.stderr
    data = json.loads(cli_proc.stdout)
    assert data["ok"] is True
    assert data["cure_installed"] is True
    assert data["state"]["is_course"] is True
    assert data["state"]["selected_course_id"] == "CHEM311"
    course_ids = [c["course_id"] for c in data["courses"]]
    assert "CHEM311" in course_ids and "CHEM495" in course_ids
    assert data["pathway"]["course_id"] == "CHEM311"
    assert len(data["milestones"]) == 2


def test_student_handoff_dynamic_course_id_resolution(tmp_path: Path) -> None:
    """student/handoff.py stays pure-stdlib standalone and dynamically resolves CURE course IDs when available."""
    # Case 1: Pure standalone outside CoChem-BASE src/
    standalone_code = (
        "import sys; "
        f"sys.path = [{str(REPO_ROOT / 'student')!r}] + [p for p in sys.path if 'CoChem-BASE' not in p and 'cochem' not in p.lower()]; "
        "import handoff; "
        "assert handoff.get_allowed_course_ids() == handoff.V2_ALLOWED_COURSE_IDS; "
        "print('STANDALONE_OK')\n"
    )
    bare_venv = tmp_path / "standalone_venv"
    venv.create(bare_venv, with_pip=False, system_site_packages=False)
    bare_py = bare_venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    proc_standalone = subprocess.run(
        [str(bare_py), "-B", "-c", standalone_code],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert proc_standalone.returncode == 0, proc_standalone.stdout + proc_standalone.stderr
    assert "STANDALONE_OK" in proc_standalone.stdout

    # Case 2: With CoChem-BASE src/ + real temp CoChem-CURE package providing CHEM495
    cure_repo = _create_temp_cure_git_repo(tmp_path)
    dynamic_code = (
        "import sys; "
        f"sys.path.insert(0, {str(cure_repo / 'src')!r}); "
        f"sys.path.insert(0, {str(SRC_ROOT)!r}); "
        f"sys.path.insert(0, {str(REPO_ROOT)!r}); "
        "from student import handoff; "
        "allowed = handoff.get_allowed_course_ids(); "
        "assert 'CHEM495' in allowed and 'CHEM311' in allowed, allowed; "
        "manifest = {\n"
        "    'schema': handoff.SCHEMA_V2,\n"
        "    'workflow_type': 'conformer',\n"
        "    'input_name': 'h2co.xyz',\n"
        "    'charge': 0,\n"
        "    'multiplicity': 1,\n"
        "    'length_unit': 'angstrom',\n"
        "    'method': 'GFN2-xTB',\n"
        "    'basis': 'def2-SVP',\n"
        "    'solvation': 'gas',\n"
        "    'hessian_calculated': False,\n"
        "    'n_imaginary_modes': None,\n"
        "    'course_id': 'CHEM495',\n"
        "    'collaborator_institution': 'Tennessee Tech University',\n"
        "    'target_continuation': 'workstation',\n"
        "    'candidate_count': 1,\n"
        "    'commit': 'a' * 40,\n"
        "    'starting_xyz': 'input.xyz',\n"
        "    'primary_xyz': 'refined.xyz',\n"
        "    'repository': 'ProfJJK-CoChem/CoChem-BASE',\n"
        "    'run_id': '12345',\n"
        "    'attempt': '1',\n"
        "};\n"
        "validated = handoff.validate_v2_manifest_fields(manifest)\n"
        "assert validated['course_id'] == 'CHEM495'\n"
        "bad = dict(manifest, course_id='CHEM999')\n"
        "try:\n"
        "    handoff.validate_v2_manifest_fields(bad)\n"
        "    raise AssertionError('Expected HandoffValidationError for CHEM999')\n"
        "except handoff.HandoffValidationError:\n"
        "    print('REJECTED_CHEM999')\n"
        "print('DYNAMIC_HANDOFF_OK')\n"
    )
    proc_dyn = subprocess.run(
        [str(bare_py), "-B", "-c", dynamic_code],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert proc_dyn.returncode == 0, proc_dyn.stdout + proc_dyn.stderr
    assert "DYNAMIC_HANDOFF_OK" in proc_dyn.stdout


@pytest.mark.parametrize("case", ["gui_cure_absent", "gui_cure_installed"])
def test_gui_course_mode_toggle_preserves_draft(tmp_path: Path, case: str) -> None:
    """Real CoChemGUI widget visibility toggles for No vs Yes without mutating calculation drafts."""
    art_dir = tmp_path / f"artifacts_{case}"
    extra: list[Path] = []
    if case == "gui_cure_installed":
        cure_repo = _create_temp_cure_git_repo(tmp_path)
        extra.append(cure_repo / "src")
    env = _clean_python_env(extra_pythonpath=extra, artifact_dir=art_dir)
    env["COCHEM_CONFIG"] = str(tmp_path / "absent-registry.json")
    completed = subprocess.run(
        [sys.executable, "-B", str(Path(__file__).resolve()), case],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=90,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def _walk_widgets(widget, seen=None):
    seen = set() if seen is None else seen
    if widget.model_id in seen:
        return
    seen.add(widget.model_id)
    yield widget
    for child in getattr(widget, "children", ()):
        yield from _walk_widgets(child, seen)


def _gui_draft(gui):
    return (
        gui.matrix_geometry.value,
        gui.charge_input.value,
        gui.multiplicity_input.value,
        gui.matrix_engine.value,
        gui.matrix_method.value,
        gui.matrix_basis.value,
        gui.matrix_tier.value,
        gui.matrix_solvation.value,
        gui.product_class_selector.value,
        gui.cb_recipe_r1.value,
        gui.cb_recipe_r2.value,
        gui.native_operation.value,
        gui.actions_operation.value,
        gui.xtb_task.value,
    )


def _exercise_gui_case(case: str) -> None:
    from cochem_base import course_loader as cl
    from ui.voila_layout.cochem_gui import CoChemGUI

    gui = CoChemGUI()
    for worker_name in ("_student_setup_initial_worker", "_research_capability_worker"):
        worker = getattr(gui, worker_name, None)
        if worker is not None:
            worker.join(timeout=15)
            assert not worker.is_alive()

    # Regression guard invariants
    assert len(gui._initial_library_state_models) == 15
    assert list(gui.guided_step_buttons) == ["install", "inputs", "matrix", "modules"]
    install_widgets = tuple(_walk_widgets(gui.view_install))
    assert gui.course_mode_section in install_widgets
    assert gui.course_mode_selector in install_widgets

    # Default startup is always standalone research mode (zero auto-install/network)
    assert gui.course_mode_selector.value == "research"
    assert gui.btn_obtain_cure.layout.display == "none"
    assert gui.cure_course_selector.layout.display == "none"

    # Configure a real student draft
    raw = b"3\nWater draft\nO 0 0 0\nH 0 0 .96\nH .92 0 -.24\n"
    gui.xyz_upload.value = (
        {
            "name": "water.xyz",
            "type": "chemical/x-xyz",
            "size": len(raw),
            "content": memoryview(raw),
            "last_modified": datetime.now(timezone.utc),
        },
    )
    gui.matrix_engine.value = "XTB"
    gui.charge_input.value = 1
    gui.multiplicity_input.value = 2
    before = _gui_draft(gui)

    if case == "gui_cure_absent":
        # Toggle Yes when CoChem-CURE is not installed
        if not cl.is_cure_installed():
            gui.course_mode_selector.value = "course"
            assert gui.btn_obtain_cure.layout.display == ""
            assert gui.cure_course_selector.layout.display == "none"
            assert "CoChem-CURE" in gui.cure_pathway_status.value
            assert _gui_draft(gui) == before
            saved = cl.load_course_mode_state()
            assert saved["is_course"] is True
            gui.course_mode_selector.value = "research"
            assert gui.btn_obtain_cure.layout.display == "none"
            assert gui.cure_course_selector.layout.display == "none"
            assert _gui_draft(gui) == before
            saved_no = cl.load_course_mode_state()
            assert saved_no["is_course"] is False
    elif case == "gui_cure_installed":
        assert cl.is_cure_installed() is True
        gui.course_mode_selector.value = "course"
        assert gui.btn_obtain_cure.layout.display == "none"
        assert gui.cure_course_selector.layout.display == ""
        option_values = [val for _, val in gui.cure_course_selector.options]
        assert "CHEM311" in option_values and "CHEM495" in option_values
        assert _gui_draft(gui) == before

        gui.cure_course_selector.value = "CHEM495"
        assert "Advanced Computational Spectroscopy Capstone" in gui.cure_pathway_status.value
        assert "Anharmonic VPT2" in gui.cure_pathway_status.value
        assert _gui_draft(gui) == before
        saved = cl.load_course_mode_state()
        assert saved["is_course"] is True
        assert saved["selected_course_id"] == "CHEM495"

        gui.course_mode_selector.value = "research"
        assert gui.btn_obtain_cure.layout.display == "none"
        assert gui.cure_course_selector.layout.display == "none"
        assert _gui_draft(gui) == before
    else:
        raise ValueError(f"Unknown case: {case}")


if __name__ == "__main__":
    _exercise_gui_case(sys.argv[1])
