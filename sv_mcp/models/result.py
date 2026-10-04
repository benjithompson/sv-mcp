from typing import Any, Optional, List

from pydantic import BaseModel, Field, model_validator


class BaseResult(BaseModel):
    result: Optional[Any] = Field(description="Result", default=None)
    total: Optional[int] = Field(description="Total available records", default=None)
    has_more: Optional[bool] = Field(description="More records per page to list", default=None)
    error: Optional[str] = Field(description="Error message", default=None)
    info: Optional[List[str]] = Field(description="Info messages", default=None)
    warning: Optional[List[str]] = Field(description="Warning messages", default=None)

    @model_validator(mode="after")
    def count_rows(self) -> "BaseResult":
        if isinstance(self.result, list):
            if self.total is None:
                self.total = len(self.result)
            if self.has_more is None:
                self.has_more = False
        return self

    def append_warnings(self, messages: List[str]):
        if not self.warning:
            self.warning = []
        self.warning.extend(messages)

    def append_info(self, info: List[str]):
        if not self.info:
            self.info = []
        self.info.extend(info)

    def model_dump(self, **kwargs):
        return super().model_dump(exclude_none=True, **kwargs)

    def model_dump_json(self, **kwargs):
        return super().model_dump_json(exclude_none=True, **kwargs)
