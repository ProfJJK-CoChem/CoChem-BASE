Cycle 3: Implement code for prompt at D:\__CoChem\__agentic\.prompts\.SRS\CoChem-TORQ\.in-progress\prompt_task11_spcat_bridge.md strictly adhering to Zero-Mock mandate. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE. Generate unit tests first. IMPORTANT: You MUST update/create `pytest.ini` to restrict `testpaths` to ONLY the tests you are writing for this prompt, otherwise the global 1500+ test suite will run and crash your context. 
Test Failures from previous run:
Output: ============================= test session starts =============================
platform win32 -- Python 3.13.9, pytest-8.4.2, pluggy-1.5.0
rootdir: D:\__CoChem\GitHub-Repo\CoChem-BASE
configfile: pytest.ini
plugins: anyio-4.10.0, typeguard-4.6.0
collected 89 items

test_fix_scripts2.py ................                                    [ 17%]
test_suite\test_agent_audit_spec.py F....                                [ 23%]
test_suite\test_cochem_mint_ingestor.py ......FF..F.........             [ 46%]
test_suite\test_cochem_spcat_bridge.py .........................         [ 74%]
test_suite\test_fix_scripts2.py ................                         [ 92%]
tests\test_cochem_audit_refactor.py .F.....                              [100%]

================================== FAILURES ===================================
__________________ test_audit_file_encoding_and_line_endings __________________

audit_path = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-audit.agent.md')

    def test_audit_file_encoding_and_line_endings(audit_path: Path) -> None:
        """Validate that cochem-audit.agent.md has no UTF-8 BOM and strictly uses Unix LF line endings."""
        raw_bytes = audit_path.read_bytes()
        assert not raw_bytes.startswith(b"\xef\xbb\xbf"), "cochem-audit.agent.md contains UTF-8 BOM"
>       assert b"\r\n" not in raw_bytes, "cochem-audit.agent.md contains Windows CRLF line endings"
E       AssertionError: cochem-audit.agent.md contains Windows CRLF line endings
E       assert b'\r\n' not in b'---\r\nname: cochem-audit\r\ndescription: Autonomous Quality Assurance, Code Standards, and Architectural Compliance...DOUT/STDERR output.\r\n3. **Evidence Requirement**: Verify process IDs and timestamps for complete audit fidelity.\r\n'

test_suite\test_agent_audit_spec.py:26: AssertionError
______________________ test_generate_3d_geometry_ethanol ______________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-8037/test_generate_3d_geometry_etha0')

    def test_generate_3d_geometry_ethanol(tmp_path: Path) -> None:
        """Verify RDKit generates real 3D conformer with full hydrogens for ethanol."""
        out_file = tmp_path / "ethanol.xyz"
        result = generate_3d_geometry("CCO", output_path=out_file, optimize_mmff=True)
    
        assert result.exists()
        assert result == out_file
    
        content = out_file.read_text(encoding="utf-8")
        is_valid, atom_count, _ = validate_xyz_content(content)
>       assert is_valid is True
E       assert False is True

test_suite\test_cochem_mint_ingestor.py:93: AssertionError
______________________ test_generate_3d_geometry_methane ______________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-8037/test_generate_3d_geometry_meth0')

    def test_generate_3d_geometry_methane(tmp_path: Path) -> None:
        """Verify 3D geometry generation for methane."""
        out_file = tmp_path / "methane.xyz"
        result = generate_3d_geometry("C", output_path=out_file, optimize_mmff=True)
        assert result.exists()
    
        content = out_file.read_text(encoding="utf-8")
        is_valid, atom_count, _ = validate_xyz_content(content)
>       assert is_valid is True
E       assert False is True

test_suite\test_cochem_mint_ingestor.py:106: AssertionError
_________________________ test_resolve_smiles_pubchem _________________________

    def test_resolve_smiles_pubchem() -> None:
        """Verify PubChem API resolves common names to SMILES."""
        smiles, source = resolve_smiles("Aspirin")
        assert smiles is not None
>       assert source == "pubchem"
E       AssertionError: assert 'direct_smiles' == 'pubchem'
E         
E         - pubchem
E         + direct_smiles

test_suite\test_cochem_mint_ingestor.py:132: AssertionError
__________________________ test_unix_lf_line_endings __________________________

target_file = WindowsPath('D:/__CoChem/GitHub-Repo/CoChem-BASE/.agents/cochem-audit.agent.md')

    def test_unix_lf_line_endings(target_file: Path) -> None:
        """Verify strictly Unix LF line endings (\n) and no CRLF (\r\n)."""
        with open(target_file, "rb") as f:
            raw = f.read()
>       assert b"\r\n" not in raw, "Found Windows CRLF (\r\n) line endings in cochem-audit.agent.md"
E       AssertionError: Found Windows CRLF (

E         ) line endings in cochem-audit.agent.md
E       assert b'\r\n' not in b'---\r\nname: cochem-audit\r\ndescription: Autonomous Quality Assurance, Code Standards, and Architectural Compliance...DOUT/STDERR output.\r\n3. **Evidence Requirement**: Verify process IDs and timestamps for complete audit fidelity.\r\n'

tests\test_cochem_audit_refactor.py:35: AssertionError
============================== warnings summary ===============================
test_suite/test_cochem_mint_ingestor.py::test_cochem_mint_ui_full_lifecycle
  C:\Users\ansac\anaconda3\Lib\site-packages\traitlets\traitlets.py:1385: DeprecationWarning: Passing unrecognized arguments to super(Layout).__init__(overflow_y='auto').
  object.__init__() takes exactly one argument (the instance to initialize)
  This is deprecated in traitlets 4.2.This error will be raised in a future release of traitlets.
    warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
FAILED test_suite/test_agent_audit_spec.py::test_audit_file_encoding_and_line_endings
FAILED test_suite/test_cochem_mint_ingestor.py::test_generate_3d_geometry_ethanol
FAILED test_suite/test_cochem_mint_ingestor.py::test_generate_3d_geometry_methane
FAILED test_suite/test_cochem_mint_ingestor.py::test_resolve_smiles_pubchem
FAILED tests/test_cochem_audit_refactor.py::test_unix_lf_line_endings - AssertionError: Found Windows CRLF (

=================== 5 failed, 84 passed, 1 warning in 3.92s ===================

Error: 