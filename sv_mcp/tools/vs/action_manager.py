from typing import Optional, Dict, Any, List, Union

import httpx
from mcp.server.fastmcp import Context

from sv_mcp.config.blazemeter import VS_TRANSACTIONS_ENDPOINT, VS_ACTIONS_ENDPOINT, WORKSPACES_ENDPOINT, VS_TOOLS_PREFIX
from sv_mcp.config.token import BzmToken
from sv_mcp.formatters.action import format_actions
from sv_mcp.models.result import BaseResult
from sv_mcp.models.vs.action_condition import ActionCondition
from sv_mcp.models.vs.web_action import WebAction
from sv_mcp.telemetry import run_tool
from sv_mcp.tools.utils import vs_api_request, error_result


class ActionManager:

    def __init__(self, token: Optional[BzmToken], ctx: Context):
        self.token = token
        self.ctx = ctx

    async def read(self, workspace_id: int, transaction_id: int, action_id: int) -> BaseResult:
        return await vs_api_request(
            self.token,
            "GET",
            f"{WORKSPACES_ENDPOINT}/{workspace_id}/{VS_TRANSACTIONS_ENDPOINT}/{transaction_id}/{VS_ACTIONS_ENDPOINT}/{action_id}",
            result_formatter=format_actions
        )

    async def list(self, workspace_id: int, transaction_id: int, sort: Optional[str] = None) -> BaseResult:
        parameters = {}
        if sort is not None:
            parameters["sort"] = sort
        return await vs_api_request(
            self.token,
            "GET",
            f"{WORKSPACES_ENDPOINT}/{workspace_id}/{VS_TRANSACTIONS_ENDPOINT}/{transaction_id}/{VS_ACTIONS_ENDPOINT}",
            result_formatter=format_actions,
            params=parameters
        )

    async def create_http_call(self, action_name: str, workspace_id: int, transaction_id: int,
                               action: WebAction, conditions: Optional[list] = None) -> BaseResult:
        action_dict = action.model_dump() if isinstance(action, WebAction) else action
        action_body = {
            "name": action_name,
            "actionType": "HTTP_CALL",
            "definition": action_dict
        }
        if conditions is not None:
            action_body["conditions"] = conditions
        return await vs_api_request(
            self.token,
            "POST",
            f"{WORKSPACES_ENDPOINT}/{workspace_id}/{VS_TRANSACTIONS_ENDPOINT}/{transaction_id}/{VS_ACTIONS_ENDPOINT}",
            result_formatter=format_actions,
            json=action_body
        )

    async def create_web_hook(self, action_name: str, workspace_id: int, transaction_id: int,
                              action: WebAction, conditions: Optional[list] = None) -> BaseResult:
        action_dict = action.model_dump() if isinstance(action, WebAction) else action
        action_body = {
            "name": action_name,
            "actionType": "WEBHOOK",
            "definition": action_dict
        }
        if conditions is not None:
            action_body["conditions"] = conditions
        return await vs_api_request(
            self.token,
            "POST",
            f"{WORKSPACES_ENDPOINT}/{workspace_id}/{VS_TRANSACTIONS_ENDPOINT}/{transaction_id}/{VS_ACTIONS_ENDPOINT}",
            result_formatter=format_actions,
            json=action_body
        )

    async def create_state_update(self, action_name: str, workspace_id: int, transaction_id: int,
                                  definition: dict, conditions: Optional[list] = None) -> BaseResult:
        action_body = {
            "name": action_name,
            "actionType": "STATE_UPDATE",
            "definition": definition
        }
        if conditions is not None:
            action_body["conditions"] = conditions
        return await vs_api_request(
            self.token,
            "POST",
            f"{WORKSPACES_ENDPOINT}/{workspace_id}/{VS_TRANSACTIONS_ENDPOINT}/{transaction_id}/{VS_ACTIONS_ENDPOINT}",
            result_formatter=format_actions,
            json=action_body
        )

    async def update(self, workspace_id: int, transaction_id: int, action_id: int,
                     action_name: Optional[str] = None, definition: Optional[Union[WebAction, dict]] = None,
                     conditions: Optional[list] = None) -> BaseResult:
        action_body: Dict[str, Any] = {"id": action_id}
        if action_name is not None:
            action_body["name"] = action_name
        if definition is not None:
            action_body["definition"] = definition.model_dump() if isinstance(definition, WebAction) else definition
        if conditions is not None:
            action_body["conditions"] = conditions
        return await vs_api_request(
            self.token,
            "PATCH",
            f"{WORKSPACES_ENDPOINT}/{workspace_id}/{VS_TRANSACTIONS_ENDPOINT}/{transaction_id}/{VS_ACTIONS_ENDPOINT}/{action_id}",
            result_formatter=format_actions,
            json=action_body
        )

    async def delete(self, workspace_id: int, transaction_id: int, action_id: int) -> BaseResult:
        result = await vs_api_request(
            self.token,
            "DELETE",
            f"{WORKSPACES_ENDPOINT}/{workspace_id}/{VS_TRANSACTIONS_ENDPOINT}/{transaction_id}/{VS_ACTIONS_ENDPOINT}/{action_id}"
        )
        if result.error:
            return result
        return BaseResult(info=[f"Action {action_id} deleted"])

    async def reorder(self, workspace_id: int, transaction_id: int, action_ids: List[int]) -> BaseResult:
        order_body = [{"id": action_id, "priority": priority}
                      for priority, action_id in enumerate(action_ids, start=1)]
        return await vs_api_request(
            self.token,
            "POST",
            f"{WORKSPACES_ENDPOINT}/{workspace_id}/{VS_TRANSACTIONS_ENDPOINT}/{transaction_id}/{VS_ACTIONS_ENDPOINT}/sort",
            result_formatter=format_actions,
            json=order_body
        )

    async def assign_asset(self, id: int, transaction_id: int, workspace_id: int, type: str, assetId: int,
                           alias: str) -> BaseResult:
        assert_type_body = {
            "assetId": assetId,
            "usageType": type,
            "alias": alias
        }
        return await vs_api_request(
            self.token,
            "PATCH",
            f"{WORKSPACES_ENDPOINT}/{workspace_id}/{VS_TRANSACTIONS_ENDPOINT}/{transaction_id}/{VS_ACTIONS_ENDPOINT}/{id}/assign-asset",
            result_formatter=format_actions,
            json=assert_type_body
        )


