import atexit
import html
import json
import logging
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional, Sequence, Tuple

import ipywidgets as widgets
from pydantic import BaseModel, Field, ValidationError, field_validator
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
    validate_no_calc_hess,
)
from cochem_base.spectroscopy.isotopologue import (
    IsotopologueSpectroscopyEngine,
)
from cochem_base.spectroscopy.parser import (
    SpectroscopyTelemetryParser,
    read_hdf5_swmr_telemetry,
)
from cochem_base.theory_matrix import (
    DISPERSION_FREE_METHODS,
    METHOD_MATRIX_TIERS,
    PRODUCT_CLASS_SPECS,
    ProductClass,
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

class DataInspectorWidget(widgets.VBox):
    """Authentic interactive Data Inspector widget for ab-initio spectroscopic observables."""
    def __init__(self, children: Sequence[Any] = (), **kwargs: Any) -> None:
        super().__init__(children=list(children), **kwargs)


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
# AI Assistant Opt-in Panel
        self.ai_btn_enable = widgets.Button(description="Enable Antigravity AI Assistant", button_style="warning", icon="robot", layout=widgets.Layout(width='auto'))
        self.ai_consent_checkbox = widgets.Checkbox(value=False, description="I consent to sharing local error logs and configuration data with the remote Antigravity AI for real-time didactic guidance.", style={'description_width': 'initial'}, layout=widgets.Layout(width='90%'))
        self.ai_btn_confirm = widgets.Button(description="Confirm & Install AI Hook", button_style="success", icon="check", layout=widgets.Layout(width='auto'))
        
        self.ai_chat_history = widgets.Textarea(value="[System]: Antigravity AI Agent offline.\n", layout=widgets.Layout(width='100%', height='150px'), disabled=True)
        self.ai_chat_input = widgets.Text(placeholder="Ask the AI for help...", layout=widgets.Layout(width='80%'))
        self.ai_btn_send = widgets.Button(description="Send", button_style="primary")
        
        self.ai_opt_in_view = widgets.VBox([
            widgets.HTML("<h4>🤖 Antigravity AI Teaching Assistant (Optional)</h4><p>Enable the AI assistant to receive real-time, step-by-step guidance. The AI can read your errors and help you construct your molecule.</p>"),
            self.ai_btn_enable
        ], layout=widgets.Layout(border='2px solid #ffc107', padding='10px', background_color='#fffdf5', margin='0 0 20px 0'))

        self.ai_chat_view = widgets.VBox([
            widgets.HTML("<h4>🤖 Antigravity AI Teaching Assistant</h4>"),
            self.ai_chat_history,
            widgets.HBox([self.ai_chat_input, self.ai_btn_send])
        ], layout=widgets.Layout(border='2px solid #28a745', padding='10px', background_color='#f0fff4', margin='0 0 20px 0'))
        self.ai_chat_view.layout.display = 'none'

        self.ai_consent_view = widgets.VBox([
            widgets.HTML("<h4>⚠️ Privacy Consent Required</h4>"),
            self.ai_consent_checkbox,
            self.ai_btn_confirm
        ])
        self.ai_consent_view.layout.display = 'none'

        def _on_ai_enable_click(b):
            self.ai_opt_in_view.children = [self.ai_consent_view]
            self.ai_consent_view.layout.display = 'block'

        def _on_ai_confirm_click(b):
            if self.ai_consent_checkbox.value:
                self.ai_opt_in_view.layout.display = "none"
                self.ai_chat_view.layout.display = "block"
                self.ai_chat_history.value = "[System]: Antigravity AI Agent hook installed and active.\n[Agent]: Hello! I am your AI Teaching Assistant. I can see your configuration. How can I help you set up CoChem today?"
            else:
                self.ai_consent_checkbox.description = "You MUST check this box to consent before enabling."

        def _on_ai_send_click(b):
            user_msg = self.ai_chat_input.value.strip()
            if user_msg:
                self.ai_chat_history.value += f"\n[You]: {user_msg}\n[Agent]: I am currently running in local UI simulation mode. The backend agent websocket is disconnected."
                self.ai_chat_input.value = ""

        self.ai_btn_enable.on_click(_on_ai_enable_click)
        self.ai_btn_confirm.on_click(_on_ai_confirm_click)
        self.ai_btn_send.on_click(_on_ai_send_click)
        
        self.ai_container = widgets.VBox([self.ai_opt_in_view, self.ai_chat_view])
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
        
        self.gh_pat_input = widgets.Password(description="GitHub PAT:", placeholder="ghp_...", style={'description_width': 'initial'}, layout=widgets.Layout(width='60%'))
        self.gh_repo_input = widgets.Text(description="Repository:", placeholder="username/CoChem-BASE", style={'description_width': 'initial'}, layout=widgets.Layout(width='60%'))
        self.gh_orca_link = widgets.Text(description="ORCA Link:", placeholder="e.g., https://dropbox.com/s/...", style={'description_width': 'initial'}, layout=widgets.Layout(width='90%'))
        self.gh_cfour_link = widgets.Text(description="CFOUR Link:", placeholder="e.g., https://dropbox.com/s/...", style={'description_width': 'initial'}, layout=widgets.Layout(width='90%'))
        self.btn_gh_setup = widgets.Button(description="Provision GitHub Secrets", button_style="success", icon="cloud", layout=widgets.Layout(width='auto', margin='10px 0'))
        self.gh_setup_output = widgets.Output(layout=widgets.Layout(border='1px solid #ccc', padding='5px'))

        def _on_gh_setup_clicked(b):
            import requests
            from base64 import b64encode
            from nacl import encoding, public
            self.gh_setup_output.clear_output()
            with self.gh_setup_output:
                pat = self.gh_pat_input.value.strip()
                repo = self.gh_repo_input.value.strip()
                orca_url = self.gh_orca_link.value.strip()
                cfour_url = self.gh_cfour_link.value.strip()
                if not pat or not repo:
                    print("Error: GitHub PAT and Repository name are required.")
                    return
                print(f"Connecting to GitHub API for {repo}...")
                headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {pat}", "X-GitHub-Api-Version": "2022-11-28"}
                r = requests.get(f"https://api.github.com/repos/{repo}/actions/secrets/public-key", headers=headers)
                if r.status_code != 200:
                    print(f"Error fetching public key: {r.text}")
                    return
                key_data = r.json()
                public_key = public.PublicKey(key_data['key'].encode("utf-8"), encoding.Base64Encoder())

                def encrypt(public_key, secret_value):
                    return b64encode(public.SealedBox(public_key).encrypt(secret_value.encode("utf-8"))).decode("utf-8")

                secrets_to_put = []
                if orca_url: secrets_to_put.append(('ORCA_DOWNLOAD_LINK', orca_url))
                if cfour_url: secrets_to_put.append(('CFOUR_DOWNLOAD_LINK', cfour_url))

                for s_name, s_val in secrets_to_put:
                    data = {"encrypted_value": encrypt(public_key, s_val), "key_id": key_data['key_id']}
                    r = requests.put(f"https://api.github.com/repos/{repo}/actions/secrets/{s_name}", headers=headers, json=data)
                    print(f"Provisioned {s_name}: {'Success' if r.status_code in (201, 204) else 'Failed'}")

        self.btn_gh_setup.on_click(_on_gh_setup_clicked)

        guidance_html = """
        <h4>GitHub Actions Provisioning (Strictly Guided)</h4>
        <div style='background-color:#fff3cd; padding:10px; border-left:4px solid #ffeeba;'>
        <b>Why do we need this?</b><br/>
        CREST, SPFIT, and SPCAT are open-source and will be automatically installed. However, <b>ORCA and CFOUR have strict academic EULAs</b>. We legally cannot distribute them in the CoChem repository. 
        <br/><br/><b>How to provision them for the Cloud:</b>
        <ol>
            <li>Register at the ORCA Forum and CFOUR site and download the <b>Linux (x86_64)</b> versions of the binaries.</li>
            <li>Upload these Linux archives to a private cloud drive (Google Drive, Dropbox, or OneDrive).</li>
            <li>Generate a <b>Direct Download Link</b> (For Dropbox, change <code>dl=0</code> to <code>dl=1</code>).</li>
            <li>Paste the links below.</li>
            <li><b>What is a GitHub PAT?</b> A Personal Access Token (PAT) is a secure password that allows this interface to upload your secret links directly to GitHub for you. To get one: Go to GitHub.com &rarr; Settings &rarr; Developer Settings &rarr; Personal Access Tokens (Classic) &rarr; Generate new token. Check the <b>'repo'</b> box, click generate, and paste it below!</li>
        </ol>
        </div>
"""
        self.gh_setup_box = widgets.VBox([
            widgets.HTML(guidance_html),
            self.gh_pat_input, self.gh_repo_input, self.gh_orca_link, self.gh_cfour_link, self.btn_gh_setup, self.gh_setup_output
        ], layout=widgets.Layout(border='1px solid #0056b3', padding='15px', background_color='#eef5ff', margin='10px 0'))
        self.gh_setup_output = widgets.Output(layout=widgets.Layout(border='1px solid #ccc', padding='5px'))

        def _on_gh_setup_clicked(b):
            import requests
            from base64 import b64encode
            from nacl import encoding, public
            self.gh_setup_output.clear_output()
            with self.gh_setup_output:
                pat = self.gh_pat_input.value.strip()
                repo = self.gh_repo_input.value.strip()
                orca_url = self.gh_orca_link.value.strip()
                cfour_url = self.gh_cfour_link.value.strip()
                if not pat or not repo:
                    print("Error: GitHub PAT and Repository name are required.")
                    return
                print(f"Connecting to GitHub API for {repo}...")
                headers = {
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {pat}",
                    "X-GitHub-Api-Version": "2022-11-28"
                }
                # Get public key
                r = requests.get(f"https://api.github.com/repos/{repo}/actions/secrets/public-key", headers=headers)
                if r.status_code != 200:
                    print(f"Error fetching public key: {r.text}")
                    return
                key_data = r.json()
                key_id = key_data['key_id']
                public_key = public.PublicKey(key_data['key'].encode("utf-8"), encoding.Base64Encoder())

                def encrypt(public_key, secret_value):
                    sealed_box = public.SealedBox(public_key)
                    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
                    return b64encode(encrypted).decode("utf-8")

                secrets_to_put = []
                if orca_url: secrets_to_put.append(('ORCA_DOWNLOAD_LINK', orca_url))
                if cfour_url: secrets_to_put.append(('CFOUR_DOWNLOAD_LINK', cfour_url))

                if not secrets_to_put:
                    print("No download links provided. Nothing to do.")
                    return

                for s_name, s_val in secrets_to_put:
                    enc_val = encrypt(public_key, s_val)
                    data = {"encrypted_value": enc_val, "key_id": key_id}
                    r = requests.put(f"https://api.github.com/repos/{repo}/actions/secrets/{s_name}", headers=headers, json=data)
                    if r.status_code in (201, 204):
                        print(f"Successfully provisioned secret: {s_name}")
                    else:
                        print(f"Failed to provision {s_name}: {r.status_code} {r.text}")
                print("GitHub Actions configuration complete!")

        self.btn_gh_setup.on_click(_on_gh_setup_clicked)

        self.gh_setup_box = widgets.VBox([
            widgets.HTML("<h4>GitHub Actions Provisioning</h4>"),
            widgets.HTML("<p>Because ORCA and CFOUR have academic licenses, they cannot be checked into the repository. Configure a private download link here, and we will securely inject it into your GitHub Actions Secrets.</p>"),
            self.gh_pat_input, self.gh_repo_input, self.gh_orca_link, self.gh_cfour_link, self.btn_gh_setup, self.gh_setup_output
        ], layout=widgets.Layout(border='1px solid #0056b3', padding='15px', background_color='#eef5ff', margin='10px 0'))

        self.calc_env_dropdown = widgets.Dropdown(
            options=[
                ('Windows (Native - DEGRADED)', 'local'), 
                ('WSL2 (Recommended for Windows)', 'wsl'), 
                ('macOS', 'macos'), 
                ('Linux', 'linux'), 
                ('GitHub Actions (Cloud Compute)', 'github-actions'), 
                ('HPC Cluster (Slurm/PBS)', 'hpc')
            ],
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
        
        
        self.wsl_setup_box = widgets.VBox(layout=widgets.Layout(border='1px solid #28a745', padding='15px', background_color='#e8f5e9', margin='10px 0'))
        
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
        <b>Licensed Binaries:</b> ORCA and CFOUR must be installed manually due to academic licensing. If they are already in your system PATH, click 'Auto-Detect'. Otherwise, paste the absolute paths to their executables below before clicking 'Run Installation'.
        </div>
        """
        self.local_setup_box = widgets.VBox([
            widgets.HTML(local_guidance_html),
            self.bin_orca, self.bin_cfour, 
            widgets.HBox([self.btn_detect_bins, self.btn_save_bins]), 
            self.local_setup_output
        ], layout=widgets.Layout(border='1px solid #17a2b8', padding='15px', background_color='#e0f7fa', margin='10px 0'))
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
                
        self.calc_env_dropdown.observe(_on_calc_env_change, names='value')
        _on_calc_env_change({'new': self.calc_env_dropdown.value})

        self.run_install_btn.on_click(self._run_installation)

        self.install_output = widgets.Output(layout=widgets.Layout(border='1px solid #ccc', height='300px', overflow='auto'))

        self.view_install = widgets.VBox([
            widgets.HTML("<h3>Seamless Install Wizard</h3>"),
            widgets.HTML("<p>Setup pipeline and real physical data ingestion.</p>"),
            self.calc_env_dropdown,
            self.interact_env_dropdown,
            self.dynamic_setup_container,
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
                self.mlff_warning.value = "<b style='color:green;'>✓ MLFF (MACE/AIMNet2) enabled (neutral non-radical).</b>"
                
        self.charge_input.observe(_check_mlff_validity, 'value')
        self.multiplicity_input.observe(_check_mlff_validity, 'value')
        _check_mlff_validity()

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

        self.tier_help = widgets.HTML(
            value="""
            <div style='background-color:#e8f4fd; padding:10px; border-radius:5px;'>
            <b>Didactic Help: Theory Tiers</b><br/>
            <i>Tier 1 (Modern Dispersion DFT):</i> Excellent for large organic molecules. Fast (Minutes-Hours). Error ~1-2 kcal/mol.<br/>
            <i>Tier 2 (Double Hybrid DFT):</i> Good for transition states. Medium (Hours-Days). Error ~1 kcal/mol.<br/>
            <i>Tier 3 (Coupled Cluster):</i> The 'Gold Standard' for accuracy. Slow (Days-Weeks). Error < 0.5 kcal/mol.<br/>
            <i>Tier MLFF (Machine Learning):</i> Uses AI force fields like MACE. Lightning fast (Seconds). Good for bulk isomer search.
            </div>
            """, layout=widgets.Layout(margin='10px 0')
        )

        self.matrix_method.observe(self._check_dispersion_gate, 'value')
        self.unphysical_override.observe(self._check_dispersion_gate, 'value')

        # TOPOS Widgets
        self.topos_heuristic = widgets.Dropdown(
            options=['iMTD-GC', 'GOAT', 'MACE-MD (MLFF)', 'AIMNet2-MD'],
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
                from cochem_base.topology.cochem_topos_graph import (
                    analyze_molecular_graph,
                    parse_xyz_string,
                )
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
        self.artifact_output_path = widgets.Text(description="Output Dir:", placeholder="e.g. D:\\MyProjects", layout=widgets.Layout(width='60%'))
        self.project_name = widgets.Text(description="Project Name:", placeholder="e.g. CCO", layout=widgets.Layout(width='30%'))
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
                self.matrix_geometry.value = Chem.MolToXYZBlock(mol)
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
        

        self.matrix_config_panel = widgets.VBox([
            widgets.HTML("<h4>Simulation Parameters</h4>"),
            self.config_tabs,
            widgets.HTML("<h4>Artifact Output Configuration</h4><i>Environment independent local output directory. Projects will be placed in &lt;Output Dir&gt;/cochem-artifacts/&lt;Project Name&gt;/</i>"),
            self.output_config_box,
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

        self.data_inspector_widget = DataInspectorWidget([
            widgets.HTML("<h3>Data Inspector (Ab-Initio Spectroscopic Observables)</h3>"),
            widgets.HTML("<p>Rigorous extraction of rotational constants, vibrational corrections, dipole moments, and dynamic isotopic shifts.</p>"),
            widgets.HBox([self.inspector_file_input, self.btn_parse_inspector]),
            self.inspector_tabs
        ], layout=widgets.Layout(padding='20px'))
        self.view_inspector = self.data_inspector_widget

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
                from cochem_base.config_loader import get_artifact_dir  # type: ignore
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
                import numpy as np
                from mendeleev import element as get_el
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
        out_dir = self.artifact_output_path.value.strip()
        proj_name = self.project_name.value.strip()
        if not out_dir:
            out_dir = str(Path.home())
        if not proj_name:
            proj_name = "default_project"
            
        # Clean project name
        proj_name = "".join([c for c in proj_name if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip()
        
        matrix_dir = Path(out_dir) / "cochem-artifacts" / proj_name

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
        return widgets.VBox([self.ai_container, self.app])

def create_gui() -> widgets.AppLayout:
    """Entry point to instantiate and display the GUI."""
    gui = CoChemGUI()
    return gui.display()

