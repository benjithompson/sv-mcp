from typing import Optional, List

from pydantic import BaseModel, Field

from sv_mcp.models.vs.action_mock import ActionMock


class Sandbox(BaseModel):
    userId: Optional[int] = Field(
        None,
        description="User id"
    )
    serviceId: Optional[int] = Field(
        None,
        description="Service id"
    )
    transactionId: Optional[int] = Field(
        None,
        description="Transaction id"
    )
    actionMocks: Optional[List[ActionMock]] = Field(
        [],
        description="Processing action responses currently mocked in the sandbox (see set_action_mocks)"
    )

    class Config:
        extra = "ignore"  # ignore any additional fields in input dicts
