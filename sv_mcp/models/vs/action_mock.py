from typing import Optional, List

from pydantic import BaseModel, Field

from sv_mcp.models.vs.http_header import HttpHeader


class ActionMock(BaseModel):
    """Mocked response for an HTTP_CALL/WEBHOOK processing action while testing in the sandbox."""
    actionName: Optional[str] = Field(
        None,
        description="Name of the processing action to mock"
    )
    actionId: Optional[int] = Field(
        None,
        description="Id of the processing action to mock"
    )
    statusCode: Optional[int] = Field(
        None,
        description="HTTP status code the mocked action returns, e.g. 200"
    )
    headers: Optional[List[HttpHeader]] = Field(
        [],
        description="List of response headers the mocked action returns"
    )
    body: Optional[str] = Field(
        None,
        description="Response body as the action would receive it"
    )

    class Config:
        extra = "ignore"  # ignore any additional fields in input dicts
