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
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

import httpx
from aiolimiter import AsyncLimiter

DEFAULT_ENDPOINT = "https://i.weread.qq.com/api/agent/gateway"
DEFAULT_SKILL_VERSION = "1.0.5"
# /review/list/mine 在 count 小于 totalCount 时只返回前 count 条且 hasMore=0，
# 所以默认要一个足够大的页大小，避免长笔记书籍被静默截断。
DEFAULT_REVIEW_PAGE_SIZE = 200


def _review_key(item: Any) -> Any:
    """想法/点评的稳定去重键。"""
    if not isinstance(item, dict):
        return None
    review = item.get("review") if isinstance(item.get("review"), dict) else item
    key = review.get("reviewId") or item.get("reviewId")
    if key:
        return key
    # 兜底：用 创建时间 + 内容 组合，避免整页重复
    return (review.get("createTime"), (review.get("content") or "")[:80]) or None


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

    async def my_reviews_all(
        self, book_id: str, count: int = DEFAULT_REVIEW_PAGE_SIZE
    ) -> Tuple[List[Dict[str, Any]], Optional[int]]:
        """取回单本书的全部想法/点评，返回 ``(条目列表, 上游声明的 totalCount)``。

        官方网关的 /review/list/mine 有个坑：``count`` 小于 ``totalCount`` 时
        它只返回前 ``count`` 条，并且把 ``hasMore`` 置 0、``synckey`` 也翻不到
        第二页。默认的 20 会让长笔记书籍静默丢数据，所以这里按 ``totalCount``
        自适应放量，并保留 ``synckey`` 兜底。
        """
        page = await self.my_reviews_page(book_id, count=count, synckey=0)
        reviews = list(page.get("reviews") or [])
        total = page.get("totalCount") or len(reviews)

        if len(reviews) < total:
            bigger = await self.my_reviews_page(book_id, count=max(total, count), synckey=0)
            bigger_reviews = bigger.get("reviews") or []
            if len(bigger_reviews) > len(reviews):
                reviews = list(bigger_reviews)
                total = bigger.get("totalCount") or total

        # synckey 兜底：个别书籍只有走翻页游标才拿得到后续页
        synckey = page.get("synckey")
        while synckey and len(reviews) < total:
            page = await self.my_reviews_page(book_id, count=count, synckey=synckey)
            more = page.get("reviews") or []
            if not more:
                break
            reviews.extend(more)
            next_key = page.get("synckey")
            if not next_key or next_key == synckey:
                break
            synckey = next_key

        deduped: List[Dict[str, Any]] = []
        seen = set()
        for item in reviews:
            key = _review_key(item)
            if key is not None:
                if key in seen:
                    continue
                seen.add(key)
            deduped.append(item)

        return deduped, total

    async def iter_my_reviews(
        self, book_id: str, count: int = DEFAULT_REVIEW_PAGE_SIZE
    ) -> AsyncIterator[Dict[str, Any]]:
        """遍历单本书的个人想法/点评（``my_reviews_all`` 的流式包装）。"""
        reviews, _total = await self.my_reviews_all(book_id, count=count)
        for item in reviews:
            yield item

    async def readdata(self, mode: str = "monthly", base_time: int = 0) -> Dict[str, Any]:
        """阅读统计。mode: weekly / monthly / annually / overall。"""
        return await self.call("/readdata/detail", mode=mode, baseTime=base_time)
