"""Verified package lock and immutable destination guards."""
import pytest
from cochem_base.orchestrator.micro_silo_manager import validate_pins
from cochem_base.orchestrator.silo_dependency_pins import DEFAULT_PINS
from cochem_base.orchestrator.ml_silo_manager import TORCH_CPU_WHEEL, provision_mace_silo


def test_actual_mace_lock_uses_available_release_and_pinned_cpu_wheel():
    pins=validate_pins(DEFAULT_PINS['mace'])
    assert pins['mace-torch']=='0.3.16'
    assert pins['torch']=='2.8.0+cpu'
    assert TORCH_CPU_WHEEL.endswith('#sha256=cb9a8ba8137ab24e36bf1742cb79a1294bd374db570f09fc15a5e1318160db4e')
    assert len(pins)==len(DEFAULT_PINS['mace'])


def test_nonempty_destination_is_not_repaired_or_deleted(tmp_path):
    marker=tmp_path/'keep.txt';marker.write_text('preserve')
    with pytest.raises(SystemExit,match='nonempty'):
        provision_mace_silo(tmp_path)
    assert marker.read_text()=='preserve'


def test_cuda_profile_has_exact_official_wheel_sources_and_dependency_closure():
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name
    from cochem_base.orchestrator.ml_cuda_sources import CUDA128_SOURCES
    from cochem_base.orchestrator.ml_silo_manager import mace_profile_lock

    import re
    from urllib.parse import urlsplit

    assert mace_profile_lock('cpu') == 'mace'
    assert mace_profile_lock('cuda128') == 'mace_cuda128'
    lock = {canonicalize_name(k): v for k, v in validate_pins(DEFAULT_PINS['mace_cuda128']).items()}
    assert lock['torch'] == '2.8.0'
    assert lock['mace-torch'] == '0.3.16'
    assert len(CUDA128_SOURCES['packages']) == 16
    for name, source in CUDA128_SOURCES['packages'].items():
        assert lock[canonicalize_name(name)] == source['version']
        assert urlsplit(source['url']).hostname == 'files.pythonhosted.org'
        assert source['url'].endswith('.whl')
        assert re.fullmatch(r'[a-f0-9]{64}', source['sha256'])
        assert source['size_bytes'] > 0
        for value in source['requires_dist']:
            requirement = Requirement(value)
            if requirement.marker is None or requirement.marker.evaluate({'extra': ''}):
                assert requirement.specifier.contains(lock[canonicalize_name(requirement.name)])


def test_unknown_profile_is_rejected_before_destination_mutation(tmp_path):
    with pytest.raises(SystemExit, match='cpu or cuda128'):
        provision_mace_silo(tmp_path / 'new', profile='auto')
    assert not (tmp_path / 'new').exists()
