import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..models import BookInfo, BookReview, ReadingNote, SyncResult
from ..notion.template_client import NotionTemplateClient
from ..weread.provider import OfficialWeReadProvider, WeReadProvider


def _norm_progress(raw: Any) -> Optional[float]:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return round(value / 100 if value > 1 else value, 4)


def _review_to_note(review: BookReview) -> ReadingNote:
    """书评在 Notion 里与想法共用「笔记」库，用类型区分。"""
    return ReadingNote(
        note_id=review.review_id,
        book_id=review.book_id,
        chapter_title="书评",
        chapter_uid="",
        content=review.content,
        note_type="book_review",
        create_time=review.create_time,
        is_private=review.is_private,
    )


class SyncService:
    """微信读书（官方 Agent API）到 Notion 的同步服务。

    同步语义是**全量对账**而不是只追加：
    - 上游新增 → 在 Notion 创建
    - 上游修改 → 更新对应页面
    - 上游删除 → 归档对应页面
    任何一次抓取失败都会跳过该来源的删除对账，避免误删。
    """

    def __init__(
        self,
        provider: WeReadProvider,
        notion_token: str,
        notion_database_id: str,
        book_delay: float = 0.5,
        notion_rate_limit: int = 3,
    ):
        self.provider = provider
        self.notion_client = NotionTemplateClient(
            token=notion_token,
            database_id=notion_database_id,
            rate_limit=notion_rate_limit,
        )
        self.book_delay = book_delay
        self.logger = logging.getLogger(__name__)

    @classmethod
    def from_config(cls, config) -> "SyncService":
        provider = OfficialWeReadProvider(
            api_key=getattr(config, "WEREAD_API_KEY", None),
            skill_version=getattr(config, "WEREAD_SKILL_VERSION", None),
            rate_limit=getattr(config, "WEREAD_RATE_LIMIT", 30),
            cache_path=getattr(config, "BOOK_CACHE_FILE", "logs/book_metadata.json"),
            cache_ttl=getattr(config, "BOOK_CACHE_TTL", 7 * 24 * 3600),
        )
        return cls(
            provider=provider,
            notion_token=config.NOTION_TOKEN,
            notion_database_id=config.NOTION_DATABASE_ID,
            book_delay=getattr(config, "WEREAD_REQUEST_DELAY", 0.5),
            notion_rate_limit=getattr(config, "NOTION_RATE_LIMIT", 3),
        )

    async def __aenter__(self) -> "SyncService":
        await self.provider.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.provider.__aexit__(exc_type, exc_val, exc_tb)

    # ------------------------------------------------------------------
    # Notion 结构准备
    # ------------------------------------------------------------------
    async def ensure_notion_schema(self) -> List[str]:
        return await self.notion_client.ensure_schema()

    # ------------------------------------------------------------------
    # 全量同步
    # ------------------------------------------------------------------
    async def sync_all_books(
        self,
        include_finished: bool = True,
        include_unfinished: bool = True,
        full: bool = False,
    ) -> List[SyncResult]:
        self.logger.info("🚀 开始同步微信读书数据到 Notion（%s）", "全量刷新" if full else "增量")

        shelf = await self.provider.list_shelf()
        self.logger.info("📖 书架共 %s 个条目", len(shelf))

        notebooks = await self.provider.notebook_index()
        books = self._merge_shelf_with_notes(shelf, notebooks)

        selected = [
            book for book in books if self._should_sync(book, include_finished, include_unfinished)
        ]
        skipped = len(books) - len(selected)
        if skipped:
            self.logger.info("⏭️  按配置跳过 %s 本（读完/未读完过滤）", skipped)
        self.logger.info("📋 准备同步 %s 本书籍", len(selected))

        known_books = await self.notion_client.list_book_page_ids()
        self.logger.info("🗂️  Notion 已有 %s 本书籍页", len(known_books))

        results: List[SyncResult] = []
        for index, book in enumerate(selected, 1):
            self.logger.info(
                "📖 [%s/%s] %s", index, len(selected), book.title or book.book_id
            )
            result = await self.sync_book(
                book, force=full, known_page_id=known_books.get(book.book_id)
            )
            results.append(result)

            if result.success:
                self.logger.info(
                    "   ✅ %s｜新增/更新 %s，删除 %s，跳过 %s",
                    result.book_title,
                    result.notes_synced,
                    result.notes_deleted,
                    result.notes_skipped,
                )
            else:
                self.logger.error("   ❌ %s - %s", result.book_title, result.error_message)

            if self.book_delay:
                await asyncio.sleep(self.book_delay)

        self.logger.info(
            "🎉 书籍同步完成：成功 %s/%s，笔记 %s 条，删除 %s 条",
            sum(1 for result in results if result.success),
            len(results),
            sum(result.notes_synced for result in results),
            sum(result.notes_deleted for result in results),
        )
        return results

    # ------------------------------------------------------------------
    # 单本同步
    # ------------------------------------------------------------------
    async def sync_book(
        self,
        shelf_book: BookInfo,
        force: bool = False,
        known_page_id: Optional[str] = None,
    ) -> SyncResult:
        book_id = shelf_book.book_id
        try:
            book_info = await self.provider.load_book(book_id, shelf_info=shelf_book, force=force)

            page_id = known_page_id
            if page_id is None:
                existing = await self.notion_client.find_book_page(book_id)
                page_id = existing["id"] if existing else None

            created = page_id is None
            if created:
                page = await self.notion_client.create_book_page(book_info)
                page_id = page["id"]
            else:
                await self.notion_client.update_book_page(page_id, book_info)

            counters = {"created": 0, "updated": 0, "adopted": 0, "unchanged": 0, "deleted": 0, "skipped": 0}

            if book_info.is_album:
                pass
            elif created and not self._has_notes(shelf_book):
                # 刚建的页面不可能有子记录，且上游无笔记，无需查询对账
                pass
            elif self._has_notes(shelf_book):
                notes_result = await self.provider.load_notes(book_id)
                counters = await self._reconcile_book_notes(book_id, page_id, notes_result)
            elif getattr(self.provider, "notebooks_complete", True):
                # 书架上没有笔记记录的书：仍做一次对账，清理历史上残留的笔记
                counters = await self._reconcile_book_notes(book_id, page_id, None)
            else:
                self.logger.warning(
                    "笔记本索引不完整，跳过《%s》的笔记清理对账（防误删）",
                    book_info.title or book_id,
                )

            return SyncResult(
                success=True,
                book_id=book_id,
                book_title=book_info.title,
                notes_synced=counters["created"] + counters["updated"] + counters["adopted"],
                reviews_synced=0,
                notes_deleted=counters["deleted"],
                notes_skipped=counters["skipped"],
                notion_page_id=page_id,
            )
        except Exception as exc:
            self.logger.debug("同步 %s 失败", book_id, exc_info=True)
            return SyncResult(
                success=False,
                book_id=book_id,
                book_title=shelf_book.title or book_id,
                notes_synced=0,
                reviews_synced=0,
                error_message=str(exc),
            )

    async def sync_book_by_id(self, book_id: str) -> SyncResult:
        self.logger.info("📖 开始同步书籍：%s", book_id)
        notebooks = await self.provider.notebook_index()
        counts = notebooks.get(book_id) or {}

        shelf = await self.provider.list_shelf()
        shelf_book = next((book for book in shelf if book.book_id == book_id), None)
        if shelf_book is None:
            shelf_book = BookInfo(book_id=book_id, title="未知书籍", author="未知作者")

        self._apply_note_counts(shelf_book, counts)
        return await self.sync_book(shelf_book, force=True)

    # ------------------------------------------------------------------
    # 笔记对账（新增 / 更新 / 删除）
    # ------------------------------------------------------------------
    async def _reconcile_book_notes(
        self,
        book_id: str,
        book_page_id: str,
        notes_result: Optional[Any],
    ) -> Dict[str, int]:
        counters = {"created": 0, "updated": 0, "adopted": 0, "unchanged": 0, "deleted": 0, "skipped": 0}

        if notes_result is None:
            # 书架上没有笔记：两种来源都可安全对账，清空残留
            highlights = []
            thoughts = []
            highlights_ok = reviews_ok = True
        else:
            # 除划线外的内容统一进「笔记」库，未知类型也不会被丢掉
            highlights = [note for note in notes_result.notes if note.note_type == "bookmark"]
            thoughts = [note for note in notes_result.notes if note.note_type != "bookmark"]
            thoughts += [_review_to_note(review) for review in notes_result.reviews]
            highlights_ok = notes_result.highlights_ok
            reviews_ok = notes_result.reviews_ok

        if highlights_ok:
            counters = _merge_counters(
                counters,
                await self._reconcile_database("highlights", book_page_id, highlights),
            )
        if reviews_ok:
            counters = _merge_counters(
                counters,
                await self._reconcile_database("notes", book_page_id, thoughts),
            )

        return counters

    async def _reconcile_database(
        self, database_key: str, book_page_id: str, notes: List[ReadingNote]
    ) -> Dict[str, int]:
        counters = {"created": 0, "updated": 0, "adopted": 0, "unchanged": 0, "deleted": 0, "skipped": 0}

        existing = await self.notion_client.get_book_records(database_key, book_page_id)

        seen = set()
        for note in notes:
            if not note.content:
                counters["skipped"] += 1
                continue
            action = await self.notion_client.upsert_note(database_key, book_page_id, note, existing)
            seen.add(note.note_id)
            counters[action if action in counters else "unchanged"] += 1

        stale = [
            entry["page_id"]
            for note_id, entry in existing.items()
            if not note_id.startswith("__legacy__") and note_id not in seen
        ]
        if stale:
            counters["deleted"] = await self.notion_client.archive_pages(stale)

        return counters

    # ------------------------------------------------------------------
    # 阅读记录（历史时长）
    # ------------------------------------------------------------------
    async def sync_reading_history(self) -> Dict[str, int]:
        counters = {"created": 0, "updated": 0, "skipped": 0}
        try:
            history = await self.provider.reading_history()
        except Exception as exc:
            self.logger.error("获取阅读历史失败：%s", exc)
            return counters

        if not history:
            self.logger.warning("没有取到阅读历史数据")
            return counters

        self.logger.info("📈 阅读历史共 %s 条记录，写入「阅读记录」", len(history))
        existing = await self.notion_client.list_reading_records()

        for day, seconds in history.items():
            granularity = {4: "年", 7: "月", 10: "日"}.get(len(day), "日")
            action = await self.notion_client.upsert_reading_record(
                day, seconds, granularity, page_id=existing.get(day)
            )
            counters[action if action in counters else "skipped"] += 1
        return counters

    # ------------------------------------------------------------------
    # 状态与统计
    # ------------------------------------------------------------------
    async def get_sync_status(self) -> Dict[str, Any]:
        try:
            shelf = await self.provider.list_shelf()
            notebooks = await self.provider.notebook_index()
            notion_books = await self.notion_client.list_all_books()

            return {
                "weread_shelf_items": len(shelf),
                "weread_ebooks": sum(1 for book in shelf if not book.is_album),
                "weread_albums": sum(1 for book in shelf if book.is_album),
                "weread_books_with_notes": len(notebooks),
                "notion_synced_books": len(notion_books),
                "last_check_time": datetime.now().isoformat(),
            }
        except Exception as exc:
            self.logger.error("获取同步状态失败：%s", exc)
            return {"error": str(exc), "last_check_time": datetime.now().isoformat()}

    async def get_reading_stats(self, mode: str = "monthly", base_time: int = 0) -> Dict[str, Any]:
        return await self.provider.reading_stats(mode=mode, base_time=base_time)

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _merge_shelf_with_notes(
        self, shelf: List[BookInfo], notebooks: Dict[str, Dict[str, Any]]
    ) -> List[BookInfo]:
        merged: List[BookInfo] = []
        seen = set()

        for book in shelf:
            counts = notebooks.get(book.book_id)
            if counts:
                self._apply_note_counts(book, counts)
            seen.add(book.book_id)
            merged.append(book)

        # 有笔记但已不在书架上的书（下架、归档）同样同步，避免丢数据
        for book_id, counts in notebooks.items():
            if book_id in seen:
                continue
            orphan = BookInfo(book_id=book_id, title="未知书籍", author="未知作者")
            self._apply_note_counts(orphan, counts)
            merged.append(orphan)

        merged.sort(key=lambda book: (book.total_note_count or 0), reverse=True)
        return merged

    @staticmethod
    def _apply_note_counts(book: BookInfo, counts: Dict[str, Any]) -> None:
        book.note_count = counts.get("note_count")
        book.highlight_count = counts.get("highlight_count")
        book.bookmark_count = counts.get("bookmark_count")
        if book.read_progress is None and counts.get("reading_progress") is not None:
            book.read_progress = _norm_progress(counts.get("reading_progress"))

    @staticmethod
    def _has_notes(book: BookInfo) -> bool:
        return bool(book.total_note_count)

    @staticmethod
    def _should_sync(book: BookInfo, include_finished: bool, include_unfinished: bool) -> bool:
        finished = bool(book.finish_reading) or (book.read_progress or 0) >= 1
        return include_finished if finished else include_unfinished


def _merge_counters(base: Dict[str, int], extra: Dict[str, int]) -> Dict[str, int]:
    for key, value in extra.items():
        base[key] = base.get(key, 0) + value
    return base
