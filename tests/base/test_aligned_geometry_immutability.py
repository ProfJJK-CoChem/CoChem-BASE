"""Immutable Task1 records from authentic retained ORCA water geometry."""
from __future__ import annotations

import json
import copy
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError
from scipy.spatial.transform import Rotation

from cochem_base.core import cochem_constants as constants
from cochem_base.intake import cochem_molsym_eckart_aligner as aligner


NATIVE = Path(__file__).parents[1] / 'data/orca_6_1_1_water_hf_sto3g'


@pytest.fixture(scope='module')
def aligned_native_water():
    reference, symbols, masses = aligner.parse_molecular_input(NATIVE / 'water.xyz')
    target = Rotation.from_euler('xyz', [17., 23., 31.], degrees=True).apply(reference)
    result = aligner.standardize_and_align_molsym_eckart(target, symbols=symbols,
        masses=masses, ref_coords=reference, construct_projector=True, symmetrize=True)
    assert result.molsym_profile.source == 'molsym' and result.molsym_profile.backend_version
    assert result.molsym_profile.point_group == 'C2v'
    assert result.eckart_result.is_proper_rotation
    assert result.eckart_result.rotation_determinant == pytest.approx(1., abs=1e-12)
    assert result.eckart_result.residual_rotational_norm < 1e-10
    assert result.eckart_result.translational_residual_norm < 1e-12
    assert result.vibrational_projector_result.is_idempotent
    assert result.vibrational_projector_result.expected_trace == 3
    return result


def _owner(result, path):
    parts = path.split('.')
    for part in parts[:-1]:
        result = getattr(result, part)
    return result, parts[-1]


ARRAY_FIELDS = [
    'raw_coords', 'aligned_coords', 'inertia_result.aligned_coords',
    'inertia_result.rotation_matrix', 'inertia_result.inertia_tensor',
    'eckart_result.aligned_coords', 'eckart_result.rotation_matrix',
    'vibrational_projector_result.projector_matrix', 'molsym_profile.symmetrized_coords',
]


@pytest.mark.parametrize('path', ARRAY_FIELDS)
def test_result_arrays_own_immutable_values_and_structure(aligned_native_water, path):
    owner, name = _owner(aligned_native_water, path)
    array = getattr(owner, name)
    original = np.array(array, copy=True)
    assert not array.flags.writeable and memoryview(array).readonly
    with pytest.raises(ValueError):
        array.flat[0] = float(array.flat[0]) + 1.
    with pytest.raises(ValueError):
        array.setflags(write=True)
    with pytest.raises(ValueError):
        array.flags.writeable = True
    with pytest.raises(TypeError, match='metadata is immutable'):
        array.shape = (array.size,)
    with pytest.raises(TypeError, match='metadata is immutable'):
        array.dtype = np.dtype('uint8')
    with pytest.raises(ValueError, match='cannot be resized'):
        array.resize((array.size,))
    np.testing.assert_array_equal(array, original)

    mutable = np.array(original, copy=True)
    copied = owner.model_copy(update={name: mutable}, deep=True)
    mutable.flat[0] += 1.
    np.testing.assert_array_equal(getattr(copied, name), original)
    assert not getattr(copied, name).flags.writeable
    with pytest.raises(ValueError):
        getattr(copied, name).setflags(write=True)


@pytest.mark.parametrize('path', ['', 'inertia_result', 'molsym_profile', 'eckart_result', 'vibrational_projector_result'])
def test_all_nested_result_models_reject_field_replacement(aligned_native_water, path):
    model = getattr(aligned_native_water, path) if path else aligned_native_water
    with pytest.raises(ValidationError, match='frozen'):
        if not path:
            model.total_mass_amu = model.total_mass_amu
        elif path == 'inertia_result':
            model.inertial_defect = model.inertial_defect
        elif path == 'molsym_profile':
            model.rotational_symmetry_number = model.rotational_symmetry_number
        elif path == 'eckart_result':
            model.rmsd = model.rmsd
        else:
            model.trace = model.trace
    with pytest.raises(ValidationError, match='frozen'):
        if not path:
            del model.total_mass_amu
        elif path == 'inertia_result':
            del model.inertial_defect
        elif path == 'molsym_profile':
            del model.rotational_symmetry_number
        elif path == 'eckart_result':
            del model.rmsd
        else:
            del model.trace


