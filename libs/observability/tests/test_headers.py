from __future__ import annotations

import pytest
from starlette.requests import Request

from libs.observability.headers import (
    PlatformHeaders,
    bind_platform_headers,
    get_platform_headers,
)


@pytest.mark.asyncio
async def test_get_platform_headers_normalizes_whitespace():
    headers = await get_platform_headers(
        correlation_id=" 1234 ",
        tenant_id="   ",
        api_key="\tkey-value\n",
    )

    assert headers.correlation_id == "1234"
    assert headers.tenant_id is None
    assert headers.api_key == "key-value"


@pytest.mark.asyncio
async def test_bind_platform_headers_sets_request_state():
    scope = {"type": "http", "headers": []}

    async def _receive() -> dict[str, object]:  # pragma: no cover - helper for starlette
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(scope, _receive)
    platform_headers = PlatformHeaders(correlation_id="abc", tenant_id="tenant", api_key=None)

    result = await bind_platform_headers(request, platform_headers)

    assert result is platform_headers
    assert getattr(request.state, "platform_headers") is platform_headers
*** End of File