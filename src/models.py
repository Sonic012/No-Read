from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class BookInfo:
    """书籍信息数据模型"""
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


@dataclass
class ReadingNote:
    """读书笔记数据模型"""
    note_id: str
    book_id: str
    chapter_title: str
    chapter_uid: str
    content: str
    note_type: str  # bookmark, review, etc.
    create_time: datetime
    page_number: Optional[int] = None
    color_style: Optional[int] = None
    is_private: Optional[bool] = None


@dataclass
class BookReview:
    """书评数据模型"""
    review_id: str
    book_id: str
    content: str
    create_time: datetime
    is_private: Optional[bool] = None
    star_count: Optional[int] = None


@dataclass
class SyncResult:
    """同步结果数据模型"""
    success: bool
    book_id: str
    book_title: str
    notes_synced: int
    reviews_synced: int
    error_message: Optional[str] = None
    notion_page_id: Optional[str] = None