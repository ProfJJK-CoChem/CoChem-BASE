import atexit
import base64
import hashlib
import html
import json
import logging
import math
import os
import re
import shutil
import sys
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any, Optional, Sequence, Tuple
from urllib.parse import quote

import ipywidgets as widgets
from pydantic import BaseModel, Field
from traitlets import HasTraits, Unicode

# Ensure src and Libraries directories are discoverable on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_src_path = str(_REPO_ROOT / "src")
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)
_lib_path = str(_REPO_ROOT / "Libraries")
if _lib_path not in sys.path:
    sys.path.insert(0, _lib_path)

# Core CoChem imports for Method Matrix v4 and SRS Chunk 4
from cochem.hpc.slurm_controller import (
    SlurmSubmissionController,
)
from cochem_base.exceptions import MethodologyViolationError
from cochem_base.geometry.fragment_partitioner import (
    detect_molecular_fragments,
    generate_frozen_monomer_orca_block,
)
from cochem_base.spectroscopy.isotopologue import (
    IsotopologueSpectroscopyEngine,
)
from cochem_base.spectroscopy.parser import (
    SpectroscopyTelemetryParser,
)
from cochem_base.theory_matrix import (
    COMPLEXITY_TIERS,
    METHOD_MATRIX_TIERS,
    PRODUCT_CLASS_SPECS,
    ProductClass,
    validate_method_matrix_compliance,
    validate_product_class_policy,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


METHOD_MATRIX_TIERS = dict(METHOD_MATRIX_TIERS)
METHOD_MATRIX_TIERS = {"Tier 0: Machine Learning Force Fields (MLFF)": {
    "methods": ["MACE-OFF24(M)", "AIMNet2"],
    "allowed_basis_sets": ["None (MLFF)"]
}, **METHOD_MATRIX_TIERS}

class P7RegistryModel(BaseModel):
    scheduler_detected: str = Field(default="")

# One serialization contract for both entry points; unsupported fields fail closed.
from cochem_base.calc.calculation_service import CalculationMatrixConfig


class MatrixConfigModel(CalculationMatrixConfig):
    """Compatibility name for the canonical calculation configuration schema."""


class CoChemGUIState(HasTraits):
    """
    State model for the CoChem GUI.
    Enforces MVC architecture and Strict Physical Compliance.
    """
    active_view = Unicode('install')
    system_status = Unicode('Idle')
    environment = Unicode('Detecting...')
    error_message = Unicode('')

class DataInspectorWidget(widgets.VBox):
    """Authentic interactive Data Inspector widget for ab-initio spectroscopic observables."""
    def __init__(self, children: Sequence[Any] = (), **kwargs: Any) -> None:
        super().__init__(children=list(children), **kwargs)


class BoundedTelemetryOutput(widgets.Output):
    """Keep at most 1,000 displayed lines while full process logs remain on disk."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._lines: deque[str] = deque(maxlen=1000)
        self._output_lock = threading.Lock()

    def append_stdout(self, text: str) -> None:
        with self._output_lock:
            self._lines.extend(text.splitlines(keepends=True))
            self.outputs = ({"output_type": "stream", "name": "stdout", "text": "".join(self._lines)},)

    def clear_output(self, *args: Any, **kwargs: Any) -> None:
        with self._output_lock:
            self._lines.clear()
            self.outputs = ()


def _observable(value: Optional[float], precision: int = 3) -> str:
    """Missing scientific evidence is distinct from an observed zero."""
    return "[MISSING DATA]" if value is None else f"{value:.{precision}f}"


class CourseAccessWidget(widgets.VBox):
    """Data-only lab enrollment; access remains the worker's observed authority."""

    def __init__(self, *, project_repository: str, artifact_dir: Path,
                 controller_repository: str = "", app_slug: str = "", on_refresh: Any = None) -> None:
        from cochem_base.config_loader import get_artifact_dir

        self._settings_path = get_artifact_dir(artifact_dir) / "StudentSetup" / "course-access.json"
        self._restore_warning = ""
        saved = self._load_settings()
        self.project = widgets.Text(description="Current project:", value=project_repository,
            disabled=True, style={'description_width': 'initial'}, layout=widgets.Layout(width='95%'))
        self.controller = widgets.Text(description="Instructor access repository:",
            value=controller_repository or saved.get("controller_repository", ""),
            placeholder="instructor-organization/private-access-controller",
            style={'description_width': 'initial'}, layout=widgets.Layout(width='95%'))
        self.app_slug = widgets.Text(description="Instructor lab App slug:", value=app_slug or saved.get("app_slug", ""),
            placeholder="App slug from your instructor's invitation", style={'description_width': 'initial'},
            layout=widgets.Layout(width='95%'))
        selected = saved.get("engines", ["orca", "cfour"])
        self.orca = widgets.Checkbox(description="Request optional ORCA access", value="orca" in selected,
            style={'description_width': 'initial'}, indent=False)
        self.cfour = widgets.Checkbox(description="Request optional CFOUR access", value="cfour" in selected,
            style={'description_width': 'initial'}, indent=False)
        self.links = widgets.HTML()
        self.status = widgets.HTML()
        self.btn_save = widgets.Button(description="Save lab invitation")
        self.btn_save.on_click(self._save_settings)
        self.btn_refresh = widgets.Button(description="Refresh lab access", disabled=on_refresh is None)
        if on_refresh is not None:
            self.btn_refresh.on_click(on_refresh)
        super().__init__(children=[
            widgets.HTML("<h3>Lab Access for your personal project</h3>"
                "<p>Use your own <b>private</b> GitHub project and the invitation supplied by your instructor. "
                "This keeps Actions usage with the project owner. Organization-owned assignments use the organization's Actions allowance. "
                "Organization secrets do not transfer to personal projects.</p>"),
            self.project, self.controller, self.app_slug, self.orca, self.cfour,
            widgets.HTML("<p>ORCA and CFOUR are optional and strongly recommended. You can request module access without either licensed engine. "
                "Your instructor must authorize the applicable license access.</p>"),
            self.links, self.status, widgets.HBox([self.btn_save, self.btn_refresh]),
            widgets.HTML("<ol><li>Select <b>Authorize lab app</b>. On GitHub, choose your personal account and "
                "<b>Only select repositories</b>, select the private project shown above, and approve the instructor's App.</li>"
                "<li>Select <b>Request project access</b>, then <b>Submit new issue</b> on GitHub. "
                "The request is already filled in; do not add passwords or tokens. Wait for the instructor controller's result on that issue.</li>"
                "<li>After access is granted, select <b>Refresh lab access</b> for a real Actions archive-access check. "
                "Each calculation separately verifies installation and scientific execution.</li>"
                "<li>To receive newly granted private module access, create a <b>fresh Codespace</b> for this same project. "
                "BASE installs the approved modules automatically. Your existing Codespace does not prove it has received the new access.</li></ol>"
                "<p>For an organization-owned assignment whose instructor already configured access, use the existing "
                "<b>Retry remote engine check</b>; personal-project enrollment is unnecessary.</p>"),
        ], layout=widgets.Layout(border='1px solid #b8daff', padding='12px', margin='10px 0'))
        for control in (self.controller, self.app_slug, self.orca, self.cfour):
            control.observe(self._render_links, names="value")
        self._render_links()

    def _load_settings(self) -> dict[str, Any]:
        path = self._settings_path
        if not path.exists() and not path.is_symlink():
            return {}
        try:
            if path.is_symlink() or path.parent.is_symlink() or path.stat().st_size > 4096:
                raise ValueError("The retained invitation is not a bounded regular settings file.")
            saved = json.loads(path.read_text(encoding="utf-8"))
            if (not isinstance(saved, dict) or set(saved) != {"schema", "controller_repository", "app_slug", "engines"}
                    or saved["schema"] != "cochem.course-invitation/1"
                    or not isinstance(saved["controller_repository"], str) or not isinstance(saved["app_slug"], str)
                    or not isinstance(saved["engines"], list)
                    or any(value not in {"orca", "cfour"} for value in saved["engines"])
                    or len(set(saved["engines"])) != len(saved["engines"])):
                raise ValueError("The retained invitation has an unsupported format.")
            return saved
        except (ValueError, OSError, TypeError) as exc:
            self._restore_warning = "Retained lab invitation was not loaded: " + str(exc)
            return {}

    def set_project(self, repository: str) -> None:
        self.project.value = repository
        self._render_links()

    def _enrollment_links(self) -> dict[str, str]:
        from cochem_base.interfaces.course_access import enrollment_links
        engines = tuple(engine for engine, selected in (("orca", self.orca.value), ("cfour", self.cfour.value)) if selected)
        return enrollment_links(self.controller.value.strip(), self.app_slug.value.strip(),
            self.project.value.strip(), engines)

    def _render_links(self, change: Any = None) -> None:
        self.links.value = ""
        self.btn_save.disabled = True
        if not self.controller.value.strip() or not self.app_slug.value.strip() or not self.project.value.strip():
            message = "[MISSING DATA] Confirm your project above and enter the access repository and App slug from your instructor's invitation."
        else:
            try:
                links = self._enrollment_links()
            except (ImportError, ValueError, RuntimeError) as exc:
                message = "Lab enrollment links are unavailable: " + str(exc)
            else:
                self.links.value = "<p>" + " · ".join(
                    f"<a href='{html.escape(links[key], quote=True)}' target='_blank' rel='noopener noreferrer' "
                    "style='display:inline-block;padding:8px 12px;border:1px solid #0056b3;border-radius:4px;color:#0056b3'>"
                    + label + "</a>" for key, label in (("install", "Authorize lab app"), ("enroll", "Request project access"))) + "</p>"
                self.btn_save.disabled = False
                message = "Enrollment links are ready. Access has not been verified; submitting a request does not enable calculation methods."
        if self._restore_warning:
            message += " " + self._restore_warning
        self.status.value = "<p role='status' aria-live='polite'>" + html.escape(message) + "</p>"

    def _save_settings(self, b: Any = None) -> None:
        from cochem_base.config_loader import get_artifact_dir
        try:
            self._enrollment_links()
            # Recheck the data tier rather than following a changed settings symlink.
            root = get_artifact_dir(self._settings_path.parent.parent)
            directory = root / "StudentSetup"
            if directory.is_symlink() or self._settings_path.is_symlink():
                raise ValueError("Lab invitation settings must remain in the owned data directory.")
            directory.mkdir(parents=True, exist_ok=True)
            saved = {"schema": "cochem.course-invitation/1", "controller_repository": self.controller.value.strip(),
                "app_slug": self.app_slug.value.strip(), "engines": [engine for engine, selected in
                (("orca", self.orca.value), ("cfour", self.cfour.value)) if selected]}
            temporary = directory / (".course-access-" + uuid.uuid4().hex + ".json")
            with temporary.open("x", encoding="utf-8") as stream:
                json.dump(saved, stream, sort_keys=True)
                stream.write("\n")
            temporary.replace(self._settings_path)
        except (ImportError, ValueError, RuntimeError, OSError) as exc:
            self.status.value = "<p role='alert'>Lab invitation could not be retained: " + html.escape(str(exc)) + "</p>"
            return
        self._restore_warning = ""
        self.status.value = "<p role='status'>Lab invitation saved with your research data. No credentials were stored and no access has been granted by this action.</p>"


def licensed_engine_availability(registry_path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    """Report optional engine authority without turning absence into BASE failure."""
    from cochem_base.core_engine.execution_authority import authorize_engine_execution

    availability = {}
    for engine in ("orca", "cfour"):
        try:
            authority = authorize_engine_execution(engine, registry_path=registry_path, cores=1)
        except (ValueError, RuntimeError, OSError) as exc:
            availability[engine] = {"available": False, "reason": str(exc)}
        else:
            availability[engine] = {"available": True, "executable": authority.executable}
    return availability


class CoChemGUI:
    def __init__(self) -> None:
        self.state = CoChemGUIState()
        self._pipeline_running = False
        self._pipeline_cancellation = threading.Event()
        self._student_research_running = False
        self._student_uploads: dict[str, dict[str, Any]] = {}
        self._input_library: dict[str, dict[str, Any]] = {}
        self._input_library_refresh_serial = 0
        self._ingestion_busy = False
        self._inbox_stop = threading.Event()
        self._student_setup_busy = False
        self._hpc_running = False
        self._hpc_retrieving = False
        self._hpc_submission: dict[str, Any] | None = None
        self._hpc_job_serial = 0
        self._hpc_client = None
        self._hpc_preflight_observation: dict[str, Any] | None = None
        self._hpc_preflight_running = False
        self._hpc_preflight_generation = 0
        self._hpc_preflight_worker: threading.Thread | None = None
        self._hpc_monitor_stop = threading.Event()
        self._hpc_history_loaded = threading.Event()
        self._actions_running = False
        self._actions_submission: dict[str, Any] | None = None
        self._actions_client = None
        self._actions_monitor_stop = threading.Event()
        self._actions_retrieved = None
        self._actions_input_record = None
        self._setup_service = None
        self._input_selection_running = False
        self._t9_backend_observation: dict[str, Any] | None = None
        self._t9_backend_generation = 0
        self._t9_backend_running = False
        self._t9_backend_worker: threading.Thread | None = None
        self._remote_probe_running = False
        self._actions_retrieving = False
        self._remote_probe_client = None
        self._remote_probe_submission = None
        self._remote_engine_target = None
        self._remote_engine_availability = {engine: {"status": "unknown", "provisionable": False,
            "reason": "Remote engine access has not been checked."} for engine in ("orca", "cfour")}

        # --- Environment Auto-Detection ---
        is_init, env_str, is_hpc, is_slurm = self._detect_environment()
        self.state.environment = env_str
        if not is_init:
            self.state.error_message = "Environment Not Initialized. Please complete setup."
            self.state.system_status = "Uninitialized"

        # --- UI Components ---

        # 1. Header (Appbar)
        self.header_title = widgets.HTML("<h2>CoChem No-Code Interface</h2>", layout=widgets.Layout(margin='0px 20px 0px 0px'))
        self.header_status = widgets.HTML(f"<b role='status' aria-live='polite'>[System: {self.state.system_status}]</b>", layout=widgets.Layout(margin='10px 20px 0px 0px'))
        # Remote assistance must not claim a connection without a live backend.
        self.ai_container = widgets.VBox([widgets.HTML(
            "<p role='status'>AI assistant: [MISSING DATA] No connected assistant backend.</p>"
        )])
        self.header_env = widgets.HTML(f"<i>Environment: {self.state.environment}</i>", layout=widgets.Layout(margin='10px 0px 0px 0px'))

        self.header = widgets.HBox(
            [self.header_title, self.header_status, self.header_env],
            layout=widgets.Layout(
                display='flex',
                justify_content='flex-start',
                align_items='center',
                padding='10px',
                border='1px solid #ccc',
            )
        )

        # 2. Sidebar (Navigation)
        self.btn_install = widgets.Button(description="Seamless Install", icon='cogs', layout=widgets.Layout(width='auto', margin='5px 0'))
        self.btn_matrix = widgets.Button(description="No Code Matrix", icon='table', layout=widgets.Layout(width='auto', margin='5px 0'))
        self.btn_inspector = widgets.Button(description="Data Inspector (Ab-Initio)", icon='search', layout=widgets.Layout(width='auto', margin='5px 0'))
        self.btn_modules = widgets.Button(description="Research results", layout=widgets.Layout(width='auto', margin='5px 0'))
        self.btn_periodic = widgets.Button(description="Periodic structures", layout=widgets.Layout(width='auto', margin='5px 0'))
        self.btn_inputs = widgets.Button(description="Input library", layout=widgets.Layout(width='auto', margin='5px 0'))

        # Configuration and inspection work without provisioned quantum engines.
        # Execution performs its own dependency and scientific validation.

        self.btn_install.on_click(lambda b: setattr(self.state, 'active_view', 'install'))
        self.btn_matrix.on_click(lambda b: setattr(self.state, 'active_view', 'matrix'))
        self.btn_inspector.on_click(lambda b: setattr(self.state, 'active_view', 'inspector'))
        self.btn_modules.on_click(lambda b: setattr(self.state, 'active_view', 'modules'))
        self.btn_periodic.on_click(lambda b: setattr(self.state, 'active_view', 'periodic'))
        self.btn_inputs.on_click(lambda b: setattr(self.state, 'active_view', 'inputs'))

        self.sidebar = widgets.VBox(
            [self.btn_install, self.btn_inputs, self.btn_matrix, self.btn_inspector, self.btn_periodic, self.btn_modules],
            layout=widgets.Layout(
                width='250px',
                padding='10px',
                border='1px solid #ccc',
            )
        )

        # 3. Main Content Area (Views)

        # 3.1 Seamless Install View
        
        self.gh_repo_input = widgets.Text(
            description="Course repository:", value=os.environ.get("GITHUB_REPOSITORY", ""),
            placeholder="course-organization/student-repository", style={'description_width': 'initial'},
            layout=widgets.Layout(width='90%'),
        )
        self.gh_branch_input = widgets.Text(
            description="Approved branch:", value=os.environ.get("GITHUB_REF_NAME", "main"),
            style={'description_width': 'initial'},
        )
        self.gh_guidance = widgets.HTML()
        self.remote_engine_status = widgets.HTML("<p role='status'>Remote licensed-engine availability has not been checked.</p>")
        self.btn_remote_engine_check = widgets.Button(description="Retry remote engine check")
        self.btn_remote_engine_check.on_click(self._check_remote_engines)
        self.btn_remote_engine_cancel = widgets.Button(description="Cancel remote engine check", disabled=True)
        self.btn_remote_engine_cancel.on_click(self._cancel_remote_engine_check)
        from cochem_base.config_loader import get_artifact_dir
        self.course_access_panel = CourseAccessWidget(project_repository=self.gh_repo_input.value,
            artifact_dir=get_artifact_dir(),
            controller_repository=os.environ.get("COCHEM_ACCESS_CONTROLLER_REPOSITORY", ""),
            app_slug=os.environ.get("COCHEM_ACCESS_APP_SLUG", ""), on_refresh=self._refresh_lab_access)
        self.gh_setup_box = widgets.VBox([
            self.gh_repo_input, self.gh_branch_input, self.course_access_panel,
            widgets.HBox([self.btn_remote_engine_check, self.btn_remote_engine_cancel]), self.remote_engine_status, self.gh_guidance,
        ], layout=widgets.Layout(border='1px solid #0056b3', padding='15px', margin='10px 0'))
        self.gh_repo_input.observe(self._refresh_actions_guidance, names='value')
        self.gh_repo_input.observe(lambda change: self.course_access_panel.set_project(change['new']), names='value')
        self.gh_branch_input.observe(self._refresh_actions_guidance, names='value')
        self.actions_job_download = widgets.HTML()
        self._last_actions_job = None
        self.actions_operation = widgets.Dropdown(
            options=[("Single point", "single_point"), ("Optimization", "optimization"),
                     ("Harmonic frequencies", "harmonic_frequencies"),
                     ("Optimize + harmonic frequencies", "optimization_frequencies")],
            value="single_point", description="Actions operation:", style={'description_width': 'initial'},
        )
        self.actions_timeout = widgets.BoundedIntText(
            value=300, min=30, max=1800, description="Calculation timeout (s):",
            style={'description_width': 'initial'},
        )
        self.actions_cores = widgets.BoundedIntText(value=2, min=1, max=2, description="Calculation cores:",
                                                   style={'description_width': 'initial'})
        self.actions_memory = widgets.BoundedIntText(value=512, min=256, max=1024, description="Memory per core (MB):",
                                                    style={'description_width': 'initial'})
        self.native_operation = widgets.Dropdown(options=list(self.actions_operation.options), value='optimization',
            description='Calculation operation:', style={'description_width': 'initial'})
        self.native_timeout = widgets.BoundedIntText(value=1800, min=30, max=172800,
            description='Native timeout (s):', style={'description_width': 'initial'})
        self.native_job_options = widgets.VBox([self.native_operation, self.native_timeout,
            widgets.HTML('<p>Choose an actual native operation. Frequencies at supplied coordinates do not establish a stationary structure; optimize first when a minimum is required. HPC resource requests are configured in the scheduler panel.</p>')],
            layout=widgets.Layout(display='none'))
        self.actions_job_options = widgets.VBox([
            self.actions_operation, self.actions_timeout, self.actions_cores, self.actions_memory,
            widgets.HTML("<p>Course profile: ORCA or CFOUR, up to 50 atoms, one or two cores, "
                         "512 MB per core by default (maximum 1024 MB), and at most 1800 seconds per calculation. "
                         "BASE submits the selected resources and monitors the calculation here.</p>"
                         "<p>Harmonic frequencies at supplied coordinates do not certify a stationary structure. "
                         "Choose <b>Optimize + harmonic frequencies</b> to optimize first. VPT2 remains a separate module integration.</p>"),
        ], layout=widgets.Layout(display='none'))
        self.actions_operation.observe(self._invalidate_actions_job, names='value')
        self.actions_timeout.observe(self._invalidate_actions_job, names='value')
        self.calculation_environment_status = widgets.HTML()

        self.calc_env_dropdown = widgets.Dropdown(
            options=[
                ('Windows (Native - DEGRADED)', 'local'), 
                ('WSL2 (Recommended for Windows)', 'wsl'), 
                ('macOS', 'macos'), 
                ('Linux', 'linux'), 
                ('GitHub Actions (Cloud Compute)', 'github-actions'), 
                ('HPC Cluster (Slurm/PBS)', 'hpc')
            ],
            value='github-actions' if os.environ.get('CODESPACES', '').lower() == 'true' else
                  'macos' if sys.platform == 'darwin' else 'local' if os.name == 'nt' else 'linux',
            description='Calculation Environment:',
            style={'description_width': 'initial'}
        )
        self.interact_env_dropdown = widgets.Dropdown(
            options=['Local', 'GitHub Codespaces'],
            value='GitHub Codespaces' if os.environ.get('CODESPACES', '').lower() == 'true' else 'Local',
            description='Interaction Environment:',
            style={'description_width': 'initial'}
        )

        self.run_install_btn = widgets.Button(
            description="Run Installation",
            button_style="success",
            icon="play", disabled=False,
        )
        self.license_mode = widgets.Dropdown(
            options=[("Free engines", "none"), ("Also check ORCA", "orca"), ("Also check CFOUR", "cfour")],
            description="Optional engine check:", style={'description_width': 'initial'},
        )
        self.licensed_engine_status = widgets.HTML()
        self.install_data_path = widgets.Text(
            description="Scientific data:", placeholder="Geometry-bound .npz/.h5 Hessian bundle",
            style={'description_width': 'initial'}, layout=widgets.Layout(width='90%'),
        )
        self.install_data_status = widgets.HTML("<p>Optional: validate an existing geometry-bound .h5 or .npz scientific bundle. Environment setup also works with starting geometries alone.</p>")
        self.btn_validate_install_data = widgets.Button(description="Validate scientific data")
        self.btn_validate_install_data.on_click(self._validate_installation_data)
        self.install_data_path.observe(self._invalidate_installation_data, names="value")
        self.install_min_disk = widgets.BoundedFloatText(
            value=50.0, min=0.1, max=100000.0, description="Required disk (GB):",
            style={'description_width': 'initial'},
        )
        self._install_input_artifact = None
        self._installation_running = False
        
        
        self.wsl_setup_box = widgets.VBox(layout=widgets.Layout(border='1px solid #28a745', padding='15px', margin='10px 0'))
        
        def _check_wsl_status():
            import subprocess
            try:
                # Run wsl -l -q to check if installed
                res = subprocess.run(['wsl', '-l', '-q'], capture_output=True, text=True)
                if res.returncode == 0:
                    return True, "✓ WSL2 is installed and ready!"
                else:
                    return False, "⚠️ WSL is installed but no distributions found. Open PowerShell as Admin and run: wsl --install"
            except FileNotFoundError:
                return False, "❌ WSL is NOT installed! Open PowerShell as Admin and run: wsl --install"
        
        self.wsl_status_html = widgets.HTML()
        self.btn_refresh_wsl = widgets.Button(description="Check WSL Status", button_style="info", icon="refresh")
        
        def _update_wsl_ui(*args):
            is_installed, msg = _check_wsl_status()
            if is_installed:
                self.wsl_status_html.value = f"<h4 style='color:green;'>{msg}</h4><p>You can now use the Optimal WSL2 backend for heavy calculations.</p>"
            else:
                self.wsl_status_html.value = f"<h4 style='color:red;'>{msg}</h4><p>Native Windows is restricted to DEGRADED mode due to kernel stack limits. Installing WSL2 is strongly recommended for CoChem.</p>"

        self.btn_refresh_wsl.on_click(_update_wsl_ui)
        _update_wsl_ui()

        self.wsl_setup_box.children = [
            widgets.HTML("<h4>WSL2 Local Backend Provisioning</h4>"),
            self.wsl_status_html,
            self.btn_refresh_wsl
        ]

        
        

        
        self.bin_orca = widgets.Text(description="ORCA Path:", placeholder="Absolute path to orca executable", layout=widgets.Layout(width='80%'))
        self.bin_cfour = widgets.Text(description="CFOUR Path:", placeholder="Absolute path to xcfour executable", layout=widgets.Layout(width='80%'))
        
        self.btn_detect_bins = widgets.Button(description="Auto-Detect from PATH", button_style="info", icon="search", layout=widgets.Layout(width='auto'))
        self.btn_save_bins = widgets.Button(description="Inject Paths into Environment", button_style="success", icon="save", layout=widgets.Layout(width='auto'))
        self.local_setup_output = widgets.HTML("")

        def _auto_detect(b):
            import shutil
            orca_path = shutil.which("orca")
            cfour_path = shutil.which("xcfour")
            if orca_path: self.bin_orca.value = orca_path
            if cfour_path: self.bin_cfour.value = cfour_path
            
            msg = "Auto-detection complete. "
            if orca_path or cfour_path:
                self.local_setup_output.value = f"<b style='color:green'>{msg} Found binaries in PATH!</b>"
            else:
                self.local_setup_output.value = f"<b style='color:orange'>{msg} No binaries found in system PATH.</b>"

        def _save_local_bins(b):
            import os
            paths = [os.path.dirname(self.bin_orca.value), os.path.dirname(self.bin_cfour.value)]
            valid_paths = [p for p in paths if p and os.path.isdir(p)]
            if valid_paths:
                os.environ["PATH"] = os.pathsep.join(valid_paths) + os.pathsep + os.environ.get("PATH", "")
                self.local_setup_output.value = "<b style='color:green'>Paths temporarily added to system PATH for installation!</b>"

        self.btn_detect_bins.on_click(_auto_detect)
        self.btn_save_bins.on_click(_save_local_bins)

        local_guidance_html = """
        <h4>Local Binary Setup (ORCA / CFOUR)</h4>
        <div style='background-color:#e2e3e5; padding:10px; border-left:4px solid #6c757d; margin-bottom:10px;'>
        <b>Open Source Binaries:</b> CREST, SPFIT, and SPCAT will be downloaded and compiled automatically by CoChem during the installation phases. You do not need to provide them.<br/>
        <b>Optional, strongly recommended licensed engines:</b> ORCA and CFOUR broaden the available calculations. BASE works without either engine. If already installed, click 'Auto-Detect' or provide their executable paths. An unavailable engine disables only its dependent calculations.
        </div>
        """
        self.local_setup_box = widgets.VBox([
            widgets.HTML(local_guidance_html),
            self.bin_orca, self.bin_cfour, 
            widgets.HBox([self.btn_detect_bins, self.btn_save_bins]), 
            self.local_setup_output
        ], layout=widgets.Layout(border='1px solid #17a2b8', padding='15px', margin='10px 0'))
        self.dynamic_setup_container = widgets.VBox([])
        
        def _on_calc_env_change(change):
            env = change['new']
            if env == 'hpc' and hasattr(self, 'btn_hpc_connect'):
                self._check_student_hpc_connection()
            if env == 'github-actions':
                self.dynamic_setup_container.children = [self.gh_setup_box]
            elif env == 'wsl':
                self.dynamic_setup_container.children = [self.wsl_setup_box, self.local_setup_box]
            elif env in ['local', 'windows', 'macos', 'linux', 'hpc']:
                self.dynamic_setup_container.children = [self.local_setup_box]
            else:
                self.dynamic_setup_container.children = []
            self._invalidate_actions_job()
            self._refresh_actions_guidance()
            self.run_install_btn.description = "Review Actions setup" if env == "github-actions" else "Run Installation"
            self.run_install_btn.disabled = self._installation_running
            if hasattr(self, 'local_install_options'):
                self.local_install_options.layout.display = 'none' if env == 'github-actions' else ''
            if hasattr(self, 'btn_execute'):
                self._check_dispersion_gate()
                self._refresh_topos_capabilities()
                if env == 'github-actions' and self._automatic_remote_checks_enabled():
                    self._check_remote_engines()
                
        self.calc_env_dropdown.observe(_on_calc_env_change, names='value')
        _on_calc_env_change({'new': self.calc_env_dropdown.value})

        self.run_install_btn.on_click(self._run_installation)

        self.install_output = BoundedTelemetryOutput(layout=widgets.Layout(border='1px solid #ccc', height='300px', overflow='auto'))
        self.local_install_options = widgets.VBox([
            self.license_mode,
            widgets.HTML("<p>ORCA and CFOUR are optional and strongly recommended. Free dependencies are installed or audited; "
                         "licensed engines are discovered when separately provisioned. An unavailable licensed engine does not fail BASE setup. "
                         "Its dependent methods remain unavailable until that engine passes its execution audit.</p>"),
            self.licensed_engine_status,
            self.install_data_path, self.btn_validate_install_data, self.install_data_status,
            self.install_min_disk,
            widgets.HTML("<p>Set the required disk space to the measured needs of your workload. The default reserves 50 GB.</p>"),
            widgets.HTML("<h4>Installation Logs</h4>"),
            self.install_output,
        ], layout=widgets.Layout(display='none' if self.calc_env_dropdown.value == 'github-actions' else ''))
        self.view_install = widgets.VBox([
            widgets.HTML("<h3>Seamless Install Wizard</h3>"),
            widgets.HTML("<p>Setup pipeline and real physical data ingestion.</p>"),
            self.calc_env_dropdown,
            self.interact_env_dropdown,
            self.dynamic_setup_container,
            self.local_install_options,
            self.run_install_btn,
        ], layout=widgets.Layout(padding='20px'))
        self._build_student_setup_panel()
        self.view_install.children = (self.student_setup_panel, *self.view_install.children)

        # 3.2 Step 0: Product Class Gate & No Code Matrix View
        self.product_class_selector = widgets.RadioButtons(
            options=[pc.value for pc in ProductClass] + ["Screening (no product accuracy claim)"],
            value=ProductClass.PRODUCT_A.value,
            description="Step 0 Gate:",
            style={'description_width': 'initial'},
            layout=widgets.Layout(width='100%')
        )
        self.product_class_card = widgets.HTML(
            self._format_product_class_card(ProductClass.PRODUCT_A.value),
            layout=widgets.Layout(border='1px solid #b8daff', padding='8px', margin='5px 0')
        )
        self.product_class_selector.observe(self._on_product_class_changed, 'value')

        
        self.charge_input = widgets.IntText(value=0, description="Charge:")
        self.multiplicity_input = widgets.IntText(value=1, description="Multiplicity:")
        self.mlff_warning = widgets.HTML("", layout=widgets.Layout(margin='5px 0'))
        
        def _check_mlff_validity(*args):
            c = self.charge_input.value
            m = self.multiplicity_input.value
            # Method Matrix v4: MACE-OFF limited to neutral, non-radical systems
            if c != 0 or m != 1:
                self.mlff_warning.value = "<b style='color:red;'>⚠️ MLFF (MACE/AIMNet2) disabled: Molecule must be neutral (charge=0) and non-radical (mult=1).</b>"
                # If currently selected, revert
                if hasattr(self, 'matrix_tier') and 'Tier 0' in self.matrix_tier.value:
                    self.matrix_tier.value = 'Tier 1: Modern Dispersion DFT'
            else:
                self.mlff_warning.value = "<b style='color:green;'>Neutral closed-shell MLFF eligibility satisfied; MLFF execution is not connected to this launcher.</b>"
                
        self.charge_input.observe(_check_mlff_validity, 'value')
        self.multiplicity_input.observe(_check_mlff_validity, 'value')
        _check_mlff_validity()

        self.matrix_geometry = widgets.Textarea(
            description="Geometry (XYZ):",
            placeholder="O 0.0 0.0 0.0\nH 0.0 0.75 -0.5\nH 0.0 0.75 0.5",
            layout=widgets.Layout(width='100%', height='100px')
        )
        engine_options = self._local_engine_choices()
        self._local_engine_options = tuple(engine_options)

        self.matrix_engine = widgets.Dropdown(
            options=engine_options,
            value='ORCA' if any(value == 'ORCA' for _, value in engine_options) else None,
            description='Engine:'
        )
        self.matrix_engine.tooltip = "Scientific execution requires the complete eleven-phase setup audit. Licensed binaries must be installed separately. Other module requests use Module handoff."
        self.cfour_operation = widgets.Dropdown(
            options=[("Single point", "single_point"), ("Optimization", "optimization"),
                     ("Harmonic frequencies", "harmonic_frequencies"),
                     ("Optimize + harmonic frequencies", "optimization_frequencies")],
            value='single_point', description='CFOUR operation:',
            style={'description_width': 'initial'}, layout=widgets.Layout(display='none'),
        )
        self.cfour_operation.observe(self._check_dispersion_gate, names='value')

        # Method Matrix v4 Tier and Method selection
        self.matrix_tier = widgets.Dropdown(
            options=list(METHOD_MATRIX_TIERS.keys()),
            value="T4",
            description="Theory Tier:",
            style={'description_width': 'initial'}
        )
        default_methods = METHOD_MATRIX_TIERS["T4"]["methods"]

        default_bases = METHOD_MATRIX_TIERS["T4"]["allowed_basis_sets"]

        self.matrix_method = widgets.Dropdown(
            options=default_methods,
            value=default_methods[0],
            description='Method:'
        )
        self.matrix_basis = widgets.Dropdown(
            options=default_bases,
            value=default_bases[0],
            description='Basis Set:'
        )
        self.matrix_solvation = widgets.Dropdown(
            options=[("None", None), ("Water (CPCM)", "CPCM(Water)"), ("Acetone (CPCM)", "CPCM(Acetone)"), ("Ethanol (CPCM)", "CPCM(Ethanol)")],
            value="CPCM(Water)", description="Solvation:",
        )
        self.matrix_cbs_pair = widgets.Dropdown(
            options=[("Not supplied", None), ("Triple/quadruple zeta", (3, 4)), ("Quadruple/quintuple zeta", (4, 5))],
            value=None, description="CBS pair:",
        )
        self.unphysical_override = widgets.Checkbox(
            value=False,
            description="Dispersion safeguards are required",
            disabled=True,
            style={'description_width': 'initial'}
        )
        self.dispersion_warning = widgets.HTML("", layout=widgets.Layout(margin='5px 0'))
        self.engine_warning = widgets.HTML("", layout=widgets.Layout(margin='5px 0'))

        self.matrix_tier.observe(self._on_tier_changed, 'value')

        self.tier_help = widgets.HTML(
            value="<details><summary>Canonical T0–T9 theory families</summary><ul>"
            + "".join(f"<li>{html.escape(tier)}: {html.escape(metadata['classification'])}</li>"
                      for tier, metadata in COMPLEXITY_TIERS.items())
            + "</ul><p>Calculation time and product accuracy require measured evidence for the selected system; a tier label alone does not establish either.</p></details>",
            layout=widgets.Layout(margin='10px 0'),
        )

        self.matrix_method.observe(self._check_dispersion_gate, 'value')
        self.matrix_engine.observe(self._check_dispersion_gate, 'value')
        self.matrix_engine.observe(self._on_engine_changed, 'value')
        self.charge_input.observe(self._check_dispersion_gate, 'value')
        self.multiplicity_input.observe(self._check_dispersion_gate, 'value')
        self.matrix_solvation.observe(self._check_dispersion_gate, 'value')
        self.matrix_cbs_pair.observe(self._check_dispersion_gate, 'value')
        self.unphysical_override.observe(self._check_dispersion_gate, 'value')

        # TOPOS Widgets
        self._topos_broker = None
        self._topos_job_id = None
        self._topos_running = False
        self._topos_cancellation = threading.Event()
        atexit.register(self._cleanup_topos_search)
        self.topos_heuristic = widgets.Dropdown(
            options=[('Checking audited engines', 'CREST_NCI')],
            value='CREST_NCI',
            description='Search protocol:', style={'description_width': 'initial'},
            layout=widgets.Layout(width='90%'),
        )
        self.topos_dedup = widgets.FloatSlider(
            value=0.05, min=0.01, max=0.5, step=0.01,
            description='Dedup Tol:'
        )

        # TORQ Widgets
        self.torq_dihedrals = widgets.Text(
            placeholder='e.g. 0 1 2 3',
            description='Active Dihedrals:',
            style={'description_width': 'initial'}
        )
        self.torq_resolution = widgets.IntSlider(
            value=36, min=12, max=72, step=12,
            description='Scan Res:'
        )
        self.torq_qrrho = widgets.Checkbox(
            value=False,
            description='Enable qRRHO'
        )

        for unavailable in (self.topos_heuristic, self.topos_dedup, self.torq_dihedrals,
                            self.torq_resolution, self.torq_qrrho):
            unavailable.disabled = True
        self.topos_walltime = widgets.BoundedFloatText(
            value=2.0, min=0.1, max=1440.0, description="Search limit (min):",
            style={'description_width': 'initial'},
        )
        self.topos_status = widgets.HTML("<p role='status'>No conformer search submitted.</p>")
        self.topos_capabilities = widgets.HTML()
        self.topos_results = widgets.HTML()
        self.btn_topos_refresh = widgets.Button(description="Refresh search engines")
        self.btn_topos_refresh.on_click(self._refresh_topos_capabilities)
        self.btn_topos_submit = widgets.Button(description="Start conformer search", button_style="success")
        self.btn_topos_submit.on_click(self._start_topos_search)
        self.btn_topos_cancel = widgets.Button(description="Cancel conformer search", disabled=True)
        self.btn_topos_cancel.on_click(lambda _: self._topos_cancellation.set())
        self.btn_topos_promote = widgets.Button(description="Publish conformer ensemble", disabled=True)
        self.btn_topos_promote.on_click(self._promote_topos_search)
        self._refresh_topos_capabilities()

        # Task 10: Fragment Partitioning & Frozen Monomer Controls
        self.btn_detect_fragments = widgets.Button(
            description="Auto-Detect Monomers",
            button_style="info",
            icon="cubes"
        )
        self.btn_detect_fragments.on_click(self._on_detect_fragments_clicked)
        self.fragments_output = widgets.HTML("<i>No fragments detected yet. Click 'Auto-Detect Monomers'.</i>")
        self.cb_recipe_r1 = widgets.Checkbox(
            value=True,
            description="Freeze all monomer internals (bonds/angles/dihedrals)",
            style={'description_width': 'initial'}
        )
        self.cb_recipe_r2 = widgets.Checkbox(
            value=False,
            description="Recipe R2: reference monomers and intermolecular relaxation",
            style={'description_width': 'initial'}
        )
        self.r2_reference_manifest = widgets.Text(
            description="R2 reference manifest:", placeholder="Path to validated reference-monomer JSON",
            style={'description_width': 'initial'}, layout=widgets.Layout(width='95%'),
        )
        self.t9_config_path = widgets.Text(
            description="T9 active-space JSON:", placeholder="Optional validated CASSCF/NEVPT2 configuration",
            style={'description_width': 'initial'}, layout=widgets.Layout(width='95%'),
        )
        self.t9_config_path.layout.display = 'none'
        self.t9_enable = widgets.Checkbox(value=False, description="Enable explicit T9 spin-contamination recovery")
        self.t9_method = widgets.Dropdown(options=['CASSCF', 'NEVPT2'], value='NEVPT2', description="Recovery method:",
            style={'description_width': 'initial'})
        self.t9_basis = widgets.Dropdown(options=['STO-3G', 'def2-SVP', 'def2-TZVP', 'cc-pVDZ', 'aug-cc-pVDZ'],
            value='def2-SVP', description="Recovery basis:", style={'description_width': 'initial'})
        self.t9_electrons = widgets.IntText(value=0, description="Active electrons:", style={'description_width': 'initial'})
        self.t9_orbitals = widgets.Text(value='', description="Active MO indices:", placeholder="Distinct zero-based indices, e.g. 4,5,6",
            style={'description_width': 'initial'}, layout=widgets.Layout(width='95%'))
        self.t9_rationale = widgets.Textarea(value='', description="Active-space rationale:",
            style={'description_width': 'initial'}, layout=widgets.Layout(width='95%', height='80px'))
        self.t9_guidance = widgets.HTML()
        self.t9_panel = widgets.VBox([
            widgets.HTML("<h4>T9 recovery</h4><p>An explicit CASSCF/NEVPT2 active space can recover a rejected single-reference spin-contaminated result. Choose the electron count, zero-based molecular orbitals, basis and scientific rationale. BASE binds the audited PySCF interpreter; no executable path or code is entered. Recovery is a single-point calculation on the original geometry and does not certify an interrupted optimization or Hessian.</p>"),
            self.t9_enable, self.t9_method, self.t9_basis, self.t9_electrons, self.t9_orbitals, self.t9_rationale, self.t9_guidance,
        ])
        self.scientific_r2_upload = widgets.FileUpload(accept='.zip', multiple=False, description="Upload R2 references")
        self.scientific_read_upload = widgets.FileUpload(accept='.hess', multiple=False, description="Upload READ Hessian")
        self.scientific_input_status = widgets.HTML("<p role='status'>R2 needs a genuine reference package with original engine evidence. READ needs an authentic Cartesian Hessian bound to this geometry. Missing scientific files disable their dependent requests.</p>")
        self._scientific_inputs = {}
        self.scientific_initial_hessian = widgets.Dropdown(options=[('xTB2 initial curvature', 'XTB2'),
            ('BFGS initial curvature', 'BFGS'), ('Read uploaded Cartesian Hessian', 'READ')], value='XTB2',
            description="Initial Hessian:", style={'description_width': 'initial'})
        self.scientific_r2_upload.observe(lambda change: self._ingest_student_scientific_input('r2_reference', self.scientific_r2_upload), names='value')
        self.scientific_read_upload.observe(lambda change: self._ingest_student_scientific_input('read_hessian', self.scientific_read_upload), names='value')
        self.r2_reference_manifest.layout.display = 'none'
        self.cb_recipe_r2.observe(lambda change: setattr(self.cb_recipe_r1, 'value', False) if change['new'] else None, names='value')
        self.cb_recipe_r1.observe(lambda change: setattr(self.cb_recipe_r2, 'value', False) if change['new'] else None, names='value')
        self.fragment_preview = widgets.Textarea(
            description="ORCA %geom:",
            layout=widgets.Layout(width='100%', height='140px'),
            disabled=True
        )

        # Live Input Preview
        self.live_preview = widgets.Textarea(
            description='Run configuration:',
            layout=widgets.Layout(width='100%', height='150px'),
            disabled=True
        )

        def update_preview(*args):
            self._invalidate_actions_job()
            try:
                self.live_preview.value = json.dumps(self._collect_run_config(), indent=2)
            except (ValueError, RuntimeError, OSError, MethodologyViolationError) as exc:
                self.live_preview.value = f"Configuration requires attention: {exc}"

        self.matrix_geometry.observe(self._check_dispersion_gate, 'value')

        self.matrix_engine.observe(update_preview, 'value')
        self.actions_operation.observe(update_preview, 'value')
        self.native_operation.observe(update_preview, 'value')
        self.native_timeout.observe(update_preview, 'value')
        self.native_operation.observe(self._check_dispersion_gate, 'value')
        self.cfour_operation.observe(update_preview, 'value')
        self.actions_timeout.observe(update_preview, 'value')
        self.calc_env_dropdown.observe(update_preview, 'value')
        self.cb_recipe_r1.observe(self._check_dispersion_gate, 'value')
        self.cb_recipe_r2.observe(self._check_dispersion_gate, 'value')
        self.cb_recipe_r1.observe(update_preview, 'value')
        self.cb_recipe_r2.observe(update_preview, 'value')
        self.r2_reference_manifest.observe(update_preview, 'value')
        self.t9_config_path.observe(update_preview, 'value')
        for control in (self.t9_enable, self.t9_method, self.t9_basis, self.t9_electrons, self.t9_orbitals,
                        self.t9_rationale, self.scientific_initial_hessian):
            control.observe(update_preview, 'value')
            control.observe(self._check_dispersion_gate, 'value')
        self.charge_input.observe(update_preview, 'value')
        self.multiplicity_input.observe(update_preview, 'value')
        self.multiplicity_input.observe(self._check_dispersion_gate, 'value')
        self.matrix_solvation.observe(update_preview, 'value')
        self.matrix_cbs_pair.observe(update_preview, 'value')
        self.matrix_method.observe(update_preview, 'value')
        self.matrix_basis.observe(update_preview, 'value')
        self.matrix_geometry.observe(update_preview, 'value')
        self.product_class_selector.observe(update_preview, 'value')
        self.topos_heuristic.observe(update_preview, 'value')
        self.topos_dedup.observe(update_preview, 'value')
        self.torq_dihedrals.observe(update_preview, 'value')
        self.torq_resolution.observe(update_preview, 'value')
        self.torq_qrrho.observe(update_preview, 'value')

        update_preview()
        self._check_dispersion_gate()

        self.btn_save_matrix = widgets.Button(
            description="Save configuration",
            button_style="success",
            icon="save",
            layout=widgets.Layout(width="auto", min_width="180px"),
        )
        self.matrix_output = widgets.Output()
        self.artifact_output_path = widgets.Text(description="Output Dir:", placeholder="e.g. D:\\MyProjects", layout=widgets.Layout(width='60%'))
        self.project_name = widgets.Text(description="Project Name:", placeholder="e.g. CCO", layout=widgets.Layout(width='30%'))
        self.project_name.observe(self._invalidate_actions_job, names='value')
        self.output_config_box = widgets.HBox([self.artifact_output_path, self.project_name], layout=widgets.Layout(margin='10px 0'))


        self.btn_save_matrix.on_click(self._save_matrix_config)

        self.tab_base = widgets.VBox([
            widgets.HBox([self.charge_input, self.multiplicity_input]),
            self.mlff_warning,
            self.tier_help,
            
            self.matrix_tier,
            self.matrix_method,
            self.matrix_basis,
            self.matrix_engine,
            self.cfour_operation,
            self.matrix_solvation,
            self.matrix_cbs_pair,
            self.unphysical_override,
            self.dispersion_warning,
            self.engine_warning,
            self.t9_panel,
        ])

        self.tab_topos = widgets.VBox([
            widgets.HTML("<b>TOPOS: Conformer Generation</b>"),
            widgets.HTML("<p>Search the Molecule Builder geometry with audited CREST or ORCA GOAT engines. "
                         "These are closed-shell conformer screening results; production accuracy requires subsequent electronic relaxation. "
                         "The CREST + GOAT union runs both engines when they are installed.</p>"),
            self.topos_capabilities,
            self.topos_heuristic,
            self.topos_walltime,
            widgets.HTML("<p>Deduplication uses the mandatory connectivity, RMSD and rotational-constant gates.</p>"),
            widgets.HBox([self.btn_topos_refresh, self.btn_topos_submit, self.btn_topos_cancel]),
            self.topos_status, self.btn_topos_promote, self.topos_results,
        ])

        self.tab_torq = widgets.VBox([
            widgets.HTML("<b>TORQ: Torsional Optimization</b>"),
            widgets.HTML("<p>CoChem-TORQ is a future module. Prepare validated input in Module handoff; torsional jobs are not submitted by this BASE panel.</p>"),
            self.torq_dihedrals,
            self.torq_resolution,
            self.torq_qrrho
        ])

        self.tab_fragments = widgets.VBox([
            widgets.HTML("<b>Method Matrix §9A Recipe R1/R2: Intermolecular Complex Constraints</b>"),
            self.btn_detect_fragments,
            self.fragments_output,
            self.cb_recipe_r1,
            self.cb_recipe_r2,
            self.scientific_r2_upload, self.scientific_initial_hessian, self.scientific_read_upload,
            self.scientific_input_status,
            widgets.HTML("<b>Generated Frozen Monomer Directives:</b>"),
            self.fragment_preview
        ])

        
        

        
        self.smiles_input = widgets.Text(description="Name or SMILES:", placeholder="e.g. ethanol or CCO",
            style={'description_width': 'initial'}, layout=widgets.Layout(width='95%'))
        self.btn_build_smiles = widgets.Button(description="Build starting geometry", button_style="info")
        self.xyz_upload = widgets.FileUpload(accept='.xyz', multiple=True, description="Upload .xyz")
        self.student_geometry_choice = widgets.Dropdown(options=[("Upload your starting geometry", "")],
            description="Starting geometry:", style={'description_width': 'initial'}, layout=widgets.Layout(width='95%'))
        self.student_input_role = widgets.Dropdown(options=[("Complex starting geometry", "complex"),
            ("Monomer A", "monomer_a"), ("Monomer B", "monomer_b"), ("Additional monomer", "monomer")],
            value="complex", description="Input type:", style={'description_width': 'initial'})
        self.student_input_label = widgets.Text(description="Geometry label:", placeholder="Your monomer or complex name",
            style={'description_width': 'initial'})
        self.student_fragment_atoms = widgets.Text(description="Fragment atom groups:",
            placeholder="Optional: 1,2,3;4,5,6 (one-based atom indices)", style={'description_width': 'initial'},
            layout=widgets.Layout(width='95%'))
        self.student_upload_status = widgets.HTML("<p role='status'>Upload the monomer or complex starting geometries you made in Avogadro 2. Coordinates must be in ångströms. Originals are preserved with SHA-256 hashes.</p>")
        self.btn_save_input_details = widgets.Button(description="Save geometry details")
        self.btn_save_input_details.on_click(self._save_student_input_details)
        self.student_geometry_choice.observe(self._select_student_geometry, names="value")
        self.student_monomer_choices = widgets.SelectMultiple(options=[], description="Your monomers:",
            style={'description_width': 'initial'}, layout=widgets.Layout(width='95%'))
        self.student_seed_separation = widgets.BoundedFloatText(value=5.0, min=2, max=100,
            description="Seed separation (Å):", style={'description_width': 'initial'})
        self.btn_assemble_monomers = widgets.Button(description="Prepare complex starting seed")
        self.btn_assemble_monomers.on_click(self._assemble_student_monomers)
        
        # 3D Viewer Output
        self.viewer_output = widgets.Output(layout=widgets.Layout(width='400px', height='300px', border='1px solid #ccc'))
        
        def _update_3d_viewer(*args):
            self.viewer_output.clear_output()
            xyz_data = self.matrix_geometry.value.strip()
            if not xyz_data:
                return
            with self.viewer_output:
                try:
                    import py3Dmol
                    from IPython.display import display

                    from cochem_base.geometry.nuclide_geometry import parse_geometry_identity
                    identity = parse_geometry_identity(xyz_data)
                    viewer_xyz = str(len(identity.elements)) + "\nBASE display geometry; nuclear labels retained in input\n" + "\n".join(
                        element + " " + " ".join(format(value, ".17g") for value in row)
                        for element, row in zip(identity.elements, identity.coordinates_angstrom, strict=True)) + "\n"
                    view = py3Dmol.view(width=400, height=300)
                    view.addModel(viewer_xyz, 'xyz')
                    view.setStyle({'stick': {}, 'sphere': {'radius': 0.4}})
                    view.zoomTo()
                    rendered = view.write_html()
                    # Uploading a new geometry can remove an earlier viewer
                    # while its library promise is pending. Never instantiate
                    # WebGL against a detached/missing DOM element.
                    guard = f'if (!document.getElementById("3dmolviewer_{view.uniqueid}")) {{ return; }}\n'
                    rendered = rendered.replace('$3Dmolpromise.then(function() {', '$3Dmolpromise.then(function() {\n' + guard, 1)
                    display({'application/3dmoljs_load.v0': rendered, 'text/html': rendered}, raw=True)
                except ImportError:
                    print("The 3D viewer is unavailable. Open CoChem setup and choose Retry setup.")
                except Exception as e:
                    print(f"Viewer Error: {e}")

        def _on_smiles_build(b):
            self._build_student_molecule()
                
        self.btn_build_smiles.on_click(_on_smiles_build)
        self.xyz_upload.observe(self._on_student_xyz_upload, names='value')
        
        # Add an observe to matrix_geometry so manual typing updates the 3D model
        self.matrix_geometry.observe(lambda c: _update_3d_viewer(), names='value')
        
        self.tab_builder = widgets.HBox([
            widgets.VBox([
                widgets.HTML("<b>Your starting geometries</b><p>Upload your own Avogadro 2 monomer or complex XYZ files. Supply charge, multiplicity and fragment membership; XYZ does not contain those reliably. Atom order and isotope labels are retained.</p>"),
                widgets.HBox([self.smiles_input, self.btn_build_smiles]),
                self.xyz_upload, self.student_geometry_choice, self.student_input_role, self.student_input_label,
                self.student_fragment_atoms, self.btn_save_input_details, self.student_upload_status,
                widgets.HTML("<details><summary>Starting from separate monomer XYZ files</summary><p>Save each monomer's charge and multiplicity, select its uploaded geometry below, and prepare a translated starting seed. This packing is an initial guess; TOPOS must calculate and search it before any binding or minimum claim.</p></details>"),
                self.student_monomer_choices, self.student_seed_separation, self.btn_assemble_monomers,
                widgets.HTML("<b>Manual Coordinate Editor (Build from scratch):</b>"),
                self.matrix_geometry
            ], layout=widgets.Layout(width='50%')),
            widgets.VBox([
                widgets.HTML("<b>Interactive 3D Viewer:</b>"),
                self.viewer_output
            ], layout=widgets.Layout(width='50%', padding='0 0 0 20px'))
        ])
        

        self.config_tabs = widgets.Tab(children=[self.tab_builder, self.tab_base, self.tab_topos, self.tab_torq, self.tab_fragments])
        self.config_tabs.set_title(0, 'Molecule Builder')
        self.config_tabs.set_title(1, 'Base Config')
        self.config_tabs.set_title(2, 'TOPOS')
        self.config_tabs.set_title(3, 'TORQ')
        self.config_tabs.set_title(4, 'Fragments / Frozen')
        

        self.output_destination_guidance = widgets.HTML()
        self.configuration_export = widgets.Accordion(children=[widgets.VBox([
            self.live_preview, self.btn_save_matrix, self.matrix_output, self.actions_job_download])])
        self.configuration_export.set_title(0, 'Optional reproducibility export')
        self.configuration_export.selected_index = None
        self.matrix_config_panel = widgets.VBox([
            widgets.HTML("<h4>Simulation Parameters</h4>"),
            self.calculation_environment_status,
            self.actions_job_options, self.native_job_options,
            self.config_tabs,
            self.output_destination_guidance,
            self.output_config_box,
            self.configuration_export,
        ], layout=widgets.Layout(border='1px solid #ccc', padding='10px', margin='10px 0'))

        # Task 3: Connected HPC / Slurm Panel
        self.scheduler_input = widgets.Dropdown(options=[("Detect configured scheduler", "auto"), ("Slurm", "slurm"), ("PBS", "pbs")], description="Scheduler:")
        self.partition_input = widgets.Text(description="Queue:", value="standard")
        self.nodes_input = widgets.IntText(description="Nodes:", value=1, disabled=True)
        self.tasks_per_node_input = widgets.IntText(description="Tasks/Node:", value=16)
        self.mem_input = widgets.Text(description="Memory:", value="32GB")
        self.walltime_input = widgets.Text(description="Walltime:", value="04:00:00")
        self.job_name_input = widgets.Text(description="Job Name:", value="cochem_job")
        self.email_input = widgets.Text(description="Email:", value="")
        self.btn_slurm_submit = widgets.Button(description="Submit Job", button_style="primary", icon="cloud-upload", disabled=True)
        self.slurm_submit_btn = self.btn_slurm_submit
        self.btn_slurm_submit.on_click(self._on_slurm_submit)
        self.slurm_status_output = widgets.HTML("<p>No scheduler calculation submitted.</p>")
        self.hpc_connection_status = widgets.HTML("<p role='status'>Select HPC to check the configured cluster connection.</p>")
        self.btn_hpc_connect = widgets.Button(description="Check HPC connection", disabled=self.calc_env_dropdown.value != "hpc")
        self.btn_hpc_connect.on_click(self._check_student_hpc_connection)
        self.scheduler_input.observe(lambda change: self._refresh_execution_gate(), names='value')
        self.btn_hpc_refresh = widgets.Button(description="Refresh HPC status", disabled=True)
        self.btn_hpc_refresh.on_click(self._refresh_student_hpc)
        self.btn_hpc_retrieve = widgets.Button(description="Retrieve HPC results", disabled=True)
        self.btn_hpc_retrieve.on_click(self._retrieve_student_hpc)
        self.btn_hpc_cancel = widgets.Button(description="Cancel HPC job", disabled=True)
        self.btn_hpc_cancel.on_click(self._cancel_student_hpc)
        self.hpc_results_download = widgets.HTML()
        self.hpc_history = widgets.Dropdown(options=[("No retained scheduler jobs", "")], description="HPC history:", style={"description_width": "initial"})
        self.btn_hpc_open = widgets.Button(description="Open retained HPC job", disabled=True)
        self.btn_hpc_open.on_click(self._open_student_hpc_history)

        self.slurm_panel = widgets.VBox([
            widgets.HTML("<h4>HPC scheduler submission</h4>"),
            widgets.HTML("<p>HPC calculations enter a real Slurm or PBS queue and run in its compute allocation. Configure the cluster queue and single-node resource request. The interface host does not execute these calculations.</p>"),
            self.btn_hpc_connect, self.hpc_connection_status,
            self.scheduler_input,
            widgets.HBox([self.partition_input, self.job_name_input]),
            widgets.HBox([self.nodes_input, self.tasks_per_node_input]),
            widgets.HBox([self.mem_input, self.walltime_input]),
            self.email_input,
            self.btn_slurm_submit,
            self.slurm_status_output,
            self.hpc_history, self.btn_hpc_open,
            widgets.HBox([self.btn_hpc_refresh, self.btn_hpc_retrieve, self.btn_hpc_cancel]),
            self.hpc_results_download
        ], layout=widgets.Layout(border='1px solid #ccc', padding='10px', margin='10px 0'))

        # Hide SLURM panel if not HPC
        if self.calc_env_dropdown.value != "hpc":
            self.slurm_panel.layout.display = 'none'

        self.btn_execute = widgets.Button(
            description="Run ORCA optimization",
            button_style="danger",
            icon="rocket",
            layout=widgets.Layout(width="auto", min_width="190px"),
        )
        self.btn_execute.on_click(self._execute_pipeline)
        self.btn_cancel = widgets.Button(description="Cancel calculation", icon="stop", disabled=True, layout=widgets.Layout(width="auto", min_width="180px"))
        self.btn_cancel.on_click(self._cancel_pipeline)
        self.telemetry_output = BoundedTelemetryOutput(layout=widgets.Layout(border='1px solid #ccc', height='400px', overflow='auto', padding='5px'))
        self.calculation_result = widgets.HTML("<i>No accepted calculation result yet.</i>")
        self.execution_description = widgets.HTML()
        self.actions_status = widgets.HTML("<p role='status'>No remote calculation submitted.</p>")
        self.btn_actions_refresh = widgets.Button(description="Refresh calculation status", disabled=True)
        self.btn_actions_refresh.on_click(self._refresh_student_actions)
        self.btn_actions_retrieve = widgets.Button(description="Retrieve and inspect results", disabled=True)
        self.btn_actions_retrieve.on_click(self._retrieve_student_actions)
        self.actions_results_download = widgets.HTML()
        self.actions_calculated_geometry = widgets.Dropdown(options=[("No retained calculated geometry", "")],
            description="Calculated geometry:", style={'description_width': 'initial'}, layout=widgets.Layout(width='95%'))
        self.btn_actions_use_geometry = widgets.Button(description="Use calculated structure", disabled=True)
        self.btn_actions_use_geometry.on_click(self._use_student_calculated_geometry)
        self.actions_history = widgets.Dropdown(options=[("No retained calculations", "")],
            description="Previous calculations:", style={'description_width': 'initial'}, layout=widgets.Layout(width='90%'))
        self.btn_actions_open = widgets.Button(description="Open selected calculation", disabled=True)
        self.btn_actions_open.on_click(self._open_student_actions_history)
        self.actions_controls = widgets.VBox([self.actions_status,
            self.actions_history, self.btn_actions_open,
            widgets.HBox([self.btn_actions_refresh, self.btn_actions_retrieve]), self.actions_results_download],
            layout=widgets.Layout(display='none'))
        self.actions_controls.children += (self.actions_calculated_geometry, self.btn_actions_use_geometry)

        self.telemetry_panel = widgets.VBox([
            widgets.HTML("<h4>Live Telemetry & Execution</h4>"),
            self.execution_description,
            widgets.HBox([self.btn_execute, self.btn_cancel]),
            self.actions_controls,
            self.calculation_result,
            self.telemetry_output
        ], layout=widgets.Layout(border='1px solid #ccc', padding='10px', margin='10px 0'))

        self.view_matrix = widgets.VBox([
            widgets.HTML("<h3>No Code Matrix Configuration</h3>"),
            widgets.HTML("<p>Interface for configuring and launching physical simulations mapped to the Method Matrix [M].</p>"),
            self.product_class_card,
            self.product_class_selector,
            self.matrix_config_panel,
            self.slurm_panel,
            self.telemetry_panel
        ], layout=widgets.Layout(padding='20px'))

        # 3.3 Authentic Data Inspector View
        self.inspector_file_input = widgets.Text(
            description="Log / H5 File:",
            placeholder="e.g. tests/data/cfour.log or calc.property.txt",
            layout=widgets.Layout(width='70%'),
            style={'description_width': 'initial'}
        )
        self.btn_parse_inspector = widgets.Button(
            description="Parse Observables",
            button_style="info",
            icon="binoculars"
        )
        self.btn_parse_inspector.on_click(self._on_parse_inspector_clicked)

        self.inspector_banner = widgets.HTML(
            "<div style='background-color:#d1ecf1; color:#0c5460; padding:8px; border-radius:4px; margin-bottom:8px;'>"
            "<b>Method Matrix §3.0:</b> Equilibrium $B_e$ is purely theoretical at the PES minimum; "
            "effective ground-state $B_0$ is the actual observable measured in rotational spectroscopy."
            "</div>"
        )
        self.inspector_rot_table = widgets.HTML("<i>No output parsed yet. Provide file path and click 'Parse Observables'.</i>")

        # Isotope Re-analysis panel
        self._isotope_hessian_data = None
        self._calculation_hessians: dict[str, dict[str, Any]] = {}
        self.calculation_hessian_choice = widgets.Dropdown(options=[("No calculation Hessian selected", "")],
            description="Calculation Hessian:", style={"description_width": "initial"}, layout=widgets.Layout(width="95%"))
        self.calculation_hessian_choice.observe(self._select_calculation_hessian, names="value")
        self.isotope_selectors = []
        self.isotope_elements_box = widgets.VBox()
        self.isotope_hessian_path = widgets.Text(
            description="Hessian bundle:", placeholder="ORCA .hess or geometry-bound .npz/.h5",
            style={'description_width': 'initial'}, layout=widgets.Layout(width='95%'),
        )
        self.btn_load_hessian = widgets.Button(description="Load geometry and Hessian", icon="folder-open")
        self.btn_load_hessian.on_click(self._on_load_hessian_clicked)
        self.btn_clear_hessian = widgets.Button(description="Clear Hessian", icon="times")
        self.btn_clear_hessian.on_click(self._on_clear_hessian_clicked)
        self.isotope_hessian_status = widgets.HTML("<p>[MISSING DATA] No Cartesian Hessian loaded.</p>")
        self.matrix_geometry.observe(self._update_isotope_selectors, names="value")
        self._update_isotope_selectors()
        self.btn_run_isotope_reanalysis = widgets.Button(
            description="Re-analyze Isotopologue",
            button_style="success",
            icon="refresh"
        )
        self.btn_run_isotope_reanalysis.on_click(self._on_run_isotope_reanalysis_clicked)
        self.isotope_results_table = widgets.HTML("<i>Provide geometry and select an isotope for each atom.</i>")
        self.isotope_modes_plot = widgets.HTML()

        # HDF5 SWMR Store panel
        self.btn_read_hdf5 = widgets.Button(description="Inspect HDF5 / NPZ data", button_style="warning", icon="database")
        self._managed_physical_data: dict[str, Any] | None = None
        self.btn_read_hdf5.on_click(self._on_read_hdf5_clicked)
        self.hdf5_results_table = widgets.HTML("<i>Select a retained HDF5 or NPZ file to preview up to 100 datasets and 500 values per dataset. HDF5 uses SWMR and the shared file lock; NPZ object arrays are rejected.</i>")

        self.inspector_tabs = widgets.Tab(children=[
            widgets.VBox([self.inspector_banner, self.inspector_rot_table]),
            widgets.VBox([
                widgets.HTML("<b>Isotopic Substitution (Mendeleev masses)</b>"),
                self.isotope_hessian_path, self.calculation_hessian_choice,
                widgets.HBox([self.btn_load_hessian, self.btn_clear_hessian]),
                self.isotope_hessian_status,
                self.isotope_elements_box,
                self.btn_run_isotope_reanalysis,
                self.isotope_results_table,
                self.isotope_modes_plot,
            ]),
            widgets.VBox([
                widgets.HTML("<b>SWMR HDF5 Concurrency Telemetry Store</b>"),
                self.btn_read_hdf5,
                self.hdf5_results_table
            ])
        ])
        self.inspector_tabs.set_title(0, "Rotational Observables (B_e vs B_0)")
        self.inspector_tabs.set_title(1, "Isotopic Re-analysis")
        self.inspector_tabs.set_title(2, "HDF5 SWMR Store")

        self.data_inspector_widget = DataInspectorWidget([
            widgets.HTML("<h3>Data Inspector (Ab-Initio Spectroscopic Observables)</h3>"),
            widgets.HTML("<p>Rigorous extraction of rotational constants, vibrational corrections, dipole moments, and dynamic isotopic shifts.</p>"),
            widgets.HBox([self.inspector_file_input, self.btn_parse_inspector]),
            self.inspector_tabs
        ], layout=widgets.Layout(padding='20px'))
        self.view_inspector = self.data_inspector_widget

        from cochem_base.config_loader import get_artifact_dir
        from cochem_base.interfaces.module_registry import list_module_capabilities
        self.module_capabilities = widgets.HTML()
        self.module_recipient = widgets.Dropdown(
            options=[(item.name, item.module_id) for item in list_module_capabilities()],
            value="topos", description="Recipient module:", style={'description_width': 'initial'},
        )
        self.module_artifact = widgets.Text(description="Input artifact:", layout=widgets.Layout(width='90%'))
        self.module_operation = widgets.Text(description="Requested task:", value="geometry_analysis",
                                             style={'description_width': 'initial'})
        self.module_output = widgets.Text(description="Package directory:",
            value=str(get_artifact_dir() / "Handoffs"), style={'description_width': 'initial'},
            layout=widgets.Layout(width='90%'))
        self.btn_module_handoff = widgets.Button(description="Prepare validated handoff", button_style="primary",
                                                 layout=widgets.Layout(width='auto'))
        self.btn_module_handoff.on_click(self._prepare_module_handoff)
        self.btn_module_refresh = widgets.Button(description="Refresh module availability", layout=widgets.Layout(width='auto'))
        self.btn_module_refresh.on_click(self._refresh_module_capabilities)
        self.module_handoff_status = widgets.HTML("<p role='status'>No handoff prepared.</p>")
        self.module_root = widgets.Text(description="Module storage:", value=str(get_artifact_dir() / "Modules"),
                                        style={'description_width': 'initial'}, layout=widgets.Layout(width='90%'))
        self.btn_module_install = widgets.Button(description="Install selected recipient", layout=widgets.Layout(width='auto'))
        self.btn_module_install.on_click(self._install_selected_module)
        self.btn_module_run = widgets.Button(description="Run geometry analysis", layout=widgets.Layout(width='auto'))
        self.btn_module_run.on_click(self._run_module_geometry)
        self.module_install_status = widgets.HTML("<p role='status'>Select a module to install or inspect.</p>")
        self.view_modules = widgets.VBox([
            widgets.HTML("<h3>Module installation and execution</h3><p>Install approved modules in separate environments. TOPOS and TORQ expose geometry analysis; other operations require a reviewed adapter. Installation does not certify scientific accuracy.</p>"),
            self.btn_module_refresh, self.module_capabilities,
            widgets.HTML("<p>Select a single XYZ geometry, geometry-bound Hessian (.npz/.h5/.hess), or converged result JSON. The package preserves its source and verifies its contents when loaded by a recipient.</p>"),
            self.module_recipient, self.module_root, self.btn_module_install, self.module_install_status,
            self.module_artifact, self.module_operation,
            self.module_output, self.btn_module_handoff, self.module_handoff_status,
            self.btn_module_run,
        ], layout=widgets.Layout(padding='20px'))
        self._refresh_module_capabilities()
        self._build_student_research_panels()

        self.periodic_input_path = widgets.Text(description="Periodic input:", layout=widgets.Layout(width='90%'))
        self.periodic_settings_path = widgets.Text(description="PAW settings JSON:", style={'description_width': 'initial'},
                                                  layout=widgets.Layout(width='90%'))
        self.periodic_output_path = widgets.Text(description="Periodic output:", value=str(get_artifact_dir() / "Periodic"),
                                                style={'description_width': 'initial'}, layout=widgets.Layout(width='90%'))
        self.btn_periodic_inspect = widgets.Button(description="Validate periodic structure", button_style="primary",
                                                   layout=widgets.Layout(width='auto'))
        self.btn_periodic_inspect.on_click(self._inspect_periodic_input)
        self.btn_periodic_save = widgets.Button(description="Save periodic calculation request", layout=widgets.Layout(width='auto'))
        self.btn_periodic_save.on_click(self._save_periodic_config)
        self.btn_periodic_run = widgets.Button(description="Run periodic PBE/PAW single point", button_style="danger",
                                               layout=widgets.Layout(width='auto'))
        self.btn_periodic_run.on_click(self._execute_periodic_pipeline)
        self.btn_periodic_cancel = widgets.Button(description="Cancel periodic calculation", disabled=True,
                                                  layout=widgets.Layout(width='auto'))
        self.btn_periodic_cancel.on_click(self._cancel_pipeline)
        self.periodic_structure_status = widgets.HTML("<p role='status'>No periodic structure loaded.</p>")
        self.view_periodic = widgets.VBox([
            widgets.HTML("<h3>Product B periodic structure ingestion</h3><p>Load an ordered bulk CIF or explicitly unit-labelled periodic JSON. Cell vectors, fractional coordinates and source hashes are preserved. Disordered or partially occupied structures require resolved input.</p>"),
            self.periodic_input_path, self.btn_periodic_inspect, self.periodic_structure_status,
            widgets.HTML("<p>Native Quantum ESPRESSO execution requires supplied PBE PAW pseudopotential paths and SHA-256 values in the settings JSON, plus explicit numerical settings. SCF convergence does not certify empirical band-gap or lattice accuracy.</p>"),
            self.periodic_settings_path, self.periodic_output_path,
            widgets.HBox([self.btn_periodic_save, self.btn_periodic_run, self.btn_periodic_cancel]),
            self.calculation_result, self.telemetry_output,
        ], layout=widgets.Layout(padding='20px'))
        self._build_input_library_panel()
        self.view_periodic.children += (self.slurm_panel,)

        self.main_content = widgets.VBox(
            [self.view_install], # Default view
            layout=widgets.Layout(flex='1')
        )

        # 4. Footer (Error & Notification System)
        self.footer_message = widgets.HTML("")
        self.telemetry_html = widgets.HTML("")
        self.telemetry_accordion = widgets.Accordion(children=[self.telemetry_html])
        self.telemetry_accordion.set_title(0, "Diagnostic Telemetry")
        self.telemetry_accordion.layout.display = 'none'

        self.footer = widgets.VBox(
            [self.footer_message, self.telemetry_accordion],
            layout=widgets.Layout(
                padding='10px',
                border='1px solid #ccc',
                min_height='60px',
            )
        )


        # Set initial footer message if error exists
        if self.state.error_message:
            self._update_footer(self.state.error_message)

        # 5. AppLayout Assembly
        self.app = widgets.AppLayout(
            header=self.header,
            left_sidebar=self.sidebar,
            center=self.main_content,
            right_sidebar=None,
            footer=self.footer,
            pane_widths=['250px', 1, 0],
            pane_heights=['80px', 1, '80px']
        )

        # Icon font pseudo-elements enter some browsers' accessible names.
        # Every control already has a text label, so keep the spoken name exact.
        pending = [self.app, self.view_matrix, self.view_inspector, self.view_modules, self.view_periodic, self.view_inputs]
        while pending:
            control = pending.pop()
            if isinstance(control, widgets.Button):
                control.icon = ""
            pending.extend(getattr(control, "children", ()))

        # Bind traitlets observers
        self.state.observe(self._on_view_change, names='active_view')
        self.state.observe(self._on_status_change, names='system_status')
        self.state.observe(self._on_error_change, names='error_message')
        self.state.observe(self._on_environment_change, names='environment')
        self._refresh_actions_guidance()
        self._check_dispersion_gate()
        self._start_student_hpc_history()
        self._start_student_setup()
        self._refresh_student_actions_history()
        self._restore_student_inputs()
        self._restore_student_scientific_inputs()
        self._refresh_input_library()
        self._start_course_project_discovery()
        atexit.register(self._inbox_stop.set)
        atexit.register(self._hpc_monitor_stop.set)
        if self.calc_env_dropdown.value == "github-actions" and self._automatic_remote_checks_enabled():
            self._check_remote_engines()

    def _ui_call(self, callback: Any) -> None:
        """Publish background progress on the live notebook event loop."""
        try:
            from IPython import get_ipython
            kernel = getattr(get_ipython(), "kernel", None)
            loop = getattr(kernel, "io_loop", None)
            if loop is not None and threading.current_thread() is not threading.main_thread():
                loop.add_callback(callback)
                return
        except ImportError:
            callback()
            return
        callback()

    def _start_course_project_discovery(self) -> None:
        """Resolve the original project off the UI thread when no launcher context exists."""
        if self.gh_repo_input.value.strip():
            return
        def discover() -> None:
            import subprocess
            try:
                from scripts.hosted_dashboard import assignment_identity
                source = Path(os.environ.get("COCHEM_ASSIGNMENT_ROOT", str(_REPO_ROOT)))
                identity = assignment_identity(source)
            except (ImportError, ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
                message = str(exc)
                self._ui_call(lambda: setattr(self.course_access_panel.status, 'value',
                    "<p role='status'>Project discovery could not complete: " + html.escape(message)
                    + ". Confirm the project repository above before enrollment.</p>"))
                return
            def publish() -> None:
                if not self.gh_repo_input.value.strip() and identity.get("GITHUB_REPOSITORY"):
                    self.gh_branch_input.value = identity.get("GITHUB_REF_NAME", "main")
                    self.gh_repo_input.value = identity["GITHUB_REPOSITORY"]
            self._ui_call(publish)
        self._course_discovery_worker = threading.Thread(target=discover, daemon=True)
        self._course_discovery_worker.start()

    def _refresh_lab_access(self, b: Any = None) -> None:
        if self.calc_env_dropdown.value != "github-actions":
            self.course_access_panel.status.value = (
                "<p role='status'>Lab enrollment does not alter local or HPC installations. "
                "Select GitHub Actions as the Calculation Environment to check this project's hosted engine access.</p>")
            return
        self._check_remote_engines()

    def _build_input_library_panel(self) -> None:
        """Expose canonical readers through uploads and verified retained selections."""
        self.input_kind = widgets.Dropdown(options=[("Detect from file", "auto"),
            ("Molecular coordinates / multi-frame ensemble", "molecular"),
            ("CREST / ORCA GOAT conformer pool", "conformer_pool"),
            ("Periodic structure", "periodic"), ("Geometry-bound Hessian", "hessian"),
            ("Native spectroscopy output", "spectroscopy"), ("Measured HDF5 trajectories", "telemetry"),
            ("Physical HDF5 / NPZ data", "physical_data"),
            ("Native calculation result", "native_result"), ("PAW pseudopotential", "pseudopotential")],
            description="Scientific input type:", style={'description_width': 'initial'})
        self.input_upload = widgets.FileUpload(
            accept='.xyz,.mol,.sdf,.mol2,.pdb,.json,.cif,.hess,.h5,.hdf5,.npz,.out,.log,.txt,.upf',
            multiple=True, description="Upload scientific inputs")
        self.input_pool_producer = widgets.Dropdown(options=[('Explicit energy labels and units', 'declared'),
            ('Native CREST ensemble', 'crest'), ('Native ORCA GOAT ensemble', 'orca_goat')],
            description='Pool producer:', style={'description_width': 'initial'})
        self.input_pool_energy_unit = widgets.Dropdown(options=[('Hartree', 'hartree'), ('kcal/mol', 'kcal/mol')],
            description='Recorded energy unit:', style={'description_width': 'initial'})
        self.input_pool_producer.layout.display = self.input_pool_energy_unit.layout.display = 'none'
        self.input_kind.observe(lambda change: self._show_pool_import_controls(change['new']), names='value')
        self.input_library_status = widgets.HTML("<p role='status'>Upload your molecular structures, native outputs, conformer ensembles or physical data. BASE validates the complete file before adding it; original bytes and hashes are retained outside the application.</p>")
        self.input_library_table = widgets.HTML()
        self.input_library_choice = widgets.Dropdown(options=[("Upload a scientific input", "")],
            description="Retained input:", style={'description_width': 'initial'}, layout=widgets.Layout(width='95%'))
        self.input_library_choice.observe(self._select_library_input, names="value")
        self.input_record_choice = widgets.Dropdown(options=[], description="Structure / frame:",
            style={'description_width': 'initial'}, layout=widgets.Layout(width='95%'))
        self.btn_use_input_geometry = widgets.Button(description="Use selected starting geometry", disabled=True)
        self.btn_use_input_geometry.on_click(self._use_library_geometry)
        self.input_upload.observe(lambda change: self._upload_input_files(self.input_upload, self.input_kind.value), names="value")
        self.btn_input_refresh = widgets.Button(description="Refresh retained inputs")
        self.btn_input_refresh.on_click(self._refresh_input_library)
        self.btn_inbox_scan = widgets.Button(description="Import files from VS Code inbox")
        self.btn_inbox_watch = widgets.Button(description="Watch VS Code inbox")
        self.btn_inbox_stop = widgets.Button(description="Stop watching inbox", disabled=True)
        self.btn_inbox_scan.on_click(self._scan_input_inbox)
        self.btn_inbox_watch.on_click(self._watch_input_inbox)
        self.btn_inbox_stop.on_click(self._stop_input_inbox)
        self.input_pool_choices = widgets.SelectMultiple(options=[], description="Conformer pools:",
            style={'description_width': 'initial'}, layout=widgets.Layout(width='95%'))
        self.input_pool_declare_context = widgets.Checkbox(value=False, description='Declare common state and protocol for energy ranking')
        self.input_pool_charge = widgets.IntText(value=0, description='Pool charge:')
        self.input_pool_multiplicity = widgets.BoundedIntText(value=1, min=1, max=100, description='Pool multiplicity:', style={'description_width': 'initial'})
        self.input_pool_engine = widgets.Dropdown(options=['xTB', 'ORCA', 'CFOUR', 'PySCF'], description='Recorded engine:')
        self.input_pool_method = widgets.Text(description='Recorded method:', placeholder='Exact method used for every selected frame', style={'description_width': 'initial'})
        self.input_pool_basis = widgets.Text(description='Recorded basis:', placeholder='Blank only for a parameterized model without a basis', style={'description_width': 'initial'})
        self.input_pool_version = widgets.Text(description='Engine / model version:', placeholder='Exact common engine/model version', style={'description_width': 'initial'})
        self.input_pool_context_box = widgets.VBox([self.input_pool_charge, self.input_pool_multiplicity,
            self.input_pool_engine, self.input_pool_method, self.input_pool_basis, self.input_pool_version], layout=widgets.Layout(display='none'))
        self.input_pool_declare_context.observe(lambda change: setattr(self.input_pool_context_box.layout, 'display', '' if change['new'] else 'none'), names='value')
        self.btn_sieve_inputs = widgets.Button(description="Merge and sieve native conformer pools")
        self.btn_sieve_inputs.on_click(self._sieve_input_pools)
        self.input_unique_conformer = widgets.Dropdown(options=[], description='Retained conformer:',
            style={'description_width': 'initial'}, layout=widgets.Layout(width='95%'))
        self.btn_use_unique_conformer = widgets.Button(description='Use retained conformer geometry', disabled=True)
        self.btn_use_unique_conformer.on_click(self._use_unique_conformer)
        self.input_pool_status = widgets.HTML("<p>Native CREST/GOAT energies must be explicitly recorded in Hartree in every frame. Coordinate-only ensembles remain starting geometries; they do not establish minima or equilibrium populations.</p>")
        self.view_inputs = widgets.VBox([
            widgets.HTML("<h3>Scientific input library</h3><p>Import XYZ, MOL V2000/V3000, multi-record SDF, MOL2, PDB and QCSchema structures; periodic CIF; geometry-bound Hessians; native spectroscopy outputs; and HDF5/NPZ data. Atom order, isotope identities, source units and encoded electronic states are retained by the canonical readers.</p>"),
            self.input_kind, self.input_pool_producer, self.input_pool_energy_unit,
            self.input_upload, self.input_library_status, self.btn_input_refresh,
            self.input_library_choice, self.input_record_choice, self.btn_use_input_geometry,
            self.input_library_table,
            widgets.HTML("<p>For an existing file in VS Code, drag it into the course inbox shown in the workspace. Import or watch that inbox here; no terminal command is needed.</p>"),
            widgets.HBox([self.btn_inbox_scan, self.btn_inbox_watch, self.btn_inbox_stop]),
            self.input_pool_choices, self.input_pool_declare_context, self.input_pool_context_box,
            self.btn_sieve_inputs, self.input_pool_status,
            self.input_unique_conformer, self.btn_use_unique_conformer,
        ], layout=widgets.Layout(padding='20px'))
        self._input_selectors = {}
        for key, description, kind, suffixes in (
            ('install', 'Scientific bundle:', 'hessian', '.npz,.h5,.hdf5'),
            ('hessian', 'Retained Hessian:', 'hessian', '.hess,.npz,.h5,.hdf5'),
            ('telemetry', 'Native output:', 'spectroscopy', '.out,.log,.txt'),
            ('physical_data', 'Physical data:', 'physical_data', '.h5,.hdf5,.npz'),
            ('periodic', 'Periodic structure:', 'periodic', '.cif,.json'),
            ('module', 'Validated module input:', 'auto', '.xyz,.hess,.npz,.h5,.hdf5,.json'),
        ):
            chooser = widgets.Dropdown(options=[("Upload or choose a retained input", "")],
                description=description, style={'description_width': 'initial'}, layout=widgets.Layout(width='95%'))
            uploader = widgets.FileUpload(accept=suffixes, multiple=False, description="Upload " + key.replace('_', ' '))
            uploader.observe(lambda change, control=uploader, category=kind: self._upload_input_files(control, category), names='value')
            chooser.observe(lambda change, category=key: self._bind_library_path(category, change['new']), names='value')
            self._input_selectors[key] = chooser
            setattr(self, f'{key}_input_upload', uploader)
        # Paths remain private bindings for the native APIs. The student chooses files.
        self.local_install_options.children = tuple(self._input_selectors['install'] if child is self.install_data_path else child
            for child in self.local_install_options.children)
        self.local_install_options.children = (self.install_input_upload, *self.local_install_options.children)
        isotope_panel = self.inspector_tabs.children[1]
        isotope_panel.children = tuple(self._input_selectors['hessian'] if child is self.isotope_hessian_path else child
            for child in isotope_panel.children)
        isotope_panel.children = (self.hessian_input_upload, *isotope_panel.children)
        physical_panel = self.inspector_tabs.children[2]
        physical_panel.children = (self.physical_data_input_upload, self._input_selectors['physical_data'], *physical_panel.children)
        self.inspector_rot_table.value = "<i>Upload or select a native calculation output, then choose Parse Observables.</i>"
        self.data_inspector_widget.children = (self.data_inspector_widget.children[0], self.data_inspector_widget.children[1],
            self.telemetry_input_upload, self._input_selectors['telemetry'], self.btn_parse_inspector, self.inspector_tabs)
        advanced = self.view_modules.children[-1].children[0]
        advanced.children = tuple(self._input_selectors['module'] if child is self.module_artifact else child
            for child in advanced.children if child not in (self.module_root, self.module_output, self.module_operation))
        advanced.children = (self.module_input_upload, *advanced.children)
        self.artifact_output_path.layout.display = 'none'
        self._build_periodic_input_controls()

    def _bind_library_path(self, kind: str, input_id: str) -> None:
        record = self._input_library.get(input_id)
        if not record:
            return
        if kind == "hessian" and self.calculation_hessian_choice.value:
            self.calculation_hessian_choice.value = ""
        if kind == 'physical_data':
            self._managed_physical_data = None
        field = {'install': self.install_data_path, 'hessian': self.isotope_hessian_path,
            'telemetry': self.inspector_file_input, 'physical_data': self.inspector_file_input,
            'periodic': self.periodic_input_path, 'module': self.module_artifact}[kind]
        field.value = str(record['path'])
        if kind == 'periodic':
            self._inspect_periodic_input()
            self._refresh_paw_species()

    def _show_pool_import_controls(self, kind: str) -> None:
        visible = '' if kind == 'conformer_pool' else 'none'
        self.input_pool_producer.layout.display = visible
        self.input_pool_energy_unit.layout.display = visible

    def _upload_input_files(self, control: Any, kind: str = 'auto') -> None:
        if self._ingestion_busy or not control.value:
            return
        values = list(control.value.values()) if isinstance(control.value, dict) else list(control.value)
        pool_options = {'producer': self.input_pool_producer.value, 'energy_unit': self.input_pool_energy_unit.value} if kind == 'conformer_pool' else {}
        self._ingestion_busy = True
        control.disabled = True
        self.input_library_status.value = "<p role='status'>Validating complete uploaded scientific inputs…</p>"
        def ingest() -> None:
            from cochem_base.config_loader import get_artifact_dir
            accepted, errors = [], []
            try:
                from cochem_base.interfaces.student_ingestion import ingest_uploaded_file
                for entry in values:
                    try:
                        name = entry.get('name') or entry.get('metadata', {}).get('name')
                        receipt = ingest_uploaded_file(name, bytes(entry['content']), artifact_dir=get_artifact_dir(), kind=kind, **pool_options)
                        accepted.append(receipt)
                    except (ValueError, RuntimeError, OSError, KeyError, TypeError, UnicodeError) as exc:
                        errors.append(str(entry.get('name', 'Input')) + ': ' + str(exc))
            except ImportError as exc:
                errors.append(str(exc))
            try:
                snapshot = self._read_input_library()
            except (ImportError, ValueError, RuntimeError, OSError) as exc:
                snapshot = {'inputs': accepted, 'rejections': []}
                errors.append('Retained library refresh: ' + str(exc))
            def finish() -> None:
                self._ingestion_busy = False
                control.disabled = False
                self._input_library_refresh_serial += 1
                self._apply_input_library(snapshot)
                self.input_library_status.value = (f"<p role='status'>Validated and retained {len(accepted)} input(s).</p>" +
                    ("<p role='alert'>Rejected inputs: " + '<br/>'.join(html.escape(item) for item in errors) + '</p>' if errors else ''))
                for receipt in accepted:
                    input_id = receipt.get('input_id', receipt.get('id'))
                    if input_id in self._input_library:
                        self.input_library_choice.value = input_id
                        for key, selector in self._input_selectors.items():
                            if input_id in [value for _, value in selector.options]:
                                selector.value = input_id
                if hasattr(self, '_paw_pseudopotential_choices'):
                    self._refresh_paw_species()
            self._ui_call(finish)
        self._ingestion_worker = threading.Thread(target=ingest, daemon=True)
        self._ingestion_worker.start()

    def _refresh_input_library(self, b: Any = None) -> None:
        self._input_library_refresh_serial += 1
        serial = self._input_library_refresh_serial
        self.btn_input_refresh.disabled = True
        def refresh() -> None:
            try:
                snapshot = self._read_input_library()
                self._ui_call(lambda: self._apply_input_library(snapshot) if serial == self._input_library_refresh_serial else None)
            except (ImportError, ValueError, RuntimeError, OSError) as exc:
                message = str(exc)
                self._ui_call(lambda: setattr(self.input_library_status, 'value',
                    f"<p role='alert'>Input library could not be loaded: {html.escape(message)}</p>") if serial == self._input_library_refresh_serial else None)
            finally:
                self._ui_call(lambda: setattr(self.btn_input_refresh, 'disabled', False) if serial == self._input_library_refresh_serial else None)
        self._input_library_worker = threading.Thread(target=refresh, daemon=True)
        self._input_library_worker.start()

    @staticmethod
    def _read_input_library() -> dict[str, Any]:
        from cochem_base.config_loader import get_artifact_dir
        from cochem_base.interfaces.student_ingestion import scan_ingested_inputs
        return scan_ingested_inputs(get_artifact_dir())

    def _apply_input_library(self, snapshot: dict[str, Any]) -> None:
        self._input_library = {item['input_id']: item for item in snapshot['inputs']}
        self.btn_input_refresh.disabled = False
        choices = [(str(item['filename']) + ' (' + item['kind'].replace('_', ' ') + ')', key)
                   for key, item in self._input_library.items()]
        selected = self.input_library_choice.value
        self.input_library_choice.options = choices or [("Upload a scientific input", "")]
        if selected in self._input_library:
            self.input_library_choice.value = selected
        for kind, selector in self._input_selectors.items():
            selected = selector.value
            allowed = {'install': {'hessian'}, 'hessian': {'hessian'}, 'telemetry': {'spectroscopy'},
                'physical_data': {'physical_data', 'hessian', 'telemetry'}, 'periodic': {'periodic'},
                'module': {'molecular', 'hessian', 'native_result'}}[kind]
            items = [(item['filename'], key) for key, item in self._input_library.items() if item['kind'] in allowed
                     and (kind != 'install' or Path(item['path']).suffix.lower() in {'.h5', '.hdf5', '.npz'})
                     and (kind != 'physical_data' or Path(item['path']).suffix.lower() in {'.h5', '.hdf5', '.npz'})
                     and (kind != 'module' or item['kind'] != 'molecular'
                          or Path(item['path']).suffix.lower() == '.xyz' and len(item.get('records', [])) == 1)]
            selector.options = ([("Choose uploaded data or inspect the retained calculation result", "")] + items
                                if kind == 'physical_data' else items or [("Upload or choose a retained input", "")])
            if selected in [value for _, value in items]:
                selector.value = selected
        self.input_pool_choices.options = [(item['filename'], key) for key, item in self._input_library.items()
                                          if item['kind'] in {'conformer_pool', 'molecular'}]
        rows = ''.join('<tr>' + ''.join('<td>' + html.escape(str(value)) + '</td>' for value in
            (item['filename'], item['kind'], len(item.get('records', [])), item['sha256'])) + '</tr>'
            for item in self._input_library.values())
        self.input_library_table.value = '<table><caption>Verified retained scientific inputs</caption><thead><tr><th>File</th><th>Type</th><th>Structures</th><th>Original SHA-256</th></tr></thead><tbody>' + rows + '</tbody></table>'
        self._input_library_rejections = snapshot.get('rejections', [])
        if self._input_library_rejections:
            self.input_library_table.value += '<p role="alert">Rejected retained inputs; original files remain preserved: ' + '<br/>'.join(
                html.escape(item['input_id'] + ': ' + item['reason']) for item in self._input_library_rejections) + '</p>'
        self._refresh_paw_species()

    def _select_library_input(self, change: Any) -> None:
        receipt = self._input_library.get(change['new'], {})
        records = receipt.get('records', [])
        self.input_record_choice.options = [(f"{receipt.get('filename', 'Input')} — frame {index + 1}", index)
            for index in range(len(records))]
        if records:
            self.input_record_choice.value = 0
        self.btn_use_input_geometry.disabled = not records

    def _use_library_geometry(self, b: Any = None) -> None:
        """Use a canonical parsed frame without modifying its uploaded source."""
        from cochem_base.config_loader import get_artifact_dir
        from cochem_base.geometry.nuclide_geometry import parse_geometry_identity
        try:
            receipt = self._input_library[self.input_library_choice.value]
            original = Path(receipt['path']).read_bytes()
            if hashlib.sha256(original).hexdigest() != receipt['sha256']:
                raise ValueError('Retained original SHA-256 no longer matches')
            frame_index = self.input_record_choice.value
            frame = receipt['records'][frame_index]
            if frame.get('requires_counterpoise_adapter') or frame.get('ghost_atom_indices'):
                raise ValueError('Ghost centers are retained for a counterpoise-capable adapter. They cannot be used as physical atoms by this starting-geometry calculation route.')
            symbols = frame.get('nuclides') or frame.get('symbols')
            coordinates = frame.get('coordinates_angstrom', frame.get('coords'))
            xyz = str(len(symbols)) + '\nCanonical frame from ' + receipt['filename'] + '\n' + '\n'.join(
                str(token) + ' ' + ' '.join(format(float(value), '.17g') for value in row)
                for token, row in zip(symbols, coordinates, strict=True)) + '\n'
            identity = parse_geometry_identity(xyz)
            digest = hashlib.sha256(xyz.encode()).hexdigest()
            key = uuid.uuid4().hex
            directory = get_artifact_dir() / 'StudentInputs' / key
            directory.mkdir(parents=True, exist_ok=False)
            path = directory / 'canonical-frame.xyz'
            path.write_bytes(xyz.encode())
            path.chmod(0o444)
            charge = frame.get('charge') if frame.get('charge') is not None else self.charge_input.value
            multiplicity = frame.get('multiplicity') if frame.get('multiplicity') is not None else self.multiplicity_input.value
            label = Path(receipt['filename']).stem + (f' frame {frame_index + 1}' if len(receipt['records']) > 1 else '')
            record = {'schema_version': 'cochem.student-input/1', 'id': key, 'filename': path.name,
                'path': str(path), 'sha256': digest, 'byte_count': len(xyz.encode()), 'atom_count': len(symbols),
                'elements': list(identity.elements), 'nuclides': list(identity.nuclides),
                'coordinates_angstrom': [list(row) for row in identity.coordinates_angstrom],
                'role': self.student_input_role.value, 'label': label, 'charge': charge,
                'multiplicity': multiplicity, 'fragments': None, 'coordinate_unit': 'angstrom',
                'origin': 'canonical_ingestion', 'source_input_id': receipt.get('input_id', receipt.get('id')),
                'source_sha256': receipt['sha256'], 'source_frame': frame_index}
            (directory / 'input-manifest.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
            self._student_uploads[key] = record
            self.student_geometry_choice.options = [(item['label'], key) for key, item in self._student_uploads.items()]
            self.student_geometry_choice.value = key
            self._refresh_student_monomer_choices()
            self.input_library_status.value = f"<p role='status'>Starting geometry selected from frame {frame_index + 1}. Original source SHA-256 <code>{receipt['sha256']}</code> retained. Confirm the charge and multiplicity when the source does not encode them.</p>"
            self.state.active_view = 'matrix'
        except (ValueError, RuntimeError, OSError, KeyError, TypeError, IndexError) as exc:
            self.input_library_status.value = f"<p role='alert'>Structure was not selected: {html.escape(str(exc))}</p>"

    def _scan_input_inbox(self, b: Any = None) -> None:
        if self._ingestion_busy:
            return
        from cochem_base.config_loader import get_artifact_dir
        inbox = get_artifact_dir() / 'Input_Files' / 'Inbox'
        inbox.mkdir(parents=True, exist_ok=True)
        if inbox.is_symlink():
            self.input_library_status.value = '<p role="alert">The input inbox must be an owned directory.</p>'
            return
        self._ingestion_busy = True
        self.btn_inbox_scan.disabled = True
        def scan() -> None:
            errors, count = [], 0
            try:
                from cochem_base.interfaces.student_ingestion import ingest_uploaded_file
                for path in sorted(inbox.iterdir())[:500]:
                    if path.is_symlink() or not path.is_file() or path.name.startswith('.'):
                        continue
                    try:
                        size = path.stat().st_size
                        if not 0 < size <= 64 * 1024 * 1024:
                            raise ValueError('Input must contain 1 byte to 64 MiB')
                        before = path.stat()
                        content = path.read_bytes()
                        after = path.stat()
                        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                            continue  # A producer is still writing; read on the next scan.
                        digest = hashlib.sha256(content).hexdigest()
                        if any(item['sha256'] == digest and item['filename'] == path.name for item in self._input_library.values()):
                            continue
                        ingest_uploaded_file(path.name, content, artifact_dir=get_artifact_dir(), kind='auto')
                        count += 1
                    except (ValueError, RuntimeError, OSError, UnicodeError) as exc:
                        errors.append(path.name + ': ' + str(exc))
            except (ImportError, OSError) as exc:
                errors.append(str(exc))
            try:
                snapshot = self._read_input_library()
            except (ImportError, OSError, ValueError, RuntimeError) as exc:
                snapshot = {'inputs': list(self._input_library.values()), 'rejections': []}
                errors.append(str(exc))
            def finish() -> None:
                self._ingestion_busy = False
                self.btn_inbox_scan.disabled = False
                self._input_library_refresh_serial += 1
                self._apply_input_library(snapshot)
                self.input_library_status.value = f'<p role="status">Imported {count} new validated inbox input(s).</p>' + (
                    '<p role="alert">' + '<br/>'.join(html.escape(item) for item in errors) + '</p>' if errors else '')
            self._ui_call(finish)
        self._ingestion_worker = threading.Thread(target=scan, daemon=True)
        self._ingestion_worker.start()

    def _watch_input_inbox(self, b: Any = None) -> None:
        if getattr(self, '_input_inbox_worker', None) is not None and self._input_inbox_worker.is_alive():
            return
        self._inbox_stop.clear()
        self.btn_inbox_watch.disabled = True
        self.btn_inbox_stop.disabled = False
        self._scan_input_inbox()
        def watch() -> None:
            while not self._inbox_stop.wait(5):
                if not self._ingestion_busy:
                    self._ui_call(self._scan_input_inbox)
        self._input_inbox_worker = threading.Thread(target=watch, daemon=True)
        self._input_inbox_worker.start()

    def _stop_input_inbox(self, b: Any = None) -> None:
        self._inbox_stop.set()
        self.btn_inbox_watch.disabled = False
        self.btn_inbox_stop.disabled = True

    def _sieve_input_pools(self, b: Any = None) -> None:
        if self._ingestion_busy or not self.input_pool_choices.value:
            self.input_pool_status.value = '<p role="alert">Select retained native conformer pools before merging.</p>'
            return
        selection = tuple(self.input_pool_choices.value)
        context = {}
        if self.input_pool_declare_context.value:
            method, version = self.input_pool_method.value.strip(), self.input_pool_version.value.strip()
            if not 1 <= len(method) <= 200 or not 1 <= len(version) <= 200 or len(self.input_pool_basis.value) > 200:
                self.input_pool_status.value = '<p role="alert">Energy ranking requires the exact common recorded method and engine/model version. Source declarations must agree with these values.</p>'
                return
            context = {'charge': self.input_pool_charge.value, 'multiplicity': self.input_pool_multiplicity.value,
                'comparison_protocol': json.dumps({'engine': self.input_pool_engine.value, 'method': method,
                    'basis': self.input_pool_basis.value.strip() or None, 'version': version}, sort_keys=True)}
        self._ingestion_busy = True
        self.btn_sieve_inputs.disabled = True
        self.input_pool_status.value = '<p role="status">Applying the canonical graph, energy, RMSD and rotational-constant sieve…</p>'
        def sieve() -> None:
            try:
                from cochem_base.config_loader import get_artifact_dir
                from cochem_base.interfaces.student_ingestion import deduplicate_ingested_pools
                receipt = deduplicate_ingested_pools(selection, artifact_dir=get_artifact_dir(), **context)
                snapshot = self._read_input_library()
                def success() -> None:
                    self._input_library_refresh_serial += 1
                    self._apply_input_library(snapshot)
                    self._last_input_pool_sieve = receipt
                    identifiers = []
                    for item in receipt['unique_records']:
                        source = next((entry for entry in receipt['source_inputs']
                            if entry['source_sha256'] == item['source_sha256'] and entry['source_filename'] == item['source_filename']), None)
                        if source is None:
                            raise ValueError('Retained conformer lacks its original library source')
                        identifiers.append(source['input_id'] + ':' + str(item['record_index']))
                    self.input_unique_conformer.options = [(f'Retained conformer {index + 1}', identifier)
                        for index, identifier in enumerate(identifiers)]
                    if identifiers:
                        self.input_unique_conformer.value = identifiers[0]
                    self.btn_use_unique_conformer.disabled = not identifiers
                    source_rows = ''.join('<tr>' + ''.join('<td>' + html.escape(str(value)) + '</td>' for value in
                        (item['source_filename'] + ' frame ' + str(item['record_index'] + 1),
                         item.get('imported_energy', '[MISSING DATA]'), item.get('imported_energy_unit', '[MISSING DATA]'),
                         item['source_sha256'])) + '</tr>' for item in receipt['unique_records'])
                    self.input_pool_status.value = (f'<p role="status">Retained {receipt["unique_count"]} of {receipt["input_count"]} imported conformers. '
                        'The graph, energy, RMSD and rotational sieve groups supplied structures; it does not verify stationary minima or energy accuracy.</p>'
                        '<p>Structures without comparable recorded energies, electronic states or a common protocol remain unranked and retained.</p>'
                        '<table><caption>Retained conformer source evidence</caption><thead><tr><th>Conformer</th><th>Imported energy</th><th>Recorded unit</th><th>Original SHA-256</th></tr></thead><tbody>' + source_rows + '</tbody></table>')
                self._ui_call(success)
            except (ImportError, ValueError, RuntimeError, OSError) as exc:
                message = str(exc)
                self._ui_call(lambda: setattr(self.input_pool_status, 'value',
                    '<p role="alert">Pool merge was not performed: ' + html.escape(message) + '</p>'))
            finally:
                def finish() -> None:
                    self._ingestion_busy = False
                    self.btn_sieve_inputs.disabled = False
                self._ui_call(finish)
        self._ingestion_worker = threading.Thread(target=sieve, daemon=True)
        self._ingestion_worker.start()

    def _use_unique_conformer(self, b: Any = None) -> None:
        identifier = self.input_unique_conformer.value
        try:
            input_id, index = identifier.rsplit(':', 1)
            frame_index = int(index)
            receipt = self._input_library[input_id]
            if not 0 <= frame_index < len(receipt['records']):
                raise ValueError('Retained conformer frame is outside its original input')
            self.input_library_choice.value = input_id
            self.input_record_choice.value = frame_index
            self._use_library_geometry()
        except (AttributeError, ValueError, KeyError) as exc:
            self.input_pool_status.value = '<p role="alert">Retained conformer was not selected: ' + html.escape(str(exc)) + '</p>'

    def _build_periodic_input_controls(self) -> None:
        self.paw_input_upload = widgets.FileUpload(accept='.upf,.UPF', multiple=True, description='Upload PAW files')
        self.paw_input_upload.observe(lambda change: self._upload_input_files(self.paw_input_upload, 'pseudopotential'), names='value')
        self._paw_pseudopotential_choices = {}
        self.paw_species_box = widgets.VBox([widgets.HTML('<p>Select a periodic structure to assign one validated PBE PAW pseudopotential to each element.</p>')])
        self.paw_ecutwfc = widgets.BoundedFloatText(value=45, min=.1, max=1000, description='Wavefunction cutoff (Ry):', style={'description_width': 'initial'})
        self.paw_ecutrho = widgets.BoundedFloatText(value=360, min=.1, max=10000, description='Density cutoff (Ry):', style={'description_width': 'initial'})
        self.paw_kpoints = [widgets.BoundedIntText(value=2, min=1, max=32, description=f'k-grid {axis}:') for axis in ('a', 'b', 'c')]
        self.paw_scf_tolerance = widgets.BoundedFloatText(value=1e-8, min=1e-14, max=1e-6, description='SCF tolerance (Ry):', style={'description_width': 'initial'})
        self.paw_scf_steps = widgets.BoundedIntText(value=100, min=1, max=1000, description='Maximum SCF steps:', style={'description_width': 'initial'})
        self.view_periodic.children = (
            widgets.HTML('<h3>Product B periodic structures</h3><p>Upload an ordered bulk CIF or explicitly unit-labelled periodic structure. BASE preserves the original cell, coordinates and source hash. Partially occupied or disordered structures require resolved input.</p>'),
            self.periodic_input_upload, self._input_selectors['periodic'], self.btn_periodic_inspect, self.periodic_structure_status,
            widgets.HTML('<p>Upload the authentic PBE PAW UPF files for your atomic species and assign them below. BASE verifies each header and SHA-256 before execution. Numerical settings must satisfy the pseudopotential recommendations. This adapter requires a neutral closed-shell cell.</p>'),
            self.paw_input_upload, self.paw_species_box, self.paw_ecutwfc, self.paw_ecutrho,
            widgets.HBox(self.paw_kpoints), self.paw_scf_tolerance, self.paw_scf_steps,
            widgets.HBox([self.btn_periodic_save, self.btn_periodic_run, self.btn_periodic_cancel]),
            self.actions_controls, self.calculation_result, self.telemetry_output,
        )

    def _refresh_paw_species(self) -> None:
        structure = getattr(self, '_periodic_structure', None)
        if structure is None:
            return
        previous = {symbol: chooser.value for symbol, chooser in self._paw_pseudopotential_choices.items()}
        self._paw_pseudopotential_choices = {}
        guidance = []
        for symbol in sorted(set(structure.elements)):
            choices = [(item['filename'], key) for key, item in self._input_library.items()
                if item['kind'] == 'pseudopotential' and item.get('metadata', {}).get('element') == symbol
                and ' '.join(item.get('metadata', {}).get('header', {}).get('functional', '').upper().split()) in {'PBE', 'SLA PW PBX PBC'}
                and item.get('metadata', {}).get('header', {}).get('has_so', '').strip().upper() in {'F', 'FALSE', '.FALSE.'}]
            selector = widgets.Dropdown(options=choices or [(f'Upload a PBE PAW UPF for {symbol}', '')],
                description=f'{symbol} PAW file:', style={'description_width': 'initial'}, layout=widgets.Layout(width='95%'))
            if previous.get(symbol) in [value for _, value in choices]:
                selector.value = previous[symbol]
            self._paw_pseudopotential_choices[symbol] = selector
            excluded = [item['filename'] for item in self._input_library.values()
                if item['kind'] == 'pseudopotential' and item.get('metadata', {}).get('element') == symbol
                and item['filename'] not in [label for label, _ in choices]]
            if excluded:
                guidance.append(widgets.HTML('<p role="status">Unavailable for this PBE closed-shell adapter: ' +
                    html.escape(', '.join(excluded)) + '. A different functional or spin-orbit dataset requires its own validated adapter.</p>'))
        self.paw_species_box.children = (*self._paw_pseudopotential_choices.values(), *guidance)

    def _periodic_settings_from_form(self) -> dict[str, Any]:
        if not self._paw_pseudopotential_choices:
            raise ValueError('Upload and select a periodic structure first')
        pseudopotentials = {}
        for symbol, chooser in self._paw_pseudopotential_choices.items():
            receipt = self._input_library.get(chooser.value)
            if not receipt:
                raise ValueError(f'Upload and select a validated PBE PAW pseudopotential for {symbol}')
            if hashlib.sha256(Path(receipt['path']).read_bytes()).hexdigest() != receipt['sha256']:
                raise ValueError(f'Retained PAW input hash changed for {symbol}')
            pseudopotentials[symbol] = {'path': receipt['path'], 'sha256': receipt['sha256']}
        return {'pseudopotentials': pseudopotentials, 'ecutwfc_ry': self.paw_ecutwfc.value,
            'ecutrho_ry': self.paw_ecutrho.value, 'kpoints': [item.value for item in self.paw_kpoints],
            'conv_thr_ry': self.paw_scf_tolerance.value, 'max_scf_steps': self.paw_scf_steps.value}

    def _build_student_molecule(self, b: Any = None) -> None:
        query = self.smiles_input.value.strip()
        if not query or self._ingestion_busy:
            return
        self._ingestion_busy = True
        self.btn_build_smiles.disabled = True
        self.student_upload_status.value = '<p role="status">Resolving your molecule and constructing a force-field starting geometry…</p>'
        def build() -> None:
            try:
                from cochem_base.config_loader import get_artifact_dir
                from cochem_base.intake.cochem_mint_ingestor import generate_3d_geometry
                from cochem_base.interfaces.student_ingestion import ingest_uploaded_file
                directory = get_artifact_dir() / 'Input_Files' / 'Generated' / uuid.uuid4().hex
                path = generate_3d_geometry(query, directory / 'starting-geometry.xyz')
                sidecar = path.with_suffix('.starting-geometry.json')
                provenance = json.loads(sidecar.read_text(encoding='utf-8'))
                raw = path.read_bytes()
                if hashlib.sha256(raw).hexdigest() != provenance['sha256']:
                    raise ValueError('Generated coordinates disagree with their canonical provenance')
                receipt = ingest_uploaded_file('generated-starting-geometry.xyz', raw, artifact_dir=get_artifact_dir(), kind='molecular')
                snapshot = self._read_input_library()
                def success() -> None:
                    self._input_library_refresh_serial += 1
                    self._apply_input_library(snapshot)
                    self.input_library_choice.value = receipt['input_id']
                    self.charge_input.value = provenance['charge']
                    self._use_library_geometry()
                    record = self._student_uploads.get(self.student_geometry_choice.value)
                    if record:
                        record['generation_provenance'] = {'path': str(sidecar), 'sha256': hashlib.sha256(sidecar.read_bytes()).hexdigest(),
                            'query': query, 'resolution_source': provenance['resolution_source'], 'quantum_optimized': False}
                        Path(record['path']).parent.joinpath('input-manifest.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
                    self.student_upload_status.value += ('<p role="status">Generated starting geometry only. ' +
                        html.escape(str(provenance['forcefield'])) + '; molecular identity source: ' +
                        html.escape(str(provenance['resolution_source'])) +
                        '. Confirm spin multiplicity before calculation; atom radical flags do not define coupled molecular spin. No quantum minimum or energy is claimed.</p>')
                self._ui_call(success)
            except (ImportError, ValueError, RuntimeError, OSError, KeyError) as exc:
                message = str(exc)
                self._ui_call(lambda: setattr(self.student_upload_status, 'value',
                    '<p role="alert">Starting geometry was not generated: ' + html.escape(message) + '</p>'))
            finally:
                def finish() -> None:
                    self._ingestion_busy = False
                    self.btn_build_smiles.disabled = False
                self._ui_call(finish)
        self._ingestion_worker = threading.Thread(target=build, daemon=True)
        self._ingestion_worker.start()

    def _build_student_setup_panel(self) -> None:
        self.student_setup_status = widgets.HTML("<p role='status'>Checking CoChem setup…</p>")
        self.btn_setup_retry = widgets.Button(description="Retry setup", icon="refresh")
        self.btn_setup_updates = widgets.Button(description="Check for updates")
        self.btn_setup_apply = widgets.Button(description="Apply compatible updates", disabled=True)
        self.btn_setup_rollback = widgets.Button(description="Roll back update", disabled=True)
        self.btn_setup_restart = widgets.Button(description="Restart interface", disabled=True)
        for button, action in ((self.btn_setup_retry, "install_default_modules"),
                               (self.btn_setup_updates, "check_updates"),
                               (self.btn_setup_apply, "apply_updates"),
                               (self.btn_setup_rollback, "rollback"),
                               (self.btn_setup_restart, "restart_dashboard")):
            button.on_click(lambda _, name=action: self._student_setup_action(name))
        self.student_setup_panel = widgets.VBox([
            widgets.HTML("<h3>CoChem setup and updates</h3><p>BASE prepares TOPOS and TORQ automatically in separate environments. You use every module here; no terminal commands or separate repository installation are needed. Your input geometries and results stay outside application source during updates.</p>"),
            self.student_setup_status,
            widgets.HBox([self.btn_setup_retry, self.btn_setup_updates, self.btn_setup_apply]),
            widgets.HBox([self.btn_setup_rollback, self.btn_setup_restart]),
        ], layout=widgets.Layout(border='1px solid #b8daff', padding='12px', margin='10px 0'))

    def _render_student_setup_status(self, status: dict[str, Any]) -> None:
        rows = []
        for name, observation in status.get("modules", {}).items():
            rows.append("<tr>" + "".join(f"<td>{html.escape(str(value))}</td>" for value in
                (name.upper(), observation.get("status", "unavailable"), observation.get("revision", ""),
                 observation.get("message", ""))) + "</tr>")
        free_engines = status.get('free_engines', {})
        if free_engines:
            rows.append('<tr>' + ''.join('<td>' + html.escape(str(value)) + '</td>' for value in
                ('Free screening engines', free_engines.get('status', 'unavailable'), '', free_engines.get('message', ''))) + '</tr>')
            for name, observed in free_engines.get('engines', {}).items():
                rows.append('<tr>' + ''.join('<td>' + html.escape(str(value)) + '</td>' for value in
                    (name.upper(), observed.get('status', 'unavailable'), observed.get('version', ''), observed.get('message', observed.get('reason', '')))) + '</tr>')
        base = status.get("base", {})
        operation = status.get("operation", {})
        self.student_setup_status.value = (
            f"<p role='status' aria-live='polite'><b>{'Ready' if status.get('ready') else 'Setup requires attention'}</b>. "
            f"BASE revision: {html.escape(str(base.get('revision', 'unavailable')))}. "
            f"{html.escape(str(operation.get('message', '')))}</p>"
            "<table><caption>CoChem components</caption><thead><tr><th>Component</th><th>Status</th><th>Revision</th><th>Details</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table>"
        )
        self.btn_setup_restart.disabled = self._student_setup_busy or not base.get("restart_required", False)
        self.btn_setup_rollback.disabled = self._student_setup_busy or not bool(status.get("rollback_available", False))
        plan = status.get("update_plan") or {}
        self.btn_setup_apply.disabled = self._student_setup_busy or not bool(plan.get("status") == "updates_available" or
            plan.get("updates") or plan.get("available") or plan.get("compatible_updates"))
        if plan:
            self.student_setup_status.value += (
                f"<p role='status'>Update check: {html.escape(str(plan.get('status', 'complete')))}. "
                "Apply compatible updates checks approved published revisions and preserves your research data.</p>"
            )
        self._student_setup_observation = status

    def _start_student_setup(self) -> None:
        """Initialize services without blocking the interface or importing other modules."""
        def check() -> None:
            try:
                self._hpc_history_loaded.wait(timeout=10)
                from cochem_base.config_loader import get_artifact_dir
                from cochem_base.interfaces.student_setup import StudentSetupService
                self._setup_service = StudentSetupService(artifact_dir=get_artifact_dir(), repository_root=_REPO_ROOT,
                    idle_check=lambda: not (
                    self._pipeline_running or self._topos_running or self._hpc_running or self._hpc_retrieving or self._actions_running or self._actions_retrieving or self._remote_probe_running or self._ingestion_busy))
                status = self._setup_service.status()
                self._ui_call(lambda: self._render_student_setup_status(status))
                automatic = os.environ.get("COCHEM_STUDENT_AUTO_SETUP", "").lower()
                if (not status.get("ready") or status.get("free_engines", {}).get("status") == "failed") and (automatic in {"1", "true", "yes"} or
                    automatic not in {"0", "false", "no"} and os.environ.get("CODESPACES", "").lower() == "true"):
                    self._student_setup_action("install_default_modules")
            except (ImportError, ValueError, RuntimeError, OSError) as exc:
                message = str(exc)
                self._ui_call(lambda: setattr(self.student_setup_status, "value",
                    f"<p role='alert'>CoChem setup could not be checked: {html.escape(message)}. Choose Retry setup after access is corrected.</p>"))
        self._student_setup_initial_worker = threading.Thread(target=check, daemon=True)
        self._student_setup_initial_worker.start()

    def _student_setup_action(self, action: str) -> None:
        if self._student_setup_busy:
            return
        if self._pipeline_running or self._topos_running or self._actions_running:
            self.student_setup_status.value = "<p role='alert'>Wait for the running calculation to finish or cancel it before changing CoChem installations.</p>"
            return
        self._student_setup_busy = True
        if action in {"install_default_modules", "apply_updates", "rollback"}:
            self._invalidate_t9_backend()
        self.student_setup_status.value = f"<p role='status' aria-live='polite'>CoChem: {html.escape(action.replace('_', ' '))}…</p>"
        for button in (self.btn_setup_retry, self.btn_setup_updates, self.btn_setup_apply,
                       self.btn_setup_rollback, self.btn_setup_restart):
            button.disabled = True
        finished = threading.Event()
        def progress() -> None:
            while not finished.wait(2):
                if self._setup_service is None:
                    continue
                try:
                    status = self._setup_service.status()
                    self._ui_call(lambda current=status: self._render_student_setup_status(current)
                        if self._student_setup_busy else None)
                except (ValueError, RuntimeError, OSError):
                    continue
        def perform() -> None:
            try:
                if self._setup_service is None:
                    from cochem_base.config_loader import get_artifact_dir
                    from cochem_base.interfaces.student_setup import StudentSetupService
                    self._setup_service = StudentSetupService(artifact_dir=get_artifact_dir(), repository_root=_REPO_ROOT,
                        idle_check=lambda: not (
                        self._pipeline_running or self._topos_running or self._hpc_running or self._hpc_retrieving or self._actions_running or self._actions_retrieving or self._remote_probe_running or self._ingestion_busy))
                receipt = getattr(self._setup_service, action)()
                status = self._setup_service.status()
                if action == "check_updates" and isinstance(receipt, dict):
                    status["update_plan"] = receipt
                def success() -> None:
                    self._student_setup_busy = False
                    self._render_student_setup_status(status)
                    self.btn_setup_retry.disabled = False
                    self.btn_setup_updates.disabled = False
                    self._refresh_module_capabilities()
                    self._refresh_orbital_backend_choices()
                    if self.calc_env_dropdown.value == 'hpc':
                        self._check_student_hpc_connection()
                    if hasattr(self, "_refresh_research_capabilities"):
                        self._refresh_research_capabilities()
                self._ui_call(success)
            except (ValueError, RuntimeError, OSError, ImportError) as exc:
                message = str(exc)
                def failure() -> None:
                    self._student_setup_busy = False
                    self.btn_setup_retry.disabled = False
                    self.btn_setup_updates.disabled = False
                    self.student_setup_status.value = f"<p role='alert'>CoChem setup operation failed: {html.escape(message)}. Your uploaded inputs and results are retained.</p>"
                self._ui_call(failure)
            finally:
                finished.set()
        self._student_setup_worker = threading.Thread(target=perform, daemon=True)
        self._student_setup_progress_worker = threading.Thread(target=progress, daemon=True)
        self._student_setup_worker.start()
        self._student_setup_progress_worker.start()

    def _on_student_xyz_upload(self, change: Any = None) -> None:
        """Accept actual ipywidgets 8 uploads and preserve original validated bytes."""
        from cochem_base.config_loader import get_artifact_dir
        from cochem_base.geometry.nuclide_geometry import parse_geometry_identity
        raw = self.xyz_upload.value
        if not raw:
            return
        files = list(raw.values()) if isinstance(raw, dict) else list(raw)
        accepted, errors = [], []
        for entry in files:
            try:
                filename = str(entry.get("name") or entry.get("metadata", {}).get("name") or "geometry.xyz")
                if "/" in filename or "\\" in filename or not filename.lower().endswith(".xyz"):
                    raise ValueError("Use an XYZ filename without directory components")
                content = bytes(entry["content"])
                if not content or len(content) > 2 * 1024 * 1024:
                    raise ValueError("An XYZ upload must contain 1 byte to 2 MiB")
                text = content.decode("utf-8-sig", errors="strict")
                lines = text.strip().splitlines()
                if not lines or not lines[0].strip().isdigit():
                    raise ValueError("Uploaded XYZ requires atom count, comment line and one frame of coordinates in ångströms")
                identity = parse_geometry_identity(text)
                if len(identity.elements) > 5000:
                    raise ValueError("Geometry ingestion supports at most 5,000 atoms")
                digest = hashlib.sha256(content).hexdigest()
                existing = next((key for key, item in self._student_uploads.items()
                                 if item["sha256"] == digest and item["filename"] == filename), None)
                if existing:
                    accepted.append(existing)
                    continue
                key = uuid.uuid4().hex
                directory = get_artifact_dir() / "StudentInputs" / key
                directory.mkdir(parents=True, exist_ok=False)
                safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", filename).lstrip(".")[:160] or "geometry.xyz"
                path = directory / safe_name
                with path.open("xb") as handle:
                    handle.write(content)
                path.chmod(0o444)
                record = {"schema_version": "cochem.student-input/1", "id": key, "filename": filename,
                    "path": str(path), "sha256": digest, "byte_count": len(content), "atom_count": len(identity.elements),
                    "elements": list(identity.elements), "nuclides": list(identity.nuclides),
                    "coordinates_angstrom": [list(row) for row in identity.coordinates_angstrom],
                    "role": self.student_input_role.value, "label": Path(filename).stem,
                    "charge": self.charge_input.value, "multiplicity": self.multiplicity_input.value,
                    "fragments": None, "coordinate_unit": "angstrom", "origin": "student_upload"}
                (directory / "input-manifest.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
                self._student_uploads[key] = record
                accepted.append(key)
            except (ValueError, OSError, UnicodeError, KeyError, TypeError) as exc:
                errors.append(f"{entry.get('name', 'XYZ')}: {exc}")
        if accepted:
            self.student_geometry_choice.options = [(record["filename"], key) for key, record in self._student_uploads.items()]
            self.student_geometry_choice.value = accepted[-1]
            self._select_student_geometry({"new": accepted[-1]})
            self._refresh_student_monomer_choices()
        if errors:
            self.student_upload_status.value += "<p role='alert'>Rejected uploads: " + "<br/>".join(html.escape(message) for message in errors) + "</p>"

    def _select_student_geometry(self, change: Any) -> None:
        key = change["new"]
        record = self._student_uploads.get(key)
        if not record or self._input_selection_running:
            return
        path = Path(record["path"])
        try:
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != record["sha256"]:
                raise ValueError("Preserved original geometry hash no longer matches")
            self._input_selection_running = True
            self.matrix_geometry.value = content.decode("utf-8-sig")
            self.project_name.value = record["label"]
            self.student_input_label.value = record["label"]
            self.student_input_role.value = record["role"]
            self.charge_input.value = record["charge"]
            self.multiplicity_input.value = record["multiplicity"]
            self.student_fragment_atoms.value = ";".join(",".join(str(index + 1) for index in fragment)
                for fragment in record.get("fragments") or [])
            self.module_artifact.value = str(path) if hasattr(self, "module_artifact") else ""
            self.student_upload_status.value = (
                f"<p role='status'><b>{html.escape(record['filename'])}</b>: {record['atom_count']} atoms. "
                "Original bytes, atom order and isotope labels preserved. "
                f"SHA-256: <code>{record['sha256']}</code>.</p>"
                "<p>Confirm this geometry's input type, charge and multiplicity, then choose Save geometry details. "
                "Fragment groups use one-based atom indices. Editing coordinates creates a distinct calculation request; the uploaded original remains unchanged.</p>"
            )
        except (ValueError, OSError, UnicodeError) as exc:
            self.student_upload_status.value = f"<p role='alert'>Geometry could not be loaded: {html.escape(str(exc))}</p>"
        finally:
            self._input_selection_running = False

    def _save_student_input_details(self, b: Any = None) -> None:
        record = self._student_uploads.get(self.student_geometry_choice.value)
        if not record:
            self.student_upload_status.value = "<p role='alert'>Upload and select your XYZ before saving its details.</p>"
            return
        try:
            if self.multiplicity_input.value < 1:
                raise ValueError("Multiplicity must be a positive integer")
            groups = None
            if self.student_fragment_atoms.value.strip():
                groups = [[int(index.strip()) - 1 for index in group.split(",")]
                          for group in self.student_fragment_atoms.value.split(";")]
                indices = [index for group in groups for index in group]
                if any(not group for group in groups) or sorted(indices) != list(range(record["atom_count"])):
                    raise ValueError("Fragment groups must assign every atom exactly once using indices 1 through the atom count")
            record.update(role=self.student_input_role.value, label=self.student_input_label.value.strip() or Path(record["filename"]).stem,
                          charge=self.charge_input.value, multiplicity=self.multiplicity_input.value, fragments=groups)
            Path(record["path"]).parent.joinpath("input-manifest.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            self.project_name.value = record["label"]
            self.student_upload_status.value = f"<p role='status'>Saved {html.escape(record['role'])} details: {html.escape(record['label'])}, charge {record['charge']}, multiplicity {record['multiplicity']}. Original SHA-256 <code>{record['sha256']}</code> unchanged.</p>"
            self._refresh_student_monomer_choices()
        except (ValueError, OSError) as exc:
            self.student_upload_status.value = f"<p role='alert'>Geometry details were not saved: {html.escape(str(exc))}</p>"

    def _refresh_student_monomer_choices(self) -> None:
        chosen = set(self.student_monomer_choices.value)
        choices = [(item["label"], key) for key, item in self._student_uploads.items() if item["role"].startswith("monomer")]
        self.student_monomer_choices.options = choices
        self.student_monomer_choices.value = tuple(key for _, key in choices if key in chosen)

    def _restore_student_inputs(self) -> None:
        """Reopen the student's retained, hash-checked inputs after GUI updates."""
        from cochem_base.config_loader import get_artifact_dir
        from cochem_base.geometry.nuclide_geometry import parse_geometry_identity
        root = get_artifact_dir() / "StudentInputs"
        if not root.is_dir() or root.is_symlink():
            return
        records = {}
        manifests = []
        for candidate in root.glob("*/input-manifest.json"):
            try:
                if candidate.is_symlink() or candidate.parent.is_symlink():
                    continue
                manifests.append((candidate.stat().st_mtime, candidate))
            except OSError:
                continue
        for _, manifest in sorted(manifests, key=lambda item: item[0])[-500:]:
            try:
                if manifest.is_symlink() or manifest.parent.is_symlink() or manifest.stat().st_size > 2 * 1024 * 1024:
                    continue
                record = json.loads(manifest.read_text(encoding="utf-8"))
                key = record["id"]
                if (record.get("schema_version") != "cochem.student-input/1" or not re.fullmatch(r"[a-f0-9]{32}", key)
                        or manifest.parent.name != key or record.get("role") not in {"complex", "monomer_a", "monomer_b", "monomer"}
                        or type(record.get("charge")) is not int or type(record.get("multiplicity")) is not int or record["multiplicity"] < 1):
                    continue
                path = Path(record["path"])
                if (path.is_symlink() or path.parent.resolve() != manifest.parent.resolve() or not path.is_file()
                        or path.stat().st_size > 2 * 1024 * 1024):
                    continue
                content = path.read_bytes()
                if hashlib.sha256(content).hexdigest() != record["sha256"]:
                    continue
                identity = parse_geometry_identity(content.decode("utf-8-sig"))
                if list(identity.elements) != record["elements"] or list(identity.nuclides) != record["nuclides"]:
                    continue
                if (record.get("coordinate_unit") != "angstrom" or type(record.get("atom_count")) is not int
                        or record["atom_count"] != len(identity.elements) or not 1 <= record["atom_count"] <= 5000
                        or type(record.get("byte_count")) is not int or record["byte_count"] != len(content)
                        or record.get("coordinates_angstrom") != [list(row) for row in identity.coordinates_angstrom]
                        or not isinstance(record.get("filename"), str) or not 1 <= len(record["filename"]) <= 256
                        or "/" in record["filename"] or "\\" in record["filename"] or "\0" in record["filename"]
                        or not isinstance(record.get("label"), str) or not 1 <= len(record["label"]) <= 500
                        or any(character in record["label"] for character in "\0\r\n")):
                    continue
                groups = record.get("fragments")
                if groups is not None:
                    if (not isinstance(groups, list) or not groups or any(not isinstance(group, list) or not group for group in groups)):
                        continue
                    indices = [index for group in groups for index in group]
                    if any(type(index) is not int for index in indices) or sorted(indices) != list(range(record["atom_count"])):
                        continue
                states = record.get("fragment_states")
                if states is not None:
                    if not groups or not isinstance(states, list) or len(states) != len(groups):
                        continue
                    valid_states = all(isinstance(state, dict) and state.get("atom_indices") == group
                        and type(state.get("charge")) is int and type(state.get("multiplicity")) is int and state["multiplicity"] > 0
                        for state, group in zip(states, groups, strict=True))
                    if not valid_states or sum(state["charge"] for state in states) != record["charge"]:
                        continue
                records[key] = record
            except (ValueError, KeyError, TypeError, UnicodeError, OSError):
                continue
        if records:
            self._student_uploads.update(records)
            self.student_geometry_choice.options = [(record["label"], key) for key, record in self._student_uploads.items()]
            self.student_geometry_choice.value = next(reversed(records))
            self._refresh_student_monomer_choices()

    def _assemble_student_monomers(self, b: Any = None) -> None:
        try:
            from cochem_base.config_loader import get_artifact_dir
            from cochem_base.geometry.nuclide_geometry import parse_geometry_identity
            from cochem_base.interfaces.student_research import assemble_monomers
            records = [self._student_uploads[key] for key in self.student_monomer_choices.value]
            if len(records) < 2:
                raise ValueError("Upload at least two monomers, save their input types and electronic states, then select them above")
            monomers = []
            for item in records:
                raw = Path(item["path"]).read_bytes()
                if hashlib.sha256(raw).hexdigest() != item["sha256"]:
                    raise ValueError("Original monomer geometry hash has changed")
                monomers.append({"xyz": raw.decode("utf-8-sig"), "charge": item["charge"], "multiplicity": item["multiplicity"]})
            result = assemble_monomers(monomers, separation_angstrom=self.student_seed_separation.value,
                                      multiplicity=self.multiplicity_input.value)
            identity = parse_geometry_identity(result["xyz"])
            content = result["xyz"].encode("utf-8")
            key = uuid.uuid4().hex
            directory = get_artifact_dir() / "StudentInputs" / key
            directory.mkdir(parents=True, exist_ok=False)
            path = directory / "student-monomer-complex-seed.xyz"
            path.write_bytes(content)
            path.chmod(0o444)
            record = {"schema_version": "cochem.student-input/1", "id": key, "filename": path.name,
                "path": str(path), "sha256": hashlib.sha256(content).hexdigest(), "byte_count": len(content),
                "atom_count": len(identity.elements), "elements": list(identity.elements), "nuclides": list(identity.nuclides),
                "coordinates_angstrom": [list(row) for row in identity.coordinates_angstrom], "role": "complex",
                "label": " + ".join(item["label"] for item in records), "charge": result["molecule"]["charge"],
                "multiplicity": result["molecule"]["multiplicity"], "fragments": result["molecule"]["fragments"],
                "fragment_states": result["molecule"]["fragment_states"], "coordinate_unit": "angstrom",
                "origin": "student_monomer_translation_seed", "monomer_sources": [{"id": item["id"], "sha256": item["sha256"]} for item in records],
                "assembly": result["topos_request"]["metadata"]["assembly"]}
            (directory / "input-manifest.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            self._student_uploads[key] = record
            self.student_geometry_choice.options = [(item["label"], identity) for identity, item in self._student_uploads.items()]
            self.student_geometry_choice.value = key
            self.student_upload_status.value += "<p><b>Starting packing prepared by translation only.</b> No energy or stable-complex claim has been made. Select a TOPOS search or association calculation next.</p>"
        except (ValueError, OSError, ImportError) as exc:
            self.student_upload_status.value = f"<p role='alert'>Complex starting seed was not prepared: {html.escape(str(exc))}</p>"

    def _student_current_xyz(self) -> str:
        from cochem_base.geometry.nuclide_geometry import parse_geometry_identity
        identity = parse_geometry_identity(self.matrix_geometry.value)
        text = self.matrix_geometry.value
        if text.strip().splitlines()[0].strip().isdigit():
            return text
        return str(len(identity.elements)) + "\nStudent geometry entered in BASE; angstrom\n" + "\n".join(
            symbol + " " + " ".join(format(value, ".17g") for value in row)
            for symbol, row in zip(identity.nuclides, identity.coordinates_angstrom, strict=True)) + "\n"

    def _t9_admission_reason(self) -> str:
        if self.matrix_engine.value != 'ORCA':
            self.t9_guidance.value = '<p>T9 recovery belongs to the ORCA single-reference calculation route.</p>'
            return ''
        remote = self.calc_env_dropdown.value in {'github-actions', 'hpc'}
        required = self.multiplicity_input.value > 1
        # Missing open-shell recovery intent has its own immediate refusal.
        # Only a selected recovery inspects the optional PySCF environment.
        requested = self.t9_enable.value
        backend_reason = ''
        if not remote and requested:
            observation = self._t9_backend_observation
            if observation is not None and not self._t9_backend_binding_matches(observation):
                self._invalidate_t9_backend()
                observation = None
            if observation is None:
                self._start_t9_backend_check()
                backend_reason = 'Checking the configured PySCF recovery environment. T9-dependent calculations remain unavailable until verification finishes.'
            elif not observation.get('available'):
                backend_reason = 'Audited PySCF recovery is unavailable: ' + observation['reason']
        # The intent checkbox remains usable; it requests an asynchronous check.
        # Required/requested recovery and every dependent Run control fail closed.
        for control in (self.t9_method, self.t9_basis, self.t9_electrons, self.t9_orbitals, self.t9_rationale):
            control.disabled = bool(backend_reason)
        reason = ''
        if required and not self.t9_enable.value:
            reason = 'Open-shell ORCA requires explicit T9 recovery before starting: enable recovery and choose the active electrons, molecular orbitals and scientific rationale.'
        if (required or self.t9_enable.value) and backend_reason:
            reason = backend_reason + '. Complete setup for the supported free PySCF backend before selecting this open-shell calculation.'
        elif self.t9_enable.value:
            try:
                self._portable_t9_request()
            except (ValueError, RuntimeError, OSError) as exc:
                reason = str(exc)
        qualification = (
            'The calculation worker requires pinned PySCF and fresh Stage 0 authority before automatic recovery.'
            if remote else backend_reason if backend_reason else
            'PySCF recovery availability was observed for this retained environment. Scientific dispatch re-verifies its complete Stage 0 authority.' if requested else
            'PySCF recovery has not been requested. Closed-shell calculations with T9 off do not inspect or require this optional backend.'
        )
        self.t9_guidance.value = (
            '<p role="alert">' + html.escape(reason) + '</p>' if reason else '<p role="status">' + html.escape(qualification) + '</p>'
        ) + '<p>At or above 10% spin contamination, the rejected single-reference result requires T9 recovery. An interrupted optimization or frequency job is not certified by a recovered single-point result.</p>'
        return reason

    def _invalidate_t9_backend(self) -> None:
        """Discard UI readiness; scientific execution never trusts this observation."""
        self._t9_backend_generation += 1
        self._t9_backend_observation = None

    @staticmethod
    def _t9_backend_file_state(path: Path) -> tuple[Any, ...]:
        stat = path.stat()
        return (str(path), stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_mode)

    def _t9_backend_binding(self) -> tuple[list[tuple[Any, ...]], list[Path]]:
        """Bind readiness to actual registry, controller source and silo files.

        Full content hashes are acquired by the background verifier. Subsequent
        UI transitions inspect filesystem identity only; actual dispatch always
        repeats the complete scientific authorization regardless of this state.
        """
        from cochem_base.config_loader import resolve_config_path
        from cochem_base.core_engine import execution_authority
        from cochem_base.orchestrator import micro_silo_manager
        registry = resolve_config_path()
        payload = json.loads(registry.read_text(encoding='utf-8'))
        stage0 = payload.get('stage0') if isinstance(payload, dict) else None
        silos = stage0.get('micro_silos') if isinstance(stage0, dict) else None
        silo = silos.get('cochem_calc_silo') if isinstance(silos, dict) else None
        if not isinstance(silo, dict):
            raise ValueError('PySCF recovery requires a complete Stage 0 micro-silo record')
        if not silo.get('root') or not silo.get('python_executable'):
            raise ValueError('PySCF recovery requires a complete Stage 0 micro-silo record')
        silo_root = Path(silo['root'])
        files = [registry, Path(__file__).resolve(), Path(execution_authority.__file__).resolve(),
                 Path(micro_silo_manager.__file__).resolve()]
        states = []
        if silo_root.is_dir():
            files.extend([silo_root / 'pyvenv.cfg', Path(silo['python_executable'])])
            package_roots = list((silo_root / 'lib').glob('python*/site-packages'))
            if (silo_root / 'Lib' / 'site-packages').is_dir():
                package_roots.append(silo_root / 'Lib' / 'site-packages')
            for package_root in package_roots:
                def reject_unreadable_path(error: OSError) -> None:
                    raise error
                for directory, child_dirs, child_files in os.walk(package_root, followlinks=False, onerror=reject_unreadable_path):
                    child_dirs[:] = [name for name in child_dirs if name != '__pycache__']
                    states.append(self._t9_backend_file_state(Path(directory)))
                    files.extend(Path(directory) / name for name in child_files if not name.endswith(('.pyc', '.pyo')))
                    if len(files) + len(states) > 50000:
                        raise ValueError('PySCF readiness inventory exceeds the bounded file limit')
        states.extend(self._t9_backend_file_state(path) for path in files)
        return sorted(states), files

    def _t9_backend_binding_matches(self, observation: dict[str, Any]) -> bool:
        try:
            from cochem_base.config_loader import resolve_config_path
            registry = resolve_config_path()
            if observation.get('generation') != self._t9_backend_generation:
                return False
            if observation.get('registry_path') != str(registry):
                return False
            if observation.get('resources') != (self.actions_cores.value, self.actions_memory.value):
                return False
            if observation.get('registry_absent') and registry.exists():
                return False
            for state in observation['file_states']:
                if self._t9_backend_file_state(Path(state[0])) != state:
                    return False
            return True
        except (OSError, ValueError, KeyError, TypeError):
            return False

    def _start_t9_backend_check(self) -> None:
        if self._t9_backend_running:
            return
        self._t9_backend_running = True
        generation = self._t9_backend_generation
        cores, memory = self.actions_cores.value, self.actions_memory.value
        def check() -> None:
            from cochem_base.config_loader import resolve_config_path
            registry = resolve_config_path()
            observation = {'generation': generation, 'available': False, 'reason': '', 'file_states': [],
                           'registry_path': str(registry), 'registry_absent': not registry.exists(),
                           'resources': (cores, memory)}
            try:
                from cochem_base.core_engine.execution_authority import authorize_engine_execution
                before, files = self._t9_backend_binding()
                authorization = authorize_engine_execution('pyscf', cores=cores, maxcore_mb=memory)
                after, _ = self._t9_backend_binding()
                if before != after:
                    raise ValueError('Recovery environment changed during verification; retry after setup finishes')
                content_hashes = {}
                total_size = 0
                for path in files:
                    total_size += path.stat().st_size
                    if total_size > 2 * 1024**3:
                        raise ValueError('Recovery source inventory exceeds the bounded byte limit')
                    with path.open('rb') as handle:
                        content_hashes[str(path)] = hashlib.file_digest(handle, 'sha256').hexdigest()
                final, _ = self._t9_backend_binding()
                if final != after:
                    raise ValueError('Recovery source or package state changed while recording its identity')
                observation.update(available=True, file_states=final, content_sha256=content_hashes,
                                   executable=authorization.executable, observed_at=time.time())
            except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
                observation['reason'] = str(exc)
                try:
                    observation['file_states'], _ = self._t9_backend_binding()
                except (ValueError, RuntimeError, OSError, KeyError, TypeError):
                    from cochem_base.config_loader import resolve_config_path
                    registry = resolve_config_path()
                    if registry.exists():
                        observation['file_states'] = [self._t9_backend_file_state(registry)]
            def publish() -> None:
                self._t9_backend_running = False
                if generation == self._t9_backend_generation:
                    self._t9_backend_observation = observation
                if hasattr(self, 'btn_execute'):
                    self._check_dispersion_gate()
            self._ui_call(publish)
        self._t9_backend_worker = threading.Thread(target=check, daemon=True)
        self._t9_backend_worker.start()

    def _portable_t9_request(self) -> dict[str, Any] | None:
        if not self.t9_enable.value:
            return None
        from cochem_base.geometry.nuclide_geometry import parse_geometry_identity
        from cochem_base.physics.nuclide_resolver import get_element
        orbitals = [int(value.strip()) for value in self.t9_orbitals.value.split(',') if value.strip()]
        if (not orbitals or any(index < 0 for index in orbitals) or len(set(orbitals)) != len(orbitals)
                or not 1 <= self.t9_electrons.value <= 2 * len(orbitals)):
            raise ValueError("T9 requires distinct nonnegative MO indices and a compatible positive active-electron count")
        rationale = self.t9_rationale.value.strip()
        if not rationale or len(rationale) > 4000:
            raise ValueError("T9 requires a scientific active-space rationale of at most 4,000 characters")
        identity = parse_geometry_identity(self.matrix_geometry.value)
        total = sum(int(get_element(symbol).atomic_number) for symbol in identity.elements) - self.charge_input.value
        spin = self.multiplicity_input.value - 1
        inactive = total - self.t9_electrons.value
        if (inactive < 0 or inactive % 2 or (self.t9_electrons.value - spin) % 2
                or spin > self.t9_electrons.value or (self.t9_electrons.value + spin) // 2 > len(orbitals)):
            raise ValueError("The requested active space cannot represent this geometry's charge and multiplicity")
        return {"pyscf_version": "2.14.0", "method": self.t9_method.value, "basis": self.t9_basis.value,
            "active_electrons": self.t9_electrons.value, "active_orbitals": orbitals,
            "active_space_rationale": rationale, "threads": self.actions_cores.value,
            "memory_mb": self.actions_memory.value * self.actions_cores.value,
            "timeout_seconds": float(self.actions_timeout.value), "max_cycle": 200}

    def _ingest_student_scientific_input(self, kind: str, widget: widgets.FileUpload) -> None:
        if not widget.value:
            return
        entry = list(widget.value.values())[0] if isinstance(widget.value, dict) else widget.value[0]
        try:
            content = bytes(entry['content'])
            if not content or len(content) > 16 * 1024 * 1024:
                raise ValueError("Scientific uploads must contain 1 byte to 16 MiB")
            geometry = self._student_current_xyz()
            filename = str(entry.get('name', 'scientific-input'))
        except (ValueError, KeyError, TypeError) as exc:
            self.scientific_input_status.value = f"<p role='alert'>Scientific input was not accepted: {html.escape(str(exc))}</p>"
            return
        widget.disabled = True
        self.scientific_input_status.value = "<p role='status'>Verifying retained scientific evidence and its geometry binding…</p>"
        def ingest() -> None:
            try:
                from cochem_base.config_loader import get_artifact_dir
                from cochem_base.interfaces.scientific_inputs import ingest_scientific_upload
                destination = get_artifact_dir() / "ScientificInputs" / f"{kind}-{uuid.uuid4().hex}"
                destination.parent.mkdir(parents=True, exist_ok=True)
                receipt = ingest_scientific_upload(kind, content, filename, geometry_xyz=geometry, destination=destination)
                retained = {key: receipt[key] for key in ('kind', 'entrypoint', 'geometry_sha256', 'input_scope', 'scientific_validation_performed')}
                retained['schema_version'] = 'cochem.student-scientific-input/1'
                retained['files'] = {name: {'sha256': hashlib.sha256(raw).hexdigest(), 'size_bytes': len(raw)}
                                     for name, raw in receipt['files'].items()}
                metadata = destination / 'student-scientific-input.json'
                metadata.write_text(json.dumps(retained, indent=2, allow_nan=False) + '\n', encoding='utf-8')
                metadata.chmod(0o444)
                def success() -> None:
                    self._scientific_inputs[kind] = receipt
                    if kind == 'r2_reference':
                        self.r2_reference_manifest.value = str(receipt['entrypoint_path'])
                    self.scientific_input_status.value = (
                        f"<p role='status'><b>{html.escape(kind)} retained.</b> "
                        f"Input scope: {html.escape(str(receipt.get('input_scope', 'transport and source binding')))}. "
                        "The worker validates native evidence before executing its dependent scientific method.</p>"
                    )
                    self._check_dispersion_gate()
                    try:
                        self.live_preview.value = json.dumps(self._collect_run_config(), indent=2)
                    except (ValueError, RuntimeError, OSError, MethodologyViolationError) as exc:
                        self.live_preview.value = f"Configuration requires attention: {exc}"
                self._ui_call(success)
            except (ValueError, RuntimeError, OSError, ImportError) as exc:
                message = str(exc)
                self._ui_call(lambda: setattr(self.scientific_input_status, 'value', f"<p role='alert'>Scientific input was rejected: {html.escape(message)}</p>"))
            finally:
                self._ui_call(lambda: setattr(widget, 'disabled', False))
        self._scientific_input_worker = threading.Thread(target=ingest, daemon=True)
        self._scientific_input_worker.start()

    def _restore_student_scientific_inputs(self) -> None:
        """Recover only bounded intact evidence stored in this student's workspace."""
        def restore() -> None:
            from cochem_base.config_loader import get_artifact_dir
            from cochem_base.interfaces.scientific_inputs import safe_relative_path
            root = get_artifact_dir() / 'ScientificInputs'
            if root.is_symlink() or not root.is_dir():
                return
            candidates = []
            for path in root.glob('*/student-scientific-input.json'):
                try:
                    if not path.is_symlink() and not path.parent.is_symlink() and path.stat().st_size <= 256 * 1024:
                        candidates.append((path.stat().st_mtime, path))
                except OSError:
                    continue
            restored = {}
            for _, path in sorted(candidates, reverse=True)[:20]:
                try:
                    record = json.loads(path.read_text(encoding='utf-8'))
                    kind = record['kind']
                    if kind in restored or kind not in {'r2_reference', 'read_hessian'} or record.get('schema_version') != 'cochem.student-scientific-input/1':
                        continue
                    if not re.fullmatch('[a-f0-9]{64}', record['geometry_sha256']) or not isinstance(record.get('files'), dict) or not 1 <= len(record['files']) <= 512:
                        continue
                    files, total = {}, 0
                    for name, expected in record['files'].items():
                        safe_relative_path(name)
                        source = path.parent.joinpath(*name.split('/'))
                        if source.is_symlink() or not source.resolve().is_relative_to(path.parent.resolve()) or not source.is_file():
                            raise ValueError('Evidence file is outside the owned receipt')
                        size = source.stat().st_size
                        total += size
                        if not 0 < size <= 16 * 1024 * 1024 or total > 64 * 1024 * 1024 or type(expected['size_bytes']) is not int or size != expected['size_bytes']:
                            raise ValueError('Evidence size differs from the receipt')
                        raw = source.read_bytes()
                        if hashlib.sha256(raw).hexdigest() != expected['sha256']:
                            raise ValueError('Evidence hash differs from the receipt')
                        files[name] = raw
                    entrypoint = record['entrypoint']
                    if entrypoint not in files:
                        continue
                    restored[kind] = {**record, 'files': files, 'entrypoint_path': path.parent.joinpath(*entrypoint.split('/'))}
                except (ValueError, TypeError, KeyError, OSError):
                    continue
            def complete() -> None:
                for kind, receipt in restored.items():
                    self._scientific_inputs.setdefault(kind, receipt)
                if restored:
                    self.scientific_input_status.value = '<p role="status">Retained R2/READ evidence was reopened after verifying its original file hashes. Choose the matching geometry; native scientific validation remains required.</p>'
                    self._check_dispersion_gate()
            self._ui_call(complete)
        self._scientific_restore_worker = threading.Thread(target=restore, daemon=True)
        self._scientific_restore_worker.start()

    def _selected_scientific_input(self) -> dict[str, Any] | None:
        requested = []
        if self.cb_recipe_r2.value:
            requested.append('r2_reference')
        if self.scientific_initial_hessian.value == 'READ':
            requested.append('read_hessian')
        if len(requested) > 1:
            raise ValueError("R2 uses its reference-monomer protocol; a separate READ Hessian cannot replace that request")
        if not requested:
            return None
        receipt = self._scientific_inputs.get(requested[0])
        if not receipt:
            raise ValueError("Upload the genuine " + requested[0] + " input before choosing this dependent calculation")
        geometry = self._student_current_xyz()
        if receipt['geometry_sha256'] != hashlib.sha256(geometry.encode('utf-8')).hexdigest():
            raise ValueError("Scientific reference/Hessian input belongs to a different geometry. Upload evidence bound to the currently selected structure")
        return receipt

    def _build_student_research_panels(self) -> None:
        self._research_capability_observations = {}
        self._research_observations = []
        self._research_reports = []
        self.research_capabilities = widgets.HTML("<p role='status'>Checking installed research capabilities…</p>")
        self.btn_research_refresh = widgets.Button(description="Refresh research capabilities")
        self.btn_research_refresh.on_click(self._refresh_research_capabilities)
        self.research_topos_operation = widgets.Dropdown(options=[("Checking capabilities", "")],
            description="Research operation:", style={'description_width': 'initial'}, disabled=True)
        self.research_topos_engine = widgets.Dropdown(options=[("xTB GFN2 screening", "xtb")], value="xtb", description="Research method:", style={'description_width': 'initial'})
        self.research_matrix_recipe = widgets.Dropdown(options=[("No verified molecule-only recipe", "")],
            description="Optimization recipe:", style={'description_width': 'initial'}, disabled=True)
        self.research_matrix_guidance = widgets.HTML("<p>Only complete recipes supported by the installed TOPOS catalog can be selected. R1 association references and scan-coordinate recipes require their own validated inputs.</p>")
        self.research_candidates = widgets.BoundedIntText(value=4, min=1, max=100, description="Starting candidates:",
            style={'description_width': 'initial'})
        self.research_temperature = widgets.BoundedFloatText(value=298.15, min=1, max=2000,
            description="Temperature (K):", style={'description_width': 'initial'})
        self.research_fragment_states = widgets.VBox()
        self._research_fragment_state_inputs = []
        self.btn_research_fragment_states = widgets.Button(description="Set monomer electronic states")
        self.btn_research_fragment_states.on_click(self._build_student_fragment_states)
        self.btn_research_topos = widgets.Button(description="Run TOPOS research", button_style="success", disabled=True)
        self.btn_research_topos.on_click(self._run_student_topos)
        self.research_status = widgets.HTML("<p role='status'>Upload your own monomer or complex starting geometries in Molecule Builder.</p>")
        self.research_topos_panel = widgets.VBox([
            widgets.HTML("<h4>TOPOS research through BASE</h4><p>Use your uploaded starting geometry or a documented seed assembled from your own monomers. Choose an installed operation; results retain the actual method, input and provider identities.</p>"),
            self.research_capabilities, self.btn_research_refresh, self.research_topos_operation,
            self.research_topos_engine, self.research_matrix_recipe, self.research_matrix_guidance, self.research_candidates, self.research_temperature,
            self.btn_research_fragment_states, self.research_fragment_states, self.btn_research_topos, self.research_status,
        ])
        old_topos = widgets.Accordion(children=[self.tab_topos])
        old_topos.set_title(0, "Advanced native conformer search")
        old_topos.selected_index = None
        self.tab_topos = widgets.VBox([self.research_topos_panel, old_topos])
        self.research_scan_method = widgets.Dropdown(options=[("HF (installation example)", "hf"),
            ("PBE-D4", "pbe-d4"), ("B3LYP-D4", "b3lyp-d4"), ("MP2", "mp2")],
            value="pbe-d4", description="Scan method:", style={'description_width': 'initial'})
        self.research_scan_basis = widgets.Dropdown(options=["sto-3g", "def2-svp", "def2-tzvp", "cc-pvdz", "aug-cc-pvdz"],
            value="def2-svp", description="Scan basis:", style={'description_width': 'initial'})
        self.research_scan_start = widgets.BoundedFloatText(value=3.0, min=.2, max=100, description="Start separation (Å):",
            style={'description_width': 'initial'})
        self.research_scan_end = widgets.BoundedFloatText(value=6.0, min=.2, max=100, description="End separation (Å):",
            style={'description_width': 'initial'})
        self.research_scan_points = widgets.BoundedIntText(value=5, min=2, max=20, description="Scan points:",
            style={'description_width': 'initial'})
        self.btn_research_torq = widgets.Button(description="Run TORQ potential energy scan", button_style="success", disabled=True)
        self.btn_research_torq.on_click(self._run_student_torq)
        self.btn_research_nbo = widgets.Button(description="Run NBO analysis", disabled=True)
        self.btn_research_nbo.on_click(lambda _: self._run_student_orbital_analysis("nbo_analysis"))
        self.btn_research_wiberg = widgets.Button(description="Run Löwdin Wiberg analysis", disabled=True)
        self.btn_research_wiberg.on_click(self._run_student_wiberg)
        self.btn_research_wiberg_nao = widgets.Button(description="Run NAO Wiberg analysis", disabled=True)
        self.btn_research_wiberg_nao.on_click(lambda _: self._run_student_orbital_analysis("wiberg_nao"))
        self.research_orbital_backend = widgets.Dropdown(options=[('No verified orbital backend', None)],
            description='Orbital backend:', style={'description_width': 'initial'}, disabled=True)
        self.research_orbital_backend.observe(lambda change: self._refresh_execution_gate(), names='value')
        self.research_bond_capability = widgets.HTML("<p>NBO and Wiberg calculations require an installed provider that returns authentic, hash-bound analysis. An unavailable provider disables those selections. Mayer, Löwdin and NAO-Wiberg bond definitions are distinct.</p>")
        self.tab_torq = widgets.VBox([
            widgets.HTML("<h4>TORQ research through BASE</h4><p>Rigid two-fragment scans translate the second monomer along the initial mass-center separation. They calculate each point and preserve all monomer internal coordinates. This operation does not optimize the scan points or claim a multidimensional surface.</p>"),
            self.research_scan_method, self.research_scan_basis,
            widgets.HBox([self.research_scan_start, self.research_scan_end]), self.research_scan_points,
            self.btn_research_torq, self.research_orbital_backend, widgets.HBox([self.btn_research_nbo, self.btn_research_wiberg, self.btn_research_wiberg_nao]),
            self.research_bond_capability,
        ])
        children = list(self.config_tabs.children)
        children[2:4] = [self.tab_topos, self.tab_torq]
        self.config_tabs.children = children
        self.research_energy_kind = widgets.Dropdown(options=[("Electronic energies", "electronic_energy"),
            ("Gibbs free energies", "gibbs_free_energy")], value="electronic_energy", description="Compare:")
        self.research_populations = widgets.Checkbox(value=False, description="Include minimum-based population model")
        self.research_isomer_choices = widgets.SelectMultiple(options=[], description="Calculated structures:",
            style={'description_width': 'initial'}, layout=widgets.Layout(width='95%', height='130px'))
        self.btn_research_compare = widgets.Button(description="Compare calculated isomers", disabled=True)
        self.btn_research_compare.on_click(self._compare_student_isomers)
        self.research_report_output = widgets.HTML("<p role='status'>Verified calculations produce energy tables, population models, potential-energy diagrams and available orbital/bond diagrams here. Starting XYZ coordinates alone do not supply those observations.</p>")
        self.research_report_download = widgets.HTML()
        advanced = widgets.Accordion(children=[self.view_modules])
        advanced.set_title(0, "Advanced module installation and validated handoff")
        advanced.selected_index = None
        self.view_modules = widgets.VBox([
            widgets.HTML("<h3>Research results</h3>"), self.research_report_output,
            self.research_isomer_choices, self.research_energy_kind, self.research_populations, self.btn_research_compare,
            self.research_report_download, advanced,
        ], layout=widgets.Layout(padding='20px'))
        self._refresh_research_capabilities()

    def _refresh_research_capabilities(self, b: Any = None) -> None:
        if not hasattr(self, "research_capabilities"):
            return
        self.btn_research_refresh.disabled = True
        def refresh() -> None:
            try:
                from cochem_base.interfaces.student_research import get_student_capabilities
                observations = get_student_capabilities(root=Path(self.module_root.value))
                def render() -> None:
                    self._research_capability_observations = {item["module_id"]: item for item in observations}
                    available = self._research_capability_observations.get("topos", {})
                    labels = {"energy": "Single-point energy", "gradient": "Energy and Cartesian gradient",
                        "optimize": "Optimize starting geometry", "search": "Find isomer candidates",
                        "frequency": "Harmonic frequencies", "thermochemistry": "Thermochemistry",
                        "association": "Monomer association search", "matrix": "Validated matrix optimization recipe"}
                    options = [(labels[operation], operation) for operation in available.get("operations", []) if operation in labels]
                    self.research_topos_operation.options = options or [("No installed research provider", "")]
                    self.research_topos_operation.disabled = not options
                    self.btn_research_topos.disabled = not options or self._actions_running or self._pipeline_running
                    torq = self._research_capability_observations.get("torq", {})
                    self.btn_research_torq.disabled = "research_scan" not in torq.get("operations", []) or self._actions_running or self._pipeline_running
                    self.btn_research_wiberg.disabled = "wiberg_lowdin" not in torq.get("operations", []) or self._actions_running or self._pipeline_running
                    self.btn_research_nbo.disabled = "nbo_analysis" not in torq.get("operations", []) or self._actions_running or self._pipeline_running
                    self.btn_research_wiberg_nao.disabled = "wiberg_nao" not in torq.get("operations", []) or self._actions_running or self._pipeline_running
                    definitions = torq.get("provider_capabilities", {}).get("scientific_apis", {})
                    reasons = {name: item.get("reason", item.get("scope", "No installed provider"))
                               for name, item in definitions.items() if isinstance(item, dict) and not item.get("available")}
                    if reasons:
                        self.research_bond_capability.value = "<ul>" + "".join(
                            f"<li>{html.escape(str(name))}: {html.escape(str(reason))}</li>" for name, reason in reasons.items()) + "</ul>"
                    self.research_capabilities.value = "<ul>" + "".join(
                        f"<li><b>{html.escape(item['module_id'].upper())}</b>: {html.escape(item.get('status', 'unavailable'))}; "
                        f"{html.escape(', '.join(item.get('operations', [])) or 'no reviewed scientific operation available')}. "
                        f"{html.escape(str(item.get('reason', '')))}</li>" for item in observations) + "</ul>"
                    self._refresh_research_engine_choices()
                    self._refresh_orbital_backend_choices()
                    self._refresh_execution_gate()
                    self.btn_research_refresh.disabled = False
                self._ui_call(render)
            except (ValueError, RuntimeError, OSError, ImportError) as exc:
                message = str(exc)
                self._ui_call(lambda: setattr(self.research_capabilities, "value", f"<p role='alert'>Research capabilities could not be checked: {html.escape(message)}</p>"))
                self._ui_call(lambda: setattr(self.btn_research_refresh, "disabled", False))
        self._research_capability_worker = threading.Thread(target=refresh, daemon=True)
        self._research_capability_worker.start()

    def _refresh_research_engine_choices(self) -> None:
        if not hasattr(self, "research_topos_engine"):
            return
        remote = self.calc_env_dropdown.value == "github-actions"
        orca_ready = (self._remote_engine_availability['orca'].get('provisionable', False)
                      if remote else licensed_engine_availability()['orca']['available'])
        options = [("xTB GFN2 screening", "xtb")]
        if orca_ready:
            options.append(("ORCA r2SCAN-3c", "orca"))
        previous = self.research_topos_engine.value
        self.research_topos_engine.options = options
        self.research_topos_engine.value = previous if previous in dict(options).values() else "xtb"
        from cochem_base.interfaces.student_research import student_matrix_recipes
        recipes = student_matrix_recipes(capabilities=list(self._research_capability_observations.values()))
        self._student_matrix_recipes = {item['row_id']: item for item in recipes if item['engine'] != 'orca' or orca_ready}
        choices = [(f"{row}: {item['method']} / {item['basis'] or 'built in'}", row)
                   for row, item in self._student_matrix_recipes.items()]
        current = self.research_matrix_recipe.value
        self.research_matrix_recipe.options = choices or [("No verified molecule-only recipe", "")]
        self.research_matrix_recipe.value = current if current in self._student_matrix_recipes else (choices[0][1] if choices else '')
        self.research_matrix_recipe.disabled = not choices

    def _refresh_orbital_backend_choices(self) -> None:
        if not hasattr(self, 'research_orbital_backend'):
            return
        torq = self._research_capability_observations.get('torq', {})
        definitions = torq.get('provider_capabilities', {}).get('scientific_apis', {})
        engines = set()
        for operation in ('nbo_analysis', 'wiberg_nao'):
            record = definitions.get(operation, {})
            if operation in torq.get('operations', []) and record.get('available') is True:
                engines.update(engine for engine in record.get('supported_engines', []) if engine in {'orca', 'pyscf'})
        remote = self.calc_env_dropdown.value == 'github-actions'
        orca_ready = (self._remote_engine_availability['orca'].get('provisionable', False)
                      if remote else licensed_engine_availability()['orca']['available'])
        if not orca_ready:
            engines.discard('orca')
        choices = [(engine.upper(), engine) for engine in sorted(engines)]
        previous = self.research_orbital_backend.value
        self.research_orbital_backend.options = choices or [('No verified orbital backend', None)]
        self.research_orbital_backend.value = previous if previous in engines else (choices[0][1] if choices else None)
        self.research_orbital_backend.disabled = not choices

    def _student_fragment_groups(self) -> list[list[int]]:
        from cochem_base.geometry.nuclide_geometry import parse_geometry_identity
        identity = parse_geometry_identity(self._student_current_xyz())
        record = self._student_uploads.get(self.student_geometry_choice.value)
        groups = record.get("fragments") if record else None
        if self.student_fragment_atoms.value.strip():
            groups = [[int(index.strip()) - 1 for index in group.split(",")]
                      for group in self.student_fragment_atoms.value.split(";")]
        if not groups:
            groups = detect_molecular_fragments(list(identity.elements), list(identity.coordinates_angstrom))
        flattened = [index for group in groups for index in group]
        if sorted(flattened) != list(range(len(identity.elements))):
            raise ValueError("Fragment membership must assign every atom exactly once")
        return [list(group) for group in groups]

    def _build_student_fragment_states(self, b: Any = None) -> None:
        try:
            groups = self._student_fragment_groups()
            current = self._student_uploads.get(self.student_geometry_choice.value) or {}
            states = current.get("fragment_states", [])
            controls, rows = [], []
            for index, group in enumerate(groups):
                state = states[index] if index < len(states) else {"charge": 0, "multiplicity": 1}
                charge = widgets.IntText(value=state["charge"], description=f"Monomer {index + 1} charge:", style={'description_width': 'initial'})
                spin = widgets.BoundedIntText(value=state["multiplicity"], min=1, max=21,
                    description=f"Monomer {index + 1} multiplicity:", style={'description_width': 'initial'})
                controls.append((group, charge, spin))
                rows.append(widgets.VBox([widgets.HTML(f"<p>Monomer {index + 1}: atoms {html.escape(', '.join(str(i + 1) for i in group))}</p>"), widgets.HBox([charge, spin])]))
            self._research_fragment_state_inputs = controls
            self.research_fragment_states.children = rows
        except (ValueError, RuntimeError) as exc:
            self.research_status.value = f"<p role='alert'>Monomer states require valid input: {html.escape(str(exc))}</p>"

    def _run_student_topos(self, b: Any = None) -> None:
        try:
            from cochem_base.interfaces.student_research import (
                SCHEMA,
                build_topos_matrix_request,
                build_topos_request,
            )
            geometry = self._student_current_xyz()
            operation = self.research_topos_operation.value
            if operation not in self._research_capability_observations.get("topos", {}).get("operations", []):
                raise ValueError("The installed TOPOS provider does not support this operation")
            engine = self.research_topos_engine.value
            fragments, states = None, None
            if operation == "association":
                fragments = self._student_fragment_groups()
                if not self._research_fragment_state_inputs or [row[0] for row in self._research_fragment_state_inputs] != fragments:
                    self._build_student_fragment_states()
                    raise ValueError("Confirm each displayed monomer charge and multiplicity, then run the association search")
                states = [{"atom_indices": group, "charge": charge.value, "multiplicity": spin.value}
                          for group, charge, spin in self._research_fragment_state_inputs]
                if sum(state["charge"] for state in states) != self.charge_input.value:
                    raise ValueError("Monomer charges must sum to the selected complex charge")
            if operation == 'matrix':
                row = self.research_matrix_recipe.value
                if row not in getattr(self, '_student_matrix_recipes', {}):
                    raise ValueError("Select a complete optimization recipe from the verified installed catalog")
                request = build_topos_matrix_request(geometry, row_id=row,
                    charge=self.charge_input.value, multiplicity=self.multiplicity_input.value,
                    capabilities=list(self._research_capability_observations.values()), options={
                        "threads": self.actions_cores.value, "memory_mb": self.actions_memory.value * self.actions_cores.value,
                        "budget_seconds": self.actions_timeout.value})
            else:
                request = build_topos_request(geometry, operation=operation,
                    charge=self.charge_input.value, multiplicity=self.multiplicity_input.value,
                    engine=engine, method="r2SCAN-3c" if engine == "orca" else "GFN2-xTB",
                    fragments=fragments, fragment_states=states, options={
                        "n_candidates": self.research_candidates.value if operation in {"search", "association"} else 1,
                        "threads": self.actions_cores.value, "memory_mb": self.actions_memory.value * self.actions_cores.value,
                        "budget_seconds": self.actions_timeout.value, "temperature_k": self.research_temperature.value})
            provider = {"schema_version": SCHEMA, "module": "topos", "operation": operation,
                "artifact": "inputs/starting-geometry.xyz", "artifact_sha256": hashlib.sha256(geometry.encode("utf-8")).hexdigest(),
                "options": {"topos_request": request}}
            self._run_student_provider(provider, geometry)
        except (ValueError, RuntimeError, OSError, ImportError) as exc:
            self.research_status.value = f"<p role='alert'>TOPOS research was not started: {html.escape(str(exc))}</p>"

    def _run_student_torq(self, b: Any = None) -> None:
        try:
            from cochem_base.geometry.nuclide_geometry import parse_geometry_identity
            from cochem_base.interfaces.student_research import SCHEMA
            from cochem_base.interfaces.torq_research import validate_scan_options
            if "research_scan" not in self._research_capability_observations.get("torq", {}).get("operations", []):
                raise ValueError("The installed TORQ provider does not support this scan")
            geometry = self._student_current_xyz()
            if self.research_scan_end.value <= self.research_scan_start.value:
                raise ValueError("Scan end separation must exceed its start")
            count = self.research_scan_points.value
            distances = [self.research_scan_start.value + (self.research_scan_end.value - self.research_scan_start.value) * index / (count - 1)
                         for index in range(count)]
            options = validate_scan_options({"method": {"name": self.research_scan_method.value, "basis": self.research_scan_basis.value},
                "charge": self.charge_input.value, "multiplicity": self.multiplicity_input.value,
                "fragments": self._student_fragment_groups(), "distances_angstrom": distances,
                "cores": self.actions_cores.value, "memory_mb": self.actions_memory.value * self.actions_cores.value},
                len(parse_geometry_identity(geometry).elements))
            provider = {"schema_version": SCHEMA, "module": "torq", "operation": "research_scan",
                "artifact": "inputs/starting-geometry.xyz", "artifact_sha256": hashlib.sha256(geometry.encode("utf-8")).hexdigest(),
                "options": options}
            self._run_student_provider(provider, geometry)
        except (ValueError, RuntimeError, OSError, ImportError) as exc:
            self.research_status.value = f"<p role='alert'>TORQ scan was not started: {html.escape(str(exc))}</p>"

    def _run_student_provider(self, provider: dict[str, Any], geometry: str) -> None:
        if self.calc_env_dropdown.value == "hpc":
            self._submit_student_hpc(provider=provider, geometry=geometry)
            self.research_status.value = "<p role='status'>Preparing the research request for the selected HPC scheduler. Track its queue state and retrieve verified results in the HPC panel.</p>"
            return
        if self.calc_env_dropdown.value == "github-actions":
            self._submit_student_actions(provider=provider)
            self.research_status.value = (
                "<p role='status'>Preparing this research request for the selected Actions route. Monitor its submission and calculation below; retrieve verified results when complete.</p>"
                if self._actions_running else f"<p role='alert'>Research request was not submitted: {html.escape(self.state.error_message)}</p>"
            )
            return
        if self._pipeline_running or self._topos_running or self._hpc_running or self._actions_running:
            raise ValueError("Wait for or cancel the current calculation before starting another")
        self._pipeline_cancellation.clear()
        self._student_research_running = True
        self._pipeline_running = True
        self.btn_cancel.disabled = False
        self.research_status.value = "<p role='status'>Running the installed scientific provider on the configured local host…</p>"
        self._refresh_execution_gate()
        def run() -> None:
            try:
                from cochem_base.config_loader import get_artifact_dir
                from cochem_base.interfaces.module_execution import ModuleOperationCancelled
                from cochem_base.interfaces.student_research import execute_provider_request
                root = get_artifact_dir() / "StudentResearch" / uuid.uuid4().hex
                path = root / provider["artifact"]
                path.parent.mkdir(parents=True, exist_ok=False)
                path.write_text(geometry, encoding="utf-8", newline="")
                result = execute_provider_request(provider, root, root / "results", root=Path(self.module_root.value),
                    cancel_event=self._pipeline_cancellation, resources={"cores": self.actions_cores.value,
                        "memory_mb": self.actions_memory.value * self.actions_cores.value, "budget_seconds": self.actions_timeout.value})
                def success() -> None:
                    self._last_module_result = result
                    self._load_student_research_report(root / "results")
                    self.research_status.value = "<p role='status'>Research calculation completed. Open Research results for retained tables and diagrams.</p>"
                self._ui_call(success)
            except ModuleOperationCancelled as exc:
                message = str(exc)
                self._ui_call(lambda: setattr(self.research_status, "value", f"<p role='status'>Research calculation cancelled: {html.escape(message)}. Owned native processes stopped; partial artifacts retain their provenance.</p>"))
            except (ValueError, RuntimeError, OSError) as exc:
                message = str(exc)
                self._ui_call(lambda: setattr(self.research_status, "value", f"<p role='alert'>Research calculation failed: {html.escape(message)}</p>"))
            finally:
                self._student_research_running = False
                self._pipeline_running = False
                self._ui_call(lambda: setattr(self.btn_cancel, "disabled", True))
                self._ui_call(self._refresh_execution_gate)
        self._research_worker = threading.Thread(target=run, daemon=True)
        self._research_worker.start()

    def _run_student_wiberg(self, b: Any = None) -> None:
        self._run_student_orbital_analysis("wiberg_lowdin")

    def _run_student_orbital_analysis(self, operation: str) -> None:
        try:
            from cochem_base.interfaces.student_research import SCHEMA
            if operation not in self._research_capability_observations.get("torq", {}).get("operations", []):
                raise ValueError("The installed TORQ provider does not support authentic " + operation)
            if self.research_scan_method.value == "mp2":
                raise ValueError("The installed Wiberg provider requires HF, PBE-D4 or B3LYP-D4; MP2 density is not supported")
            geometry = self._student_current_xyz()
            provider = {"schema_version": SCHEMA, "module": "torq", "operation": operation,
                "artifact": "inputs/starting-geometry.xyz", "artifact_sha256": hashlib.sha256(geometry.encode("utf-8")).hexdigest(),
                "options": {"method": {"name": self.research_scan_method.value, "basis": self.research_scan_basis.value},
                    "charge": self.charge_input.value, "multiplicity": self.multiplicity_input.value,
                    "cores": self.actions_cores.value, "memory_mb": self.actions_memory.value * self.actions_cores.value}}
            if operation in {'nbo_analysis', 'wiberg_nao'}:
                declaration = self._research_capability_observations.get('torq', {}).get('provider_capabilities', {}).get('scientific_apis', {}).get(operation, {})
                engine = self.research_orbital_backend.value
                if declaration.get('available') is not True or engine not in declaration.get('supported_engines', []):
                    raise ValueError('Choose an authentic provider-declared orbital backend; unavailable dependencies cannot be substituted')
                provider['options']['engine'] = engine
            self._run_student_provider(provider, geometry)
        except (ValueError, RuntimeError, OSError, ImportError) as exc:
            self.research_status.value = f"<p role='alert'>Orbital/bond analysis was not started: {html.escape(str(exc))}</p>"

    def _load_student_research_report(self, root: Path) -> None:
        from cochem_base.interfaces.student_reports import (
            discover_observations,
            load_reports,
            report_html,
        )
        reports = load_reports(root)
        observations = discover_observations(root)
        self._research_reports.extend(reports)
        existing = {(json.dumps(item.get("source", {}), sort_keys=True), item.get("energy_kind")) for item in self._research_observations}
        for item in observations:
            key = (json.dumps(item.get("source", {}), sort_keys=True), item.get("energy_kind"))
            if key not in existing:
                kind = "Gibbs free energy" if item.get("energy_kind") == "gibbs_free_energy" else "Electronic energy"
                item["label"] = f"{root.name[:36]} · {item['label']} · {kind}"
                self._research_observations.append(item)
                existing.add(key)
        chosen = set(self.research_isomer_choices.value)
        self.research_isomer_choices.options = [(item["label"], index) for index, item in enumerate(self._research_observations)]
        self.research_isomer_choices.value = tuple(index for _, index in self.research_isomer_choices.options
                                                   if index in chosen or not chosen)
        if reports:
            self.research_report_output.value = "\n".join(report_html(report) for report in self._research_reports)
        elif observations:
            self.research_report_output.value = f"<p role='status'>Retained {len(self._research_observations)} computed energy observations. Choose Compare calculated isomers for compatible structures.</p>"
        else:
            self.research_report_output.value = "<p role='status'>Calculation artifacts were retained. The provider returned no compatible scientific report observations; no diagram or population has been invented.</p>"
        self.btn_research_compare.disabled = not bool(self._research_observations)

    def _compare_student_isomers(self, b: Any = None) -> None:
        try:
            from cochem_base.config_loader import get_artifact_dir
            from cochem_base.interfaces.student_reports import (
                build_isomer_report,
                export_report,
                report_html,
            )
            observations = [self._research_observations[index] for index in self.research_isomer_choices.value
                            if self._research_observations[index].get("energy_kind") == self.research_energy_kind.value]
            report = build_isomer_report(observations, energy_kind=self.research_energy_kind.value,
                temperature_kelvin=self.research_temperature.value, populations=self.research_populations.value)
            self.research_report_output.value = report_html(report)
            paths = export_report(report, get_artifact_dir() / "StudentReports" / uuid.uuid4().hex)
            links = []
            for filename, path in paths.items():
                content = Path(path).read_bytes()
                media = "image/svg+xml" if filename.endswith(".svg") else "text/csv" if filename.endswith(".csv") else "application/json" if filename.endswith(".json") else "text/html"
                encoded = base64.b64encode(content).decode("ascii")
                links.append(f"<a download='{html.escape(filename)}' href='data:{media};base64,{encoded}'>Download {html.escape(filename)}</a>")
            self.research_report_download.value = "<p>" + " · ".join(links) + "</p>"
        except (ValueError, RuntimeError, OSError) as exc:
            self.research_report_output.value = f"<p role='alert'>Scientific comparison requires complete compatible evidence: {html.escape(str(exc))}</p>"

    def _invalidate_actions_job(self, change: Any = None) -> None:
        self._last_actions_job = None
        if hasattr(self, 'actions_job_download'):
            self.actions_job_download.value = ""

    def _actions_repository(self) -> str:
        repository = self.gh_repo_input.value.strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9._-]*", repository):
            raise ValueError("Confirm your private project or instructor-provided assignment repository as OWNER/REPOSITORY.")
        return repository

    def _local_engine_choices(self) -> list[tuple[str, str | None]]:
        """Hide unaudited licensed choices while retaining free-engine setup paths."""
        available = licensed_engine_availability()
        self._licensed_engine_availability = available
        if hasattr(self, 'licensed_engine_status'):
            descriptions = []
            for engine, observation in available.items():
                descriptions.append(
                    f"<li><b>{engine.upper()}:</b> "
                    + ("available for audited calculations" if observation['available'] else
                       "unavailable; dependent calculations disabled. " + html.escape(observation['reason']))
                    + "</li>"
                )
            self.licensed_engine_status.value = (
                "<p>Licensed engines are optional and strongly recommended. BASE ingestion, inspection and free-engine setup remain available.</p>"
                "<ul>" + "".join(descriptions) + "</ul>"
            )
        choices = [("Choose an available calculation engine", None)]
        if available['orca']['available']:
            choices.append(("ORCA", "ORCA"))
        if available['cfour']['available']:
            from cochem_base.interfaces.scientific_jobs import calculation_capability
            capability = calculation_capability(CalculationMatrixConfig(
                geometry='H 0 0 0\nH 0 0 0.74', engine='cfour', method='HF', basis_set='STO-3G',
                product_class=None, is_opt=False, is_freq=False,
            ))
            if capability.adapter_status == 'connected':
                choices.append(("CFOUR", "CFOUR"))
            elif hasattr(self, 'licensed_engine_status'):
                self.licensed_engine_status.value += (
                    "<p>CFOUR runtime authority is present; scientific adapter integration is pending. "
                    + html.escape(capability.reason) + "</p>"
                )
        choices.extend((("xTB", "XTB"), ("PySCF (RHF single point)", "PYSCF")))
        return choices

    def _refresh_engine_choices(self) -> None:
        """Refresh capabilities after setup or changing the execution target."""
        if not hasattr(self, 'matrix_engine'):
            return
        remote = self.calc_env_dropdown.value == 'github-actions'
        self._local_engine_options = tuple(self._local_engine_choices())
        selected = self.matrix_engine.value
        options = (
            tuple([("Choose a calculation engine", None)]
                  + [(engine.upper() + " (verified archive access)", engine.upper())
                     for engine, item in self._remote_engine_availability.items() if item.get("provisionable") is True]
                  + [("xTB (free Actions optimization)", "XTB")])
            if remote else self._local_engine_options
        )
        values = {value for _, value in options}
        self.matrix_engine.options = options
        self.matrix_engine.value = selected if selected in values else None
        if remote:
            self.licensed_engine_status.value = (
                "<p>ORCA and CFOUR are optional and strongly recommended. A genuine Actions check must verify archive access before each dependent choice is enabled. "
                "Archive access does not establish installation or scientific acceptance; the calculation worker verifies its actual runtime before executing. "
                "Local engine availability does not establish GitHub Actions availability.</p>"
            )
        if hasattr(self, "slurm_panel"):
            self.slurm_panel.layout.display = "" if self.calc_env_dropdown.value == "hpc" else "none"
        if hasattr(self, 'btn_execute'):
            self._refresh_execution_gate()

    def _automatic_remote_checks_enabled(self) -> bool:
        configured = os.environ.get("COCHEM_STUDENT_AUTO_REMOTE_CHECK", "").lower()
        if configured:
            return configured in {"1", "true", "yes"}
        if os.environ.get("CODESPACES", "").lower() == "true":
            return True
        try:
            from IPython import get_ipython
            return getattr(get_ipython(), "kernel", None) is not None
        except ImportError:
            return False

    def _check_remote_engines(self, b: Any = None) -> None:
        if self._remote_probe_running or self.calc_env_dropdown.value != "github-actions":
            return
        try:
            repository = self._actions_repository()
            branch = self.gh_branch_input.value.strip() or "main"
            probe_target = (repository, branch)
        except ValueError as exc:
            self.remote_engine_status.value = f"<p role='status'>Remote engine check requires your assignment repository: {html.escape(str(exc))}</p>"
            return
        self._remote_probe_running = True
        self.btn_remote_engine_check.disabled = True
        self.btn_remote_engine_cancel.disabled = False
        self.remote_engine_status.value = "<p role='status' aria-live='polite'>Checking approved ORCA and CFOUR archive access on GitHub Actions. BASE remains usable with free engines.</p>"
        def check() -> None:
            try:
                from cochem_base.config_loader import get_artifact_dir
                from cochem_base.interfaces.student_actions import StudentActionsClient
                artifacts = get_artifact_dir()
                client = StudentActionsClient(repository, branch=branch,
                    repository_root=Path(os.environ.get("COCHEM_ASSIGNMENT_ROOT", str(_REPO_ROOT))), artifact_dir=artifacts)
                self._remote_probe_client = client
                pending = []
                cache = artifacts / 'StudentActions' / 'submissions'
                if cache.is_dir() and not cache.is_symlink():
                    for path in cache.glob('*.json'):
                        try:
                            if path.is_symlink() or path.stat().st_size > 64 * 1024:
                                continue
                            cached = json.loads(path.read_text(encoding='utf-8'))
                            if cached.get('request_kind') == 'capability_probe' and (cached.get('repository'), cached.get('branch')) == probe_target and cached.get('status') not in {'completed', 'rejected'}:
                                pending.append((path.stat().st_mtime, cached))
                        except (ValueError, OSError, TypeError):
                            continue
                submission = max(pending, key=lambda item: item[0])[1] if pending else client.check_engines(engines=["orca", "cfour"])
                self._remote_probe_submission = submission
                deadline = time.monotonic() + 20 * 60
                while True:
                    current = client.status(submission)
                    submission = current
                    self._remote_probe_submission = current
                    if current.get("status") == "completed":
                        break
                    if time.monotonic() >= deadline:
                        client.cancel(submission)
                        raise RuntimeError("The remote engine check exceeded 20 minutes; cancellation was requested. Retry after the workflow stops.")
                    time.sleep(3)
                directory = artifacts / "RemoteEngineChecks" / f"{submission['request_id']}-{uuid.uuid4().hex}"
                receipt = client.download_results(submission, directory)
                report = receipt["report"]
                if report.get("capability_probe_performed") is not True or report.get("operation_performed") is not False:
                    raise ValueError("The workflow did not return a verified licensed-engine readiness report")
                engines = report.get("result", {}).get("engines", {})
                if set(engines) != {"orca", "cfour"}:
                    raise ValueError("The remote engine check returned an incomplete engine inventory")
                def success() -> None:
                    if (self.gh_repo_input.value.strip(), self.gh_branch_input.value.strip() or "main") != probe_target:
                        return
                    self._remote_engine_target = probe_target
                    self._remote_engine_availability = engines
                    self.remote_engine_status.value = "<ul>" + "".join(
                        f"<li><b>{html.escape(engine.upper())}:</b> {html.escape(str(item.get('status', 'unavailable')))}. "
                        f"{html.escape(str(item.get('reason', '')))}</li>" for engine, item in engines.items()) + "</ul><p>Provisionable means approved archive access was verified. Each calculation still verifies installation, Stage 0 authority and native execution.</p>"
                    self._refresh_engine_choices()
                    self._refresh_research_capabilities()
                self._ui_call(success)
            except (ValueError, RuntimeError, OSError, ImportError, AttributeError) as exc:
                message = str(exc)
                self._ui_call(lambda: setattr(self.remote_engine_status, "value",
                    f"<p role='alert'>Remote licensed-engine access was not verified: {html.escape(message)}. Those methods remain unavailable; free-engine calculations and geometry ingestion remain available.</p>"))
            finally:
                def finished() -> None:
                    self._remote_probe_running = False
                    self.btn_remote_engine_check.disabled = False
                    self.btn_remote_engine_cancel.disabled = True
                    if (self.gh_repo_input.value.strip(), self.gh_branch_input.value.strip() or "main") != probe_target and self._automatic_remote_checks_enabled():
                        self._check_remote_engines()
                self._ui_call(finished)
        self._remote_probe_worker = threading.Thread(target=check, daemon=True)
        self._remote_probe_worker.start()

    def _cancel_remote_engine_check(self, b: Any = None) -> None:
        if not self._remote_probe_running or self._remote_probe_client is None or self._remote_probe_submission is None:
            return
        self.btn_remote_engine_cancel.disabled = True
        def cancel() -> None:
            try:
                self._remote_probe_client.cancel(dict(self._remote_probe_submission))
                self._ui_call(lambda: setattr(self.remote_engine_status, 'value', '<p role="status">Remote engine check cancellation requested. BASE waits for GitHub confirmation; free engines remain available.</p>'))
            except (ValueError, RuntimeError, OSError) as exc:
                message = str(exc)
                self._ui_call(lambda: setattr(self.remote_engine_status, 'value', f'<p role="alert">Engine check cancellation could not be confirmed: {html.escape(message)}.</p>'))
        self._remote_probe_cancel_worker = threading.Thread(target=cancel, daemon=True)
        self._remote_probe_cancel_worker.start()

    def _refresh_actions_guidance(self, change: Any = None) -> None:
        repository = self.gh_repo_input.value.strip()
        target = (repository, self.gh_branch_input.value.strip() or "main")
        if self._remote_engine_target != target:
            self._remote_engine_availability = {engine: {"status": "unknown", "provisionable": False,
                "reason": "Archive access has not been verified for this assignment repository and branch."}
                for engine in ("orca", "cfour")}
            self.remote_engine_status.value = "<p role='status'>Licensed-engine archive access has not been checked for this assignment repository and branch.</p>"
        valid_repository = bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9._-]*", repository))
        guide_repository = repository if valid_repository else "ProfJJK-CoChem/CoChem-BASE"
        branch = self.gh_branch_input.value.strip() or "main"
        guide = f"https://github.com/{guide_repository}/blob/{quote(branch, safe='')}/.docs/GitHub_Classroom_ORCA_Setup.md"
        student_guide = f"https://github.com/{guide_repository}/blob/{quote(branch, safe='')}/.docs/Student_Research_No_Code.md"
        cfour_guide = f"https://github.com/{guide_repository}/blob/{quote(branch, safe='')}/.docs/CFOUR_Actions_Setup.md"
        self.gh_guidance.value = (
            "<h4>GitHub Actions: research project setup</h4>"
            "<p>Use your own private project or an organization-owned assignment provided by your Classroom50 instructor. "
            "For a personal project, use <b>Lab Access</b> above to request approved module and optional engine access. "
            "For an organization-owned assignment, your instructor configures the applicable repository access. "
            "Students do not enter tokens or binary download links in this interface.</p>"
            "<ol><li>Confirm the assignment repository and branch shown here.</li>"
            "<li>Open <b>No Code Matrix</b>, upload your Avogadro starting XYZ, and confirm charge, multiplicity and calculation method.</li>"
            "<li>Select <b>Run on GitHub Actions</b>. BASE checks your access, submits the request and shows its progress here.</li>"
            "<li>After successful completion, select <b>Retrieve and inspect results</b>. BASE verifies and imports the result bundle. "
            "You can also download the bundle for your research records.</li></ol>"
            f"<p><a href='{student_guide}#start-your-workspace' target='_blank' rel='noopener'>Student quick start</a> · "
            f"<a href='{guide}#instructor-setup' target='_blank' rel='noopener'>Instructor setup</a> · "
            f"<a href='{guide}#troubleshooting' target='_blank' rel='noopener'>Troubleshooting</a></p>"
            f"<p><a href='{cfour_guide}' target='_blank' rel='noopener'>CFOUR setup and calculation instructions</a></p>"
        )
        remote = hasattr(self, 'calc_env_dropdown') and self.calc_env_dropdown.value == "github-actions"
        if hasattr(self, 'matrix_engine'):
            self._refresh_engine_choices()
            self._refresh_research_engine_choices()
            self._refresh_orbital_backend_choices()
            self.matrix_engine.tooltip = (
                "Run an ORCA, CFOUR or free xTB request without a local engine. The approved workflow provisions and authorizes its own engine."
                if remote else "Native execution requires the complete eleven-phase setup audit on the configured host."
            )
        self.actions_job_options.layout.display = '' if remote else 'none'
        self.native_job_options.layout.display = '' if not remote and hasattr(self, 'matrix_engine') and self.matrix_engine.value == 'ORCA' else 'none'
        if hasattr(self, 'actions_controls'):
            self.actions_controls.layout.display = '' if remote else 'none'
        if hasattr(self, 'artifact_output_path'):
            self.artifact_output_path.layout.display = 'none'
        if hasattr(self, 'output_destination_guidance'):
            self.output_destination_guidance.value = (
                "<h4>Research request</h4><p>BASE submits your uploaded geometry and calculation request directly. "
                "Save configuration provides an optional reproducibility copy.</p>"
                if remote else "<h4>Artifact Output Configuration</h4><p>Saved configurations use &lt;Output Dir&gt;/&lt;Project Name&gt;/. "
                "Each calculation writes logs and results below &lt;Output Dir&gt;/GUI/run_…/.</p>"
            )
        if hasattr(self, 'execution_description'):
            self.execution_description.value = (
                "<p>Run the selected ORCA, CFOUR or free xTB operation on GitHub Actions. "
                "BASE monitors its workflow and retrieves verified calculation logs and scientific results.</p>"
                if remote else "<p>Run ORCA, supported closed-shell CFOUR calculations, xTB optimization, or a PySCF RHF single point on the configured host. "
                "Screening carries no product accuracy certification. TOPOS and TORQ use their separate runners.</p>"
            )
        if hasattr(self, 'execution_description') and self.calc_env_dropdown.value == 'hpc':
            self.execution_description.value = "<p>Submit the selected native or ecosystem operation to the configured Slurm/PBS queue. Fresh Stage 0 inside the allocated compute node authorizes its engines. BASE monitors the scheduler and verifies retained results; scientific workloads do not run on the interface/login host.</p>"
        self.calculation_environment_status.value = (
            "<p><b>Calculation target: GitHub Actions.</b> BASE submits, monitors and retrieves your calculation. "
            f"<a href='{student_guide}#run-your-calculation' target='_blank' rel='noopener'>Course instructions</a></p>"
            if remote else "<p>Calculation target: the configured Slurm/PBS scheduler. Use the HPC panel for queue resources, status and results.</p>" if self.calc_env_dropdown.value == "hpc" else "<p>Calculation target: the configured local execution host.</p>"
        )
        self._invalidate_actions_job()
        if hasattr(self, 'btn_execute'):
            self._refresh_execution_gate()
        if remote and valid_repository and self._remote_engine_target != target and self._automatic_remote_checks_enabled():
            self._check_remote_engines()

    def _detect_environment(self) -> Tuple[bool, str, bool, bool]:
        """Display measured, signed registry state; individual phase files are insufficient."""
        from cochem_base.core.cochem_core_registry_manager import (
            RegistryError,
            load_system_config,
        )
        try:
            registry = load_system_config()
        except (RegistryError, ValueError, OSError) as exc:
            self.state.error_message = f"Execution registry is not ready: {exc}"
            return False, "Not Initialized", False, False
        target = registry.environment.os_target
        environment = target.value if hasattr(target, 'value') else str(target)
        scheduler = registry.hpc.scheduler.lower()
        is_hpc = scheduler in {'slurm', 'pbs', 'sge'}
        if is_hpc:
            environment += f" / {scheduler.upper()}"
        environment += f" [{registry.status}]"
        complete = registry.stage0 is not None
        if not complete:
            environment += " [Full bootstrap evidence unavailable]"
        return complete, environment, is_hpc, scheduler == 'slurm'

    def _on_view_change(self, change: Any) -> None:
        new_view: str = change['new']
        for name, button in (("install", self.btn_install), ("matrix", self.btn_matrix),
                             ("inspector", self.btn_inspector), ("modules", self.btn_modules), ("periodic", self.btn_periodic),
                             ("inputs", self.btn_inputs)):
            button.button_style = "primary" if name == new_view else ""
        if new_view == 'install':
            self.main_content.children = [self.view_install]
        elif new_view == 'matrix':
            self.main_content.children = [self.view_matrix]
        elif new_view == 'inspector':
            self.main_content.children = [self.view_inspector]
        elif new_view == 'modules':
            self.main_content.children = [self.view_modules]
        elif new_view == 'periodic':
            self.main_content.children = [self.view_periodic]
        elif new_view == 'inputs':
            self.main_content.children = [self.view_inputs]

    def _inspect_periodic_input(self, b: Any = None) -> None:
        try:
            structure = self._selected_periodic_structure()
            self._periodic_structure = structure
            rows = "".join("<tr><td>" + html.escape(symbol) + "</td>" +
                           "".join(f"<td>{value:.12g}</td>" for value in position) + "</tr>"
                           for symbol, position in zip(structure.elements, structure.coordinates_fractional, strict=True))
            self.periodic_structure_status.value = (
                f"<p role='status'>Validated periodic structure: {len(structure.elements)} atoms; three periodic boundaries.</p>"
                f"<p>Source SHA-256: <code>{structure.source.source_sha256}</code><br/>Structure SHA-256: <code>{structure.source.structure_sha256}</code></p>"
                "<p>Cell vectors (Å):</p><pre>" + html.escape(json.dumps(structure.cell_angstrom)) + "</pre>"
                "<table><caption>Fractional coordinates</caption><thead><tr><th scope='col'>Element</th><th scope='col'>a</th><th scope='col'>b</th><th scope='col'>c</th></tr></thead><tbody>" + rows + "</tbody></table>"
            )
        except (ValueError, OSError, RuntimeError) as exc:
            self._periodic_structure = None
            self.periodic_structure_status.value = f"<p role='alert'>Periodic structure was not accepted: {html.escape(str(exc))}</p>"

    def _selected_periodic_structure(self) -> Any:
        from cochem_base.calc.periodic import PeriodicStructure, ingest_periodic_structure
        receipt = self._input_library.get(self._input_selectors['periodic'].value)
        if receipt is None:
            return ingest_periodic_structure(self.periodic_input_path.value)
        content = Path(receipt['path']).read_bytes()
        if hashlib.sha256(content).hexdigest() != receipt['sha256']:
            raise ValueError('Retained periodic structure hash changed')
        structure = PeriodicStructure.model_validate(receipt['metadata']['validated_periodic_structure'])
        if structure.source.source_sha256 != receipt['sha256'] or structure.source.source_filename != receipt['filename']:
            raise ValueError('Periodic structure receipt disagrees with its preserved original')
        return structure

    def _prepare_periodic_config(self) -> Path:
        import uuid

        from cochem.core.context import assert_writable_path

        structure = self._selected_periodic_structure()
        if self.periodic_settings_path.value.strip():
            # Compatibility for existing native callers; students use typed controls.
            settings = json.loads(Path(self.periodic_settings_path.value).expanduser().read_text(encoding="utf-8"))
            if not isinstance(settings, dict):
                raise ValueError("PAW calculation settings must be a JSON object")
        else:
            settings = self._periodic_settings_from_form()
        config = CalculationMatrixConfig.model_validate(structure.to_calculation_config(settings))
        root = Path(self.periodic_output_path.value).expanduser().resolve()
        assert_writable_path(root)
        run = root / f"run_{uuid.uuid4().hex}"
        run.mkdir(parents=True)
        config_path = run / "matrix_config.json"
        config_path.write_text(config.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return config_path

    def _save_periodic_config(self, b: Any = None) -> None:
        try:
            target = self._prepare_periodic_config()
            self.periodic_structure_status.value += f"<p role='status'>Saved periodic calculation request: <code>{html.escape(str(target))}</code></p>"
        except (ValueError, OSError, RuntimeError) as exc:
            self.periodic_structure_status.value += f"<p role='alert'>Periodic request was not saved: {html.escape(str(exc))}</p>"

    def _execute_periodic_pipeline(self, b: Any = None) -> None:
        if self.calc_env_dropdown.value == "hpc":
            try:
                target = self._prepare_periodic_config()
                calculation = json.loads(target.read_text(encoding="utf-8"))
                self._submit_student_hpc(calculation_override=calculation)
            except (ValueError, RuntimeError, OSError) as exc:
                self.state.error_message = str(exc)
            return
        if self.calc_env_dropdown.value == "github-actions":
            try:
                config_path = self._prepare_periodic_config()
                configuration = json.loads(config_path.read_text(encoding='utf-8'))
                from cochem_base.geometry.nuclide_geometry import parse_geometry_identity
                identity = parse_geometry_identity(configuration['geometry'])
                configuration['geometry'] = str(len(identity.elements)) + '\nUploaded periodic structure; Cartesian angstrom\n' + configuration['geometry'] + '\n'
                structure = self._input_library.get(self._input_selectors['periodic'].value)
                if structure is None:
                    raise ValueError('Select a validated uploaded periodic structure for hosted execution')
                content = Path(structure['path']).read_bytes()
                if hashlib.sha256(content).hexdigest() != structure['sha256']:
                    raise ValueError('Retained periodic structure hash changed')
                pseudopotentials = {}
                for symbol, chooser in self._paw_pseudopotential_choices.items():
                    item = self._input_library[chooser.value]
                    raw = Path(item['path']).read_bytes()
                    if hashlib.sha256(raw).hexdigest() != item['sha256']:
                        raise ValueError('Retained pseudopotential hash changed for ' + symbol)
                    pseudopotentials[symbol] = {'filename': item['filename'], 'sha256': item['sha256'], 'content': raw}
                periodic_inputs = {'structure': {'filename': structure['filename'],
                    'format': Path(structure['path']).suffix.lstrip('.').lower(), 'content': content},
                    'pseudopotentials': pseudopotentials}
                self._submit_student_actions(calculation_override=configuration, periodic_inputs=periodic_inputs)
            except (ValueError, OSError, RuntimeError, KeyError) as exc:
                self.state.error_message = str(exc)
            return
        if self._pipeline_running or self._hpc_running or self._topos_running or self._installation_running:
            self.state.error_message = "Wait for the active operation before starting a periodic calculation"
            return
        try:
            target = self._prepare_periodic_config()
        except (ValueError, OSError, RuntimeError) as exc:
            self.state.error_message = str(exc)
            return
        self._pipeline_cancellation.clear()
        self._pipeline_running = True
        self.btn_periodic_run.disabled = True
        self.btn_periodic_cancel.disabled = False
        self.btn_cancel.disabled = False
        self.state.system_status = "Running periodic calculation..."
        self.telemetry_output.clear_output()
        self.calculation_result.value = "<p role='status'>Periodic calculation is running.</p>"
        self._pipeline_worker = threading.Thread(target=self._pipeline_thread, args=(target,), daemon=True)
        self._pipeline_worker.start()

    def _refresh_module_capabilities(self, b: Any = None) -> None:
        from cochem_base.interfaces.module_execution import installed_module_status
        from cochem_base.interfaces.module_registry import list_module_capabilities
        self.module_capabilities.value = "<p role='status'>Checking module installations…</p>"
        root = Path(self.module_root.value)
        self.btn_module_refresh.disabled = True

        def refresh() -> None:
            try:
                managed = {entry['module_id']: entry for entry in installed_module_status(root)}
                rows = []
                for item in list_module_capabilities():
                    state = item.status.value.replace("_", " ")
                    if item.module_id in managed:
                        observed = managed[item.module_id]
                        state = observed['status'].replace('_', ' ')
                        if observed['operations']:
                            state += ': ' + ', '.join(observed['operations'])
                    rows.append(f"<tr><td>{html.escape(item.name)}</td><td>{html.escape(state)}</td><td>{html.escape(item.responsibility)}</td></tr>")
                self.module_capabilities.value = (
                    "<table><caption>Observed module availability</caption><thead><tr><th scope='col'>Module</th><th scope='col'>Status</th><th scope='col'>Responsibility</th></tr></thead><tbody>"
                    + "".join(rows) + "</tbody></table>")
            except Exception as exc:
                self.module_capabilities.value = f"<p role='alert'>Module status check failed: {html.escape(str(exc))}</p>"
            finally:
                self.btn_module_refresh.disabled = False
        self._module_refresh_worker = threading.Thread(target=refresh, daemon=True)
        self._module_refresh_worker.start()

    def _install_selected_module(self, b: Any = None) -> None:
        from scripts.manage_modules import DEFAULT_MANIFEST, install_module, load_manifest
        name = self.module_recipient.value
        spec = load_manifest(DEFAULT_MANIFEST)["modules"].get(name)
        if spec is None or spec['distribution'] is None or spec.get('install_blocker'):
            self.module_install_status.value = "<p role='alert'>This recipient has no installable package in the approved catalog. Source download is available through the module CLI where catalogued.</p>"
            return
        root = Path(self.module_root.value).expanduser()
        self.btn_module_install.disabled = True
        self.module_install_status.value = "<p role='status'>Installing the pinned module in its own environment…</p>"

        def install() -> None:
            try:
                receipt = install_module(name, spec, root)
                self.module_install_status.value = f"<p role='status'>{html.escape(name)} installed at revision {html.escape(receipt['revision'])}.</p>"
                self._refresh_module_capabilities()
            except Exception as exc:
                self.module_install_status.value = f"<p role='alert'>Module installation failed: {html.escape(str(exc))}</p>"
            finally:
                self.btn_module_install.disabled = False
        self._module_worker = threading.Thread(target=install, daemon=True)
        self._module_worker.start()

    def _run_module_geometry(self, b: Any = None) -> None:
        import uuid

        from cochem_base.interfaces.artifact_handoff import prepare_module_handoff
        from cochem_base.interfaces.module_execution import execute_module_handoff
        name = self.module_recipient.value
        artifact = self.module_artifact.value
        if self.calc_env_dropdown.value in {"hpc", "github-actions"}:
            from cochem_base.interfaces.student_research import SCHEMA
            path = Path(artifact)
            if path.suffix.lower() != '.xyz':
                self.module_handoff_status.value = "<p role='alert'>Managed geometry analysis requires a retained single-frame molecular geometry. Select it from the Input library.</p>"
                return
            text = path.read_text(encoding='utf-8')
            provider = {'schema_version': SCHEMA, 'module': name.lower(), 'operation': 'geometry_analysis',
                'artifact': 'inputs/starting-geometry.xyz', 'artifact_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(), 'options': {}}
            self._run_student_provider(provider, text)
            return
        destination = Path(self.module_output.value).expanduser() / f"execution_{uuid.uuid4().hex}"
        root = Path(self.module_root.value).expanduser()
        self.btn_module_run.disabled = True
        self.module_handoff_status.value = "<p role='status'>Running geometry analysis…</p>"

        def run() -> None:
            try:
                prepare_module_handoff(name, artifact, destination / 'handoff', operation='geometry_analysis')
                result = execute_module_handoff(destination / 'handoff/handoff.json', destination / 'result', root=root)
                self._last_module_result = result
                self.module_handoff_status.value = (
                    f"<p role='status'>Geometry analysis completed for {html.escape(name)}.</p>"
                    f"<p>{html.escape(result['scope'])}</p><p>Result: <code>{html.escape(str(destination / 'result/result.json'))}</code></p>"
                    f"<pre>{html.escape(json.dumps(result['operation_report'], indent=2, allow_nan=False))}</pre>")
            except Exception as exc:
                self.module_handoff_status.value = f"<p role='alert'>Module operation failed: {html.escape(str(exc))}</p>"
            finally:
                self.btn_module_run.disabled = False
        self._module_worker = threading.Thread(target=run, daemon=True)
        self._module_worker.start()

    def _prepare_module_handoff(self, b: Any = None) -> None:
        import base64
        import io
        import uuid
        import zipfile

        from cochem_base.interfaces.artifact_handoff import (
            load_module_handoff,
            prepare_module_handoff,
        )

        self.btn_module_handoff.disabled = True
        try:
            destination = Path(self.module_output.value).expanduser() / f"handoff_{uuid.uuid4().hex}"
            handoff = prepare_module_handoff(
                self.module_recipient.value, self.module_artifact.value, destination,
                operation=self.module_operation.value.strip(),
            )
            manifest = destination / "handoff.json"
            load_module_handoff(manifest)
            self._last_module_handoff_path = manifest
            message = (
                f"<p role='status'>Handoff prepared for {html.escape(handoff.capability.name)}. Pending integration; no scientific job was submitted.</p>"
                f"<p>Package: <code>{html.escape(str(destination))}</code><br/>Source SHA-256: <code>{handoff.artifact.sha256}</code></p>"
            )
            if handoff.artifact.size_bytes <= 20 * 1024 * 1024:
                archive = io.BytesIO()
                with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as package:
                    package.write(manifest, "handoff.json")
                    package.write(destination / handoff.artifact.filename, handoff.artifact.filename)
                encoded = base64.b64encode(archive.getvalue()).decode("ascii")
                message += f"<a download='cochem-{html.escape(handoff.module_id)}-handoff.zip' href='data:application/zip;base64,{encoded}'>Download validated handoff package</a>"
            self.module_handoff_status.value = message
        except (ValueError, OSError, RuntimeError) as exc:
            self.module_handoff_status.value = f"<p role='alert'>Handoff was not prepared: {html.escape(str(exc))}</p>"
        finally:
            self.btn_module_handoff.disabled = False

    def _on_status_change(self, change: Any) -> None:
        safe_val = html.escape(str(change['new']))
        self.header_status.value = f"<b role='status' aria-live='polite'>[System: {safe_val}]</b>"

    def _on_environment_change(self, change: Any) -> None:
        safe_val = html.escape(str(change['new']))
        self.header_env.value = f"<i>Environment: {safe_val}</i>"

    def _update_footer(self, err: Any) -> None:
        if not err:
            self.footer_message.value = ""
            if hasattr(self, 'telemetry_accordion'):
                self.telemetry_accordion.layout.display = 'none'
            return

        guidance = ""
        telemetry = None
        if hasattr(err, "to_pedagogical_guidance"):
            try:
                guidance = err.to_pedagogical_guidance()
            except Exception:
                guidance = str(err)
        else:
            guidance = str(err)

        if hasattr(err, "to_diagnostic_telemetry"):
            try:
                telemetry = err.to_diagnostic_telemetry()
            except Exception:
                telemetry = None

        safe_guidance = html.escape(str(guidance))
        self.footer_message.value = f'<div role="alert" style="color: #721c24; background-color: #f8d7da; padding: 10px; border: 1px solid #f5c6cb; border-radius: 5px; width: 100%;"><b>Guidance:</b> {safe_guidance}</div>'

        if hasattr(self, 'telemetry_accordion') and hasattr(self, 'telemetry_html'):
            if telemetry:
                telemetry_str = html.escape(json.dumps(telemetry, indent=2))
                self.telemetry_html.value = f"<pre style='font-size: 11px; max-height: 200px; overflow-y: auto;'>{telemetry_str}</pre>"
                self.telemetry_accordion.layout.display = 'block'
            else:
                self.telemetry_accordion.layout.display = 'none'


    def _on_error_change(self, change: Any) -> None:
        self._update_footer(change['new'])

    def _invalidate_installation_data(self, change: Any = None) -> None:
        self._install_input_artifact = None
        self.run_install_btn.disabled = self._installation_running
        self.install_data_status.value = "<p>Validate the selected scientific bundle to use its data. It is optional for environment setup.</p>"

    def _validate_installation_data(self, b: Any = None) -> bool:
        from cochem_base.spectroscopy.artifacts import load_hessian_artifact

        try:
            path = Path(self.install_data_path.value.strip())
            if path.suffix.lower() not in {".h5", ".hdf5", ".npz"}:
                raise ValueError("Select a .h5 or .npz scientific bundle containing symbols, coordinates_angstrom, hessian_hartree_bohr2 and source")
            artifact = load_hessian_artifact(path)
            self._install_input_artifact = artifact
            self.install_data_status.value = (
                f"<p role='status'>Scientific input validated: {html.escape(artifact.source)}<br/>"
                f"SHA-256: <code>{artifact.sha256}</code></p>"
            )
            self.run_install_btn.disabled = self._installation_running
            return True
        except (ValueError, OSError, RuntimeError) as exc:
            self._install_input_artifact = None
            self.run_install_btn.disabled = self._installation_running
            self.install_data_status.value = f"<p role='alert'>Scientific input was not accepted: {html.escape(str(exc))}</p>"
            return False

    def _run_installation(self, b: Any) -> None:
        if self.calc_env_dropdown.value == "github-actions":
            self._refresh_actions_guidance()
            self.state.system_status = "Actions setup instructions"
            self.state.error_message = ""
            return
        if self._installation_running:
            return
        if self.install_data_path.value.strip() and self._install_input_artifact is None:
            self._validate_installation_data()
        if self._topos_running or self._pipeline_running:
            self.state.error_message = "Wait for the active calculation before changing the execution environment."
            return
        self._installation_running = True
        self.run_install_btn.disabled = True
        self.state.system_status = 'Installing...'
        self.install_output.clear_output()
        request = {
            "artifact": self._install_input_artifact,
            "license_mode": self.license_mode.value,
            "calculation_environment": self.calc_env_dropdown.value,
            "interaction_environment": self.interact_env_dropdown.value,
            "required_disk_gb": self.install_min_disk.value,
        }
        self._installation_worker = threading.Thread(target=self._installation_thread, args=(request,), daemon=True)
        self._installation_worker.start()

    def _installation_thread(self, request: dict[str, Any]) -> None:
        from cochem_base.config_loader import get_artifact_dir
        from cochem_base.core.cochem_core_registry_manager import atomic_write_json
        from cochem_base.orchestrator.bootstrap_service import run_setup

        def on_event(event: dict[str, Any]) -> None:
            if event['event'] == 'phase_start':
                self.state.system_status = f"Installing: Phase {event['phase_number']}"
                self.install_output.append_stdout(f"Phase {event['phase_number']}: {event['phase_name']}\n")
            elif event['event'] == 'phase_result':
                self.install_output.append_stdout(f"Phase {event['phase_number']}: {event['status']}\n")
                if not event['success']:
                    self.install_output.append_stdout(json.dumps(event['report'], indent=2) + "\n")

        try:
            artifact_dir = get_artifact_dir()
            artifact = request['artifact']
            atomic_write_json(artifact_dir / "Registry" / "gui_setup_request.json", {
                "license_mode": request['license_mode'],
                "calculation_environment": request['calculation_environment'],
                "interaction_environment": request['interaction_environment'],
                "scientific_input": str(artifact.path) if artifact is not None else None,
                "input_sha256": artifact.sha256 if artifact is not None else None,
                "input_source": artifact.source if artifact is not None else None,
                "required_disk_gb": request['required_disk_gb'],
            })
            summary = run_setup(artifact_dir, min_disk_space_gb=request['required_disk_gb'], on_event=on_event)
            if summary['overall_status'] not in {'LOCKED', 'PASSED', 'DEGRADED_OPERATIONAL'}:
                raise RuntimeError(f"Stage 0 was not accepted: {summary['overall_status']}. See {artifact_dir / 'Registry' / 'setup_summary.json'}")
            optional = licensed_engine_availability(summary['registry_path'])
            for engine, observation in optional.items():
                if not observation['available']:
                    self.install_output.append_stdout(
                        f"Optional {engine.upper()} unavailable; dependent calculations are disabled: {observation['reason']}\n"
                    )
            self.state.system_status = f"Setup {summary['overall_status']}"
            self.state.error_message = ''
            self.install_output.append_stdout(f"Complete setup evidence: {artifact_dir / 'Registry' / 'setup_summary.json'}\n")
            self._refresh_engine_choices()
            self._refresh_topos_capabilities()
            self._on_engine_changed({"new": self.matrix_engine.value})
        except (ValueError, RuntimeError, OSError, KeyError) as exc:
            self.state.system_status = 'Installation Error'
            self.state.error_message = str(exc)
            self.install_output.append_stdout(f"Setup was not accepted: {exc}\n")
        finally:
            self._installation_running = False
            self.run_install_btn.disabled = False

    def _format_product_class_card(self, pc_val: str) -> str:
        try:
            pc = ProductClass(pc_val)
            spec = PRODUCT_CLASS_SPECS[pc]
            return (
                f"<b>{pc.value}</b><br/>"
                f"<b>Description:</b> {spec['description']}<br/>"
                f"<b>Target Accuracy:</b> <code>{spec['target_accuracy']}</code><br/>"
                f"<b>Spend Priority (§3.3):</b> {spec['spend_priority_focus']}"
            )
        except Exception:
            return f"<b>{pc_val}</b>"

    def _on_product_class_changed(self, change: Any) -> None:
        pc_val = change["new"]
        self.product_class_card.value = self._format_product_class_card(pc_val)
        if "Product A" in pc_val and "T4" in self.matrix_tier.options:
            self.matrix_tier.value = "T4"
        elif "Product B" in pc_val:
            if hasattr(self, 'config_tabs') and len(self.config_tabs.children) > 3:
                self.config_tabs.selected_index = 3
        elif "Product C" in pc_val:
            self.state.active_view = "inspector"
            if hasattr(self, 'inspector_tabs'):
                self.inspector_tabs.selected_index = 1
        self._check_dispersion_gate()

    def _on_engine_changed(self, change: Any) -> None:
        if change['new'] != 'ORCA' and hasattr(self, 't9_enable'):
            self.t9_enable.value = False
            self.scientific_initial_hessian.value = 'XTB2'
        if change["new"] == "XTB":
            self.product_class_selector.value = "Screening (no product accuracy claim)"
            self.matrix_tier.value = "T1"
            self._on_tier_changed({'new': 'T1'})
            self.matrix_method.value = "GFN2-xTB"
            self.matrix_basis.value = "built-in"
            self.matrix_solvation.value = None
            self.matrix_cbs_pair.value = None
            self.cb_recipe_r1.value = False
            self.cb_recipe_r2.value = False
        elif change["new"] == "PYSCF":
            self.product_class_selector.value = "Screening (no product accuracy claim)"
            self.matrix_tier.value = "T2"
            self._on_tier_changed({'new': 'T2'})
            self.matrix_method.value = "HF/STO-3G"
            self.matrix_basis.value = "STO-3G"
            self.matrix_solvation.value = None
            self.matrix_cbs_pair.value = None
            self.cb_recipe_r1.value = False
            self.cb_recipe_r2.value = False
        elif change["new"] == "CFOUR":
            self.product_class_selector.value = "Screening (no product accuracy claim)"
            self.matrix_tier.value = "T2"
            self._on_tier_changed({'new': 'T2'})
            self.matrix_method.value = "HF"
            self.matrix_basis.value = "cc-pVDZ"
            self.matrix_solvation.value = None
            self.matrix_cbs_pair.value = None
            self.cb_recipe_r1.value = False
            self.cb_recipe_r2.value = False
        else:
            # Changing the engine can retain the same tier. Refresh its method
            # and basis catalogs even when the tier trait emits no change.
            self._on_tier_changed({'new': self.matrix_tier.value})
        self.btn_execute.description = {"XTB": "Run xTB optimization", "PYSCF": "Run PySCF single point",
                                        "CFOUR": "Run CFOUR calculation", None: "Select a calculation engine"}.get(change["new"], "Run ORCA optimization")
        self._check_dispersion_gate()

    def _on_tier_changed(self, change: Any) -> None:
        tier = change["new"]
        if tier in METHOD_MATRIX_TIERS:
            methods = METHOD_MATRIX_TIERS[tier]["methods"]
            if self.matrix_engine.value == 'CFOUR':
                methods = {"T2": ["HF"], "T6": ["MP2"], "T8": ["CCSD", "CCSD(T)"]}[tier]
            bases = METHOD_MATRIX_TIERS[tier]["allowed_basis_sets"]
            if self.matrix_engine.value == 'CFOUR':
                from cochem_base.calc.cfour_execution import SUPPORTED_CFOUR_BASIS_LABELS
                bases = ['cc-pVDZ', *(basis for basis in SUPPORTED_CFOUR_BASIS_LABELS if basis != 'cc-pVDZ')]
            self.matrix_method.options = methods
            self.matrix_method.value = methods[0]
            self.matrix_basis.options = bases
            self.matrix_basis.value = bases[0]
            self._check_dispersion_gate()

    def _check_dispersion_gate(self, *args: Any) -> None:
        """Use the same mandatory methodology guard as calculation dispatch."""
        try:
            if self.product_class_selector.value == ProductClass.PRODUCT_B.value:
                raise MethodologyViolationError(
                    "Product B materials use the Periodic structures panel with a validated cell and PBE plane-wave/PAW settings."
                )
            if self.matrix_engine.value is None:
                raise MethodologyViolationError("Select an available engine. ORCA and CFOUR are optional; free-engine setup and data inspection remain available.")
            if self.matrix_engine.value in {"XTB", "PYSCF"}:
                self._xtb_run_config() if self.matrix_engine.value == "XTB" else self._pyscf_run_config()
                self.dispersion_warning.value = ""
                if hasattr(self, "btn_execute"):
                    self._refresh_execution_gate()
                return
            if self.matrix_engine.value == 'CFOUR':
                self._cfour_run_config()
                self.dispersion_warning.value = ''
                if hasattr(self, 'btn_execute'):
                    self._refresh_execution_gate()
                return
            import numpy as np

            from cochem_base.calc.calculation_service import parse_run_geometry

            symbols, coordinates = parse_run_geometry(self.matrix_geometry.value)
            if not symbols:
                raise MethodologyViolationError("Enter valid XYZ geometry before execution.")
            fragments = detect_molecular_fragments(symbols, np.asarray(coordinates))
            validate_method_matrix_compliance(
                self.matrix_method.value, num_fragments=len(fragments),
                unphysical_override=self.unphysical_override.value,
            )
            self._portable_t9_request()
            self._selected_scientific_input()
            if self.cb_recipe_r2.value and (self.matrix_method.value != "wB97M-V" or self.matrix_basis.value != "def2-QZVPP"):
                raise MethodologyViolationError("Recipe R2 requires its verified wB97M-V/def2-QZVPP protocol")
            operation = self.actions_operation.value if self.calc_env_dropdown.value == "github-actions" else self.native_operation.value
            if self.cb_recipe_r2.value and operation not in {"optimization", "optimization_frequencies"}:
                raise MethodologyViolationError("Recipe R2 requires intermolecular optimization")
            if self.product_class_selector.value != "Screening (no product accuracy claim)":
                validate_product_class_policy(
                    self.product_class_selector.value, tier=self._selected_canonical_tier(),
                    method=self.matrix_method.value, solvation=self.matrix_solvation.value,
                    cbs_cardinal_pair=self.matrix_cbs_pair.value,
                )
        except (ValueError, RuntimeError, MethodologyViolationError) as exc:
            import html
            if hasattr(self, 'btn_execute'):
                self.btn_execute.disabled = True
            self.dispersion_warning.value = f"<b>Calculation requires attention:</b> {html.escape(str(exc))}"
        else:
            self.dispersion_warning.value = ""
        if hasattr(self, "btn_execute"):
            self._refresh_execution_gate()

    def _refresh_execution_gate(self) -> None:
        from cochem_base.core_engine.execution_authority import authorize_engine_execution
        reason = ""
        remote = self.calc_env_dropdown.value == "github-actions"
        if remote:
            self.btn_execute.description = "Run on GitHub Actions"
            if self.matrix_engine.value not in {"ORCA", "CFOUR", "XTB"}:
                reason = "Choose xTB for free screening or verify remote ORCA/CFOUR access before selecting a licensed engine."
            elif self.matrix_engine.value in {"ORCA", "CFOUR"} and not self._remote_engine_availability[self.matrix_engine.value.lower()].get("provisionable"):
                reason = "This licensed engine is unavailable until a genuine remote engine check verifies approved archive access."
            else:
                try:
                    self._actions_repository()
                except ValueError as exc:
                    reason = str(exc)
        elif self.matrix_engine.value is None:
            reason = "Choose an available engine; licensed engines are optional."
        elif self.matrix_engine.value not in {"ORCA", "XTB", "PYSCF", "CFOUR"}:
            reason = "This engine requires its dedicated scientific adapter."
        else:
            engine = self.matrix_engine.value.lower()
            try:
                authorize_engine_execution(engine, cores=1)
            except (ValueError, RuntimeError, OSError) as exc:
                reason = f"{self.matrix_engine.value} execution is unavailable: {exc}"
                if self.matrix_engine.value in {'ORCA', 'CFOUR'}:
                    # A once-authorized engine can lose its binary or its audit.
                    # Remove it immediately rather than leaving dependent
                    # controls enabled until the next installation refresh.
                    self._refresh_engine_choices()
                    return
        if not remote:
            self.btn_execute.description = {"XTB": "Run xTB optimization", "PYSCF": "Run PySCF single point",
                                            "CFOUR": "Run CFOUR calculation", None: "Select a calculation engine"}.get(self.matrix_engine.value, "Run ORCA optimization")
        if self.calc_env_dropdown.value == "hpc":
            self.btn_execute.description = "Submit HPC calculation"
        elif not remote and self.matrix_engine.value == 'ORCA':
            self.btn_execute.description = {'single_point': 'Run ORCA single point', 'optimization': 'Run ORCA optimization',
                'harmonic_frequencies': 'Run ORCA frequencies', 'optimization_frequencies': 'Run ORCA optimize + frequencies'}[self.native_operation.value]
        self.native_job_options.layout.display = '' if not remote and hasattr(self, 'matrix_engine') and self.matrix_engine.value == 'ORCA' else 'none'
        # Disabled controls retain catalog metadata for inspection but cannot be
        # chosen in the browser when no authorized licensed engine is selected.
        selected = self.matrix_engine.value
        tiers = {'XTB': ['T1'], 'PYSCF': ['T2'], 'CFOUR': ['T2', 'T6', 'T8']}.get(selected, list(METHOD_MATRIX_TIERS))
        if tuple(self.matrix_tier.options) != tuple(tiers):
            previous = self.matrix_tier.value
            self.matrix_tier.options = tiers
            self.matrix_tier.value = previous if previous in tiers else tiers[0]
        self.matrix_tier.disabled = selected is None or selected in {'XTB', 'PYSCF'}
        self.matrix_method.disabled = selected is None or selected in {'XTB', 'PYSCF'}
        self.matrix_basis.disabled = selected is None or selected == 'XTB'
        for control in (self.matrix_solvation, self.matrix_cbs_pair, self.cb_recipe_r1,
                        self.cb_recipe_r2, self.r2_reference_manifest, self.t9_config_path,
                        self.t9_enable, self.t9_method, self.t9_basis, self.t9_electrons, self.t9_orbitals, self.t9_rationale,
                        self.scientific_initial_hessian, self.scientific_r2_upload, self.scientific_read_upload):
            control.disabled = selected != 'ORCA'
        self.cfour_operation.layout.display = '' if selected == 'CFOUR' and not remote else 'none'
        self.cfour_operation.disabled = selected != 'CFOUR'
        cfour_operations = ([('Single point', 'single_point'), ('Optimization', 'optimization'),
                             ('Harmonic frequencies', 'harmonic_frequencies'),
                             ('Optimize + harmonic frequencies', 'optimization_frequencies')]
                            if self.matrix_method.value in {'HF', 'HF/STO-3G'} else
                            [('Single point', 'single_point')])
        if selected == 'CFOUR' and tuple(self.cfour_operation.options) != tuple(cfour_operations):
            previous = self.cfour_operation.value
            self.cfour_operation.options = cfour_operations
            self.cfour_operation.value = previous if previous in {value for _, value in cfour_operations} else 'single_point'
        actions_operations = ([('Geometry optimization', 'optimization')] if selected == 'XTB' and remote else
                              cfour_operations if selected == 'CFOUR' else
                              [('Single point', 'single_point'), ('Optimization', 'optimization'),
                               ('Harmonic frequencies', 'harmonic_frequencies'),
                               ('Optimize + harmonic frequencies', 'optimization_frequencies')])
        if tuple(self.actions_operation.options) != tuple(actions_operations):
            previous = self.actions_operation.value
            self.actions_operation.options = actions_operations
            self.actions_operation.value = previous if previous in {value for _, value in actions_operations} else actions_operations[0][1]
        self.product_class_selector.disabled = selected in {'XTB', 'PYSCF', 'CFOUR'}
        t9_reason = self._t9_admission_reason()
        reason = reason or t9_reason
        hpc_reason = self._student_hpc_admission_reason() if self.calc_env_dropdown.value == 'hpc' else ''
        reason = reason or hpc_reason
        self.btn_hpc_connect.disabled = self.calc_env_dropdown.value != 'hpc' or self._hpc_preflight_running
        self.engine_warning.value = f"<b>{html.escape(reason)}</b>" if reason else ""
        self.btn_execute.disabled = bool(reason or self.dispersion_warning.value or self._pipeline_running or self._hpc_running or self._hpc_retrieving or self._actions_running
                                         or self._topos_running or self._installation_running)
        self.btn_slurm_submit.disabled = self.calc_env_dropdown.value != 'hpc' or self.btn_execute.disabled
        if hasattr(self, 'btn_periodic_run'):
            self.btn_periodic_run.disabled = bool(hpc_reason or self._pipeline_running or self._hpc_running or self._hpc_retrieving)
        if hasattr(self, 'btn_topos_submit') and self.calc_env_dropdown.value == 'hpc':
            self.btn_topos_submit.disabled = bool(hpc_reason or not self.topos_heuristic.value or self._topos_running
                                                or self._pipeline_running or self._hpc_running or self._installation_running)
        if hasattr(self, 'btn_research_topos'):
            busy = bool(hpc_reason) or self._pipeline_running or self._hpc_running or self._hpc_retrieving or self._actions_running or self._topos_running or self._student_setup_busy
            top_ops = self._research_capability_observations.get('topos', {}).get('operations', [])
            torq_ops = self._research_capability_observations.get('torq', {}).get('operations', [])
            self.btn_research_topos.disabled = busy or not bool(top_ops and self.research_topos_operation.value in top_ops)
            for button, operation in ((self.btn_research_torq, 'research_scan'),
                                      (self.btn_research_wiberg, 'wiberg_lowdin'),
                                      (self.btn_research_wiberg_nao, 'wiberg_nao'),
                                      (self.btn_research_nbo, 'nbo_analysis')):
                button.disabled = busy or operation not in torq_ops
                if operation in {'nbo_analysis', 'wiberg_nao'}:
                    declaration = self._research_capability_observations.get('torq', {}).get('provider_capabilities', {}).get('scientific_apis', {}).get(operation, {})
                    button.disabled = button.disabled or declaration.get('available') is not True or self.research_orbital_backend.value not in declaration.get('supported_engines', [])

    def _on_detect_fragments_clicked(self, b: Any) -> None:
        geom = self.matrix_geometry.value
        try:
            from cochem_base.calc.calculation_service import parse_run_geometry
            symbols, coords = parse_run_geometry(geom)
            if not symbols:
                self.fragments_output.value = "<b style='color:red;'>Failed to parse XYZ geometry.</b>"
                return
            import numpy as np
            from mendeleev import element as get_el
            atomic_numbers = [get_el(s).atomic_number for s in symbols]
            frags = detect_molecular_fragments(atomic_numbers, np.array(coords))
            frag_desc = []
            for idx, f in enumerate(frags):
                f_syms = [symbols[i] for i in f]
                frag_desc.append(f"Fragment {idx}: atoms {f} ({''.join(f_syms)})")
            self.fragments_output.value = "<b>Detected Fragments:</b><br/>" + "<br/>".join(frag_desc)

            # Generate frozen monomer block
            orca_block = generate_frozen_monomer_orca_block(
                fragments=frags,
                symbols=symbols,
                coordinates_angstrom=np.array(coords),
                freeze_all_monomers=self.cb_recipe_r1.value,
            )
            self.fragment_preview.value = orca_block
        except Exception as exc:
            self.fragments_output.value = f"<b style='color:red;'>Detection failed: {exc}</b>"

    def _on_slurm_submit(self, b: Any = None) -> None:
        return self._on_slurm_submit_clicked(b)

    def _on_slurm_submit_clicked(self, b: Any) -> None:
        if self.calc_env_dropdown.value != "hpc":
            self.slurm_status_output.value = "<p role='alert'>Select HPC as the calculation environment before submitting a scheduler job.</p>"
            return
        self._submit_student_hpc()

    def _on_parse_inspector_clicked(self, b: Any) -> None:
        choice = self._input_selectors['telemetry'].value
        if choice in self._input_library:
            self.inspector_file_input.value = str(self._input_library[choice]['path'])
        file_path_str = self.inspector_file_input.value.strip()
        if not file_path_str:
            self.inspector_rot_table.value = "<b style='color:red;'>Upload or select a native spectroscopy output.</b>"
            return
        fpath = Path(file_path_str)
        if not fpath.exists():
            self.inspector_rot_table.value = f"<b style='color:red;'>File not found: {html.escape(str(fpath))}</b>"
            return
        try:
            parser = SpectroscopyTelemetryParser()
            res = parser.parse_file(fpath)
            geometry_label = 'Equilibrium Value ($B_e$) [MHz]' if res.equilibrium_geometry_verified else 'Reported geometry [MHz]'
            html_table = (
                "<table border='1' cellpadding='5' style='border-collapse:collapse; width:100%;'>"
                "<thead><tr style='background:#f2f2f2;'>"
                f"<th>Observable</th><th>{geometry_label}</th>"
                "<th>Vib Correction ($\\Delta B_{\\text{vib}}$) [MHz]</th>"
                "<th>Ground State ($B_0$) [MHz]</th><th>Provenance</th></tr></thead><tbody>"
                f"<tr><td><b>A</b></td><td>{_observable(res.a_e)}</td><td>{_observable(res.delta_a_vib)}</td><td>{_observable(res.a_0)}</td><td>[M, D]</td></tr>"
                f"<tr><td><b>B</b></td><td>{_observable(res.b_e)}</td><td>{_observable(res.delta_b_vib)}</td><td>{_observable(res.b_0)}</td><td>[M, D]</td></tr>"
                f"<tr><td><b>C</b></td><td>{_observable(res.c_e)}</td><td>{_observable(res.delta_c_vib)}</td><td>{_observable(res.c_0)}</td><td>[M, D]</td></tr>"
                f"<tr><td><b>Inertial Defect ($\\Delta$)</b></td><td colspan='3'>{res.inertial_defect:.6f} amu·Å²</td><td>[D]</td></tr>"
                f"<tr><td><b>Dipole Magnitude (|$\\mu$|)</b></td><td colspan='3'>{_observable(res.total_dipole, 4)} Debye</td><td>[M]</td></tr>"
                "</tbody></table>"
            )
            html_table += ('<p>Rotational-constant scope: ' + html.escape(res.rotational_constant_scope) +
                '. Ground-state scope: ' + html.escape(res.ground_state_constant_scope) +
                '. Dipole component frame: ' + html.escape(res.dipole_component_frame) +
                '.<br/>Source: ' + html.escape(res.source_filename or fpath.name) +
                '<br/>Original SHA-256: <code>' + html.escape(res.source_sha256 or '') + '</code>.</p>')
            self.inspector_rot_table.value = html_table
        except Exception as exc:
            self.inspector_rot_table.value = f"<b style='color:red;'>Parse Error: {html.escape(str(exc))}</b>"

    def _update_isotope_selectors(self, change: Any = None) -> None:
        from cochem_base.calc.calculation_service import parse_run_geometry_identity
        from cochem_base.physics.isotopes import parse_nuclide_token
        from cochem_base.physics.nuclide_resolver import get_element

        try:
            symbols = list(parse_run_geometry_identity(self.matrix_geometry.value).nuclides)
            previous = [selector.value for selector in self.isotope_selectors]
            previous_parents = getattr(self, "_isotope_selector_parent_nuclides", ())
            selectors = []
            for index, token in enumerate(symbols):
                element, mass_number = parse_nuclide_token(token)
                options = [(f"Parent ({token})", token)]
                options.extend((f"{isotope.mass_number}{element}", f"{isotope.mass_number}{element}")
                               for isotope in get_element(element).isotopes
                               if isotope.mass is not None and isotope.mass > 0
                               and f"{isotope.mass_number}{element}" != token)
                values = [value for _, value in options]
                preferred = ({"H": "2H", "C": "13C", "O": "18O"}.get(element)
                             if index == 0 and mass_number is None else token)
                same_parent = index < len(previous_parents) and previous_parents[index] == token
                selected = previous[index] if same_parent and index < len(previous) and previous[index] in values else preferred
                selectors.append(widgets.Dropdown(
                    options=options, value=selected if selected in values else token,
                    description=f"Atom {index + 1} ({element}):", style={'description_width': 'initial'},
                ))
            self._isotope_selector_parent_nuclides = tuple(symbols)
            self.isotope_selectors = selectors
            self.isotope_elements_box.children = selectors or [widgets.HTML("<p>[MISSING DATA] Enter molecular geometry.</p>")]
        except (ValueError, KeyError, IndexError):
            self.isotope_selectors = []
            self.isotope_elements_box.children = [widgets.HTML("<p>[MISSING DATA] Enter valid molecular geometry.</p>")]

    def _prepare_calculation_hessians(self, root: Path) -> dict[str, dict[str, Any]]:
        """Bind readable native/array Hessian outputs to their exact retained bytes."""
        from cochem_base.spectroscopy.artifacts import load_hessian_artifact
        root = Path(root).resolve(strict=True)
        candidates = {}
        for path in sorted(root.rglob('*'))[:20000]:
            if path.suffix.lower() not in {'.hess', '.npz', '.h5', '.hdf5'} or not path.is_file() or path.is_symlink():
                continue
            if not path.resolve(strict=True).is_relative_to(root):
                continue
            try:
                artifact = load_hessian_artifact(path)
                key = hashlib.sha256((str(path) + ':' + artifact.sha256).encode('utf-8')).hexdigest()
                candidates[key] = {'path': str(path), 'sha256': artifact.sha256,
                    'label': root.name + ' · ' + path.relative_to(root).as_posix(),
                    'scope': artifact.qualification['scope']}
                if len(candidates) >= 128:
                    break
            except (ValueError, RuntimeError, OSError, KeyError):
                continue  # General scientific archives remain inspectable as data, not Hessians.
        return candidates

    def _publish_calculation_hessians(self, candidates: dict[str, dict[str, Any]]) -> None:
        self._calculation_hessians.update(candidates)
        selected = self.calculation_hessian_choice.value
        self.calculation_hessian_choice.options = [("Choose a retained calculation Hessian", "")] + [
            (item['label'], key) for key, item in self._calculation_hessians.items()]
        if selected in self._calculation_hessians:
            self.calculation_hessian_choice.value = selected
        elif candidates:
            self.calculation_hessian_choice.value = next(iter(candidates))

    def _select_calculation_hessian(self, change: dict[str, Any]) -> None:
        record = self._calculation_hessians.get(change['new'])
        if not record:
            return
        try:
            path = Path(record['path'])
            if path.is_symlink():
                raise ValueError('Retained calculation Hessian became a symbolic link')
            with path.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != record['sha256']:
                    raise ValueError('Retained calculation Hessian hash changed; reopen and verify its result package')
            self._isotope_hessian_data = None
            self.isotope_hessian_path.value = str(path)
            self.isotope_hessian_status.value = (
                '<p role="status">Retained Hessian selected: ' + html.escape(record['label']) +
                '. Choose Load geometry and Hessian.<br/>SHA-256: <code>' + record['sha256'] +
                '</code><br/>Validation scope: ' + html.escape(record['scope']) + '</p>'
            )
        except (OSError, ValueError) as exc:
            self._isotope_hessian_data = None
            self.isotope_hessian_path.value = ''
            self.isotope_hessian_status.value = '<p role="alert">Calculation Hessian was not selected: ' + html.escape(str(exc)) + '</p>'

    def _on_clear_hessian_clicked(self, b: Any) -> None:
        self._isotope_hessian_data = None
        self.isotope_modes_plot.value = ""
        self.isotope_hessian_status.value = "<p>[MISSING DATA] No Cartesian Hessian loaded.</p>"

    def _on_load_hessian_clicked(self, b: Any) -> None:
        from cochem_base.spectroscopy.artifacts import load_hessian_artifact
        if b is not None and self._ingestion_busy:
            self.isotope_hessian_status.value = '<p role="status">Wait for the current scientific input operation to finish before loading another Hessian.</p>'
            return
        if self.calculation_hessian_choice.value:
            self._select_calculation_hessian({'new': self.calculation_hessian_choice.value})
        path = self.isotope_hessian_path.value.strip()
        self._isotope_hessian_data = None
        if not path:
            self.isotope_hessian_status.value = '<p role="alert">Select a retained uploaded or calculation Hessian first.</p>'
            return
        def load() -> None:
            try:
                artifact = load_hessian_artifact(path)
                def loaded() -> None:
                    self.matrix_geometry.value = "\n".join(
                        f"{symbol} {row[0]:.15g} {row[1]:.15g} {row[2]:.15g}"
                        for symbol, row in zip(artifact.symbols, artifact.coordinates_angstrom)
                    )
                    self._isotope_hessian_data = artifact
                    self.isotope_hessian_status.value = (
                        "<p role='status'>Geometry and Cartesian Hessian loaded. Units: Hartree/bohr².<br/>"
                        f"Source: {html.escape(artifact.source)}<br/>SHA-256: <code>{artifact.sha256}</code><br/>"
                        f"Validation scope: {html.escape(artifact.qualification['scope'])}</p>"
                    )
                self._ui_call(loaded)
            except (OSError, ValueError, KeyError, RuntimeError) as exc:
                message = str(exc)
                self._ui_call(lambda: setattr(self.isotope_hessian_status, 'value', f"<p role='alert'>Hessian was not loaded: {html.escape(message)}</p>"))
            finally:
                if b is not None:
                    def finish() -> None:
                        self._ingestion_busy = False
                        self.btn_load_hessian.disabled = False
                    self._ui_call(finish)
        if b is None:
            load()
            return
        self._ingestion_busy = True
        self.btn_load_hessian.disabled = True
        self.isotope_hessian_status.value = '<p role="status">Checking the bounded tensor, original hashes and any native scientific qualification in the background…</p>'
        self._hessian_load_worker = threading.Thread(target=load, daemon=True)
        self._hessian_load_worker.start()

    def _on_run_isotope_reanalysis_clicked(self, b: Any) -> None:
        """Compute from one geometry/isotope snapshot without blocking widget events."""
        if b is not None and self._ingestion_busy:
            self.isotope_results_table.value = '<p role="status">Wait for the current scientific input operation to finish.</p>'
            return
        geom_str = self.matrix_geometry.value.strip()
        if not geom_str:
            self.isotope_results_table.value = "<b style='color:red;'>Please provide molecular geometry in Base Config tab first.</b>"
            return
        artifact = self._isotope_hessian_data
        selected_nuclides = tuple(selector.value for selector in self.isotope_selectors)
        self.isotope_modes_plot.value = ""

        def compute() -> None:
            try:
                results, modes = self._isotope_reanalysis_result(geom_str, artifact, selected_nuclides)
            except Exception as exc:
                results = f"<p role='alert'>Isotopic re-analysis failed: {html.escape(str(exc))}</p>"
                modes = ""
            def publish() -> None:
                self.isotope_results_table.value = results
                self.isotope_modes_plot.value = modes
                if b is not None:
                    self._ingestion_busy = False
                    self.btn_run_isotope_reanalysis.disabled = False
            self._ui_call(publish)

        # Retain the synchronous programmatic API; actual Button.click passes the widget.
        if b is None:
            compute()
            return
        self._ingestion_busy = True
        self.btn_run_isotope_reanalysis.disabled = True
        self.isotope_results_table.value = (
            '<p role="status">Reweighting the selected geometry and supplied tensor in the background. '
            'The interface remains available; this bounded numerical analysis must finish before another input operation.</p>'
        )
        self._isotope_worker = threading.Thread(target=compute, daemon=True)
        self._isotope_worker.start()

    def _isotope_reanalysis_result(self, geom_str: str, artifact: Any,
                                  selected_nuclides: tuple[str, ...]) -> tuple[str, str]:
        """Return real mass-reweighted observables and a provenance-labelled figure."""
        modes_plot = ""
        from cochem_base.calc.calculation_service import parse_run_geometry_identity
        identity = parse_run_geometry_identity(geom_str)
        symbols, coords = list(identity.nuclides), identity.coordinates_angstrom
        if not symbols or len(symbols) == 0:
            raise ValueError("Failed to parse symbols and coordinates from geometry")

        if artifact is not None:
            import numpy as np

            from cochem_base.geometry.nuclide_geometry import resolve_nuclear_identity
            if tuple(symbols) != resolve_nuclear_identity(artifact.symbols).nuclides or not np.allclose(
                coords, artifact.coordinates_angstrom, rtol=0, atol=1e-10
            ):
                raise ValueError("Geometry changed after loading the Hessian. Reload it or clear it before analysis.")
        engine = IsotopologueSpectroscopyEngine(
            symbols=symbols,
            coordinates_angstrom=coords,
            cartesian_hessian=artifact.hessian_hartree_bohr2 if artifact is not None else None,
            hessian_qualification=artifact.qualification if artifact is not None else None,
        )
        parent_res = engine.compute_observables()
        rotor_labels = ('A_e', 'B_e', 'C_e') if parent_res.equilibrium_geometry_verified else ('A (geometry)', 'B (geometry)', 'C (geometry)')

        html_rows = [
            "<table border='1' cellpadding='5' style='border-collapse:collapse; width:100%;'>",
            "<thead><tr style='background:#f2f2f2;'>",
            "<th>Isotopologue</th><th>Total Mass (amu) [M]</th>" + ''.join('<th>' + label + ' (MHz)</th>' for label in rotor_labels),
            "<th>B_0 (MHz) [D]</th><th>Inertial Defect (amu·Å²) [D]</th><th>Walltime (ms)</th></tr></thead><tbody>",
            f"<tr><td><b>Parent ({''.join(parent_res.symbols)})</b></td><td>{parent_res.total_mass_amu:.4f}</td>"
            f"<td>{parent_res.A_e_MHz:.2f}</td><td>{parent_res.B_e_MHz:.2f}</td><td>{parent_res.C_e_MHz:.2f}</td>"
            f"<td>{_observable(parent_res.B_0_MHz, 2)}</td><td>{parent_res.inertial_defect_amu_A2:.4f}</td><td>{parent_res.execution_walltime_ms:.2f}</td></tr>",
        ]

        if len(selected_nuclides) != len(symbols):
            raise ValueError("Isotope selections must match every atom in the geometry")
        sub_dict = {index: nuclide for index, nuclide in enumerate(selected_nuclides)
                    if nuclide != symbols[index]}
        iso_res = None
        if sub_dict:
            iso_res = engine.compute_observables(isotopic_substitution=sub_dict)
            html_rows.append(
                f"<tr><td><b>Substituted ({''.join(iso_res.symbols)})</b></td><td>{iso_res.total_mass_amu:.4f}</td>"
                f"<td>{iso_res.A_e_MHz:.2f}</td><td>{iso_res.B_e_MHz:.2f}</td><td>{iso_res.C_e_MHz:.2f}</td>"
                f"<td>{_observable(iso_res.B_0_MHz, 2)}</td><td>{iso_res.inertial_defect_amu_A2:.4f}</td><td>{iso_res.execution_walltime_ms:.2f}</td></tr>"
            )

        html_rows.append("</tbody></table>")
        if artifact is not None:
            html_rows.append('<h4>Projected harmonic modes</h4><p>' + html.escape(parent_res.harmonic_frequency_scope) +
                '. Signed eigenfrequencies in cm⁻¹; negative values indicate negative-curvature tensor modes. No electronic recalculation.</p>')
            html_rows.append("<table><caption>Mass-weighted Cartesian Hessian frequencies</caption><thead><tr><th scope='col'>Mode</th><th scope='col'>Parent (cm⁻¹)</th><th scope='col'>Substituted (cm⁻¹)</th></tr></thead><tbody>")
            for index, frequency in enumerate(parent_res.harmonic_frequencies_cm1):
                replacement = iso_res.harmonic_frequencies_cm1[index] if iso_res is not None else None
                html_rows.append(f"<tr><th scope='row'>{index + 1}</th><td>{frequency:.4f}</td><td>{_observable(replacement, 4)}</td></tr>")
            html_rows.append(f"</tbody></table><p>Rigid modes removed: {parent_res.rigid_mode_count}. Source: {html.escape(artifact.source)}. SHA-256: <code>{artifact.sha256}</code></p>")
            modes_plot = self._render_harmonic_plot(parent_res, iso_res, artifact)
        evidence_note = (
            html.escape(parent_res.harmonic_frequency_scope) + ". Anharmonic vibrational corrections were not supplied; B0 is [MISSING DATA]. "
            if artifact is not None else
            "No Hessian or vibrational correction was supplied; B0 is [MISSING DATA]. "
        )
        results_table = (
            "<div style='margin-bottom:8px; background-color:#d4edda; color:#155724; padding:8px; border-radius:4px;'>"
            "<b>Dynamic Mendeleev Isotopologue Re-analysis:</b><br/>" +
            html.escape(parent_res.rotational_constant_scope) + '. ' + evidence_note +
            'Mass convention: ' + html.escape(parent_res.mass_convention) + '. ' +
            "Per-calculation walltimes are measured in the table."
            "</div>" + "\n".join(html_rows)
        )
        return results_table, modes_plot

    @staticmethod
    def _render_harmonic_plot(parent: Any, substituted: Any, artifact: Any) -> str:
        """Plot observed Hessian modes with explicit units and exportable provenance."""
        import base64
        import csv
        import io

        from matplotlib.figure import Figure

        frequencies = parent.harmonic_frequencies_cm1
        if not frequencies:
            return "<p>[MISSING DATA] This geometry has no vibrational modes.</p>"
        figure = Figure(figsize=(6.5, 3.5), dpi=150, layout="constrained")
        axis = figure.subplots()
        indices = list(range(1, len(frequencies) + 1))
        axis.plot(indices, frequencies, "o-", color="#005a9c", linewidth=1.2, label="Parent")
        if substituted is not None:
            axis.plot(indices, substituted.harmonic_frequencies_cm1, "s--", color="#8c2d04",
                      linewidth=1.2, label="Substituted")
        axis.set_xlabel("Ordered vibrational mode", fontfamily="serif")
        axis.set_ylabel("Harmonic frequency (cm⁻¹)" if parent.physical_hessian_verified else "Supplied tensor eigenfrequency (cm⁻¹)", fontfamily="serif")
        axis.tick_params(labelsize=9, direction="in")
        axis.legend(frameon=False, fontsize=9)
        axis.grid(alpha=0.2)
        rendered = io.StringIO()
        figure.savefig(rendered, format="svg", metadata={"Description": artifact.source + "; SHA-256 " + artifact.sha256})
        svg = rendered.getvalue()
        csv_data = io.StringIO()
        writer = csv.writer(csv_data)
        writer.writerow(["mode", "parent_cm-1", "substituted_cm-1", "source", "sha256", "physical_hessian_verified", "minimum_verified", "validation_scope"])
        for index, frequency in enumerate(frequencies):
            writer.writerow([index + 1, frequency,
                             substituted.harmonic_frequencies_cm1[index] if substituted else "",
                             artifact.source, artifact.sha256, parent.physical_hessian_verified,
                             parent.minimum_verified, parent.harmonic_frequency_scope])
        svg_uri = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        csv_uri = base64.b64encode(csv_data.getvalue().encode("utf-8")).decode("ascii")
        return (
            '<figure><figcaption>' + html.escape(parent.harmonic_frequency_scope) + '. '
            "Modes are ordered by frequency; matching indices do not imply identical mode character.</figcaption>"
            f"<img alt='Parent and substituted harmonic frequencies; numerical values are in the preceding table.' src='data:image/svg+xml;base64,{svg_uri}'/>"
            f"<p><a download='harmonic-modes.svg' href='data:image/svg+xml;base64,{svg_uri}'>Download SVG figure</a> | "
            f"<a download='harmonic-modes.csv' href='data:text/csv;base64,{csv_uri}'>Download frequency data (CSV)</a></p></figure>"
        )

    def _on_read_hdf5_clicked(self, b: Any, *, result_source: dict[str, Any] | None = None) -> None:
        if result_source is not None:
            self._managed_physical_data = dict(result_source)
            self._input_selectors['physical_data'].value = ''
        if self._ingestion_busy:
            self.hdf5_results_table.value = '<p role="status">Wait for the current scientific input operation to finish, then inspect this dataset.</p>'
            return
        choice = self._input_selectors['physical_data'].value
        if choice in self._input_library:
            receipt = self._input_library[choice]
            selected = {'input_id': choice, 'path': receipt['path'], 'filename': receipt['filename'], 'sha256': receipt['sha256']}
        else:
            selected = dict(self._managed_physical_data) if self._managed_physical_data else {'path': self.inspector_file_input.value.strip()}
        self._ingestion_busy = True
        self.btn_read_hdf5.disabled = True
        self.hdf5_results_table.value = '<p role="status">Reading bounded scientific dataset previews…</p>'
        def inspect() -> None:
            try:
                self._read_physical_data(selected_source=selected)
            finally:
                def finish() -> None:
                    self._ingestion_busy = False
                    self.btn_read_hdf5.disabled = False
                self._ui_call(finish)
        self._physical_data_worker = threading.Thread(target=inspect, daemon=True)
        self._physical_data_worker.start()

    def _read_physical_data(self, *, selected_source: dict[str, Any] | None = None) -> None:
        try:
            if selected_source is None:
                choice = self._input_selectors['physical_data'].value
                if choice in self._input_library:
                    receipt = self._input_library[choice]
                    selected_source = {'input_id': choice, 'path': receipt['path'], 'filename': receipt['filename'], 'sha256': receipt['sha256']}
                else:
                    selected_source = dict(self._managed_physical_data) if self._managed_physical_data else {'path': self.inspector_file_input.value.strip()}
            fpath = Path(selected_source['path'])
            expected = selected_source.get('sha256')
            if expected is not None:
                if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-f]{64}', expected):
                    raise ValueError('The selected scientific archive has an invalid integrity receipt')
                with fpath.open('rb') as stream:
                    if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                        raise ValueError('Selected scientific archive changed after verification')
            if selected_source.get('input_id'):
                from cochem_base.config_loader import get_artifact_dir
                from cochem_base.interfaces.student_ingestion import preview_ingested_input
                previews = preview_ingested_input(selected_source['input_id'], artifact_dir=get_artifact_dir())
                source_sha256 = expected
            else:
                from cochem_base.interfaces.student_ingestion import preview_scientific_archive
                previews = preview_scientific_archive(fpath)
                with fpath.open("rb") as stream:
                    source_sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
            if expected is not None and source_sha256 != expected:
                raise ValueError('Selected scientific archive changed during inspection')
            filename = selected_source.get('filename', fpath.name)
            container_source = f"<p>Original file: {html.escape(filename)}; SHA-256: <code>{source_sha256}</code>.</p>"
            rows = []
            for preview in previews:
                rows.append("<tr>" + "".join(
                    f"<td><pre>{html.escape(str(value))}</pre></td>" for value in (
                        preview["name"], preview["shape"], preview["units"], preview["source"],
                        f"{preview['shown']} / {preview['total']}", preview["values"],
                    )
                ) + "</tr>")
            rendered = container_source + (
                f"<b>Scientific data read succeeded:</b> Previewed {len(previews)} datasets. HDF5 reads use SWMR and the shared file lock. "
                "Values are a bounded prefix of each dataset.<br/>"
                "<table><caption>Stored scientific values</caption><thead><tr>"
                + "".join(f"<th scope='col'>{label}</th>" for label in ("Dataset", "Shape", "Units", "Source", "Shown / total", "Values"))
                + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
            )
            self._ui_call(lambda: setattr(self.hdf5_results_table, 'value', rendered))
        except Exception as exc:
            message = str(exc)
            self._ui_call(lambda: setattr(self.hdf5_results_table, 'value', f"<b style='color:red;'>Scientific data read failed: {html.escape(message)}</b>"))

    def _refresh_topos_capabilities(self, b: Any = None) -> None:
        from cochem_base.core_engine.execution_authority import authorize_engine_execution

        if self._topos_running:
            return
        if self.calc_env_dropdown.value == "github-actions":
            self.btn_topos_submit.disabled = True
            self.topos_capabilities.value = "<p>Use the integrated TOPOS research panel for approved Actions searches. This native CREST/GOAT screening panel requires a configured local or HPC host.</p>"
            return
        available = {}
        missing = []
        for engine in ("crest", "orca"):
            try:
                available[engine] = authorize_engine_execution(engine, cores=1).executable
            except (ValueError, RuntimeError, OSError) as exc:
                missing.append(f"{engine.upper()}: {exc}")
        options = []
        if "crest" in available:
            options.append(("CREST NCI (GFN2-xTB screening)", "CREST_NCI"))
        if "orca" in available:
            options.append(("ORCA GOAT (XTB2 screening)", "GOAT"))
        if len(available) == 2:
            options.append(("Parallel CREST + GOAT union", "CREST_GOAT"))
        self._topos_engines = available
        self.topos_heuristic.options = options or [("[MISSING DATA] No audited search engine", "")]
        self.topos_heuristic.disabled = not options
        self.btn_topos_submit.disabled = not options or getattr(self, '_pipeline_running', False) or self._installation_running
        if self.calc_env_dropdown.value == 'hpc':
            self.btn_topos_submit.disabled = self.btn_topos_submit.disabled or bool(self._student_hpc_admission_reason())
        self.topos_capabilities.value = (
            "<p>Audited search engines: " + html.escape(", ".join(name.upper() for name in available) or "none") + ".</p>"
            + ("<details><summary>Unavailable search engines</summary><p>" + "<br/>".join(html.escape(item) for item in missing) + "</p></details>" if missing else "")
        )

    def _cleanup_topos_search(self) -> None:
        if self._topos_running and self._topos_broker is not None and self._topos_job_id is not None:
            self._topos_cancellation.set()
            try:
                self._topos_broker.cancel_search(self._topos_job_id)
            except (ValueError, RuntimeError, OSError):
                logger.exception("Could not stop owned TOPOS search during kernel shutdown")

    def _start_topos_search(self, b: Any = None) -> None:
        import uuid

        from cochem_base.calc.calculation_service import parse_run_geometry_identity
        from cochem_base.physics.nuclide_resolver import get_element
        from cochem_base.topos_runner import TOPOSExecutionBroker, TOPOSSearchConfig

        if self._topos_running:
            return
        if self.calc_env_dropdown.value == "hpc":
            try:
                geometry = self._student_current_xyz()
                identity = parse_run_geometry_identity(geometry)
                if self.multiplicity_input.value != 1:
                    raise ValueError("The installed native CREST/GOAT broker accepts a singlet state only")
                protocol = self.topos_heuristic.value
                if protocol not in {'CREST_NCI', 'GOAT', 'CREST_GOAT'}:
                    raise ValueError("Choose an available canonical native conformer-search protocol")
                cores = self._hpc_resources()['cores']
                native_search = {'input_xyz_path': 'inputs/starting-geometry.xyz', 'atom_count': len(identity.elements),
                    'protocol': protocol, 'max_hours': self.topos_walltime.value / 60,
                    'charge': self.charge_input.value, 'multiplicity': self.multiplicity_input.value,
                    'threads_per_engine': max(1, cores // 2) if protocol == 'CREST_GOAT' else cores}
                self._submit_student_hpc(native_search=native_search, geometry=geometry)
                self.topos_status.value = "<p role='status'>Native screening request staged for the HPC scheduler. Follow its queue state and verified results in the HPC panel; no login-host conformer calculation was launched.</p>"
            except (ValueError, RuntimeError, OSError) as exc:
                self.topos_status.value = f"<p role='alert'>HPC conformer search was not submitted: {html.escape(str(exc))}</p>"
            return
        if self.calc_env_dropdown.value == "github-actions":
            self.topos_status.value = "<p role='alert'>Use the integrated TOPOS research panel to submit an approved search on Actions. This native screening request was not started.</p>"
            return
        try:
            if self._pipeline_running or self._hpc_running or self._installation_running:
                raise ValueError("Wait for the active operation before starting another calculation")
            identity = parse_run_geometry_identity(self.matrix_geometry.value)
            symbols, coordinates = list(identity.nuclides), identity.coordinates_angstrom
            electrons = sum(get_element(symbol).atomic_number for symbol in identity.elements) - self.charge_input.value
            if self.multiplicity_input.value != 1 or electrons < 1 or electrons % 2:
                raise ValueError("This conformer interface accepts closed-shell, even-electron inputs; open-shell spin acceptance is not yet connected")
            if not self.topos_heuristic.value or self.topos_heuristic.disabled:
                raise ValueError("Refresh search engines after completing the Golden Registry audit")
            root = self._run_artifact_root() / "TOPOS" / f"submission_{uuid.uuid4().hex}"
            root.mkdir(parents=True)
            source = root / "input.xyz"
            source.write_text(
                f"{len(symbols)}\nUser supplied conformer-search geometry\n" + "\n".join(
                    symbol + " " + " ".join(f"{value:.17g}" for value in row)
                    for symbol, row in zip(symbols, coordinates, strict=True)
                ) + "\n", encoding="utf-8",
            )
            broker = TOPOSExecutionBroker(root / "Scratch", root / "Results")
            config = TOPOSSearchConfig(
                input_xyz_path=str(source), atom_count=len(symbols), protocol=self.topos_heuristic.value,
                max_hours=self.topos_walltime.value / 60, charge=self.charge_input.value,
                multiplicity=self.multiplicity_input.value, threads_per_engine=1,
                crest_binary=self._topos_engines.get("crest") if self.topos_heuristic.value != "GOAT" else None,
                orca_binary=self._topos_engines.get("orca") if self.topos_heuristic.value != "CREST_NCI" else None,
            )
            self._topos_job_id = broker.launch_search(config)
            self._topos_broker = broker
            self._topos_cancellation.clear()
            self._topos_running = True
            self.state.system_status = "TOPOS RUNNING"
            self._refresh_execution_gate()
            self.btn_topos_submit.disabled = True
            self.btn_topos_cancel.disabled = False
            self.btn_topos_promote.disabled = True
            self.topos_results.value = ""
            self._topos_worker = threading.Thread(target=self._poll_topos_search, daemon=True)
            self._topos_worker.start()
        except (ValueError, RuntimeError, OSError) as exc:
            self.topos_status.value = f"<p role='alert'>Conformer search was not started: {html.escape(str(exc))}</p>"

    def _poll_topos_search(self) -> None:
        broker, job = self._topos_broker, self._topos_job_id
        try:
            while True:
                if self._topos_cancellation.is_set():
                    broker.cancel_search(job)
                data = broker.poll_telemetry(job)
                status = data["status"]
                self.state.system_status = f"TOPOS {status}"
                self.topos_status.value = (
                    f"<p role='status' aria-live='polite'><b>Conformer search: {status}</b><br/>"
                    f"Job: <code>{html.escape(job)}</code><br/>"
                    f"Screening observations found: {data['candidates_found']}; retained screening observations: {data['deduplicated_count']}.<br/>"
                    f"Comparable lowest energy: {_observable(data['lowest_energy_hartree'], 12)} Hartree. "
                    f"Ranking scope: {html.escape(str(data.get('energy_ranking_scope', 'native producer context')))}.<br/>"
                    f"Diagnostics: <code>{html.escape(str(broker.scratch_root / job))}</code></p>"
                )
                if status != "RUNNING":
                    if status == "FAILED":
                        self.topos_status.value += f"<p role='alert'>{html.escape(str(data.get('error')))}</p>"
                    self.btn_topos_promote.disabled = status != "COMPLETED"
                    break
                self._topos_cancellation.wait(0.25)
        except (ValueError, RuntimeError, OSError) as exc:
            self.topos_status.value = f"<p role='alert'>Conformer monitoring failed: {html.escape(str(exc))}</p>"
            try:
                broker.cancel_search(job)
            except (ValueError, RuntimeError, OSError):
                logger.exception("Failed to stop owned conformer job %s", job)
        finally:
            self._topos_running = False
            self.btn_topos_cancel.disabled = True
            self._refresh_topos_capabilities()
            self._refresh_execution_gate()

    def _promote_topos_search(self, b: Any = None) -> None:
        import base64

        try:
            published = self._topos_broker.promote_artifacts(self._topos_job_id)
            ensemble = published["ensemble_xyz"]
            self.topos_results.value = (
                f"<p role='status'><b>Conformer ensemble published.</b><br/>"
                f"Validated ensemble and provenance: <code>{html.escape(str(published['promoted_dir']))}</code></p>"
            )
            if ensemble.stat().st_size <= 10 * 1024 * 1024:
                data = base64.b64encode(ensemble.read_bytes()).decode("ascii")
                self.topos_results.value += f"<p><a download='conformer-ensemble.xyz' href='data:chemical/x-xyz;base64,{data}'>Download conformer ensemble (XYZ)</a></p>"
            self.btn_topos_promote.disabled = True
        except (ValueError, RuntimeError, OSError, AttributeError) as exc:
            self.topos_results.value = f"<p role='alert'>Conformer ensemble was not published: {html.escape(str(exc))}</p>"

    def _selected_canonical_tier(self) -> str:
        selected = self.matrix_tier.value
        if selected in COMPLEXITY_TIERS:
            return selected
        method = self.matrix_method.value.upper()
        matches = [tier for tier, metadata in COMPLEXITY_TIERS.items()
                   if method in {name.upper() for name in metadata["methods"]}]
        if len(matches) != 1:
            raise MethodologyViolationError("Select an explicit T0--T9 tier for this method.")
        return matches[0]

    def _collect_run_config(self) -> dict[str, Any]:
        """Serialize only operations supported by the selected engine adapter."""
        from cochem_base.calc.calculation_service import CalculationMatrixConfig, parse_run_geometry
        from cochem_base.calc.t9_fallback import T9FallbackConfig
        if self.matrix_engine.value == "XTB":
            return self._xtb_run_config()
        if self.matrix_engine.value == "PYSCF":
            return self._pyscf_run_config()
        if self.matrix_engine.value == 'CFOUR':
            return self._cfour_run_config()
        if self.matrix_engine.value != "ORCA":
            raise MethodologyViolationError("Select an available calculation engine; ORCA and CFOUR are optional.")
        remote = self.calc_env_dropdown.value in {"github-actions", "hpc"}
        operation = self.actions_operation.value if self.calc_env_dropdown.value == "github-actions" else self.native_operation.value
        timeout = self.actions_timeout.value if self.calc_env_dropdown.value == "github-actions" else self.native_timeout.value
        if remote and self.t9_config_path.value.strip():
            raise MethodologyViolationError("Remote T9 uses the active-space form; computer-local configuration paths are not portable")
        self._check_dispersion_gate()
        if self.dispersion_warning.value:
            raise MethodologyViolationError("Resolve the methodology validation message before running or saving.")
        elements, coordinates = parse_run_geometry(self.matrix_geometry.value)
        fragments = detect_molecular_fragments(elements, coordinates)
        fallback = None
        if self.t9_config_path.value.strip():
            fallback = T9FallbackConfig.model_validate_json(Path(self.t9_config_path.value).expanduser().read_text(encoding='utf-8'))
        t9 = self._portable_t9_request()
        if self.multiplicity_input.value > 1 and t9 is None and fallback is None:
            raise MethodologyViolationError("Open-shell ORCA requires an explicit scientifically chosen T9 recovery active space before starting")
        if t9 is not None and not remote:
            observation = self._t9_backend_observation
            if (observation is None or not observation.get('available')
                    or not self._t9_backend_binding_matches(observation)):
                raise MethodologyViolationError('Wait for the actual PySCF recovery check or retry setup before configuring T9')
            interpreter = observation['executable']
            fallback = T9FallbackConfig.model_validate({**t9, 'python_executable': interpreter})
        scientific = self._selected_scientific_input()
        references = None
        if self.cb_recipe_r2.value:
            if self.matrix_method.value != 'wB97M-V' or self.matrix_basis.value != 'def2-QZVPP':
                raise MethodologyViolationError("Recipe R2 requires its verified wB97M-V/def2-QZVPP protocol")
            if operation not in {'optimization', 'optimization_frequencies'}:
                raise MethodologyViolationError("Recipe R2 requires intermolecular optimization")
            if not remote:
                references = Path(scientific['entrypoint_path']).expanduser().resolve(strict=True)
        config = CalculationMatrixConfig(
            geometry=self.matrix_geometry.value, engine="orca",
            method="HF" if self.matrix_method.value in {"HF/MINI", "HF/STO-3G"} else self.matrix_method.value,
            basis_set=self.matrix_basis.value,
            product_class=None if self.product_class_selector.value == "Screening (no product accuracy claim)" else self.product_class_selector.value,
            theory_tier=self._selected_canonical_tier(),
            charge=self.charge_input.value, multiplicity=self.multiplicity_input.value,
            implicit_solvation=self.matrix_solvation.value,
            cbs_cardinal_pair=self.matrix_cbs_pair.value,
            frozen_monomer_indices=list(range(len(elements))) if (self.cb_recipe_r1.value or self.cb_recipe_r2.value) and len(fragments) > 1 else None,
            recipe="R2" if self.cb_recipe_r2.value else "R1" if self.cb_recipe_r1.value and len(fragments) > 1 else None,
            r2_reference_manifest=references, t9_fallback=fallback,
            initial_hessian=self.scientific_initial_hessian.value,
            hessian_file=Path(scientific['entrypoint_path']) if scientific and scientific['kind'] == 'read_hessian' and not remote else None,
            grid_stage=3 if (self.product_class_selector.value == ProductClass.PRODUCT_C.value
                             or self.cb_recipe_r2.value
                             or operation in {"harmonic_frequencies", "optimization_frequencies"}) else 2,
            **{"is_opt": operation in {"optimization", "optimization_frequencies"},
                "is_freq": operation in {"harmonic_frequencies", "optimization_frequencies"},
                "is_vpt2": False, "timeout_seconds": float(timeout)},
        )
        return config.model_dump(mode="json")

    def _cfour_run_config(self) -> dict[str, Any]:
        """Use the native CFOUR operation validator for the selected request."""
        from cochem_base.interfaces.scientific_jobs import (
            calculation_capability,
            validate_job_configuration,
        )

        remote = self.calc_env_dropdown.value == 'github-actions'
        if (self.cb_recipe_r1.value or self.cb_recipe_r2.value or self.matrix_solvation.value
                or self.matrix_cbs_pair.value or self.t9_config_path.value.strip()
                or self.product_class_selector.value != "Screening (no product accuracy claim)"):
            raise MethodologyViolationError("The CFOUR adapter requires a molecular screening request without ORCA recipes, solvation, CBS or T9 recovery")
        method = 'HF' if self.matrix_method.value == 'HF/STO-3G' else self.matrix_method.value
        operation = self.actions_operation.value if remote else self.cfour_operation.value
        optimize = operation in {'optimization', 'optimization_frequencies'}
        config = CalculationMatrixConfig(
            geometry=self.matrix_geometry.value, engine='cfour', method=method,
            basis_set=self.matrix_basis.value,
            product_class=None, charge=self.charge_input.value, multiplicity=self.multiplicity_input.value,
            is_opt=optimize,
            is_freq=operation in {'harmonic_frequencies', 'optimization_frequencies'},
            initial_hessian='BFGS' if optimize else 'XTB2',
            is_vpt2=False,
            **({'timeout_seconds': float(self.actions_timeout.value)} if remote else {}),
        )
        validate_job_configuration(config)
        capability = calculation_capability(config)
        if capability.adapter_status != 'connected':
            raise MethodologyViolationError(f"CFOUR {capability.operation} is unavailable: {capability.reason}")
        return config.model_dump(mode='json')

    def _xtb_run_config(self) -> dict[str, Any]:
        from cochem_base.calc.calculation_service import CalculationMatrixConfig, parse_run_geometry
        from cochem_base.calc.xtb_execution import validate_xtb_config
        elements, _ = parse_run_geometry(self.matrix_geometry.value)
        if self.t9_config_path.value.strip():
            raise MethodologyViolationError("T9 recovery is configured for ORCA; clear the active-space configuration before xTB screening")
        config = CalculationMatrixConfig(
            geometry=self.matrix_geometry.value, engine="xtb", method=self.matrix_method.value,
            basis_set=self.matrix_basis.value, theory_tier=self._selected_canonical_tier(),
            charge=self.charge_input.value, multiplicity=self.multiplicity_input.value,
            product_class=None if self.product_class_selector.value == "Screening (no product accuracy claim)" else self.product_class_selector.value,
            implicit_solvation=self.matrix_solvation.value,
            cbs_cardinal_pair=self.matrix_cbs_pair.value,
            recipe="R1" if self.cb_recipe_r1.value else ("R2" if self.cb_recipe_r2.value else None),
            **({"is_opt": True, "is_freq": False, "timeout_seconds": float(self.actions_timeout.value)}
               if self.calc_env_dropdown.value == "github-actions" else {}),
        )
        validate_xtb_config(config, elements)
        return config.model_dump(mode="json")

    def _pyscf_run_config(self) -> dict[str, Any]:
        from cochem_base.calc.calculation_service import CalculationMatrixConfig, parse_run_geometry
        from cochem_base.physics.nuclide_resolver import get_element

        elements, coordinates = parse_run_geometry(self.matrix_geometry.value)
        if self.matrix_method.value not in {"HF", "HF/MINI", "HF/STO-3G"} or self._selected_canonical_tier() != "T2":
            raise MethodologyViolationError("The PySCF adapter supports T2 Hartree-Fock single points only")
        if self.multiplicity_input.value != 1:
            raise MethodologyViolationError("The PySCF RHF adapter requires a closed-shell singlet")
        electrons = sum(get_element(symbol).atomic_number for symbol in elements) - self.charge_input.value
        if electrons <= 0 or electrons % 2:
            raise MethodologyViolationError("PySCF RHF requires a positive even electron count")
        if (self.cb_recipe_r1.value or self.cb_recipe_r2.value or self.matrix_solvation.value
                or self.matrix_cbs_pair.value or self.t9_config_path.value.strip()
                or self.product_class_selector.value != "Screening (no product accuracy claim)"):
            raise MethodologyViolationError("PySCF RHF single points require screening mode without optimization recipes, solvation, CBS or T9 recovery")
        validate_method_matrix_compliance("HF", num_fragments=len(detect_molecular_fragments(elements, coordinates)))
        config = CalculationMatrixConfig(
            geometry=self.matrix_geometry.value, engine="pyscf", method="HF", basis_set=self.matrix_basis.value,
            theory_tier="T2", product_class=None, charge=self.charge_input.value, multiplicity=1,
            is_opt=False, is_freq=False,
        )
        return config.model_dump(mode="json")

    def _run_artifact_root(self) -> Path:
        from cochem_base.config_loader import get_artifact_dir
        return get_artifact_dir(self.artifact_output_path.value.strip() or None)

    def _build_pipeline_command(self) -> list[str]:
        """Export an equivalent CLI invocation for reproducibility."""
        if self.calc_env_dropdown.value == "github-actions":
            raise ValueError("GitHub Actions is selected. Use Run on GitHub Actions in BASE to submit, monitor and retrieve this calculation.")
        if self.calc_env_dropdown.value == "hpc":
            raise ValueError("HPC is selected. Use Submit HPC calculation so the configured scheduler allocates a compute node; a local CLI command is not generated.")
        config_path = self._prepare_pipeline()
        runtime = config_path.parent
        cli_path = Path(__file__).resolve().parents[2] / "cli.py"
        return [sys.executable, str(cli_path), "run", "--config", str(config_path),
                "--scratch", str(runtime / "Scratch"), "--output", str(runtime / "Results"), "--device", "cpu"]

    def _prepare_pipeline(self) -> Path:
        """Persist the validated configuration before native execution."""
        import uuid

        from cochem_base.topos_runner import _write_json
        config = self._collect_run_config()
        runtime = self._run_artifact_root() / "GUI" / f"run_{uuid.uuid4().hex}"
        runtime.mkdir(parents=True)
        config_path = runtime / "matrix_config.json"
        _write_json(config_path, config)
        return config_path

    def _save_matrix_config(self, b: Any) -> None:
        if self.calc_env_dropdown.value == "github-actions":
            self._prepare_actions_job()
            return
        self.btn_save_matrix.disabled = True
        self.matrix_output.clear_output()
        try:
            from cochem_base.topos_runner import _write_json
            config = self._collect_run_config()
            project = "".join(char for char in self.project_name.value if char.isalnum() or char in "-_") or "default_project"
            target = self._run_artifact_root() / project / "matrix_config.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            _write_json(target, config)
            operation = ('optimization + harmonic frequencies' if config['is_opt'] and config['is_freq'] else
                         'harmonic frequencies' if config['is_freq'] else 'optimization' if config['is_opt'] else 'single point')
            self.matrix_output.append_stdout(f"Saved {config['engine']} {operation} configuration: {target}\n")
        except Exception as exc:
            self.matrix_output.append_stdout(f"Configuration was not saved: {exc}\n")
        finally:
            self.btn_save_matrix.disabled = False

    def _execute_pipeline(self, b: Any) -> None:
        if self._pipeline_running:
            return
        if self.calc_env_dropdown.value == "hpc":
            self._submit_student_hpc()
            return
        if self.calc_env_dropdown.value == "github-actions":
            self._submit_student_actions()
            return
        self._check_dispersion_gate()
        if self.btn_execute.disabled:
            self.state.error_message = "Resolve the engine or methodology validation message before execution."
            return
        try:
            config_path = self._prepare_pipeline()
        except Exception as exc:
            self.state.error_message = str(exc)
            return
        self._pipeline_cancellation.clear()
        self._pipeline_running = True
        self.btn_topos_submit.disabled = True
        self.btn_execute.disabled = True
        self.btn_cancel.disabled = False
        self.state.system_status = 'Running Pipeline...'
        self.telemetry_output.clear_output()
        self.calculation_result.value = "<i>Calculation is running.</i>"
        self._pipeline_worker = threading.Thread(target=self._pipeline_thread, args=(config_path,), daemon=True)
        self._pipeline_worker.start()

    def _student_original_ingestion_input(self) -> dict[str, Any] | None:
        original = self._student_uploads.get(self.student_geometry_choice.value)
        if original is None or original.get('origin') != 'canonical_ingestion':
            return None
        source = self._input_library.get(original.get('source_input_id'))
        if source is None:
            raise ValueError('Refresh the retained input library before submitting its selected geometry')
        raw = Path(source['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != original['source_sha256']:
            raise ValueError('The preserved molecular source hash changed')
        suffix = Path(source['filename']).suffix.lstrip('.').lower()
        return {'filename': source['filename'], 'format': 'qcschema' if suffix == 'json' else suffix,
            'content': raw, 'record_index': original['source_frame']}

    def _student_periodic_input_bundle(self) -> dict[str, Any]:
        structure = self._input_library.get(self._input_selectors['periodic'].value)
        if structure is None:
            raise ValueError('Select a validated uploaded periodic structure before scheduler submission')
        content = Path(structure['path']).read_bytes()
        if hashlib.sha256(content).hexdigest() != structure['sha256']:
            raise ValueError('Retained periodic structure hash changed')
        pseudopotentials = {}
        for symbol, chooser in self._paw_pseudopotential_choices.items():
            item = self._input_library[chooser.value]
            raw = Path(item['path']).read_bytes()
            if hashlib.sha256(raw).hexdigest() != item['sha256']:
                raise ValueError('Retained pseudopotential hash changed for ' + symbol)
            pseudopotentials[symbol] = {'filename': item['filename'], 'sha256': item['sha256'], 'content': raw}
        return {'structure': {'filename': structure['filename'],
                'format': Path(structure['filename']).suffix.lstrip('.').lower(), 'content': content},
                'pseudopotentials': pseudopotentials}

    def _student_hpc_preflight_binding(self) -> tuple:
        """Detect registry or scheduler-command changes without contacting a controller."""
        from cochem_base.config_loader import resolve_config_path
        registry = resolve_config_path()
        def file_state(path: Path) -> tuple:
            try:
                state = path.stat()
                return (str(path), state.st_dev, state.st_ino, state.st_size, state.st_mtime_ns, state.st_ctime_ns)
            except OSError:
                return (str(path), None)
        commands = tuple((name, file_state(Path(target)) if (target := shutil.which(name)) else None)
                         for name in ('sbatch', 'squeue', 'scontrol', 'scancel', 'qsub', 'qstat', 'qdel'))
        return (str(registry), file_state(registry), os.environ.get('PATH', ''), commands)

    def _cache_student_hpc_preflight(self, result: dict, binding: tuple) -> None:
        """Record an actual connection observation; submission still checks it again."""
        self._hpc_preflight_generation += 1
        self._hpc_preflight_observation = {**result, 'binding': binding, 'observed_at': time.monotonic()}
        if result.get('ready') is True:
            self.hpc_connection_status.value = (
                '<p role="status">Connected ' + html.escape(str(result.get('scheduler', 'HPC')).upper()) +
                ' scheduler. Scientific inputs must also pass admission; each submission rechecks the connection.</p>')
        else:
            self.hpc_connection_status.value = (
                '<p role="alert">HPC scheduler access is unavailable: ' + html.escape(str(result.get('reason', 'Connection not verified'))) +
                '. No interface-host scientific fallback is performed. Correct the cluster connection or complete BASE setup on its login host, '
                'then select Check HPC connection.</p>')

    def _check_student_hpc_connection(self, b: Any = None) -> None:
        if self.calc_env_dropdown.value != 'hpc' or self._hpc_preflight_running:
            return
        self._hpc_preflight_observation = None
        if hasattr(self, 'btn_execute'):
            self._refresh_execution_gate()

    def _student_hpc_admission_reason(self) -> str:
        try:
            binding = self._student_hpc_preflight_binding()
        except (ValueError, RuntimeError, OSError) as exc:
            return 'HPC connection cannot be verified: ' + str(exc)
        observation = self._hpc_preflight_observation
        if (observation is None or observation.get('binding') != binding or
                observation.get('ready') is True and time.monotonic() - observation['observed_at'] > 30):
            self._start_student_hpc_preflight(binding)
            return 'Checking the configured HPC scheduler. Submission remains unavailable until access is verified.'
        if observation.get('ready') is not True:
            return 'HPC scheduler access is unavailable: ' + str(observation.get('reason', 'Connection not verified'))
        if self.scheduler_input.value not in {'auto', observation.get('scheduler')}:
            return 'The selected scheduler differs from the verified cluster connection.'
        return ''

    def _start_student_hpc_preflight(self, binding: tuple) -> None:
        if self._hpc_preflight_running or not hasattr(self, 'module_root'):
            return
        self._hpc_preflight_running = True
        self._hpc_preflight_generation += 1
        generation = self._hpc_preflight_generation
        module_root = Path(self.module_root.value)
        self.btn_hpc_connect.disabled = True
        self.hpc_connection_status.value = '<p role="status">Checking the configured HPC scheduler. Submission remains unavailable until access is verified.</p>'
        def check() -> None:
            client = None
            try:
                from cochem_base.config_loader import get_artifact_dir
                from cochem_base.interfaces.student_hpc import StudentHpcClient
                client = StudentHpcClient(artifact_dir=get_artifact_dir(), module_root=module_root, registry_path=Path(binding[0]))
                observation = client.preflight()
            except (ImportError, ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
                observation = {'ready': False, 'scheduler': None, 'reason': str(exc)}
            def publish() -> None:
                self._hpc_preflight_running = False
                if generation == self._hpc_preflight_generation:
                    if self._hpc_submission is None and client is not None:
                        self._hpc_client = client
                    self._cache_student_hpc_preflight(observation, binding)
                self._refresh_execution_gate()
            self._ui_call(publish)
        self._hpc_preflight_worker = threading.Thread(target=check, daemon=True)
        self._hpc_preflight_worker.start()

    def _hpc_resources(self) -> dict[str, Any]:
        from cochem_base.calc.slurm_submission import memory_megabytes, validate_slurm_walltime
        if self.nodes_input.value != 1:
            raise ValueError("BASE scheduler calculations require exactly one compute node")
        if type(self.tasks_per_node_input.value) is not int or self.tasks_per_node_input.value < 1:
            raise ValueError("Request a positive integer number of compute cores")
        resources = {"scheduler": self.scheduler_input.value, "queue": self.partition_input.value.strip(),
            "job_name": self.job_name_input.value.strip(), "cores": self.tasks_per_node_input.value,
            "memory_mb": memory_megabytes(self.mem_input.value.strip()),
            "walltime": validate_slurm_walltime(self.walltime_input.value.strip())}
        if self.email_input.value.strip():
            resources["email"] = self.email_input.value.strip()
        return resources

    def _submit_student_hpc(self, b: Any = None, *, calculation_override: dict[str, Any] | None = None,
                            provider: dict[str, Any] | None = None, geometry: str | None = None,
                            native_search: dict[str, Any] | None = None) -> None:
        """Submit scientific inputs to the configured scheduler without local fallback."""
        if self._hpc_running or self._hpc_retrieving or self._pipeline_running or self._topos_running or self._actions_running:
            self.slurm_status_output.value = "<p role='alert'>Wait for or cancel the active calculation before submitting another scheduler job.</p>"
            return
        try:
            resources = self._hpc_resources()
            calculation = (calculation_override if calculation_override is not None else
                self._collect_run_config() if provider is None and native_search is None else None)
            text = geometry if geometry is not None else self._student_current_xyz() if calculation_override is None else None
            files = ({provider['artifact']: text} if provider is not None else
                     {'inputs/starting-geometry.xyz': text} if text is not None else {})
            periodic_inputs = self._student_periodic_input_bundle() if calculation and calculation.get("periodic") is not None else None
            ingestion_inputs = self._student_original_ingestion_input() if periodic_inputs is None else None
            scientific_inputs = self._selected_scientific_input() if calculation and calculation.get("engine") == "orca" else None
            t9_request = self._portable_t9_request() if calculation and calculation.get("engine") == "orca" else None
        except (ValueError, RuntimeError, OSError, MethodologyViolationError) as exc:
            self.slurm_status_output.value = f"<p role='alert'>HPC request was not staged: {html.escape(str(exc))}. No interface-host calculation was started.</p>"
            self.state.error_message = str(exc)
            return
        self._hpc_running = True
        self._hpc_submission = None
        self._hpc_job_serial += 1
        self._hpc_monitor_stop.clear()
        self.btn_slurm_submit.disabled = True
        self.btn_hpc_refresh.disabled = True
        self.btn_hpc_retrieve.disabled = True
        self.btn_hpc_cancel.disabled = True
        self.state.system_status = 'Preparing scheduler submission'
        self.slurm_status_output.value = "<p role='status'>Checking the configured cluster scheduler and staging immutable scientific inputs…</p>"
        self._refresh_execution_gate()
        def submit() -> None:
            try:
                from cochem_base.config_loader import get_artifact_dir
                from cochem_base.interfaces.student_hpc import StudentHpcClient
                client = StudentHpcClient(artifact_dir=get_artifact_dir(), module_root=Path(self.module_root.value))
                self._hpc_client = client
                binding = self._student_hpc_preflight_binding()
                preflight = client.preflight()
                self._ui_call(lambda: self._cache_student_hpc_preflight(preflight, binding))
                if preflight.get('ready') is not True:
                    raise RuntimeError(preflight.get('reason', 'No configured cluster scheduler is available'))
                submission = client.submit(calculation, provider=provider, xyz_files=files,
                    resources=resources, native_search=native_search, ingestion_inputs=ingestion_inputs, periodic_inputs=periodic_inputs,
                    scientific_inputs=scientific_inputs, t9_request=t9_request)
                self._hpc_client = client
                self._hpc_submission = submission
                def submitted() -> None:
                    self.btn_hpc_refresh.disabled = False
                    self.btn_hpc_cancel.disabled = False
                    self.btn_cancel.disabled = False
                    self._render_student_hpc_status(submission)
                self._ui_call(submitted)
                self._poll_student_hpc()
            except (ImportError, ValueError, RuntimeError, OSError, KeyError) as exc:
                message = str(exc)
                def failed() -> None:
                    pending = self._hpc_submission is not None and self._hpc_submission.get("status") != "completed"
                    self._hpc_running = pending
                    self.btn_slurm_submit.disabled = pending
                    self.btn_hpc_refresh.disabled = self._hpc_submission is None
                    self.btn_hpc_cancel.disabled = not pending
                    self.slurm_status_output.value = f"<p role='alert'>HPC submission or monitoring failed: {html.escape(message)}. No interface-host scientific fallback is performed. Retained scheduler jobs can be reopened and their status refreshed.</p>"
                    self.state.error_message = message
                    self._refresh_execution_gate()
                self._ui_call(failed)
            finally:
                self._refresh_student_hpc_history()
        self._hpc_worker = threading.Thread(target=submit, daemon=True)
        self._hpc_worker.start()

    def _render_student_hpc_status(self, observation: dict[str, Any]) -> None:
        if self._hpc_submission is None:
            return
        for field in ("status", "conclusion"):
            if field in observation:
                self._hpc_submission[field] = observation[field]
        state = observation.get('status', 'unknown')
        finished = state == 'completed'
        self._hpc_running = not finished
        self.btn_hpc_refresh.disabled = False
        self.btn_hpc_cancel.disabled = finished
        self.btn_hpc_retrieve.disabled = not finished
        self.btn_slurm_submit.disabled = not finished
        self.btn_cancel.disabled = finished
        self.slurm_status_output.value = (
            f"<p role='status' aria-live='polite'><b>{html.escape(str(observation.get('scheduler', self._hpc_submission.get('scheduler', 'HPC'))).upper())} job "
            f"{html.escape(str(observation.get('job_id', self._hpc_submission.get('job_id', 'pending'))))}: {html.escape(str(state))}</b><br/>"
            f"Outcome: {html.escape(str(observation.get('conclusion') or 'pending'))}. "
            "Scheduler acceptance alone does not establish a completed scientific result.</p>"
        )
        self.state.system_status = 'HPC ' + str(state)
        self._refresh_execution_gate()

    def _poll_student_hpc(self) -> None:
        submission = dict(self._hpc_submission)
        client = self._hpc_client
        serial = self._hpc_job_serial
        while serial == self._hpc_job_serial and not self._hpc_monitor_stop.is_set():
            observation = client.status(submission)
            for field in ("status", "conclusion"):
                if field in observation:
                    submission[field] = observation[field]
            self._ui_call(lambda current=observation: self._render_student_hpc_status(current)
                if serial == self._hpc_job_serial else None)
            if observation.get('status') == 'completed':
                return
            self._hpc_monitor_stop.wait(5)

    def _refresh_student_hpc(self, b: Any = None) -> None:
        if self._hpc_client is None or self._hpc_submission is None:
            return
        self.btn_hpc_refresh.disabled = True
        submission = dict(self._hpc_submission)
        def refresh() -> None:
            try:
                observation = self._hpc_client.status(submission)
                self._ui_call(lambda: self._render_student_hpc_status(observation))
            except (ValueError, RuntimeError, OSError) as exc:
                message = str(exc)
                self._ui_call(lambda: setattr(self.slurm_status_output, 'value', f"<p role='alert'>HPC status could not be refreshed: {html.escape(message)}.</p>"))
            finally:
                self._ui_call(lambda: setattr(self.btn_hpc_refresh, 'disabled', False))
        self._hpc_refresh_worker = threading.Thread(target=refresh, daemon=True)
        self._hpc_refresh_worker.start()

    def _cancel_student_hpc(self, b: Any = None) -> None:
        if self._hpc_client is None or self._hpc_submission is None:
            return
        self.btn_hpc_cancel.disabled = True
        submission = dict(self._hpc_submission)
        def cancel() -> None:
            try:
                self._hpc_client.cancel(submission)
                self._ui_call(lambda: setattr(self.slurm_status_output, 'value', "<p role='status'>Scheduler cancellation requested. Refresh status to confirm the final queue outcome; partial diagnostics remain available.</p>"))
                self._refresh_student_hpc()
            except (ValueError, RuntimeError, OSError) as exc:
                message = str(exc)
                self._ui_call(lambda: setattr(self.slurm_status_output, 'value', f"<p role='alert'>HPC cancellation was not confirmed: {html.escape(message)}. Refresh status before taking another action.</p>"))
                self._ui_call(lambda: setattr(self.btn_hpc_cancel, 'disabled', False))
        self._hpc_cancel_worker = threading.Thread(target=cancel, daemon=True)
        self._hpc_cancel_worker.start()

    def _retrieve_student_hpc(self, b: Any = None) -> None:
        if self._hpc_client is None or self._hpc_submission is None or self._hpc_retrieving:
            return
        self._hpc_retrieving = True
        self.btn_hpc_retrieve.disabled = True
        submission = dict(self._hpc_submission)
        self.slurm_status_output.value = "<p role='status'>Verifying retained scheduler identity, compute-allocation provenance and result hashes…</p>"
        def retrieve() -> None:
            try:
                receipt = self._hpc_client.retrieve_results(submission)
                root = Path(receipt['path'])
                download = self._student_result_download_html(receipt)
                hessians = self._prepare_calculation_hessians(root)
                def imported() -> None:
                    report = receipt.get('report', {})
                    self.hpc_results_download.value = download
                    if report.get('status') == 'completed' and report.get('operation_performed') is True:
                        self._publish_calculation_hessians(hessians)
                        self._load_student_research_report(root)
                        self._collect_student_calculated_geometries(root)
                        self.calculation_result.value = '<p>Verified scheduler calculation results are available in Research results and Data Inspector.</p>'
                        self.slurm_status_output.value = '<p role="status">HPC results verified and imported. Scheduler job identity, compute-node setup and retained scientific file hashes were checked.</p>'
                        self.state.system_status = 'HPC results imported'
                    else:
                        self.slurm_status_output.value = f"<p role='alert'>Verified HPC diagnostics retained: {html.escape(str(report.get('error', 'Scientific execution did not complete')))}. No completed scientific result was accepted.</p>"
                self._ui_call(imported)
            except (ValueError, RuntimeError, OSError, KeyError) as exc:
                message = str(exc)
                self._ui_call(lambda: setattr(self.slurm_status_output, 'value', f"<p role='alert'>HPC results were not imported: {html.escape(message)}.</p>"))
            finally:
                self._hpc_retrieving = False
                self._ui_call(lambda: setattr(self.btn_hpc_retrieve, 'disabled', False))
        self._hpc_retrieve_worker = threading.Thread(target=retrieve, daemon=True)
        self._hpc_retrieve_worker.start()

    def _start_student_hpc_history(self) -> None:
        def restore() -> None:
            try:
                from cochem_base.config_loader import get_artifact_dir
                from cochem_base.interfaces.student_hpc import StudentHpcClient
                if self._hpc_client is None:
                    self._hpc_client = StudentHpcClient(artifact_dir=get_artifact_dir(), module_root=Path(self.module_root.value))
                self._refresh_student_hpc_history()
            except (ImportError, ValueError, RuntimeError, OSError) as exc:
                logger.info('HPC history is unavailable: %s', exc)
            finally:
                self._hpc_history_loaded.set()
        self._hpc_history_worker = threading.Thread(target=restore, daemon=True)
        self._hpc_history_worker.start()

    def _refresh_student_hpc_history(self) -> None:
        if self._hpc_client is None:
            return
        try:
            items = self._hpc_client.history()
            history = {str(item['request_id']): item for item in items}
            pending = next((item for item in reversed(items) if item.get('status') != 'completed'), None)
            if pending is not None and self._hpc_submission is None:
                self._hpc_running = True
                self._hpc_submission = dict(pending)
                self._hpc_job_serial += 1
            def publish() -> None:
                self._hpc_history = history
                self.hpc_history.options = [(f"{item.get('scheduler', 'HPC')} {item.get('job_id', 'pending')} ({item.get('status', 'unknown')})", key)
                    for key, item in history.items()] or [("No retained scheduler jobs", "")]
                self.btn_hpc_open.disabled = not bool(history)
                if pending is not None and self._hpc_submission is not None:
                    self.hpc_history.value = str(self._hpc_submission['request_id'])
                    self._render_student_hpc_status(self._hpc_submission)
            self._ui_call(publish)
        except (ValueError, RuntimeError, OSError, KeyError) as exc:
            logger.warning('Retained HPC history was not loaded: %s', exc)

    def _open_student_hpc_history(self, b: Any = None) -> None:
        item = getattr(self, '_hpc_history', {}).get(self.hpc_history.value)
        if item is None:
            return
        self._hpc_job_serial += 1
        self._hpc_submission = dict(item)
        self._render_student_hpc_status(item)
        self._refresh_student_hpc()

    def _prepare_actions_job(self) -> None:
        """Validate the direct request and provide an optional reproducibility copy."""
        import base64
        import hashlib

        from cochem_base.calc.calculation_service import CalculationMatrixConfig, parse_run_geometry
        from cochem_base.interfaces.actions_jobs import validate_configuration

        self._invalidate_actions_job()
        try:
            repository = self._actions_repository()
            if self.matrix_engine.value not in {'ORCA', 'CFOUR', 'XTB'}:
                raise ValueError("The course workflows accept molecular ORCA, CFOUR or supported free xTB jobs only.")
            if self.matrix_engine.value in {'ORCA', 'CFOUR'} and not self._remote_engine_availability[self.matrix_engine.value.lower()].get('provisionable'):
                raise ValueError("Licensed-engine archive access must be verified for this assignment before submission")
            if self.t9_config_path.value.strip():
                raise ValueError("Remote T9 must use the explicit portable active-space form")
            if len(parse_run_geometry(self.matrix_geometry.value)[0]) > 50:
                raise ValueError("The course Actions profile accepts at most 50 atoms per job.")
            config = self._collect_run_config()
            model = CalculationMatrixConfig.model_validate(config)
            if any(getattr(model, name) is not None for name in ("hessian_file", "r2_reference_manifest", "t9_fallback", "periodic")):
                raise ValueError("The course job cannot reference files on this computer or a separate calculation environment.")
            payload = model.model_dump_json(indent=2).encode("utf-8") + b"\n"
            if len(payload) > 256 * 1024:
                raise ValueError("The course job JSON must be at most 256 KiB.")
            if model.engine == 'xtb':
                from cochem_base.calc.xtb_execution import validate_xtb_config
                validate_xtb_config(model, parse_run_geometry(model.geometry)[0])
            elif not (self._selected_scientific_input() or self._portable_t9_request()):
                validate_configuration(payload, model.model_dump(mode="json"))
            project = re.sub(r"[^A-Za-z0-9_-]", "_", self.project_name.value).strip("_")[:64] or "molecule"
            engine_name = model.engine.upper()
            filename = f"{project}-{model.engine}-job.json"
            job_file = f"jobs/{filename}"
            digest = hashlib.sha256(payload).hexdigest()
            self._last_actions_job = {"job_file": job_file, "config": model.model_dump(mode="json"), "sha256": digest}
            encoded = base64.b64encode(payload).decode("ascii")
            self.actions_job_download.value = (
                "<p role='status'><b>Actions request validated.</b> No calculation has been submitted or run.</p>"
                f"<p><a download='{filename}' href='data:application/json;base64,{encoded}'>Download {engine_name} request JSON</a></p>"
                "<p>This copy is optional. Select <b>Run on GitHub Actions</b> to submit, monitor and retrieve your calculation directly in BASE.</p>"
                f"<p>Input SHA-256: <code>{digest}</code>. Calculation timeout: {self.actions_timeout.value} seconds.</p>"
            )
            self.state.system_status = "Actions job prepared"
            self.state.error_message = ""
            self.calculation_result.value = "<p>Remote request prepared; awaiting submission and verified results from GitHub Actions.</p>"
        except (ValueError, RuntimeError, OSError, MethodologyViolationError) as exc:
            self.state.error_message = str(exc)
            self.actions_job_download.value = f"<p role='alert'>Actions job was not prepared: {html.escape(str(exc))}</p>"

    def _submit_student_actions(self, b: Any = None, *, provider: dict[str, Any] | None = None,
                               calculation_override: dict[str, Any] | None = None,
                               periodic_inputs: dict[str, Any] | None = None) -> None:
        """Submit data, dispatch and correlate a hosted calculation through BASE."""
        if self._actions_running or self._hpc_running or self._hpc_retrieving or self._pipeline_running or self._topos_running:
            return
        try:
            geometry = calculation_override['geometry'] if calculation_override is not None else self._student_current_xyz()
            repository = self._actions_repository()
            branch = self.gh_branch_input.value.strip() or "main"
            if calculation_override is not None:
                if provider is not None or periodic_inputs is None:
                    raise ValueError('A typed periodic calculation requires its bound uploaded inputs')
                configuration = CalculationMatrixConfig.model_validate(calculation_override).model_dump(mode='json')
                scientific_input = None
                t9_request = None
            elif provider is None:
                self._prepare_actions_job()
                if self._last_actions_job is None:
                    return
                configuration = dict(self._last_actions_job["config"])
                configuration["geometry"] = geometry
                scientific_input = self._selected_scientific_input()
                t9_request = self._portable_t9_request()
            else:
                from cochem_base.interfaces.student_research import validate_provider_request
                validate_provider_request(provider)
                configuration = None
                scientific_input = None
                t9_request = None
        except (ValueError, RuntimeError, OSError) as exc:
            self.state.error_message = str(exc)
            self.actions_status.value = f"<p role='alert'>Calculation was not submitted: {html.escape(str(exc))}</p>"
            return
        inputs: dict[str, str | bytes] = {"inputs/starting-geometry.xyz": geometry}
        ingestion_input = None
        original = self._student_uploads.get(self.student_geometry_choice.value) if calculation_override is None else None
        if original:
            content = Path(original["path"]).read_bytes()
            if hashlib.sha256(content).hexdigest() != original["sha256"]:
                self.state.error_message = "Original input geometry hash no longer matches; calculation was not submitted."
                return
            inputs["inputs/original-student-geometry.xyz"] = content
            if original.get('origin') == 'canonical_ingestion':
                source = self._input_library.get(original.get('source_input_id'))
                if source is None:
                    self.state.error_message = 'The selected geometry needs its verified original input-library source. Refresh retained inputs before submission.'
                    return
                raw_source = Path(source['path']).read_bytes()
                if hashlib.sha256(raw_source).hexdigest() != original['source_sha256']:
                    self.state.error_message = 'Original scientific source hash changed; calculation was not submitted.'
                    return
                source_format = Path(source['filename']).suffix.lstrip('.').lower()
                ingestion_input = {'filename': source['filename'], 'format': 'qcschema' if source_format == 'json' else source_format,
                    'content': raw_source, 'record_index': original['source_frame']}
            for item in original.get("monomer_sources", []):
                monomer = self._student_uploads.get(item["id"])
                if monomer:
                    raw = Path(monomer["path"]).read_bytes()
                    if hashlib.sha256(raw).hexdigest() != item["sha256"]:
                        self.state.error_message = "Preserved monomer input hash changed; research request was not submitted."
                        return
                    inputs[f"inputs/monomer-{item['id']}.xyz"] = raw
        self._actions_submission = None
        self._actions_client = None
        self._actions_running = True
        self._refresh_execution_gate()
        self._actions_monitor_stop.clear()
        self.btn_execute.disabled = True
        self.btn_cancel.disabled = True
        self.btn_actions_retrieve.disabled = True
        self.actions_results_download.value = ""
        self.actions_status.value = "<p role='status' aria-live='polite'>Checking access and submitting your calculation…</p>"
        self.state.system_status = "Submitting Actions calculation"
        self._actions_input_record = dict(original) if original else None
        cores, maxcore_mb = self.actions_cores.value, self.actions_memory.value
        def submit() -> None:
            try:
                from cochem_base.config_loader import get_artifact_dir
                from cochem_base.interfaces.student_actions import StudentActionsClient
                client = StudentActionsClient(repository, branch=branch,
                    repository_root=Path(os.environ.get("COCHEM_ASSIGNMENT_ROOT", str(_REPO_ROOT))), artifact_dir=get_artifact_dir())
                submission = client.submit(configuration, xyz_files=inputs, provider=provider,
                    scientific_inputs=scientific_input, t9_request=t9_request,
                    **({'periodic_inputs': periodic_inputs} if periodic_inputs is not None else {}),
                    **({'ingestion_inputs': ingestion_input} if ingestion_input is not None else {}),
                    cores=cores, maxcore_mb=maxcore_mb)
                self._actions_client = client
                self._actions_submission = submission
                self._retain_student_actions_submission(submission)
                def submitted() -> None:
                    self.btn_cancel.disabled = False
                    self.btn_actions_refresh.disabled = False
                    self.state.error_message = ""
                    self.actions_job_download.value = "<p>The calculation has been submitted through BASE. Configuration export is available separately for reproducibility.</p>"
                    self._render_student_actions_status(submission)
                self._ui_call(submitted)
                self._poll_student_actions()
            except (ValueError, RuntimeError, OSError, ImportError) as exc:
                message = str(exc)
                rejected = getattr(exc, 'submission', None)
                if isinstance(rejected, dict) and rejected.get('status') == 'rejected':
                    self._retain_student_actions_submission(rejected)
                def failure() -> None:
                    dispatched = self._actions_submission is not None
                    self._actions_running = dispatched
                    self.btn_cancel.disabled = not dispatched
                    self.state.error_message = message
                    self.state.system_status = "Actions monitoring requires attention" if dispatched else "Actions submission failed"
                    self.actions_status.value = (
                        f"<p role='alert'>Calculation {'was submitted, but monitoring paused' if dispatched else 'was not submitted'}: "
                        f"{html.escape(message)}. {'Use Refresh calculation status; do not create a duplicate request.' if dispatched else 'BASE has retained your original geometry.'}</p>"
                    )
                    self._refresh_execution_gate()
                self._ui_call(failure)
        self._actions_worker = threading.Thread(target=submit, daemon=True)
        self._actions_worker.start()

    def _render_student_actions_status(self, observation: dict[str, Any]) -> None:
        if self._actions_submission is not None and observation.get("request_id") == self._actions_submission.get("request_id"):
            self._actions_submission = dict(observation)
            self._retain_student_actions_submission(observation)
        status = observation.get("status", "awaiting_workflow")
        conclusion = observation.get("conclusion")
        request = observation.get("request_id", "")
        url = observation.get("url")
        link = ""
        if isinstance(url, str) and url.startswith("https://github.com/"):
            link = f" <a href='{html.escape(url, quote=True)}' target='_blank' rel='noopener'>Calculation run details</a>"
        self.actions_status.value = (
            f"<p role='status' aria-live='polite'><b>Calculation: {html.escape(str(status))}</b>"
            + (f"; result: {html.escape(str(conclusion))}" if conclusion else "")
            + f".<br/>Request: <code>{html.escape(str(request))}</code>." + link + "</p>"
        )
        if status == 'dispatch_unconfirmed':
            self.actions_status.value += "<p role='status'>GitHub acknowledgement is delayed. BASE is checking the original request; do not submit it again.</p>"
        complete = status in {"completed", "rejected"}
        self._actions_running = not complete
        self.btn_cancel.disabled = complete
        self.btn_actions_retrieve.disabled = not (complete and conclusion is not None)
        self.btn_actions_retrieve.description = "Retrieve and inspect results" if conclusion == "success" else "Retrieve calculation diagnostics"
        self.state.system_status = f"Actions {conclusion if complete and conclusion else status}"
        self._actions_last_status = observation
        self.btn_actions_open.disabled = not bool(getattr(self, "_actions_history_records", {})) or self._actions_running
        self._refresh_execution_gate()

    def _retain_student_actions_submission(self, submission: dict[str, Any]) -> None:
        from cochem_base.config_loader import get_artifact_dir
        request_id = str(submission.get("request_id", ""))
        if not re.fullmatch(r"[a-f0-9-]{36}", request_id):
            raise ValueError("Remote submission requires a UUID identity")
        directory = get_artifact_dir() / "StudentActions" / request_id
        directory.mkdir(parents=True, exist_ok=True)
        temporary = directory / f".submission-{uuid.uuid4().hex}.json"
        temporary.write_text(json.dumps(submission, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(directory / "submission.json")
        self._ui_call(self._refresh_student_actions_history)

    def _refresh_student_actions_history(self) -> None:
        from cochem_base.config_loader import get_artifact_dir
        root = get_artifact_dir() / "StudentActions"
        observed = {}
        if root.is_dir() and not root.is_symlink():
            candidates = []
            paths = list(root.glob("*/submission.json")) + list((root / "submissions").glob("*.json"))
            for path in paths:
                try:
                    if not path.is_symlink() and not path.parent.is_symlink():
                        candidates.append((path.stat().st_mtime, path))
                except OSError:
                    continue
            for _, path in sorted(candidates, reverse=True)[:100]:
                try:
                    if path.is_symlink() or path.stat().st_size > 64 * 1024:
                        continue
                    record = json.loads(path.read_text(encoding="utf-8"))
                    key = str(record["request_id"])
                    if re.fullmatch(r"[a-f0-9-]{36}", key) and isinstance(record.get("repository"), str) and record.get("request_kind") != "capability_probe":
                        observed.setdefault(key, record)
                except (ValueError, OSError, KeyError, TypeError):
                    continue
        self._actions_history_records = observed
        selected = self.actions_history.value
        self.actions_history.options = [(f"{record['repository']} · {record.get('status', 'submitted')} · {key[:8]}", key)
                                        for key, record in observed.items()] or [("No retained calculations", "")]
        if selected in observed:
            self.actions_history.value = selected
        self.btn_actions_open.disabled = not bool(observed) or self._actions_running

    def _open_student_actions_history(self, b: Any = None) -> None:
        if self._actions_running or self._hpc_running or self._hpc_retrieving or self._pipeline_running or self._topos_running:
            self.actions_status.value = "<p role='alert'>Finish or cancel the current calculation before opening another.</p>"
            return
        record = self._actions_history_records.get(self.actions_history.value)
        if not record:
            return
        self.btn_actions_open.disabled = True
        def reopen() -> None:
            try:
                from cochem_base.config_loader import get_artifact_dir
                from cochem_base.interfaces.student_actions import (
                    StudentActionsClient,
                    verify_retained_results,
                )
                artifacts = get_artifact_dir()
                retained = artifacts / 'StudentActions' / record['request_id'] / 'retained-result.json'
                if record.get('status') == 'rejected':
                    def rejection() -> None:
                        self._actions_submission = dict(record)
                        self._actions_client = None
                        self._render_student_actions_status(record)
                        self.btn_actions_refresh.disabled = True
                        self.actions_status.value += '<p role="alert">GitHub rejected this original request before a calculation run was accepted. Correct assignment access, then submit a new request; this retained identity remains unchanged.</p>'
                    self._ui_call(rejection)
                elif retained.is_file():
                    if retained.is_symlink() or retained.stat().st_size > 128 * 1024:
                        raise ValueError('The retained result receipt is invalid')
                    saved = json.loads(retained.read_text(encoding='utf-8'))
                    submission = saved['submission']
                    identity = ('request_id', 'repository', 'source_sha', 'worker_source_sha', 'payload_sha256', 'run_id', 'run_attempt')
                    if saved.get('schema_version') != 'cochem.student-retained-result/1' or any(submission.get(key) != record.get(key) for key in identity):
                        raise ValueError('The retained result differs from the selected calculation identity')
                    path = Path(saved['path']).absolute()
                    if not path.resolve().is_relative_to((artifacts / 'StudentResults').resolve()):
                        raise ValueError('The retained result is outside this student workspace')
                    receipt = verify_retained_results(path, submission)
                    download = self._student_result_download_html(receipt)
                    hessians = self._prepare_calculation_hessians(Path(receipt["path"]))
                    def imported() -> None:
                        self._actions_submission = dict(submission)
                        self._actions_client = None
                        self._actions_retrieved = receipt
                        self._render_student_actions_status(submission)
                        self._apply_student_engine_diagnostics(receipt['report'], submission)
                        if receipt['report'].get('status') == 'completed' and receipt['report'].get('operation_performed') is True:
                            self._publish_calculation_hessians(hessians)
                            self._import_student_actions_results(receipt)
                            self.actions_status.value = '<p role="status"><b>Retained results verified and reopened.</b> Original request, run, approved sources and every retained file hash were checked without downloading or rerunning chemistry.</p>'
                        else:
                            self.actions_status.value = '<p role="status">Retained calculation diagnostics verified and reopened. No incomplete scientific result has been accepted.</p>'
                        self.actions_results_download.value = download
                        self.btn_actions_refresh.disabled = True
                        self.btn_actions_retrieve.disabled = True
                    self._ui_call(imported)
                else:
                    client = StudentActionsClient(record['repository'], branch=record['branch'],
                        repository_root=Path(os.environ.get('COCHEM_ASSIGNMENT_ROOT', str(_REPO_ROOT))), artifact_dir=artifacts)
                    self._actions_client = client
                    self._actions_submission = dict(record)
                    self._ui_call(lambda: setattr(self.btn_actions_refresh, 'disabled', False))
                    self._refresh_student_actions()
            except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
                message = str(exc)
                self._ui_call(lambda: setattr(self.actions_status, 'value', f'<p role="alert">Previous calculation could not be reopened: {html.escape(message)}. No unverified data was accepted.</p>'))
            finally:
                self._ui_call(lambda: setattr(self.btn_actions_open, 'disabled', False))
        self._actions_reopen_worker = threading.Thread(target=reopen, daemon=True)
        self._actions_reopen_worker.start()

    def _poll_student_actions(self) -> None:
        deadline = time.monotonic() + 90 * 60
        while self._actions_submission is not None and not self._actions_monitor_stop.is_set():
            observation = self._actions_client.status(self._actions_submission)
            self._ui_call(lambda current=observation: self._render_student_actions_status(current))
            if observation.get("status") == "completed":
                return
            if time.monotonic() >= deadline:
                self._actions_client.cancel(self._actions_submission)
                self._ui_call(lambda: setattr(self.actions_status, "value",
                    "<p role='alert'>The 90-minute monitoring limit was reached. BASE requested cancellation; refresh status to confirm the final workflow outcome.</p>"))
                return
            self._actions_monitor_stop.wait(5)

    def _refresh_student_actions(self, b: Any = None) -> None:
        if self._actions_submission is None or self._actions_client is None:
            return
        self.btn_actions_refresh.disabled = True
        def refresh() -> None:
            try:
                observation = self._actions_client.status(self._actions_submission)
                self._ui_call(lambda: self._render_student_actions_status(observation))
            except (ValueError, RuntimeError, OSError) as exc:
                message = str(exc)
                self._ui_call(lambda: setattr(self.actions_status, "value", f"<p role='alert'>Status could not be refreshed: {html.escape(message)}</p>"))
            finally:
                self._ui_call(lambda: setattr(self.btn_actions_refresh, "disabled", False))
        self._actions_refresh_worker = threading.Thread(target=refresh, daemon=True)
        self._actions_refresh_worker.start()

    def _cancel_student_actions(self, b: Any = None) -> None:
        if self._actions_submission is None or self._actions_client is None:
            return
        self.btn_cancel.disabled = True
        self.state.system_status = "Requesting remote cancellation"
        def cancel() -> None:
            try:
                self._actions_client.cancel(self._actions_submission)
                self._ui_call(lambda: setattr(self.actions_status, "value",
                    "<p role='status'>Cancellation requested. BASE continues monitoring until GitHub confirms the final outcome.</p>"))
            except (ValueError, RuntimeError, OSError) as exc:
                message = str(exc)
                self._ui_call(lambda: setattr(self.actions_status, "value", f"<p role='alert'>Cancellation could not be confirmed: {html.escape(message)}. Refresh status.</p>"))
                self._ui_call(lambda: setattr(self.btn_cancel, "disabled", False))
        self._actions_cancel_worker = threading.Thread(target=cancel, daemon=True)
        self._actions_cancel_worker.start()

    def _retrieve_student_actions(self, b: Any = None) -> None:
        if self._actions_submission is None or self._actions_client is None:
            return
        self.btn_actions_retrieve.disabled = True
        self._actions_retrieving = True
        self.actions_status.value = "<p role='status'>Retrieving and verifying calculation provenance and file hashes…</p>"
        submission = dict(self._actions_submission)
        def retrieve() -> None:
            try:
                from cochem_base.config_loader import get_artifact_dir
                destination = get_artifact_dir() / "StudentResults" / str(submission["request_id"])
                if destination.exists():
                    destination = destination.parent / f"{submission['request_id']}-{uuid.uuid4().hex}"
                receipt = self._actions_client.download_results(submission, destination)
                self._actions_retrieved = receipt
                submission.update(run_id=receipt['report']['run_id'], run_attempt=receipt['report']['run_attempt'])
                self._retain_student_actions_submission(submission)
                retained = get_artifact_dir() / 'StudentActions' / submission['request_id'] / 'retained-result.json'
                retained.parent.mkdir(parents=True, exist_ok=True)
                retained.write_text(json.dumps({'schema_version': 'cochem.student-retained-result/1',
                    'path': receipt['path'], 'submission': submission}, indent=2, allow_nan=False) + '\n', encoding='utf-8')
                retained.chmod(0o600)
                download = self._student_result_download_html(receipt)
                hessians = self._prepare_calculation_hessians(Path(receipt["path"]))
                def imported() -> None:
                    try:
                        report = receipt.get("report", {})
                        self._apply_student_engine_diagnostics(report, submission)
                        if report.get("status") == "completed" and report.get("operation_performed") is True:
                            self._publish_calculation_hessians(hessians)
                            self._import_student_actions_results(receipt)
                            self.actions_status.value = "<p role='status'><b>Results verified and imported.</b> Request, workflow, source identity and every retained file hash have been checked.</p>"
                            self.state.system_status = "Actions results imported"
                        else:
                            reason = report.get("error", "The workflow did not complete its scientific operation. Review the retained diagnostics.")
                            self.actions_status.value = f"<p role='alert'><b>Diagnostics verified and imported.</b> Calculation did not complete: {html.escape(str(reason))}. No scientific result has been accepted.</p>"
                            self.state.system_status = "Actions diagnostics imported"
                        self.actions_results_download.value = download
                    except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
                        self.actions_status.value = f"<p role='alert'>Verified artifacts were retained, but their scientific view could not be imported: {html.escape(str(exc))}.</p>"
                        self.actions_results_download.value = download
                        self.state.system_status = "Result inspection requires attention"
                self._ui_call(imported)
            except (ValueError, RuntimeError, OSError) as exc:
                message = str(exc)
                self._ui_call(lambda: setattr(self.actions_status, "value",
                    f"<p role='alert'>Results were not imported: {html.escape(message)}. No unverified science has been accepted.</p>"))
            finally:
                self._actions_retrieving = False
                self._ui_call(lambda: setattr(self.btn_actions_retrieve, "disabled", False))
        self._actions_retrieve_worker = threading.Thread(target=retrieve, daemon=True)
        self._actions_retrieve_worker.start()

    def _apply_student_engine_diagnostics(self, report: dict[str, Any], submission: dict[str, Any]) -> None:
        if report.get('failure_category') == 'engine_provisioning':
            unavailable = report.get('engine_availability', {})
            if isinstance(unavailable, dict) and submission.get('repository') == self.gh_repo_input.value.strip() and submission.get('branch') == (self.gh_branch_input.value.strip() or 'main'):
                for engine in ('orca', 'cfour'):
                    item = unavailable.get(engine)
                    if isinstance(item, dict) and item.get('status') == 'unavailable' and item.get('provisionable') is False:
                        self._remote_engine_availability[engine] = item
                self._refresh_engine_choices()
                self._refresh_research_engine_choices()

    def _import_student_actions_results(self, receipt: dict[str, Any]) -> None:
        root = Path(receipt["path"]).resolve()
        if not root.is_dir():
            raise ValueError("Verified result directory is unavailable")
        report = receipt.get("report", {})
        if report.get("status") != "completed" or report.get("operation_performed") is not True:
            raise ValueError("The verified package contains diagnostics for an incomplete calculation, not completed scientific results")
        archives = sorted(path for path in root.rglob('*') if path.suffix.lower() in {'.h5', '.hdf5', '.npz'} and path.is_file())
        xyz = sorted(root.rglob("*.xyz"))
        if archives:
            manifest = json.loads((root / 'publication-manifest.json').read_text(encoding='utf-8'))
            source = archives[0]
            identity = manifest['files'][source.relative_to(root).as_posix()]
            self._on_read_hdf5_clicked(None, result_source={'path': str(source), 'filename': source.name,
                'sha256': identity['sha256']})
        if xyz:
            final = next((path for path in xyz if path.name in {"optimized.xyz", "xtbopt.xyz", "final.xyz"}), None)
            if final:
                self.module_artifact.value = str(final)
        self._collect_student_calculated_geometries(root)
        if self._actions_input_record:
            manifest = root.parent / f"{receipt.get('request_id', 'results')}-student-original-input.json"
            manifest.write_text(json.dumps(self._actions_input_record, indent=2) + "\n", encoding="utf-8")
        self.calculation_result.value = (
            f"<p><b>Verified calculation results</b> for request <code>{html.escape(str(receipt.get('request_id', '')))}</code>. "
            "Open Data Inspector for native observables and Research results for module tables and figures.</p>"
        )
        if hasattr(self, "_load_student_research_report"):
            self._load_student_research_report(root)

    def _student_result_download_html(self, receipt: dict[str, Any]) -> str:
        """Prepare bounded downloads on the retrieval worker, preserving the GUI loop."""
        import io
        import zipfile
        root = Path(receipt["path"]).resolve()
        files = [path for path in sorted(root.rglob("*")) if path.is_file() and not path.is_symlink()]
        if sum(path.stat().st_size for path in files) > 32 * 1024 * 1024:
            url = (self._actions_submission or {}).get("url", "")
            return f"<p>The bundle exceeds the browser's 32 MiB inline limit. <a href='{html.escape(str(url), quote=True)}' target='_blank' rel='noopener'>Download its artifact from the calculation run</a>.</p>"
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in files:
                archive.write(path, path.relative_to(root).as_posix())
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"<p><a download='cochem-calculation-{html.escape(str(receipt.get('request_id', 'results')))}.zip' href='data:application/zip;base64,{encoded}'>Download calculation bundle</a></p>"

    def _collect_student_calculated_geometries(self, root: Path) -> None:
        from cochem_base.geometry.nuclide_geometry import parse_geometry_identity
        request = json.loads((root / "request.json").read_text(encoding="utf-8"))
        state = request.get("calculation") or request.get("provider", {}).get("options", {}).get("topos_request", {}).get("molecule", {})
        charge, multiplicity = state.get("charge"), state.get("multiplicity")
        if type(charge) is not int or type(multiplicity) is not int:
            self.btn_actions_use_geometry.disabled = True
            return
        geometries = {}
        for source in sorted(root.rglob("result.json"))[:2000]:
            if source.is_symlink() or source.stat().st_size > 32 * 1024 * 1024:
                continue
            try:
                raw = source.read_bytes()
                native = json.loads(raw)
                if native.get("converged") is not True or not math.isfinite(native["energy_hartree"]):
                    continue
                symbols = native.get("nuclides", native.get("elements"))
                coordinates = native["coordinates_angstrom"]
                text = str(len(symbols)) + "\nVerified native calculation geometry; angstrom\n" + "\n".join(
                    label + " " + " ".join(format(value, ".17g") for value in point)
                    for label, point in zip(symbols, coordinates, strict=True)) + "\n"
                parse_geometry_identity(text)
                key = source.relative_to(root).as_posix()
                geometries[key] = {"xyz": text, "charge": charge, "multiplicity": multiplicity,
                    "source": str(source), "source_sha256": hashlib.sha256(raw).hexdigest(),
                    "request_id": request["request_id"], "optimization_performed": native.get("optimization_performed", False),
                    "fragments": state.get("fragments") or (self._actions_input_record or {}).get("fragments"),
                    "fragment_states": state.get("fragment_states") or (self._actions_input_record or {}).get("fragment_states")}
            except (ValueError, KeyError, TypeError, OSError):
                continue
        self._actions_calculated_geometries = geometries
        self.actions_calculated_geometry.options = [(f"{key} ({'optimized' if item['optimization_performed'] else 'supplied coordinates'})", key)
            for key, item in geometries.items()] or [("No retained calculated geometry", "")]
        self.btn_actions_use_geometry.disabled = not bool(geometries)

    def _use_student_calculated_geometry(self, b: Any = None) -> None:
        from cochem_base.config_loader import get_artifact_dir
        from cochem_base.geometry.nuclide_geometry import parse_geometry_identity
        item = getattr(self, "_actions_calculated_geometries", {}).get(self.actions_calculated_geometry.value)
        if not item:
            return
        try:
            if hashlib.sha256(Path(item["source"]).read_bytes()).hexdigest() != item["source_sha256"]:
                raise ValueError("Calculated source geometry changed after verified import")
            identity = parse_geometry_identity(item["xyz"])
            key = uuid.uuid4().hex
            directory = get_artifact_dir() / "StudentInputs" / key
            directory.mkdir(parents=True, exist_ok=False)
            path = directory / "calculated-geometry.xyz"
            content = item["xyz"].encode("utf-8")
            path.write_bytes(content)
            path.chmod(0o444)
            record = {"schema_version": "cochem.student-input/1", "id": key, "filename": path.name,
                "path": str(path), "sha256": hashlib.sha256(content).hexdigest(), "byte_count": len(content),
                "atom_count": len(identity.elements), "elements": list(identity.elements), "nuclides": list(identity.nuclides),
                "coordinates_angstrom": [list(row) for row in identity.coordinates_angstrom], "role": "complex",
                "label": f"Calculated structure {item['request_id'][:8]}", "charge": item["charge"], "multiplicity": item["multiplicity"],
                "fragments": item["fragments"], "fragment_states": item["fragment_states"], "coordinate_unit": "angstrom",
                "origin": "verified_calculation_geometry", "source_result": {"path": item["source"], "sha256": item["source_sha256"]},
                "optimization_performed": item["optimization_performed"]}
            (directory / "input-manifest.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            self._student_uploads[key] = record
            self.student_geometry_choice.options = [(entry["label"], identifier) for identifier, entry in self._student_uploads.items()]
            self.student_geometry_choice.value = key
            self.module_artifact.value = str(path)
            self.state.active_view = "matrix"
        except (ValueError, OSError) as exc:
            self.actions_status.value = f"<p role='alert'>Calculated structure was not loaded: {html.escape(str(exc))}</p>"

    def _cancel_pipeline(self, b: Any = None) -> None:
        if self._hpc_running and self._hpc_submission is not None:
            self._cancel_student_hpc()
            return
        if self._actions_running and self._actions_submission is not None:
            self._cancel_student_actions()
            return
        if self._pipeline_running:
            self._pipeline_cancellation.set()
            self.btn_cancel.disabled = True
            self.btn_periodic_cancel.disabled = True
            self.state.system_status = "Cancelling calculation..."

    def _pipeline_thread(self, config_path: Path) -> None:
        from cochem_base.calc.calculation_service import run_calculation
        from cochem_base.core_engine.cochem_core_subprocess_broker import (
            SubprocessCancelledError,
        )

        def on_event(event: dict[str, Any]) -> None:
            if event.get("kind") == "log":
                self.telemetry_output.append_stdout(event["message"])
            elif event.get("status") == "RUNNING":
                self.state.system_status = "Running Pipeline..."

        try:
            work_dir = config_path.parent
            configuration = json.loads(config_path.read_text(encoding="utf-8"))
            if configuration.get('t9_fallback') is not None:
                from cochem_base.calc.t9_fallback import T9FallbackConfig
                from cochem_base.core_engine.execution_authority import authorize_engine_execution
                recovery = T9FallbackConfig.model_validate(configuration['t9_fallback'])
                self.telemetry_output.append_stdout('Verifying fresh PySCF recovery authority before starting the saved calculation.\n')
                authorize_engine_execution('pyscf', executable=recovery.python_executable,
                    cores=recovery.threads, maxcore_mb=math.ceil(recovery.memory_mb / recovery.threads))
            engine = configuration["engine"].upper()
            operation = ("optimization + harmonic frequencies" if configuration['is_opt'] and configuration['is_freq']
                         else "harmonic frequencies" if configuration['is_freq']
                         else "optimization" if configuration['is_opt'] else "single point")
            self.telemetry_output.append_stdout(f"Running the saved {engine} {operation} configuration.\nFull logs and results: {work_dir}\n")
            result = run_calculation(
                config_path, scratch=work_dir / "Scratch", output=work_dir / "Results", device="cpu",
                on_event=on_event,
                cancellation_event=self._pipeline_cancellation,
            )
            if result["status"] == "PENDING_INTEGRATION":
                self.state.system_status = "Pending Integration"
                self.state.error_message = ""
                self.calculation_result.value = (
                    "<p role='status'>Validated request prepared for integration. No scientific calculation was performed.</p>"
                    f"<p>Handoff: <code>{html.escape(str(result['handoff_manifest']))}</code></p>"
                )
                return
            if result["status"] != "EXECUTION_VERIFIED":
                raise RuntimeError(f"{engine} {operation} was not completed; diagnostics: {work_dir}.")
            self.state.system_status = ("Optimization Finished" if configuration['is_opt'] else
                                        "Harmonic Frequencies Finished" if configuration['is_freq'] else "Single Point Finished")
            self.state.error_message = ""
            self.telemetry_output.append_stdout(f"\n{engine} execution and scientific output checks passed. Results: {work_dir / 'Results'}\n")
            hessians = self._prepare_calculation_hessians(work_dir / "Results")
            self._ui_call(lambda: self._publish_calculation_hessians(hessians))
            if engine in {"XTB", "PYSCF"}:
                result_path = work_dir / "Results" / "result.json"
                payload = json.loads(result_path.read_text(encoding="utf-8"))
                self.calculation_result.value = (
                    f"<b>{'xTB screening result' if engine == 'XTB' else 'PySCF RHF single-point result'}</b> (no product accuracy certification)<br/>"
                    f"Method: {html.escape(payload['method'])}<br/>"
                    f"Energy: {float(payload['energy_hartree']):.12f} Hartree<br/>"
                    + (f"Optimization converged: {payload['optimization_converged'] is True}<br/>" if engine == "XTB" else f"SCF converged: {payload['scf_converged'] is True}<br/>Nuclear gradient: recorded in the result artifact.<br/>")
                    +
                    f"Artifact: <code>{html.escape(str(result_path))}</code>"
                )
            elif engine == "QE":
                # The service publishes one canonical result at this boundary;
                # engine-private evidence may also contain its own result file.
                result_path = work_dir / "Results" / "result.json"
                payload = json.loads(result_path.read_text(encoding="utf-8"))
                self.calculation_result.value = (
                    "<b>Quantum ESPRESSO periodic PBE/PAW result</b><br/>"
                    f"Energy: {float(payload['energy_hartree']):.12f} Hartree<br/>"
                    f"SCF converged: {payload['scf_converged'] is True}<br/>"
                    "Empirical product accuracy: unverified.<br/>"
                    f"Artifact: <code>{html.escape(str(result_path))}</code>"
                )
            elif engine == 'CFOUR':
                result_path = work_dir / 'Results' / 'result.json'
                payload = json.loads(result_path.read_text(encoding='utf-8'))
                self.calculation_result.value = (
                    f"<b>CFOUR {html.escape(operation)} result</b> (no product accuracy certification)<br/>"
                    f"Method: {html.escape(payload['method'])}<br/>"
                    f"Energy: {float(payload['energy_hartree']):.12f} Hartree<br/>"
                    f"Artifact: <code>{html.escape(str(result_path))}</code>"
                )
            else:
                self.calculation_result.value = f"<b>ORCA {html.escape(operation)} accepted.</b> Results: <code>{html.escape(str(work_dir / 'Results'))}</code>"
        except SubprocessCancelledError:
            self.state.system_status = "Calculation Cancelled"
            self.state.error_message = ""
            self.calculation_result.value = "<i>Calculation cancelled; no accepted result was reported.</i>"
            self.telemetry_output.append_stdout("\nCalculation cancelled; its owned processes were stopped.\n")
        except Exception as exc:
            self.state.system_status = "Calculation Error"
            self.state.error_message = str(exc)
            self.calculation_result.value = "<b>Calculation was not accepted.</b> See diagnostics below."
            self.telemetry_output.append_stdout(f"\nCalculation was not accepted: {exc}\n")
        finally:
            self._pipeline_running = False
            self.btn_cancel.disabled = True
            self.btn_periodic_cancel.disabled = True
            self.btn_periodic_run.disabled = False
            self._check_dispersion_gate()
            self._refresh_topos_capabilities()

    def display(self) -> widgets.VBox:
        styles = widgets.HTML("""<style>
        .cochem-accessible .jupyter-button {color: #17212b; background: #eef1f4;}
        .cochem-accessible .jupyter-button.mod-primary,
        .cochem-accessible .jupyter-button.mod-info {color: #fff; background: #005a9c;}
        .cochem-accessible .jupyter-button.mod-success {color: #fff; background: #216334;}
        .cochem-accessible .jupyter-button.mod-warning {color: #302400; background: #ffdb75;}
        .cochem-accessible .jupyter-button.mod-danger {color: #fff; background: #9b1c31;}
        .cochem-accessible button:focus-visible,
        .cochem-accessible input:focus-visible,
        .cochem-accessible select:focus-visible,
        .cochem-accessible textarea:focus-visible {outline: 3px solid #005a9c; outline-offset: 2px;}
        .cochem-accessible table {border-collapse: collapse;}
        .cochem-accessible th, .cochem-accessible td {padding: 6px; border: 1px solid #68737d;}
        .cochem-accessible pre {white-space: pre-wrap; overflow-wrap: anywhere;}
        </style>""")
        return widgets.VBox([styles, self.ai_container, self.app]).add_class("cochem-accessible")

def create_gui() -> widgets.VBox:
    """Entry point to instantiate and display the GUI."""
    gui = CoChemGUI()
    return gui.display()
