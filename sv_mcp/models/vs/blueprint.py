from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


class BlueprintTransaction(BaseModel):
    id: Optional[int] = Field(None, description="The unique identifier of the blueprint transaction")
    name: Optional[str] = Field(None, description="The name of the transaction")
    type: Optional[str] = Field(None, description="Transaction type: HTTP or MESSAGING")
    description: Optional[str] = Field(None, description="Human-readable description")
    dsl: Optional[Dict[str, Any]] = Field(
        None, description="Transaction DSL as stored in the blueprint (GenericDsl for HTTP, MessagingDsl for MESSAGING)"
    )
    sampleBody: Optional[str] = Field(None, description="Example request body")
    sqlHint: Optional[str] = Field(
        None,
        description=(
            "SQLite query used to select service data rows for this transaction when the virtual service "
            "uses SQL data mode, e.g. select * from users where email = '${request.query.email}'"
        )
    )
    actionsData: Optional[List[Dict[str, Any]]] = Field(
        [],
        description=(
            "Processing actions of the transaction, returned verbatim; STATE_UPDATE entries show "
            "the exact definition shape to reuse"
        )
    )

    class Config:
        extra = "ignore"


class Blueprint(BaseModel):
    id: Optional[int] = Field(None, description="The unique identifier of the blueprint")
    name: Optional[str] = Field(None, description="The name of the blueprint")
    description: Optional[str] = Field(None, description="Human-readable description")
    tags: Optional[List[str]] = Field([], description="Tags for filtering")
    scope: Optional[str] = Field(None, description="Visibility scope: GLOBAL, ACCOUNT or PRIVATE")
    hasBlazeData: Optional[bool] = Field(
        None, description="True when the blueprint includes service data, copied by apply unless skipBlazeData=true"
    )
    transactionCount: Optional[int] = Field(None, description="Number of transactions in the blueprint")
    transactions: Optional[List[BlueprintTransaction]] = Field(
        [], description="Blueprint transactions; read returns them only with includeTransactions=true"
    )

    class Config:
        extra = "ignore"


class TransactionSummary(BaseModel):
    id: Optional[int] = Field(None, description="The unique identifier of the created transaction")
    name: Optional[str] = Field(None, description="The name of the transaction")
    type: Optional[str] = Field(None, description="Transaction type: HTTP or MESSAGING")
    serviceId: Optional[int] = Field(
        None, description="The unique identifier of the service where the transaction was created"
    )

    class Config:
        extra = "ignore"
