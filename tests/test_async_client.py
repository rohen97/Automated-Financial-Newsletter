import asyncio

import httpx
import pytest

from src.fetchers.async_client import AsyncProviderClient


def test_async_client_parses_json_with_mock_transport():
    async def request(request):
        return httpx.Response(200, json={"series": "DGS10"}, request=request)

    async def execute():
        async with AsyncProviderClient(
            {"fred": {"max_concurrency": 1, "retries": 0}},
            transport=httpx.MockTransport(request),
        ) as client:
            return await client.get_json(
                "fred",
                "https://api.example.test/series",
                params={"api_key": "must-not-appear"},
            )

    assert asyncio.run(execute()) == {"series": "DGS10"}


def test_async_client_limits_response_and_sanitizes_http_errors():
    async def oversized(request):
        return httpx.Response(200, content=b"x" * 32, request=request)

    async def forbidden(request):
        return httpx.Response(403, request=request)

    async def execute(handler):
        async with AsyncProviderClient(
            {
                "marketaux": {
                    "max_concurrency": 1,
                    "timeout_seconds": 1,
                    "retries": 0,
                    "max_response_bytes": 8,
                }
            },
            transport=httpx.MockTransport(handler),
        ) as client:
            return await client.get_bytes(
                "marketaux",
                "https://api.example.test/news",
                params={"api_token": "must-not-appear"},
            )

    with pytest.raises(ValueError, match="configured size limit"):
        asyncio.run(execute(oversized))
    with pytest.raises(RuntimeError, match="marketaux request failed with status 403") as error:
        asyncio.run(execute(forbidden))
    assert "must-not-appear" not in str(error.value)
