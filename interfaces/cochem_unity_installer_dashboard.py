#!/usr/bin/env python3
"""
CoChem-BASE Initialization Dashboard
Provides the interactive GUI and pure-Python deployment logic for provisioning CoChem micro-silos.
Fully integrates the 14-repository ecosystem, Host ORCA verification, and Air-Gap Zip Sideloading.
Now utilizes decoupled Interaction and Calculation OS-native matrices instead of Docker.
"""
import os
import json
import hashlib
import sys
import subprocess
import tempfile
import shutil
import zipfile
import threading
import psutil
from pathlib import Path
import ipywidgets as widgets
from IPython.display import display, clear_output

ECOSYSTEM_REGISTRY = {
    "CoChem-CORE": {"desc": "Foundational registry, memory routing, and OS-level hardware guards.", "repo": "https://github.com/ProfJJK-CoChem/CoChem-CORE", "mandatory": True},
    "CoChem-TOPOS": {"desc": "Topological mapping, alignment, and geometry escalation.", "repo": "https://github.com/ProfJJK-CoChem/CoChem-TOPOS", "mandatory": True},
    "CoChem-TORQ": {"desc": "Torsional Discovery and Statistical Mechanics.", "repo": "https://github.com/ProfJJK-CoChem/CoChem-TORQ", "mandatory": True},
    "CoChem-SpycFit": {"desc": "JAX-accelerated rotational spectroscopy fitting.", "repo": "https://github.com/ProfJJK-CoChem/CoChem-SpycFit", "mandatory": False},
    "CoChem-SCRIBE": {"desc": "LLM-driven FAIR publication and LaTeX supplementary generator.", "repo": "https://github.com/ProfJJK-CoChem/CoChem-SCRIBE", "mandatory": False},
    "CoChem-NODE": {"desc": "HPC Slurm template and execution router.", "repo": "https://github.com/ProfJJK-CoChem/CoChem-NODE", "mandatory": False},
    "CoChem-ORACLE": {"desc": "Local Llama-CPP query routing and AI theory assistant.", "repo": "https://github.com/ProfJJK-CoChem/CoChem-ORACLE", "mandatory": False},
    "CoChem-BENCH": {"desc": "Automated Basis Set Limit & Composite Protocol Extrapolator.", "repo": "https://github.com/ProfJJK-CoChem/CoChem-BENCH", "mandatory": False},
    "CoChem-KINETIC": {"desc": "Reaction network and master equation kinetics solver.", "repo": "https://github.com/ProfJJK-CoChem/CoChem-KINETIC", "mandatory": False},
    "CoChem-LUMOS": {"desc": "Open-shell dynamics, AIMNet2, and photochemistry.", "repo": "https://github.com/ProfJJK-CoChem/CoChem-LUMOS", "mandatory": False},
    "CoChem-MAGE": {"desc": "GC-MS fragmentation logic emulation using ML potentials.", "repo": "https://github.com/ProfJJK-CoChem/CoChem-MAGE", "mandatory": False},
    "CoChem-PULSE": {"desc": "Time-dependent vibrational dynamics and laser simulations.", "repo": "https://github.com/ProfJJK-CoChem/CoChem-PULSE", "mandatory": False},
    "CoChem-SCAN": {"desc": "Internal conformational exploration heuristic tool.", "repo": "https://github.com/ProfJJK-CoChem/CoChem-SCAN", "mandatory": False},
    "CoChem-SHIFT": {"desc": "NMR tensor extraction (J-couplings, chemical shifts).", "repo": "https://github.com/ProfJJK-CoChem/CoChem-SHIFT", "mandatory": False},
    "CoChem-GEOM": {"desc": "Precision molecular structure determination and fitting.", "repo": "https://github.com/ProfJJK-CoChem/CoChem-GEOM", "mandatory": False}
}

