from typing import Any
import json
from pydantic import BaseModel, Field, ValidationError

class SwarmGoal(BaseModel):
    goal_id: str
    task_type: str
    payload_data: dict[str, Any] = Field(default_factory=dict)
    priority: int = 0

def validate_payloads_batch(payload_json_strings: list[str]) -> list[SwarmGoal]:
    """
    High-throughput batch validation for JSON payload strings using Pydantic V2.
    Optimized for throughput >10,000 payloads/sec.
    """
    validated = []
    for s in payload_json_strings:
        try:
            validated.append(SwarmGoal.model_validate_json(s))
        except (ValidationError, json.JSONDecodeError) as e:
            raise ValueError(f"Failed to parse or validate payload: {s}. Error: {e}") from e
    return validated
