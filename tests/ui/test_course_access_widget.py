"""Actual widgets and data-only enrollment, without impersonated GitHub access."""
from __future__ import annotations

import html
import json
import os
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from cochem.core.context import AirGapViolationError
from cochem_base.interfaces.course_access import parse_enrollment
from ui.voila_layout.cochem_gui import CourseAccessWidget


class EnrollmentAnchors(HTMLParser):
    def __init__(self, content: str) -> None:
        super().__init__()
        self.links: list[dict[str, str | None]] = []
        self.feed(content)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.links.append(dict(attrs))


def panel(tmp_path: Path) -> CourseAccessWidget:
    return CourseAccessWidget(project_repository="student/vdw-research", artifact_dir=tmp_path / "data")


def enrollment(widget: CourseAccessWidget):
    links = EnrollmentAnchors(widget.links.value).links
    assert len(links) == 2
    for link in links:
        assert link["target"] == "_blank"
        assert set(str(link["rel"]).split()) == {"noopener", "noreferrer"}
        assert urlsplit(str(link["href"])).hostname == "github.com"
    issue = urlsplit(str(links[1]["href"]))
    assert issue.path == "/instructor/private-lab-controller/issues/new"
    return parse_enrollment(parse_qs(issue.query)["body"][0])


def configure(widget: CourseAccessWidget) -> None:
    widget.controller.value = "instructor/private-lab-controller"
    widget.app_slug.value = "instructor-chemistry-app"


def test_unconfigured_invitation_keeps_links_unavailable(tmp_path):
    widget = panel(tmp_path)
    assert widget.links.value == ""
    assert widget.btn_save.disabled
    assert widget.btn_refresh.disabled
    assert widget.app_slug.description == "Instructor lab App slug:"
    assert "[MISSING DATA]" in widget.status.value
    assert not widget._settings_path.exists()


def test_real_widgets_generate_exact_private_project_request(tmp_path):
    widget = panel(tmp_path)
    configure(widget)
    request = enrollment(widget)
    assert request.repository == "student/vdw-research"
    assert request.engines == ("orca", "cfour")
    assert "Authorize lab app" in widget.links.value
    assert "Request project access" in widget.links.value
    assert "Access has not been verified" in widget.status.value
    assert not widget._settings_path.exists()


def test_optional_engines_can_both_be_declined(tmp_path):
    widget = panel(tmp_path)
    configure(widget)
    widget.orca.value = False
    widget.cfour.value = False
    assert enrollment(widget).engines == ()
    widget.cfour.value = True
    assert enrollment(widget).engines == ("cfour",)


@pytest.mark.parametrize("field, value", [
    ("controller", "https://github.com/instructor/private-controller"),
    ("controller", "instructor/../project"),
    ("app_slug", "bad-app' onclick='steal()"),
    ("app_slug", "<script>alert(1)</script>"),
    ("project", "student/private-project?token=secret"),
])
def test_invalid_invitation_removes_stale_links_safely(tmp_path, field, value):
    widget = panel(tmp_path)
    configure(widget)
    if field == "controller":
        widget.controller.value = value
    elif field == "app_slug":
        widget.app_slug.value = value
    else:
        widget.set_project(value)
    assert widget.links.value == ""
    assert widget.btn_save.disabled
    assert "unavailable" in widget.status.value
    assert "<script>" not in widget.status.value
    assert not widget._settings_path.exists()


def test_project_change_rebuilds_enrollment_without_granting_access(tmp_path):
    widget = panel(tmp_path)
    configure(widget)
    widget.set_project("another-student/new-private-project")
    assert enrollment(widget).repository == "another-student/new-private-project"
    assert "Access has not been verified" in widget.status.value
    widget.set_project("")
    assert not widget.links.value and widget.btn_save.disabled


def test_save_click_retains_only_nonsecret_settings_and_reopens(tmp_path):
    widget = panel(tmp_path)
    configure(widget)
    widget.orca.value = False
    widget.btn_save.click()
    receipt = json.loads(widget._settings_path.read_text(encoding="utf-8"))
    assert receipt == {"schema": "cochem.course-invitation/1",
        "controller_repository": "instructor/private-lab-controller",
        "app_slug": "instructor-chemistry-app", "engines": ["cfour"]}
    assert "No credentials were stored" in widget.status.value
    reopened = panel(tmp_path)
    assert enrollment(reopened).engines == ("cfour",)
    assert "Access has not been verified" in reopened.status.value
    configured = CourseAccessWidget(project_repository="student/vdw-research", artifact_dir=tmp_path / "data",
        controller_repository="instructor/new-controller", app_slug="new-course-app")
    assert configured.controller.value == "instructor/new-controller"
    assert configured.app_slug.value == "new-course-app"