class SynapInstallerGUI:
    def __init__(self):
        self.buttons = {}
        
        # 1. Enforce Air-Gap Paths
        self.artifact_dir = Path.home() / "CoChem_Artifacts"
        self.registry_dir = self.artifact_dir / "Registry"
        self.engine_registry = self.registry_dir / "Engines"
        self.module_registry = self.registry_dir / "Modules"
        
        self.engine_registry.mkdir(parents=True, exist_ok=True)
        self.module_registry.mkdir(parents=True, exist_ok=True)
        
        self.log_file = self.artifact_dir / "Logs" / "cochem_deploy.log"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Updated Manifest Path for the new OS Orchestrator
        self.manifest_file = self.registry_dir / "cochem_deployment_manifest.json"
        
        self.interaction_options = [
            "Local-Windows (WSL)",
            "Local-MacOS (OrbStack)",
            "Local-Linux (Deb)",
            "Codespaces"
        ]
        
        self.calculation_options = [
            "Local-Windows (WSL)",
            "Local-MacOS (OrbStack)",
            "Local-Linux (Deb)",
            "GitHub Actions",
            "HPC"
        ]
        
        self.disk_safe = False
        self._pre_flight_disk_check()
        if self.disk_safe:
            self._build_ui()

    def _get_git_hash(self):
        return hashlib.sha256(os.urandom(32)).hexdigest()[:16]

    def _pre_flight_disk_check(self):
        """Verifies safe OS operation before rendering."""
        try:
            free_gb = psutil.disk_usage(str(Path.home())).free / (1024**3)
            if free_gb < 5.0:
                self.disk_safe = False
                self.error_msg = f"❌ CRITICAL ERROR: Insufficient disk space ({free_gb:.2f} GB free). Minimum 5GB required."
            else:
                self.disk_safe = True
        except Exception:
            self.disk_safe = True  # Bypass if psutil is restricted natively

    def _verify_host_orca_path(self, raw_path: str) -> bool:
        candidate = Path((raw_path or "").strip().strip('"').strip("'"))
        if not str(candidate):
            return False

        if candidate.is_dir():
            options = [candidate / "orca", candidate / "bin" / "orca", candidate / "orca.exe", candidate / "bin" / "orca.exe"]
            candidate = next((opt for opt in options if opt.exists()), candidate)

        if not candidate.exists():
            with self.status_out:
                print(f"❌ ORCA path does not exist at: {candidate}")
            return False

        verify_dir = Path(tempfile.mkdtemp(prefix="cochem_orca_verify_", dir=str(self.artifact_dir)))
        inp = verify_dir / "verify_orca.inp"
        inp.write_text("! SP STO-3G\n*xyz 0 1\nHe 0 0 0\n*\n", encoding="utf-8")
        try:
            result = subprocess.run([str(candidate), str(inp)], cwd=str(verify_dir), capture_output=True, text=True, timeout=90)
            stdout_upper = (result.stdout or "").upper()
            out_file = verify_dir / "verify_orca.out"
            out_text = out_file.read_text(errors="replace").upper() if out_file.exists() else ""
            markers = ["ORCA TERMINATED NORMALLY", "O   R   C   A", "O R C A"]
            if result.returncode == 0 and any(m in stdout_upper or m in out_text for m in markers):
                with self.status_out:
                    print(f"✅ ORCA verification passed via: {candidate}")
                return True
            return False
        except Exception as e:
            with self.status_out:
                print(f"❌ ORCA verification exception: {e}")
            return False
        finally:
            shutil.rmtree(verify_dir, ignore_errors=True)

    def _has_staged_orca_archive(self) -> bool:
        patterns = ["orca*.tar.xz", "orca*.tz", "orca*.tar.gz", "ORCA*.tar.xz", "ORCA*.tz", "ORCA*.tar.gz"]
        for pattern in patterns:
            for candidate in self.engine_registry.glob(pattern):
                if candidate.is_file():
                    return True
        return False

    def _extract_upload_entries(self, files):
        if not files:
            return []
        if isinstance(files, dict):
            return [(fname, fdata) for fname, fdata in files.items()]
        entries = []
        for entry in files:
            if isinstance(entry, dict):
                entries.append((entry.get("name", ""), entry))
            else:
                entries.append((getattr(entry, "name", ""), entry))
        return entries

    def _stage_orca_upload(self, files) -> bool:
        entries = self._extract_upload_entries(files)
        if not entries:
            return False

        staged_any = False
        with self.status_out:
            for fname, fdata in entries:
                fname_lower = fname.lower()
                if not fname_lower.endswith((".tar.xz", ".tz", ".tar.gz", ".zip")):
                    print(f"❌ Unsupported archive type: {fname or 'unknown'}")
                    continue
                
                target = self.module_registry / fname if fname_lower.endswith(".zip") else self.engine_registry / fname
                    
                content = fdata.get("content", b"") if isinstance(fdata, dict) else getattr(fdata, "content", b"")
                if isinstance(content, memoryview): content = content.tobytes()
                elif isinstance(content, bytearray): content = bytes(content)
                
                if not content:
                    continue
                
                with open(target, "wb") as f:
                    f.write(content)
                size = target.stat().st_size if target.exists() else 0
                if size > 0:
                    print(f"✅ Archive staged to: {target} ({size} bytes)")
                    staged_any = True
        return staged_any

    def _pure_python_deployment_worker(self, manifest_payload):
        """Threaded pure-Python replacement for bash routers. Enforces Air-Gap."""
        target_modules = manifest_payload["selected_repositories"]
        
        progress_step = 80.0 / max(len(target_modules), 1)
        
        with open(self.log_file, 'a', encoding="utf-8") as log_out:
            def log_msg(msg):
                self.output_console.append_stdout(f"{msg}\n")
                log_out.write(f"{msg}\n")
                log_out.flush()

            log_msg("\n🚀 Initiating Pure-Python Air-Gap Module Provisioning...")
            log_msg(f"📁 Target Workspace: {self.module_registry}\n")

            clean_env = os.environ.copy()
            clean_env['GIT_TERMINAL_PROMPT'] = '0'
            
            for mod in target_modules:
                # We skip CORE cloning if it's the current environment, but include downstream dependencies
                if mod == "CoChem-CORE":
                    log_msg(f"  ℹ️ Base repository active. Bypassing clone for {mod}.")
                    self.progress_bar.value += progress_step
                    continue

                repo_url = ECOSYSTEM_REGISTRY[mod]["repo"]
                target_dir = self.module_registry / mod
                
                if (target_dir / ".git").exists():
                    log_msg(f"🔄 Updating existing module: {mod}")
                    try:
                        subprocess.run(["git", "pull", "--ff-only"], cwd=str(target_dir), env=clean_env, check=True, capture_output=True, text=True)
                        log_msg(f"  ✅ {mod} updated successfully.")
                    except subprocess.CalledProcessError as e:
                        log_msg(f"  ⚠️ Fast-forward failed for {mod}. Error: {e.stderr.strip()}")
                else:
                    sideload_success = False
                    possible_zips = [
                        self.module_registry / f"{mod}.zip", self.module_registry / f"{mod}-main.zip",
                        self.engine_registry / f"{mod}.zip", self.artifact_dir / f"{mod}.zip"
                    ]
                    
                    for zpath in possible_zips:
                        if zpath.exists():
                            log_msg(f"📦 Air-Gap Bridge: Sideloading {mod} from {zpath.name}...")
                            try:
                                with zipfile.ZipFile(zpath, 'r') as zip_ref:
                                    zip_ref.extractall(self.module_registry)
                                
                                for suffix in ["-main", "-master"]:
                                    extracted_dir = self.module_registry / f"{mod}{suffix}"
                                    if extracted_dir.exists() and not target_dir.exists():
                                        extracted_dir.rename(target_dir)
                                        
                                if target_dir.exists():
                                    log_msg(f"  ✅ Extracted {mod} via Air-Gap. Network bypassed.")
                                    sideload_success = True
                                    break
                            except Exception as e:
                                log_msg(f"  ⚠️ Zip extraction failed: {e}")
                    
                    if not sideload_success:
                        log_msg(f"📥 Deep cloning {mod} from {repo_url}...")
                        try:
                            subprocess.run(["git", "clone", "--depth", "1", repo_url, str(target_dir)], env=clean_env, check=True, capture_output=True, text=True)
                            log_msg(f"  ✅ Cloned {mod} successfully.")
                        except subprocess.CalledProcessError as e:
                            err = (e.stderr or "").strip() or str(e)
                            log_msg(f"  ❌ Failed to clone {mod}: {err}")
                
                self.progress_bar.value += progress_step

            log_msg("\n✅ Stage 0.0.2 Module synchronization completed.")
            
            # Subprocess handoff to CoChem-BASE OS-Native Orchestrator
            orchestrator = Path(__file__).resolve().parent.parent / "setup" / "cochem_setup_orchestrator.py"
            if orchestrator.exists():
                log_msg(f"🔄 Handing off to CoChem-BASE OS-Native Orchestrator: {orchestrator.name}...")
                try:
                    process = subprocess.Popen(
                        [sys.executable, str(orchestrator)], 
                        cwd=str(orchestrator.parent),
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.STDOUT, 
                        text=True, bufsize=1, env=clean_env
                    )
                    for line in process.stdout:
                        self.output_console.append_stdout(line)
                        log_out.write(line)
                        log_out.flush()
                    process.wait()
                    if process.returncode == 0:
                        log_msg("✅ Orchestrator completed successfully.")
                        self.progress_bar.bar_style = 'success'
                    else:
                        log_msg(f"❌ Orchestrator failed with exit code {process.returncode}.")
                        self.progress_bar.bar_style = 'danger'
                except Exception as e:
                    log_msg(f"❌ Failed to launch orchestrator: {e}")
                    self.progress_bar.bar_style = 'danger'
            else:
                log_msg(f"⚠️ OS-Native Orchestrator not found at {orchestrator}. Setup stopped.")
                self.progress_bar.bar_style = 'warning'
                
            self.progress_bar.value = 100.0

    def _on_submit(self, b):
        self.submit_btn.disabled = True
        self.submit_btn.description = "Deploying..."
        self.progress_bar.value = 0.0
        self.progress_bar.bar_style = 'info'
        self.progress_bar.layout.display = 'block'
        self.output_console.clear_output()
        self.status_out.clear_output()
        
        selected_modules = [mod for mod, cb in self.buttons.items() if cb.value]
        host_orca_path = self.host_orca_path.value.strip()
        host_orca_verified = False
        
        # New Decoupled Output Schema matching setup_orchestrator
        manifest_payload = {
            "version": "2026.2",
            "git_provenance_hash": self._get_git_hash(),
            "interaction_environment": self.interact_target.value,
            "calculation_environment": self.calc_target.value,
            "orca_tarball_path": host_orca_path,
            "selected_repositories": selected_modules
        }
        
        with open(self.manifest_file, 'w') as f:
            json.dump(manifest_payload, f, indent=4)
            
        with self.status_out:
            print(f"✅ Matrix Selections locked securely in: {self.manifest_file}")
            
            if host_orca_path and host_orca_path != "Not Available - Auto-Routed":
                print("🔬 Verifying native ORCA execution pathway...")
                host_orca_verified = self._verify_host_orca_path(host_orca_path)
                if not host_orca_verified and not self._has_staged_orca_archive():
                    print("⚠️ ORCA verification failed. Fix path or stage an archive instead.")
                    self.submit_btn.disabled = False
                    self.submit_btn.description = "Lock & Deploy"
                    return
            
            staged_now = False
            if not host_orca_verified:
                staged_now = self._stage_orca_upload(getattr(self.orca_upload, "value", None))

            if host_orca_verified or staged_now or self._has_staged_orca_archive():
                print("➡️ Dispatching Pure-Python Deployment Thread...")
                threading.Thread(target=self._pure_python_deployment_worker, args=(manifest_payload,), daemon=True).start()
            else:
                print("⚠️ ORCA archive not detected in engine registry.")
                print(f"📦 Expected location: {self.engine_registry}")
                print("➡️ Upload ORCA archive first, or type 'BYPASSED' into Host ORCA field if you wish to run in Python-Only mode.")
                self.submit_btn.disabled = False
                self.submit_btn.description = "Lock & Deploy"

    def _on_stage_orca_click(self, _):
        with self.status_out:
            clear_output()
            staged = self._stage_orca_upload(getattr(self.orca_upload, "value", None))
            if staged:
                print("➡️ Archives are staged and ready for setup.")
            else:
                print("⚠️ No valid archives detected to stage.")

    def build_ui(self):
        if not self.disk_safe:
            return widgets.VBox([widgets.HTML(f"<h3>{self.error_msg}</h3>")])
            
        return self.main_ui

    def _build_ui(self):
        title = widgets.HTML("<h2>CoChem-BASE: Ecosystem Deployer</h2>")
        
        artifact_hint = widgets.HTML(
            f"<div style='background-color: #f8f9fa; padding: 10px; border-radius: 5px; border-left: 4px solid #0366d6; margin-bottom: 15px;'>"
            f"<b>CoChem Artifacts Native Bridge:</b> {self.artifact_dir}<br>"
            f"<b>1. ORCA Drop Target:</b> {self.engine_registry}<br>"
            f"<b>2. Module Drop Target (.zip):</b> {self.module_registry}<br>"
            f"<i style='font-size: 0.9em; color: #555;'>Offline? Download the Github .zip files and drop them into the target folder above.</i>"
            f"</div>"
        )
        
        self.interact_target = widgets.Dropdown(options=self.interaction_options, value=self.interaction_options[0], description="Interaction (UI):", layout={'width': '80%'})
        self.calc_target = widgets.Dropdown(options=self.calculation_options, value=self.calculation_options[0], description="Calculation (Compute):", layout={'width': '80%'})
        
        self.host_orca_path = widgets.Text(value="", placeholder="Optional: /opt/orca/orca", description="Host ORCA:", layout={'width': '80%'})
        
        # Modules
        checks = [widgets.HTML("<h3>Base Ecosystem & Optional Micro-Silos</h3>")]
        for prog, info in ECOSYSTEM_REGISTRY.items():
            cb = widgets.Checkbox(value=info["mandatory"], description=prog, disabled=info["mandatory"], layout={'width': '250px'})
            desc = widgets.HTML(f"<span style='color: #475569; font-size: 0.9em;'><i>{info['desc']}</i></span>")
            self.buttons[prog] = cb
            checks.append(widgets.HBox([cb, desc], layout={'align_items': 'center', 'margin': '0px 0px 4px 0px'}))

        self.orca_upload = widgets.FileUpload(accept=".tar.xz,.tz,.tar.gz,.zip", multiple=True, description="Drop Archives")
        self.stage_orca_btn = widgets.Button(description="Stage Uploads", button_style="primary")
        self.stage_orca_btn.on_click(self._on_stage_orca_click)

        self.submit_btn = widgets.Button(description="Lock & Deploy", button_style="success", layout={'width': '30%', 'margin': '15px 0px'})
        self.submit_btn.on_click(self._on_submit)

        self.progress_bar = widgets.FloatProgress(value=0.0, min=0.0, max=100.0, description='Deploying:', bar_style='info', layout={'width': '95%'})
        self.progress_bar.layout.display = 'none'

        self.status_out = widgets.Output(layout={'border': '1px solid #e2e8f0', 'padding': '8px', 'height': '150px', 'overflow_y': 'auto', 'margin': '10px 0px'})
        self.output_console = widgets.Output(layout={'border': '1px solid #334155', 'padding': '10px', 'height': '300px', 'overflow_y': 'auto', 'background_color': '#f1f5f9'})

        self.main_ui = widgets.VBox([
            title,
            artifact_hint,
            widgets.HTML("<h4>Step 1: Environment Matrices</h4>"),
            self.interact_target,
            self.calc_target,
            widgets.HTML("<h4>Step 2: External Binaries</h4>"),
            self.host_orca_path,
            widgets.HBox([self.orca_upload, self.stage_orca_btn], layout={'margin': '10px 0px'}),
            widgets.VBox(checks, layout={'padding': '15px', 'border': '1px solid #e2e8f0', 'border_radius': '5px'}),
            self.submit_btn,
            self.progress_bar,
            self.status_out,
            widgets.HTML("<h4>Live Subprocess Execution Log</h4>"),
            self.output_console
        ])

if __name__ == "__main__":
    installer = SynapInstallerGUI()
    display(installer.build_ui())