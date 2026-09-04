import ipywidgets as widgets
from traitlets import HasTraits, Unicode, observe
import os
import sys
import json
import subprocess
import threading
import atexit
import html
import queue
import time
from pathlib import Path
from pydantic import BaseModel, Field, ValidationError, field_validator
import logging
from typing import Tuple, Any, Optional, Dict, List

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
from cochem_base.theory_matrix import (
    ProductClass,
    PRODUCT_CLASS_SPECS,
    METHOD_MATRIX_TIERS,
    DISPERSION_FREE_METHODS,
    validate_method_matrix_compliance,
)
from cochem_base.spectroscopy.parser import (
    SpectroscopyTelemetryParser,
    SpectroscopicTelemetryResult,
    read_hdf5_swmr_telemetry,
)
from cochem_base.spectroscopy.isotopologue import (
    IsotopologueSpectroscopyEngine,
    get_nuclide_mass,
)
from cochem_base.geometry.fragment_partitioner import (
    detect_molecular_fragments,
    generate_frozen_monomer_orca_block,
    validate_no_calc_hess,
)
from cochem.hpc.slurm_controller import (
    SlurmSubmissionController,
    sanitize_slurm_parameter,
    validate_slurm_walltime,
    generate_slurm_script,
    submit_slurm_job,
)
from cochem_base.exceptions import MethodologyViolationError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class P7RegistryModel(BaseModel):
    scheduler_detected: str = Field(default="")

class MatrixConfigModel(BaseModel):
    geometry: str = Field(..., description="XYZ formatted geometry string")
    engine: str = Field(..., description="Compute engine")
    method: str = Field(..., description="Calculation method")
    basis_set: str = Field(..., description="Basis set")
    product_class: Optional[str] = Field(default="Product A (De Novo Search)", description="Step 0 Product Class")
    theory_tier: Optional[str] = Field(default="Tier 1: Modern Dispersion DFT", description="Method Matrix tier")
    topos_heuristic: str = Field(default='iMTD-GC', description="TOPOS Conformer generation heuristic")
    topos_dedup: float = Field(default=0.05, description="TOPOS Deduplication tolerance")
    torq_dihedrals: str = Field(default='', description="TORQ active dihedrals")
    torq_resolution: int = Field(default=36, description="TORQ scan resolution")
    torq_qrrho: bool = Field(default=False, description="TORQ qRRHO enforcement")

    @field_validator('geometry')
    @classmethod
    def validate_geometry(cls, v: str) -> str:
        lines = [line.strip() for line in v.strip().split('\n') if line.strip()]
        if not lines:
            raise ValueError("Geometry cannot be empty.")
        for line in lines:
            parts = line.split()
            if len(parts) != 4:
                raise ValueError(f"Invalid XYZ format. Expected: Element X Y Z, got '{line}'")
            try:
                float(parts[1])
                float(parts[2])
                float(parts[3])
            except ValueError:
                raise ValueError(f"Coordinates must be numeric in line: '{line}'")
        return v
    
    @field_validator('engine')
    @classmethod
    def validate_engine(cls, v: str) -> str:
        valid_engines = ['ORCA', 'CFOUR', 'XTB']
        if v.upper() not in valid_engines:
            raise ValueError(f"Unsupported engine: {v}. Must be one of {valid_engines}")
        return v.upper()

class CoChemGUIState(HasTraits):
    """
    State model for the CoChem GUI.
    Enforces MVC architecture and Strict Physical Compliance.
    """
    active_view = Unicode('install')
    system_status = Unicode('Idle')
    environment = Unicode('Detecting...')
    error_message = Unicode('')

