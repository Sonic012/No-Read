"""官方网关回包 → 内部模型的映射测试（离线，不访问网络）。"""

import asyncio
from datetime import datetime
from typing import Any, Dict, Iterator, List

import pytest

from src.models import BookInfo
from src.notion.template_client import NotionTemplateClient, _format_duration
from src.weread.provider import (
    NotesResult,
    OfficialWeReadProvider,
    _parse_key_start,
)


class FakeGateway:
    """复刻官方文档里给出的回包结构。"""

    def __init__(self):
        self.shelf = {
            "books": [
                {
                    "bookId": "43697528",
                    "title": "长安的荔枝",
                    "author": "马伯庸",
                    "cover": "https://cdn.example/cover.jpg",
                    "category": "精品小说-历史小说",
                    "readUpdateTime": 1720000000,
                    "finishReading": 1,
                    "readerLink": "weread://reading?bId=43697528",
                }
            ],
            "albums": [
                {
                    "albumInfo": {
                        "albumId": "ALBUM_1",
                        "name": "半小时漫画中国史",
                        "authorName": "混子哥",
                        "cover": "https://cdn.example/album.jpg",
                        "intro": "专辑简介",
                        "finish": 1,
                    },
                    "albumInfoExtra": {"secret": 0, "lectureReadUpdateTime": 1721000000},
                }
            ],
            "mp": {"name": "文章收藏"},
            "bookCount": 1,
        }
        self.info = {
            "bookId": "43697528",
            "title": "长安的荔枝",
            "author": "马伯庸",
            "cover": "https://cdn.example/cover.jpg",
            "intro": "简介",
            "category": "精品小说-历史小说",
            "publisher": "湖南文艺出版社",
            "publishTime": "2022-10-01",
            "isbn": "9787540490947",
            "wordCount": 90000,
            "newRating": 900,
        }
        self.progress = {
            "book": {
                "progress": 100,
                "recordReadingTime": 6626,
                "updateTime": 1720000000,
                "finishTime": 1720000000,
            }
        }
        self.bookmarks = {
            "updated": [
                {
                    "bookmarkId": "bm1",
                    "chapterUid": 5,
                    "markText": "一骑红尘妃子笑",
                    "createTime": 1719000000,
                    "colorStyle": 1,
                    "range": "100-120",
                },
                {"bookmarkId": "bm2", "chapterUid": 5, "markText": "", "createTime": 1719000001},
            ],
            "chapters": [{"chapterUid": 5, "chapterIdx": 1, "title": "第一章"}],
        }
        self.reviews = [
            # 划线想法：有 chapterUid
            {
                "review": {
                    "reviewId": "rv1",
                    "content": "这句写得真好",
                    "abstract": "一骑红尘妃子笑",
                    "chapterUid": 5,
                    "chapterName": "第一章",
                    "createTime": 1719100000,
                }
            },
            # 整本书评：无 chapterUid，带评分
            {
                "review": {
                    "reviewId": "rv2",
                    "content": "整本书节奏很好",
                    "createTime": 1719200000,
                    "star": 5,
                }
            },
            {"review": {"reviewId": "rv3", "content": "", "chapterUid": 5}},
        ]

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def shelf_sync(self):
        return self.shelf

    async def book_info(self, book_id: str):
        return self.info

    async def book_progress(self, book_id: str):
        return self.progress

    async def bookmark_list(self, book_id: str):
        return self.bookmarks

    async def my_reviews_all(self, book_id: str):
        return list(self.reviews), len(self.reviews)

    async def iter_my_reviews(self, book_id: str):
        for item in self.reviews:
            yield item


def _provider() -> OfficialWeReadProvider:
    provider = OfficialWeReadProvider(api_key="wrk-test", cache_path="")
    provider.gateway = FakeGateway()
    return provider


