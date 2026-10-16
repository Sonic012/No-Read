"""Notion 请求重试测试：429/5xx 必须重试，业务错误必须立刻抛出。"""

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from notion_client.errors import APIResponseError, HTTPResponseError

from src.notion.template_client import NotionTemplateClient


def _response(status: int, headers=None) -> httpx.Response:
    return httpx.Response(
        status,
        headers=headers or {},
        request=httpx.Request("POST", "https://api.notion.com/v1/pages"),
    )


def _client(max_retries: int = 4) -> NotionTemplateClient:
    return NotionTemplateClient(token="ntn_test", database_id="db", max_retries=max_retries)


def test_retries_on_rate_limit_then_succeeds():
    client = _client()
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise HTTPResponseError(_response(429, {"retry-after": "0"}))
        return {"ok": True}

    with patch("src.notion.template_client.asyncio.sleep", new=AsyncMock()) as sleeper:
        result = asyncio.run(client._request(flaky))

    assert result == {"ok": True}
    assert calls["n"] == 3
    assert sleeper.await_count == 2


def test_gives_up_after_max_retries():
    client = _client(max_retries=2)
    calls = {"n": 0}

    async def always_429():
        calls["n"] += 1
        raise HTTPResponseError(_response(503))

    with patch("src.notion.template_client.asyncio.sleep", new=AsyncMock()):
        with pytest.raises(HTTPResponseError):
            asyncio.run(client._request(always_429))

    assert calls["n"] == 2


def test_non_retryable_error_raises_immediately():
    client = _client()
    calls = {"n": 0}

    async def bad_request():
        calls["n"] += 1
        raise APIResponseError(_response(400), "bad", "validation_error")

    with patch("src.notion.template_client.asyncio.sleep", new=AsyncMock()):
        with pytest.raises(APIResponseError):
            asyncio.run(client._request(bad_request))

    assert calls["n"] == 1


def test_retry_delay_prefers_retry_after_header():
    exc = HTTPResponseError(_response(429, {"retry-after": "7"}))
    assert NotionTemplateClient._retry_delay(exc, attempt=1) == 7.0

    no_header = HTTPResponseError(_response(429))
    assert NotionTemplateClient._retry_delay(no_header, attempt=2) == 4.0
