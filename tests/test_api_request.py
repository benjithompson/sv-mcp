from unittest.mock import MagicMock, patch

import httpx

from sv_mcp.tools.utils import vs_api_request

_RealAsyncClient = httpx.AsyncClient


def _client_returning(response: httpx.Response):
    """Patch target for httpx.AsyncClient: same client, but every request gets `response`."""
    def factory(**kwargs):
        kwargs.pop("http2", None)
        return _RealAsyncClient(transport=httpx.MockTransport(lambda request: response), **kwargs)
    return factory


def _token():
    token = MagicMock()
    token.as_basic_auth.return_value = "Basic abc"
    return token


async def test_json_envelope_result_is_unwrapped():
    response = httpx.Response(200, json={"result": [{"id": 1}], "total": 1, "skip": 0, "limit": 1})
    with patch("sv_mcp.tools.utils.httpx.AsyncClient", _client_returning(response)):
        result = await vs_api_request(_token(), "GET", "/things")
    assert result.result == [{"id": 1}]
    assert result.error is None


async def test_plain_text_body_is_returned_as_result_not_crash():
    response = httpx.Response(200, text="Action deleted")
    with patch("sv_mcp.tools.utils.httpx.AsyncClient", _client_returning(response)):
        result = await vs_api_request(_token(), "DELETE", "/things/1")
    assert result.result == ["Action deleted"]
    assert result.error is None


async def test_bare_json_string_body_is_returned_as_result_not_crash():
    response = httpx.Response(200, json="deleted")
    with patch("sv_mcp.tools.utils.httpx.AsyncClient", _client_returning(response)):
        result = await vs_api_request(_token(), "DELETE", "/things/1")
    assert result.result == ["deleted"]
    assert result.total == 1


async def test_bare_json_array_body_is_formatted_like_an_envelope_result():
    response = httpx.Response(200, json=[{"id": 1}, {"id": 2}])
    with patch("sv_mcp.tools.utils.httpx.AsyncClient", _client_returning(response)):
        result = await vs_api_request(
            _token(), "GET", "/things", result_formatter=lambda items, params: [i["id"] for i in items]
        )
    assert result.result == [1, 2]


async def test_empty_body_returns_empty_result():
    response = httpx.Response(204)
    with patch("sv_mcp.tools.utils.httpx.AsyncClient", _client_returning(response)):
        result = await vs_api_request(_token(), "DELETE", "/things/1")
    assert result.result is None
    assert result.error is None


async def test_single_object_response_has_no_more():
    # /user returns one object without skip/limit
    response = httpx.Response(200, json={"result": {"id": 1}})
    with patch("sv_mcp.tools.utils.httpx.AsyncClient", _client_returning(response)):
        result = await vs_api_request(_token(), "GET", "/user")
    assert result.total == 1
    assert result.has_more is False


async def test_has_more_counts_returned_rows():
    first_page = httpx.Response(200, json={"result": [{"id": 1}, {"id": 2}], "total": 3, "skip": 0, "limit": 2})
    with patch("sv_mcp.tools.utils.httpx.AsyncClient", _client_returning(first_page)):
        assert (await vs_api_request(_token(), "GET", "/things")).has_more is True
    last_page = httpx.Response(200, json={"result": [{"id": 3}], "total": 3, "skip": 2, "limit": 2})
    with patch("sv_mcp.tools.utils.httpx.AsyncClient", _client_returning(last_page)):
        assert (await vs_api_request(_token(), "GET", "/things")).has_more is False


async def test_401_names_the_api_key_source():
    token = _token()
    token.source = "key file /keys/api-key.json"
    response = httpx.Response(401, json={"error": "Unauthorized"})
    with patch("sv_mcp.tools.utils.httpx.AsyncClient", _client_returning(response)):
        result = await vs_api_request(token, "GET", "/things")
    assert result.error == "Invalid credentials: Unauthorized (API key source: key file /keys/api-key.json)"


async def test_401_without_known_source():
    token = _token()
    token.source = None
    response = httpx.Response(401, json={"error": "Unauthorized"})
    with patch("sv_mcp.tools.utils.httpx.AsyncClient", _client_returning(response)):
        result = await vs_api_request(token, "GET", "/things")
    assert result.error == "Invalid credentials: Unauthorized"
