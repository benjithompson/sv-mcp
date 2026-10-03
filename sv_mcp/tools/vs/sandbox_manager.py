from typing import Optional, Dict, Any

import httpx
from mcp.server.fastmcp import Context

from sv_mcp.config.blazemeter import VS_SANDBOX_ENDPOINT, VS_TOOLS_PREFIX, WORKSPACES_ENDPOINT
from sv_mcp.config.token import BzmToken
from sv_mcp.formatters.sandbox import format_sandbox_test_request, format_sandbox, format_sandbox_dataset_state
from sv_mcp.models.result import BaseResult
from sv_mcp.models.vs.action_mock import ActionMock
from sv_mcp.models.vs.sandbox_dataset_state import SandboxDatasetState
from sv_mcp.models.vs.sandbox_request import SandboxRequest
from sv_mcp.models.vs.sandbox_response import SandboxResponse
from sv_mcp.telemetry import run_tool
from sv_mcp.tools.utils import vs_api_request, error_result


class SandboxManager:

    def __init__(self, token: Optional[BzmToken], ctx: Context):
        self.token = token
        self.ctx = ctx

    async def init(self, workspace_id: int, transaction_id: int) -> BaseResult:
        parameters = {
            "transactionId": transaction_id
        }
        result = await vs_api_request(
            self.token,
            "GET",
            f"{WORKSPACES_ENDPOINT}/{workspace_id}/{VS_SANDBOX_ENDPOINT}",
            result_formatter=format_sandbox,
            params=parameters
        )
        if result.error:
            return result
        # The GET loads the transaction only until the sandbox regenerates its service data; the
        # sandbox then falls back to its stored configuration. PATCH stores this transaction there.
        service_id = result.result[0].serviceId if result.result else None
        if service_id is not None:
            result = await vs_api_request(
                self.token,
                "PATCH",
                f"{WORKSPACES_ENDPOINT}/{workspace_id}/{VS_SANDBOX_ENDPOINT}",
                result_formatter=format_sandbox,
                json={"serviceId": service_id, "transactionId": transaction_id}
            )
            if result.error:
                return result
        result.append_info(["Sandbox initialized. You MUST now call 'test_request' action with the HTTP request details to actually run the test. "
                            "Processing actions on the transaction, state updates included, run during 'test_request'."])
        return result

    async def test_request(self, request: SandboxRequest, workspace_id: int) -> BaseResult:
        http_request = request.model_dump() if isinstance(request, SandboxRequest) else dict(request)
        # The API reads the request body from "body"; earlier versions of this tool documented "content".
        if "content" in http_request and "body" not in http_request:
            http_request["body"] = http_request.pop("content")
        sandbox_request = {
            "httpRequest": http_request,
        }
        return await vs_api_request(
            self.token,
            "POST",
            f"{WORKSPACES_ENDPOINT}/{workspace_id}/{VS_SANDBOX_ENDPOINT}/test-request",
            result_formatter=format_sandbox_test_request,
            json=sandbox_request
        )

    async def dataset_state(self, workspace_id: int) -> BaseResult:
        return await vs_api_request(
            self.token,
            "GET",
            f"{WORKSPACES_ENDPOINT}/{workspace_id}/{VS_SANDBOX_ENDPOINT}/dataset-state",
            result_formatter=format_sandbox_dataset_state
        )

    async def reset_dataset(self, workspace_id: int) -> BaseResult:
        result = await vs_api_request(
            self.token,
            "DELETE",
            f"{WORKSPACES_ENDPOINT}/{workspace_id}/{VS_SANDBOX_ENDPOINT}/cache"
        )
        if result.error:
            return result
        return BaseResult(info=["Sandbox dataset reset; it is regenerated from the service data on next init."])

    async def generation_status(self, workspace_id: int) -> BaseResult:
        result = await vs_api_request(
            self.token,
            "GET",
            f"{WORKSPACES_ENDPOINT}/{workspace_id}/{VS_SANDBOX_ENDPOINT}/generation-status"
        )
        if not result.error:
            result.append_info(["true means service data generation has completed and stateful tests can run; "
                                "false means it is still in progress, so call 'generation_status' again shortly."])
        return result

    async def set_action_mocks(self, workspace_id: int, action_mocks: list) -> BaseResult:
        action_mocks_body = [
            action_mock.model_dump() if isinstance(action_mock, ActionMock) else action_mock
            for action_mock in action_mocks
        ]
        return await vs_api_request(
            self.token,
            "PUT",
            f"{WORKSPACES_ENDPOINT}/{workspace_id}/{VS_SANDBOX_ENDPOINT}/actions",
            result_formatter=format_sandbox,
            json=action_mocks_body
        )


