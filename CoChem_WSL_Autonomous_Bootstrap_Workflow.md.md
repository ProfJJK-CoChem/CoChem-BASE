**Template C — Workflow**  
**Workflow goal**  
To engineer an autonomous, cross-boundary bootstrap sequence for Windows users. We will upgrade interact\_wsl.py into a "Dual-OS Bridge" that detects native Windows execution, checks for WSL2/Ubuntu, and autonomously triggers the Windows installation process if missing. Concurrently, we will upgrade calc\_wsl.py to feature an "Active Repair" architecture that automatically downloads and installs OpenMPI within the Linux subsystem if it is not found, dynamically binding the paths for downstream ORCA execution.  
**Stage map**

* **Stage \-0.1:** Windows Host Pre-Flight & WSL2 Bootstrapper (Update to setup/interact\_wsl.py)  
* **Stage 0.1a:** WSL Interaction Provisioning & UI Dependency (Update to setup/interact\_wsl.py)  
* **Stage 0.1b:** Autonomous OpenMPI Installer & Path Binder (Update to setup/calc\_wsl.py)

**Detailed stage segments**  
**Stage \-0.1 — Windows Host Pre-Flight & WSL2 Bootstrapper**

* **Purpose:** To intercept users who accidentally (or necessarily) run the setup on native Windows instead of inside WSL, and autonomously provision the required Microsoft WSL2 Ubuntu infrastructure.  
* **Inputs:** OS platform check (sys.platform \== "win32").  
* **Outputs:** Invocation of wsl \--install \-d Ubuntu via PowerShell.  
* **Files created or modified:** Modifies setup/interact\_wsl.py.  
* **Key dependencies:** Windows subprocess, ctypes (for UAC Admin elevation).  
* **Key scientific or logic checks:**  
  * Probes for wsl.exe in the Windows System32 path.  
  * Detects if the script has Administrator privileges (required to install WSL features).  
* **Failure risks:** Installing WSL2 natively requires a system reboot. The script will be forcibly interrupted by the OS.  
* **Suggested validation tests:** Execute on a fresh Windows VM without WSL installed. Ensure it triggers the UAC Admin prompt, executes the install, and halts with clear instructions to reboot and re-run.  
* **Estimated coding size risk:** Medium.  
* **Context safety note:** We must implement this as a graceful halt. Attempting to programmatically write Windows Registry RunOnce keys to auto-resume the script after a reboot violates the "non-hacky" prime directive and risks corrupting the user's OS.

**Stage 0.1a — WSL Interaction Provisioning & UI Dependency**

* **Purpose:** To resume the original Interaction provisioning (installing Jupyter, creating Air-Gap directories) once the user is successfully inside the WSL kernel.  
* **Inputs:** /proc/version confirming Microsoft WSL.  
* **Outputs:** Air-gap directories, pip UI dependencies, and updated cochem\_system\_config.json.  
* **Files created or modified:** Modifies setup/interact\_wsl.py.  
* **Key dependencies:** psutil, pip.  
* **Key scientific or logic checks:** Explicitly routes the pip commands to the active Linux kernel, completely bypassing Windows path collisions.  
* **Failure risks:** Pip failure due to missing Python venv or python3-pip packages in a completely fresh Ubuntu install.  
* **Suggested validation tests:** Run within the newly installed WSL Ubuntu terminal to verify the Air-Gap workspace appears in the Linux \~ (home) directory, not the Windows C:\\ drive.  
* **Estimated coding size risk:** Low.  
* **Context safety note:** Merges seamlessly with the existing Stage 0.1a logic we already wrote, simply sitting behind the new Stage \-0.1 OS gatekeeper.

**Stage 0.1b — Autonomous OpenMPI Installer & Path Binder**

* **Purpose:** To upgrade the Calculation environment setup with "Active Repair." If mpirun is missing, the script will autonomously execute the package manager to install OpenMPI 4.1.x and lock the paths.  
* **Inputs:** shutil.which("mpirun") returns None.  
* **Outputs:** Installation of OpenMPI via apt-get (or conda if available), updating cochem\_system\_config.json with the new absolute path.  
* **Files created or modified:** Modifies setup/calc\_wsl.py.  
* **Key dependencies:** subprocess targeting the apt package manager.  
* **Key scientific or logic checks:**  
  * Must verify the installed OpenMPI version is exactly 4.1.x, as ORCA 6.1.1 is strictly compiled against this version and will segfault on OpenMPI 3.x or 5.x.  
* **Failure risks:** sudo apt-get requires the user's password. The script must gracefully prompt the user for their Linux password in the terminal without hanging silently in the background.  
* **Suggested validation tests:** Uninstall OpenMPI (sudo apt remove openmpi-bin), run the script, and verify it interactively requests permission to reinstall it, subsequently updating the Golden Registry correctly.  
* **Estimated coding size risk:** Medium.  
* **Context safety note:** By utilizing subprocess with stdout=None (allowing terminal passthrough), we can safely let Ubuntu handle the sudo password prompt natively without building insecure password-scraping logic.

**Context risk points**

* Attempting to bridge Windows execution, a mandatory Windows reboot, and a subsequent Linux execution in a single seamless Python thread is impossible. The workflow *must* pause, request a reboot, and explicitly tell the user to open the WSL Ubuntu terminal for the next step.

**Save-point recommendation for external reference**  
Save this mapping as CoChem\_WSL\_Autonomous\_Bootstrap\_Workflow.md. It formally documents the UAC elevation and active repair protocols necessary for bare-metal Windows setups.  
Do you authorize proceeding to **Coding Mode** to refactor setup/interact\_wsl.py (combining Stage \-0.1 and 0.1a), introducing the Windows-native UAC elevation and WSL2 bootstrapper?