#!/usr/bin/env python3
"""
CoChem-SCRIBE Stage 6.0 Interactive Voila GUI Dashboard Architecture.

Governed by Phase 1, Task 3: Voila GUI Component Architecture (ui/voila_layout/scribe_gui_dashboard.py),
the CoChem v4.1 Method Matrix, and the Zero-Tolerance Anti-Mocking Mandate.

Provides a 3-Tab interactive interface:
1. Hardware HUD & RESOURCE_GUARD Hardware Metrology
2. Document & Provenance Configuration
3. Execution Telemetry & Compilation Status
"""

from __future__ import annotations

import json
import platform
import shutil
import stat
import sys
import threading
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class DocumentSettings(BaseModel):
    generate_latex_manuscript: bool = True
    generate_user_guide: bool = True
    target_journal: str = "ACS Standard"
    crossref_doi_autofill: bool = False
    zstd_compression: bool = True
    methodology_level: str = "Standard"

class SystemConfig(BaseModel):
    document_settings: DocumentSettings = Field(default_factory=DocumentSettings)
    methodology_level: str = "Standard"
    target_journal: str = "ACS Standard"

class AuditLogEntry(BaseModel):
    timestamp: str = "AUDIT"
    event: str = "INFO"
    details: str = ""


import ipywidgets as widgets
import psutil
from IPython.display import display

from core.cochem_scribe_master import (
    RESOURCE_GUARD_RAM_THRESHOLD_GB,
    CompilationResult,
    PreferredEngine,
    ScribeOrchestrationConfig,
    ScribeOrchestrator,
    get_default_artifacts_dir,
    get_default_config_path,
    get_default_h5_path,
    get_default_output_dir,
    record_fatal_crash,
)


