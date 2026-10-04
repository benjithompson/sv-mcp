import httpx
from unittest.mock import MagicMock

from sv_mcp.tools.utils import error_result


def _http_error(status_code: int, body: dict | None = None, text: str = ""):
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    if body is not None:
        response.json.return_value = body
    else:
        response.json.side_effect = ValueError("no json")
    response.text = text
    return httpx.HTTPStatusError("err", request=MagicMock(), response=response)


class TestErrorResult:
    def test_401_is_invalid_credentials(self):
        r = error_result(_http_error(401, {"error": "bad key"}))
        assert r.error == "Invalid credentials: bad key"

    def test_403_is_access_forbidden(self):
        r = error_result(_http_error(403, {"message": "nope"}))
        assert r.error == "Access forbidden (check workspace permissions): nope"

    def test_404_is_not_found(self):
        r = error_result(_http_error(404, {"error": "missing"}))
        assert r.error == "Not found: missing"

    def test_429_is_rate_limited(self):
        r = error_result(_http_error(429))
        assert "Rate limited" in r.error

    def test_5xx_is_server_error(self):
        r = error_result(_http_error(503))
        assert "server-side problem" in r.error
        assert "503" in r.error

    def test_timeout_is_environmental(self):
        r = error_result(httpx.TimeoutException("slow"))
        assert "timed out" in r.error

    def test_network_error(self):
        r = error_result(httpx.ConnectError("refused"))
        assert "Network error" in r.error

    def test_unexpected_exception_has_no_traceback(self):
        r = error_result(ValueError("secret /home/user/path leaked"))
        # Clean, classified message — no raw value or stack trace forwarded.
        assert r.error.startswith("Internal error: ValueError")
        assert "secret" not in r.error
        assert "/home/user/path" not in r.error
        assert "Traceback" not in r.error

    def test_never_forwards_raw_traceback_for_http_errors(self):
        r = error_result(_http_error(500))
        assert "Traceback" not in r.error


def _dispatch(args):
    return args["id"]


def format_asset(raw):
    return raw["id"]


def _key_error(fn) -> KeyError:
    try:
        fn({})
    except KeyError as e:
        return e


class TestMissingArgument:
    def test_keyerror_in_dispatch_names_argument_and_action(self):
        r = error_result(_key_error(_dispatch), "read_data")
        assert r.error == ("Missing required argument 'id' for action 'read_data'. "
                           "Check the argument names in the tool description.")

    def test_keyerror_outside_dispatch_stays_internal(self):
        # e.g. a formatter reading a field the API did not return
        r = error_result(_key_error(format_asset), "read_data")
        assert r.error.startswith("Internal error: KeyError")

    def test_keyerror_without_traceback_stays_internal(self):
        r = error_result(KeyError("id"))
        assert r.error.startswith("Internal error: KeyError")


def test_internal_error_points_to_sv_mcp_issues():
    r = error_result(ValueError("boom"))
    assert "https://github.com/Blazemeter/sv-mcp/issues" in r.error
    assert "bzm-mcp" not in r.error


async def test_tool_call_with_wrong_argument_name_reports_missing_argument():
    from mcp.server.fastmcp import FastMCP
    from sv_mcp.server import register_tools

    mcp = FastMCP("test")
    register_tools(mcp, None)
    result = await mcp.call_tool(
        "virtual_services_state",
        {"action": "read_data", "args": {"workspace_id": 1, "virtual_service_id": 2}},
    )
    text = str(result)
    assert "Missing required argument 'id' for action 'read_data'" in text
    assert "Internal error" not in text