def test_damaged_retained_invitation_does_not_abort_widget(tmp_path):
    widget = panel(tmp_path)
    widget._settings_path.parent.mkdir()
    widget._settings_path.write_text('{"unexpected": true}', encoding="utf-8")
    reopened = panel(tmp_path)
    assert not reopened.links.value and reopened.btn_save.disabled
    assert "Retained lab invitation was not loaded" in reopened.status.value
    assert json.loads(widget._settings_path.read_text()) == {"unexpected": True}


def test_settings_symlink_cannot_overwrite_other_student_data(tmp_path):
    widget = panel(tmp_path)
    configure(widget)
    widget._settings_path.parent.mkdir()
    original = tmp_path / "retained-results.txt"
    original.write_text("original research data", encoding="utf-8")
    widget._settings_path.symlink_to(original)
    widget.btn_save.click()
    assert "could not be retained" in widget.status.value
    assert original.read_text() == "original research data"


def test_invitation_is_not_saved_inside_application_source():
    source = Path(__file__).resolve().parents[2]
    with pytest.raises(AirGapViolationError, match="outside|SOURCE|immutable|codebase"):
        CourseAccessWidget(project_repository="student/vdw-research", artifact_dir=source)


def test_actual_gui_integration_has_no_fabricated_license_readiness(tmp_path):
    environment = dict(os.environ, COCHEM_ARTIFACTS=str(tmp_path / "data"),
        COCHEM_ARTIFACT_DIR=str(tmp_path / "data"), COCHEM_CONFIG=str(tmp_path / "absent-registry.json"),
        COCHEM_STUDENT_AUTO_SETUP="false", COCHEM_STUDENT_AUTO_REMOTE_CHECK="false", CODESPACES="false",
        GITHUB_REPOSITORY="student/vdw-research", GITHUB_REF_NAME="main",
        COCHEM_ACCESS_CONTROLLER_REPOSITORY="instructor/private-lab-controller",
        COCHEM_ACCESS_APP_SLUG="instructor-chemistry-app")
    completed = subprocess.run([sys.executable, str(Path(__file__).resolve()), "actual-gui"],
        env=environment, capture_output=True, text=True, stdin=subprocess.DEVNULL,
        timeout=60, check=False)
    assert completed.returncode == 0, completed.stdout + completed.stderr


def exercise_actual_gui() -> None:
    from ui.voila_layout.cochem_gui import CoChemGUI
    gui = CoChemGUI()
    try:
        assert gui.course_access_panel in gui.gh_setup_box.children
        assert enrollment(gui.course_access_panel).repository == "student/vdw-research"
        assert gui.course_access_panel.btn_refresh.disabled is False
        assert all(item["provisionable"] is False for item in gui._remote_engine_availability.values())
        gui.course_access_panel.btn_refresh.click()
        assert "local or HPC" in gui.course_access_panel.status.value
        assert gui._remote_probe_running is False
        gui.calc_env_dropdown.value = "github-actions"
        assert {"ORCA", "CFOUR"}.isdisjoint(value for _, value in gui.matrix_engine.options)
        gui.gh_repo_input.value = "student/second-private-project"
        assert enrollment(gui.course_access_panel).repository == "student/second-private-project"
        gui.gh_repo_input.value = "invalid-project"
        gui.course_access_panel.btn_refresh.click()
        assert "repository" in html.unescape(gui.remote_engine_status.value)
        assert gui._remote_probe_running is False
        assert not gui._pipeline_running and not gui._actions_running
    finally:
        gui._inbox_stop.set()
        gui._hpc_monitor_stop.set()
        gui._actions_monitor_stop.set()
        gui._cleanup_topos_search()


if __name__ == "__main__":
    if sys.argv[1:] == ["actual-gui"]:
        exercise_actual_gui()
    else:
        raise SystemExit("Select the actual-gui admission case.")
