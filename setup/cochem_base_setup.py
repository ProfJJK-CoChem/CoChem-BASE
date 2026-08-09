#!/usr/bin/env python3
"""
CoChem-BASE Setup Script
This script handles the environment setup and detection logic for CoChem-BASE.
"""

import ipywidgets as widgets
import json
from pathlib import Path
from IPython.display import display, HTML

def setup_cochem_base():
    """Main setup function for CoChem-BASE environment"""
    
    print("=======================================================")
    print(" ⚙️ CoChem-BASE: Artifact & Silo Registry Configuration")
    print("=======================================================\n")

    # Check if a previous configuration exists
    cfg_path = Path.cwd() / ".cochem_env.json"
    previous_path = None
    if cfg_path.exists():
        try:
            with open(cfg_path, "r") as f:
                config = json.load(f)
                if "artifact_dir" in config:
                    previous_path = config["artifact_dir"]
        except Exception:
            pass

    # Set up widgets
    if previous_path:
        path_input = widgets.Text(
            value=previous_path,
            placeholder="Enter absolute path",
            description="Storage Path:",
            layout=widgets.Layout(width="80%")
        )
        keep_btn = widgets.Button(description="Keep Previous Path", button_style="info", layout=widgets.Layout(width="150px"))
        set_btn = widgets.Button(description="Set New Path & Build Silo", button_style="success", layout=widgets.Layout(width="200px"))
        
        # Create output widget for displaying messages
        output = widgets.Output()
        
        def on_keep_click(b):
            # Use the previous path and check if environment exists
            path_input.value = previous_path
            set_btn.disabled = True
            keep_btn.disabled = True
            set_btn.description = "Checking Silo..."
            
            with output:
                output.clear_output()
                cfg = {"artifact_dir": path_input.value}
                with open(cfg_path, "w") as f:
                    json.dump(cfg, f)
                print(f"✅ Saved Artifact registry path to: {cfg_path}")
                print(f"⚙️ Target Artifact Director: {path_input.value}\n")
                
                # Check if the environment already exists
                env_dir = Path(path_input.value) / "Silos" / "cochem_base_silo"
                
                # More robust check - verify conda environment actually exists and is valid
                env_exists = False
                try:
                    import subprocess
                    result = subprocess.run(["conda", "info", "--envs"], check=True, capture_output=True, text=True)
                    # Check if our environment path is in the conda environments list
                    if str(env_dir) in result.stdout:
                        # Additional verification: make sure it's actually a valid conda environment
                        # by checking for conda-meta directory or other conda artifacts
                        conda_meta_path = env_dir / "conda-meta"
                        if conda_meta_path.exists():
                            env_exists = True
                        else:
                            print(f"⚠️ Environment path found but conda-meta directory missing: {conda_meta_path}")
                            # If we can't find conda-meta, it might be a directory from old setup or broken installation
                            # In this case, we'll proceed with recreation to be safe
                            env_exists = False
                    else:
                        # Also check if the directory exists (fallback method)
                        env_exists = env_dir.exists()
                except Exception as e:
                    # If conda command fails or environment not found, fall back to filesystem check
                    print(f"⚠️ Conda check failed, falling back to directory check: {e}")
                    # Even with fallback, we should be more careful - if directory exists but no conda-meta,
                    # it's likely an invalid environment that needs recreation
                    if env_dir.exists():
                        conda_meta_path = env_dir / "conda-meta"
                        if conda_meta_path.exists():
                            env_exists = True
                        else:
                            print(f"⚠️ Directory exists but conda-meta missing - treating as invalid environment")
                            env_exists = False
                    else:
                        env_exists = False
                
                if env_exists:
                    print("✅ Conda environment detected at:", env_dir)
                    print("   Skipping full setup - using existing environment")
                    
                    # Show success message with kernel selection
                    html_str = """
                        <div style="padding: 10px; background-color: #d4edda; border: 1px solid #c3e6cb; border-radius: 5px; color: #155724; margin-top: 15px;">
                            <b>✅ Conda Silo Already Provisioned!</b><br><br>
                            Using existing environment at: {env_dir}<br><br>
                            Please click the secure link below to trigger the VS Code Kernel Selector. <br>
                            Select the <b>cochem_base_silo</b> environment, wait 2 seconds for it to attach, and then execute the UI Matrix block below.<br><br>
                            <a href="command:notebook.selectKernel" style="font-size: 16px; font-weight: bold; padding: 5px 10px; background-color: #155724; color: white; text-decoration: none; border-radius: 3px;">🔄 Select cochem_base_silo Kernel</a>
                        </div>
                    """.format(env_dir=env_dir)
                    output.append_display_data(HTML(html_str))
                else:
                    print("▶️ Handing off to Silo creation agent...\n")
                    
                    log_output = widgets.Textarea(value='', disabled=True, layout=widgets.Layout(height='250px', width='100%'))
                    display(log_output)
                    
                    def run_silo():
                        import subprocess
                        import sys
                        try:
                            proc = subprocess.Popen(
                                [sys.executable, "setup/cochem_base_silo_setup.py"], 
                                stdout=subprocess.PIPE, 
                                stderr=subprocess.STDOUT, 
                                text=True, 
                                encoding="utf-8",
                                bufsize=1
                            )
                            for line in iter(proc.stdout.readline, ''):
                                log_output.value += line
                            proc.wait()
                            if proc.returncode == 0:
                                html_str = """
                                    <div style="padding: 10px; background-color: #d4edda; border: 1px solid #c3e6cb; border-radius: 5px; color: #155724; margin-top: 15px;">
                                        <b>✅ Conda Silo Provisioned!</b><br><br>
                                        Please click the secure link below to trigger the VS Code Kernel Selector. <br>
                                        Select the newly created <b>cochem_base_silo</b> environment, wait 2 seconds for it to attach, and then execute the UI Matrix block below.<br><br>
                                        <a href="command:notebook.selectKernel" style="font-size: 16px; font-weight: bold; padding: 5px 10px; background-color: #155724; color: white; text-decoration: none; border-radius: 3px;">🔄 Select cochem_base_silo Kernel</a>
                                    </div>
                                """
                                output.append_display_data(HTML(html_str))
                            else:
                                log_output.value += f"\n❌ Silo build failed with code {proc.returncode}\n"
                        except Exception as e:
                            log_output.value += f"Error launching script: {e}\n"
                        finally:
                            set_btn.disabled = False
                            keep_btn.disabled = False
                            set_btn.description = "Set New Path & Build Silo"
                            
                    import threading
                    threading.Thread(target=run_silo, daemon=True).start()
            
        def on_set_click(b):
            set_btn.disabled = True
            keep_btn.disabled = True
            set_btn.description = "Checking Silo..."
            with output:
                output.clear_output()
                cfg = {"artifact_dir": path_input.value}
                with open(cfg_path, "w") as f:
                    json.dump(cfg, f)
                print(f"✅ Saved Artifact registry path to: {cfg_path}")
                print(f"⚙️ Target Artifact Director: {path_input.value}\n")
                
                # Check if the environment already exists
                env_dir = Path(path_input.value) / "Silos" / "cochem_base_silo"
                
                # More robust check - verify conda environment actually exists and is valid
                env_exists = False
                try:
                    import subprocess
                    result = subprocess.run(["conda", "info", "--envs"], check=True, capture_output=True, text=True)
                    # Check if our environment path is in the conda environments list
                    if str(env_dir) in result.stdout:
                        # Additional verification: make sure it's actually a valid conda environment
                        # by checking for conda-meta directory or other conda artifacts
                        conda_meta_path = env_dir / "conda-meta"
                        if conda_meta_path.exists():
                            env_exists = True
                        else:
                            print(f"⚠️ Environment path found but conda-meta directory missing: {conda_meta_path}")
                            # If we can't find conda-meta, it might be a directory from old setup or broken installation
                            # In this case, we'll proceed with recreation to be safe
                            env_exists = False
                    else:
                        # Also check if the directory exists (fallback method)
                        env_exists = env_dir.exists()
                except Exception as e:
                    # If conda command fails or environment not found, fall back to filesystem check
                    print(f"⚠️ Conda check failed, falling back to directory check: {e}")
                    # Even with fallback, we should be more careful - if directory exists but no conda-meta,
                    # it's likely an invalid environment that needs recreation
                    if env_dir.exists():
                        conda_meta_path = env_dir / "conda-meta"
                        if conda_meta_path.exists():
                            env_exists = True
                        else:
                            print(f"⚠️ Directory exists but conda-meta missing - treating as invalid environment")
                            env_exists = False
                    else:
                        env_exists = False
                
                if env_exists:
                    print("✅ Conda environment detected at:", env_dir)
                    print("   Skipping full setup - using existing environment")
                    
                    # Show success message with kernel selection
                    html_str = """
                        <div style="padding: 10px; background-color: #d4edda; border: 1px solid #c3e6cb; border-radius: 5px; color: #155724; margin-top: 15px;">
                            <b>✅ Conda Silo Already Provisioned!</b><br><br>
                            Using existing environment at: {env_dir}<br><br>
                            Please click the secure link below to trigger the VS Code Kernel Selector. <br>
                            Select the <b>cochem_base_silo</b> environment, wait 2 seconds for it to attach, and then execute the UI Matrix block below.<br><br>
                            <a href="command:notebook.selectKernel" style="font-size: 16px; font-weight: bold; padding: 5px 10px; background-color: #155724; color: white; text-decoration: none; border-radius: 3px;">🔄 Select cochem_base_silo Kernel</a>
                        </div>
                    """.format(env_dir=env_dir)
                    output.append_display_data(HTML(html_str))
                else:
                    print("▶️ Handing off to Silo creation agent...\n")
                    
                    log_output = widgets.Textarea(value='', disabled=True, layout=widgets.Layout(height='250px', width='100%'))
                    display(log_output)
                    
                    def run_silo():
                        import subprocess
                        import sys
                        try:
                            proc = subprocess.Popen(
                                [sys.executable, "setup/cochem_base_silo_setup.py"], 
                                stdout=subprocess.PIPE, 
                                stderr=subprocess.STDOUT, 
                                text=True, 
                                encoding="utf-8",
                                bufsize=1
                            )
                            for line in iter(proc.stdout.readline, ''):
                                log_output.value += line
                            proc.wait()
                            if proc.returncode == 0:
                                html_str = """
                                    <div style="padding: 10px; background-color: #d4edda; border: 1px solid #c3e6cb; border-radius: 5px; color: #155724; margin-top: 15px;">
                                        <b>✅ Conda Silo Provisioned!</b><br><br>
                                        Please click the secure link below to trigger the VS Code Kernel Selector. <br>
                                        Select the newly created <b>cochem_base_silo</b> environment, wait 2 seconds for it to attach, and then execute the UI Matrix block below.<br><br>
                                        <a href="command:notebook.selectKernel" style="font-size: 16px; font-weight: bold; padding: 5px 10px; background-color: #155724; color: white; text-decoration: none; border-radius: 3px;">🔄 Select cochem_base_silo Kernel</a>
                                    </div>
                                """
                                output.append_display_data(HTML(html_str))
                            else:
                                log_output.value += f"\n❌ Silo build failed with code {proc.returncode}\n"
                        except Exception as e:
                            log_output.value += f"Error launching script: {e}\n"
                        finally:
                            set_btn.disabled = False
                            keep_btn.disabled = False
                            set_btn.description = "Set New Path & Build Silo"
                            
                    import threading
                    threading.Thread(target=run_silo, daemon=True).start()

        # Create layout with both buttons
        keep_btn.on_click(on_keep_click)
        set_btn.on_click(on_set_click)
        
        display(widgets.VBox([
            widgets.HBox([path_input, keep_btn, set_btn]),
            output
        ]))
        
        print(f"ℹ️ Previous configuration detected: {previous_path}")
        print("   Click 'Keep Previous Path' to use the existing setup")
        print("   Or modify the path and click 'Set New Path & Build Silo'")
    else:
        path_input = widgets.Text(
            value=str(Path.home() / "CoChem_Artifacts"),
            placeholder="Enter absolute path",
            description="Storage Path:",
            layout=widgets.Layout(width="80%")
        )
        set_btn = widgets.Button(description="Set Path & Build Silo", button_style="success", layout=widgets.Layout(width="200px"))
        output = widgets.Output()

        def on_click(b):
            set_btn.disabled = True
            set_btn.description = "Building Silo..."
            with output:
                output.clear_output()
                cfg = {"artifact_dir": path_input.value}
                cfg_path = Path.cwd() / ".cochem_env.json"
                with open(cfg_path, "w") as f:
                    json.dump(cfg, f)
                print(f"✅ Saved Artifact registry path to: {cfg_path}")
                print(f"⚙️ Target Artifact Director: {path_input.value}\n")
                print("▶️ Handing off to Silo creation agent...\n")
                
                log_output = widgets.Textarea(value='', disabled=True, layout=widgets.Layout(height='250px', width='100%'))
                display(log_output)
                
                def run_silo():
                    import subprocess
                    import sys
                    try:
                        proc = subprocess.Popen(
                            [sys.executable, "setup/cochem_base_silo_setup.py"], 
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.STDOUT, 
                            text=True, 
                            encoding="utf-8",
                            bufsize=1
                        )
                        for line in iter(proc.stdout.readline, ''):
                            log_output.value += line
                        proc.wait()
                        if proc.returncode == 0:
                            html_str = """
                                <div style="padding: 10px; background-color: #d4edda; border: 1px solid #c3e6cb; border-radius: 5px; color: #155724; margin-top: 15px;">
                                    <b>✅ Conda Silo Provisioned!</b><br><br>
                                    Please click the secure link below to trigger the VS Code Kernel Selector. <br>
                                    Select the newly created <b>cochem_base_silo</b> environment, wait 2 seconds for it to attach, and then execute the UI Matrix block below.<br><br>
                                    <a href="command:notebook.selectKernel" style="font-size: 16px; font-weight: bold; padding: 5px 10px; background-color: #155724; color: white; text-decoration: none; border-radius: 3px;">🔄 Select cochem_base_silo Kernel</a>
                                </div>
                            """
                            output.append_display_data(HTML(html_str))
                        else:
                            log_output.value += f"\n❌ Silo build failed with code {proc.returncode}\n"
                    except Exception as e:
                        log_output.value += f"Error launching script: {e}\n"
                    finally:
                        set_btn.disabled = False
                        set_btn.description = "Set Path & Build Silo"
                        
                import threading
                threading.Thread(target=run_silo, daemon=True).start()

        set_btn.on_click(on_click)
        display(widgets.VBox([widgets.HBox([path_input, set_btn]), output]))

if __name__ == "__main__":
    setup_cochem_base()