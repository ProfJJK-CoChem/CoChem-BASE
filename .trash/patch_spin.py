import os
import re

filepath = r"D:\__CoChem\GitHub-Repo\CoChem-BASE\calc\cochem_calc_output_parser.py"

with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

spin_check = '''
    def check_spin_contamination(self, log_path: Path) -> bool:
        s_squared_actual = None
        s_squared_ideal = None
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                if "Expectation value of <S**2>" in line:
                    try:
                        s_squared_actual = float(line.split(":")[-1].strip())
                    except ValueError:
                        pass
                if "Ideal value S*(S+1)" in line:
                    try:
                        s_squared_ideal = float(line.split(":")[-1].strip())
                    except ValueError:
                        pass

        if s_squared_actual is not None and s_squared_ideal is not None and s_squared_ideal > 0:
            deviation = (s_squared_actual - s_squared_ideal) / s_squared_ideal
            if deviation > 0.10:
                logger.error(f"❌ [HARD_ABORT: PHYSICS WALL] Spin contamination exceeded 10% tolerance: {deviation*100:.1f}%")
                return False
        return True
'''

if "def check_spin_contamination" not in content:
    content = content.replace('def verify_basis_saturation', spin_check + '\n    def verify_basis_saturation')

if "if not self.verify_scf_convergence(log_path):" in content:
    content = content.replace(
        'if not self.verify_scf_convergence(log_path):\n            return False',
        'if not self.verify_scf_convergence(log_path):\n            return False\n\n        if not self.check_spin_contamination(log_path):\n            return False'
    )

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
