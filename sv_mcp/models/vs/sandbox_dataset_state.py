from typing import Any, Dict, List

from pydantic import BaseModel, Field


class SandboxDatasetState(BaseModel):
    models: Dict[str, List[Dict[str, Any]]] = Field(
        {},
        description="Data entity name -> current rows in the sandbox dataset, including the changes "
                    "made by STATE_UPDATE processing actions during test requests"
    )

    class Config:
        extra = "ignore"  # ignore any additional fields in input dicts