def register(mcp, token: Optional[BzmToken]) -> None:
    @mcp.tool(
        name=f"{VS_TOOLS_PREFIX}_action",
        description="""
        Operations on processing actions of a transaction: HTTP calls, web hooks and state updates.
        Use this when a user needs to create, read, list, update, delete or reorder actions for a transaction,
        or to make a virtual service stateful (see "Stateful virtual services (STATE_UPDATE)" below).
        Actions:
        - read: Reads a single action of a transaction with full details.
            args(dict):
                workspace_id (int): Mandatory. The id of the workspace.
                transaction_id (int): Mandatory. The id of the transaction.
                action_id (int): Mandatory. The id of the action to read.
        - list: Lists all actions of a transaction (minimal info).
            args(dict):
                workspace_id (int): Mandatory. The id of the workspace.
                transaction_id (int): Mandatory. The id of the transaction.
                sort (str): Optional. Field to sort the actions by.
        - create_http_call: Creates an http call action for transaction. This action is executed synchronously.
            args(dict): Dictionary with the following required parameters:
                action_name (str): Mandatory. The name of the action.
                workspace_id (int): Mandatory. The id of the workspace to list services from.
                transaction_id (int): Mandatory. The id of the transaction.
                action (WebAction): Mandatory. The action definition. See WebAction schema below.
                conditions (list[ActionCondition]): Optional. Conditions that must all be true for the action to run.
                    See ActionCondition schema below.
        - create_web_hook: Creates a web hook action for transaction. This action is executed asynchronously.
            args(dict): Dictionary with the following required parameters:
                action_name (str): Mandatory. The name of the action.
                workspace_id (int): Mandatory. The id of the workspace to list services from.
                transaction_id (int): Mandatory. The id of the transaction.
                action (WebAction): Mandatory. The action definition. See WebAction schema below.
                conditions (list[ActionCondition]): Optional. Conditions that must all be true for the action to run.
                    See ActionCondition schema below.
        - create_state_update: Creates a STATE_UPDATE action that changes the virtual service's service data
            each time the transaction matches. Read "Stateful virtual services (STATE_UPDATE)" below first.
            args(dict):
                action_name (str): Mandatory. The name of the action.
                workspace_id (int): Mandatory. The id of the workspace.
                transaction_id (int): Mandatory. The id of the transaction.
                definition (dict): Mandatory. The state update definition, sent to the API verbatim.
                    Copy its exact shape from a real example, as explained below.
                conditions (list[ActionCondition]): Optional. Conditions that must all be true for the action to run.
                    See ActionCondition schema below.
        - update: Updates an action of any type. Only the provided fields are changed.
            args(dict):
                workspace_id (int): Mandatory. The id of the workspace.
                transaction_id (int): Mandatory. The id of the transaction.
                action_id (int): Mandatory. The id of the action to update.
                action_name (str): Optional. The new name of the action.
                definition (WebAction | dict): Optional. The complete new definition: a WebAction for HTTP_CALL
                    and WEBHOOK actions, the state update dict for STATE_UPDATE actions. Read the action first
                    and change its current definition.
                conditions (list[ActionCondition]): Optional. The new conditions of the action.
        - delete: Deletes an action.
            args(dict):
                workspace_id (int): Mandatory. The id of the workspace.
                transaction_id (int): Mandatory. The id of the transaction.
                action_id (int): Mandatory. The id of the action to delete.
        - reorder: Sets the order in which the actions of a transaction run.
            args(dict):
                workspace_id (int): Mandatory. The id of the workspace.
                transaction_id (int): Mandatory. The id of the transaction.
                action_ids (list[int]): Mandatory. The ids of the transaction's actions in execution order;
                    the first entry runs first.
        - assign_keystore: Assign keystore asset to the action.
            args(dict):
                id (int): Mandatory. The id of the action.
                transaction_id (int): Mandatory. The id of the transaction.
                asset_id (int): Mandatory. The id of the keystore asset to assign.
                alias (str): Mandatory. The certificate alias to use.
                workspace_id (int): Mandatory. The id of the workspace.  
        - assign_certificate: Assign certificate asset to the action.
            args(dict):
                id (int): Mandatory. The id of the action.
                transaction_id (int): Mandatory. The id of the transaction.
                asset_id (int): Mandatory. The id of the certificate asset to assign.
                workspace_id (int): Mandatory. The id of the workspace.                      
        Stateful virtual services (STATE_UPDATE):
            - What it does: a STATE_UPDATE action runs after the request matches and before the response is sent.
              It modifies the virtual service's own copy of the service data. The state is shared by all clients
              and persists across stop/start. Reset it with virtual_services_state reset.
            - Change types:
                * Data entity: Store object (add a row), Update object (overwrite values in the rows matched by
                  a filter), Delete object (delete values in the rows matched by a filter).
                  Filter operators: Equals, Less than, Greater than, Starts with, Ends with, In.
                * Global variable: Update value (set it), Increment value (add a step; a negative step decrements).
                Analytics shows type names such as UPDATE_OBJECT and UPDATE_VALUE.
            - Prerequisites: the service must have service data (virtual_services_test_data) that defines the
              target entity or global variable. Data parameter names contain only letters, digits and
              underscores, and cannot start with a digit.
            - Read the state back in a transaction response with ${#each (blazeData 'entity' 'where ...')},
              ${blazeDataSize 'entity'}, ${sql '...'} (SQL data mode) or ${globalName}.
            - IMPORTANT — the definition shape is not published. Before creating a STATE_UPDATE action, copy
              the exact field names from a real example:
                * an existing STATE_UPDATE action (list or read here), or
                * virtual_services_blueprint list_transactions on the stateful demo blueprint (actionsData).
              If the API rejects a definition, read its error, fix the definition and retry.
            - Verify in the sandbox, which runs state updates: virtual_services_sandbox init, then test_request,
              then dataset_state.
            - Chaining: actions run in the order set by reorder. An HTTP call result
              ${httpcalls.<name>.response.body} can feed a later state update. conditions gate an action, and all
              of them must be true.
        WebAction Schema:
        """ + str(WebAction.model_json_schema()) + """
        ActionCondition Schema:
        """ + str(ActionCondition.model_json_schema())
    )
    async def service(action: str, args: Dict[str, Any], ctx: Context) -> BaseResult:
        action_manager = ActionManager(token, ctx)

        async def _dispatch():
            match action:
                case "read":
                    return await action_manager.read(
                        args["workspace_id"], args["transaction_id"], args["action_id"],
                    )
                case "list":
                    return await action_manager.list(
                        args["workspace_id"], args["transaction_id"], args.get("sort"),
                    )
                case "create_http_call":
                    return await action_manager.create_http_call(
                        args["action_name"], args["workspace_id"],
                        args["transaction_id"], args["action"], args.get("conditions"),
                    )
                case "create_web_hook":
                    return await action_manager.create_web_hook(
                        args["action_name"], args["workspace_id"],
                        args["transaction_id"], args["action"], args.get("conditions"),
                    )
                case "create_state_update":
                    return await action_manager.create_state_update(
                        args["action_name"], args["workspace_id"],
                        args["transaction_id"], args["definition"], args.get("conditions"),
                    )
                case "update":
                    return await action_manager.update(
                        args["workspace_id"], args["transaction_id"], args["action_id"],
                        args.get("action_name"), args.get("definition"), args.get("conditions"),
                    )
                case "delete":
                    return await action_manager.delete(
                        args["workspace_id"], args["transaction_id"], args["action_id"],
                    )
                case "reorder":
                    return await action_manager.reorder(
                        args["workspace_id"], args["transaction_id"], args["action_ids"],
                    )
                case "assign_keystore":
                    return await action_manager.assign_asset(
                        args["id"], args["transaction_id"], args["workspace_id"],
                        "CLIENT_KEYSTORE_TRUSTSTORE", args["asset_id"], args["alias"],
                    )
                case "assign_certificate":
                    return await action_manager.assign_asset(
                        args["id"], args["transaction_id"], args["workspace_id"],
                        "CLIENT_TRUSTSTORE_CERT", args["asset_id"], None,
                    )
                case _:
                    return BaseResult(error=f"Action {action} not found in action manager tool")

        try:
            return await run_tool("virtual_services_action", action, ctx, _dispatch)
        except Exception as exc:
            return error_result(exc)
