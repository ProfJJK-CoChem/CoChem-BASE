import atexit
import html
import json
import logging
import os
import re
import sys
import threading
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
        self.btn_modules = widgets.Button(description="Module handoff", layout=widgets.Layout(width='auto', margin='5px 0'))
        self.btn_periodic = widgets.Button(description="Periodic structures", layout=widgets.Layout(width='auto', margin='5px 0'))

        # Configuration and inspection work without provisioned quantum engines.
        # Execution performs its own dependency and scientific validation.

        self.btn_install.on_click(lambda b: setattr(self.state, 'active_view', 'install'))
        self.btn_matrix.on_click(lambda b: setattr(self.state, 'active_view', 'matrix'))
        self.btn_inspector.on_click(lambda b: setattr(self.state, 'active_view', 'inspector'))
        self.btn_modules.on_click(lambda b: setattr(self.state, 'active_view', 'modules'))
        self.btn_periodic.on_click(lambda b: setattr(self.state, 'active_view', 'periodic'))

        self.sidebar = widgets.VBox(
            [self.btn_install, self.btn_matrix, self.btn_inspector, self.btn_periodic, self.btn_modules],
            layout=widgets.Layout(
                width='250px',
                padding='10px',
                border='1px solid #ccc',
            )
        )

        # 3. Main Content Area (Views)

        # 3.1 Seamless Install View
        
        self.gh_repo_input = widgets.Text(
            description="Private project:", value=os.environ.get("GITHUB_REPOSITORY", ""),
            placeholder="your-account/private-project", style={'description_width': 'initial'},
            layout=widgets.Layout(width='90%'),
        )
        self.gh_branch_input = widgets.Text(
            description="Approved branch:", value=os.environ.get("GITHUB_REF_NAME", "main"),
            style={'description_width': 'initial'},
        )
        self.gh_guidance = widgets.HTML()
        self.gh_setup_box = widgets.VBox([
            self.gh_repo_input, self.gh_branch_input, self.gh_guidance,
        ], layout=widgets.Layout(border='1px solid #0056b3', padding='15px', margin='10px 0'))
        self.gh_repo_input.observe(self._refresh_actions_guidance, names='value')
        self.gh_branch_input.observe(self._refresh_actions_guidance, names='value')
        self.actions_job_download = widgets.HTML()
        self._last_actions_job = None
        self._actions_lifecycle_running = False
        self.actions_asset_descriptor = widgets.Text(
            description="Reviewed descriptor:", placeholder="Path to approved ORCA/CFOUR distribution JSON",
            style={'description_width': 'initial'}, layout=widgets.Layout(width='90%'),
        )
        self.actions_asset_descriptor_sha256 = widgets.Text(
            description="Reviewed file SHA-256:", placeholder="Independently retained descriptor file SHA-256",
            style={'description_width': 'initial'}, layout=widgets.Layout(width='90%'),
        )
        self.actions_cores = widgets.Dropdown(options=[1, 2], value=1, description="Actions cores:")
        self.actions_memory = widgets.BoundedIntText(
            value=512, min=1, max=1024, description="MB per core:",
            style={'description_width': 'initial'},
        )
        self.actions_task_id = widgets.Text(
            description="Retained task:", placeholder="Actual task UUID returned after staging",
            style={'description_width': 'initial'},
        )
        self.actions_stage_submit = widgets.Button(description="Stage privately and submit", button_style="primary")
        self.actions_refresh = widgets.Button(description="Refresh owned run")
        self.actions_cancel = widgets.Button(description="Cancel owned run")
        self.actions_download = widgets.Button(description="Download owned results")
        self.actions_cleanup = widgets.Button(description="Clean completed staged assets")
        self.actions_repair = widgets.Button(description="Review staged-asset repair")
        self.actions_run_id = widgets.Text(description="Actual run ID:", value="")
        self.actions_select_run = widgets.Button(description="Select observed owned run")
        self.actions_lifecycle_status = widgets.HTML("<p>No private Actions task has been submitted.</p>")
        self.actions_stage_submit.on_click(lambda _: self._run_private_actions("submit"))
        self.actions_refresh.on_click(lambda _: self._run_private_actions("status"))
        self.actions_cancel.on_click(lambda _: self._run_private_actions("cancel"))
        self.actions_download.on_click(lambda _: self._run_private_actions("download"))
        self.actions_cleanup.on_click(lambda _: self._run_private_actions("cleanup"))
        self.actions_repair.on_click(lambda _: self._run_private_actions("repair"))
        self.actions_select_run.on_click(lambda _: self._run_private_actions("select"))
        self.actions_private_panel = widgets.VBox([
            widgets.HTML(
                "<h4>Private personal project Actions</h4>"
                "<p>Codespaces supplies the interface. Your personal private repository runs the calculation "
                "and uses your Actions quota. Staging temporarily copies approved licensed assets into that "
                "private project; the lab credential is never copied into the project or Actions.</p>"
                "<p>Use your existing authorized GitHub identity with access to the lab's private release "
                "and your own project. Codespaces additional repository permissions do not grant access "
                "across different owners. If access is unavailable, staging stays blocked; complete your "
                "own browser authentication and approved laboratory access first.</p>"
            ),
            self.actions_asset_descriptor, self.actions_asset_descriptor_sha256,
            widgets.HBox([self.actions_cores, self.actions_memory]),
            self.actions_stage_submit, self.actions_task_id,
            widgets.HBox([self.actions_refresh, self.actions_cancel, self.actions_download]),
            widgets.HBox([self.actions_run_id, self.actions_select_run]),
            widgets.HBox([self.actions_cleanup, self.actions_repair]), self.actions_lifecycle_status,
        ])
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
        self.actions_job_options = widgets.VBox([
            self.actions_operation, self.actions_timeout,
            widgets.HTML("<p>Course profile: ORCA or CFOUR, up to 50 atoms, one or two cores, "
                         "512 MB per core by default (maximum 1024 MB), and at most 1800 seconds per calculation. "
                         "Choose cores and memory on GitHub when starting the workflow.</p>"
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
            value='macos' if sys.platform == 'darwin' else 'local' if os.name == 'nt' else 'linux',
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
            icon="play", disabled=True,
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
        self.install_data_status = widgets.HTML("<p>[MISSING DATA] Validate a scientific .h5 or .npz bundle before initialization.</p>")
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
            self.run_install_btn.disabled = self._installation_running or (env != "github-actions" and self._install_input_artifact is None)
            if hasattr(self, 'local_install_options'):
                self.local_install_options.layout.display = 'none' if env == 'github-actions' else ''
            if hasattr(self, 'btn_execute'):
                self._check_dispersion_gate()
                self._refresh_topos_capabilities()
                
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
        self.cfour_operation.observe(update_preview, 'value')
        self.actions_timeout.observe(update_preview, 'value')
        self.calc_env_dropdown.observe(update_preview, 'value')
        self.cb_recipe_r1.observe(self._check_dispersion_gate, 'value')
        self.cb_recipe_r2.observe(self._check_dispersion_gate, 'value')
        self.cb_recipe_r1.observe(update_preview, 'value')
        self.cb_recipe_r2.observe(update_preview, 'value')
        self.r2_reference_manifest.observe(update_preview, 'value')
        self.t9_config_path.observe(update_preview, 'value')
        self.charge_input.observe(update_preview, 'value')
        self.multiplicity_input.observe(update_preview, 'value')
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
            self.t9_config_path,
            widgets.HTML("<p>T9 recovery requires a scientifically selected active space. Supply its validated JSON configuration; no active space is guessed.</p>"),
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
            self.r2_reference_manifest,
            widgets.HTML("<b>Generated Frozen Monomer Directives:</b>"),
            self.fragment_preview
        ])

        
        

        
        self.smiles_input = widgets.Text(description="SMILES:", placeholder="e.g. CCO")
        self.btn_build_smiles = widgets.Button(description="Build from SMILES", button_style="info")
        self.xyz_upload = widgets.FileUpload(accept='.xyz', multiple=False, description="Upload .xyz")
        
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
                    view = py3Dmol.view(width=400, height=300)
                    view.addModel(xyz_data, 'xyz')
                    view.setStyle({'stick': {}, 'sphere': {'radius': 0.4}})
                    view.zoomTo()
                    display(view)
                except ImportError:
                    print("py3Dmol is not installed. Run pip install py3Dmol to view 3D models.")
                except Exception as e:
                    print(f"Viewer Error: {e}")

        def _on_smiles_build(b):
            smiles = self.smiles_input.value.strip()
            if not smiles: return
            try:
                from rdkit import Chem
                from rdkit.Chem import AllChem
                mol = Chem.MolFromSmiles(smiles)
                if mol is None:
                    self.matrix_geometry.value = "Error: Invalid SMILES"
                    return
                mol = Chem.AddHs(mol)
                AllChem.EmbedMolecule(mol, AllChem.ETKDG())
                AllChem.UFFOptimizeMolecule(mol)
                from cochem_base.geometry.nuclide_geometry import rdkit_geometry_xyz
                self.matrix_geometry.value = rdkit_geometry_xyz(mol)
                self.project_name.value = smiles.replace('/', '_').replace('\\', '_')
                _update_3d_viewer()
            except ImportError:
                self.matrix_geometry.value = "Error: RDKit is not installed. Run conda install -c conda-forge rdkit"
            except Exception as e:
                self.matrix_geometry.value = f"SMILES Build Error: {e}"
                
        def _on_xyz_upload(change):
            if self.xyz_upload.value:
                file_name = list(self.xyz_upload.value.keys())[0]
                self.project_name.value = file_name.replace('.xyz', '')
                file_info = list(self.xyz_upload.value.values())[0]
                content = file_info['content'].decode('utf-8')
                self.matrix_geometry.value = content
                _update_3d_viewer()

        self.btn_build_smiles.on_click(_on_smiles_build)
        self.xyz_upload.observe(_on_xyz_upload, names='value')
        
        # Add an observe to matrix_geometry so manual typing updates the 3D model
        self.matrix_geometry.observe(lambda c: _update_3d_viewer(), names='value')
        
        self.tab_builder = widgets.HBox([
            widgets.VBox([
                widgets.HTML("<b>Molecule Builder & Import</b><br/><i>Generate 3D geometries from SMILES or import existing .xyz files.</i>"),
                widgets.HBox([self.smiles_input, self.btn_build_smiles]),
                self.xyz_upload,
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
        self.matrix_config_panel = widgets.VBox([
            widgets.HTML("<h4>Simulation Parameters</h4>"),
            self.calculation_environment_status,
            self.actions_job_options,
            self.config_tabs,
            self.output_destination_guidance,
            self.output_config_box,
            widgets.HTML("<h4>Saved Run Configuration Preview</h4>"),
            self.live_preview,
            self.btn_save_matrix,
            self.matrix_output,
            self.actions_job_download,
            self.actions_private_panel,
        ], layout=widgets.Layout(border='1px solid #ccc', padding='10px', margin='10px 0'))

        # Task 3: Connected HPC / Slurm Panel
        self.partition_input = widgets.Text(description="Partition:", value="standard")
        self.nodes_input = widgets.IntText(description="Nodes:", value=1)
        self.tasks_per_node_input = widgets.IntText(description="Tasks/Node:", value=16)
        self.mem_input = widgets.Text(description="Memory:", value="32GB")
        self.walltime_input = widgets.Text(description="Walltime:", value="04:00:00")
        self.job_name_input = widgets.Text(description="Job Name:", value="cochem_job")
        self.email_input = widgets.Text(description="Email:", value="")
        self.btn_slurm_submit = widgets.Button(description="Submit Job", button_style="primary", icon="cloud-upload")
        self.slurm_submit_btn = self.btn_slurm_submit
        self.btn_slurm_submit.on_click(self._on_slurm_submit)
        self.slurm_status_output = widgets.HTML("<b>Slurm Status:</b> Ready for dispatch [M].")

        self.slurm_panel = widgets.VBox([
            widgets.HTML("<h4>HPC/SLURM Submission Panel</h4>"),
            widgets.HTML("<p>Configure HPC scheduler parameters for distributed execution.</p>"),
            widgets.HBox([self.partition_input, self.job_name_input]),
            widgets.HBox([self.nodes_input, self.tasks_per_node_input]),
            widgets.HBox([self.mem_input, self.walltime_input]),
            self.email_input,
            self.btn_slurm_submit,
            self.slurm_status_output
        ], layout=widgets.Layout(border='1px solid #ccc', padding='10px', margin='10px 0'))

        # Hide SLURM panel if not HPC
        if not is_hpc:
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

        self.telemetry_panel = widgets.VBox([
            widgets.HTML("<h4>Live Telemetry & Execution</h4>"),
            self.execution_description,
            widgets.HBox([self.btn_execute, self.btn_cancel]),
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
        self.btn_read_hdf5 = widgets.Button(description="Read HDF5 (SWMR)", button_style="warning", icon="database")
        self.btn_read_hdf5.on_click(self._on_read_hdf5_clicked)
        self.hdf5_results_table = widgets.HTML("<i>Select an .h5 file to preview up to 100 datasets and 500 values per dataset using SWMR and the shared file lock.</i>")

        self.inspector_tabs = widgets.Tab(children=[
            widgets.VBox([self.inspector_banner, self.inspector_rot_table]),
            widgets.VBox([
                widgets.HTML("<b>Isotopic Substitution (Mendeleev masses)</b>"),
                self.isotope_hessian_path,
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

        from cochem_base.interfaces.module_registry import list_module_capabilities
        from cochem_base.config_loader import get_artifact_dir
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
        pending = [self.app, self.view_matrix, self.view_inspector, self.view_modules, self.view_periodic]
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

    def _invalidate_actions_job(self, change: Any = None) -> None:
        self._last_actions_job = None
        if hasattr(self, 'actions_job_download'):
            self.actions_job_download.value = ""

    def _actions_repository(self) -> str:
        repository = self.gh_repo_input.value.strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9._-]*", repository):
            raise ValueError("Enter your own private personal project as OWNER/REPOSITORY.")
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
            (("ORCA (course Actions workflow)", "ORCA"),
             ("CFOUR (course Actions workflow)", "CFOUR"),
             ("xTB (local/HPC only)", "XTB"),
             ("PySCF (local/HPC only)", "PYSCF"))
            if remote else self._local_engine_options
        )
        values = {value for _, value in options}
        self.matrix_engine.options = options
        self.matrix_engine.value = selected if selected in values else ('ORCA' if remote else None)
        if remote:
            self.licensed_engine_status.value = (
                "<p>ORCA and CFOUR are optional and strongly recommended. Remote licensed-engine availability is unverified in this interface. "
                "An ORCA or CFOUR choice prepares a request only; the course workflow checks its own download, installation and execution authority. "
                "Local engine availability does not establish GitHub Actions availability.</p>"
            )
        if hasattr(self, 'btn_execute'):
            self._refresh_execution_gate()

    def _refresh_actions_guidance(self, change: Any = None) -> None:
        repository = self.gh_repo_input.value.strip()
        valid_repository = bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9._-]*", repository))
        guide_repository = repository if valid_repository else "ProfJJK-CoChem/CoChem-BASE"
        branch = self.gh_branch_input.value.strip() or "main"
        guide = f"https://github.com/{guide_repository}/blob/{quote(branch, safe='')}/.docs/GitHub_Classroom_ORCA_Setup.md"
        cfour_guide = f"https://github.com/{guide_repository}/blob/{quote(branch, safe='')}/.docs/CFOUR_Actions_Setup.md"
        self.gh_guidance.value = (
            "<h4>GitHub Actions: private personal student project</h4>"
            "<p>Use your own private personal project with the reviewed ORCA/CFOUR workflows. "
            "Codespaces stages approved assets using your own authorized identity. "
            "Students do not enter tokens or binary download links in this interface.</p>"
            "<ol><li>Enter your private personal project and reviewed branch.</li>"
            "<li>Ask the instructor to confirm calculation acceptance passed for your selected licensed engine in this repository.</li>"
            "<li>Open <b>No Code Matrix</b>, choose ORCA or CFOUR, enter your molecule and method, then choose "
            "<b>Prepare GitHub Actions job</b>.</li>"
            "<li>Use <b>Stage privately and submit</b> with your independently reviewed distribution descriptor. "
            "The interface uploads the validated job, stages its approved private asset, and dispatches the owning project workflow.</li>"
            "<li>Wait for the calculation to finish. Download its result artifact and retain the run URL. "
            "A prepared file or an archive-access check is not a completed calculation.</li></ol>"
            f"<p><a href='{guide}#student-quick-start' target='_blank' rel='noopener'>Student quick start</a> · "
            f"<a href='{guide}#instructor-setup' target='_blank' rel='noopener'>Instructor setup</a> · "
            f"<a href='{guide}#troubleshooting' target='_blank' rel='noopener'>Troubleshooting</a></p>"
            f"<p><a href='{cfour_guide}' target='_blank' rel='noopener'>CFOUR setup and calculation instructions</a></p>"
        )
        remote = hasattr(self, 'calc_env_dropdown') and self.calc_env_dropdown.value == "github-actions"
        if hasattr(self, 'matrix_engine'):
            self._refresh_engine_choices()
            self.matrix_engine.tooltip = (
                "Prepare an ORCA or CFOUR request without a local engine. The approved workflow provisions and authorizes its own engine."
                if remote else "Native execution requires the complete eleven-phase setup audit on the configured host."
            )
        self.actions_job_options.layout.display = '' if remote else 'none'
        self.actions_private_panel.layout.display = '' if remote else 'none'
        if hasattr(self, 'artifact_output_path'):
            self.artifact_output_path.layout.display = 'none' if remote else ''
        if hasattr(self, 'output_destination_guidance'):
            self.output_destination_guidance.value = (
                "<h4>Actions job download</h4><p>The project name determines the downloaded JSON filename. "
                "Upload that file to the course repository's <code>jobs/</code> directory.</p>"
                if remote else "<h4>Artifact Output Configuration</h4><p>Saved configurations use &lt;Output Dir&gt;/&lt;Project Name&gt;/. "
                "Each calculation writes logs and results below &lt;Output Dir&gt;/GUI/run_…/.</p>"
            )
        if hasattr(self, 'execution_description'):
            self.execution_description.value = (
                "<p>Prepare the selected ORCA or CFOUR operation for its course Actions workflow. "
                "Its calculation logs and validated results are available in the GitHub run artifact after execution.</p>"
                if remote else "<p>Run ORCA, supported closed-shell CFOUR calculations, xTB optimization, or a PySCF RHF single point on the configured host. "
                "Screening carries no product accuracy certification. TOPOS and TORQ use their separate runners.</p>"
            )
        self.calculation_environment_status.value = (
            "<p><b>Calculation target: GitHub Actions.</b> This interface prepares a job file; "
            "the approved workflow runs the calculation after you submit it on GitHub. "
            f"<a href='{guide}#student-quick-start' target='_blank' rel='noopener'>Course instructions</a></p>"
            if remote else "<p>Calculation target: the configured local or HPC execution host.</p>"
        )
        self._invalidate_actions_job()
        if hasattr(self, 'btn_execute'):
            self._refresh_execution_gate()

    def _detect_environment(self) -> Tuple[bool, str, bool, bool]:
        """Display measured, signed registry state; individual phase files are insufficient."""
        from cochem_base.core.cochem_core_registry_manager import (
            load_system_config, RegistryError,
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
                             ("inspector", self.btn_inspector), ("modules", self.btn_modules), ("periodic", self.btn_periodic)):
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

    def _inspect_periodic_input(self, b: Any = None) -> None:
        from cochem_base.calc.periodic import ingest_periodic_structure
        try:
            structure = ingest_periodic_structure(self.periodic_input_path.value)
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

    def _prepare_periodic_config(self) -> Path:
        from cochem_base.calc.periodic import ingest_periodic_structure
        from cochem.core.context import assert_writable_path
        import uuid

        structure = ingest_periodic_structure(self.periodic_input_path.value)
        settings = json.loads(Path(self.periodic_settings_path.value).expanduser().read_text(encoding="utf-8"))
        if not isinstance(settings, dict):
            raise ValueError("PAW calculation settings must be a JSON object")
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
        if self.calc_env_dropdown.value == "github-actions":
            self.state.error_message = "The course Actions workflow accepts molecular ORCA jobs. Choose a configured local/HPC host for periodic QE execution."
            return
        if self._pipeline_running or self._topos_running or self._installation_running:
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
        from cochem_base.interfaces.module_registry import list_module_capabilities
        from cochem_base.interfaces.module_execution import installed_module_status
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
        from scripts.manage_modules import DEFAULT_MANIFEST, load_manifest, install_module
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
        from cochem_base.interfaces.artifact_handoff import prepare_module_handoff
        from cochem_base.interfaces.module_execution import execute_module_handoff
        import uuid
        name = self.module_recipient.value
        artifact = self.module_artifact.value
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
        from cochem_base.interfaces.artifact_handoff import prepare_module_handoff, load_module_handoff
        import base64
        import io
        import uuid
        import zipfile

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
        self.run_install_btn.disabled = self.calc_env_dropdown.value != "github-actions"
        self.install_data_status.value = "<p>[MISSING DATA] Validate the selected scientific bundle.</p>"

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
            self.run_install_btn.disabled = True
            self.install_data_status.value = f"<p role='alert'>Scientific input was not accepted: {html.escape(str(exc))}</p>"
            return False

    def _run_installation(self, b: Any) -> None:
        if self.calc_env_dropdown.value == "github-actions":
            self._refresh_actions_guidance()
            self.state.system_status = "Actions setup instructions"
            self.state.error_message = ""
            return
        if self._installation_running or not self._validate_installation_data():
            return
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
        from cochem_base.orchestrator.bootstrap_service import run_setup
        from cochem_base.core.cochem_core_registry_manager import atomic_write_json
        from cochem_base.config_loader import get_artifact_dir

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
            if artifact is None:
                raise ValueError("Validated scientific input is required")
            atomic_write_json(artifact_dir / "Registry" / "gui_setup_request.json", {
                "license_mode": request['license_mode'],
                "calculation_environment": request['calculation_environment'],
                "interaction_environment": request['interaction_environment'],
                "scientific_input": str(artifact.path), "input_sha256": artifact.sha256,
                "input_source": artifact.source, "required_disk_gb": request['required_disk_gb'],
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
            self.run_install_btn.disabled = self._install_input_artifact is None

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
            from cochem_base.calc.calculation_service import parse_run_geometry
            from cochem_base.physics.isotopes import get_element_mass_and_abundance
            import numpy as np

            symbols, coordinates = parse_run_geometry(self.matrix_geometry.value)
            if not symbols:
                raise MethodologyViolationError("Enter valid XYZ geometry before execution.")
            numbers = [get_element_mass_and_abundance(symbol)[2] for symbol in symbols]
            fragments = detect_molecular_fragments(numbers, np.asarray(coordinates))
            validate_method_matrix_compliance(
                self.matrix_method.value, num_fragments=len(fragments),
                unphysical_override=self.unphysical_override.value,
            )
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
            self.btn_execute.description = "Prepare GitHub Actions job"
            if self.matrix_engine.value not in {"ORCA", "CFOUR"}:
                reason = "The course Actions workflows accept ORCA or CFOUR jobs. Choose either engine or return to the configured local/HPC host."
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
                        self.cb_recipe_r2, self.r2_reference_manifest, self.t9_config_path):
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
        actions_operations = (cfour_operations if selected == 'CFOUR' else
                              [('Single point', 'single_point'), ('Optimization', 'optimization'),
                               ('Harmonic frequencies', 'harmonic_frequencies'),
                               ('Optimize + harmonic frequencies', 'optimization_frequencies')])
        if tuple(self.actions_operation.options) != tuple(actions_operations):
            previous = self.actions_operation.value
            self.actions_operation.options = actions_operations
            self.actions_operation.value = previous if previous in {value for _, value in actions_operations} else 'single_point'
        self.product_class_selector.disabled = selected in {'XTB', 'PYSCF', 'CFOUR'}
        self.engine_warning.value = f"<b>{html.escape(reason)}</b>" if reason else ""
        self.btn_execute.disabled = bool(reason or self.dispersion_warning.value or self._pipeline_running
                                         or self._topos_running or self._installation_running)

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
        import uuid

        if self.calc_env_dropdown.value == "github-actions":
            self.slurm_status_output.value = "<p role='alert'>GitHub Actions is selected. Prepare the course job JSON and submit it through ORCA calculation on GitHub.</p>"
            return
        try:
            controller = SlurmSubmissionController()
            destination = self._run_artifact_root() / "SlurmStaging" / ("job_" + uuid.uuid4().hex)
            script_path = controller.stage_calculation(
                self._collect_run_config(), destination,
                job_name=self.job_name_input.value,
                partition=self.partition_input.value,
                nodes=self.nodes_input.value,
                ntasks_per_node=self.tasks_per_node_input.value,
                mem=self.mem_input.value,
                walltime=self.walltime_input.value,
                email=self.email_input.value if self.email_input.value.strip() else None,
            )
            status = controller.dispatch(script_path)
            message = (f"Submitted Slurm job {status}; scientific results remain pending."
                       if status.isdigit() else status)
            self.slurm_status_output.value = f"<p role='status'>{html.escape(message)}</p>"
        except Exception as err:
            self.slurm_status_output.value = f"<p role='alert'>Slurm job was not submitted: {html.escape(str(err))}</p>"

    def _on_parse_inspector_clicked(self, b: Any) -> None:
        file_path_str = self.inspector_file_input.value.strip()
        if not file_path_str:
            self.inspector_rot_table.value = "<b style='color:red;'>Please enter a file path.</b>"
            return
        fpath = Path(file_path_str)
        if not fpath.exists():
            self.inspector_rot_table.value = f"<b style='color:red;'>File not found: {html.escape(str(fpath))}</b>"
            return
        try:
            parser = SpectroscopyTelemetryParser()
            res = parser.parse_file(fpath)
            html_table = (
                "<table border='1' cellpadding='5' style='border-collapse:collapse; width:100%;'>"
                "<thead><tr style='background:#f2f2f2;'>"
                "<th>Observable</th><th>Equilibrium Value ($B_e$) [MHz]</th>"
                "<th>Vib Correction ($\\Delta B_{\\text{vib}}$) [MHz]</th>"
                "<th>Ground State ($B_0$) [MHz]</th><th>Provenance</th></tr></thead><tbody>"
                f"<tr><td><b>A</b></td><td>{_observable(res.a_e)}</td><td>{_observable(res.delta_a_vib)}</td><td>{_observable(res.a_0)}</td><td>[M, D]</td></tr>"
                f"<tr><td><b>B</b></td><td>{_observable(res.b_e)}</td><td>{_observable(res.delta_b_vib)}</td><td>{_observable(res.b_0)}</td><td>[M, D]</td></tr>"
                f"<tr><td><b>C</b></td><td>{_observable(res.c_e)}</td><td>{_observable(res.delta_c_vib)}</td><td>{_observable(res.c_0)}</td><td>[M, D]</td></tr>"
                f"<tr><td><b>Inertial Defect ($\\Delta$)</b></td><td colspan='3'>{res.inertial_defect:.6f} amu·Å²</td><td>[D]</td></tr>"
                f"<tr><td><b>Dipole Magnitude (|$\\mu$|)</b></td><td colspan='3'>{_observable(res.total_dipole, 4)} Debye</td><td>[M]</td></tr>"
                "</tbody></table>"
            )
            self.inspector_rot_table.value = html_table
        except Exception as exc:
            self.inspector_rot_table.value = f"<b style='color:red;'>Parse Error: {html.escape(str(exc))}</b>"

    def _update_isotope_selectors(self, change: Any = None) -> None:
        from cochem_base.physics.isotopes import parse_nuclide_token
        from cochem_base.physics.nuclide_resolver import get_element
        from cochem_base.calc.calculation_service import parse_run_geometry_identity

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

    def _on_clear_hessian_clicked(self, b: Any) -> None:
        self._isotope_hessian_data = None
        self.isotope_modes_plot.value = ""
        self.isotope_hessian_status.value = "<p>[MISSING DATA] No Cartesian Hessian loaded.</p>"

    def _on_load_hessian_clicked(self, b: Any) -> None:
        from cochem_base.spectroscopy.artifacts import load_hessian_artifact

        self._isotope_hessian_data = None
        try:
            artifact = load_hessian_artifact(self.isotope_hessian_path.value.strip())
            self.matrix_geometry.value = "\n".join(
                f"{symbol} {row[0]:.15g} {row[1]:.15g} {row[2]:.15g}"
                for symbol, row in zip(artifact.symbols, artifact.coordinates_angstrom)
            )
            self._isotope_hessian_data = artifact
            self.isotope_hessian_status.value = (
                "<p role='status'>Geometry and Cartesian Hessian loaded. Units: Hartree/bohr².<br/>"
                f"Source: {html.escape(artifact.source)}<br/>SHA-256: <code>{artifact.sha256}</code></p>"
            )
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            self.isotope_hessian_status.value = f"<p role='alert'>Hessian was not loaded: {html.escape(str(exc))}</p>"

    def _on_run_isotope_reanalysis_clicked(self, b: Any) -> None:
        self.isotope_modes_plot.value = ""
        geom_str = self.matrix_geometry.value.strip()
        if not geom_str:
            self.isotope_results_table.value = "<b style='color:red;'>Please provide molecular geometry in Base Config tab first.</b>"
            return
        try:
            from cochem_base.calc.calculation_service import parse_run_geometry_identity
            identity = parse_run_geometry_identity(geom_str)
            symbols, coords = list(identity.nuclides), identity.coordinates_angstrom
            if not symbols or len(symbols) == 0:
                self.isotope_results_table.value = "<b style='color:red;'>Failed to parse symbols and coordinates from geometry.</b>"
                return

            artifact = self._isotope_hessian_data
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
            )
            parent_res = engine.compute_observables()

            html_rows = [
                "<table border='1' cellpadding='5' style='border-collapse:collapse; width:100%;'>",
                "<thead><tr style='background:#f2f2f2;'>",
                "<th>Isotopologue</th><th>Total Mass (amu) [M]</th><th>A_e (MHz) [M]</th><th>B_e (MHz) [M]</th><th>C_e (MHz) [M]</th>",
                "<th>B_0 (MHz) [D]</th><th>Inertial Defect (amu·Å²) [D]</th><th>Walltime (ms)</th></tr></thead><tbody>",
                f"<tr><td><b>Parent ({''.join(parent_res.symbols)})</b></td><td>{parent_res.total_mass_amu:.4f}</td>"
                f"<td>{parent_res.A_e_MHz:.2f}</td><td>{parent_res.B_e_MHz:.2f}</td><td>{parent_res.C_e_MHz:.2f}</td>"
                f"<td>{_observable(parent_res.B_0_MHz, 2)}</td><td>{parent_res.inertial_defect_amu_A2:.4f}</td><td>{parent_res.execution_walltime_ms:.2f}</td></tr>",
            ]

            if len(self.isotope_selectors) != len(symbols):
                raise ValueError("Isotope selections must match every atom in the geometry")
            sub_dict = {index: selector.value for index, selector in enumerate(self.isotope_selectors)
                        if selector.value != symbols[index]}
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
                html_rows.append("<h4>Projected harmonic modes</h4><p>Signed frequencies in cm⁻¹; negative values indicate imaginary modes. No electronic recalculation.</p>")
                html_rows.append("<table><caption>Mass-weighted Cartesian Hessian frequencies</caption><thead><tr><th scope='col'>Mode</th><th scope='col'>Parent (cm⁻¹)</th><th scope='col'>Substituted (cm⁻¹)</th></tr></thead><tbody>")
                for index, frequency in enumerate(parent_res.harmonic_frequencies_cm1):
                    replacement = iso_res.harmonic_frequencies_cm1[index] if iso_res is not None else None
                    html_rows.append(f"<tr><th scope='row'>{index + 1}</th><td>{frequency:.4f}</td><td>{_observable(replacement, 4)}</td></tr>")
                html_rows.append(f"</tbody></table><p>Rigid modes removed: {parent_res.rigid_mode_count}. Source: {html.escape(artifact.source)}. SHA-256: <code>{artifact.sha256}</code></p>")
                self.isotope_modes_plot.value = self._render_harmonic_plot(parent_res, iso_res, artifact)
            evidence_note = (
                "The supplied Hessian provides harmonic modes. Anharmonic vibrational corrections were not supplied; B0 is [MISSING DATA]. "
                if artifact is not None else
                "No Hessian or vibrational correction was supplied; B0 is [MISSING DATA]. "
            )
            self.isotope_results_table.value = (
                "<div style='margin-bottom:8px; background-color:#d4edda; color:#155724; padding:8px; border-radius:4px;'>"
                "<b>Dynamic Mendeleev Isotopologue Re-analysis:</b><br/>"
                "Rigid-rotor constants use the supplied geometry; equilibrium status is not inferred. " + evidence_note +
                "Per-calculation walltimes are measured in the table."
                "</div>" + "\n".join(html_rows)
            )
        except Exception as exc:
            self.isotope_results_table.value = f"<b style='color:red;'>Isotopic re-analysis failed: {html.escape(str(exc))}</b>"

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
        axis.set_ylabel("Harmonic frequency (cm⁻¹)", fontfamily="serif")
        axis.tick_params(labelsize=9, direction="in")
        axis.legend(frameon=False, fontsize=9)
        axis.grid(alpha=0.2)
        rendered = io.StringIO()
        figure.savefig(rendered, format="svg", metadata={"Description": artifact.source + "; SHA-256 " + artifact.sha256})
        svg = rendered.getvalue()
        csv_data = io.StringIO()
        writer = csv.writer(csv_data)
        writer.writerow(["mode", "parent_cm-1", "substituted_cm-1", "source", "sha256"])
        for index, frequency in enumerate(frequencies):
            writer.writerow([index + 1, frequency,
                             substituted.harmonic_frequencies_cm1[index] if substituted else "",
                             artifact.source, artifact.sha256])
        svg_uri = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        csv_uri = base64.b64encode(csv_data.getvalue().encode("utf-8")).decode("ascii")
        return (
            "<figure><figcaption>Harmonic mode comparison; signed frequencies from the loaded Cartesian Hessian. "
            "Modes are ordered by frequency; matching indices do not imply identical mode character.</figcaption>"
            f"<img alt='Parent and substituted harmonic frequencies; numerical values are in the preceding table.' src='data:image/svg+xml;base64,{svg_uri}'/>"
            f"<p><a download='harmonic-modes.svg' href='data:image/svg+xml;base64,{svg_uri}'>Download SVG figure</a> | "
            f"<a download='harmonic-modes.csv' href='data:text/csv;base64,{csv_uri}'>Download frequency data (CSV)</a></p></figure>"
        )

    def _on_read_hdf5_clicked(self, b: Any) -> None:
        fpath_str = self.inspector_file_input.value.strip()
        fpath = Path(fpath_str)
        if not fpath.exists():
            self.hdf5_results_table.value = f"<b style='color:red;'>HDF5 file not found: {html.escape(str(fpath))}</b>"
            return
        try:
            from cochem_base.spectroscopy.parser import read_hdf5_dataset_previews
            previews = read_hdf5_dataset_previews(fpath)
            rows = []
            for preview in previews:
                rows.append("<tr>" + "".join(
                    f"<td><pre>{html.escape(str(value))}</pre></td>" for value in (
                        preview["name"], preview["shape"], preview["units"], preview["source"],
                        f"{preview['shown']} / {preview['total']}", preview["values"],
                    )
                ) + "</tr>")
            self.hdf5_results_table.value = (
                f"<b>SWMR Read Success:</b> Previewed {len(previews)} datasets using the shared file lock. "
                "Values are a bounded prefix of each dataset.<br/>"
                "<table><caption>Stored scientific values</caption><thead><tr>"
                + "".join(f"<th scope='col'>{label}</th>" for label in ("Dataset", "Shape", "Units", "Source", "Shown / total", "Values"))
                + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
            )
        except Exception as exc:
            self.hdf5_results_table.value = f"<b style='color:red;'>SWMR Read Error: {html.escape(str(exc))}</b>"

    def _refresh_topos_capabilities(self, b: Any = None) -> None:
        from cochem_base.core_engine.execution_authority import authorize_engine_execution

        if self._topos_running:
            return
        if self.calc_env_dropdown.value == "github-actions":
            self.btn_topos_submit.disabled = True
            self.topos_capabilities.value = "<p>Conformer search is not submitted by the molecular ORCA course workflow. Choose a configured local/HPC host to use this panel.</p>"
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
        from cochem_base.calc.calculation_service import parse_run_geometry_identity
        from cochem_base.physics.nuclide_resolver import get_element
        from cochem_base.topos_runner import TOPOSExecutionBroker, TOPOSSearchConfig
        import uuid

        if self._topos_running:
            return
        if self.calc_env_dropdown.value == "github-actions":
            self.topos_status.value = "<p role='alert'>No conformer calculation was started. The selected Actions route uses the exported molecular ORCA job and its approved workflow.</p>"
            return
        try:
            if self._pipeline_running or self._installation_running:
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
                    f"Candidates found: {data['candidates_found']}; unique conformers: {data['deduplicated_count']}.<br/>"
                    f"Lowest energy: {_observable(data['lowest_energy_hartree'], 12)} Hartree.<br/>"
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
        remote = self.calc_env_dropdown.value == "github-actions"
        if remote and (self.cb_recipe_r2.value or self.t9_config_path.value.strip()):
            raise MethodologyViolationError("The course Actions job must be self-contained; R2 reference files and T9 checkpoints require a separate approved workflow.")
        self._check_dispersion_gate()
        if self.dispersion_warning.value:
            raise MethodologyViolationError("Resolve the methodology validation message before running or saving.")
        elements, coordinates = parse_run_geometry(self.matrix_geometry.value)
        fragments = detect_molecular_fragments(elements, coordinates)
        fallback = None
        if self.t9_config_path.value.strip():
            fallback = T9FallbackConfig.model_validate_json(Path(self.t9_config_path.value).expanduser().read_text(encoding='utf-8'))
        references = None
        if self.cb_recipe_r2.value:
            if not self.r2_reference_manifest.value.strip():
                raise MethodologyViolationError("Recipe R2 requires its reference-monomer manifest")
            references = Path(self.r2_reference_manifest.value).expanduser().resolve(strict=True)
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
            grid_stage=3 if (self.product_class_selector.value == ProductClass.PRODUCT_C.value
                             or self.cb_recipe_r2.value
                             or remote and self.actions_operation.value in {"harmonic_frequencies", "optimization_frequencies"}) else 2,
            **({"is_opt": self.actions_operation.value in {"optimization", "optimization_frequencies"},
                "is_freq": self.actions_operation.value in {"harmonic_frequencies", "optimization_frequencies"},
                "is_vpt2": False, "timeout_seconds": float(self.actions_timeout.value)} if remote else {}),
        )
        return config.model_dump(mode="json")

    def _cfour_run_config(self) -> dict[str, Any]:
        """Use the native CFOUR operation validator for the selected request."""
        from cochem_base.interfaces.scientific_jobs import calculation_capability, validate_job_configuration

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
            raise ValueError("Prepare the Actions job JSON and submit it through the course workflow.")
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
        if self.calc_env_dropdown.value == "github-actions":
            self._prepare_actions_job()
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

    def _prepare_actions_job(self) -> None:
        """Export a validated portable request; submission happens in GitHub."""
        import base64
        import hashlib
        from cochem_base.calc.calculation_service import CalculationMatrixConfig, parse_run_geometry
        from cochem_base.interfaces.actions_jobs import validate_configuration

        self._invalidate_actions_job()
        try:
            repository = self._actions_repository()
            if self.matrix_engine.value not in {'ORCA', 'CFOUR'}:
                raise ValueError("The course workflows accept molecular ORCA or CFOUR jobs only.")
            if self.cb_recipe_r2.value or self.t9_config_path.value.strip():
                raise ValueError("The course job must be self-contained; R2 reference files and T9 checkpoints require a separate approved workflow.")
            if len(parse_run_geometry(self.matrix_geometry.value)[0]) > 50:
                raise ValueError("The course Actions profile accepts at most 50 atoms per job.")
            config = self._collect_run_config()
            model = CalculationMatrixConfig.model_validate(config)
            if any(getattr(model, name) is not None for name in ("hessian_file", "r2_reference_manifest", "t9_fallback", "periodic")):
                raise ValueError("The course job cannot reference files on this computer or a separate calculation environment.")
            payload = model.model_dump_json(indent=2).encode("utf-8") + b"\n"
            if len(payload) > 256 * 1024:
                raise ValueError("The course job JSON must be at most 256 KiB.")
            validate_configuration(payload, model.model_dump(mode="json"))
            project = re.sub(r"[^A-Za-z0-9_-]", "_", self.project_name.value).strip("_")[:64] or "molecule"
            engine_name = model.engine.upper()
            filename = f"{project}-{model.engine}-job.json"
            job_file = f"jobs/{filename}"
            digest = hashlib.sha256(payload).hexdigest()
            self._last_actions_job = {"job_file": job_file, "config": model.model_dump(mode="json"), "sha256": digest, "payload": payload}
            encoded = base64.b64encode(payload).decode("ascii")
            workflow = f"https://github.com/{repository}/actions/workflows/{model.engine}_calculation.yml"
            self.actions_job_download.value = (
                "<p role='status'><b>Actions job prepared.</b> No calculation has been submitted or run.</p>"
                f"<p><a download='{filename}' href='data:application/json;base64,{encoded}'>Download {engine_name} job JSON</a></p>"
                "<p>Use <b>Stage privately and submit</b> with the actual independently reviewed distribution "
                "descriptor and its file checksum. The interface uploads a unique job to your private project "
                "and dispatches the workflow with its exact private staging receipt.</p>"
                f"<p><a href='{workflow}' target='_blank' rel='noopener'>Open owning {engine_name} workflow</a></p>"
                f"<p>Input SHA-256: <code>{digest}</code>. Calculation timeout: {self.actions_timeout.value} seconds.</p>"
            )
            self.state.system_status = "Actions job prepared"
            self.state.error_message = ""
            self.calculation_result.value = "<p>Remote request prepared; awaiting submission and verified results from GitHub Actions.</p>"
        except (ValueError, RuntimeError, OSError, MethodologyViolationError) as exc:
            self.state.error_message = str(exc)
            self.actions_job_download.value = f"<p role='alert'>Actions job was not prepared: {html.escape(str(exc))}</p>"

    def _run_private_actions(self, operation: str) -> None:
        """Run a real owning-project lifecycle operation without blocking the notebook."""
        if self._actions_lifecycle_running:
            return
        try:
            if self.calc_env_dropdown.value != "github-actions":
                raise ValueError("Select GitHub Actions as the calculation environment.")
            repository = self._actions_repository()
            if operation == "submit":
                self._prepare_actions_job()
                if self._last_actions_job is None:
                    raise ValueError("Prepare a valid connected ORCA/CFOUR request first.")
                payload = self._last_actions_job["payload"]
                descriptor = Path(self.actions_asset_descriptor.value.strip()).expanduser()
                descriptor_sha256 = self.actions_asset_descriptor_sha256.value.strip()
                ref = "refs/heads/" + (self.gh_branch_input.value.strip() or "main")
                cores, memory = self.actions_cores.value, self.actions_memory.value
            else:
                payload, descriptor, descriptor_sha256, ref, cores, memory = None, None, None, None, None, None
            task = self.actions_task_id.value.strip()
            selected_run = self.actions_run_id.value.strip()
            runtime = self._run_artifact_root() / "GUI" / "PrivateActions"
        except (ValueError, OSError, RuntimeError) as exc:
            self.actions_lifecycle_status.value = "<p role='alert'>Private Actions operation blocked: " + html.escape(str(exc)) + "</p>"
            return
        self._actions_lifecycle_running = True
        controls = [self.actions_stage_submit, self.actions_refresh, self.actions_cancel,
                    self.actions_download, self.actions_cleanup, self.actions_repair,
                    self.actions_select_run]
        for button in controls:
            button.disabled = True
        self.actions_lifecycle_status.value = "<p role='status'>Running the requested private project operation.</p>"

        def work() -> None:
            try:
                from cochem_base.interfaces.private_actions import PrivateActionsController
                controller = PrivateActionsController(repository, runtime)
                if operation == "submit":
                    result = controller.stage_and_dispatch(
                        payload, descriptor, descriptor_sha256,
                        ref=ref, cores=cores, maxcore_mb=memory,
                    )
                elif operation == "select":
                    if not selected_run.isdigit():
                        raise ValueError("Enter the actual owning-project run ID.")
                    result = controller.select_run(task, int(selected_run))
                elif operation in {"status", "cancel", "download", "cleanup", "repair"}:
                    result = getattr(controller, operation)(task)
                else:
                    raise ValueError("Unsupported private project operation.")
                self.actions_task_id.value = result["task_id"]
                self.actions_lifecycle_status.value = (
                    "<p>Observed private Actions lifecycle:</p><pre>"
                    + html.escape(json.dumps(result, sort_keys=True, indent=2)) + "</pre>"
                )
            except Exception as exc:
                self.actions_lifecycle_status.value = (
                    "<p role='alert'>Private Actions operation blocked: "
                    + html.escape(str(exc))
                    + "</p><p>Use your own authorized browser identity with lab release read access "
                    "and private project Contents/Actions access. No lab credential is needed in Actions.</p>"
                )
            finally:
                self._actions_lifecycle_running = False
                for button in controls:
                    button.disabled = False

        threading.Thread(target=work, daemon=True).start()

    def _cancel_pipeline(self, b: Any = None) -> None:
        if self._pipeline_running:
            self._pipeline_cancellation.set()
            self.btn_cancel.disabled = True
            self.btn_periodic_cancel.disabled = True
            self.state.system_status = "Cancelling calculation..."

    def _pipeline_thread(self, config_path: Path) -> None:
        from cochem_base.core_engine.cochem_core_subprocess_broker import (
            SubprocessCancelledError,
        )
        from cochem_base.calc.calculation_service import run_calculation

        def on_event(event: dict[str, Any]) -> None:
            if event.get("kind") == "log":
                self.telemetry_output.append_stdout(event["message"])
            elif event.get("status") == "RUNNING":
                self.state.system_status = "Running Pipeline..."

        try:
            work_dir = config_path.parent
            configuration = json.loads(config_path.read_text(encoding="utf-8"))
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
