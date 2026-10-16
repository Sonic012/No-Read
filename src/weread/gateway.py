"""微信读书官方 Agent API Gateway 客户端。

官方入口：https://weread.qq.com/r/weread-skills
官方示例：https://github.com/Tencent/WeChatReading

鉴权使用扫码换取的 API Key（``wrk-`` 前缀），不再依赖网页 Cookie。
所有接口统一走 ``POST https://i.weread.qq.com/api/agent/gateway``，
通过请求体里的 ``api_name`` 路由，业务参数平铺在顶层。
"""

import asyncio
import logging
import os
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx
from aiolimiter import AsyncLimiter

DEFAULT_ENDPOINT = "https://i.weread.qq.com/api/agent/gateway"
DEFAULT_SKILL_VERSION = "1.0.5"


class WeReadError(Exception):
    """微信读书接口通用错误。"""


class WeReadAuthError(WeReadError):
    """API Key 缺失、失效或未授权。"""


class WeReadUpgradeRequired(WeReadError):
    """官方要求升级 skill_version，需先更新后再调用。"""


class WeReadGateway:
    """官方 Agent API Gateway 的异步客户端。"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        skill_version: Optional[str] = None,
        endpoint: str = DEFAULT_ENDPOINT,
        rate_limit: int = 30,
        timeout: float = 60.0,
        max_retries: int = 3,
    ):
        self.api_key = api_key or os.getenv("WEREAD_API_KEY")
        if not self.api_key:
            raise WeReadAuthError(
                "未配置微信读书 API Key。请到 https://weread.qq.com/r/weread-skills "
                "扫码获取，并设置 WEREAD_API_KEY 环境变量或 config.WEREAD_API_KEY。"
            )

        self.skill_version = skill_version or os.getenv("WEREAD_SKILL_VERSION") or DEFAULT_SKILL_VERSION
        self.endpoint = endpoint
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limiter = AsyncLimiter(max_rate=rate_limit, time_period=60)
        self.logger = logging.getLogger(__name__)
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "WeReadGateway":
        await self._init_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def _init_client(self) -> None:
        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "No-Read/2.0 (+https://github.com/Tencent/WeChatReading)",
                },
            )

    async def close(self) -> None:
        if self.client is not None:
            await self.client.aclose()
            self.client = None

    async def call(self, api_name: str, **params: Any) -> Dict[str, Any]:
        """调用一个网关接口，返回裁剪后的数据。"""
        await self._init_client()

        body: Dict[str, Any] = {"api_name": api_name, "skill_version": self.skill_version}
        for key, value in params.items():
            if value is not None:
                body[key] = value

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with self.rate_limiter:
                    response = await self.client.post(self.endpoint, json=body)

                if response.status_code in (401, 403):
                    raise WeReadAuthError(
                        f"微信读书 API Key 无效或未授权（HTTP {response.status_code}），"
                        "请重新到 https://weread.qq.com/r/weread-skills 获取。"
                    )
                if response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"网关返回 {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                payload = response.json()
            except WeReadAuthError:
                raise
            except Exception as exc:  # 网络抖动/5xx，退避重试
                last_error = exc
                if attempt >= self.max_retries:
                    break
                delay = 2 ** attempt
                self.logger.warning(
                    "微信读书接口 %s 第 %s 次调用失败：%s，%ss 后重试",
                    api_name, attempt, exc, delay,
                )
                await asyncio.sleep(delay)
                continue

            return self._unwrap(api_name, payload)

        raise WeReadError(f"微信读书接口 {api_name} 调用失败：{last_error}")

    def _unwrap(self, api_name: str, payload: Any) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise WeReadError(f"微信读书接口 {api_name} 返回了非预期结构：{type(payload).__name__}")

        upgrade = payload.get("upgrade_info")
        if upgrade:
            message = upgrade.get("message") if isinstance(upgrade, dict) else str(upgrade)
            raise WeReadUpgradeRequired(
                f"官方要求升级微信读书 Skill：{message or '请到 https://weread.qq.com/r/weread-skills 更新'}"
            )

        errcode = payload.get("errcode", payload.get("errCode", 0))
        if errcode:
            message = payload.get("errmsg") or payload.get("errMsg") or payload.get("message") or "未知错误"
            if errcode in (-2012, -2010, 401, 403):
                raise WeReadAuthError(f"微信读书鉴权失败（errcode={errcode}）：{message}")
            raise WeReadError(f"微信读书接口 {api_name} 返回错误（errcode={errcode}）：{message}")

        return payload

    # ------------------------------------------------------------------
    # 高层接口封装
    # ------------------------------------------------------------------
    async def list_api(self) -> Dict[str, Any]:
        """列出网关当前开放的接口及参数定义。"""
        return await self.call("/_list")

    async def shelf_sync(self) -> Dict[str, Any]:
        """书架全量：books[]（电子书）+ albums[]（有声书专辑）+ mp（文章收藏入口）。"""
        return await self.call("/shelf/sync")

    async def book_info(self, book_id: str) -> Dict[str, Any]:
        return await self.call("/book/info", bookId=book_id)

    async def book_progress(self, book_id: str) -> Dict[str, Any]:
        return await self.call("/book/getprogress", bookId=book_id)

    async def chapter_info(self, book_id: str) -> Dict[str, Any]:
        return await self.call("/book/chapterinfo", bookId=book_id)

    async def notebook_page(self, count: int = 100, last_sort: Optional[int] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"count": count}
        if last_sort:
            params["lastSort"] = last_sort
        return await self.call("/user/notebooks", **params)

    async def iter_notebooks(self, count: int = 100) -> AsyncIterator[Dict[str, Any]]:
        """遍历所有「有笔记的书籍」，自动处理 lastSort 游标分页。"""
        last_sort: Optional[int] = None
        while True:
            page = await self.notebook_page(count=count, last_sort=last_sort)
            books = page.get("books") or []
            for book in books:
                yield book
            if not page.get("hasMore") or not books:
                return
            last_sort = books[-1].get("sort")
            if not last_sort:
                return

    async def bookmark_list(self, book_id: str) -> Dict[str, Any]:
        """单本书划线内容（已过滤书签）。"""
        return await self.call("/book/bookmarklist", bookId=book_id)

    async def my_reviews_page(self, book_id: str, count: int = 20, synckey: int = 0) -> Dict[str, Any]:
        return await self.call("/review/list/mine", bookid=book_id, count=count, synckey=synckey)

    async def iter_my_reviews(self, book_id: str, count: int = 20) -> AsyncIterator[Dict[str, Any]]:
        """遍历单本书的个人想法/点评，自动处理 synckey 分页。"""
        synckey = 0
        while True:
            page = await self.my_reviews_page(book_id, count=count, synckey=synckey)
            reviews = page.get("reviews") or []
            for item in reviews:
                yield item
            if not page.get("hasMore"):
                return
            next_key = page.get("synckey")
            if not next_key or next_key == synckey:
                return
            synckey = next_key

    async def readdata(self, mode: str = "monthly", base_time: int = 0) -> Dict[str, Any]:
        """阅读统计。mode: weekly / monthly / annually / overall。"""
        return await self.call("/readdata/detail", mode=mode, baseTime=base_time)
