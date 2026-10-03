from mcp.server.fastmcp import FastMCP

from sv_mcp.server import register_tools

ALL_TOOLS = {
    "blazemeter_user",
    "blazemeter_workspaces",
    "blazemeter_account",
    "virtual_services_service",
    "virtual_services_http_transaction",
    "virtual_services_messaging_transaction",
    "virtual_services_virtual_service",
    "virtual_services_virtual_service_template",
    "virtual_services_tracking",
    "virtual_services_location",
    "virtual_services_sandbox",
    "virtual_services_action",
    "virtual_services_configuration",
    "virtual_services_asset",
    "virtual_services_test_data",
    "virtual_services_recording",
    "virtual_services_messaging_virtual_service",
    "virtual_services_state",
    "virtual_services_blueprint",
}


async def _registered_tool_names() -> set:
    mcp = FastMCP("test")
    register_tools(mcp, None)
    return {tool.name for tool in await mcp.list_tools()}


async def test_all_tools_registered_when_filter_unset(monkeypatch):
    """Every tool registers and builds its description (schemas are concatenated at registration)."""
    monkeypatch.delenv("MCP_ENABLED_TOOLS", raising=False)
    assert await _registered_tool_names() == ALL_TOOLS


async def test_enabled_tools_filter_registers_only_listed_tools(monkeypatch):
    monkeypatch.setenv("MCP_ENABLED_TOOLS", "virtual_services_state, VIRTUAL_SERVICES_BLUEPRINT")
    assert await _registered_tool_names() == {"virtual_services_state", "virtual_services_blueprint"}
