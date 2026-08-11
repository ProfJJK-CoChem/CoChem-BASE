"""HDF5 Ontology Enforcer for CoChem Base metadata validation."""

from pydantic import BaseModel, Field, ValidationError
from pathlib import Path
from typing import Any, Dict, Optional, Union
import h5py
import numpy as np
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from cochem_base.core.models import CoChemConfig, ToposStage, CorrelationMatrix


class BasinRecord(BaseModel):
    """Pydantic model for HDF5 Basin Record schema enforcement."""
    molecule_name: str = Field(..., description="Name or identifier of the molecule")
    xyz_coordinates: Optional[Any] = Field(None, description="Atomic coordinates tensor or list")
    energy: float = Field(..., description="Total energy of the basin")
    symmetry_group: str = Field(default="C1", description="Point group symmetry")
    LAM_TRIGGER_REQUIRED: bool = Field(default=False, description="Large Amplitude Motion trigger flag")


class HDF5OntologyEnforcer:
    """Enforces dynamic schema validation on payload metadata before writing to HDF5 store."""

    def __init__(self, hdf5_path: Union[str, Path] = "cochem_state.h5") -> None:
        self.hdf5_path = Path(hdf5_path)

    def validate_payload(self, payload: Dict[str, Any], model_cls: Any = BasinRecord) -> Any:
        """Validate payload dict against the specified Pydantic model class.
        
        Raises ValueError if schema validation fails.
        """
        try:
            return model_cls(**payload)
        except ValidationError as exc:
            raise ValueError(f"HDF5 metadata schema validation failed: {exc}") from exc

    def write_record(self, group_path: str, data: Dict[str, Any]) -> None:
        """Validate data into BasinRecord and commit to HDF5 store at group_path."""
        record = self.validate_payload(data, model_cls=BasinRecord)
        with h5py.File(self.hdf5_path, "a") as h5f:
            grp = h5f.require_group(group_path)
            grp.attrs["molecule_name"] = record.molecule_name
            grp.attrs["energy"] = record.energy
            grp.attrs["symmetry_group"] = record.symmetry_group
            grp.attrs["LAM_TRIGGER_REQUIRED"] = record.LAM_TRIGGER_REQUIRED
            if record.xyz_coordinates is not None:
                if "xyz_coordinates" in grp:
                    del grp["xyz_coordinates"]
                coords_arr = np.array(record.xyz_coordinates)
                grp.create_dataset("xyz_coordinates", data=coords_arr)

    def write_dataset_with_attributes(
        self,
        dataset_name: str,
        data: Any,
        metadata_payload: Dict[str, Any],
        group_name: str = "method_matrix",
    ) -> None:
        """Validates payload against BasinRecord or CoChemConfig model and commits dataset + attributes to HDF5."""
        try:
            validated: Any = BasinRecord(**metadata_payload)
        except ValidationError:
            try:
                validated = CoChemConfig(**metadata_payload)
            except ValidationError as exc:
                raise ValueError(f"HDF5 metadata schema validation failed: {exc}") from exc

        with h5py.File(self.hdf5_path, "a") as h5f:
            grp = h5f.require_group(group_name)
            if dataset_name in grp:
                del grp[dataset_name]
            dset = grp.create_dataset(dataset_name, data=data)

            # Store validated attributes
            dset.attrs["LAM_TRIGGER_REQUIRED"] = getattr(validated, "LAM_TRIGGER_REQUIRED", False)
            dset.attrs["symmetry_group"] = getattr(validated, "symmetry_group", "C1")

            # Store all other top-level fields
            model_dict = validated.model_dump() if hasattr(validated, "model_dump") else validated.dict()
            for key, val in model_dict.items():
                if isinstance(val, (int, float, str, bool)):
                    dset.attrs[key] = val


# Backward-compatible alias
CoChemHDF5Manager = HDF5OntologyEnforcer
