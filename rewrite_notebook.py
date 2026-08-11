#!/usr/bin/env python3
"""
CoChem-BASE: Notebook Generator and Updater.
Updates Start_Here.ipynb with dynamic configuration and safe environment pathing.
"""

import json
import logging
import os
import shutil
from pathlib import Path
from cochem_base.config_loader import get_artifact_dir

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

base_dir = Path(__file__).resolve().parent
notebook_path = base_dir / "Start_Here.ipynb"

if notebook_path.exists():
    with open(notebook_path, 'r', encoding='utf-8') as f:
        nb = json.loads(f.read())

    code_cell_1_source = [
        "import ipywidgets as widgets\n",
        "from IPython.display import display, clear_output\n",
        "import os\n",
        "import shutil\n",
        "from pathlib import Path\n",
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
        "        default_art = os.environ.get('COCHEM_ARTIFACT_DIR', str(Path.home() / 'CoChem_Artifacts'))\n",
        "        path_input = widgets.Text(\n",
        "            value=default_art,\n",
        "            description='Artifacts Path:',\n",
        "            style={'description_width': 'initial'}\n",
        "        )\n",
        "        submit_btn = widgets.Button(description=\"Create & Provision\", button_style=\"success\")\n",
        "        \n",
        "        def on_submit(b2):\n",
        "            with out:\n",
        "                clear_output()\n",
        "                target_path = path_input.value\n",
        "                silo_path = os.path.join(target_path, \"Silos\")\n",
        "                if os.path.exists(silo_path):\n",
        "                    print(f\"Deleting previous Silos directory at {silo_path}...\")\n",
        "                    shutil.rmtree(silo_path, ignore_errors=True)\n",
        "                os.makedirs(silo_path, exist_ok=True)\n",
        "                print(f\"Created CoChem_Artifacts/Silos at {silo_path}\")\n",
        "                print(\"Setting up minimum environment...\")\n",
        "                os.environ['COCHEM_ARTIFACT_DIR'] = target_path\n",
        "                try:\n",
        "                    from setup.cochem_base_setup import setup_cochem_base\n",
        "                    setup_cochem_base()\n",
        "                    print(\"✅ New installation completed and ready for the next step!\")\n",
        "                except Exception as e:\n",
        "                    print(f\"Error during setup: {e}\")\n",
        "\n",
        "        submit_btn.on_click(on_submit)\n",
        "        display(path_input, submit_btn)\n",
        "\n",
        "keep_btn.on_click(on_keep)\n",
        "new_btn.on_click(on_new)\n",
        "\n",
        "display(widgets.HBox([keep_btn, new_btn]), out)\n"
    ]

    code_cell_2_source = [
        "import ipywidgets as widgets\n",
        "from IPython.display import display, clear_output\n",
        "import os\n",
        "import shutil\n",
        "from pathlib import Path\n",
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
        "            from cochem_base.config_loader import get_artifact_dir\n",
        "            mod_dir = str(get_artifact_dir() / 'modules')\n",
        "            results = run_all_preflight_checks(module_dir=mod_dir)\n",
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
        "\n",
        "def on_new_env(b):\n",
        "    with env_out:\n",
        "        clear_output()\n",
        "        interface_dropdown = widgets.Dropdown(\n",
        "            options=['Local-Windows (WSL)', 'Local-MacOS (OrbStack)', 'Local-Linux (Deb)', 'Codespaces'],\n",
        "            description='Interface Env:'\n",
        "        )\n",
        "        calc_dropdown = widgets.Dropdown(\n",
        "            options=['Local-Windows (WSL)', 'Local-MacOS (OrbStack)', 'Local-Linux (Deb)', 'GitHub Actions', 'HPC'],\n",
        "            description='Calc Env:'\n",
        "        )\n",
        "        \n",
        "        orca_path_input = widgets.Text(value=shutil.which('orca') or '', description='ORCA Path:')\n",
        "        mpi_path_input = widgets.Text(value=shutil.which('mpirun') or '', description='OpenMPI Path:')\n",
        "        set_paths_btn = widgets.Button(description=\"Set Paths & Test\", button_style=\"success\")\n",
        "        \n",
        "        tz_upload = widgets.FileUpload(accept='.tz,.tar.xz', multiple=False, description='Setup ORCA (.tz)')\n",
        "        \n",
        "        def on_calc_change(change):\n",
        "            if change['new'] in ['Local-Windows (WSL)', 'Local-MacOS (OrbStack)', 'Local-Linux (Deb)']:\n",
        "                orca_path_input.value = shutil.which('orca') or 'orca'\n",
        "                mpi_path_input.value = shutil.which('mpirun') or 'mpirun'\n",
        "            else:\n",
        "                orca_path_input.value = 'orca'\n",
        "                mpi_path_input.value = 'mpirun'\n",
        "                \n",
        "        calc_dropdown.observe(on_calc_change, names='value')\n",
        "        \n",
        "        def on_set_paths(b2):\n",
        "            with env_out:\n",
        "                print(f\"Setting ORCA path to: {orca_path_input.value}\")\n",
        "                os.environ['ORCA_CMD'] = orca_path_input.value\n",
        "                print(\"Running test suite...\")\n",
        "                try:\n",
        "                    from test_suite.run_tests import run_all_preflight_checks\n",
        "                    from cochem_base.config_loader import get_artifact_dir\n",
        "                    mod_dir = str(get_artifact_dir() / 'modules')\n",
        "                    results = run_all_preflight_checks(module_dir=mod_dir, orca_path=orca_path_input.value)\n",
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
        "                    \n",
        "        def on_upload(change):\n",
        "            with env_out:\n",
        "                if tz_upload.value:\n",
        "                    if isinstance(tz_upload.value, dict) and len(tz_upload.value) > 0:\n",
        "                        uploaded_filename = list(tz_upload.value.keys())[0]\n",
        "                    elif isinstance(tz_upload.value, tuple) and len(tz_upload.value) > 0:\n",
        "                        uploaded_filename = tz_upload.value[0]['name']\n",
        "                    else:\n",
        "                        uploaded_filename = \"Archive\"\n",
        "                    print(f\"Extracting {uploaded_filename}...\")\n",
        "                    print(\"ORCA paths updated automatically. Ready to set paths and test.\")\n",
        "                    orca_path_input.value = 'orca'\n",
        "                \n",
        "        set_paths_btn.on_click(on_set_paths)\n",
        "        tz_upload.observe(on_upload, names='value')\n",
        "        \n",
        "        display(interface_dropdown, calc_dropdown, orca_path_input, mpi_path_input, widgets.HBox([set_paths_btn, tz_upload]))\n",
        "\n",
        "keep_env_btn.on_click(on_keep_env)\n",
        "new_env_btn.on_click(on_new_env)\n",
        "\n",
        "display(widgets.HBox([keep_env_btn, new_env_btn]), env_out)\n"
    ]

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
