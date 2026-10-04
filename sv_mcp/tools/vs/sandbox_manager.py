import asyncio
import base64
import time
from typing import Optional, Dict, Any, List

import httpx
from mcp.server.fastmcp import Context

from sv_mcp.config.blazemeter import VS_SANDBOX_ENDPOINT, VS_TOOLS_PREFIX, VS_TRANSACTIONS_ENDPOINT, WORKSPACES_ENDPOINT
from sv_mcp.config.token import BzmToken
from sv_mcp.formatters.sandbox import format_sandbox_test_request, format_sandbox, format_sandbox_dataset_state
from sv_mcp.models.result import BaseResult
from sv_mcp.models.vs.action_mock import ActionMock
from sv_mcp.models.vs.sandbox_dataset_state import SandboxDatasetState
from sv_mcp.models.vs.sandbox_request import SandboxRequest
from sv_mcp.models.vs.sandbox_response import SandboxResponse
from sv_mcp.telemetry import run_tool
from sv_mcp.tools.utils import vs_api_request, error_result


def _is_base64(value: Any) -> bool:
    try:
        base64.b64decode(value, validate=True)
        return True
    except (TypeError, ValueError):
        return False


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
        if service_id is None:
            result.append_warnings(["The sandbox returned no serviceId, so the transaction was not stored in its "
                                    "configuration. It can fall back to its stored transaction after the next "
                                    "data regeneration."])
        else:
            stored = await self._store(workspace_id, service_id, transaction_id)
            if stored.error:
                return stored
            if stored.result:
                result = stored
        result.append_info(["Sandbox initialized. You MUST now call 'test_request' action with the HTTP request details to actually run the test. "
                            "Processing actions on the transaction, state updates included, run during 'test_request'."])
        return result

    async def _store(self, workspace_id: int, service_id: int, transaction_id: int) -> BaseResult:
        return await vs_api_request(
            self.token,
            "PATCH",
            f"{WORKSPACES_ENDPOINT}/{workspace_id}/{VS_SANDBOX_ENDPOINT}",
            result_formatter=format_sandbox,
            json={"serviceId": service_id, "transactionId": transaction_id}
        )

    async def _service_id_of(self, workspace_id: int, transaction_id: int) -> Optional[int]:
        result = await vs_api_request(
            self.token,
            "GET",
            f"{WORKSPACES_ENDPOINT}/{workspace_id}/{VS_TRANSACTIONS_ENDPOINT}/{transaction_id}"
        )
        if result.error or not result.result or not isinstance(result.result[0], dict):
            return None
        return result.result[0].get("serviceId")

    async def hold_transaction(self, workspace_id: int, transaction_id: int,
                               service_id: Optional[int] = None) -> BaseResult:
        check_result = await self.check_transaction(workspace_id, transaction_id)
        if not check_result.error:
            return check_result
        # When the data generation started by init finishes, the sandbox falls back to an older stored
        # transaction and drops the PATCH sent by init. Storing the transaction again after that keeps it.
        if service_id is None:
            service_id = await self._service_id_of(workspace_id, transaction_id)
            if service_id is None:
                return check_result
        stored = await self._store(workspace_id, service_id, transaction_id)
        if stored.error:
            return stored
        held = await self.check_transaction(workspace_id, transaction_id)
        if not held.error:
            held.append_info([f"The sandbox had fallen back to another transaction; transaction {transaction_id} "
                              "was stored again."])
        return held

    async def check_transaction(self, workspace_id: int, transaction_id: int) -> BaseResult:
        result = await vs_api_request(
            self.token,
            "GET",
            f"{WORKSPACES_ENDPOINT}/{workspace_id}/{VS_SANDBOX_ENDPOINT}",
            result_formatter=format_sandbox
        )
        if result.error:
            return result
        # There is one sandbox per user, so another session can replace the transaction after init.
        held = result.result[0].transactionId if result.result else None
        if held != transaction_id:
            return BaseResult(error=f"The sandbox now holds transaction {held}, not {transaction_id}. Another session "
                                    "or a stored configuration replaced it. Call init again.")
        return result

    async def test_request(self, request: Dict[str, Any], workspace_id: int,
                           transaction_id: Optional[int] = None) -> BaseResult:
        if not isinstance(request, dict):
            return BaseResult(error="request must be an object with the HTTP request details. See SandboxRequest schema.")
        http_request = dict(request)
        # The API reads the request body from "body"; earlier versions of this tool documented "content".
        content = http_request.pop("content", None)
        if "body" not in http_request and content is not None:
            http_request["body"] = content
        if http_request.get("body") is not None and not _is_base64(http_request["body"]):
            return BaseResult(error="request.body must be base64-encoded.")
        if transaction_id is not None:
            held = await self.hold_transaction(workspace_id, transaction_id)
            if held.error:
                return held
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

    async def wait_for_generation(self, workspace_id: int, timeout: float = 60.0, interval: float = 2.0) -> BaseResult:
        deadline = time.monotonic() + timeout
        while True:
            status = await self.generation_status(workspace_id)
            if status.error or status.result == [True]:
                return status
            if time.monotonic() >= deadline:
                return BaseResult(error=f"Sandbox data generation did not finish within {timeout:g} s.")
            await asyncio.sleep(interval)

    async def set_action_mocks(self, workspace_id: int, action_mocks: List[Dict[str, Any]]) -> BaseResult:
        if not isinstance(action_mocks, list) or not all(isinstance(m, dict) for m in action_mocks):
            return BaseResult(error="action_mocks must be a list of ActionMock objects.")
        return await vs_api_request(
            self.token,
            "PUT",
            f"{WORKSPACES_ENDPOINT}/{workspace_id}/{VS_SANDBOX_ENDPOINT}/actions",
            result_formatter=format_sandbox,
            json=action_mocks
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
          Limits: when the data generation started by `init` finishes, the sandbox can fall back to an older
          stored transaction. There is also one sandbox per user, so another session that calls `init` replaces
          the transaction. Pass transaction_id to `test_request`: it stores the transaction again if the sandbox
          holds another one, and sends the request only when the sandbox holds it.
          The sandbox state is not consistent between calls.
          `dataset_state` can return an older copy of the data for some seconds, and `reset_dataset` does not
          always clear it. Prefer the response of a state-reading transaction over `dataset_state`. For a final
          check, deploy the virtual service and use virtual_services_state (export_data, read_data, reset), whose
          state is consistent.
        Actions:
        - init: Places transaction into sandbox and stores it as the sandbox's transaction. Must be called BEFORE test_request.
            args(dict): Dictionary with the following required parameters:
                workspace_id (int): Mandatory. The id of the workspace.
                transaction_id (int): Mandatory. The id of the transaction to test.
        - test_request: Sends test request to sandbox and returns match result. Must be called AFTER init.
            args(dict): Dictionary with the following required parameters:
                request (SandboxRequest): Mandatory. The request definition (method, path, headers, body).
                workspace_id (int): Mandatory. The id of the workspace.
                transaction_id (int): Optional. The id of the transaction passed to init. When set and the
                    sandbox holds another transaction, the tool stores this one again; the request is sent only
                    if the sandbox then holds it.
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
                    return await sandbox_manager.test_request(
                        args["request"], args["workspace_id"], args.get("transaction_id")
                    )
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
            return error_result(exc, action)
