import httpx
import pytest
from unittest.mock import MagicMock, patch

from sv_mcp.models.result import BaseResult
from sv_mcp.tools.vs.virtual_service_manager import VirtualServiceManager

pytestmark = pytest.mark.asyncio

_RealAsyncClient = httpx.AsyncClient


@pytest.fixture
def manager():
    token = MagicMock()
    token.as_basic_auth.return_value = "Basic abc"
    return VirtualServiceManager(token=token, ctx=MagicMock())


async def test_configure_without_keep_blaze_data_sends_no_params(manager):
    with patch("sv_mcp.tools.vs.base_virtual_service_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.configure(workspace_id=1, vs_id=55)
    call = mock_req.call_args
    assert call.args[1] == "GET"
    assert call.args[2] == "/workspaces/1/service-mocks/55/configure"
    assert call.kwargs["params"] == {}


async def test_configure_with_keep_blaze_data(manager):
    with patch("sv_mcp.tools.vs.base_virtual_service_manager.vs_api_request") as mock_req:
        mock_req.return_value = BaseResult(result=[])
        await manager.configure(workspace_id=1, vs_id=55, keep_blaze_data=True)
    call = mock_req.call_args
    assert call.args[2] == "/workspaces/1/service-mocks/55/configure"
    assert call.kwargs["params"] == {"keepBlazeData": True}


async def test_configure_without_keep_blaze_data_request_has_no_query_string(manager):
    """The request on the wire is unchanged for existing callers: no keepBlazeData, no '?'."""
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"result": {"trackingId": "uuid-track-001"}})

    def client_factory(**kwargs):
        kwargs.pop("http2", None)
        return _RealAsyncClient(transport=httpx.MockTransport(handler), **kwargs)

    with patch("sv_mcp.tools.utils.httpx.AsyncClient", client_factory):
        result = await manager.configure(workspace_id=1, vs_id=55)
    assert requests[0].url.path.endswith("/workspaces/1/service-mocks/55/configure")
    assert requests[0].url.query == b""
    assert result.result[0].tracking_id == "uuid-track-001"
