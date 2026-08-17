import json

with open('D:/__CoChem/GitHub-Repo/CoChem-BASE/Start_Here.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

for idx, cell in enumerate(nb['cells']):
    if cell['cell_type'] == 'code':
        source = ''.join(cell['source'])
        if 'except Exception as e:' in source:
            new_source = source.replace(
                'except Exception as e:\n                    print(f"Error during setup: {e}")',
                'except Exception as e:\n                    print(f"Error during setup: {e}")\n                    raise'
            )
            new_source = new_source.replace(
                'except Exception as e:\n            print(f"❌ Error: {e}. Please run a New Install.")',
                'except Exception as e:\n            print(f"❌ Error: {e}. Please run a New Install.")\n            raise'
            )
            new_source = new_source.replace(
                'except Exception as e:\n            print(f"❌ Error running tests: {e}")',
                'except Exception as e:\n            print(f"❌ Error running tests: {e}")\n            raise'
            )
            new_source = new_source.replace(
                'except Exception as e:\n                    print(f"❌ Error running tests: {e}")',
                'except Exception as e:\n                    print(f"❌ Error running tests: {e}")\n                    raise'
            )
            nb['cells'][idx]['source'] = [line + '\n' for line in new_source.split('\n')][:-1]

with open('D:/__CoChem/GitHub-Repo/CoChem-BASE/Start_Here.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)