def test_list_shelf_includes_ebooks_and_albums():
    shelf = asyncio.run(_provider().list_shelf())

    assert [book.kind for book in shelf] == ["ebook", "album"]
    ebook, album = shelf
    assert ebook.book_id == "43697528"
    assert ebook.reader_link.endswith("bId=43697528")
    assert album.title == "半小时漫画中国史"
    assert album.author == "混子哥"
    assert album.category == "有声书"


def test_load_book_normalizes_units():
    book = asyncio.run(_provider().load_book("43697528"))

    assert book.rating == 45.0, "newRating 是百分制，应折算到 0-5"
    assert book.read_progress == 1.0, "progress 是 0-100，应折算到 0-1"
    assert book.finish_reading == 1
    assert book.reading_time_seconds == 6626
    assert book.isbn == "9787540490947"
    assert isinstance(book.last_read_time, datetime)


def test_load_notes_splits_highlights_thoughts_and_reviews():
    result = asyncio.run(_provider().load_notes("43697528"))
    notes, reviews = result.notes, result.reviews

    highlights = [note for note in notes if note.note_type == "bookmark"]
    thoughts = [note for note in notes if note.note_type == "review"]

    assert [note.content for note in highlights] == ["一骑红尘妃子笑"], "空划线应被跳过"
    assert highlights[0].chapter_title == "第一章"
    assert highlights[0].location == "100-120"

    assert [note.content for note in thoughts] == ["这句写得真好"]
    assert thoughts[0].abstract == "一骑红尘妃子笑"

    assert [review.content for review in reviews] == ["整本书节奏很好"]
    assert reviews[0].star_count == 5
    assert reviews[0].review_id == "review_rv2"


def test_book_status_covers_all_three_states():
    client = NotionTemplateClient.__new__(NotionTemplateClient)

    assert client._book_status(BookInfo("1", "t", "a", finish_reading=1)) == "已读"
    assert client._book_status(BookInfo("2", "t", "a", read_progress=1.0)) == "已读"
    assert client._book_status(BookInfo("3", "t", "a", read_progress=0.42)) == "在读"
    assert client._book_status(BookInfo("4", "t", "a")) == "想读"


def test_format_duration():
    assert _format_duration(6626) == "1小时50分钟"
    assert _format_duration(3600) == "1小时"
    assert _format_duration(300) == "5分钟"
    assert _format_duration(None) is None


def test_load_notes_reports_partial_failure():
    """抓取失败的来源必须被标记，供上层跳过删除对账。"""

    class HalfBrokenGateway(FakeGateway):
        async def bookmark_list(self, book_id: str):
            raise RuntimeError("boom")

    provider = _provider()
    provider.gateway = HalfBrokenGateway()

    result = asyncio.run(provider.load_notes("43697528"))

    assert isinstance(result, NotesResult)
    assert result.highlights_ok is False
    assert result.reviews_ok is True
    assert result.notes  # 想法仍然拿到了


def test_notebook_index_detects_complete_paging():
    class NotebooksGateway(FakeGateway):
        def __init__(self, books, total):
            super().__init__()
            self._books = books
            self._total = total
            self.pages = []

        async def notebook_page(self, count: int = 100, last_sort=None):
            self.pages.append(last_sort)
            if last_sort is None:
                return {
                    "totalBookCount": self._total,
                    "hasMore": 1,
                    "books": [self._books[0]],
                }
            return {"totalBookCount": self._total, "hasMore": 0, "books": [self._books[1]]}

    entries = [
        {"bookId": "b1", "reviewCount": 3, "noteCount": 10, "bookmarkCount": 1, "sort": 100},
        {"bookId": "b2", "reviewCount": 0, "noteCount": 2, "bookmarkCount": 0, "sort": 50},
    ]

    provider = _provider()
    provider.gateway = NotebooksGateway(entries, total=2)
    index = asyncio.run(provider.notebook_index())

    assert provider.notebooks_complete is True
    assert set(index) == {"b1", "b2"}
    assert index["b1"]["note_count"] == 3, "reviewCount 是想法/点评数"
    assert index["b1"]["highlight_count"] == 10, "noteCount 是划线数"
    assert index["b1"]["bookmark_count"] == 1


