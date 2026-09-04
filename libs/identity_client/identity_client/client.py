"""
Minimal async client for Identity-Service introspection.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx


class IdentityClient:
    def __init__(self, base_url: str, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(timeout)

    async def introspect(self, token: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/api/v1/auth/introspect",
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            return resp.json()


async def introspect_token(base_url: str, token: str, timeout: float = 5.0) -> Dict[str, Any]:
    client = IdentityClient(base_url, timeout)
    return await client.introspect(token)


async def introspect_token_optional(base_url: Optional[str], token: str, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
    if not base_url:
        return None
    try:
        return await introspect_token(base_url, token, timeout)
    except Exception:
        return None

