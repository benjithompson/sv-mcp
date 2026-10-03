from typing import Optional, Dict, Any, List

from mcp.server.fastmcp import Context

from sv_mcp.config.blazemeter import VS_TOOLS_PREFIX, VS_BLUEPRINTS_ENDPOINT
from sv_mcp.config.token import BzmToken
from sv_mcp.formatters.blueprint import format_blueprints, format_blueprint_transactions, format_transaction_summaries
from sv_mcp.models.result import BaseResult
from sv_mcp.models.vs.blueprint import Blueprint, BlueprintTransaction, TransactionSummary
from sv_mcp.telemetry import run_tool
from sv_mcp.tools.utils import vs_api_request, error_result


class BlueprintManager:

    def __init__(self, token: Optional[BzmToken], ctx: Context):
        self.token = token
        self.ctx = ctx

    async def list(
            self,
            keyword: Optional[str] = None,
            tags: Optional[List[str]] = None,
            limit: int = 50,
            offset: int = 0,
    ) -> BaseResult:
        params: Dict[str, Any] = {"limit": limit, "skip": offset}
        if keyword is not None:
            params["keyword"] = keyword
        if tags is not None:
            params["tags"] = tags
        return await vs_api_request(
            self.token, "GET", VS_BLUEPRINTS_ENDPOINT,
            result_formatter=format_blueprints, params=params
        )

    async def read(self, blueprint_id: int, include_transactions: bool = False) -> BaseResult:
        return await vs_api_request(
            self.token, "GET", f"{VS_BLUEPRINTS_ENDPOINT}/{blueprint_id}",
            result_formatter=format_blueprints, params={"includeTransactions": include_transactions}
        )

    async def list_transactions(self, blueprint_id: int) -> BaseResult:
        return await vs_api_request(
            self.token, "GET", f"{VS_BLUEPRINTS_ENDPOINT}/{blueprint_id}/transactions",
            result_formatter=format_blueprint_transactions
        )

    async def apply(
            self,
            blueprint_id: int,
            workspace_id: int,
            service_id: Optional[int] = None,
            new_service_name: Optional[str] = None,
            skip_blaze_data: bool = False,
    ) -> BaseResult:
        if (service_id is None) == (new_service_name is None):
            return BaseResult(error="Provide exactly one of serviceId (existing service) or newServiceName (new service).")
        params: Dict[str, Any] = {"workspaceId": workspace_id, "skipBlazeData": skip_blaze_data}
        if service_id is not None:
            params["serviceId"] = service_id
        if new_service_name is not None:
            params["newServiceName"] = new_service_name
        return await vs_api_request(
            self.token, "POST", f"{VS_BLUEPRINTS_ENDPOINT}/{blueprint_id}/apply",
            result_formatter=format_transaction_summaries, params=params
        )


def register(mcp, token: Optional[BzmToken]) -> None:
    @mcp.tool(
        name=f"{VS_TOOLS_PREFIX}_blueprint",
        description="""
        Operations on blueprints: BlazeMeter's ready-made service templates, which bundle transactions (with
        their processing actions) and service data.
        Use this when a user wants to start from a ready-made service.
        Blueprints are not workspace-scoped; only apply needs a workspace_id.

        Actions:
        - list: List blueprints.
            args(dict):
                keyword (str): Optional. Search text, e.g. "stateful".
                tags (list[str]): Optional. Filter by blueprint tags.
                limit (int, default=50): The number of blueprints to list.
                offset (int, default=0): Number of blueprints to skip.
        - read: Read a blueprint.
            args(dict):
                id (int): Mandatory. The id of the blueprint.
                includeTransactions (bool, default=false): Also return the blueprint's transactions with their actionsData.
        - list_transactions: List the transactions of a blueprint with their DSL and processing actions
            (actionsData, returned verbatim).
            args(dict):
                id (int): Mandatory. The id of the blueprint.
        - apply: Apply a blueprint. Creates the blueprint's transactions in an existing service (serviceId) or in
            a new service (newServiceName), together with its service data unless skipBlazeData=true.
            Returns the created transactions; their serviceId is the target service.
            The transactions are real, but not part of any virtual service yet: assign them with
            virtual_services_virtual_service assign_transactions.
            args(dict):
                id (int): Mandatory. The id of the blueprint.
                workspace_id (int): Mandatory. The id of the workspace to create the transactions in.
                serviceId (int): Optional. The id of an existing service. Provide exactly one of serviceId or newServiceName.
                newServiceName (str): Optional. The name of a new service to create.
                skipBlazeData (bool, default=false): true to create only the transactions, without the service data.
        Blueprint Schema:
        """ + str(Blueprint.model_json_schema()) + """
        BlueprintTransaction Schema:
        """ + str(BlueprintTransaction.model_json_schema()) + """
        apply result schema:
        """ + str(TransactionSummary.model_json_schema())
    )
    async def blueprint(action: str, args: Dict[str, Any], ctx: Context) -> BaseResult:
        blueprint_manager = BlueprintManager(token, ctx)

        async def _dispatch():
            match action:
                case "list":
                    return await blueprint_manager.list(
                        args.get("keyword"), args.get("tags"), args.get("limit", 50), args.get("offset", 0)
                    )
                case "read":
                    return await blueprint_manager.read(args["id"], args.get("includeTransactions", False))
                case "list_transactions":
                    return await blueprint_manager.list_transactions(args["id"])
                case "apply":
                    return await blueprint_manager.apply(
                        args["id"], args["workspace_id"], args.get("serviceId"),
                        args.get("newServiceName"), args.get("skipBlazeData", False),
                    )
                case _:
                    return BaseResult(error=f"Action {action} not found in blueprint manager tool")

        try:
            return await run_tool("virtual_services_blueprint", action, ctx, _dispatch)
        except Exception as exc:
            return error_result(exc)