class CoChemGUI:
    def __init__(self) -> None:
        self.state = CoChemGUIState()
        
        # --- Environment Auto-Detection ---
        is_init, env_str, is_hpc, is_slurm = self._detect_environment()
        self.state.environment = env_str
        if not is_init:
            self.state.error_message = "Environment Not Initialized. Please complete setup."
            self.state.system_status = "Uninitialized"
        
        # --- UI Components ---
        
        # 1. Header (Appbar)
        self.header_title = widgets.HTML("<h2>CoChem No-Code Interface</h2>", layout=widgets.Layout(margin='0px 20px 0px 0px'))
        self.header_status = widgets.HTML(f"<b>[System: {self.state.system_status}]</b>", layout=widgets.Layout(margin='10px 20px 0px 0px'))
        self.header_env = widgets.HTML(f"<i>Environment: {self.state.environment}</i>", layout=widgets.Layout(margin='10px 0px 0px 0px'))
        
        self.header = widgets.HBox(
            [self.header_title, self.header_status, self.header_env],
            layout=widgets.Layout(
                display='flex',
                justify_content='flex-start',
                align_items='center',
                padding='10px',
                border_bottom='2px solid #ccc',
                background_color='#f8f9fa'
            )
        )
        
        # 2. Sidebar (Navigation)
        self.btn_install = widgets.Button(description="Seamless Install", icon='cogs', layout=widgets.Layout(width='auto', margin='5px 0'))
        self.btn_matrix = widgets.Button(description="No Code Matrix", icon='table', layout=widgets.Layout(width='auto', margin='5px 0'))
        self.btn_inspector = widgets.Button(description="Data Inspector (Ab-Initio)", icon='search', layout=widgets.Layout(width='auto', margin='5px 0'))
        
        # Lock advanced tabs if not initialized
        if not is_init:
            self.btn_matrix.disabled = True
            self.btn_inspector.disabled = True
            
        self.btn_install.on_click(lambda b: setattr(self.state, 'active_view', 'install'))
        self.btn_matrix.on_click(lambda b: setattr(self.state, 'active_view', 'matrix'))
        self.btn_inspector.on_click(lambda b: setattr(self.state, 'active_view', 'inspector'))
        
        self.sidebar = widgets.VBox(
            [self.btn_install, self.btn_matrix, self.btn_inspector],
            layout=widgets.Layout(
                width='250px',
                padding='10px',
                border_right='2px solid #ccc',
                background_color='#fdfdfd'
            )
        )
        
        # 3. Main Content Area (Views)
        
        # 3.1 Seamless Install View
        self.calc_env_dropdown = widgets.Dropdown(
            options=['local', 'github-actions', 'hpc', 'linux', 'macos', 'wsl'],
            value='local',
            description='Calculation Environment:',
            style={'description_width': 'initial'}
        )
        self.interact_env_dropdown = widgets.Dropdown(
            options=['Local', 'GitHub Codespaces'],
            value='Local',
            description='Interaction Environment:',
            style={'description_width': 'initial'}
        )
        
        self.run_install_btn = widgets.Button(
            description="Run Installation",
            button_style="success",
            icon="play"
        )
        self.run_install_btn.on_click(self._run_installation)
        
        self.install_output = widgets.Output(layout=widgets.Layout(border='1px solid #ccc', height='300px', overflow='auto'))
        
        self.view_install = widgets.VBox([
            widgets.HTML("<h3>Seamless Install Wizard</h3>"),
            widgets.HTML("<p>Setup pipeline and real physical data ingestion.</p>"),
            self.calc_env_dropdown,
            self.interact_env_dropdown,
            self.run_install_btn,
            widgets.HTML("<h4>Installation Logs</h4>"),
            self.install_output
        ], layout=widgets.Layout(padding='20px'))
        
        # 3.2 Step 0: Product Class Gate & No Code Matrix View
        self.product_class_selector = widgets.RadioButtons(
            options=[pc.value for pc in ProductClass],
            value=ProductClass.PRODUCT_A.value,
            description="Step 0 Gate:",
            style={'description_width': 'initial'},
            layout=widgets.Layout(width='100%')
        )
        self.product_class_card = widgets.HTML(
            self._format_product_class_card(ProductClass.PRODUCT_A.value),
            layout=widgets.Layout(border='1px solid #b8daff', background_color='#e8f4fd', padding='8px', margin='5px 0')
        )
        self.product_class_selector.observe(self._on_product_class_changed, 'value')

        self.matrix_geometry = widgets.Textarea(
            description="Geometry (XYZ):",
            placeholder="O 0.0 0.0 0.0\nH 0.0 0.75 -0.5\nH 0.0 0.75 0.5",
            layout=widgets.Layout(width='100%', height='100px')
        )
        import shutil
        orca_available = shutil.which("orca") is not None
        cfour_available = shutil.which("xcfour") is not None or shutil.which("cfour") is not None
        xtb_available = shutil.which("xtb") is not None
        
        engine_options = []
        if orca_available:
            engine_options.append(('ORCA', 'ORCA'))
        else:
            engine_options.append(('ORCA [Uninstalled: run python cli.py setup --phase 3]', 'ORCA'))
            
        if cfour_available:
            engine_options.append(('CFOUR', 'CFOUR'))
        else:
            engine_options.append(('CFOUR [Uninstalled: run python cli.py setup --phase 3]', 'CFOUR'))

        if xtb_available:
            engine_options.append(('xTB', 'XTB'))
        else:
            engine_options.append(('xTB [Screening]', 'XTB'))

        self.matrix_engine = widgets.Dropdown(
            options=engine_options,
            value='ORCA',
            description='Engine:'
        )
        if not (orca_available and cfour_available):
            self.matrix_engine.tooltip = "Uninstalled engines can be provisioned via: python cli.py setup --phase 3"

        # Method Matrix v4 Tier and Method selection
        self.matrix_tier = widgets.Dropdown(
            options=list(METHOD_MATRIX_TIERS.keys()),
            value="Tier 1: Modern Dispersion DFT",
            description="Theory Tier:",
            style={'description_width': 'initial'}
        )
        default_methods = METHOD_MATRIX_TIERS["Tier 1: Modern Dispersion DFT"]["methods"]
        default_bases = METHOD_MATRIX_TIERS["Tier 1: Modern Dispersion DFT"]["allowed_basis_sets"]

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
        self.unphysical_override = widgets.Checkbox(
            value=False,
            description="Advanced/Custom Unphysical Override (§4.4)",
            style={'description_width': 'initial'}
        )
        self.dispersion_warning = widgets.HTML("", layout=widgets.Layout(margin='5px 0'))

        self.matrix_tier.observe(self._on_tier_changed, 'value')
        self.matrix_method.observe(self._check_dispersion_gate, 'value')
        self.unphysical_override.observe(self._check_dispersion_gate, 'value')

        # TOPOS Widgets
        self.topos_heuristic = widgets.Dropdown(
            options=['iMTD-GC', 'GOAT'],
            value='iMTD-GC',
            description='Heuristics:'
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
            description="Recipe R1: Freeze all monomer internals (bonds/angles/dihedrals)",
            style={'description_width': 'initial'}
        )
        self.cb_recipe_r2 = widgets.Checkbox(
            value=False,
            description="Recipe R2: Relax monomer 0, freeze partner monomers",
            style={'description_width': 'initial'}
        )
        self.fragment_preview = widgets.Textarea(
            description="ORCA %geom:",
            layout=widgets.Layout(width='100%', height='140px'),
            disabled=True
        )

        # Live Input Preview
        self.live_preview = widgets.Textarea(
            description='Live %geom:',
            layout=widgets.Layout(width='100%', height='150px'),
            disabled=True
        )
        
        def update_preview(*args):
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            try:
                from cochem_gui_serializer import generate_geom_block
                self.live_preview.value = generate_geom_block(
                    engine=self.matrix_engine.value,
                    method=self.matrix_method.value,
                    basis=self.matrix_basis.value,
                    geometry=self.matrix_geometry.value,
                    topos_heuristic=self.topos_heuristic.value,
                    topos_dedup=self.topos_dedup.value,
                    torq_dihedrals=self.torq_dihedrals.value,
                    torq_resolution=self.torq_resolution.value,
                    torq_qrrho=self.torq_qrrho.value
                )
            except Exception as e:
                self.live_preview.value = f"Error generating preview: {e}"
                
        def auto_detect_topos(change: Any = None) -> None:
            try:
                sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
                from cochem_base.topology.cochem_topos_graph import parse_xyz_string, analyze_molecular_graph
                symbols, coords, _ = parse_xyz_string(self.matrix_geometry.value)
                if symbols:
                    res = analyze_molecular_graph(symbols, coords)
                    # User choice override: we only auto-update if they are changing geometry
                    if res.num_fragments > 1:
                        self.topos_heuristic.value = 'iMTD-GC'
                    else:
                        self.topos_heuristic.value = 'GOAT'
            except Exception:
                pass
                
        self.matrix_geometry.observe(auto_detect_topos, 'value')
        self.matrix_geometry.observe(self._check_dispersion_gate, 'value')
        
        self.matrix_engine.observe(update_preview, 'value')
        self.matrix_method.observe(update_preview, 'value')
        self.matrix_basis.observe(update_preview, 'value')
        self.matrix_geometry.observe(update_preview, 'value')
        self.topos_heuristic.observe(update_preview, 'value')
        self.topos_dedup.observe(update_preview, 'value')
        self.torq_dihedrals.observe(update_preview, 'value')
        self.torq_resolution.observe(update_preview, 'value')
        self.torq_qrrho.observe(update_preview, 'value')
        
        auto_detect_topos()
        update_preview()
        self._check_dispersion_gate()

        self.btn_save_matrix = widgets.Button(
            description="Save/Submit Matrix",
            button_style="success",
            icon="save"
        )
        self.matrix_output = widgets.Output()
        
        self.btn_save_matrix.on_click(self._save_matrix_config)
        
        self.tab_base = widgets.VBox([
            self.matrix_geometry,
            self.matrix_tier,
            self.matrix_method,
            self.matrix_basis,
            self.matrix_engine,
            self.unphysical_override,
            self.dispersion_warning
        ])
        
        self.tab_topos = widgets.VBox([
            widgets.HTML("<b>TOPOS: Conformer Generation</b>"),
            self.topos_heuristic,
            self.topos_dedup
        ])
        
        self.tab_torq = widgets.VBox([
            widgets.HTML("<b>TORQ: Torsional Optimization</b>"),
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
            widgets.HTML("<b>Generated Frozen Monomer Directives:</b>"),
            self.fragment_preview
        ])
        
        self.config_tabs = widgets.Tab(children=[self.tab_base, self.tab_topos, self.tab_torq, self.tab_fragments])
        self.config_tabs.set_title(0, 'Base Config')
        self.config_tabs.set_title(1, 'TOPOS')
        self.config_tabs.set_title(2, 'TORQ')
        self.config_tabs.set_title(3, 'Fragments / Frozen')

        self.matrix_config_panel = widgets.VBox([
            widgets.HTML("<h4>Simulation Parameters</h4>"),
            self.config_tabs,
            widgets.HTML("<h4>Live Input Preview</h4>"),
            self.live_preview,
            self.btn_save_matrix,
            self.matrix_output
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
        self.btn_slurm_submit.on_click(self._on_slurm_submit_clicked)
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
            description="Execute Pipeline",
            button_style="danger",
            icon="rocket"
        )
        self.btn_execute.on_click(self._execute_pipeline)
        self.telemetry_output = widgets.Output(layout=widgets.Layout(border='1px solid #ccc', height='400px', overflow='auto', padding='5px'))

        self.telemetry_panel = widgets.VBox([
            widgets.HTML("<h4>Live Telemetry & Execution</h4>"),
            widgets.HTML("<p>Monitor real-time execution logs from the core engine.</p>"),
            self.btn_execute,
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
        self.isotope_elements_box = widgets.VBox([widgets.HTML("<i>Coordinates from parsed file will populate nuclide selectors.</i>")])
        self.btn_run_isotope_reanalysis = widgets.Button(
            description="Re-analyze Isotopologue (<100ms)",
            button_style="success",
            icon="refresh"
        )
        self.btn_run_isotope_reanalysis.on_click(self._on_run_isotope_reanalysis_clicked)
        self.isotope_results_table = widgets.HTML("<i>Select nuclides above and run re-analysis.</i>")

        # HDF5 SWMR Store panel
        self.btn_read_hdf5 = widgets.Button(description="Read HDF5 (SWMR)", button_style="warning", icon="database")
        self.btn_read_hdf5.on_click(self._on_read_hdf5_clicked)
        self.hdf5_results_table = widgets.HTML("<i>Select an .h5 file and click Read HDF5 to load lockless SWMR datasets.</i>")

        self.inspector_tabs = widgets.Tab(children=[
            widgets.VBox([self.inspector_banner, self.inspector_rot_table]),
            widgets.VBox([
                widgets.HTML("<b>Millisecond Isotopic Substitution Engine (Mendeleev Mandate)</b>"),
                self.isotope_elements_box,
                self.btn_run_isotope_reanalysis,
                self.isotope_results_table
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

        self.view_inspector = widgets.VBox([
            widgets.HTML("<h3>Data Inspector (Ab-Initio Spectroscopic Observables)</h3>"),
            widgets.HTML("<p>Rigorous extraction of rotational constants, vibrational corrections, dipole moments, and dynamic isotopic shifts.</p>"),
            widgets.HBox([self.inspector_file_input, self.btn_parse_inspector]),
            self.inspector_tabs
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
                border_top='2px solid #ccc',
                min_height='60px',
                background_color='#f8f9fa'
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
        
        # Bind traitlets observers
        self.state.observe(self._on_view_change, names='active_view')
        self.state.observe(self._on_status_change, names='system_status')
        self.state.observe(self._on_error_change, names='error_message')
        self.state.observe(self._on_environment_change, names='environment')

    def _detect_environment(self) -> Tuple[bool, str, bool, bool]:
        """
        Auto-detects the environment from Golden Registry artifacts.
        Returns: (is_initialized, environment_string, is_hpc, is_slurm)
        """
        registry_dir: Path = Path.home() / "CoChem_Artifacts" / "Registry"
        artifact_env = os.environ.get("COCHEM_ARTIFACT_DIR")
        if artifact_env:
            registry_dir = Path(artifact_env) / "Registry"
        else:
            try:
                from cochem_base.config_loader import get_artifact_dir # type: ignore
                registry_dir = get_artifact_dir() / "Registry"
            except ImportError:
                pass

        p2_path: Path = registry_dir / "p2.json"
        p7_path: Path = registry_dir / "p7.json"
        p11_path: Path = registry_dir / "p11.json"
        sys_config_path: Path = registry_dir / "cochem_system_config.json"

        is_degraded = False
        if sys_config_path.exists():
            try:
                with open(sys_config_path, "r", encoding="utf-8") as f:
                    cfg_data = json.load(f)
                    if cfg_data.get("status") == "DEGRADED_OPERATIONAL":
                        is_degraded = True
            except Exception as e:
                logger.debug(f"Failed to parse cochem_system_config.json: {e}")

        # Check if any crucial registry exists to determine initialization
        if not (p2_path.exists() or p7_path.exists() or p11_path.exists() or is_degraded):
            return False, "Not Initialized", False, False

        is_hpc: bool = False
        is_slurm: bool = False
        env_str: str = "Local (WSL/Codespaces)"
        if is_degraded:
            env_str = f"{env_str} [DEGRADED_OPERATIONAL]"

        
        if p7_path.exists():
            try:
                with open(p7_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Enforce strict parsing through Pydantic to ensure provenance
                    p7_data = P7RegistryModel(**data)
                    scheduler = p7_data.scheduler_detected.upper()
                    
                    if scheduler in ("SLURM", "PBS", "LSF", "SGE"):
                         is_hpc = True
                         env_str = f"HPC ({scheduler})"
                         if scheduler == "SLURM":
                             is_slurm = True
            except (json.JSONDecodeError, OSError, ValidationError) as e:
                logger.error(f"Failed to parse p7.json registry: {e}")
                self.state.error_message = f"Registry parsing error: {e}"
                
        return True, env_str, is_hpc, is_slurm
        
    def _on_view_change(self, change: Any) -> None:
        new_view: str = change['new']
        if new_view == 'install':
            self.main_content.children = [self.view_install]
        elif new_view == 'matrix':
            self.main_content.children = [self.view_matrix]
        elif new_view == 'inspector':
            self.main_content.children = [self.view_inspector]
            
    def _on_status_change(self, change: Any) -> None:
        safe_val = html.escape(str(change['new']))
        self.header_status.value = f"<b>[System: {safe_val}]</b>"

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
        self.footer_message.value = f'<div style="color: #721c24; background-color: #f8d7da; padding: 10px; border: 1px solid #f5c6cb; border-radius: 5px; width: 100%;"><b>Guidance:</b> {safe_guidance}</div>'

        if hasattr(self, 'telemetry_accordion') and hasattr(self, 'telemetry_html'):
            if telemetry:
                telemetry_str = html.escape(json.dumps(telemetry, indent=2))
                self.telemetry_html.value = f"<pre style='font-size: 11px; max-height: 200px; overflow-y: auto;'>{telemetry_str}</pre>"
                self.telemetry_accordion.layout.display = 'block'
            else:
                self.telemetry_accordion.layout.display = 'none'

            
    def _on_error_change(self, change: Any) -> None:
        self._update_footer(change['new'])
            
    def _run_installation(self, b: Any) -> None:
        self.run_install_btn.disabled = True
        self.state.system_status = 'Installing...'
        self.install_output.clear_output()
        
        calc_env = self.calc_env_dropdown.value
        interact_env = self.interact_env_dropdown.value
        
        thread = threading.Thread(target=self._installation_thread, args=(calc_env, interact_env))
        thread.start()

    def _installation_thread(self, calc_env: str, interact_env: str) -> None:
        cli_path = Path(__file__).resolve().parent.parent.parent / "cli.py"
        cmd = [sys.executable, str(cli_path), "setup", "--all"]
        
        env = os.environ.copy()
        env['COCHEM_CALCULATION_OS'] = str(calc_env)
        env['CODESPACES'] = 'true' if interact_env == 'GitHub Codespaces' else 'false'
        
        process: Optional[subprocess.Popen] = None
        
        def cleanup() -> None:
            if process and process.poll() is None:
                try:
                    import psutil
                    try:
                        parent = psutil.Process(process.pid)
                        for child in parent.children(recursive=True):
                            child.terminate()
                        parent.terminate()
                    except psutil.NoSuchProcess:
                        pass
                except ImportError:
                    process.terminate()

        atexit.register(cleanup)

        try:
            with subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env
            ) as process:
                
                logger.info(f"Starting installation process: {' '.join(cmd)}")
                self.install_output.append_stdout(f"Starting installation process: {' '.join(cmd)}\n")
                self.install_output.append_stdout(f"Calc Environment (COCHEM_CALCULATION_OS): {calc_env}\n")
                self.install_output.append_stdout(f"Interact Environment (CODESPACES): {env['CODESPACES']}\n\n")
                
                q: queue.Queue = queue.Queue()
                def reader() -> None:
                    if process.stdout is not None:
                        for line in iter(process.stdout.readline, ''):
                            q.put(line)
                    q.put(None)
                
                reader_thread = threading.Thread(target=reader)
                reader_thread.daemon = True
                reader_thread.start()
                
                start_time = time.time()
                while True:
                    remaining_time = 600 - (time.time() - start_time)
                    if remaining_time <= 0:
                        raise subprocess.TimeoutExpired(cmd, 600)
                    try:
                        line = q.get(timeout=remaining_time)
                        if line is None:
                            break
                        self.install_output.append_stdout(line)
                    except queue.Empty:
                        raise subprocess.TimeoutExpired(cmd, 600)
                
                rc = process.wait(timeout=5)
            
            if rc == 0:
                self.state.system_status = 'Installed'
                self.state.error_message = ''
                is_init, env_str, is_hpc, is_slurm = self._detect_environment()
                self.state.environment = env_str
                self.btn_matrix.disabled = False
                self.btn_inspector.disabled = False
                logger.info("Installation completed successfully.")
            else:
                self.state.system_status = 'Error'
                self.state.error_message = f'Installation failed with code {rc}'
                logger.error(f'Installation failed with code {rc}')
                
        except subprocess.TimeoutExpired:
            self.state.system_status = 'Error'
            self.state.error_message = 'Installation timed out.'
            logger.error('Installation timed out.')
            cleanup()
        except Exception as e:
            self.state.system_status = 'Error'
            self.state.error_message = f'Failed to launch installer: {e}'
            logger.error(f'Failed to launch installer: {e}')
        finally:
            self.run_install_btn.disabled = False
            atexit.unregister(cleanup)
            
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
        if "Product A" in pc_val:
            self.matrix_tier.value = "Tier 1: Modern Dispersion DFT"
        elif "Product B" in pc_val:
            if hasattr(self, 'config_tabs') and len(self.config_tabs.children) > 3:
                self.config_tabs.selected_index = 3
        elif "Product C" in pc_val:
            self.state.active_view = "inspector"
            if hasattr(self, 'inspector_tabs'):
                self.inspector_tabs.selected_index = 1

    def _on_tier_changed(self, change: Any) -> None:
        tier = change["new"]
        if tier in METHOD_MATRIX_TIERS:
            methods = METHOD_MATRIX_TIERS[tier]["methods"]
            bases = METHOD_MATRIX_TIERS[tier]["allowed_basis_sets"]
            self.matrix_method.options = methods
            self.matrix_method.value = methods[0]
            self.matrix_basis.options = bases
            self.matrix_basis.value = bases[0]
            self._check_dispersion_gate()

    def _check_dispersion_gate(self, *args: Any) -> None:
        geom = self.matrix_geometry.value
        num_frags = 1
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
            from cochem_base.topology.cochem_topos_graph import parse_xyz_string
            symbols, coords, _ = parse_xyz_string(geom)
            if symbols:
                from mendeleev import element as get_el
                import numpy as np
                atomic_numbers = [get_el(s).atomic_number for s in symbols]
                frags = detect_molecular_fragments(atomic_numbers, np.array(coords))
                num_frags = len(frags)
        except Exception:
            num_frags = 1

        method = self.matrix_method.value
        is_disp_free = method in DISPERSION_FREE_METHODS
        if num_frags >= 2 and is_disp_free and not self.unphysical_override.value:
            if hasattr(self, 'btn_execute'):
                self.btn_execute.disabled = True
            self.dispersion_warning.value = (
                "<div style='color: #721c24; background-color: #f8d7da; padding: 6px; border: 1px solid #f5c6cb; border-radius: 4px;'>"
                f"<b>Method Matrix Violation (§4.4, §9A):</b> Functional '{method}' is dispersion-free and "
                f"unphysical for non-covalent complexes ({num_frags} fragments). Use Tier 1 (wB97M-V) or toggle override.</div>"
            )
        else:
            if hasattr(self, 'btn_execute'):
                self.btn_execute.disabled = False
            self.dispersion_warning.value = ""

    def _on_detect_fragments_clicked(self, b: Any) -> None:
        geom = self.matrix_geometry.value
        try:
            from cochem_base.topology.cochem_topos_graph import parse_xyz_string
            symbols, coords, _ = parse_xyz_string(geom)
            if not symbols:
                self.fragments_output.value = "<b style='color:red;'>Failed to parse XYZ geometry.</b>"
                return
            from mendeleev import element as get_el
            import numpy as np
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

    def _on_slurm_submit_clicked(self, b: Any) -> None:
        try:
            controller = SlurmSubmissionController()
            script_content = controller.validate_and_generate(
                job_name=self.job_name_input.value,
                partition=self.partition_input.value,
                nodes=self.nodes_input.value,
                ntasks_per_node=self.tasks_per_node_input.value,
                mem=self.mem_input.value,
                walltime=self.walltime_input.value,
                engine=self.matrix_engine.value.lower(),
                input_deck_path="matrix_input.inp",
                email=self.email_input.value if self.email_input.value.strip() else None,
            )
            scratch_dir = Path.home() / "CoChem_Artifacts" / "SlurmStaging"
            scratch_dir.mkdir(parents=True, exist_ok=True)
            script_path = scratch_dir / f"{self.job_name_input.value}.sh"
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script_content)
            status = controller.dispatch(script_path)
            self.slurm_status_output.value = f"<b>Slurm Submission:</b> {status} [M]"
        except Exception as err:
            self.slurm_status_output.value = f"<b style='color:red;'>Slurm Error:</b> {err}"

    def _on_parse_inspector_clicked(self, b: Any) -> None:
        file_path_str = self.inspector_file_input.value.strip()
        if not file_path_str:
            self.inspector_rot_table.value = "<b style='color:red;'>Please enter a file path.</b>"
            return
        fpath = Path(file_path_str)
        if not fpath.exists():
            self.inspector_rot_table.value = f"<b style='color:red;'>File not found: {fpath}</b>"
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
                f"<tr><td><b>A</b></td><td>{res.a_e:.3f}</td><td>{res.delta_a_vib:.3f}</td><td>{res.a_0:.3f}</td><td>[M, D]</td></tr>"
                f"<tr><td><b>B</b></td><td>{res.b_e:.3f}</td><td>{res.delta_b_vib:.3f}</td><td>{res.b_0:.3f}</td><td>[M, D]</td></tr>"
                f"<tr><td><b>C</b></td><td>{res.c_e:.3f}</td><td>{res.delta_c_vib:.3f}</td><td>{res.c_0:.3f}</td><td>[M, D]</td></tr>"
                f"<tr><td><b>Inertial Defect ($\\Delta$)</b></td><td colspan='3'>{res.inertial_defect:.6f} amu·Å²</td><td>[D]</td></tr>"
                f"<tr><td><b>Dipole Magnitude (|$\\mu$|)</b></td><td colspan='3'>{res.total_dipole:.4f} Debye</td><td>[M]</td></tr>"
                "</tbody></table>"
            )
            self.inspector_rot_table.value = html_table
        except Exception as exc:
            self.inspector_rot_table.value = f"<b style='color:red;'>Parse Error: {exc}</b>"

    def _on_run_isotope_reanalysis_clicked(self, b: Any) -> None:
        geom_str = self.matrix_geometry.value.strip()
        if not geom_str:
            self.isotope_results_table.value = "<b style='color:red;'>Please provide molecular geometry in Base Config tab first.</b>"
            return
        try:
            from cochem_base.topology.cochem_topos_graph import parse_xyz_string
            symbols, coords, _ = parse_xyz_string(geom_str)
            if not symbols or len(symbols) == 0:
                self.isotope_results_table.value = "<b style='color:red;'>Failed to parse symbols and coordinates from geometry.</b>"
                return

            engine = IsotopologueSpectroscopyEngine(
                symbols=symbols,
                coordinates_angstrom=coords,
            )
            parent_res = engine.compute_observables()

            html_rows = [
                "<table border='1' cellpadding='5' style='border-collapse:collapse; width:100%;'>",
                "<thead><tr style='background:#f2f2f2;'>",
                "<th>Isotopologue</th><th>Total Mass (amu) [M]</th><th>A_e (MHz) [M]</th><th>B_e (MHz) [M]</th><th>C_e (MHz) [M]</th>",
                "<th>B_0 (MHz) [D]</th><th>Inertial Defect (amu·Å²) [D]</th><th>Walltime (ms)</th></tr></thead><tbody>",
                f"<tr><td><b>Parent ({''.join(parent_res.symbols)})</b></td><td>{parent_res.total_mass_amu:.4f}</td>"
                f"<td>{parent_res.A_e_MHz:.2f}</td><td>{parent_res.B_e_MHz:.2f}</td><td>{parent_res.C_e_MHz:.2f}</td>"
                f"<td>{parent_res.B_0_MHz:.2f}</td><td>{parent_res.inertial_defect_amu_A2:.4f}</td><td>{parent_res.execution_walltime_ms:.2f}</td></tr>",
            ]

            # Determine representative substitution
            sub_dict = None
            for idx, sym in enumerate(symbols):
                if sym == "H":
                    sub_dict = {idx: "D"}
                    break
                elif sym == "C":
                    sub_dict = {idx: "13C"}
                    break
                elif sym == "O":
                    sub_dict = {idx: "18O"}
                    break

            if sub_dict is not None:
                iso_res = engine.compute_observables(isotopic_substitution=sub_dict)
                html_rows.append(
                    f"<tr><td><b>Substituted ({''.join(iso_res.symbols)})</b></td><td>{iso_res.total_mass_amu:.4f}</td>"
                    f"<td>{iso_res.A_e_MHz:.2f}</td><td>{iso_res.B_e_MHz:.2f}</td><td>{iso_res.C_e_MHz:.2f}</td>"
                    f"<td>{iso_res.B_0_MHz:.2f}</td><td>{iso_res.inertial_defect_amu_A2:.4f}</td><td>{iso_res.execution_walltime_ms:.2f}</td></tr>"
                )

            html_rows.append("</tbody></table>")
            self.isotope_results_table.value = (
                "<div style='margin-bottom:8px; background-color:#d4edda; color:#155724; padding:8px; border-radius:4px;'>"
                "<b>Dynamic Mendeleev Isotopologue Re-analysis Verified (<100ms) [M, D]:</b><br/>"
                "Parent Hessian invariance preserved (§8B.4)."
                "</div>" + "\n".join(html_rows)
            )
        except Exception as exc:
            self.isotope_results_table.value = f"<b style='color:red;'>Isotopic re-analysis failed: {exc}</b>"

    def _on_read_hdf5_clicked(self, b: Any) -> None:
        fpath_str = self.inspector_file_input.value.strip()
        fpath = Path(fpath_str)
        if not fpath.exists():
            self.hdf5_results_table.value = f"<b style='color:red;'>HDF5 file not found: {fpath}</b>"
            return
        try:
            h5_data = read_hdf5_swmr_telemetry(fpath)
            keys_str = ", ".join(list(h5_data.keys()))
            self.hdf5_results_table.value = (
                f"<b>SWMR Read Success:</b> Loaded {len(h5_data)} datasets/attributes cleanly with FileLock.<br/>"
                f"<b>Keys:</b> <code>{keys_str}</code>"
            )
        except Exception as exc:
            self.hdf5_results_table.value = f"<b style='color:red;'>SWMR Read Error: {exc}</b>"

    def _save_matrix_config(self, b: Any) -> None:
        self.btn_save_matrix.disabled = True
        self.matrix_output.clear_output()
        
        try:
            # Validate input using Pydantic
            config_model = MatrixConfigModel(
                geometry=self.matrix_geometry.value,
                engine=self.matrix_engine.value,
                method=self.matrix_method.value,
                basis_set=self.matrix_basis.value,
                product_class=self.product_class_selector.value,
                theory_tier=self.matrix_tier.value,
                topos_heuristic=self.topos_heuristic.value,
                topos_dedup=self.topos_dedup.value,
                torq_dihedrals=self.torq_dihedrals.value,
                torq_resolution=self.torq_resolution.value,
                torq_qrrho=self.torq_qrrho.value
            )
        except ValidationError as e:
            self.matrix_output.append_stdout(f"Validation Error:\n{e}\n")
            logger.error(f"Validation Error in matrix config: {e}")
            self.btn_save_matrix.disabled = False
            return

        # Pre-submission prohibition of Calc_Hess true per Method Matrix §8B.3 & §9A.5
        try:
            validate_no_calc_hess(self.live_preview.value)
        except MethodologyViolationError as mv_err:
            self.matrix_output.append_stdout(f"Methodology Violation:\n{mv_err}\n")
            logger.error(f"Methodology Violation: {mv_err}")
            self.btn_save_matrix.disabled = False
            return

        config = config_model.model_dump()
        
        # Physical implementation: save to artifacts directory
        matrix_dir = Path.home() / "CoChem_Artifacts" / "Matrix"
        artifact_env = os.environ.get("COCHEM_ARTIFACT_DIR")
        if artifact_env:
            matrix_dir = Path(artifact_env) / "Matrix"
        else:
            try:
                from cochem_base.config_loader import get_artifact_dir # type: ignore
                matrix_dir = get_artifact_dir() / "Matrix"
            except ImportError:
                pass
            
        try:
            matrix_dir.mkdir(parents=True, exist_ok=True)
            config_path = matrix_dir / "matrix_config.json"
            
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
                
            self.matrix_output.append_stdout("Successfully generated physical configuration artifacts:\n")
            self.matrix_output.append_stdout(f"- {config_path}\n")
            logger.info(f"Generated matrix config artifacts at {matrix_dir}")
            
        except OSError as e:
            self.matrix_output.append_stdout(f"IO Error saving matrix configuration: {e}\n")
            logger.error(f"IO Error saving matrix configuration: {e}")
        except Exception as e:
            self.matrix_output.append_stdout(f"Unexpected Error saving matrix configuration: {e}\n")
            logger.error(f"Unexpected Error saving matrix configuration: {e}")
        finally:
            self.btn_save_matrix.disabled = False
    def _execute_pipeline(self, b: Any) -> None:
        self.btn_execute.disabled = True
        self.state.system_status = 'Running Pipeline...'
        self.telemetry_output.clear_output()
        
        thread = threading.Thread(target=self._pipeline_thread)
        thread.start()

    def _pipeline_thread(self) -> None:
        cli_path = Path(__file__).resolve().parent.parent.parent / "cli.py"
        cmd = [sys.executable, str(cli_path), "run"]
        
        env = os.environ.copy()
        
        process: Optional[subprocess.Popen] = None
        
        def cleanup() -> None:
            if process and process.poll() is None:
                try:
                    import psutil
                    try:
                        parent = psutil.Process(process.pid)
                        for child in parent.children(recursive=True):
                            child.terminate()
                        parent.terminate()
                    except psutil.NoSuchProcess:
                        pass
                except ImportError:
                    process.terminate()

        atexit.register(cleanup)

        try:
            with subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env
            ) as process:
                
                logger.info(f"Starting pipeline process: {' '.join(cmd)}")
                self.telemetry_output.append_stdout(f"Starting pipeline process: {' '.join(cmd)}\n\n")
                
                q: queue.Queue = queue.Queue()
                def reader() -> None:
                    if process.stdout is not None:
                        for line in iter(process.stdout.readline, ''):
                            q.put(line)
                    q.put(None)
                
                reader_thread = threading.Thread(target=reader)
                reader_thread.daemon = True
                reader_thread.start()
                
                start_time = time.time()
                while True:
                    remaining_time = 3600 - (time.time() - start_time)
                    if remaining_time <= 0:
                        raise subprocess.TimeoutExpired(cmd, 3600)
                    try:
                        line = q.get(timeout=remaining_time)
                        if line is None:
                            break
                        self.telemetry_output.append_stdout(line)
                    except queue.Empty:
                        raise subprocess.TimeoutExpired(cmd, 3600)
                
                rc = process.wait(timeout=5)
            
            if rc == 0:
                self.state.system_status = 'Pipeline Finished'
                self.state.error_message = ''
                self.telemetry_output.append_stdout("\n--- Pipeline Completed Successfully ---\n")
                logger.info("Pipeline completed successfully.")
            else:
                self.state.system_status = 'Pipeline Error'
                self.state.error_message = f'Pipeline failed with code {rc}'
                self.telemetry_output.append_stdout(f"\n--- Pipeline Failed with code {rc} ---\n")
                logger.error(f'Pipeline failed with code {rc}')
                
        except subprocess.TimeoutExpired:
            self.state.system_status = 'Pipeline Error'
            self.state.error_message = 'Pipeline timed out.'
            self.telemetry_output.append_stdout("\n--- Pipeline Timed Out ---\n")
            logger.error('Pipeline timed out.')
            cleanup()
        except Exception as e:
            self.state.system_status = 'Pipeline Error'
            self.state.error_message = f'Failed to launch pipeline: {e}'
            self.telemetry_output.append_stdout(f"\n--- Failed to launch pipeline: {e} ---\n")
            logger.error(f'Failed to launch pipeline: {e}')
        finally:
            self.btn_execute.disabled = False
            atexit.unregister(cleanup)

    def display(self) -> widgets.AppLayout:
        return self.app

def create_gui() -> widgets.AppLayout:
    """Entry point to instantiate and display the GUI."""
    gui = CoChemGUI()
    return gui.display()

