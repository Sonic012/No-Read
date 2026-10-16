"""笔记对账测试：新增 / 更新 / 删除，以及抓取失败时不得误删。"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytest

from src.models import ReadingNote
from src.sync.service import SyncService
from src.weread.provider import NotesResult


class StubNotionClient:
    """记录调用的假 Notion 客户端。"""

    def __init__(self, existing: Optional[Dict[str, Dict[str, Any]]] = None):
        self._existing = existing or {}
        self.upserts: List[str] = []
        self.archived: List[str] = []
        self.records_for: Dict[str, Dict[str, Dict[str, Any]]] = {}

    async def get_book_records(self, database_key: str, book_page_id: str):
        return dict(self.records_for.get(database_key, self._existing))

    async def upsert_note(self, database_key, book_page_id, note, existing):
        self.upserts.append(note.note_id)
        if note.note_id in existing:
            return "updated"
        existing[note.note_id] = {"page_id": f"page-{note.note_id}", "content": "", "chapter": ""}
        return "created"

    async def archive_pages(self, page_ids):
        self.archived.extend(page_ids)
        return len(page_ids)


def _service(notion_client: StubNotionClient) -> SyncService:
    service = SyncService.__new__(SyncService)
    service.notion_client = notion_client
    import logging

    service.logger = logging.getLogger("test")
    service.book_delay = 0
    return service


def _note(note_id: str, content: str = "内容") -> ReadingNote:
    return ReadingNote(
        note_id=note_id,
        book_id="b1",
        chapter_title="第一章",
        chapter_uid="5",
        content=content,
        note_type="bookmark",
        create_time=datetime(2026, 1, 1),
    )


def test_reconcile_creates_updates_and_deletes():
    existing = {
        "bm_keep": {"page_id": "p-keep", "content": "内容", "chapter": "第一章"},
        "bm_gone": {"page_id": "p-gone", "content": "旧内容", "chapter": "第一章"},
    }
    client = StubNotionClient(existing)
    service = _service(client)

    counters = asyncio.run(
        service._reconcile_database("highlights", "book-page", [_note("bm_keep"), _note("bm_new")])
    )

    assert sorted(client.upserts) == ["bm_keep", "bm_new"]
    assert counters["created"] == 1
    assert counters["updated"] == 1
    assert client.archived == ["p-gone"], "上游已删除的划线应被归档"
    assert counters["deleted"] == 1


def test_reconcile_never_deletes_when_fetch_failed():
    """划线抓取失败时，绝不能把 Notion 里已有划线当成「已删除」。"""
    client = StubNotionClient(
        {"bm_old": {"page_id": "p-old", "content": "旧", "chapter": "第一章"}}
    )
    service = _service(client)

    result = NotesResult(
        notes=[_note("rv_1")],  # 只有想法，没有划线
        highlights_ok=False,
        reviews_ok=True,
    )
    client.records_for = {"highlights": {}, "notes": {}}

    counters = asyncio.run(service._reconcile_book_notes("b1", "book-page", result))

    assert client.archived == [], "抓取失败时不得归档任何划线"
    assert counters["deleted"] == 0
    assert "rv_1" in client.upserts, "没取全时仍要写入已取到的部分，保证下次继续收敛"


def test_reconcile_skips_empty_content_without_deleting():
    client = StubNotionClient({})
    service = _service(client)

    counters = asyncio.run(
        service._reconcile_database("notes", "book-page", [_note("rv_empty", content="")])
    )

    assert counters["skipped"] == 1
    assert client.upserts == []
    assert client.archived == []


def test_sync_book_skips_cleanup_when_notebook_index_incomplete():
    """笔记本索引不完整时，不能对有书架无笔记的书做「上游已删除」清理。"""

    class StubProvider:
        notebooks_complete = False

        async def load_book(self, book_id, shelf_info=None, force=False):
            return shelf_info

    class PageClient(StubNotionClient):
        def __init__(self):
            super().__init__({})
            self.calls = []

        async def find_book_page(self, book_id):
            return {"id": "book-page"}

        async def update_book_page(self, page_id, book_info):
            self.calls.append(("update", page_id))

        async def create_book_page(self, book_info):
            self.calls.append(("create", book_info.book_id))
            return {"id": "book-page"}

    from src.models import BookInfo

    client = PageClient()
    service = _service(client)
    service.provider = StubProvider()

    book = BookInfo(book_id="b1", title="无笔记的书", author="作者")
    result = asyncio.run(service.sync_book(book, known_page_id="book-page"))

    assert result.success is True
    assert client.archived == [], "索引不完整时不得归档任何记录"
    assert client.records_for == {}, "不应发起笔记对账查询"


def test_sync_book_cleans_up_when_index_complete():
    """索引完整时，无笔记的书仍要清理历史残留。"""

    class StubProvider:
        notebooks_complete = True

        async def load_book(self, book_id, shelf_info=None, force=False):
            return shelf_info

    class PageClient(StubNotionClient):
        async def find_book_page(self, book_id):
            return {"id": "book-page"}

        async def update_book_page(self, page_id, book_info):
            return {}

    from src.models import BookInfo

    client = PageClient({})
    client.records_for = {
        "highlights": {"bm_old": {"page_id": "p-old", "content": "旧", "chapter": "第一章"}},
        "notes": {},
    }
    service = _service(client)
    service.provider = StubProvider()

    book = BookInfo(book_id="b1", title="无笔记的书", author="作者")
    result = asyncio.run(service.sync_book(book, known_page_id="book-page"))

    assert result.success is True
    assert client.archived == ["p-old"]
    assert result.notes_deleted == 1


def test_sync_reading_history_maps_granularity_by_key_length():
    class Provider:
        async def reading_history(self):
            return {"2024": 3600, "2024-06": 7200, "2024-06-02": 600}

    recorded = []

    class Client(StubNotionClient):
        async def list_reading_records(self):
            return {}

        async def upsert_reading_record(self, day, seconds, granularity="日", page_id=None):
            recorded.append((day, seconds, granularity))
            return "created"

    service = _service(Client({}))
    service.provider = Provider()
    counters = asyncio.run(service.sync_reading_history())

    assert recorded == [
        ("2024", 3600, "年"),
        ("2024-06", 7200, "月"),
        ("2024-06-02", 600, "日"),
    ]
    assert counters["created"] == 3
