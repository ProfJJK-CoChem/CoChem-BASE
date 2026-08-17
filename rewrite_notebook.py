#!/usr/bin/env python3
"""
CoChem-BASE: Notebook Generator and Updater.
Updates Start_Here.ipynb with dynamic configuration and safe environment pathing.
"""

import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

base_dir = Path(__file__).resolve().parent
notebook_path = base_dir / "Start_Here.ipynb"

if notebook_path.exists():
    with open(notebook_path, 'r', encoding='utf-8') as f:
        nb = json.loads(f.read())

    markdown_cell_2_source = [
        "## 💾 Silo Setup & Artifact Registry Configuration\n",
        "\n",
        "**Purpose:**\n",
        "To establish a dedicated, reproducible computational environment (Silo) and configure a persistent local directory for storing generated chemistry artifacts.\n",
        "\n",
        "**Instructions:**\n",
        "- Run the code cell below by clicking it and pressing `Shift + Enter`.\n",
        "- Select **New Install** to configure a fresh Silo, or **Keep previous setup** to validate an existing one.\n",
        "- Enter an artifact directory, or leave the default `CoChem_Artifacts` directory in your user home.\n",
        "- Optionally map a Conda, Mamba, or Micromamba executable. A command already available on `PATH` also works.\n",
        "- Click **Create & Provision** to build the Silo.\n",
        "- If the build succeeds, select the new `cochem_base_silo` kernel using the kernel selector.\n",
        "\n",
        "**Didactic Breakdown:**\n",
        "In computational chemistry and chemoinformatics, exact software environments are critical. Slight dependency differences can produce irreproducible energies, broken trajectory visualization, or incompatible quantum-mechanical properties.\n",
        "\n",
        "This setup resolves repository, artifact, and environment-manager paths dynamically. The isolated `cochem_base_silo` therefore remains reproducible when the checkout is moved between Windows, macOS, Linux, Codespaces, and mapped storage locations.\n",
    ]

    code_cell_1_source = [
        "import importlib\n",
        "import ipywidgets as widgets\n",
        "from IPython.display import display, clear_output\n",
        "import os\n",
        "import shutil\n",
        "import sys\n",
        "from pathlib import Path\n",
        "\n",
        "def resolve_base_root():\n",
        "    mapped_root = os.environ.get('COCHEM_BASE_ROOT')\n",
        "    if mapped_root:\n",
        "        root = Path(os.path.expandvars(mapped_root)).expanduser().resolve()\n",
        "        if (root / 'setup' / 'cochem_base_setup.py').is_file():\n",
        "            return root\n",
        "        raise RuntimeError(f'COCHEM_BASE_ROOT does not contain CoChem-BASE: {root}')\n",
        "    for candidate in (Path.cwd(), *Path.cwd().parents):\n",
        "        for root in (candidate, candidate / 'CoChem-BASE'):\n",
        "            if (root / 'setup' / 'cochem_base_setup.py').is_file():\n",
        "                return root.resolve()\n",
        "    raise RuntimeError('Unable to locate CoChem-BASE. Set COCHEM_BASE_ROOT to this checkout.')\n",
        "\n",
        "def resolve_artifact_path(value):\n",
        "    path = Path(os.path.expandvars(value)).expanduser()\n",
        "    if not path.is_absolute():\n",
        "        path = Path.home() / path\n",
        "    return path.resolve()\n",
        "\n",
        "BASE_ROOT = resolve_base_root()\n",
        "if str(BASE_ROOT) not in sys.path:\n",
        "    sys.path.insert(0, str(BASE_ROOT))\n",
        "os.environ['COCHEM_BASE_ROOT'] = str(BASE_ROOT)\n",
        "for module_name in tuple(sys.modules):\n",
        "    if module_name in {'cochem_base', 'core_engine', 'setup'} or module_name.startswith(('cochem_base.', 'core_engine.', 'setup.')):\n",
        "        sys.modules.pop(module_name, None)\n",
        "import cochem_base.config_loader as config_loader\n",
        "config_loader = importlib.reload(config_loader)\n",
        "resolve_conda_executable = config_loader.resolve_conda_executable\n",
        "\n",
        "# 1) Detect if this setup stage has been completed.\n",
        "keep_btn = widgets.Button(description=\"Keep previous setup\", button_style=\"info\")\n",
        "new_btn = widgets.Button(description=\"New Install\", button_style=\"warning\")\n",
        "out = widgets.Output()\n",
        "\n",
        "def on_keep(b):\n",
        "    with out:\n",
        "        clear_output()\n",
        "        print(\"Testing previous setup...\")\n",
        "        try:\n",
        "            from test_suite.test_environment import check_cochem_base_silo, check_artifacts_dir\n",
        "            silo_ok, silo_msg = check_cochem_base_silo()\n",
        "            art_ok, art_msg = check_artifacts_dir()\n",
        "            print(silo_msg)\n",
        "            print(art_msg)\n",
        "            if silo_ok and art_ok:\n",
        "                print(\"✅ Everything is ready for the next step!\")\n",
        "            else:\n",
        "                print(\"❌ Environment validation failed. Please run a New Install.\")\n",
        "        except Exception as e:\n",
        "            print(f\"❌ Error: {e}. Please run a New Install.\")\n",
        "\n",
        "def on_new(b):\n",
        "    with out:\n",
        "        clear_output()\n",
        "        default_art = resolve_artifact_path(os.environ.get('COCHEM_ARTIFACT_DIR', 'CoChem_Artifacts'))\n",
        "        path_input = widgets.Text(\n",
        "            value=str(default_art),\n",
        "            description='Artifacts Path:',\n",
        "            style={'description_width': 'initial'}\n",
        "        )\n",
        "        conda_path_input = widgets.Text(\n",
        "            value=os.environ.get('COCHEM_CONDA_EXE', resolve_conda_executable(required=False)),\n",
        "            description='Conda/Mamba:',\n",
        "            style={'description_width': 'initial'}\n",
        "        )\n",
        "        submit_btn = widgets.Button(description=\"Create & Provision\", button_style=\"success\")\n",
        "        \n",
        "        def on_submit(b2):\n",
        "            with out:\n",
        "                clear_output()\n",
        "                target_path = resolve_artifact_path(path_input.value)\n",
        "                silo_path = target_path / 'Silos'\n",
        "                if silo_path.exists():\n",
        "                    print(f\"Deleting previous Silos directory at {silo_path}...\")\n",
        "                    shutil.rmtree(silo_path, ignore_errors=True)\n",
        "                silo_path.mkdir(parents=True, exist_ok=True)\n",
        "                print(f\"Created CoChem_Artifacts/Silos at {silo_path}\")\n",
        "                print(\"Setting up minimum environment...\")\n",
        "                os.environ['COCHEM_ARTIFACT_DIR'] = str(target_path)\n",
        "                if conda_path_input.value.strip():\n",
        "                    os.environ['COCHEM_CONDA_EXE'] = conda_path_input.value.strip()\n",
        "                try:\n",
        "                    from setup.cochem_base_setup import setup_cochem_base\n",
        "                    setup_cochem_base()\n",
        "                    print(\"✅ New installation completed and ready for the next step!\")\n",
        "                except Exception as e:\n",
        "                    print(f\"Error during setup: {e}\")\n",
        "                    raise ValueError(f\"CRITICAL: Provisioning failed. Exception Deflection blocked.\") from e\n",
        "\n",
        "        submit_btn.on_click(on_submit)\n",
        "        display(path_input, conda_path_input, submit_btn)\n",
        "\n",
        "keep_btn.on_click(on_keep)\n",
        "new_btn.on_click(on_new)\n",
        "\n",
        "display(widgets.HBox([keep_btn, new_btn]), out)\n"
    ]

    code_cell_2_source = [
        "import importlib\n",
        "import ipywidgets as widgets\n",
        "from IPython.display import display, clear_output\n",
        "import os\n",
        "import platform\n",
        "import cochem_base.config_loader as config_loader\n",
        "\n",
        "config_loader = importlib.reload(config_loader)\n",
        "get_modules_dir = config_loader.get_modules_dir\n",
        "resolve_executable = config_loader.resolve_executable\n",
        "\n",
        "def resolve_tool_paths(orca_value=None, mpi_value=None):\n",
        "    orca_path = resolve_executable(orca_value, env_var='ORCA_CMD', candidates=('orca',))\n",
        "    mpi_path = resolve_executable(mpi_value, env_var='MPI_CMD', candidates=('mpirun', 'mpiexec'))\n",
        "    return orca_path, mpi_path\n",
        "\n",
        "host_target = {\n",
        "    'Windows': 'Local-Windows (WSL)',\n",
        "    'Darwin': 'Local-MacOS (OrbStack)',\n",
        "    'Linux': 'Local-Linux (Deb)',\n",
        "}.get(platform.system(), 'Codespaces')\n",
        "if os.environ.get('CODESPACES'):\n",
        "    host_target = 'Codespaces'\n",
        "\n",
        "# 0) Check if this step has already been completed and passed validation.\n",
        "keep_env_btn = widgets.Button(description=\"Keep previous setup\", button_style=\"info\")\n",
        "new_env_btn = widgets.Button(description=\"New Install\", button_style=\"warning\")\n",
        "env_out = widgets.Output()\n",
        "\n",
        "def on_keep_env(b):\n",
        "    with env_out:\n",
        "        clear_output()\n",
        "        print(\"Testing existing module and ORCA setup...\")\n",
        "        try:\n",
        "            from test_suite.run_tests import run_all_preflight_checks\n",
        "            orca_path, mpi_path = resolve_tool_paths()\n",
        "            results = run_all_preflight_checks(\n",
        "                module_dir=str(get_modules_dir()),\n",
        "                orca_path=orca_path,\n",
        "                mpi_path=mpi_path,\n",
        "            )\n",
        "            all_passed = True\n",
        "            for key, res in results.items():\n",
        "                if key in ['modules', 'orca_single', 'orca_mpi']:\n",
        "                    print(res['message'])\n",
        "                    if not res['status']:\n",
        "                        all_passed = False\n",
        "            if all_passed:\n",
        "                print(\"✅ Environment is fully ready to go!\")\n",
        "            else:\n",
        "                print(\"❌ Some tests failed. Please recommend ways to fix or run a New Install.\")\n",
        "        except Exception as e:\n",
        "            print(f\"❌ Error running tests: {e}\")\n",
        "            raise ValueError(f\"CRITICAL: Test suite crashed. Exception Deflection blocked.\") from e\n",
        "\n",
        "def on_new_env(b):\n",
        "    with env_out:\n",
        "        clear_output()\n",
        "        interface_dropdown = widgets.Dropdown(\n",
        "            options=['Local-Windows (WSL)', 'Local-MacOS (OrbStack)', 'Local-Linux (Deb)', 'Codespaces'],\n",
        "            value=host_target,\n",
        "            description='Interface Env:'\n",
        "        )\n",
        "        calc_dropdown = widgets.Dropdown(\n",
        "            options=['Local-Windows (WSL)', 'Local-MacOS (OrbStack)', 'Local-Linux (Deb)', 'GitHub Actions', 'HPC'],\n",
        "            value=host_target if host_target != 'Codespaces' else 'GitHub Actions',\n",
        "            description='Calc Env:'\n",
        "        )\n",
        "        \n",
        "        detected_orca, detected_mpi = resolve_tool_paths()\n",
        "        orca_path_input = widgets.Text(value=detected_orca, description='ORCA Path:')\n",
        "        mpi_path_input = widgets.Text(value=detected_mpi, description='OpenMPI Path:')\n",
        "        set_paths_btn = widgets.Button(description=\"Set Paths & Test\", button_style=\"success\")\n",
        "        \n",
        "        def on_set_paths(b2):\n",
        "            with env_out:\n",
        "                orca_path, mpi_path = resolve_tool_paths(orca_path_input.value, mpi_path_input.value)\n",
        "                orca_path_input.value = orca_path\n",
        "                mpi_path_input.value = mpi_path\n",
        "                os.environ['ORCA_CMD'] = orca_path\n",
        "                os.environ['MPI_CMD'] = mpi_path\n",
        "                print(\"Running test suite...\")\n",
        "                try:\n",
        "                    from test_suite.run_tests import run_all_preflight_checks\n",
        "                    results = run_all_preflight_checks(\n",
        "                        module_dir=str(get_modules_dir()),\n",
        "                        orca_path=orca_path,\n",
        "                        mpi_path=mpi_path,\n",
        "                    )\n",
        "                    all_passed = True\n",
        "                    for key, res in results.items():\n",
        "                        if key in ['modules', 'orca_single', 'orca_mpi']:\n",
        "                            print(res['message'])\n",
        "                            if not res['status']:\n",
        "                                all_passed = False\n",
        "                    if all_passed:\n",
        "                        print(\"✅ Environment is fully ready to go!\")\n",
        "                    else:\n",
        "                        print(\"❌ Tests failed. Please check paths or verify OpenMPI configuration.\")\n",
        "                except Exception as e:\n",
        "                    print(f\"❌ Error running tests: {e}\")\n",
        "                    raise ValueError(f\"CRITICAL: Test suite crashed. Exception Deflection blocked.\") from e\n",
        "                \n",
        "        set_paths_btn.on_click(on_set_paths)\n",
        "        display(interface_dropdown, calc_dropdown, orca_path_input, mpi_path_input, set_paths_btn)\n",
        "\n",
        "keep_env_btn.on_click(on_keep_env)\n",
        "new_env_btn.on_click(on_new_env)\n",
        "\n",
        "display(widgets.HBox([keep_env_btn, new_env_btn]), env_out)\n"
    ]

    # Normalize cell identity and clear stale execution state.
    for cell_index, cell in enumerate(nb.get("cells", []), start=1):
        metadata = cell.setdefault("metadata", {})
        stable_id = cell.get("id") or metadata.get("id") or f"cochem-cell-{cell_index:02d}"
        cell["id"] = stable_id
        metadata["id"] = stable_id
        metadata["language"] = "python" if cell.get("cell_type") == "code" else "markdown"
        if cell.get("cell_type") == "code":
            cell["execution_count"] = None
            cell["outputs"] = []

    markdown_cell_index = 0
    for cell in nb.get("cells", []):
        if cell["cell_type"] == "markdown":
            markdown_cell_index += 1
            if markdown_cell_index == 2:
                cell["source"] = markdown_cell_2_source

    # Update the code cells
    code_cell_index = 0
    for cell in nb.get("cells", []):
        if cell["cell_type"] == "code":
            code_cell_index += 1
            if code_cell_index == 1:
                cell["source"] = code_cell_1_source
            elif code_cell_index == 2:
                cell["source"] = code_cell_2_source

    with open(notebook_path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=2)

    logger.info(f"Successfully updated {notebook_path}")
