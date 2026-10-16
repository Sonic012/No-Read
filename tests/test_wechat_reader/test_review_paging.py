"""想法/点评分页测试。

官方网关的 /review/list/mine 在 count < totalCount 时只返回前 count 条，
并且 hasMore=0、synckey 也翻不到第二页。这里锁定两个契约：
1. 默认页大小必须足够大，长笔记书籍要一次取全；
2. 万一服务端给不全，必须能被上层识别为「未取全」，从而禁止清理（防误删）。
"""

import asyncio
import logging
from typing import Any, Dict, List

from src.weread.gateway import DEFAULT_REVIEW_PAGE_SIZE, WeReadGateway
from src.weread.provider import OfficialWeReadProvider


class FakeGateway(WeReadGateway):
    """模拟官方网关：返回 min(count, total) 条，且 hasMore 恒为 0。"""

    def __init__(self, total: int, server_cap: int = 10_000):
        self.api_key = "wrk-test"
        self.skill_version = "1.0.5"
        self.logger = logging.getLogger("test")
        self.total = total
        self.server_cap = server_cap
        self.calls: List[int] = []
        self._all = [
            {"review": {"reviewId": f"review_{i}", "content": f"c{i}", "createTime": 1000 - i}}
            for i in range(total)
        ]

    async def my_reviews_page(self, book_id: str, count: int = 20, synckey: int = 0) -> Dict[str, Any]:
        self.calls.append(count)
        if synckey:
            return {"reviews": [], "totalCount": self.total, "hasMore": 0, "synckey": None}
        return {
            "reviews": self._all[: min(count, self.server_cap)],
            "totalCount": self.total,
            "hasMore": 0,
            "synckey": 1700000000,
        }


def _collect(gateway: FakeGateway, book_id: str = "b1") -> List[Dict[str, Any]]:
    async def run():
        return [item async for item in gateway.iter_my_reviews(book_id)]

    return asyncio.run(run())


def test_takes_all_reviews_when_total_exceeds_default_page_size():
    gateway = FakeGateway(total=52)
    items = _collect(gateway)

    assert len(items) == 52
    assert len({i["review"]["reviewId"] for i in items}) == 52
    assert gateway.calls[0] == DEFAULT_REVIEW_PAGE_SIZE


def test_small_book_makes_only_one_request():
    gateway = FakeGateway(total=1)
    items = _collect(gateway)

    assert len(items) == 1
    assert gateway.calls == [DEFAULT_REVIEW_PAGE_SIZE]


def test_duplicate_reviews_are_deduplicated():
    gateway = FakeGateway(total=30)
    original = gateway.my_reviews_page

    async def duplicated(book_id: str, count: int = 20, synckey: int = 0):
        page = await original(book_id, count, synckey)
        if not synckey:
            page["reviews"] = page["reviews"] + page["reviews"][:5]
        return page

    gateway.my_reviews_page = duplicated  # type: ignore[assignment]

    items = _collect(gateway)
    assert len(items) == len({i["review"]["reviewId"] for i in items})


def test_truncated_response_marks_reviews_incomplete():
    """服务端给不全时，必须标记未取全，否则同步会误删 Notion 里的记录。"""
    gateway = FakeGateway(total=52, server_cap=20)
    provider = OfficialWeReadProvider(api_key="wrk-test", cache_path="")
    provider.gateway = gateway

    result = asyncio.run(provider.load_notes("b1"))

    assert result.reviews_ok is False
    assert len(result.reviews) + len([n for n in result.notes if n.note_type == "review"]) == 20
