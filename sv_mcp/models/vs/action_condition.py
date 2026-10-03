from pydantic import BaseModel, Field

from sv_mcp.models.vs.matcher_dsl import MatcherDsl


class ActionCondition(BaseModel):
    matcher: MatcherDsl = Field(
        ...,
        description=(
            "Condition that must be true for the action to run. "
            "matcher.key is the expression to evaluate in ${...} form, e.g. '${request.query.id}'; "
            "matcherName is the operator, e.g. 'equals'; matchingValue is the value to compare against."
        )
    )

    class Config:
        extra = "ignore"  # ignore any additional fields in input dicts
