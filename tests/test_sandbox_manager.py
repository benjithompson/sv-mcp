import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sv_mcp.formatters.sandbox import format_sandbox, format_sandbox_dataset_state
from sv_mcp.models.result import BaseResult
from sv_mcp.tools.vs.sandbox_manager import SandboxManager

pytestmark = pytest.mark.asyncio


@pytest.fixture
def manager():
    return SandboxManager(token=MagicMock(), ctx=MagicMock())


async def test_init_info_mentions_processing_actions(manager):
    with patch("sv_mcp.tools.vs.sandbox_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        result = await manager.init(workspace_id=1, transaction_id=2)
    assert mock_req.call_args.args[1] == "GET"
    assert mock_req.call_args.args[2] == "/workspaces/1/sandbox"
    assert mock_req.call_args.kwargs["params"] == {"transactionId": 2}
    assert "test_request" in result.info[0]
    assert "Processing actions" in result.info[0]


async def test_init_stores_transaction_in_sandbox_configuration(manager):
    with patch("sv_mcp.tools.vs.sandbox_manager.vs_api_request") as mock_req:
        mock_req.side_effect = [
            BaseResult(result=format_sandbox([{"userId": 9, "serviceId": 5, "transactionId": 2}])),
            BaseResult(result=format_sandbox([{"userId": 9, "serviceId": 5, "transactionId": 2}])),
        ]
        result = await manager.init(workspace_id=1, transaction_id=2)
    get_call, patch_call = mock_req.call_args_list
    assert get_call.args[1] == "GET"
    assert patch_call.args[1] == "PATCH"
    assert patch_call.args[2] == "/workspaces/1/sandbox"
    assert patch_call.kwargs["json"] == {"serviceId": 5, "transactionId": 2}
    assert result.result[0].transactionId == 2
    assert "test_request" in result.info[0]


async def test_init_returns_patch_error(manager):
    with patch("sv_mcp.tools.vs.sandbox_manager.vs_api_request") as mock_req:
        mock_req.side_effect = [
            BaseResult(result=format_sandbox([{"serviceId": 5, "transactionId": 2}])),
            BaseResult(error="Not found: transaction"),
        ]
        result = await manager.init(workspace_id=1, transaction_id=2)
    assert result.error == "Not found: transaction"


async def test_init_keeps_get_result_when_patch_returns_nothing(manager):
    sandbox = format_sandbox([{"serviceId": 5, "transactionId": 2}])
    with patch("sv_mcp.tools.vs.sandbox_manager.vs_api_request") as mock_req:
        mock_req.side_effect = [BaseResult(result=sandbox), BaseResult()]
        result = await manager.init(workspace_id=1, transaction_id=2)
    assert result.result == sandbox


async def test_init_warns_when_sandbox_has_no_service_id(manager):
    with patch("sv_mcp.tools.vs.sandbox_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=format_sandbox([{"transactionId": 2}]))
        result = await manager.init(workspace_id=1, transaction_id=2)
    assert mock_req.call_count == 1
    assert "no serviceId" in result.warning[0]


async def test_init_returns_get_error_without_patch(manager):
    with patch("sv_mcp.tools.vs.sandbox_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(error="Not found: transaction")
        result = await manager.init(workspace_id=1, transaction_id=2)
    assert mock_req.call_count == 1
    assert result.error == "Not found: transaction"


async def test_test_request_sends_body(manager):
    request = {"method": "POST", "path": "/orders", "name": "svc", "body": "eyJpZCI6MX0="}
    with patch("sv_mcp.tools.vs.sandbox_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.test_request(request, workspace_id=1)
    assert mock_req.call_args.args[2] == "/workspaces/1/sandbox/test-request"
    assert mock_req.call_args.kwargs["json"] == {"httpRequest": request}


async def test_test_request_maps_legacy_content_to_body(manager):
    request = {"method": "POST", "path": "/orders", "name": "svc", "content": "eyJpZCI6MX0="}
    with patch("sv_mcp.tools.vs.sandbox_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.test_request(request, workspace_id=1)
    sent = mock_req.call_args.kwargs["json"]["httpRequest"]
    assert sent["body"] == "eyJpZCI6MX0="
    assert "content" not in sent
    assert "content" in request


async def test_test_request_drops_content_when_body_is_given(manager):
    request = {"method": "POST", "path": "/orders", "name": "svc", "body": "eyJpZCI6MX0=", "content": "eA=="}
    with patch("sv_mcp.tools.vs.sandbox_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.test_request(request, workspace_id=1)
    sent = mock_req.call_args.kwargs["json"]["httpRequest"]
    assert sent["body"] == "eyJpZCI6MX0="
    assert "content" not in sent


async def test_test_request_rejects_non_object_request(manager):
    with patch("sv_mcp.tools.vs.sandbox_manager.vs_api_request") as mock_req:
        result = await manager.test_request('{"method": "GET"}', workspace_id=1)
    mock_req.assert_not_called()
    assert result.error.startswith("request must be an object")


async def test_test_request_rejects_body_that_is_not_base64(manager):
    request = {"method": "POST", "path": "/orders", "name": "svc", "body": '{"id": 1}'}
    with patch("sv_mcp.tools.vs.sandbox_manager.vs_api_request") as mock_req:
        result = await manager.test_request(request, workspace_id=1)
    mock_req.assert_not_called()
    assert result.error == "request.body must be base64-encoded."


async def test_dataset_state_builds_endpoint(manager):
    with patch("sv_mcp.tools.vs.sandbox_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.dataset_state(workspace_id=1)
    assert mock_req.call_args.args[1] == "GET"
    assert mock_req.call_args.args[2] == "/workspaces/1/sandbox/dataset-state"
    assert mock_req.call_args.kwargs["result_formatter"] is format_sandbox_dataset_state


async def test_reset_dataset_returns_info_on_success(manager):
    with patch("sv_mcp.tools.vs.sandbox_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[None], total=1)
        result = await manager.reset_dataset(workspace_id=1)
    assert mock_req.call_args.args[1] == "DELETE"
    assert mock_req.call_args.args[2] == "/workspaces/1/sandbox/cache"
    assert "result_formatter" not in mock_req.call_args.kwargs
    assert result.error is None
    assert result.result is None
    assert result.info == ["Sandbox dataset reset; it is regenerated from the service data on next init."]


async def test_reset_dataset_passes_error_through(manager):
    with patch("sv_mcp.tools.vs.sandbox_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(error="Not found")
        result = await manager.reset_dataset(workspace_id=1)
    assert result.error == "Not found"
    assert result.info is None


async def test_generation_status_returns_result_with_info(manager):
    with patch("sv_mcp.tools.vs.sandbox_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[True], total=1)
        result = await manager.generation_status(workspace_id=1)
    assert mock_req.call_args.args[1] == "GET"
    assert mock_req.call_args.args[2] == "/workspaces/1/sandbox/generation-status"
    assert "result_formatter" not in mock_req.call_args.kwargs
    assert result.result == [True]
    assert any("stateful tests can run" in i for i in result.info)


async def test_generation_status_error_has_no_info(manager):
    with patch("sv_mcp.tools.vs.sandbox_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(error="Not found")
        result = await manager.generation_status(workspace_id=1)
    assert result.error == "Not found"
    assert result.info is None


async def test_wait_for_generation_polls_until_true(manager):
    with patch("sv_mcp.tools.vs.sandbox_manager.vs_api_request") as mock_req, \
            patch("sv_mcp.tools.vs.sandbox_manager.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        mock_req.side_effect = [BaseResult(result=[False]), BaseResult(result=[True])]
        result = await manager.wait_for_generation(workspace_id=1)
    assert mock_req.call_count == 2
    mock_sleep.assert_awaited_once()
    assert result.error is None
    assert result.result == [True]


async def test_wait_for_generation_times_out(manager):
    with patch("sv_mcp.tools.vs.sandbox_manager.vs_api_request") as mock_req, \
            patch("sv_mcp.tools.vs.sandbox_manager.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        mock_req.return_value = BaseResult(result=[False])
        result = await manager.wait_for_generation(workspace_id=1, timeout=0)
    mock_sleep.assert_not_awaited()
    assert result.error == "Sandbox data generation did not finish within 0 s."


async def test_wait_for_generation_passes_error_through(manager):
    with patch("sv_mcp.tools.vs.sandbox_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(error="Not found")
        result = await manager.wait_for_generation(workspace_id=1)
    assert mock_req.call_count == 1
    assert result.error == "Not found"


async def test_set_action_mocks_puts_list_body(manager):
    action_mocks = [{"actionName": "lookup", "actionId": 7, "statusCode": 200, "body": '{"ok": true}'}]
    with patch("sv_mcp.tools.vs.sandbox_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.set_action_mocks(workspace_id=1, action_mocks=action_mocks)
    assert mock_req.call_args.args[1] == "PUT"
    assert mock_req.call_args.args[2] == "/workspaces/1/sandbox/actions"
    assert mock_req.call_args.kwargs["json"] == action_mocks
    assert mock_req.call_args.kwargs["result_formatter"] is format_sandbox


async def test_set_action_mocks_rejects_non_list(manager):
    with patch("sv_mcp.tools.vs.sandbox_manager.vs_api_request") as mock_req:
        result = await manager.set_action_mocks(workspace_id=1, action_mocks={"actionId": 1})
    mock_req.assert_not_called()
    assert result.error == "action_mocks must be a list of ActionMock objects."
