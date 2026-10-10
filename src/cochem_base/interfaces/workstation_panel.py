"""BASE app panel for the lab-workstation route: assign a Drive folder, follow jobs, import results.

Submitting only writes the job into the user's folder, so it never blocks the
app: a job may legitimately wait for hours while the workstation owner uses
the machine. A background check refreshes the selected job and retrieves its
verified results once the workstation publishes them.
"""
from __future__ import annotations

import atexit
import base64
import html
import io
import json
import threading
import zipfile
from pathlib import Path
from typing import Any, Callable

import ipywidgets as widgets

from .workstation_queue import (
    StudentWorkstationClient,
    WorkstationQueueError,
    assign_folder,
    load_settings,
)

STATE_STYLE = {"QUEUED": "#6c757d", "RUNNING": "#0056b3", "SUSPENDED": "#b8860b", "PAUSED": "#b8860b",
               "COMPLETED": "#1e7e34", "FAILED": "#c82333", "CANCELLED": "#6c757d"}


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


class WorkstationQueuePanel(widgets.VBox):
    def __init__(self, *, artifact_dir: Path | str, ui_call: Callable[[Callable[[], None]], None] | None = None,
                 on_change: Callable[[], None] | None = None, poll_seconds: float = 60.0,
                 start_polling: bool = True, transport_factory: Callable[[], Any] | None = None) -> None:
        self.artifact_dir = Path(artifact_dir)
        self._ui_call = ui_call or (lambda callback: callback())
        self._on_change = on_change or (lambda: None)
        self._transport_factory = transport_factory
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._busy = False
        self.poll_seconds = poll_seconds
        try:
            settings = load_settings(self.artifact_dir)
            settings_error = ""
        except (WorkstationQueueError, ValueError) as error:
            settings, settings_error = None, str(error)
        self.folder = widgets.Text(
            description="Drive folder:", value=settings.folder if settings else "",
            placeholder="G:/My Drive/CoChem workstation  or  https://drive.google.com/drive/folders/…",
            style={"description_width": "initial"}, layout=widgets.Layout(width="95%"))
        self.student = widgets.Text(description="Student ID:", value=settings.student_id if settings else "",
                                    placeholder="your-id", style={"description_width": "initial"})
        self.cores = widgets.Text(description="Cores:", value=str(settings.cores) if settings else "auto",
                                  style={"description_width": "initial"}, layout=widgets.Layout(width="160px"))
        self.memory = widgets.BoundedFloatText(description="Memory (GB, 0 = automatic):", min=0, max=2048,
                                               value=settings.memory_gb or 0 if settings else 0,
                                               style={"description_width": "initial"})
        self.max_hours = widgets.BoundedIntText(description="Time limit (h):", min=1, max=168,
                                                value=settings.max_hours if settings else 48,
                                                style={"description_width": "initial"})
        self.trusted_keys = widgets.Text(
            description="Workstation key:", value=", ".join(settings.trusted_keys) if settings else "",
            placeholder="fingerprint from the workstation owner (cochem-runner key)",
            style={"description_width": "initial"}, layout=widgets.Layout(width="95%"))
        self.btn_assign = widgets.Button(description="Assign folder", button_style="primary", icon="folder-open")
        self.btn_assign.on_click(self.assign)
        self.settings_status = widgets.HTML(
            f"<p role='alert'>{_escape(settings_error)}</p>" if settings_error else
            "<p role='status'>Folder assigned. Calculations sent to the lab workstation are deposited there.</p>"
            if settings else "<p role='status'>Choose the Google Drive folder your workstation jobs go to.</p>")
        self.health = widgets.HTML()
        self.history = widgets.Dropdown(options=[("No workstation jobs yet", "")], description="Workstation jobs:",
                                        style={"description_width": "initial"}, layout=widgets.Layout(width="95%"))
        self.history.observe(lambda change: self.refresh(), names="value")
        self.btn_refresh = widgets.Button(description="Refresh status", icon="refresh")
        self.btn_refresh.on_click(self.refresh)
        self.btn_retrieve = widgets.Button(description="Retrieve results", icon="download", disabled=True)
        self.btn_retrieve.on_click(self.retrieve)
        self.btn_cancel = widgets.Button(description="Cancel job", icon="stop", disabled=True)
        self.btn_cancel.on_click(self.cancel)
        self.job_status = widgets.HTML("<p>No workstation job selected.</p>")
        self.result = widgets.HTML()
        self.download = widgets.HTML()
        super().__init__([
            widgets.HTML("<h4>Lab workstation</h4><p>Calculations too large for GitHub Actions can run on the lab "
                         "workstation. BASE deposits each job in the Google Drive folder you assign; the workstation "
                         "runs it when its owner is not using the machine (jobs may pause and resume) and returns "
                         "the results to the same folder. Use a folder synced by Google Drive for desktop on this "
                         "computer, or a drive.google.com folder link from a Codespace (needs the "
                         "<code>COCHEM_WORKSTATION_DRIVE_CREDENTIALS</code> secret from your instructor).</p>"),
            self.folder, widgets.HBox([self.student, self.cores]), widgets.HBox([self.memory, self.max_hours]),
            self.trusted_keys,
            widgets.HTML("<p style='font-size:90%'>The workstation signs every result it returns; BASE imports "
                         "only results signed by a key you trust. Enter the fingerprint the workstation owner gave "
                         "you (your instructor may set it for the class).</p>"),
            self.btn_assign, self.settings_status, self.health,
            self.history, widgets.HBox([self.btn_refresh, self.btn_retrieve, self.btn_cancel]),
            self.job_status, self.result, self.download,
        ], layout=widgets.Layout(border="1px solid #6f42c1", padding="15px", margin="10px 0"))
        self._load_history()
        if start_polling:
            threading.Thread(target=self._poll_loop, daemon=True, name="cochem-workstation-poll").start()
            atexit.register(self._stop.set)

    # -- helpers -----------------------------------------------------------
    def _client(self) -> StudentWorkstationClient:
        transport = self._transport_factory() if self._transport_factory else None
        return StudentWorkstationClient(artifact_dir=self.artifact_dir, transport=transport)

    @property
    def busy(self) -> bool:
        return self._busy

    def _reserve(self) -> bool:
        """Claim the panel for one operation; button handlers and the poller share this."""
        with self._lock:
            if self._busy:
                return False
            self._busy = True
            return True

    def _release(self) -> None:
        with self._lock:
            self._busy = False

    def _background(self, work: Callable[[], None], status: str | None = None) -> bool:
        if not self._reserve():
            self.job_status.value = "<p role='alert'>Wait for the current workstation operation to finish.</p>"
            return False
        if status is not None:
            self.job_status.value = status

        def run() -> None:
            try:
                work()
            finally:
                self._release()
        threading.Thread(target=run, daemon=True).start()
        return True

    def ready_reason(self) -> str:
        try:
            settings = load_settings(self.artifact_dir)
        except (WorkstationQueueError, ValueError) as error:
            return str(error)
        return "" if settings else "Assign your workstation Drive folder in the Lab workstation panel first."

    def _selected(self) -> dict | None:
        value = self.history.value
        return json.loads(value) if value else None

    def _load_history(self, select: str | None = None) -> None:
        try:
            records = self._client().history() if load_settings(self.artifact_dir) or (
                self.artifact_dir / "StudentWorkstation").is_dir() else []
        except (WorkstationQueueError, ValueError, OSError) as error:
            self.job_status.value = f"<p role='alert'>{_escape(error)}</p>"
            return
        options = [(f"{r['job_name']} · submitted {r['submitted_at'][:16].replace('T', ' ')} UTC",
                    json.dumps(r, sort_keys=True)) for r in reversed(records)]
        self.history.options = options or [("No workstation jobs yet", "")]
        if select:
            match = next((value for _, value in options if json.loads(value)["request_id"] == select), None)
            if match:
                self.history.value = match

    # -- actions -----------------------------------------------------------
    def assign(self, b: Any = None) -> None:
        cores_text = self.cores.value.strip().lower()
        try:
            cores: int | str = "auto" if cores_text in {"", "auto"} else int(cores_text)
        except ValueError:
            self.settings_status.value = "<p role='alert'>Cores must be 'auto' or a whole number.</p>"
            return
        folder, student = self.folder.value.strip(), self.student.value.strip()
        trusted = self.trusted_keys.value
        memory = float(self.memory.value) or None
        hours = int(self.max_hours.value)
        self.btn_assign.disabled = True
        self.settings_status.value = "<p role='status'>Preparing the folder (inbox/, jobs/ and its identity file)…</p>"

        def work() -> None:
            try:
                transport = self._transport_factory() if self._transport_factory else None
                result = assign_folder(folder, student, artifact_dir=self.artifact_dir, cores=cores,
                                       memory_gb=memory, max_hours=hours, transport=transport,
                                       trusted_keys=trusted)
                message = (f"<p role='status'>Folder assigned for <b>{_escape(student)}</b> "
                           f"({'Google Drive API' if result['transport'] == 'drive_api' else 'synced folder'}). "
                           "Give your instructor this folder (or share it with the workstation owner) so the "
                           "workstation watches it.</p>")
                self._ui_call(lambda: (setattr(self.settings_status, "value", message),
                                       self._render_health(result["workstations"]), self._load_history(),
                                       self._on_change()))
            except (WorkstationQueueError, ValueError, OSError) as error:
                text = f"<p role='alert'>Folder not assigned: {_escape(error)}</p>"
                self._ui_call(lambda: setattr(self.settings_status, "value", text))
            finally:
                self._ui_call(lambda: setattr(self.btn_assign, "disabled", False))
        if not self._background(work):
            self.btn_assign.disabled = False
            self.settings_status.value = "<p role='alert'>Wait for the current workstation operation to finish.</p>"

    def _render_health(self, workstations: list[dict]) -> None:
        if not workstations:
            self.health.value = ("<p>No workstation has reported for this folder yet. Jobs wait in the folder until "
                                 "the workstation owner adds it.</p>")
            return
        rows = "".join(
            f"<li><b>{_escape(w['node_id'])}</b>: "
            + ("offline" if w["stale"] else f"{_escape(w['mode'])}, {w.get('cores_available') or 0} cores free, "
               f"{w['queued']} job(s) in its queue")
            + (f" — {_escape('; '.join(w.get('reasons') or []))}" if w.get("reasons") and not w["stale"] else "")
            + (f"<br><small>reports signing key {_escape(w['key_fingerprint'])} — compare it with the fingerprint "
               "the workstation owner gave you</small>" if w.get("key_fingerprint") else "")
            + "</li>" for w in workstations)
        self.health.value = f"<p>Workstations serving this folder:</p><ul>{rows}</ul>"

    def submit(self, calculation: dict,
               on_result: Callable[[bool, str], None] | None = None) -> bool:
        """Deposit a calculation in the assigned folder (called by the main Run button).

        Returns whether the deposit started; ``on_result(sent, html)`` reports
        the outcome once the folder write has succeeded or failed.
        """
        def report(sent: bool, text: str) -> None:
            self.job_status.value = text
            if on_result is not None:
                on_result(sent, text)

        def work() -> None:
            try:
                client = self._client()
                submission = client.submit(calculation)
                preflight = client.preflight()
                def done() -> None:
                    self._load_history(select=submission["request_id"])
                    self._render_health(preflight.get("workstations", []))
                    report(True, "<p role='status'>Queued for the lab workstation. You can keep working; "
                                 f"{_escape(preflight.get('reason', ''))}.</p>")
                self._ui_call(done)
            except (WorkstationQueueError, ValueError, OSError) as error:
                text = f"<p role='alert'>Not sent to the workstation: {_escape(error)}</p>"
                self._ui_call(lambda: report(False, text))
        started = self._background(
            work, "<p role='status'>Depositing the calculation in your workstation folder…</p>")
        if not started and on_result is not None:
            on_result(False, self.job_status.value)
        return started

    def refresh(self, b: Any = None) -> None:
        submission = self._selected()
        if submission is None:
            self.btn_retrieve.disabled = self.btn_cancel.disabled = True
            return
        def work() -> None:
            self._refresh_now(submission)
        self._background(work)

    def _refresh_now(self, submission: dict, *, auto_retrieve: bool = False) -> None:
        try:
            status = self._client().status(submission)
        except (WorkstationQueueError, ValueError, OSError) as error:
            text = f"<p role='alert'>Status unavailable: {_escape(error)}</p>"
            self._ui_call(lambda: setattr(self.job_status, "value", text))
            return
        self._ui_call(lambda: self._render_status(status))
        retained = (self.artifact_dir / "StudentWorkstation" / submission["request_id"] / "results"
                    / "workstation-result.json").is_file()
        if status["status"] == "completed" and (retained or auto_retrieve):
            self._retrieve_now(submission)

    def _render_status(self, status: dict) -> None:
        state = status.get("workstation_state") or status["status"].upper()
        colour = STATE_STYLE.get(state, "#6c757d")
        parts = [f"<p><span style='color:{colour};font-weight:bold'>{_escape(state)}</span> "
                 f"{_escape(status.get('detail', ''))}</p>"]
        if status.get("queue_position"):
            parts.append(f"<p>Position in the workstation queue: {int(status['queue_position'])}</p>")
        resources = status.get("resources") or {}
        if resources.get("cores"):
            parts.append(f"<p>Running with {resources['cores']} cores"
                         + (f", {resources['memory_per_core_mb']} MB per core" if resources.get("memory_per_core_mb") else "")
                         + ".</p>")
        if status.get("repairs"):
            parts.append("<p>Adjusted by the workstation: " + _escape("; ".join(status["repairs"])) + "</p>")
        progress = {k: v for k, v in (status.get("progress") or {}).items() if not str(k).startswith("_")}
        if progress:
            parts.append("<p>Progress: " + _escape(", ".join(f"{k} = {v}" for k, v in progress.items())) + "</p>")
        if status.get("output_tail"):
            tail = "\n".join(status["output_tail"][-20:])
            parts.append(f"<details><summary>Latest output</summary><pre style='max-height:240px;overflow:auto'>"
                         f"{_escape(tail)}</pre></details>")
        self.job_status.value = "".join(parts)
        terminal = status["status"] == "completed"
        self.btn_retrieve.disabled = not terminal
        self.btn_cancel.disabled = terminal

    def retrieve(self, b: Any = None) -> None:
        submission = self._selected()
        if submission is None:
            return
        self.result.value = "<p role='status'>Downloading and verifying the workstation results…</p>"
        self._background(lambda: self._retrieve_now(submission))

    def _retrieve_now(self, submission: dict) -> None:
        try:
            receipt = self._client().retrieve_results(submission)
        except (WorkstationQueueError, ValueError, OSError, KeyError) as error:
            text = f"<p role='alert'>Results not imported: {_escape(error)}</p>"
            self._ui_call(lambda: setattr(self.result, "value", text))
            return
        rendered, download = self._render_result(receipt), self._download_html(Path(receipt["path"]))
        self._ui_call(lambda: (setattr(self.result, "value", rendered), setattr(self.download, "value", download)))

    @staticmethod
    def _render_result(receipt: dict) -> str:
        report = receipt["report"]
        root = Path(receipt["path"])
        if report.get("status") != "completed":
            return ("<p role='alert'><b>No accepted scientific result.</b> "
                    f"{_escape(report.get('message') or 'The workstation run did not complete.')}</p>"
                    f"<p>Diagnostics retained in <code>{_escape(root)}</code>.</p>")
        execution = report.get("execution") or {}
        lines = [f"<p><b>Verified workstation result</b> ({_escape(execution.get('engine', ''))} "
                 f"{_escape(execution.get('method', ''))}/{_escape(execution.get('basis_set', ''))}, "
                 f"{_escape(execution.get('status', ''))})</p>"]
        result_path = root / "base_output" / "result.json"
        if result_path.is_file():
            try:
                payload = json.loads(result_path.read_text(encoding="utf-8"))
            except ValueError:
                payload = {}
            if isinstance(payload.get("energy_hartree"), (int, float)):
                lines.append(f"<p>Energy: {float(payload['energy_hartree']):.12f} Hartree</p>")
            for key in ("scf_converged", "converged", "optimization_converged"):
                if key in payload:
                    lines.append(f"<p>{_escape(key.replace('_', ' '))}: {payload[key] is True}</p>")
        if report.get("repairs"):
            lines.append("<p>Workstation adjustments: " + _escape("; ".join(report["repairs"])) + "</p>")
        lines.append(f"<p>Results: <code>{_escape(root)}</code></p>")
        return "".join(lines)

    @staticmethod
    def _download_html(root: Path) -> str:
        files = [p for p in sorted(root.rglob("*")) if p.is_file() and not p.is_symlink()]
        if not files or sum(p.stat().st_size for p in files) > 32 * 1024 * 1024:
            return ""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in files:
                archive.write(path, path.relative_to(root).as_posix())
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return (f"<a download='{_escape(root.parent.name)}-workstation-results.zip' "
                f"href='data:application/zip;base64,{encoded}'>Download results</a>")

    def cancel(self, b: Any = None) -> None:
        submission = self._selected()
        if submission is None:
            return
        def work() -> None:
            try:
                self._client().cancel(submission)
                message = "<p role='status'>Cancellation requested; the workstation stops the job shortly.</p>"
            except (WorkstationQueueError, ValueError, OSError) as error:
                message = f"<p role='alert'>Not cancelled: {_escape(error)}</p>"
            self._ui_call(lambda: setattr(self.job_status, "value", message))
        self._background(work)

    def _poll_loop(self) -> None:
        while not self._stop.wait(self.poll_seconds):
            submission = self._selected()
            if submission is None or not self._reserve():
                continue
            try:
                self._refresh_now(submission, auto_retrieve=True)
            except Exception:  # never let a transient Drive problem kill the poller
                continue
            finally:
                self._release()

    def close(self) -> None:
        self._stop.set()
        super().close()
