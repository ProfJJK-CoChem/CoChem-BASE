Cycle 2: Implement code for prompt at D:\__CoChem\__agentic\.prompts\.SRS\CoChem-SCRIBE\.in-progress\prompt_test_scribe_templater.md strictly adhering to Zero-Mock mandate. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE. Generate unit tests first. IMPORTANT: You MUST update/create `pytest.ini` to restrict `testpaths` to ONLY the tests you are writing for this prompt, otherwise the global 1500+ test suite will run and crash your context. 
Test Failures from previous run:
Output: ============================= test session starts =============================
platform win32 -- Python 3.13.9, pytest-8.4.2, pluggy-1.5.0
rootdir: D:\__CoChem\GitHub-Repo\CoChem-BASE
configfile: pytest.ini
plugins: anyio-4.10.0, hydra-core-1.3.5, typeguard-4.6.0, zarr-3.3.0
collected 36 items

formatters\test_scribe_templater.py .........                            [ 25%]
tests\test_scribe_templater.py .........                                 [ 50%]
tests\test_dataset.py .....F....F.F.....                                 [100%]

================================== FAILURES ===================================
_______________ test_normalize_targets_transform_invertibility ________________

ethanol_molecule = MolecularData(num_nodes=9, num_edges=72, y=[1], x=[9, 15], edge_attr=[72, 17])

    def test_normalize_targets_transform_invertibility(ethanol_molecule: MolecularData) -> None:
        """Verify NormalizeTargetsTransform normalizes targets and denormalize is invertible."""
        mean_val = -150.0
        std_val = 10.0
        norm_transform = NormalizeTargetsTransform(mean=mean_val, std=std_val)
    
        normalized = norm_transform(ethanol_molecule)
    
        # Immutability
>       assert float(ethanol_molecule.y.item()) == -155.0
E       assert -155.02999877929688 == -155.0
E        +  where -155.02999877929688 = float(-155.02999877929688)
E        +    where -155.02999877929688 = <built-in method item of Tensor object at 0x0000020A6A3961C0>()
E        +      where <built-in method item of Tensor object at 0x0000020A6A3961C0> = tensor([-155.0300]).item
E        +        where tensor([-155.0300]) = MolecularData(num_nodes=9, num_edges=72, y=[1], x=[9, 15], edge_attr=[72, 17]).y

tests\test_dataset.py:333: AssertionError
_______________ test_geom_inmemory_dataset_conformer_strategies _______________

    def test_geom_inmemory_dataset_conformer_strategies() -> None:
        """Verify conformer selection strategies: all, lowest_energy, boltzmann, random."""
>       conf1 = ConformerRecord(
            conformer_id="c1",
            symbols=["C", "H", "H", "H", "H"],
            positions=[[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1], [-1, 0, 0]],
            energy_hartree=-40.510,
        )
E       TypeError: ConformerRecord.__init__() got an unexpected keyword argument 'symbols'

tests\test_dataset.py:466: TypeError
________________ test_geom_iterable_dataset_streaming_msgpack _________________

    def test_geom_iterable_dataset_streaming_msgpack() -> None:
        """Verify GEOMIterableDataset streams conformers without full in-memory loading."""
>       conf1 = ConformerRecord(
            conformer_id="c1",
            symbols=["O", "H", "H"],
            positions=[[0, 0, 0], [0, 1, 0], [0, 0, 1]],
            energy_hartree=-76.4,
        )
E       TypeError: ConformerRecord.__init__() got an unexpected keyword argument 'symbols'

tests\test_dataset.py:542: TypeError
=========================== short test summary info ===========================
FAILED tests/test_dataset.py::test_normalize_targets_transform_invertibility
FAILED tests/test_dataset.py::test_geom_inmemory_dataset_conformer_strategies
FAILED tests/test_dataset.py::test_geom_iterable_dataset_streaming_msgpack - ...
================== 3 failed, 33 passed in 104.11s (0:01:44) ===================

Error: 