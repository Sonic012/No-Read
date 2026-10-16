from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class BookInfo:
    """书籍信息（与数据源无关的中立模型）。

    单位约定：
    - ``read_progress``：0.0 ~ 1.0 的小数（微信读书接口返回的是 0-100 整数）。
    - ``rating``：0.0 ~ 5.0 的星级（接口返回百分制）。
    - ``reading_time_seconds``：累计阅读/收听时长，秒。
    """

    book_id: str
    title: str
    author: str
    cover: Optional[str] = None
    category: Optional[str] = None
    isbn: Optional[str] = None
    publisher: Optional[str] = None
    publish_date: Optional[str] = None
    intro: Optional[str] = None
    rating: Optional[float] = None
    total_words: Optional[int] = None
    read_progress: Optional[float] = None
    finish_reading: Optional[int] = None
    last_read_time: Optional[datetime] = None
    reading_time_seconds: Optional[int] = None
    reader_link: Optional[str] = None
    kind: str = "ebook"  # ebook | album（有声书专辑）
    note_count: Optional[int] = None  # 想法/点评数
    highlight_count: Optional[int] = None  # 划线数
    bookmark_count: Optional[int] = None  # 书签数（仅数量）

    @property
    def is_album(self) -> bool:
        return self.kind == "album"

    @property
    def total_note_count(self) -> Optional[int]:
        """统计口径：想法/点评 + 划线 + 书签。"""
        parts = [self.note_count, self.highlight_count, self.bookmark_count]
        if all(part is None for part in parts):
            return None
        return sum(part or 0 for part in parts)


@dataclass
class ReadingNote:
    """读书笔记（划线或想法/点评）。"""

    note_id: str
    book_id: str
    chapter_title: str
    chapter_uid: str
    content: str
    note_type: str  # bookmark(划线) | review(想法/点评) | book_review(书评)
    create_time: datetime
    page_number: Optional[int] = None
    color_style: Optional[int] = None
    is_private: Optional[bool] = None
    abstract: Optional[str] = None  # 想法对应的划线原文
    location: Optional[str] = None  # 划线位置 range


@dataclass
class BookReview:
    """个人书评（整本书的点评）。"""

    review_id: str
    book_id: str
    content: str
    create_time: datetime
    is_private: Optional[bool] = None
    star_count: Optional[int] = None  # 0-5，-1 表示未评分


@dataclass
class SyncResult:
    """同步结果数据模型"""

    success: bool
    book_id: str
    book_title: str
    notes_synced: int
    reviews_synced: int
    notes_deleted: int = 0
    notes_skipped: int = 0
    error_message: Optional[str] = None
    notion_page_id: Optional[str] = None
