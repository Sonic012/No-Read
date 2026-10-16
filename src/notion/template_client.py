"""Notion 多数据库模板客户端。

负责把一个「父页面 + 子数据库」结构的微信读书模板当作同步目标：
- 发现 书架 / 分类 / 作者 / 笔记 / 划线，必要时补齐 阅读记录
- 按「微信读书 ID」做真正的 upsert（新增 / 更新 / 删除）
- 保持 relation（书籍 ↔ 笔记、划线、作者、分类）
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import httpx
from aiolimiter import AsyncLimiter
from notion_client import AsyncClient
from notion_client.errors import APIResponseError, HTTPResponseError

from ..models import BookInfo, BookReview, ReadingNote

logger = logging.getLogger(__name__)

TITLE_LIMIT = 1900
BODY_CHUNK_LIMIT = 1900
MAX_APPEND_CHILDREN = 100
NOTE_ID_PROPERTY = "笔记ID"

READING_RECORD_TITLE = "阅读记录"
READING_RECORD_SCHEMA: Dict[str, Any] = {
    "日期": {"title": {}},
    "阅读时长": {"number": {"format": "number"}},
    "时长": {"rich_text": {}},
    "年": {"number": {"format": "number"}},
    "月": {"number": {"format": "number"}},
    "粒度": {"select": {"options": [{"name": "日"}, {"name": "月"}, {"name": "年"}]}},
}
GRANULARITY_OPTIONS = ("日", "月", "年")


def _clip_text(value: Optional[str], limit: int = TITLE_LIMIT) -> str:
    if not value:
        return ""
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _body_chunks(value: Optional[str], limit: int = BODY_CHUNK_LIMIT) -> List[str]:
    """把超长内容切成可写入页面正文的片段（Notion 单个文本块上限 2000 字）。"""
    if not value or len(value) <= TITLE_LIMIT:
        return []
    return [value[index : index + limit] for index in range(0, len(value), limit)]


def _batched(items: Sequence[str], size: int) -> Iterable[List[str]]:
    for index in range(0, len(items), size):
        yield list(items[index : index + size])


def _simple_paragraph_text(block: Dict[str, Any]) -> Optional[str]:
    """取「普通段落 + 单个纯文本块」的文本，其他结构一律视为用户内容。"""
    if block.get("type") != "paragraph":
        return None
    rich_text = block.get("paragraph", {}).get("rich_text", [])
    if len(rich_text) != 1:
        return None
    item = rich_text[0]
    if item.get("type") != "text" or item.get("href"):
        return None
    annotations = item.get("annotations") or {}
    if any(annotations.get(key) for key in ("bold", "italic", "strikethrough", "underline", "code", "color_link")):
        return None
    return item.get("plain_text") or item.get("text", {}).get("content", "") or ""


def _is_managed_body(blocks: Sequence[Dict[str, Any]], limit: int = BODY_CHUNK_LIMIT) -> bool:
    """判断页面正文是否完全由本工具写入的分片组成（用于安全重写，避免删掉用户内容）。"""
    # 只有超长内容才会写正文，因此本工具写入的正文必然 ≥ 2 个分片；
    # 单个短段落几乎一定是用户手写内容，不能当成自己的分片删掉。
    if len(blocks) < 2:
        return False
    texts: List[str] = []
    for block in blocks:
        text = _simple_paragraph_text(block)
        if not text or len(text) > limit:
            return False
        texts.append(text)
    return all(len(text) == limit for text in texts[:-1])


def _plain_date(value: Optional[datetime]) -> Optional[Dict[str, Dict[str, str]]]:
    if not value:
        return None
    return {"date": {"start": value.isoformat()}}


def _format_duration(seconds: Optional[int]) -> Optional[str]:
    """把秒数格式化为「X小时Y分钟」。"""
    if not seconds:
        return None
    total_minutes = int(seconds) // 60
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours}小时{minutes}分钟"
    if hours:
        return f"{hours}小时"
    return f"{minutes}分钟"


class NotionTemplateClient:
    """NoRead 多数据库模板的 Notion 客户端。"""

    # 可重试的状态码：限流与临时服务端故障
    RETRYABLE_STATUS = {429, 500, 502, 503, 504}

    CHILD_DATABASE_TITLES = {
        "books": "书架",
        "categories": "分类",
        "authors": "作者",
        "notes": "笔记",
        "highlights": "划线",
        "reading_records": "阅读记录",
    }

    def __init__(
        self,
        token: str,
        database_id: str,
        rate_limit: int = 3,
        max_retries: int = 5,
    ):
        self.client = AsyncClient(auth=token)
        self.configured_database_id = database_id
        self.database_id = database_id
        self.parent_page_id: Optional[str] = None
        self.rate_limiter = AsyncLimiter(max_rate=rate_limit, time_period=1)
        self.max_retries = max(1, max_retries)
        self.logger = logging.getLogger(__name__)
        self._ready = False
        self.database_ids: Dict[str, str] = {"books": database_id}
        self.database_properties: Dict[str, Dict[str, Any]] = {}

    async def _request(self, call, *args, **kwargs):
        """所有 Notion 请求的唯一出口：本地限流 + 429/5xx 退避重试。

        Notion 对单个集成限流，批量写入时很容易撞上 429。这里必须重试，
        否则一次 429 会让整本书的笔记只写一半，且外层只会记一条「同步失败」。
        """
        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with self.rate_limiter:
                    return await call(*args, **kwargs)
            except HTTPResponseError as exc:
                if getattr(exc, "status", None) not in self.RETRYABLE_STATUS:
                    raise
                last_error = exc
                if attempt >= self.max_retries:
                    break
                delay = self._retry_delay(exc, attempt)
                self.logger.warning(
                    "Notion 请求被限流/失败（HTTP %s），%.1fs 后重试（第 %s/%s 次）",
                    exc.status,
                    delay,
                    attempt,
                    self.max_retries,
                )
                await asyncio.sleep(delay)
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                delay = min(2 ** attempt, 30)
                self.logger.warning(
                    "Notion 网络异常：%s，%.1fs 后重试（第 %s/%s 次）",
                    exc,
                    delay,
                    attempt,
                    self.max_retries,
                )
                await asyncio.sleep(delay)

        raise last_error  # type: ignore[misc]

    @staticmethod
    def _retry_delay(exc: HTTPResponseError, attempt: int) -> float:
        """优先遵循 Retry-After，其次指数退避。"""
        headers = getattr(exc, "headers", None) or {}
        raw = headers.get("retry-after") if hasattr(headers, "get") else None
        if raw:
            try:
                return max(float(raw), 1.0)
            except (TypeError, ValueError):
                pass
        return float(min(2 ** attempt, 30))

    # ------------------------------------------------------------------
    # 发现模板结构
    # ------------------------------------------------------------------
    async def _ensure_ready(self) -> None:
        if self._ready:
            return

        try:
            database = await self._request(
                self.client.databases.retrieve, database_id=self.configured_database_id
            )
            self.database_id = database["id"]
            self.database_ids["books"] = database["id"]
            self.database_properties["books"] = database.get("properties", {})
        except APIResponseError as exc:
            if "is a page, not a database" not in str(exc):
                raise
            self.parent_page_id = self.configured_database_id
            await self._discover_child_databases()

            if "books" not in self.database_ids:
                raise ValueError("未在 Notion 页面下找到名为「书架」的数据库")

            self.database_id = self.database_ids["books"]
            database = await self._request(
                self.client.databases.retrieve, database_id=self.database_id
            )
            self.database_properties["books"] = database.get("properties", {})

        for key, db_id in self.database_ids.items():
            if key == "books" or not db_id:
                continue
            database = await self._request(self.client.databases.retrieve, database_id=db_id)
            self.database_properties[key] = database.get("properties", {})

        self._ready = True

    async def _discover_child_databases(self) -> None:
        children = await self._request(
            self.client.blocks.children.list,
            block_id=self.parent_page_id,
            page_size=100,
        )
        by_title = {
            block.get("child_database", {}).get("title"): block.get("id")
            for block in children.get("results", [])
            if block.get("type") == "child_database"
        }
        for key, title in self.CHILD_DATABASE_TITLES.items():
            db_id = by_title.get(title)
            if db_id:
                self.database_ids[key] = db_id

    async def refresh(self) -> None:
        self._ready = False
        await self._ensure_ready()

    # ------------------------------------------------------------------
    # 补齐模板结构（幂等）
    # ------------------------------------------------------------------
    async def ensure_schema(self, create_reading_records: bool = True) -> List[str]:
        """补齐同步所需的属性与数据库，返回本次实际执行的动作。"""
        await self._ensure_ready()
        actions: List[str] = []

        for key in ("notes", "highlights"):
            if key not in self.database_ids:
                continue
            if NOTE_ID_PROPERTY not in self.database_properties.get(key, {}):
                await self._add_property(key, NOTE_ID_PROPERTY, {"rich_text": {}})
                actions.append(f"{self.CHILD_DATABASE_TITLES[key]}: 新增属性 {NOTE_ID_PROPERTY}")

        if create_reading_records and "reading_records" not in self.database_ids:
            if self.parent_page_id:
                await self._create_child_database(
                    "reading_records", READING_RECORD_TITLE, READING_RECORD_SCHEMA
                )
                actions.append(f"新建数据库「{READING_RECORD_TITLE}」")

        if "reading_records" in self.database_ids:
            actions += await self._ensure_granularity_options()

        if actions:
            await self.refresh()
        return actions

    async def _ensure_granularity_options(self) -> List[str]:
        """「阅读记录」的粒度是 select，历史库可能只有 日/月，需要补上 年。"""
        prop = self.database_properties.get("reading_records", {}).get("粒度")
        if not prop or prop.get("type") != "select":
            return []

        existing = [option["name"] for option in prop["select"].get("options", [])]
        missing = [name for name in GRANULARITY_OPTIONS if name not in existing]
        if not missing:
            return []

        await self._request(
            self.client.databases.update,
            database_id=self.database_ids["reading_records"],
            properties={
                "粒度": {"select": {"options": [{"name": name} for name in existing + missing]}}
            },
        )
        return [f"{READING_RECORD_TITLE}: 粒度新增 {'/'.join(missing)}"]

    async def _add_property(self, database_key: str, name: str, schema: Dict[str, Any]) -> None:
        db_id = self.database_ids[database_key]
        await self._request(
            self.client.databases.update,
            database_id=db_id,
            properties={name: schema},
        )
        self.database_properties.setdefault(database_key, {})[name] = {"type": next(iter(schema))}

    async def _create_child_database(
        self, key: str, title: str, schema: Dict[str, Any]
    ) -> str:
        database = await self._request(
            self.client.databases.create,
            parent={"type": "page_id", "page_id": self.parent_page_id},
            title=[{"type": "text", "text": {"content": title}}],
            properties=schema,
        )
        self.database_ids[key] = database["id"]
        self.database_properties[key] = database.get("properties", {})
        return database["id"]

    def _prop_type(self, database_key: str, property_name: str) -> Optional[str]:
        return self.database_properties.get(database_key, {}).get(property_name, {}).get("type")

    # ------------------------------------------------------------------
    # 属性构造函数
    # ------------------------------------------------------------------
    @staticmethod
    def _title(value: str) -> Dict[str, List[Dict[str, Dict[str, str]]]]:
        return {"title": [{"text": {"content": _clip_text(value)}}]}

    @staticmethod
    def _rich_text(value: Optional[str]) -> Dict[str, List[Dict[str, Dict[str, str]]]]:
        text = _clip_text(value)
        return {"rich_text": [{"text": {"content": text}}]} if text else {"rich_text": []}

    @staticmethod
    def _select(value: Optional[str]) -> Optional[Dict[str, Dict[str, str]]]:
        return {"select": {"name": value}} if value else None

    @staticmethod
    def _relation(page_ids: Iterable[Optional[str]]) -> Optional[Dict[str, List[Dict[str, str]]]]:
        ids = [{"id": page_id} for page_id in page_ids if page_id]
        return {"relation": ids} if ids else None

    @staticmethod
    def _external_file(name: str, url: Optional[str]) -> Optional[Dict[str, List[Dict[str, Any]]]]:
        if not url:
            return None
        return {"files": [{"name": name, "type": "external", "external": {"url": url}}]}

    # ------------------------------------------------------------------
    # 分类 / 作者主数据
    # ------------------------------------------------------------------
    async def _find_or_create_named_page(self, database_key: str, name: Optional[str]) -> Optional[str]:
        await self._ensure_ready()
        if not name:
            return None

        db_id = self.database_ids.get(database_key)
        if not db_id:
            return None

        response = await self._request(
            self.client.databases.query,
            database_id=db_id,
            filter={"property": "名称", "title": {"equals": name}},
            page_size=1,
        )
        results = response.get("results", [])
        if results:
            return results[0]["id"]

        page = await self._request(
            self.client.pages.create,
            parent={"database_id": db_id},
            properties={"名称": self._title(name)},
        )
        return page["id"]

    # ------------------------------------------------------------------
    # 书架
    # ------------------------------------------------------------------
    async def find_book_page(self, book_id: str) -> Optional[Dict[str, Any]]:
        await self._ensure_ready()
        response = await self._request(
            self.client.databases.query,
            database_id=self.database_id,
            filter={"property": "书籍ID", "rich_text": {"equals": book_id}},
            page_size=1,
        )
        results = response.get("results", [])
        return results[0] if results else None

    def _book_status(self, book_info: BookInfo) -> Optional[str]:
        if book_info.finish_reading == 1 or (book_info.read_progress or 0) >= 1:
            return "已读"
        if (book_info.read_progress or 0) > 0:
            return "在读"
        return "想读"

    async def _book_properties(self, book_info: BookInfo) -> Dict[str, Any]:
        await self._ensure_ready()
        properties: Dict[str, Any] = {
            "书名": self._title(book_info.title),
            "书籍ID": self._rich_text(book_info.book_id),
        }

        if self._prop_type("books", "作者") == "relation":
            properties["作者"] = self._relation(
                [await self._find_or_create_named_page("authors", book_info.author)]
            )
        elif self._prop_type("books", "作者") == "rich_text":
            properties["作者"] = self._rich_text(book_info.author)

        if self._prop_type("books", "分类") == "relation":
            properties["分类"] = self._relation(
                [await self._find_or_create_named_page("categories", book_info.category)]
            )
        elif self._prop_type("books", "分类") == "select":
            properties["分类"] = self._select(book_info.category)

        year_label = f"{book_info.last_read_time.year}年" if book_info.last_read_time else None
        optional_properties = {
            "ISBN": self._rich_text(book_info.isbn),
            "出版社": self._rich_text(book_info.publisher),
            "封面": self._external_file("封面", book_info.cover),
            "阅读进度": {"number": book_info.read_progress} if book_info.read_progress is not None else None,
            "阅读时长": self._rich_text(_format_duration(book_info.reading_time_seconds)),
            "最后阅读时间": _plain_date(book_info.last_read_time),
            "年份标签": self._select(year_label),
            "状态": self._select(self._book_status(book_info)),
        }
        for name, value in optional_properties.items():
            if name in self.database_properties.get("books", {}) and value is not None:
                properties[name] = value

        return {name: value for name, value in properties.items() if value is not None}

    async def create_book_page(self, book_info: BookInfo) -> Dict[str, Any]:
        await self._ensure_ready()
        return await self._request(
            self.client.pages.create,
            parent={"database_id": self.database_id},
            properties=await self._book_properties(book_info),
        )

    async def update_book_page(self, page_id: str, book_info: BookInfo) -> Dict[str, Any]:
        await self._ensure_ready()
        return await self._request(
            self.client.pages.update,
            page_id=page_id,
            properties=await self._book_properties(book_info),
        )

    # ------------------------------------------------------------------
    # 笔记 / 划线：按「笔记ID」真 upsert
    # ------------------------------------------------------------------
    async def get_book_records(
        self, database_key: str, book_page_id: str
    ) -> Dict[str, Dict[str, Any]]:
        """取某本书在指定库中的现有记录：笔记ID -> {page_id, content, chapter}。

        没有 笔记ID 的历史记录会额外按 (内容, 章节) 建立索引，便于一次性认领，
        避免重复创建。
        """
        db_id = self.database_ids.get(database_key)
        if not db_id:
            return {}

        records: Dict[str, Dict[str, Any]] = {}
        cursor = None
        while True:
            kwargs: Dict[str, Any] = {
                "database_id": db_id,
                "filter": {"property": "书籍", "relation": {"contains": book_page_id}},
                "page_size": 100,
            }
            if cursor:
                kwargs["start_cursor"] = cursor
            response = await self._request(self.client.databases.query, **kwargs)

            for page in response.get("results", []):
                props = page.get("properties", {})
                note_id = _read_rich_text(props.get(NOTE_ID_PROPERTY))
                content = _read_title(props.get("内容"))
                chapter = _read_rich_text(props.get("章节"))
                entry = {"page_id": page["id"], "content": content, "chapter": chapter}
                if note_id:
                    records[note_id] = entry
                else:
                    records[f"__legacy__{content}|{chapter}"] = entry

            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")

        return records

    async def upsert_note(
        self,
        database_key: str,
        book_page_id: str,
        note: ReadingNote,
        existing: Dict[str, Dict[str, Any]],
    ) -> str:
        """按 笔记ID upsert 一条笔记/划线，返回 created / updated / adopted / unchanged。"""
        db_id = self.database_ids.get(database_key)
        if not db_id or not note.content:
            return "skipped"

        chapter = note.chapter_title or "未知章节"
        properties = self._note_properties(database_key, book_page_id, note, chapter)

        adopted = False
        current = existing.get(note.note_id)
        if current is None:
            legacy = existing.get(f"__legacy__{_clip_text(note.content)}|{chapter}")
            if legacy is not None:
                current = legacy
                adopted = True
            else:
                page = await self._request(
                    self.client.pages.create,
                    parent={"database_id": db_id},
                    properties=properties,
                )
                existing[note.note_id] = {
                    "page_id": page["id"],
                    "content": _clip_text(note.content),
                    "chapter": chapter,
                }
                await self._sync_overflow(page["id"], note.content)
                return "created"

        content_changed = current.get("content") != _clip_text(note.content)
        chapter_changed = current.get("chapter") != chapter
        long_content = len(note.content) > TITLE_LIMIT
        property_dirty = content_changed or chapter_changed or adopted
        body_dirty = content_changed or adopted or long_content

        if not property_dirty and not body_dirty:
            existing[note.note_id] = current
            return "unchanged"

        # 长文本每次都要确认正文分片是否已是最新，避免无谓重写
        if not property_dirty and await self._body_matches(current["page_id"], note.content):
            existing[note.note_id] = current
            return "unchanged"

        if property_dirty:
            await self._request(
                self.client.pages.update, page_id=current["page_id"], properties=properties
            )
        existing[note.note_id] = {
            "page_id": current["page_id"],
            "content": _clip_text(note.content),
            "chapter": chapter,
        }
        if body_dirty:
            await self._sync_overflow(current["page_id"], note.content)
        return "adopted" if adopted else "updated"

    def _note_properties(
        self, database_key: str, book_page_id: str, note: ReadingNote, chapter: str
    ) -> Dict[str, Any]:
        properties: Dict[str, Any] = {
            "内容": self._title(note.content),
            "书籍": self._relation([book_page_id]),
            "创建时间": _plain_date(note.create_time),
            "章节": self._rich_text(chapter),
        }

        if NOTE_ID_PROPERTY in self.database_properties.get(database_key, {}):
            properties[NOTE_ID_PROPERTY] = self._rich_text(note.note_id)

        if database_key == "notes" and self._prop_type("notes", "类型") == "select":
            properties["类型"] = self._select("书评" if note.note_type == "book_review" else "想法")
        if database_key == "highlights" and self._prop_type("highlights", "样式") == "select":
            style = str(note.color_style) if note.color_style is not None else "默认"
            properties["样式"] = self._select(style)

        return {name: value for name, value in properties.items() if value is not None}

    async def _list_child_blocks(self, block_id: str) -> List[Dict[str, Any]]:
        blocks: List[Dict[str, Any]] = []
        cursor = None
        while True:
            kwargs: Dict[str, Any] = {"block_id": block_id, "page_size": 100}
            if cursor:
                kwargs["start_cursor"] = cursor
            response = await self._request(self.client.blocks.children.list, **kwargs)
            blocks.extend(response.get("results", []))
            if not response.get("has_more"):
                return blocks
            cursor = response.get("next_cursor")

    async def _delete_blocks(self, block_ids: Sequence[str]) -> None:
        for block_id in block_ids:
            try:
                await self._request(self.client.blocks.delete, block_id=block_id)
            except APIResponseError:
                continue

    async def _body_matches(self, page_id: str, content: Optional[str]) -> bool:
        """页面正文是否已经等于该内容的完整分片（用于长文本幂等判断）。"""
        chunks = _body_chunks(content)
        children = await self._list_child_blocks(page_id)
        if not children:
            return not chunks
        if not _is_managed_body(children):
            # 用户自己写的内容，本工具不碰，视为无需改动
            return True
        return [_simple_paragraph_text(block) for block in children] == chunks

    async def _sync_overflow(self, page_id: str, content: Optional[str]) -> None:
        """把完整内容写入页面正文，保证超长笔记不丢失；已是最新则不做任何改动。

        仅当正文完全由本工具写入的分片组成时才重写，避免误删用户在页面里手写的内容。
        """
        chunks = _body_chunks(content)
        children = await self._list_child_blocks(page_id)

        if children:
            texts = [_simple_paragraph_text(block) for block in children]
            if _is_managed_body(children):
                if texts == chunks:
                    return
            else:
                if chunks:
                    logger.warning("页面 %s 正文含非同步内容，跳过正文写入以避免覆盖", page_id)
                return
            await self._delete_blocks([block["id"] for block in children])
        elif not chunks:
            return

        for batch in _batched(chunks, MAX_APPEND_CHILDREN):
            await self._request(
                self.client.blocks.children.append,
                block_id=page_id,
                children=[
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": [{"type": "text", "text": {"content": chunk}}]},
                    }
                    for chunk in batch
                ],
            )

    async def archive_pages(self, page_ids: Sequence[str]) -> int:
        count = 0
        for page_id in page_ids:
            try:
                await self._request(
                    self.client.pages.update, page_id=page_id, archived=True
                )
                count += 1
            except APIResponseError:
                continue
        return count

    # ------------------------------------------------------------------
    # 阅读记录
    # ------------------------------------------------------------------
    async def upsert_reading_record(
        self, day: str, seconds: int, granularity: str = "日", page_id: Optional[str] = None
    ) -> str:
        db_id = self.database_ids.get("reading_records")
        if not db_id:
            return "skipped"

        properties: Dict[str, Any] = {
            "日期": self._title(day),
            "阅读时长": {"number": int(seconds)},
            "时长": self._rich_text(_format_duration(seconds) or "0分钟"),
            "年": {"number": int(day[:4])} if day[:4].isdigit() else None,
            "月": {"number": int(day[5:7])} if day[5:7].isdigit() else None,
        }
        if self._prop_type("reading_records", "粒度") == "select":
            properties["粒度"] = self._select(granularity)
        properties = {name: value for name, value in properties.items() if value is not None}

        resolved = page_id
        if resolved is None:
            page = await self._find_page_by_title(db_id, "日期", day)
            resolved = page["id"] if page else None

        if resolved:
            await self._request(
                self.client.pages.update, page_id=resolved, properties=properties
            )
            return "updated"

        await self._request(
            self.client.pages.create,
            parent={"database_id": db_id},
            properties=properties,
        )
        return "created"

    async def _find_page_by_title(
        self, database_id: str, title_property: str, title: str
    ) -> Optional[Dict[str, Any]]:
        response = await self._request(
            self.client.databases.query,
            database_id=database_id,
            filter={"property": title_property, "title": {"equals": title}},
            page_size=1,
        )
        results = response.get("results", [])
        return results[0] if results else None

    # ------------------------------------------------------------------
    # 全量读取
    # ------------------------------------------------------------------
    async def list_book_page_ids(self) -> Dict[str, str]:
        """一次性取回 {书籍ID: page_id}，避免逐本查询。"""
        mapping: Dict[str, str] = {}
        for page in await self.list_all_books():
            book_id = _read_rich_text(page.get("properties", {}).get("书籍ID"))
            if book_id:
                mapping[book_id] = page["id"]
        return mapping

    async def list_note_ids(self, database_key: str) -> Dict[str, str]:
        """一次性取回某库全部 {笔记ID: page_id}，用于全量对账。"""
        db_id = self.database_ids.get(database_key)
        if not db_id:
            return {}

        mapping: Dict[str, str] = {}
        cursor = None
        while True:
            kwargs: Dict[str, Any] = {"database_id": db_id, "page_size": 100}
            if cursor:
                kwargs["start_cursor"] = cursor
            response = await self._request(self.client.databases.query, **kwargs)
            for page in response.get("results", []):
                note_id = _read_rich_text(page.get("properties", {}).get(NOTE_ID_PROPERTY))
                if note_id:
                    mapping[note_id] = page["id"]
            if not response.get("has_more"):
                return mapping
            cursor = response.get("next_cursor")

    async def list_reading_records(self) -> Dict[str, str]:
        """一次性取回 {日期: page_id}。"""
        db_id = self.database_ids.get("reading_records")
        if not db_id:
            return {}

        mapping: Dict[str, str] = {}
        cursor = None
        while True:
            kwargs: Dict[str, Any] = {"database_id": db_id, "page_size": 100}
            if cursor:
                kwargs["start_cursor"] = cursor
            response = await self._request(self.client.databases.query, **kwargs)
            for page in response.get("results", []):
                title = _read_title(page.get("properties", {}).get("日期"))
                if title:
                    mapping[title] = page["id"]
            if not response.get("has_more"):
                return mapping
            cursor = response.get("next_cursor")

    async def list_all_books(self) -> List[Dict[str, Any]]:
        await self._ensure_ready()
        books: List[Dict[str, Any]] = []
        cursor = None
        while True:
            kwargs: Dict[str, Any] = {"database_id": self.database_id, "page_size": 100}
            if cursor:
                kwargs["start_cursor"] = cursor
            response = await self._request(self.client.databases.query, **kwargs)
            books.extend(response.get("results", []))
            if not response.get("has_more"):
                return books
            cursor = response.get("next_cursor")


def _read_rich_text(prop: Optional[Dict[str, Any]]) -> str:
    if not prop:
        return ""
    return "".join(item.get("plain_text", "") for item in prop.get("rich_text", []))


def _read_title(prop: Optional[Dict[str, Any]]) -> str:
    if not prop:
        return ""
    return "".join(item.get("plain_text", "") for item in prop.get("title", []))
