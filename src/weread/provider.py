"""微信读书数据源抽象层。

业务层（``src/sync/service.py``）只依赖 ``WeReadProvider`` 协议，
不再直接接触任何 HTTP 细节。这样数据源从「Cookie 抓取」切换到
「官方 Agent API Gateway」时，改动被收敛在本目录内。
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, Tuple

from ..models import BookInfo, BookReview, ReadingNote
from .gateway import WeReadGateway

DEFAULT_CACHE_PATH = "logs/book_metadata.json"
DEFAULT_CACHE_TTL = 7 * 24 * 3600  # 元数据缓存 7 天，避免每日全量重拉 /book/info


@dataclass
class NotesResult:
    """一次笔记抓取的结果，带各来源的成功标记。

    成功标记用于「防误删」：只有当某个来源确认抓取成功后，
    才允许对该来源做「上游已删除」的对账。
    """

    notes: List[ReadingNote] = field(default_factory=list)
    reviews: List[BookReview] = field(default_factory=list)
    # 完整性标记：False 表示这次没取全，允许写入已取到的部分，但禁止按
    # 「上游已删除」清理，避免半截数据把 Notion 里的正确记录删掉。
    highlights_ok: bool = True
    reviews_ok: bool = True


@dataclass
class BookBundle:
    """一本书的完整同步素材。"""

    book: BookInfo
    notes: List[ReadingNote] = field(default_factory=list)
    reviews: List[BookReview] = field(default_factory=list)
    has_notes: bool = False


class WeReadProvider(Protocol):
    """数据源契约。任何实现只要满足这些方法，就能驱动同步服务。"""

    async def __aenter__(self) -> "WeReadProvider": ...

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None: ...

    async def list_shelf(self) -> List[BookInfo]: ...

    async def load_book(
        self, book_id: str, shelf_info: Optional[BookInfo] = None, force: bool = False
    ) -> BookInfo: ...

    async def load_notes(self, book_id: str) -> NotesResult: ...

    async def reading_stats(self, mode: str = "monthly", base_time: int = 0) -> Dict[str, Any]: ...


class OfficialWeReadProvider:
    """官方 Agent API Gateway 实现。"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        skill_version: Optional[str] = None,
        rate_limit: int = 30,
        cache_path: str = DEFAULT_CACHE_PATH,
        cache_ttl: int = DEFAULT_CACHE_TTL,
    ):
        self.gateway = WeReadGateway(
            api_key=api_key, skill_version=skill_version, rate_limit=rate_limit
        )
        self.logger = logging.getLogger(__name__)
        self.cache_path = cache_path
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_dirty = False
        self._notebook_index: Optional[Dict[str, Dict[str, Any]]] = None
        # 笔记本索引是否完整（分页中途失败/条数对不上时为 False，用于禁止误删）
        self.notebooks_complete = True
        self._load_cache()

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    async def __aenter__(self) -> "OfficialWeReadProvider":
        await self.gateway.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self._save_cache()
        await self.gateway.__aexit__(exc_type, exc_val, exc_tb)

    # ------------------------------------------------------------------
    # 元数据缓存：书籍详情变化很慢，没必要每天重拉
    # ------------------------------------------------------------------
    def _load_cache(self) -> None:
        if not self.cache_path or not os.path.exists(self.cache_path):
            return
        try:
            with open(self.cache_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, dict):
                self._cache = payload
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.warning("读取书籍元数据缓存失败，将忽略：%s", exc)

    def _save_cache(self) -> None:
        if not self._cache_dirty or not self.cache_path:
            return
        try:
            directory = os.path.dirname(self.cache_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as handle:
                json.dump(self._cache, handle, ensure_ascii=False, indent=1)
            self._cache_dirty = False
        except OSError as exc:
            self.logger.warning("写入书籍元数据缓存失败：%s", exc)

    def _cache_get(self, book_id: str) -> Optional[Dict[str, Any]]:
        entry = self._cache.get(book_id)
        if not entry:
            return None
        if self.cache_ttl >= 0 and time.time() - entry.get("cached_at", 0) > self.cache_ttl:
            return None
        return entry

    def _cache_put(self, book_id: str, info: Dict[str, Any], progress: Dict[str, Any]) -> None:
        self._cache[book_id] = {
            "cached_at": time.time(),
            "info": info,
            "progress": progress,
        }
        self._cache_dirty = True

    # ------------------------------------------------------------------
    # 书架
    # ------------------------------------------------------------------
    async def list_shelf(self) -> List[BookInfo]:
        payload = await self.gateway.shelf_sync()
        books: List[BookInfo] = []

        for raw in payload.get("books") or []:
            books.append(self._shelf_book_to_info(raw, kind="ebook"))

        for raw in payload.get("albums") or []:
            album = self._album_to_info(raw)
            if album:
                books.append(album)

        return books

    async def notebook_index(self) -> Dict[str, Dict[str, Any]]:
        """有笔记的书籍索引：book_id -> 各口径笔记数 + 阅读进度。"""
        if self._notebook_index is not None:
            return self._notebook_index

        index: Dict[str, Dict[str, Any]] = {}
        total: Optional[int] = None
        last_sort: Optional[int] = None

        while True:
            page = await self.gateway.notebook_page(count=100, last_sort=last_sort)
            books = page.get("books") or []
            if total is None:
                total = page.get("totalBookCount")

            for entry in books:
                book_id = entry.get("bookId")
                if not book_id:
                    continue
                index[book_id] = {
                    "note_count": entry.get("reviewCount", 0) or 0,
                    "highlight_count": entry.get("noteCount", 0) or 0,
                    "bookmark_count": entry.get("bookmarkCount", 0) or 0,
                    "reading_progress": entry.get("readingProgress"),
                    "marked_status": entry.get("markedStatus"),
                }

            if not page.get("hasMore") or not books:
                break
            last_sort = books[-1].get("sort")
            if not last_sort:
                break

        # 条数与服务端声明不一致说明分页没走完，此时绝不允许按「上游已删除」清理
        if total and len(index) < total:
            self.notebooks_complete = False
            self.logger.warning(
                "笔记本索引不完整：应 %s 本，实际 %s 本；本次跳过「无笔记书籍」的清理对账",
                total,
                len(index),
            )

        self._notebook_index = index
        self.logger.info("📓 找到 %s 本有笔记的书籍（服务端声明 %s 本）", len(index), total or len(index))
        return index

    # ------------------------------------------------------------------
    # 单本书
    # ------------------------------------------------------------------
    async def load_book(
        self, book_id: str, shelf_info: Optional[BookInfo] = None, force: bool = False
    ) -> BookInfo:
        cached = None if force else self._cache_get(book_id)
        if cached:
            return self._merge_book(shelf_info, cached.get("info") or {}, cached.get("progress") or {}, cached=True)

        info: Dict[str, Any] = {}
        try:
            info = await self.gateway.book_info(book_id)
        except Exception as exc:
            self.logger.warning("获取书籍详情失败，改用书架信息：%s - %s", book_id, exc)

        progress: Dict[str, Any] = {}
        try:
            progress = await self.gateway.book_progress(book_id)
        except Exception as exc:
            self.logger.debug("获取阅读进度失败：%s - %s", book_id, exc)

        if info or progress:
            self._cache_put(book_id, info, progress)

        return self._merge_book(shelf_info, info, progress)

    async def load_notes(self, book_id: str) -> NotesResult:
        result = NotesResult()

        try:
            bookmarks = await self.gateway.bookmark_list(book_id)
        except Exception as exc:
            self.logger.warning("获取划线失败（本次跳过划线对账）：%s - %s", book_id, exc)
            bookmarks = {}
            result.highlights_ok = False

        chapters = {
            str(chapter.get("chapterUid")): chapter
            for chapter in (bookmarks.get("chapters") or [])
            if chapter.get("chapterUid") is not None
        }

        for raw in bookmarks.get("updated") or []:
            mark_text = raw.get("markText")
            if not mark_text:
                continue
            chapter_uid = str(raw.get("chapterUid", ""))
            result.notes.append(
                ReadingNote(
                    note_id=f"bookmark_{raw.get('bookmarkId', '')}",
                    book_id=book_id,
                    chapter_title=(chapters.get(chapter_uid) or {}).get("title") or "未知章节",
                    chapter_uid=chapter_uid,
                    content=mark_text,
                    note_type="bookmark",
                    create_time=_to_datetime(raw.get("createTime")),
                    color_style=raw.get("colorStyle"),
                    location=raw.get("range"),
                )
            )

        try:
            items, total = await self.gateway.my_reviews_all(book_id)
            if total is not None and len(items) < total:
                self.logger.warning(
                    "书籍 %s 的想法/点评未取全：上游声明 %s 条，实取 %s 条；"
                    "本次只写入不清理（防误删），下次同步会重试",
                    book_id,
                    total,
                    len(items),
                )
                result.reviews_ok = False
            for item in items:
                review = item.get("review") if isinstance(item.get("review"), dict) else item
                content = review.get("content")
                if not content:
                    continue

                review_id = str(review.get("reviewId") or item.get("reviewId") or "")
                create_time = _to_datetime(review.get("createTime"))

                # 无 chapterUid 的个人内容是整本书评
                if not review.get("chapterUid"):
                    result.reviews.append(
                        BookReview(
                            review_id=f"review_{review_id}",
                            book_id=book_id,
                            content=content,
                            create_time=create_time,
                            star_count=review.get("star"),
                        )
                    )
                    continue

                result.notes.append(
                    ReadingNote(
                        note_id=f"review_{review_id}",
                        book_id=book_id,
                        chapter_title=review.get("chapterName") or "未知章节",
                        chapter_uid=str(review.get("chapterUid", "")),
                        content=content,
                        note_type="review",
                        create_time=create_time,
                        abstract=review.get("abstract"),
                        location=review.get("range"),
                    )
                )
        except Exception as exc:
            self.logger.warning("获取想法/点评失败（本次跳过笔记对账）：%s - %s", book_id, exc)
            result.reviews_ok = False

        return result

    # ------------------------------------------------------------------
    # 阅读统计
    # ------------------------------------------------------------------
    async def reading_stats(self, mode: str = "monthly", base_time: int = 0) -> Dict[str, Any]:
        return await self.gateway.readdata(mode=mode, base_time=base_time)

    async def reading_history(self) -> Dict[str, int]:
        """回溯全部阅读历史，返回 ``{日期: 秒数}``，含 年 / 月 / 日 三个粒度。

        官方 ``/readdata/detail`` 的口径：
        - ``overall`` 的 ``readTimes`` 按年分桶 → 年粒度 ``YYYY``
        - ``annually`` 的 ``readTimes`` 按月分桶 → 月粒度 ``YYYY-MM``
        - ``monthly`` 的 ``readTimes`` 按天分桶 → 日粒度 ``YYYY-MM-DD``
          （``dailyReadTimes`` 是文档里提到但实际不返回的字段，不能依赖）

        因此日粒度只能逐月取回；只查「年度明细里读过」的月份，避免空跑。
        """
        buckets: Dict[str, int] = {}

        try:
            overall = await self.gateway.readdata(mode="overall")
        except Exception as exc:
            self.logger.warning("获取总阅读统计失败：%s", exc)
            overall = {}

        for stamp, seconds in (overall.get("readTimes") or {}).items():
            key = _stamp_to_key(stamp, "%Y")
            if key:
                buckets[key] = buckets.get(key, 0) + int(seconds or 0)

        start_year = _first_reading_year(overall)
        current_year = datetime.now().year
        if start_year is None:
            return {key: value for key, value in sorted(buckets.items()) if value > 0}

        months_with_data: List[Tuple[int, int]] = []

        for year in range(start_year, current_year + 1):
            data = await self._readdata_or_empty(mode="annually", base_time=_year_start(year))

            daily = data.get("dailyReadTimes") or {}
            for stamp, seconds in (daily or {}).items():
                key = _stamp_to_key(stamp, "%Y-%m-%d")
                if key:
                    buckets[key] = buckets.get(key, 0) + int(seconds or 0)

            for stamp, seconds in (data.get("readTimes") or {}).items():
                key = _stamp_to_key(stamp, "%Y-%m")
                if not key:
                    continue
                buckets[key] = buckets.get(key, 0) + int(seconds or 0)
                # 只在「该月有实际时长」时再拉一次日明细，省掉大量空请求
                if int(seconds or 0) > 0:
                    parsed = _parse_key_start(key)
                    if parsed is not None:
                        months_with_data.append(parsed)

        for year, month in sorted(set(months_with_data)):
            data = await self._readdata_or_empty(mode="monthly", base_time=_month_start(year, month))
            for stamp, seconds in (data.get("readTimes") or {}).items():
                key = _stamp_to_key(stamp, "%Y-%m-%d")
                if key:
                    buckets[key] = buckets.get(key, 0) + int(seconds or 0)

        return {key: value for key, value in sorted(buckets.items()) if value > 0}

    async def _readdata_or_empty(self, mode: str, base_time: int = 0) -> Dict[str, Any]:
        """取阅读统计，失败时只告警不中断整轮同步。"""
        try:
            return await self.gateway.readdata(mode=mode, base_time=base_time)
        except Exception as exc:
            self.logger.warning("获取阅读统计失败（mode=%s）：%s", mode, exc)
            return {}

    # ------------------------------------------------------------------
    # 归一化
    # ------------------------------------------------------------------
    @staticmethod
    def _shelf_book_to_info(raw: Dict[str, Any], kind: str = "ebook") -> BookInfo:
        finish = raw.get("finishReading")
        return BookInfo(
            book_id=str(raw.get("bookId", "")),
            title=raw.get("title") or "未知书籍",
            author=raw.get("author") or "未知作者",
            cover=raw.get("cover"),
            category=raw.get("category"),
            finish_reading=finish,
            last_read_time=_to_datetime(raw.get("readUpdateTime")),
            reader_link=raw.get("readerLink") or raw.get("deepLink"),
            kind=kind,
        )

    @staticmethod
    def _album_to_info(raw: Dict[str, Any]) -> Optional[BookInfo]:
        album = raw.get("albumInfo") or {}
        extra = raw.get("albumInfoExtra") or {}
        album_id = album.get("albumId")
        if not album_id:
            return None
        return BookInfo(
            book_id=str(album_id),
            title=album.get("name") or "未知专辑",
            author=album.get("authorName") or "未知作者",
            cover=album.get("cover"),
            intro=album.get("intro"),
            category="有声书",
            finish_reading=1 if album.get("finish") else 0,
            last_read_time=_to_datetime(extra.get("lectureReadUpdateTime")),
            kind="album",
        )

    @staticmethod
    def _merge_book(
        shelf_info: Optional[BookInfo],
        info: Dict[str, Any],
        progress: Dict[str, Any],
        cached: bool = False,
    ) -> BookInfo:
        book_id = info.get("bookId") or (shelf_info.book_id if shelf_info else "")
        base = shelf_info or BookInfo(book_id=str(book_id), title="未知书籍", author="未知作者")

        progress_book = progress.get("book") if isinstance(progress.get("book"), dict) else progress
        raw_progress = progress_book.get("progress")

        rating = info.get("newRating")
        reading_seconds = progress_book.get("recordReadingTime")

        return BookInfo(
            book_id=str(book_id or base.book_id),
            title=info.get("title") or base.title,
            author=info.get("author") or base.author,
            cover=info.get("cover") or base.cover,
            category=info.get("category") or base.category,
            isbn=info.get("isbn") or base.isbn,
            publisher=info.get("publisher") or base.publisher,
            publish_date=info.get("publishTime") or base.publish_date,
            intro=info.get("intro") or base.intro,
            rating=round(rating / 20, 1) if rating else base.rating,
            total_words=info.get("wordCount") or base.total_words,
            read_progress=_norm_progress(raw_progress, base.read_progress),
            finish_reading=_norm_finish(raw_progress, progress_book.get("finishTime"), base.finish_reading),
            last_read_time=(
                _to_datetime(progress_book.get("updateTime"))
                or _to_datetime(progress_book.get("readUpdateTime"))
                or base.last_read_time
            ),
            reading_time_seconds=reading_seconds if reading_seconds is not None else base.reading_time_seconds,
            reader_link=info.get("readerLink") or base.reader_link,
            kind=base.kind,
            note_count=base.note_count,
            highlight_count=base.highlight_count,
            bookmark_count=base.bookmark_count,
        )


def _year_start(year: int) -> int:
    return int(datetime(year, 1, 1).timestamp())


def _month_start(year: int, month: int) -> int:
    return int(datetime(year, month, 1).timestamp())


def _parse_key_start(key: str) -> Optional[Tuple[int, int]]:
    """把 ``YYYY-MM`` 解析成 ``(年, 月)``。"""
    parts = key.split("-")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        return None
    return int(parts[0]), int(parts[1])


def _first_reading_year(overall: Dict[str, Any]) -> Optional[int]:
    """从 overall 统计的按年分桶里推断最早的阅读年份。"""
    years = []
    for stamp in overall.get("readTimes") or {}:
        key = _stamp_to_key(stamp, "%Y")
        if key and key.isdigit():
            years.append(int(key))

    if years:
        return min(years)
    return datetime.now().year if overall.get("totalReadTime") else None


def _stamp_to_key(stamp: Any, fmt: str) -> Optional[str]:
    try:
        return datetime.fromtimestamp(int(stamp)).strftime(fmt)
    except (ValueError, TypeError, OSError):
        return None


def _to_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value))
    except (ValueError, TypeError, OSError):
        return None


def _norm_progress(raw: Any, fallback: Optional[float]) -> Optional[float]:
    """接口返回 0-100 整数；模型统一用 0.0-1.0。"""
    if raw is None:
        return fallback
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return fallback
    value = value / 100 if value > 1 else value
    return round(value, 4)


def _norm_finish(raw_progress: Any, finish_time: Any, fallback: Optional[int]) -> Optional[int]:
    if finish_time:
        return 1
    try:
        if raw_progress is not None and float(raw_progress) >= 100:
            return 1
    except (TypeError, ValueError):
        pass
    return fallback if fallback is not None else 0
