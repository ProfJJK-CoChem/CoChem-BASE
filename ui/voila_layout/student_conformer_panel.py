"""The shared student start page and results controls for public course forks."""
import base64
import hashlib
import html
import json
import os
from pathlib import Path
import re
import threading
import uuid

import ipywidgets as w

from cochem_base.interfaces.conformer_actions import ConformerActions
from cochem_base.interfaces.student_request import REPOSITORY_PATTERN
from ui.voila_layout.disclosure import Disclosure

BASE = "https://github.com/ProfJJK-CoChem/CoChem-BASE"
COURSES = {
    "Choose a course or research group": "Everyone can try ethanol. Your assignment identifies the molecule and evidence to turn in.",
    "CHEM 490 directed research": "Keep the starting file, run link, method, units and an interpretation in your weekly research record. Compare candidate structures before choosing one for later spectroscopy or a potential-energy scan.",
    "Graduate research": "Save the native files, method, basis, charge, spin and convergence information. Use the screened structures to plan the next calculation with your adviser. The ethanol exercise uses a small basis for teaching.",
    "Physical Chemistry I": "Use the physical model and units in your assignment. To compare energies, use one method and subtract its lowest energy from every value. An equilibrium constant requires additional thermodynamic information.",
    "Physical Chemistry II": "Connect a calculated quantity with a measurement. Label each as calculated or measured and explain its assumptions. Look up rotational constants, frequencies or isotopes in Help search. Follow the current assignment for the sequence.",
    "CHEM 312 Organic Chemistry II CURE": "Follow your group's current role sheet. The calculation lead records the run link and raw files. The literature, bench and spectroscopy partners connect the predicted structure to their evidence. Bring a comparison, its units and an open question to the group.",
}


def _button(label, primary=False):
    return w.Button(description=label, button_style="primary" if primary else "", layout=w.Layout(width="auto"))


def _link(url, label):
    return f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(label)}</a>'


def _file(name, data, label, mime):
    encoded = base64.b64encode(data).decode("ascii")
    return f'<a download="{html.escape(name, quote=True)}" href="data:{mime};base64,{encoded}">{label}</a>'


