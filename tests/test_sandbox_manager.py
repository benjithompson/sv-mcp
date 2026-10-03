import pytest
from unittest.mock import MagicMock, patch

from sv_mcp.formatters.sandbox import format_sandbox, format_sandbox_dataset_state
from sv_mcp.models.result import BaseResult
from sv_mcp.models.vs.action_mock import ActionMock
from sv_mcp.models.vs.http_header import HttpHeader
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


async def test_set_action_mocks_puts_list_body(manager):
    action_mocks = [{"actionName": "lookup", "actionId": 7, "statusCode": 200, "body": '{"ok": true}'}]
    with patch("sv_mcp.tools.vs.sandbox_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.set_action_mocks(workspace_id=1, action_mocks=action_mocks)
    assert mock_req.call_args.args[1] == "PUT"
    assert mock_req.call_args.args[2] == "/workspaces/1/sandbox/actions"
    assert mock_req.call_args.kwargs["json"] == action_mocks
    assert mock_req.call_args.kwargs["result_formatter"] is format_sandbox


async def test_set_action_mocks_dumps_model_instances(manager):
    action_mock = ActionMock(
        actionName="lookup", actionId=7, statusCode=200,
        headers=[HttpHeader(name="Content-Type", value="application/json")], body='{"ok": true}',
    )
    raw_mock = {"actionName": "notify", "statusCode": 204}
    with patch("sv_mcp.tools.vs.sandbox_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.set_action_mocks(workspace_id=1, action_mocks=[action_mock, raw_mock])
    body = mock_req.call_args.kwargs["json"]
    assert body[0] == action_mock.model_dump()
    assert body[0]["headers"] == [{"name": "Content-Type", "value": "application/json"}]
    assert body[1] == raw_mock
