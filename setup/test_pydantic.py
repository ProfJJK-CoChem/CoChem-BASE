from pydantic import BaseModel, ConfigDict, Field

class HPCSettings(BaseModel):
    model_config = ConfigDict(extra='allow')
    status: str = 'slurm_ready'
    scheduler: str = 'slurm'
    module_loads: str = ''
    template_path: str = ''

class ExecutionSettings(BaseModel):
    model_config = ConfigDict(extra='allow')
    default_engine: str = 'sbatch'

class SystemRegistry(BaseModel):
    model_config = ConfigDict(extra='allow')
    hpc: HPCSettings = Field(default_factory=HPCSettings)
    execution: ExecutionSettings = Field(default_factory=ExecutionSettings)

data={'other': 123}
reg=SystemRegistry.model_validate(data)
print(reg.model_dump(mode='json'))
