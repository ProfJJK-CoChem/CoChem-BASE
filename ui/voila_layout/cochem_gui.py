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
from typing import Tuple, Any, Optional

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
        valid_engines = ['ORCA', 'CFOUR']
        if v not in valid_engines:
            raise ValueError(f"Unsupported engine: {v}. Must be one of {valid_engines}")
        return v

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
        
        # 3.2 No Code Matrix View
        self.matrix_geometry = widgets.Textarea(
            description="Geometry (XYZ):",
            placeholder="O 0.0 0.0 0.0\nH 0.0 0.75 -0.5\nH 0.0 0.75 0.5",
            layout=widgets.Layout(width='100%', height='100px')
        )
        import shutil
        orca_available = shutil.which("orca") is not None
        cfour_available = shutil.which("xcfour") is not None or shutil.which("cfour") is not None
        
        engine_options = []
        if orca_available:
            engine_options.append(('ORCA', 'ORCA'))
        else:
            engine_options.append(('ORCA [Uninstalled: run python cli.py setup --phase 3]', 'ORCA'))
            
        if cfour_available:
            engine_options.append(('CFOUR', 'CFOUR'))
        else:
            engine_options.append(('CFOUR [Uninstalled: run python cli.py setup --phase 3]', 'CFOUR'))

        self.matrix_engine = widgets.Dropdown(
            options=engine_options,
            value='ORCA',
            description='Engine:'
        )
        if not (orca_available and cfour_available):
            self.matrix_engine.tooltip = "Uninstalled engines can be provisioned via: python cli.py setup --phase 3"

        self.matrix_method = widgets.Dropdown(
            options=['HF', 'B3LYP', 'MP2', 'CCSD', 'CCSD(T)'],
            value='B3LYP',
            description='Method:'
        )
        self.matrix_basis = widgets.Dropdown(
            options=['cc-pVDZ', 'cc-pVTZ', 'cc-pVQZ', 'aug-cc-pVDZ', 'aug-cc-pVTZ', 'def2-SVP', 'def2-TZVP'],
            value='cc-pVTZ',
            description='Basis Set:'
        )

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
            except Exception as e:
                pass
                
        self.matrix_geometry.observe(auto_detect_topos, 'value')
        
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

        self.btn_save_matrix = widgets.Button(
            description="Save/Submit Matrix",
            button_style="success",
            icon="save"
        )
        self.matrix_output = widgets.Output()
        
        self.btn_save_matrix.on_click(self._save_matrix_config)
        
        self.tab_base = widgets.VBox([
            self.matrix_geometry,
            self.matrix_engine,
            self.matrix_method,
            self.matrix_basis
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
        
        self.config_tabs = widgets.Tab(children=[self.tab_base, self.tab_topos, self.tab_torq])
        self.config_tabs.set_title(0, 'Base Config')
        self.config_tabs.set_title(1, 'TOPOS')
        self.config_tabs.set_title(2, 'TORQ')

        self.matrix_config_panel = widgets.VBox([
            widgets.HTML("<h4>Simulation Parameters</h4>"),
            self.config_tabs,
            widgets.HTML("<h4>Live Input Preview</h4>"),
            self.live_preview,
            self.btn_save_matrix,
            self.matrix_output
        ], layout=widgets.Layout(border='1px solid #ccc', padding='10px', margin='10px 0'))

        self.slurm_panel = widgets.VBox([
            widgets.HTML("<h4>HPC/SLURM Submission Panel</h4>"),
            widgets.HTML("<p>Configure HPC scheduler parameters for distributed execution.</p>"),
            widgets.IntText(description="Nodes:", value=1),
            widgets.IntText(description="Tasks/Node:", value=4),
            widgets.Button(description="Submit Job", button_style="primary")
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
            self.matrix_config_panel,
            self.slurm_panel,
            self.telemetry_panel
        ], layout=widgets.Layout(padding='20px'))
        
        # 3.3 Data Inspector View
        self.view_inspector = widgets.VBox([
            widgets.HTML("<h3>Data Inspector (Ab-Initio)</h3>"),
            widgets.HTML("<p>Analysis of ab-initio outputs.</p>"),
            widgets.HTML("<i>Awaiting backend wiring. (Strict Physical Compliance Enforced)</i>")
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

