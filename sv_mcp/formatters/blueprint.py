from typing import List, Any, Optional

from sv_mcp.models.vs.blueprint import Blueprint, BlueprintTransaction, TransactionSummary


def format_blueprints(blueprints: List[Any], params: Optional[dict] = None) -> List[Blueprint]:
    return [
        Blueprint(
            id=b.get("id"),
            name=b.get("name"),
            description=b.get("description"),
            tags=b.get("tags") or [],
            scope=b.get("scope"),
            hasBlazeData=b.get("hasBlazeData"),
            transactionCount=b.get("transactionCount"),
            transactions=format_blueprint_transactions(b.get("transactions") or []),
        )
        for b in blueprints
    ]


def format_blueprint_transactions(transactions: List[Any], params: Optional[dict] = None) -> List[BlueprintTransaction]:
    return [
        BlueprintTransaction(
            id=t.get("id"),
            name=t.get("name"),
            type=t.get("type"),
            description=t.get("description"),
            dsl=t.get("dsl"),
            sampleBody=t.get("sampleBody"),
            sqlHint=t.get("sqlHint"),
            # BlueprintTransactionDto names the action list "actionsData"; GET /blueprints/{id}/transactions
            # is declared as returning TransactionDto, which names the same ActionDto list "actions"
            actionsData=t.get("actionsData") or t.get("actions") or [],
        )
        for t in transactions
    ]


def format_transaction_summaries(transactions: List[Any], params: Optional[dict] = None) -> List[TransactionSummary]:
    return [
        TransactionSummary(
            id=t.get("id"),
            name=t.get("name"),
            type=t.get("type"),
            serviceId=t.get("serviceId"),
        )
        for t in transactions
    ]
