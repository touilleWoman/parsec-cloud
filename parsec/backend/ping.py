from parsec.types import DeviceID, OrganizationID
from parsec.api.protocole import ping_serializer
from parsec.backend.utils import catch_protocole_errors, anonymous_api


class BasePingComponent:
    @anonymous_api
    @catch_protocole_errors
    async def api_ping(self, client_ctx, msg):
        msg = ping_serializer.req_load(msg)
        if hasattr(client_ctx, "organization_id"):
            await self.ping(client_ctx.organization_id, client_ctx.device_id, msg["ping"])
        return ping_serializer.rep_dump({"status": "ok", "pong": msg["ping"]})

    async def ping(self, organization_id: OrganizationID, author: DeviceID, ping: str) -> None:
        raise NotImplementedError()