class StudentConformerPanel:
    def __init__(self, gui):
        self.gui = gui
        self.course = w.Dropdown(options=list(COURSES), description="Course guide:", style={"description_width":"initial"})
        self.course_note = w.HTML()
        def show_course(change=None):
            self.course_note.value = "<p>" + html.escape(COURSES[self.course.value]) + "</p>"
        self.course.observe(show_course, names="value")
        show_course()
        self.repo = gui.gh_repo_input
        self.source = w.ToggleButtons(options=["Practice with ethanol", "Use my XYZ file"], description="Molecule:")
        self.upload = w.FileUpload(accept=".xyz", multiple=False, description="Choose XYZ file")
        self.consent = w.Checkbox(description="My instructor approved this file for publication in my public fork.", indent=False, layout=w.Layout(width="100%"))
        self.custom = w.VBox([w.HTML("<p>Choose a plain-text XYZ file from your computer. Use one neutral, closed-shell molecule with 2–16 H, C, N or O atoms and coordinates in angstrom. CoChem saves this file publicly when you click Run.</p>"), self.upload, self.consent])
        self.run = _button("Run in CoChem", True)
        self.reset = _button("Start another calculation")
        self.refresh = _button("Check run and get files")
        self.address = w.Text(description="Run link:", placeholder="Paste the GitHub run link you saved", style={"description_width":"initial"}, layout=w.Layout(width="95%"))
        self.status, self.downloads, self.fallback = w.HTML(), w.HTML(), w.HTML()
        self.busy = self.locked = False
        self.record = None
        self.address.observe(self._address_changed, names="value")
        self.repo.observe(self._project_changed, names="value")
        for widget in (self.source, self.upload, self.consent):
            widget.observe(self._inputs_changed, names="value")
        self.run.on_click(self._submit)
        self.refresh.on_click(self._refresh)
        self.reset.on_click(self._reset)
        self.results = w.VBox([w.HTML("<h3>Your public course run</h3><p>Save the run link. After closing this page, paste it here to reopen the same calculation. Click <b>Check run and get files</b>. A queued or running job still needs time.</p>"), self.address, self.refresh, self.status, self.downloads, self.reset])
        self.start = w.VBox([w.HTML("<h3>Run your first molecule</h3><p>Try ethanol first. CREST looks for different shapes, MACE ranks their energies, and CPU PySCF adjusts the lowest-energy candidate in that ranking. GitHub runs the calculation. You can leave after saving its run link.</p>"),
            w.HTML("<p><b>1.</b> Sign in to GitHub and create a <b>fork</b>, your own public copy of the course project. " + _link(BASE+"/fork","Create my public fork") + ". Choose your account as Owner and click <b>Create fork</b>. Open <b>Actions</b> in your copy and enable workflows if asked.</p><p><b>2.</b> Check the GitHub project below. It should read <b>your-account/your-project</b>. Copy those two names from the top of your fork's page. Choose your molecule, then click <b>Run in CoChem</b> once.</p>"),
            self.repo, self.source, self.custom, self.run, self.results,
            Disclosure("Run using the GitHub buttons instead", self.fallback),
            Disclosure("Guidance for my course or research group", self.course, self.course_note)])
        self._project_changed()

    def _record_path(self):
        from cochem_base.config_loader import get_artifact_dir
        key = hashlib.sha256(self.repo.value.strip().lower().encode()).hexdigest()
        return Path(get_artifact_dir()) / "StudentConformers" / (key+".json")

    def _project_changed(self, change=None):
        repository = self.repo.value.strip()
        valid = REPOSITORY_PATTERN.fullmatch(repository)
        url = f"https://github.com/{repository}/actions/workflows/student_conformers.yml" if valid else BASE+"/fork"
        self.fallback.value = "<p>In your fork, click <b>Actions → Student conformers (CREST, MACE, CPU PySCF) → Run workflow</b>. Leave <b>ethanol.xyz</b> for practice, then click the green <b>Run workflow</b>. " + _link(url,"Open GitHub") + " · " + _link(BASE+"/blob/main/student/README.md","Read the click-by-click instructions") + ".</p>"
        self.record = None
        if valid:
            try:
                saved = json.loads(self._record_path().read_text(encoding="utf-8"))
                if saved["repository"].lower() == repository.lower() and type(saved["id"]) is int and saved["id"] > 0:
                    self.record = saved
            except (OSError, ValueError, KeyError, TypeError):
                pass
        self.address.value = self._url(self.record["id"]) if self.record else ""
        self.locked = bool(self.record)
        self.downloads.value = ""
        self.status.value = "<p role='status'>"+("Your last submitted run is ready to check." if self.record else "Choose your public fork and molecule, then click Run in CoChem once.")+"</p>"
        self._inputs_changed()

    def _url(self, number):
        return f"https://github.com/{self.repo.value.strip()}/actions/runs/{number}"

    def _address_changed(self, change=None):
        self.downloads.value = ""
        self.refresh.disabled = self.busy or not self.address.value.strip()

    def _inputs_changed(self, change=None):
        custom = self.source.value == "Use my XYZ file"
        self.custom.layout.display = "" if custom else "none"
        self.run.disabled = self.busy or self.locked or not REPOSITORY_PATTERN.fullmatch(self.repo.value.strip()) or (custom and not (self.upload.value and self.consent.value))
        self.refresh.disabled = self.busy or not self.address.value.strip()
        self.reset.layout.display = "" if self.locked else "none"
        for widget in (self.reset, self.source, self.repo, self.address, self.upload, self.consent):
            widget.disabled = self.busy

    def _reset(self, _):
        self.record = None
        self.address.value = ""
        self.downloads.value = ""
        self.consent.value = False
        self.locked = False
        self.status.value = "<p>Choose the next molecule. Earlier runs remain in your fork's Actions history.</p>"
        self._inputs_changed()

    def _work(self, operation, publish, message):
        if self.busy:
            return
        self.busy = True
        self.downloads.value = ""
        self._inputs_changed()
        self.status.value = "<p role='status'>"+message+"</p>"
        def worker():
            try:
                value, err = operation(), None
            except Exception as exc:
                value, err = None, exc
            def finish():
                try:
                    if err is None:
                        publish(value)
                    else:
                        if getattr(err, "uncertain", False):
                            self.locked = True
                        self.status.value = "<p role='alert'>"+html.escape(str(err))+"</p><p>Open Actions in your fork. If GitHub already lists your run, copy its address here and check it before starting another. You can also use the GitHub buttons.</p>"
                finally:
                    self.busy = False
                    self._inputs_changed()
            self.gui._ui_call(finish)
        threading.Thread(target=worker, daemon=True).start()

    def _submit(self, _):
        if self.run.disabled:
            return
        repo = self.repo.value.strip()
        data = None
        if self.source.value == "Use my XYZ file":
            selected = self.upload.value[0]
            if selected["size"] > 8192:
                self.status.value = "<p role='alert'>Choose an XYZ file smaller than 8 KiB.</p>"
                return
            data = bytes(selected["content"])
        def publish(record):
            self.record = record
            self.locked = True
            self.address.value = self._url(record["id"])
            self.status.value = "<p role='status'>Submitted. Save "+_link(self.address.value,"this GitHub run link")+". Click Check run and get files to see progress. To stop this public workflow, open its run link and choose Cancel workflow.</p>"
            try:
                path = self._record_path()
                path.parent.mkdir(parents=True, exist_ok=True)
                temp = path.with_suffix("."+uuid.uuid4().hex+".tmp")
                temp.write_text(json.dumps(record), encoding="utf-8")
                os.replace(temp, path)
            except OSError:
                self.status.value += "<p>Copy your run link now. This workspace could not save it.</p>"
        self._work(lambda: ConformerActions(repo).submit_conformer(data), publish, "Asking GitHub to start one calculation. Please wait.")

    def _refresh(self, _):
        repo = self.repo.value.strip()
        match = re.fullmatch(r"https://github\.com/"+re.escape(repo)+r"/actions/runs/([1-9][0-9]*)/?", self.address.value.strip(), re.IGNORECASE)
        if not REPOSITORY_PATTERN.fullmatch(repo) or not match:
            self.status.value = "<p role='alert'>Copy the address of one Actions run from the project shown above. It ends in /actions/runs/ followed by a number.</p>"
            return
        number = int(match[1])
        expected = self.record if self.record and self.record["id"] == number else None
        def publish(value):
            run, bundle = value
            if bundle is None:
                status = run.get("conclusion") or run["status"]
                self.status.value = "<p role='status'>GitHub reports <b>"+html.escape(str(status).replace("_"," "))+"</b>. "+_link(self._url(number),"Open this run")+" for its steps. Check again after it finishes.</p>"
                return
            name, data, checksum, receipt = bundle
            self.status.value = f"<p role='status'>Results verified. CREST found {receipt['candidate_count']} candidate shapes. MACE selected {html.escape(receipt['selected'])}. CPU PySCF optimized that shape.</p>"
            self.downloads.value = "<p>"+_file(name,data,"Save results ZIP","application/zip")+" · "+_file(name+".sha256",checksum,"Save checksum","text/plain")+"</p><p>Look in your browser’s Downloads folder. The ZIP holds your molecule files and calculations. The checksum lets your instructor check the copy. Open the Google Drive folder in your assignment, choose <b>New → File upload</b>, and upload these two files. Leave this ZIP closed for submission. Include the run link in your report.</p>"
        self._work(lambda: ConformerActions(repo).read_run(number, expected), publish, "Checking the selected GitHub run and its results.")