def test_nested_sequences_and_character_metadata_have_no_mutable_alias(aligned_native_water):
    result = aligned_native_water
    profile = result.molsym_profile
    assert isinstance(result.symbols, tuple) and isinstance(result.masses_amu, tuple)
    assert isinstance(result.center_of_mass, tuple)
    assert all(isinstance(group, tuple) for group in profile.symmetrically_equivalent_atoms)
    for sequence in (result.symbols, result.masses_amu, result.center_of_mass,
                     profile.symmetrically_equivalent_atoms, profile.symmetry_elements,
                     profile.classes, profile.irreps, profile.unavailable_properties):
        with pytest.raises(TypeError):
            sequence[0] = sequence[0]
    with pytest.raises(TypeError):
        profile.symmetrically_equivalent_atoms[0][0] = 2
    irrep = next(iter(profile.character_table))
    group = next(iter(profile.character_table[irrep]))
    with pytest.raises(TypeError):
        profile.character_table[irrep] = {}
    with pytest.raises(TypeError):
        profile.character_table[irrep][group] = 999.
    with pytest.raises(TypeError):
        profile.nuclear_spin_weights['invented'] = 1.

    source = profile.model_dump(mode='json')
    restored = aligner.MolSymProfile.model_validate(source)
    source['character_table'][irrep][group] = 999.
    source['symmetrically_equivalent_atoms'][0][0] = 2
    assert restored.character_table[irrep][group] == profile.character_table[irrep][group]
    assert restored.symmetrically_equivalent_atoms == profile.symmetrically_equivalent_atoms


@pytest.mark.parametrize('path', ['', 'inertia_result', 'molsym_profile', 'eckart_result', 'vibrational_projector_result'])
def test_json_roundtrip_preserves_native_record_and_immutability(aligned_native_water, path):
    model = getattr(aligned_native_water, path) if path else aligned_native_water
    payload = model.model_dump_json()
    assert json.loads(payload) == model.model_dump(mode='json')
    restored = type(model).model_validate_json(payload)
    assert restored.model_dump(mode='json') == model.model_dump(mode='json')
    assert type(restored).model_config['frozen']
    for name in type(restored).model_fields:
        value = getattr(restored, name)
        if isinstance(value, np.ndarray):
            assert not value.flags.writeable
            with pytest.raises(ValueError):
                value.setflags(write=True)
    if not path:
        assert restored.to_xyz_string() == model.to_xyz_string()


def test_input_source_arrays_cannot_change_an_alignment_record():
    reference, symbols, masses = aligner.parse_molecular_input(NATIVE / 'water.xyz')
    target = Rotation.from_euler('z', 33., degrees=True).apply(reference)
    aligned = aligner.align_to_eckart_frame(target, reference, masses=masses)
    snapshot = np.array(aligned.aligned_coords, copy=True)
    target[:] += 1.
    reference[:] += 1.
    masses[:] *= 2.
    np.testing.assert_array_equal(aligned.aligned_coords, snapshot)


@pytest.mark.parametrize('route', ['construct', 'legacy_copy', 'python_copy', 'python_deepcopy'])
def test_constructor_and_copy_routes_cannot_bypass_immutable_storage(aligned_native_water, route):
    source = aligned_native_water
    mutable = np.array(source.raw_coords, copy=True)
    if route == 'construct':
        fields = {name: getattr(source, name) for name in type(source).model_fields}
        fields['raw_coords'] = mutable
        cloned = type(source).model_construct(**fields)
    elif route == 'legacy_copy':
        cloned = source.copy(update={'raw_coords': mutable}, deep=True)
    elif route == 'python_copy':
        cloned = copy.copy(source)
    else:
        cloned = copy.deepcopy(source)
    mutable[:] += 1.
    np.testing.assert_array_equal(cloned.raw_coords, source.raw_coords)
    assert cloned.model_dump(mode='json') == source.model_dump(mode='json')
    with pytest.raises(ValueError):
        cloned.raw_coords.setflags(write=True)
    with pytest.raises(TypeError):
        cloned.molsym_profile.character_table[next(iter(cloned.molsym_profile.character_table))] = {}


def test_alignment_units_use_the_canonical_constant_authority(aligned_native_water):
    assert aligner.PLANCK_H == constants.PLANCK_CONSTANT_J_S
    assert aligner.ATOMIC_MASS_UNIT_U == constants.ATOMIC_MASS_UNIT_KG
    assert aligner.SPEED_OF_LIGHT_C == constants.SPEED_OF_LIGHT_M_S
    assert aligner.ANGSTROM_TO_M == constants.ANGSTROM_TO_METER
    inertia = aligned_native_water.inertia_result
    np.testing.assert_allclose(np.asarray(inertia.rotational_constants_mhz) * inertia.eigenvalues_amu_angstrom2,
        constants.C_ROT_MHZ_U_ANG2, rtol=1e-14)
    np.testing.assert_allclose(np.asarray(inertia.rotational_constants_ghz) * 1e3,
        inertia.rotational_constants_mhz, rtol=1e-14)
    np.testing.assert_allclose(np.asarray(inertia.rotational_constants_cm1) * constants.SPEED_OF_LIGHT_CM_S / 1e6,
        inertia.rotational_constants_mhz, rtol=1e-14)
