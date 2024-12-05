from typing import Annotated

from fastapi import APIRouter, Depends

from dstack._internal.proxy.deps import get_gateway_proxy_repo
from dstack._internal.proxy.repos.gateway import GatewayProxyRepo
from dstack._internal.proxy.repos.models import ACMESettings, GlobalProxyConfig
from dstack._internal.proxy.schemas.common import OkResponse
from dstack._internal.proxy.schemas.config import ConfigRequest

router = APIRouter()


@router.post("")
async def update_global_config(
    body: ConfigRequest,
    repo: Annotated[GatewayProxyRepo, Depends(get_gateway_proxy_repo)],
) -> OkResponse:
    await repo.set_config(
        GlobalProxyConfig(
            acme_settings=ACMESettings(
                server=body.acme_server,
                eab_kid=body.acme_eab_kid,
                eab_hmac_key=body.acme_eab_hmac_key,
            ),
        ),
    )
    return OkResponse()