class ScribeDashboard:
    """
    Stage 6.0 Voila GUI Dashboard providing zero-code execution, dynamic resource
    gating, provenance management, and live telemetry streaming.
    """

    def __init__(
        self,
        artifacts_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        h5_path: Optional[Path] = None,
        config_path: Optional[Path] = None,
    ) -> None:
        self.artifacts_dir: Path = (
            Path(artifacts_dir).resolve() if artifacts_dir else get_default_artifacts_dir()
        )
        self.output_dir: Path = (
            Path(output_dir).resolve() if output_dir else get_default_output_dir()
        )
        self.h5_path: Path = (
            Path(h5_path).resolve() if h5_path else get_default_h5_path()
        )
        self.config_path: Path = (
            Path(config_path).resolve() if config_path else get_default_config_path()
        )
        self.audit_log_path: Path = self.artifacts_dir / "cochem_audit_log.json"

        self.resource_guard_locked: bool = False
        self._is_running: bool = False
        self.input_widgets: List[widgets.Widget] = []

        # Construct UI Tabs
        self._build_tab1_hardware_hud()
        self._build_tab2_document_config()
        self._build_tab3_execution_telemetry()
        self._assemble_tabs()

        # Initial Resource Evaluation
        self.poll_resources()
        self.check_resource_guard()

    # =========================================================================
    # TAB 1: HARDWARE HUD & RESOURCE GUARD
    # =========================================================================

    def _build_tab1_hardware_hud(self) -> None:
        """Constructs Tab 1: Hardware Resource HUD and Engine Selector."""
        self.resource_matrix_display = widgets.HTML(
            value="<div style='padding:8px;'>Initializing Hardware Resource Matrix...</div>",
            layout=widgets.Layout(margin="0 0 12px 0"),
        )

        self.engine_dropdown = widgets.Dropdown(
            options=["Local Llama.cpp", "Gemini API", "Dry-Run Template"],
            value="Gemini API",
            description="Engine:",
            style={"description_width": "120px"},
            layout=widgets.Layout(width="380px"),
        )
        self.engine_dropdown.observe(self._on_engine_change, names="value")

        self.resource_guard_warning = widgets.HTML(value="")

        self.api_key_input = widgets.Password(
            description="API Credential:",
            style={"description_width": "120px"},
            layout=widgets.Layout(width="380px"),
        )

        self.save_key_button = widgets.Button(
            description="Save Credential",
            button_style="info",
            icon="key",
            layout=widgets.Layout(width="180px", margin="4px 0 0 124px"),
        )
        self.save_key_button.on_click(self._on_save_key_click)

        self.api_key_status = widgets.HTML(
            value="",
            layout=widgets.Layout(margin="4px 0 0 124px"),
        )

    def _on_engine_change(self, change: Dict[str, Any]) -> None:
        """Enforces RESOURCE_GUARD lock if user attempts to select Local Llama on constrained hardware."""
        new_val = change.get("new")
        if new_val == "Local Llama.cpp" and self.resource_guard_locked:
            self.engine_dropdown.value = "Gemini API"
            self.resource_guard_warning.value = (
                "<div style='color:#b91c1c; background-color:#fee2e2; "
                "border:1px solid #f87171; border-radius:4px; padding:6px 10px; margin-top:6px;'>"
                "<b>RESOURCE_GUARD Notice:</b> Insufficient RAM to load 4GB+ .gguf local weights. "
                "Route to API or use Dry-Run.</div>"
            )

    def _on_save_key_click(self, button: widgets.Button) -> None:
        """Event handler for credential persistence button."""
        self.save_api_credential()

    def check_resource_guard(self, ram_total_gb: Optional[float] = None) -> bool:
        """
        Evaluates system RAM against threshold. Disables local inference if hardware
        is insufficient to load heavy 4GB+ quantized weight models.
        """
        if ram_total_gb is None:
            ram_total_gb = psutil.virtual_memory().total / (1024**3)

        if ram_total_gb < RESOURCE_GUARD_RAM_THRESHOLD_GB:
            self.resource_guard_locked = True
            notice_text = "Insufficient RAM to load 4GB+ .gguf local weights. Route to API or use Dry-Run."
            self.engine_dropdown.tooltip = notice_text
            self.resource_guard_warning.value = (
                f"<div style='color:#b91c1c; background-color:#fee2e2; "
                f"border:1px solid #f87171; border-radius:4px; padding:6px 10px; margin-top:6px;'>"
                f"<b>RESOURCE_GUARD Notice:</b> {notice_text}</div>"
            )
            if self.engine_dropdown.value == "Local Llama.cpp":
                self.engine_dropdown.value = "Gemini API"
            return False

        self.resource_guard_locked = False
        self.engine_dropdown.tooltip = "Hardware verified. Local and cloud engines accessible."
        self.resource_guard_warning.value = ""
        return True

    def poll_resources(self) -> str:
        """Dynamically inspects RAM, VRAM, and Disk space via Path.home()."""
        vm = psutil.virtual_memory()
        total_ram_gb = vm.total / (1024**3)
        avail_ram_gb = vm.available / (1024**3)
        ram_percent = vm.percent

        vram_info = "VRAM: 0.0 GB (CPU / Headless Fallback)"
        try:
            import torch

            if torch.cuda.is_available():
                props = torch.cuda.get_device_properties(0)
                total_vram_gb = props.total_memory / (1024**3)
                allocated_gb = torch.cuda.memory_allocated(0) / (1024**3)
                vram_info = f"VRAM: {total_vram_gb:.1f} GB ({props.name}, {allocated_gb:.1f} GB Active)"
        except Exception:
            vram_info = "VRAM: N/A (CPU / Headless Fallback)"

        home_dir = Path.home()
        disk_total_gb = 0.0
        disk_free_gb = 0.0
        try:
            du = shutil.disk_usage(home_dir)
            disk_total_gb = du.total / (1024**3)
            disk_free_gb = du.free / (1024**3)
        except Exception:
            pass

        guard_status_label = (
            "<span style='color:#b91c1c; font-weight:bold;'>LOCKED (&lt; 8 GB)</span>"
            if total_ram_gb < RESOURCE_GUARD_RAM_THRESHOLD_GB
            else "<span style='color:#15803d; font-weight:bold;'>READY (&ge; 8 GB)</span>"
        )

        matrix_html = (
            "<div style='border:1px solid #e5e7eb; border-radius:6px; padding:12px; background-color:#f9fafb; font-family:sans-serif;'>"
            "<div style='font-size:14px; font-weight:bold; margin-bottom:8px; color:#111827;'>System Resource Telemetry Matrix</div>"
            "<table style='width:100%; border-collapse:collapse; font-size:12px; color:#374151;'>"
            f"<tr><td style='padding:4px 0;'><b>Host Architecture:</b></td><td>{platform.system()} {platform.machine()} ({platform.python_implementation()} {platform.python_version()})</td></tr>"
            f"<tr><td style='padding:4px 0;'><b>System RAM:</b></td><td>{total_ram_gb:.2f} GB Total | {avail_ram_gb:.2f} GB Available ({ram_percent}% utilized)</td></tr>"
            f"<tr><td style='padding:4px 0;'><b>Graphics Acceleration:</b></td><td>{vram_info}</td></tr>"
            f"<tr><td style='padding:4px 0;'><b>Scratch Disk (Home):</b></td><td>{disk_free_gb:.2f} GB Free / {disk_total_gb:.2f} GB Total ({home_dir})</td></tr>"
            f"<tr><td style='padding:4px 0;'><b>RESOURCE_GUARD:</b></td><td>{guard_status_label}</td></tr>"
            "</table>"
            "</div>"
        )
        self.resource_matrix_display.value = matrix_html
        return matrix_html

    def save_api_credential(self, key_value: Optional[str] = None) -> Path:
        """
        Serializes credential directly to Report_Archive/.env and enforces POSIX 0o600 permissions.
        Clears the widget value immediately to prevent credentials in persistent browser states.
        """
        if key_value is None:
            key_value = self.api_key_input.value

        target_dir = self.output_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        env_file = target_dir / ".env"

        env_file.write_text(f"GEMINI_API_KEY={key_value}\n", encoding="utf-8")

        perm_label = "POSIX 0o600 permissions active"
        if platform.system() != "Windows":
            try:
                env_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
            except Exception:
                perm_label = "standard permissions"
        else:
            perm_label = "Windows Access Control active"

        self.api_key_input.value = ""
        self.api_key_status.value = (
            f"<span style='color:#15803d; font-size:12px; font-weight:bold;'>"
            f"Credential serialized to {env_file.name} ({perm_label}).</span>"
        )
        return env_file

    # =========================================================================
    # TAB 2: DOCUMENT & PROVENANCE CONFIGURATION
    # =========================================================================

    def _build_tab2_document_config(self) -> None:
        """Constructs Tab 2: Document flags, journal templates, and Air-Gap options."""
        self.latex_manuscript_checkbox = widgets.Checkbox(
            value=True,
            description="Generate LaTeX Manuscript",
            indent=False,
            layout=widgets.Layout(margin="4px 0"),
        )
        self.latex_manuscript_checkbox.observe(self._on_doc_config_change, names="value")

        self.user_guide_checkbox = widgets.Checkbox(
            value=True,
            description="Generate Markdown User Guide",
            indent=False,
            layout=widgets.Layout(margin="4px 0"),
        )
        self.user_guide_checkbox.observe(self._on_doc_config_change, names="value")

        self.journal_dropdown = widgets.Dropdown(
            options=["ACS Standard", "AASTeX (Astrophysics)", "Generic APS"],
            value="ACS Standard",
            description="Target Journal:",
            style={"description_width": "140px"},
            layout=widgets.Layout(width="380px", margin="8px 0"),
        )
        self.journal_dropdown.observe(self._on_doc_config_change, names="value")

        self.crossref_doi_checkbox = widgets.Checkbox(
            value=False,
            description="Enable CrossRef DOI Autofill",
            indent=False,
            layout=widgets.Layout(margin="4px 0"),
        )
        self.crossref_doi_checkbox.observe(self._on_doc_config_change, names="value")

        self.zstd_compression_checkbox = widgets.Checkbox(
            value=True,
            description="Zstandard 3D Grid Compression",
            indent=False,
            layout=widgets.Layout(margin="4px 0"),
        )
        self.zstd_compression_checkbox.observe(self._on_doc_config_change, names="value")

        self.methodology_level_dropdown = widgets.Dropdown(
            options=["Standard", "Comprehensive", "Exhaustive", "Minimal"],
            value="Standard",
            description="Methodology Level:",
            style={"description_width": "140px"},
            layout=widgets.Layout(width="380px", margin="8px 0"),
        )
        self.methodology_level_dropdown.observe(self._on_doc_config_change, names="value")

    def _on_doc_config_change(self, change: Dict[str, Any]) -> None:
        """Synchronizes UI settings into the system config JSON on state change."""
        self.save_document_configuration()

    def save_document_configuration(self) -> Path:
        """
        Persists Tab 2 configuration settings to cochem_system_config.json,
        ensuring zero-loss propagation of user options to backend pipelines.
        """
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        config_data = {}
        if self.config_path.exists():
            try:
                config_data = json.loads(self.config_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        doc_settings = DocumentSettings(
            generate_latex_manuscript=self.latex_manuscript_checkbox.value,
            generate_user_guide=self.user_guide_checkbox.value,
            target_journal=self.journal_dropdown.value,
            crossref_doi_autofill=self.crossref_doi_checkbox.value,
            zstd_compression=self.zstd_compression_checkbox.value,
            methodology_level=self.methodology_level_dropdown.value,
        )

        sys_config = SystemConfig(
            document_settings=doc_settings,
            methodology_level=self.methodology_level_dropdown.value,
            target_journal=self.journal_dropdown.value,
        )
        
        config_data.update(sys_config.model_dump())
        self.config_path.write_text(json.dumps(config_data, indent=2), encoding="utf-8")
        return self.config_path

    # =========================================================================
    # TAB 3: EXECUTION TELEMETRY & COMPILATION STATUS
    # =========================================================================

    def _build_tab3_execution_telemetry(self) -> None:
        """Constructs Tab 3: Orchestration launcher, progress metrology, and log console."""
        self.generate_button = widgets.Button(
            description="Generate CoChem Report",
            button_style="success",
            icon="play",
            layout=widgets.Layout(width="260px", height="40px", margin="8px 0"),
        )
        self.generate_button.on_click(self._on_generate_button_click)

        self.progress_bar = widgets.IntProgress(
            value=0,
            min=0,
            max=5,
            description="Progress:",
            bar_style="info",
            orientation="horizontal",
            style={"description_width": "80px"},
            layout=widgets.Layout(width="520px", margin="4px 0"),
        )

        self.progress_label = widgets.HTML(
            value="<div style='font-size:12px; color:#4b5563;'><b>Status:</b> Ready for execution.</div>",
            layout=widgets.Layout(margin="2px 0 10px 0"),
        )

        self.telemetry_output = widgets.Output(
            layout=widgets.Layout(
                height="240px",
                border="1px solid #d1d5db",
                overflow="auto",
                padding="8px",
            )
        )

        self.download_link_html = widgets.HTML(
            value="",
            layout=widgets.Layout(margin="10px 0"),
        )

    def _assemble_tabs(self) -> None:
        """Assembles all tabs into root Tab container and registers input controls for lockdown."""
        tab1_box = widgets.VBox(
            [
                self.resource_matrix_display,
                self.engine_dropdown,
                self.resource_guard_warning,
                self.api_key_input,
                self.save_key_button,
                self.api_key_status,
            ],
            layout=widgets.Layout(padding="12px"),
        )

        tab2_box = widgets.VBox(
            [
                widgets.HTML("<div style='font-weight:bold; margin-bottom:6px;'>Document Synthesis Options</div>"),
                self.latex_manuscript_checkbox,
                self.user_guide_checkbox,
                self.journal_dropdown,
                widgets.HTML("<div style='font-weight:bold; margin:10px 0 6px 0;'>Provenance & Compression Settings</div>"),
                self.crossref_doi_checkbox,
                self.zstd_compression_checkbox,
                self.methodology_level_dropdown,
            ],
            layout=widgets.Layout(padding="12px"),
        )

        tab3_box = widgets.VBox(
            [
                self.generate_button,
                self.progress_bar,
                self.progress_label,
                self.download_link_html,
                widgets.HTML("<div style='font-weight:bold; margin:8px 0 4px 0;'>Execution Telemetry Stream</div>"),
                self.telemetry_output,
            ],
            layout=widgets.Layout(padding="12px"),
        )

        self.tab = widgets.Tab(children=[tab1_box, tab2_box, tab3_box])
        self.tab.set_title(0, "Hardware HUD (RESOURCE_GUARD)")
        self.tab.set_title(1, "Document & Provenance Configuration")
        self.tab.set_title(2, "Execution Telemetry & Compilation Status")

        self.input_widgets = [
            self.engine_dropdown,
            self.api_key_input,
            self.save_key_button,
            self.latex_manuscript_checkbox,
            self.user_guide_checkbox,
            self.journal_dropdown,
            self.crossref_doi_checkbox,
            self.zstd_compression_checkbox,
            self.methodology_level_dropdown,
            self.generate_button,
        ]

    # =========================================================================
    # STATE LOCKDOWN & PROGRESS MANAGEMENT
    # =========================================================================

    def set_lockdown(self, disabled: bool) -> None:
        """Synchronously locks/unlocks all user input widgets during execution."""
        for widget in self.input_widgets:
            widget.disabled = disabled

    def update_progress(self, step_index: int, message: str) -> None:
        """Updates progress bar value and status text."""
        self.progress_bar.value = step_index
        self.progress_label.value = (
            f"<div style='font-size:12px; color:#1f2937;'>"
            f"<b>[Step {step_index}/5]</b> {message}...</div>"
        )

    def tail_audit_log(self, max_entries: int = 25) -> None:
        """Reads recent audit log entries into the telemetry output console."""
        if not self.audit_log_path.exists():
            return

        try:
            content = self.audit_log_path.read_text(encoding="utf-8")
            data = json.loads(content)
            entries = data if isinstance(data, list) else [data]
            with self.telemetry_output:
                for entry in entries[-max_entries:]:
                    try:
                        parsed = AuditLogEntry(**entry)
                    except Exception:
                        parsed = AuditLogEntry(
                            timestamp=entry.get("timestamp", "AUDIT"),
                            event=entry.get("event", entry.get("event_type", "INFO")),
                            details=entry.get("details", entry.get("exception_message", ""))
                        )
                    print(f"[{parsed.timestamp}] {parsed.event}: {parsed.details}")
        except Exception:
            pass

    # =========================================================================
    # PIPELINE EXECUTION
    # =========================================================================

    def _on_generate_button_click(self, button: widgets.Button) -> None:
        """Launches pipeline execution with atomic re-entrancy protection."""
        if self._is_running:
            return
        self._is_running = True
        self.set_lockdown(True)
        worker = threading.Thread(target=self._run_pipeline_worker, daemon=True)
        worker.start()

    def _run_pipeline_worker(self) -> None:
        """Thread worker wrapper for asynchronous execution."""
        try:
            self.execute_pipeline_sync()
        except Exception as exc:
            with self.telemetry_output:
                print(f"[SCRIBE-ERROR] Worker exception: {exc}")
        finally:
            self._is_running = False

    def _on_orchestrator_step(self, step_index: int, description: str) -> None:
        """Reactive callback triggered by ScribeOrchestrator as each physical step executes."""
        self.update_progress(step_index, description)
        with self.telemetry_output:
            print(f"[Step {step_index}/5] {description}...")

    def execute_pipeline_sync(self) -> CompilationResult:
        """
        Executes the physical 5-step CoChem-SCRIBE pipeline synchronously with UI state locking,
        real-time reactive step progress tracking, configuration synchronization, and download link generation.
        """
        self.set_lockdown(True)
        self.progress_bar.value = 0
        self.progress_bar.bar_style = "info"
        self.download_link_html.value = ""

        with self.telemetry_output:
            self.telemetry_output.clear_output()
            print("================================================================================")
            print("Initiating CoChem-SCRIBE Stage 6.0 Master Orchestration Pipeline...")
            print("================================================================================")

        # 1. Flush any entered API key if user didn't explicitly click save
        if self.api_key_input.value.strip():
            self.save_api_credential()

        # 2. Persist Tab 2 document configuration options
        self.save_document_configuration()

        # 3. Hardware evaluation and Engine resolution
        self.check_resource_guard()
        engine_selection = self.engine_dropdown.value
        if engine_selection == "Local Llama.cpp" and self.resource_guard_locked:
            engine_selection = "Gemini API"
            with self.telemetry_output:
                print("[SCRIBE-WARNING] Local Llama.cpp locked by RESOURCE_GUARD. Routing to Gemini API.")

        engine_map = {
            "Local Llama.cpp": PreferredEngine.LOCAL_LLAMA.value,
            "Gemini API": PreferredEngine.GEMINI.value,
            "Dry-Run Template": PreferredEngine.DRY_RUN.value,
        }
        resolved_engine = engine_map.get(engine_selection, PreferredEngine.GEMINI.value)
        is_dry_run = resolved_engine == PreferredEngine.DRY_RUN.value

        config = ScribeOrchestrationConfig(
            config_path=self.config_path,
            output_dir=self.output_dir,
            h5_path=self.h5_path,
            dry_run=is_dry_run,
            model_engine=resolved_engine,
        )

        try:
            orchestrator = ScribeOrchestrator(
                config=config,
                progress_callback=self._on_orchestrator_step,
            )
            result = orchestrator.run_pipeline()

            if result.latex_compiled_successfully:
                self.progress_bar.bar_style = "success"
                self.progress_label.value = (
                    "<div style='color:#15803d; font-size:12px; font-weight:bold;'>"
                    "Synthesis Complete: LaTeX PDF and documentation archived successfully.</div>"
                )
            else:
                self.progress_bar.bar_style = "warning"
                self.progress_label.value = (
                    "<div style='color:#d97706; font-size:12px; font-weight:bold;'>"
                    "Notice: pdflatex compilation unavailable. Raw LaTeX and Markdown bundle packaged.</div>"
                )

            zip_name = Path(result.final_zip_path).name
            zip_uri = Path(result.final_zip_path).resolve().as_uri()
            self.download_link_html.value = (
                f"<div style='background-color:#f0fdf4; border:1px solid #86efac; border-radius:6px; padding:8px 12px; margin-top:8px;'>"
                f"<b>Archive Package:</b> <a href='{zip_uri}' target='_blank' "
                f"style='font-weight:bold; color:#0284c7; text-decoration:underline;'>Download {zip_name}</a> "
                f"(SHA-256: <code>{result.zip_sha256[:16]}...</code>)"
                f"</div>"
            )

            with self.telemetry_output:
                print(f"[SCRIBE-SUCCESS] Pipeline complete. Final bundle: {result.final_zip_path}")
                print(f"[SCRIBE-SUCCESS] Bundle SHA-256: {result.zip_sha256}")

            return result

        except Exception as exc:
            self.progress_bar.bar_style = "danger"
            self.progress_label.value = (
                f"<div style='color:#b91c1c; font-size:12px; font-weight:bold;'>"
                f"Pipeline Interrupted: {exc}</div>"
            )
            record_fatal_crash(exc, audit_log_path=self.audit_log_path)
            with self.telemetry_output:
                print(f"[SCRIBE-FATAL] Pipeline failed with exception: {exc}")
                traceback.print_exc(file=sys.stdout)
            self.tail_audit_log()
            raise exc

        finally:
            self._is_running = False
            self.set_lockdown(False)

    # =========================================================================
    # VOILA DOM RENDERING & DISPLAY
    # =========================================================================

    def render(self) -> widgets.Tab:
        """Returns the complete 3-tab widget tree for Voila/Jupyter DOM injection."""
        return self.tab

    def display(self) -> widgets.Tab:
        """Displays the dashboard directly in the active notebook shell."""
        rendered = self.render()
        display(rendered)
        return rendered
