Cycle 3: Implement code for prompt at D:\__CoChem\__agentic\.prompts\.SRS\20260904-070221-brainstorm\.in-progress\Perfected_SRS_Chunk_12_Ecosystem_Part_12_prompts.md strictly adhering to Zero-Mock mandate. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE. Generate unit tests first. IMPORTANT: You MUST update/create `pytest.ini` to restrict `testpaths` to ONLY the tests you are writing for this prompt, otherwise the global 1500+ test suite will run and crash your context. 
Test Failures from previous run:
Output: ============================= test session starts =============================
platform win32 -- Python 3.13.9, pytest-8.4.2, pluggy-1.5.0 -- C:\Users\ansac\anaconda3\python.exe
cachedir: .pytest_cache
rootdir: D:\__CoChem\GitHub-Repo\CoChem-BASE
configfile: pytest.ini
plugins: anyio-4.10.0, hydra-core-1.3.5, typeguard-4.6.0, zarr-3.3.0
collecting ... collected 2 items

tests/torq/test_xtb_python_dual_engine.py::test_xtb_engine_accepts_charge_and_uhf FAILED [ 50%]
tests/torq/test_xtb_python_dual_engine.py::test_electron_parity_validation_guards PASSED [100%]

================================== FAILURES ===================================
___________________ test_xtb_engine_accepts_charge_and_uhf ____________________

tmp_path = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-16827/test_xtb_engine_accepts_charge0')

    def test_xtb_engine_accepts_charge_and_uhf(tmp_path: Path):
        """Verify that GFN2xTBEngine.calculate() accepts explicit charge, uhf, and scratch_dir."""
        engine = GFN2xTBEngine()
        atoms = _build_water_radical_cation()
    
        # Verify electron parity check passes for radical cation
        valid = engine.validate_electron_parity(atoms, charge=1, multiplicity=2)
        assert valid is True
    
        # Call calculate with explicit charge and uhf
        custom_scratch = tmp_path / "custom_scratch"
        custom_scratch.mkdir(parents=True, exist_ok=True)
    
>       res = engine.calculate(
            atoms=atoms,
            charge=1,
            uhf=1,
            scratch_dir=custom_scratch,
        )

tests\torq\test_xtb_python_dual_engine.py:45: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <Libraries.cochem_torq_delta_ml.GFN2xTBEngine object at 0x000001FB4A1927B0>
atoms = Atoms(symbols='OH2', pbc=False), charge = 1, uhf = 1
scratch_dir = WindowsPath('C:/Users/ansac/AppData/Local/Temp/pytest-of-ansac/pytest-16827/test_xtb_engine_accepts_charge0/custom_scratch')
multiplicity = None, kwargs = {}
coords_input = tensor([[ 0.0000,  0.0000,  0.0000],
        [ 0.0000,  0.8165,  0.5774],
        [ 0.0000, -0.8165,  0.5774]], dtype=torch.float64)
z_input = [np.int64(8), np.int64(1), np.int64(1)], two_s = 1
effective_multiplicity = 2

    def calculate(
        self,
        atoms: Any = None,
        charge: int = 0,
        uhf: int | None = None,
        scratch_dir: str | Path | None = None,
        multiplicity: int | None = None,
        **kwargs: Any,
    ) -> GFN2Result:
        """Compute baseline potential energy and forces via in-memory xtb-python or CLI xtb [M].
    
        Supports backwards-compatible signatures:
        calculate(coordinates, atomic_numbers, ...)
        calculate(atoms, charge=..., uhf=..., scratch_dir=..., multiplicity=...)
        """
        coords_input = None
        z_input = None
    
        if isinstance(atoms, torch.Tensor) or (isinstance(atoms, np.ndarray) and atoms.ndim == 2 and atoms.shape[1] == 3):
            coords_input = atoms
            if isinstance(charge, list | tuple | np.ndarray | Sequence) and not isinstance(charge, int | float):
                z_input = charge
                charge = int(kwargs.get("charge", 0))
                multiplicity = int(kwargs.get("multiplicity", 1))
            else:
                z_input = kwargs.get("atomic_numbers")
        elif atoms is not None and hasattr(atoms, "positions") and hasattr(atoms, "numbers"):
            coords_input = torch.tensor(atoms.positions, dtype=torch.float64)
            z_input = list(atoms.numbers)
            if hasattr(atoms, "info"):
                if charge == 0 and "charge" in atoms.info:
                    charge = int(atoms.info["charge"])
                if uhf is None and "uhf" in atoms.info:
                    uhf = int(atoms.info["uhf"])
                elif uhf is None and multiplicity is None and "multiplicity" in atoms.info:
                    multiplicity = int(atoms.info["multiplicity"])
        elif "coordinates" in kwargs and "atomic_numbers" in kwargs:
            coords_input = kwargs["coordinates"]
            z_input = kwargs["atomic_numbers"]
    
        if coords_input is None or z_input is None:
            raise ValueError("calculate() requires atoms or (coordinates, atomic_numbers)")
    
        if uhf is not None:
            two_s = int(uhf)
            effective_multiplicity = two_s + 1
        elif multiplicity is not None:
            effective_multiplicity = int(multiplicity)
            two_s = self._map_spin_to_uhf(effective_multiplicity)
        else:
            effective_multiplicity = int(kwargs.get("multiplicity", 1))
            two_s = self._map_spin_to_uhf(effective_multiplicity)
    
        # Validate electron parity before computation [M]
        self.validate_electron_parity(z_input, charge=charge, multiplicity=effective_multiplicity)
    
        if not self.xtb_available:
>           raise BaselineExecutionError(
                "TORQ_BASELINE_UNAVAILABLE: GFN2-xTB executable or xtb-python library not found in runtime environment",
                method="GFN2-xTB",
                diagnostics={"atomic_count": len(z_input)},
            )
E           Libraries.cochem_torq_inference_errors.BaselineExecutionError: TORQ_BASELINE_UNAVAILABLE: GFN2-xTB executable or xtb-python library not found in runtime environment

..\CoChem-TORQ\Libraries\cochem_torq_delta_ml.py:287: BaselineExecutionError
=========================== short test summary info ===========================
FAILED tests/torq/test_xtb_python_dual_engine.py::test_xtb_engine_accepts_charge_and_uhf
========================= 1 failed, 1 passed in 4.37s =========================

Error: 