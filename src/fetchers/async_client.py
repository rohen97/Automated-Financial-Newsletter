from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
from typing import Any

import httpx


@dataclass(frozen=True)
class ProviderLimit:
    max_concurrency: int = 2
    timeout_seconds: float = 20.0
    retries: int = 2
    max_response_bytes: int = 5_000_000


class AsyncProviderClient:
    """Pooled HTTP client for provider modules migrated to native async I/O."""

    def __init__(
        self,
        limits: dict[str, dict[str, Any]] | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        configured = limits or {}
        self._limits = {
            provider: ProviderLimit(**values)
            for provider, values in configured.items()
        }
        self._semaphores = {
            provider: asyncio.Semaphore(limit.max_concurrency)
            for provider, limit in self._limits.items()
        }
        self._client = httpx.AsyncClient(
            follow_redirects=True,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            headers={"User-Agent": "WolfResearchNewsletter/2.0"},
            transport=transport,
        )

    async def __aenter__(self) -> AsyncProviderClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self._client.aclose()

    async def get_json(
        self,
        provider: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        content = await self.get_bytes(provider, url, params=params, headers=headers)
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{provider} returned invalid JSON") from exc

    async def get_bytes(
        self,
        provider: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> bytes:
        limit = self._limits.get(provider, ProviderLimit())
        semaphore = self._semaphores.setdefault(
            provider,
            asyncio.Semaphore(limit.max_concurrency),
        )
        async with semaphore:
            for attempt in range(limit.retries + 1):
                try:
                    async with self._client.stream(
                        "GET",
                        url,
                        params=params,
                        headers=headers,
                        timeout=limit.timeout_seconds,
                    ) as response:
                        response.raise_for_status()
                        declared_size = int(response.headers.get("content-length") or 0)
                        if declared_size > limit.max_response_bytes:
                            raise ValueError(
                                f"{provider} response exceeded its configured size limit"
                            )
                        content = bytearray()
                        async for chunk in response.aiter_bytes():
                            content.extend(chunk)
                            if len(content) > limit.max_response_bytes:
                                raise ValueError(
                                    f"{provider} response exceeded its configured size limit"
                                )
                        return bytes(content)
                except (httpx.HTTPError, ValueError) as exc:
                    if attempt >= limit.retries:
                        if isinstance(exc, ValueError):
                            raise
                        status = getattr(getattr(exc, "response", None), "status_code", None)
                        detail = f" with status {status}" if status else ""
                        raise RuntimeError(f"{provider} request failed{detail}") from None
                    await asyncio.sleep(min(4.0, 0.5 * (2**attempt)))
        raise RuntimeError(f"{provider} request failed")


async def fetch_fred_series(client: AsyncProviderClient, url: str, params: dict[str, Any]) -> Any:
    return await client.get_json("fred", url, params=params)


async def fetch_alpha_vantage_symbol(
    client: AsyncProviderClient,
    url: str,
    params: dict[str, Any],
) -> Any:
    return await client.get_json("alpha_vantage", url, params=params)


async def fetch_marketaux_query(
    client: AsyncProviderClient,
    url: str,
    params: dict[str, Any],
) -> Any:
    return await client.get_json("marketaux", url, params=params)


async def fetch_rss_source(client: AsyncProviderClient, url: str) -> bytes:
    return await client.get_bytes("rss", url)


async def fetch_external_asset(client: AsyncProviderClient, url: str) -> bytes:
    return await client.get_bytes("external_charts", url)
