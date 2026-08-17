import re

file_path = r'D:\__CoChem\GitHub-Repo\CoChem-BASE\monomer_relax.inp'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix syntax error: multiple simple input lines
content = re.sub(r'! r2SCAN-3c DIIS\n', '', content)
content = re.sub(r'! r2SCAN-3c TightOPT TightSCF\n', '! r2SCAN-3c TightOPT TightSCF DIIS defgrid3\n', content)

# Fix architectural error: opposite constraints
# It currently freezes intermolecular R (0-2, 0-3, etc) and optimizes monomers.
# Rule: "Freeze high-level monomers ... and optimize intermolecular R"
old_constraints = """  Constraints
    { B 0 2 C }
    { B 0 3 C }
    { B 1 2 C }
    { B 1 3 C }
  end"""

new_constraints = """  Constraints
    { B 0 1 C }
    { B 2 3 C }
  end"""

content = content.replace(old_constraints, new_constraints)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
