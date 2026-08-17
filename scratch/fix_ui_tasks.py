
file_path = r'D:\__CoChem\GitHub-Repo\CoChem-BASE\run_ui_tasks.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: Sequence architectural error
old_top = """import json
import logging
import os
import sys
from pathlib import Path

import cochem_base.config_loader as config_loader
from cochem_base.config_loader import get_artifact_dir, resolve_mapped_path
from setup.cochem_base_setup import _launch_silo_setup

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

BASE_ROOT = Path(__file__).resolve().parent
if str(BASE_ROOT) not in sys.path:
    sys.path.insert(0, str(BASE_ROOT))
os.environ['COCHEM_BASE_ROOT'] = str(BASE_ROOT)"""

new_top = """import json
import logging
import os
import sys
from pathlib import Path

BASE_ROOT = Path(__file__).resolve().parent
if str(BASE_ROOT) not in sys.path:
    sys.path.insert(0, str(BASE_ROOT))
os.environ['COCHEM_BASE_ROOT'] = str(BASE_ROOT)

import cochem_base.config_loader as config_loader  # noqa: E402
from cochem_base.config_loader import get_artifact_dir, resolve_mapped_path  # noqa: E402
from setup.cochem_base_setup import _launch_silo_setup  # noqa: E402

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)"""

content = content.replace(old_top, new_top)

# Fix 2: Typing exception deflection
old_stdout = """for line in iter(proc.stdout.readline, ''):  # type: ignore
    sys.stdout.write(line)"""
new_stdout = """if proc.stdout is not None:
    for line in iter(proc.stdout.readline, ''):
        sys.stdout.write(line)"""
content = content.replace(old_stdout, new_stdout)

# Fix 3: Exception deflection
old_except = """except Exception as e:
    logger.info(f"❌ Error running tests: {e}")
    sys.exit(1)"""
new_except = """except Exception as e:
    logger.info(f"❌ Error running tests: {e}")
    raise ValueError("CRITICAL: UI tasks failed. Exception Deflection blocked.") from e"""
content = content.replace(old_except, new_except)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