def test_notebook_index_marks_incomplete_when_paging_misses_books():
    class NotebooksGateway(FakeGateway):
        async def notebook_page(self, count: int = 100, last_sort=None):
            return {
                "totalBookCount": 5,
                "hasMore": 0,
                "books": [{"bookId": "b1", "reviewCount": 1, "noteCount": 1, "sort": 10}],
            }

    provider = _provider()
    provider.gateway = NotebooksGateway()
    index = asyncio.run(provider.notebook_index())

    assert set(index) == {"b1"}
    assert provider.notebooks_complete is False, "条数对不上必须标记不完整，禁止后续误删"


def test_reading_history_covers_year_month_and_day_granularity():
    day_stamp = int(datetime(2023, 6, 2, 12).timestamp())
    month_stamp = int(datetime(2024, 6, 1, 12).timestamp())
    year_2023 = int(datetime(2023, 6, 1, 12).timestamp())
    year_2024 = int(datetime(2024, 6, 1, 12).timestamp())

    class StatsGateway(FakeGateway):
        async def readdata(self, mode: str = "monthly", base_time: int = 0):
            if mode == "overall":
                return {"totalReadTime": 10800, "readTimes": {year_2023: 3600, year_2024: 7200}}
            if mode == "annually":
                if base_time == int(datetime(2023, 1, 1).timestamp()):
                    return {"dailyReadTimes": {day_stamp: 600}}
                if base_time == int(datetime(2024, 1, 1).timestamp()):
                    return {"readTimes": {month_stamp: 7200}}
                return {}
            return {}

    provider = _provider()
    provider.gateway = StatsGateway()
    history = asyncio.run(provider.reading_history())

    assert history["2023"] == 3600, "年粒度来自 overall 的按年分桶"
    assert history["2024"] == 7200
    assert history["2023-06-02"] == 600, "有日明细时用日粒度"
    assert history["2024-06"] == 7200, "无日明细时退化为月粒度"

def test_reading_history_falls_back_and_survives_failures():
    """monthly 明细失败不能中断整轮；月明细能取到就必须落到日粒度。"""
    day_stamp = int(datetime(2024, 6, 3, 12).timestamp())
    month_stamp = int(datetime(2024, 6, 1, 12).timestamp())
    year_2024 = int(datetime(2024, 6, 1, 12).timestamp())

    class StatsGateway(FakeGateway):
        async def readdata(self, mode: str = "monthly", base_time: int = 0):
            if mode == "overall":
                return {"totalReadTime": 7200, "readTimes": {year_2024: 7200}}
            if mode == "annually":
                if base_time == int(datetime(2024, 1, 1).timestamp()):
                    return {"readTimes": {month_stamp: 7200}}
                return {}
            if mode == "monthly":
                if base_time == int(datetime(2024, 6, 1).timestamp()):
                    return {"readTimes": {day_stamp: 7200}}
                return {}
            raise RuntimeError("接口异常")

    provider = _provider()
    provider.gateway = StatsGateway()
    history = asyncio.run(provider.reading_history())

    assert history["2024"] == 7200
    assert history["2024-06"] == 7200
    assert history["2024-06-03"] == 7200, "月明细可用时必须产出日粒度"


def test_reading_history_tolerates_readdata_errors():
    class BoomGateway(FakeGateway):
        async def readdata(self, mode: str = "monthly", base_time: int = 0):
            raise RuntimeError("500 Internal Server Error")

    provider = _provider()
    provider.gateway = BoomGateway()
    assert asyncio.run(provider.reading_history()) == {}


def test_parse_key_start_rejects_non_month_keys():
    assert _parse_key_start("2024-06") == (2024, 6)
    assert _parse_key_start("2024") is None
    assert _parse_key_start("2024-06-03") is None
    assert _parse_key_start("abcd-06") is None

