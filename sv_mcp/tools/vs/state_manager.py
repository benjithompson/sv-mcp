from typing import Optional, Dict, Any

from mcp.server.fastmcp import Context

from sv_mcp.config.blazemeter import VS_ENDPOINT, WORKSPACES_ENDPOINT, VS_TOOLS_PREFIX, VS_TESTDATA_ENDPOINT
from sv_mcp.config.token import BzmToken
from sv_mcp.formatters.service_data import format_service_data
from sv_mcp.formatters.virtual_service import format_virtual_services, format_virtual_services_action
from sv_mcp.models.result import BaseResult
from sv_mcp.models.vs.service_data import ServiceData
from sv_mcp.models.vs.virtual_service import ActionResult
from sv_mcp.telemetry import run_tool
from sv_mcp.tools.utils import vs_api_request, error_result
from sv_mcp.tools.vs.base_virtual_service_manager import BaseVirtualServiceManager

_CACHE_TYPES = ("NO_SQL", "SQL")


class StateManager(BaseVirtualServiceManager):

    async def read_data(self, workspace_id: int, vs_id: int) -> BaseResult:
        return await vs_api_request(
            self.token,
            "GET",
            f"{WORKSPACES_ENDPOINT}/{workspace_id}/{VS_ENDPOINT}/{vs_id}/{VS_TESTDATA_ENDPOINT}",
            result_formatter=format_service_data
        )

    async def export_data(self, workspace_id: int, vs_id: int) -> BaseResult:
        return await vs_api_request(
            self.token,
            "GET",
            f"{WORKSPACES_ENDPOINT}/{workspace_id}/{VS_ENDPOINT}/{vs_id}/{VS_TESTDATA_ENDPOINT}/refresh",
            result_formatter=format_virtual_services_action
        )

    async def reset(self, workspace_id: int, vs_id: int) -> BaseResult:
        return await self.configure(workspace_id, vs_id, keep_blaze_data=False)

    async def set_data_settings(
            self,
            workspace_id: int,
            vs_id: int,
            cache_type: str,
            initial_sql_script: Optional[str] = None,
    ) -> BaseResult:
        if cache_type not in _CACHE_TYPES:
            return BaseResult(error=f"Invalid cacheType '{cache_type}'. Use one of: {', '.join(_CACHE_TYPES)}.")
        update_request: Dict[str, Any] = {"id": vs_id, "workspaceId": workspace_id, "cacheType": cache_type}
        if initial_sql_script is not None:
            update_request["initialSqlScript"] = initial_sql_script
        return await vs_api_request(
            self.token,
            "PATCH",
            f"{WORKSPACES_ENDPOINT}/{workspace_id}/{VS_ENDPOINT}/{vs_id}",
            result_formatter=format_virtual_services,
            json=update_request,
        )


def register(mcp, token: Optional[BzmToken]) -> None:
    @mcp.tool(
        name=f"{VS_TOOLS_PREFIX}_state",
        description="""
        Operations on the state (service data) of a virtual service.
        Use this when a user needs to inspect, export or reset the state of a stateful virtual service,
        or to switch its test data between NO_SQL and SQL mode.

        What state is:
          - When a virtual service is deployed, it gets its own copy of its service's data: the data entities
            and the global variables. This copy is the state of the virtual service.
          - The state belongs to one virtual service. It is shared by all of its clients and by both its HTTP
            and messaging runners, and it survives stop/start.
          - STATE_UPDATE processing actions modify the state at runtime (virtual_services_action):
            store, update or delete objects in data entities, and update or increment global variables.
          - The initial state is seeded from virtual_services_test_data: entities from the data model, global
            variables from global_variables or set_global_variables.
          - Transactions read the state with ${#each (blazeData 'entity' 'where ...')}, ${blazeDataSize 'entity'},
            ${globalName}, or ${sql '...'}.

        Inspect the current state:
          1. export_data. The result contains a tracking id.
          2. Poll virtual_services_tracking read with that tracking id until status is 'FINISHED'
             ('FAILED' means the export failed).
          3. read_data. The result contains fresh download links and the global variables.
        Reset the state to its initial data:
          1. reset. The result contains a tracking id.
          2. Poll virtual_services_tracking read with that tracking id until status is 'FINISHED'
             ('FAILED' means the reset failed).

        Actions:
        - read_data: Read the service data of a virtual service: links to download the data file, a preview of it
            and the data model, the global variables, and the data settings.
            args(dict):
                workspace_id (int): Mandatory. The id of the workspace the virtual service belongs to.
                id (int): Mandatory. The id of the virtual service.
        - export_data: Export the current, state-modified dataset of a running virtual service.
            Action result contains tracking id. Poll virtual_services_tracking read until status is 'FINISHED',
            then call read_data to get the fresh download links.
            args(dict):
                workspace_id (int): Mandatory. The id of the workspace the virtual service belongs to.
                id (int): Mandatory. The id of the virtual service to export the data from.
        - reset: Reset the state of a running virtual service. Reconfigures the virtual service and regenerates its
            data from the service's data model and global variables. All changes made by STATE_UPDATE actions are lost.
            This is virtual_services_virtual_service configure with keepBlazeData=false, so it also reloads the
            assigned transactions. Works for HTTP and messaging virtual services.
            Action result contains tracking id. Poll virtual_services_tracking read until status is 'FINISHED'.
            args(dict):
                workspace_id (int): Mandatory. The id of the workspace the virtual service belongs to.
                id (int): Mandatory. The id of the virtual service to reset.
        - set_data_settings: Select the test data implementation of a virtual service.
            NO_SQL is the default. SQL adds initialSqlScript, a bootstrap script run over the service data tables,
            e.g. CREATE VIEW statements joining several data entities. Transactions can then query the views in
            their sqlHint (virtual_services_http_transaction) or with ${sql '...'}.
            Takes effect on the next deploy or configure (virtual_services_virtual_service).
            Result is the updated virtual service.
            args(dict):
                workspace_id (int): Mandatory. The id of the workspace the virtual service belongs to.
                id (int): Mandatory. The id of the virtual service.
                cacheType (str): Mandatory. 'NO_SQL' or 'SQL'.
                initialSqlScript (str): Optional. SQL bootstrap script for SQL mode.
        ServiceData Schema:
        """ + str(ServiceData.model_json_schema()) + """
        export_data/reset actions result schema:
        """ + str(ActionResult.model_json_schema())
    )
    async def state(action: str, args: Dict[str, Any], ctx: Context) -> BaseResult:
        state_manager = StateManager(token, ctx)

        async def _dispatch():
            match action:
                case "read_data":
                    return await state_manager.read_data(args["workspace_id"], args["id"])
                case "export_data":
                    return await state_manager.export_data(args["workspace_id"], args["id"])
                case "reset":
                    return await state_manager.reset(args["workspace_id"], args["id"])
                case "set_data_settings":
                    return await state_manager.set_data_settings(
                        args["workspace_id"], args["id"],
                        args["cacheType"], args.get("initialSqlScript"),
                    )
                case _:
                    return BaseResult(error=f"Action {action} not found in state manager tool")

        try:
            return await run_tool("virtual_services_state", action, ctx, _dispatch)
        except Exception as exc:
            return error_result(exc)
