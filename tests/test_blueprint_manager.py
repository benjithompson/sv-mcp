import pytest
from unittest.mock import MagicMock, patch

from sv_mcp.formatters.blueprint import format_blueprints, format_blueprint_transactions, format_transaction_summaries
from sv_mcp.models.result import BaseResult
from sv_mcp.tools.vs.blueprint_manager import BlueprintManager

pytestmark = pytest.mark.asyncio


@pytest.fixture
def manager():
    return BlueprintManager(token=MagicMock(), ctx=MagicMock())


async def test_list_builds_blueprints_endpoint(manager):
    with patch("sv_mcp.tools.vs.blueprint_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.list()
    assert mock_req.call_args.args[1] == "GET"
    assert mock_req.call_args.args[2] == "/blueprints"
    assert mock_req.call_args.kwargs["params"] == {"limit": 50, "skip": 0}
    assert mock_req.call_args.kwargs["result_formatter"] is format_blueprints


async def test_list_passes_keyword_and_tags_when_provided(manager):
    with patch("sv_mcp.tools.vs.blueprint_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.list(keyword="stateful", tags=["demo"], limit=10, offset=20)
    assert mock_req.call_args.kwargs["params"] == {
        "limit": 10, "skip": 20, "keyword": "stateful", "tags": ["demo"],
    }


async def test_read_builds_blueprint_endpoint(manager):
    with patch("sv_mcp.tools.vs.blueprint_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.read(blueprint_id=42)
    assert mock_req.call_args.args[1] == "GET"
    assert mock_req.call_args.args[2] == "/blueprints/42"
    assert mock_req.call_args.kwargs["params"] == {"includeTransactions": False}
    assert mock_req.call_args.kwargs["result_formatter"] is format_blueprints


async def test_read_include_transactions(manager):
    with patch("sv_mcp.tools.vs.blueprint_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.read(blueprint_id=42, include_transactions=True)
    assert mock_req.call_args.kwargs["params"] == {"includeTransactions": True}


async def test_list_transactions_builds_transactions_endpoint(manager):
    with patch("sv_mcp.tools.vs.blueprint_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.list_transactions(blueprint_id=42)
    assert mock_req.call_args.args[1] == "GET"
    assert mock_req.call_args.args[2] == "/blueprints/42/transactions"
    assert mock_req.call_args.kwargs["result_formatter"] is format_blueprint_transactions


async def test_apply_to_existing_service(manager):
    with patch("sv_mcp.tools.vs.blueprint_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.apply(blueprint_id=42, workspace_id=1, service_id=7)
    assert mock_req.call_args.args[1] == "POST"
    assert mock_req.call_args.args[2] == "/blueprints/42/apply"
    assert mock_req.call_args.kwargs["params"] == {"workspaceId": 1, "skipBlazeData": False, "serviceId": 7}
    assert mock_req.call_args.kwargs["result_formatter"] is format_transaction_summaries


async def test_apply_to_new_service(manager):
    with patch("sv_mcp.tools.vs.blueprint_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.apply(blueprint_id=42, workspace_id=1, new_service_name="orders", skip_blaze_data=True)
    assert mock_req.call_args.kwargs["params"] == {
        "workspaceId": 1, "skipBlazeData": True, "newServiceName": "orders",
    }


async def test_apply_without_target_service_returns_error_without_api_call(manager):
    with patch("sv_mcp.tools.vs.blueprint_manager.vs_api_request") as mock_req:
        result = await manager.apply(blueprint_id=42, workspace_id=1)
    mock_req.assert_not_called()
    assert "exactly one of serviceId" in result.error


async def test_apply_with_both_target_services_returns_error_without_api_call(manager):
    with patch("sv_mcp.tools.vs.blueprint_manager.vs_api_request") as mock_req:
        result = await manager.apply(blueprint_id=42, workspace_id=1, service_id=7, new_service_name="orders")
    mock_req.assert_not_called()
    assert "exactly one of serviceId" in result.error
