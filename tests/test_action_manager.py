import pytest
from unittest.mock import MagicMock, patch

from sv_mcp.formatters.action import format_actions
from sv_mcp.models.result import BaseResult
from sv_mcp.models.vs.web_action import WebAction
from sv_mcp.tools.vs.action_manager import ActionManager

pytestmark = pytest.mark.asyncio

CONDITIONS = [{"matcher": {"key": "${request.query.id}", "matcherName": "equals", "matchingValue": "42"}}]
WEB_ACTION = {"urlValue": "https://hooks.example.com/notify", "urlMethod": "POST", "bodyContent": None}


@pytest.fixture
def manager():
    return ActionManager(token=MagicMock(), ctx=MagicMock())


async def test_read_builds_action_endpoint(manager):
    with patch("sv_mcp.tools.vs.action_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.read(workspace_id=1, transaction_id=2, action_id=3)
    assert mock_req.call_args.args[1] == "GET"
    assert mock_req.call_args.args[2] == "/workspaces/1/transactions/2/actions/3"
    assert mock_req.call_args.kwargs["result_formatter"] is format_actions


async def test_list_builds_actions_endpoint(manager):
    with patch("sv_mcp.tools.vs.action_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.list(workspace_id=1, transaction_id=2)
    assert mock_req.call_args.args[1] == "GET"
    assert mock_req.call_args.args[2] == "/workspaces/1/transactions/2/actions"
    assert mock_req.call_args.kwargs["result_formatter"] is format_actions


async def test_list_omits_sort_when_not_provided(manager):
    with patch("sv_mcp.tools.vs.action_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.list(workspace_id=1, transaction_id=2)
    params = mock_req.call_args.kwargs.get("params") or {}
    assert "sort" not in params


async def test_list_passes_sort_when_provided(manager):
    with patch("sv_mcp.tools.vs.action_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.list(workspace_id=1, transaction_id=2, sort="name")
    assert mock_req.call_args.kwargs["params"]["sort"] == "name"


async def test_create_http_call_omits_conditions_when_not_provided(manager):
    with patch("sv_mcp.tools.vs.action_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.create_http_call("call", 1, 2, WEB_ACTION)
    assert "conditions" not in mock_req.call_args.kwargs["json"]


async def test_create_http_call_passes_conditions_when_provided(manager):
    with patch("sv_mcp.tools.vs.action_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.create_http_call("call", 1, 2, WEB_ACTION, conditions=CONDITIONS)
    assert mock_req.call_args.kwargs["json"]["conditions"] == CONDITIONS


async def test_create_web_hook_omits_conditions_when_not_provided(manager):
    with patch("sv_mcp.tools.vs.action_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.create_web_hook("hook", 1, 2, WEB_ACTION)
    assert "conditions" not in mock_req.call_args.kwargs["json"]


async def test_create_web_hook_passes_conditions_when_provided(manager):
    with patch("sv_mcp.tools.vs.action_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.create_web_hook("hook", 1, 2, WEB_ACTION, conditions=CONDITIONS)
    assert mock_req.call_args.kwargs["json"]["conditions"] == CONDITIONS


async def test_create_state_update_builds_request(manager):
    definition = {"anyKey": "any value", "nested": {"n": 1}}
    with patch("sv_mcp.tools.vs.action_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.create_state_update("store order", 1, 2, definition)
    assert mock_req.call_args.args[1] == "POST"
    assert mock_req.call_args.args[2] == "/workspaces/1/transactions/2/actions"
    assert mock_req.call_args.kwargs["result_formatter"] is format_actions
    assert mock_req.call_args.kwargs["json"] == {
        "name": "store order",
        "actionType": "STATE_UPDATE",
        "definition": definition,
    }


async def test_create_state_update_passes_conditions_when_provided(manager):
    with patch("sv_mcp.tools.vs.action_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.create_state_update("store order", 1, 2, {}, conditions=CONDITIONS)
    assert mock_req.call_args.kwargs["json"]["conditions"] == CONDITIONS


async def test_update_sends_only_id_when_nothing_provided(manager):
    with patch("sv_mcp.tools.vs.action_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.update(workspace_id=1, transaction_id=2, action_id=3)
    assert mock_req.call_args.args[1] == "PATCH"
    assert mock_req.call_args.args[2] == "/workspaces/1/transactions/2/actions/3"
    assert mock_req.call_args.kwargs["result_formatter"] is format_actions
    assert mock_req.call_args.kwargs["json"] == {"id": 3}


async def test_update_sends_provided_fields(manager):
    definition = {"anyKey": "any value"}
    with patch("sv_mcp.tools.vs.action_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.update(1, 2, 3, action_name="renamed", definition=definition, conditions=CONDITIONS)
    assert mock_req.call_args.kwargs["json"] == {
        "id": 3,
        "name": "renamed",
        "definition": definition,
        "conditions": CONDITIONS,
    }


async def test_update_dumps_web_action_definition(manager):
    with patch("sv_mcp.tools.vs.action_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.update(1, 2, 3, definition=WebAction(**WEB_ACTION))
    sent = mock_req.call_args.kwargs["json"]["definition"]
    assert isinstance(sent, dict)
    assert sent["urlValue"] == "https://hooks.example.com/notify"
    assert sent["urlMethod"] == "POST"


async def test_delete_returns_info_on_success(manager):
    with patch("sv_mcp.tools.vs.action_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=["Action deleted"], total=1)
        result = await manager.delete(workspace_id=1, transaction_id=2, action_id=3)
    assert mock_req.call_args.args[1] == "DELETE"
    assert mock_req.call_args.args[2] == "/workspaces/1/transactions/2/actions/3"
    assert "result_formatter" not in mock_req.call_args.kwargs
    assert result.error is None
    assert result.info == ["Action 3 deleted"]


async def test_delete_passes_error_through(manager):
    error = BaseResult(error="Not found")
    with patch("sv_mcp.tools.vs.action_manager.vs_api_request") as mock_req:
        mock_req.return_value = error
        result = await manager.delete(workspace_id=1, transaction_id=2, action_id=3)
    assert result is error


async def test_reorder_assigns_priorities_in_order(manager):
    with patch("sv_mcp.tools.vs.action_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.reorder(workspace_id=1, transaction_id=2, action_ids=[30, 10, 20])
    assert mock_req.call_args.args[1] == "POST"
    assert mock_req.call_args.args[2] == "/workspaces/1/transactions/2/actions/sort"
    assert mock_req.call_args.kwargs["result_formatter"] is format_actions
    assert mock_req.call_args.kwargs["json"] == [
        {"id": 30, "priority": 1},
        {"id": 10, "priority": 2},
        {"id": 20, "priority": 3},
    ]
