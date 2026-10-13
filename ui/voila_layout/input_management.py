"""Recoverable removal controls for the student's active input lists."""
from __future__ import annotations

import html

import ipywidgets as widgets

from ui.voila_layout.disclosure import Disclosure


class InputManagementMixin:
    """Keep originals and completed work while removing mistaken active choices."""

    def _build_input_management(self) -> None:
        self._removed_input_library = {}
        self._removed_student_uploads = {}
        self._last_input_removal = None
        self.btn_remove_input = widgets.Button(description="Remove from list", disabled=True, tooltip="Keep the original file and past results. You can restore it later.")
        self.btn_remove_geometry = widgets.Button(description="Remove from list", disabled=True, tooltip="Keep this geometry and past results. You can restore it later.")
        self.btn_undo_input_remove = widgets.Button(description="Undo remove", disabled=True)
        self.btn_undo_geometry_remove = widgets.Button(description="Undo remove", disabled=True)
        self.btn_clear_r2_attachment = widgets.Button(description="Clear R2 reference", disabled=True)
        self.btn_clear_read_attachment = widgets.Button(description="Clear starting Hessian", disabled=True)
        self.btn_clear_r2_attachment.on_click(lambda _: self._change_attachment_visibility("r2_reference", hidden=True))
        self.btn_clear_read_attachment.on_click(lambda _: self._change_attachment_visibility("read_hessian", hidden=True))
        self.btn_remove_input.on_click(lambda _: self._remove_input_choice("inputs", self.input_library_choice.value))
        self.btn_remove_geometry.on_click(lambda _: self._remove_input_choice("geometries", self.student_geometry_choice.value))
        self.input_library_choice.observe(lambda change: setattr(self.btn_remove_input, "disabled", not bool(change["new"])), names="value")
        self.student_geometry_choice.observe(lambda change: setattr(self.btn_remove_geometry, "disabled", not bool(change["new"])), names="value")
        self.btn_undo_input_remove.on_click(self._undo_input_removal)
        self.btn_undo_geometry_remove.on_click(self._undo_input_removal)
        self.input_management_status = widgets.HTML()
        self.removed_input_choice = widgets.Dropdown(options=[("No removed inputs", "")], description="Removed input:",
            style={"description_width": "initial"}, layout=widgets.Layout(width="95%"))
        self.btn_restore_input = widgets.Button(description="Restore selected input", disabled=True)
        self.btn_restore_input.on_click(self._restore_removed_input)
        self.removed_input_choice.observe(lambda change: setattr(self.btn_restore_input, "disabled", not bool(change["new"])), names="value")
        self.removed_inputs_panel = Disclosure("removed inputs",
            widgets.HTML("<p>Original files and completed calculations are kept. Restore an input to use it again.</p>"),
            self.removed_input_choice, self.btn_restore_input)
        self.geometry_management_controls = widgets.HBox([self.btn_remove_geometry, self.btn_undo_geometry_remove])
        self.input_management_controls = widgets.VBox([
            widgets.HBox([self.btn_remove_input, self.btn_undo_input_remove]),
            self.input_management_status, self.removed_inputs_panel])

    def _input_management_busy(self) -> bool:
        flags = ("_ingestion_busy", "_pipeline_running", "_topos_running", "_student_research_running",
                 "_actions_running", "_actions_retrieving", "_hpc_running", "_hpc_retrieving", "_installation_running")
        workers = ("_scientific_input_worker", "_scientific_restore_worker", "_hessian_load_worker", "_isotope_worker", "_physical_data_worker")
        return any(getattr(self, name, False) for name in flags) or any(
            worker is not None and worker.is_alive() for worker in (getattr(self, name, None) for name in workers))

    def _input_visibility(self) -> dict:
        from cochem_base.config_loader import get_artifact_dir
        from cochem_base.interfaces.student_input_visibility import read_input_visibility
        return read_input_visibility(get_artifact_dir())

    def _filter_input_snapshot(self, snapshot: dict) -> dict:
        """A refresh already in flight cannot revive a removed choice."""
        hidden = set(self._input_visibility()["inputs"])
        records = {item["input_id"]: item for item in [*snapshot["inputs"], *snapshot.get("removed_inputs", [])]}
        return {**snapshot, "inputs": [item for key, item in records.items() if key not in hidden],
                "removed_inputs": [item for key, item in records.items() if key in hidden]}

    def _active_geometry_records(self, records: dict) -> dict:
        from cochem_base.interfaces.student_input_visibility import partition_geometry_choices
        active, removed = partition_geometry_choices(records, self._input_visibility())
        self._removed_student_uploads = removed
        return active

    def _clear_geometry_selection(self) -> None:
        self.matrix_geometry.value = ""
        self.student_input_label.value = ""
        self.student_fragment_atoms.value = ""
        removed_paths = {item["path"] for item in getattr(self, "_removed_student_uploads", {}).values()}
        module_selection = getattr(self, "_input_selectors", {}).get("module")
        if self.module_artifact.value in removed_paths or module_selection is None or not module_selection.value:
            self.module_artifact.value = ""
        self._research_fragment_state_inputs = []
        if hasattr(self, "research_fragment_states"):
            self.research_fragment_states.children = ()
        self.student_upload_status.value = "<p role='status'>Choose a starting geometry or upload a new file.</p>"

    def _clear_input_binding(self, kind: str) -> None:
        fields = {"install": "install_data_path", "hessian": "isotope_hessian_path", "telemetry": "inspector_file_input",
                  "physical_data": "inspector_file_input", "periodic": "periodic_input_path", "module": "module_artifact"}
        getattr(self, fields[kind]).value = ""
        if kind == "install":
            self._install_input_artifact = None
        elif kind == "hessian":
            self._isotope_hessian_data = None
            self.isotope_hessian_status.value = "<p>Choose a Hessian file to inspect.</p>"
        elif kind == "physical_data":
            self._managed_physical_data = None
        elif kind == "periodic":
            self._periodic_structure = None
            self._paw_pseudopotential_choices = {}
            self.paw_species_box.children = ()
            self.periodic_structure_status.value = "<p>Choose a periodic structure to continue.</p>"

    def _sync_input_management(self, snapshot: dict | None = None) -> None:
        if snapshot is not None:
            self._removed_input_library = {item["input_id"]: item for item in snapshot.get("removed_inputs", [])}
        all_geometries = {**self._removed_student_uploads, **self._student_uploads}
        active = self._active_geometry_records(all_geometries)
        selected = self.student_geometry_choice.value
        self._student_uploads = active
        selection_running = self._input_selection_running
        self._input_selection_running = True
        try:
            self.student_geometry_choice.options = [("Choose a starting geometry", "")] + [(item["label"], key) for key, item in active.items()]
            self.student_geometry_choice.value = selected if selected in active else ""
        finally:
            self._input_selection_running = selection_running
        if selected and selected not in active:
            self._clear_geometry_selection()
        self._refresh_student_monomer_choices()
        state = self._input_visibility()
        choices = [(item["filename"], "inputs:" + key) for key, item in self._removed_input_library.items()]
        # A geometry hidden by a removed parent returns when that parent is restored.
        choices += [(item["label"] + " (starting geometry)", "geometries:" + key)
                    for key, item in self._removed_student_uploads.items() if key in state["geometries"]]
        attachment_labels = {"r2_reference": "R2 reference files", "read_hessian": "Starting Hessian attachment"}
        choices += [(attachment_labels[kind], "attachments:" + kind) for kind in state["attachments"]]
        self.removed_input_choice.options = [("Choose an input to restore", "")] + choices if choices else [("No removed inputs", "")]
        self.btn_remove_input.disabled = not bool(self.input_library_choice.value)
        self.btn_remove_geometry.disabled = not bool(self.student_geometry_choice.value)
        self.btn_undo_input_remove.disabled = self.btn_undo_geometry_remove.disabled = self._last_input_removal is None
        self.btn_clear_r2_attachment.disabled = "r2_reference" not in self._scientific_inputs
        self.btn_clear_read_attachment.disabled = "read_hessian" not in self._scientific_inputs

    def _remove_input_choice(self, category: str, input_id: str) -> None:
        if not input_id:
            self._input_management_notice("Select an input before removing it.")
            return
        self._change_input_visibility(category, input_id, hidden=True)

    def _input_management_notice(self, message: str, *, error: bool = False) -> None:
        value = "<p role='" + ("alert" if error else "status") + "'>" + html.escape(message) + "</p>"
        self.input_management_status.value = value
        self.student_upload_status.value = value

    def _change_input_visibility(self, category: str, input_id: str, *, hidden: bool) -> None:
        from cochem_base.config_loader import get_artifact_dir
        from cochem_base.interfaces.student_input_visibility import set_input_visibility
        if category == "attachments":
            self._change_attachment_visibility(input_id, hidden=hidden)
            return
        if self._input_management_busy():
            self._input_management_notice("Wait for the current upload or calculation to finish before changing the input list.", error=True)
            return
        try:
            set_input_visibility(get_artifact_dir(), category, input_id, hidden=hidden)
            self._input_library_refresh_serial += 1
            if not hidden:
                # Reread original bytes before allowing a restored item to run.
                snapshot = self._read_input_library()
                selection_running = self._input_selection_running
                self._input_selection_running = True
                try:
                    self._restore_student_inputs()
                finally:
                    self._input_selection_running = selection_running
            else:
                snapshot = {"inputs": list(self._input_library.values()), "removed_inputs": list(self._removed_input_library.values()),
                            "rejections": getattr(self, "_input_library_rejections", [])}
            snapshot = self._filter_input_snapshot(snapshot)
            if hidden:
                removed_ids = {item["input_id"] for item in snapshot["removed_inputs"]}
                for kind, selector in self._input_selectors.items():
                    if selector.value in removed_ids:
                        self._clear_input_binding(kind)
                previous_sieve = getattr(self, "_last_input_pool_sieve", None) or {}
                if (any(value in removed_ids for value in self.input_pool_choices.value)
                        or any(item.get("input_id") in removed_ids for item in previous_sieve.get("source_inputs", []))):
                    self._last_input_pool_sieve = None
                    self.input_unique_conformer.options = []
                    self.btn_use_unique_conformer.disabled = True
                self._last_input_removal = (category, input_id)
            else:
                self._last_input_removal = None
            self._apply_input_library(snapshot)
            message = "Removed from the list. Original files and completed results are kept." if hidden else "Restored. Select the input when you are ready to use it."
            self._input_management_notice(message)
        except (ValueError, RuntimeError, OSError, KeyError) as error:
            self._input_management_notice("The input list could not be changed: " + str(error), error=True)

    def _change_attachment_visibility(self, kind: str, *, hidden: bool) -> None:
        from cochem_base.config_loader import get_artifact_dir
        from cochem_base.interfaces.student_input_visibility import set_attachment_visibility
        if self._input_management_busy():
            self.scientific_input_status.value = "<p role='alert'>Wait for the current upload or calculation to finish before changing an attachment.</p>"
            return
        try:
            set_attachment_visibility(get_artifact_dir(), kind, hidden=hidden)
            if hidden:
                self._scientific_inputs.pop(kind, None)
                if kind == "r2_reference":
                    self.r2_reference_manifest.value = ""
                    self.scientific_r2_upload.value = ()
                else:
                    self.scientific_read_upload.value = ()
                self._last_input_removal = ("attachments", kind)
                self.scientific_input_status.value = "<p role='status'>Attachment cleared. Its original files and past results are kept. Upload a replacement or restore it from Show removed inputs.</p>"
            else:
                self._last_input_removal = None
                self._restore_student_scientific_inputs()
            self._sync_input_management()
            self._check_dispersion_gate()
        except (ValueError, RuntimeError, OSError) as error:
            self.scientific_input_status.value = "<p role='alert'>The attachment could not be changed: " + html.escape(str(error)) + "</p>"

    def _undo_input_removal(self, button=None) -> None:
        if self._last_input_removal is not None:
            self._change_input_visibility(*self._last_input_removal, hidden=False)

    def _restore_removed_input(self, button=None) -> None:
        selected = self.removed_input_choice.value
        if selected:
            category, input_id = selected.split(":", 1)
            self._change_input_visibility(category, input_id, hidden=False)