def register(mcp, token: Optional[BzmToken]) -> None:
    @mcp.tool(
        name=f"{VS_TOOLS_PREFIX}_sandbox",
        description="""
        Testing HTTP transactions in sandbox.
        Use this for HTTP transaction verification, or to re-test an existing transaction after update,
        or to verify the state changes made by a stateful transaction before deploying it.
        MESSAGING transactions are not supported in sandbox.
        IMPORTANT: Testing a transaction in the sandbox ALWAYS requires two sequential tool calls:
          1. Call `init` first — places the transaction into the sandbox environment.
          2. Then call `test_request` — sends the actual HTTP request and returns the match result.
        Both steps are mandatory. Calling only `init` does NOT test anything; you MUST follow it with `test_request`.
        Response fields: matched=true means the request was matched by the configured transaction.
        matched=false means no transaction matched — read mismatch_reasons to understand which
        matchers failed and what to fix in the DSL.
        Testing stateful transactions:
          Processing actions on the transaction run during `test_request`. STATE_UPDATE actions change the
          sandbox's own copy of the service data, which `dataset_state` returns.
          1. `init` the state-changing transaction (e.g. a POST with a STATE_UPDATE action).
          2. Call `generation_status` until it returns true. Each `init` regenerates the sandbox data, and
             template values such as ${globalName} stay unresolved until generation completes.
          3. `test_request` with the request body base64-encoded in `body`. The response of a transaction that
             reads the state (e.g. ${blazeDataSize 'entity'} or ${globalName}) shows the change directly.
          4. `init` the reading transaction (e.g. a GET that uses blazeData), wait for `generation_status`,
             then `test_request`.
          5. If a STATE_UPDATE consumes an HTTP call result (${httpcalls.<name>.response.body}), call
             `set_action_mocks` after `init` and before `test_request` so the HTTP_CALL action returns a fixed response.
          Limits: the sandbox state is not consistent between calls. `dataset_state` can return an older copy
          of the data for some seconds, and `reset_dataset` does not always clear it. Prefer the response of a
          state-reading transaction over `dataset_state`. For a final check, deploy the virtual service and use
          virtual_services_state (export_data, read_data, reset), whose state is consistent.
        Actions:
        - init: Places transaction into sandbox and stores it as the sandbox's transaction. Must be called BEFORE test_request.
            args(dict): Dictionary with the following required parameters:
                workspace_id (int): Mandatory. The id of the workspace.
                transaction_id (int): Mandatory. The id of the transaction to test.
        - test_request: Sends test request to sandbox and returns match result. Must be called AFTER init.
            args(dict): Dictionary with the following required parameters:
                request (SandboxRequest): Mandatory. The request definition (method, path, headers, body).
                workspace_id (int): Mandatory. The id of the workspace.
        - dataset_state: Returns the current sandbox dataset: data entity name -> rows.
            Use it after test_request to check the rows a STATE_UPDATE action stored, updated or deleted.
            args(dict): Dictionary with the following required parameters:
                workspace_id (int): Mandatory. The id of the workspace.
        - reset_dataset: Discards the sandbox dataset, including the state changes made by earlier test requests.
            It is regenerated from the service data on the next init.
            args(dict): Dictionary with the following required parameters:
                workspace_id (int): Mandatory. The id of the workspace.
        - generation_status: Returns [true] once service data generation for the sandbox has completed and
            stateful tests can run, [false] while it is still in progress.
            args(dict): Dictionary with the following required parameters:
                workspace_id (int): Mandatory. The id of the workspace.
        - set_action_mocks: Makes HTTP_CALL/WEBHOOK processing actions return a fixed response in the sandbox.
            Send every mock the test needs in a single call.
            args(dict): Dictionary with the following required parameters:
                workspace_id (int): Mandatory. The id of the workspace.
                action_mocks (list[ActionMock]): Mandatory. One entry per mocked action, identified by
                    actionId and actionName (see virtual_services_action list).
        Sandbox Request Schema:
        """ + str(SandboxRequest.model_json_schema()) + """
        Sandbox test_request response schema:
        """ + str(SandboxResponse.model_json_schema()) + """
        Sandbox dataset_state response schema:
        """ + str(SandboxDatasetState.model_json_schema()) + """
        Action Mock Schema:
        """ + str(ActionMock.model_json_schema())
    )
    async def sandbox(action: str, args: Dict[str, Any], ctx: Context) -> BaseResult:
        sandbox_manager = SandboxManager(token, ctx)

        async def _dispatch():
            match action:
                case "init":
                    return await sandbox_manager.init(args["workspace_id"], args["transaction_id"])
                case "test_request":
                    return await sandbox_manager.test_request(args["request"], args["workspace_id"])
                case "dataset_state":
                    return await sandbox_manager.dataset_state(args["workspace_id"])
                case "reset_dataset":
                    return await sandbox_manager.reset_dataset(args["workspace_id"])
                case "generation_status":
                    return await sandbox_manager.generation_status(args["workspace_id"])
                case "set_action_mocks":
                    return await sandbox_manager.set_action_mocks(args["workspace_id"], args["action_mocks"])
                case _:
                    return BaseResult(error=f"Action {action} not found in sandbox manager tool")

        try:
            return await run_tool("virtual_services_sandbox", action, ctx, _dispatch)
        except Exception as exc:
            return error_result(exc)
