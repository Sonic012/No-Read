import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..weread.api_client import WeReadApiClient
from ..notion.client import NotionClient
from ..models import BookInfo, ReadingNote, BookReview, SyncResult


class SyncService:
    """微信读书到 Notion 的同步服务"""
    
    def __init__(self, weread_cookie: str, notion_token: str, notion_database_id: str):
        """
        初始化同步服务
        
        Args:
            weread_cookie: 微信读书 Cookie
            notion_token: Notion API Token
            notion_database_id: Notion 数据库 ID
        """
        self.weread_client = WeReadApiClient(cookie=weread_cookie, rate_limit=5)
        self.notion_client = NotionClient(token=notion_token, database_id=notion_database_id)
        self.logger = logging.getLogger(__name__)
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.weread_client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.weread_client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def sync_all_books(self, include_finished: bool = True, include_unfinished: bool = True) -> List[SyncResult]:
        """
        同步所有书籍
        
        Args:
            include_finished: 是否包含已读完的书籍
            include_unfinished: 是否包含未读完的书籍
            
        Returns:
            同步结果列表
        """
        self.logger.info("🚀 开始同步微信读书数据到 Notion...")
        
        results = []
        
        try:
            # 获取笔记本列表（有笔记的书籍）
            notebooks = await self.weread_client.get_notebook_list()
            self.logger.info(f"📚 找到 {len(notebooks)} 本有笔记的书籍")
            
            # 获取完整书架信息
            entire_shelf = await self.weread_client.get_entire_shelf()
            shelf_books = entire_shelf.get('books', [])
            self.logger.info(f"📖 书架总计 {len(shelf_books)} 本书籍")
            
            # 合并书籍信息，优先处理有笔记的书籍
            books_to_sync = {}
            
            # 添加有笔记的书籍
            for notebook in notebooks:
                book_id = notebook['bookId']
                books_to_sync[book_id] = {
                    'book_info': notebook,
                    'has_notes': True
                }
            
            # 添加书架上的其他书籍
            for shelf_book in shelf_books:
                book_id = shelf_book['bookId']
                if book_id not in books_to_sync:
                    books_to_sync[book_id] = {
                        'book_info': shelf_book,
                        'has_notes': False
                    }
            
            self.logger.info(f"📋 准备同步 {len(books_to_sync)} 本书籍")
            
            # 同步每本书
            for i, (book_id, book_data) in enumerate(books_to_sync.items(), 1):
                try:
                    self.logger.info(f"📖 [{i}/{len(books_to_sync)}] 同步书籍: {book_data['book_info'].get('title', '未知书籍')}")
                    
                    result = await self.sync_single_book(book_id, book_data['has_notes'])
                    results.append(result)
                    
                    if result.success:
                        self.logger.info(f"✅ 同步成功: {result.book_title} (笔记: {result.notes_synced}, 书评: {result.reviews_synced})")
                    else:
                        self.logger.error(f"❌ 同步失败: {result.book_title} - {result.error_message}")
                    
                    # 添加延迟避免请求过于频繁
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    error_msg = f"同步书籍 {book_id} 时发生错误: {str(e)}"
                    self.logger.error(error_msg)
                    results.append(SyncResult(
                        success=False,
                        book_id=book_id,
                        book_title=book_data['book_info'].get('title', '未知书籍'),
                        notes_synced=0,
                        reviews_synced=0,
                        error_message=error_msg
                    ))
            
            # 统计结果
            success_count = sum(1 for r in results if r.success)
            total_notes = sum(r.notes_synced for r in results)
            total_reviews = sum(r.reviews_synced for r in results)
            
            self.logger.info(f"🎉 同步完成! 成功: {success_count}/{len(results)}, 笔记: {total_notes}, 书评: {total_reviews}")
            
        except Exception as e:
            self.logger.error(f"❌ 同步过程中发生错误: {str(e)}")
            raise
        
        return results
    
    async def sync_single_book(self, book_id: str, has_notes: bool = True) -> SyncResult:
        """
        同步单本书籍
        
        Args:
            book_id: 书籍 ID
            has_notes: 是否有笔记
            
        Returns:
            同步结果
        """
        try:
            # 获取书籍基本信息
            book_info_raw = await self.weread_client.get_book_info(book_id)
            
            # 获取阅读进度
            read_info = await self.weread_client.get_read_info(book_id)
            
            # 构建书籍信息对象
            book_info = await self._build_book_info(book_info_raw, read_info)
            
            # 获取笔记和书评
            notes = []
            reviews = []
            
            if has_notes:
                # 获取划线记录
                bookmarks = await self.weread_client.get_bookmark_list(book_id)
                
                # 获取笔记/想法
                review_list = await self.weread_client.get_review_list(book_id)
                
                # 获取章节信息
                chapters = await self.weread_client.get_chapter_info(book_id)
                
                # 处理笔记
                notes = await self._build_reading_notes(bookmarks, review_list, chapters, book_id)
                
                # 处理书评
                reviews = await self._build_book_reviews(review_list, book_id)
            
            # 检查 Notion 中是否已存在该书籍
            existing_page = await self.notion_client.find_book_page(book_id)
            
            if existing_page:
                # 更新现有页面
                page_id = existing_page['id']
                await self.notion_client.update_book_page(page_id, book_info, notes, reviews)
                notion_page_id = page_id
            else:
                # 创建新页面
                new_page = await self.notion_client.create_book_page(book_info, notes, reviews)
                notion_page_id = new_page['id']
            
            return SyncResult(
                success=True,
                book_id=book_id,
                book_title=book_info.title,
                notes_synced=len(notes),
                reviews_synced=len(reviews),
                notion_page_id=notion_page_id
            )
            
        except Exception as e:
            return SyncResult(
                success=False,
                book_id=book_id,
                book_title="未知书籍",
                notes_synced=0,
                reviews_synced=0,
                error_message=str(e)
            )
    
    async def _build_book_info(self, book_info_raw: Dict[str, Any], read_info: Dict[str, Any]) -> BookInfo:
        """构建书籍信息对象"""
        return BookInfo(
            book_id=book_info_raw.get('bookId', ''),
            title=book_info_raw.get('title', '未知书籍'),
            author=book_info_raw.get('author', '未知作者'),
            cover=book_info_raw.get('cover', ''),
            category=book_info_raw.get('category', ''),
            isbn=book_info_raw.get('isbn', ''),
            publisher=book_info_raw.get('publisher', ''),
            publish_date=book_info_raw.get('publishTime', ''),
            intro=book_info_raw.get('intro', ''),
            rating=book_info_raw.get('newRating', 0) / 1000 if book_info_raw.get('newRating') else None,
            total_words=book_info_raw.get('totalWords', 0),
            read_progress=read_info.get('progress', 0) / 100 if read_info.get('progress') else None,
            finish_reading=book_info_raw.get('finishReading', 0),
            last_read_time=datetime.fromtimestamp(read_info.get('readUpdateTime', 0)) if read_info.get('readUpdateTime') else None
        )
    
    async def _build_reading_notes(
        self, 
        bookmarks: List[Dict[str, Any]], 
        reviews: List[Dict[str, Any]], 
        chapters: Dict[str, Dict[str, Any]], 
        book_id: str
    ) -> List[ReadingNote]:
        """构建读书笔记列表"""
        notes = []
        
        # 处理划线记录
        for bookmark in bookmarks:
            chapter_uid = str(bookmark.get('chapterUid', ''))
            chapter_info = chapters.get(chapter_uid, {})
            chapter_title = chapter_info.get('title', '未知章节')
            
            note = ReadingNote(
                note_id=f"bookmark_{bookmark.get('bookmarkId', '')}",
                book_id=book_id,
                chapter_title=chapter_title,
                chapter_uid=chapter_uid,
                content=bookmark.get('markText', ''),
                note_type='bookmark',
                create_time=datetime.fromtimestamp(bookmark.get('createTime', 0)),
                color_style=bookmark.get('colorStyle', 0),
                is_private=bookmark.get('isPrivate', False)
            )
            notes.append(note)
        
        # 处理想法/笔记
        for review in reviews:
            if review.get('type') != 4:  # 跳过书评
                chapter_uid = str(review.get('chapterUid', ''))
                chapter_info = chapters.get(chapter_uid, {})
                chapter_title = chapter_info.get('title', '未知章节')
                
                note = ReadingNote(
                    note_id=f"review_{review.get('reviewId', '')}",
                    book_id=book_id,
                    chapter_title=chapter_title,
                    chapter_uid=chapter_uid,
                    content=review.get('content', ''),
                    note_type='review',
                    create_time=datetime.fromtimestamp(review.get('createTime', 0)),
                    is_private=review.get('isPrivate', False)
                )
                notes.append(note)
        
        return notes
    
    async def _build_book_reviews(self, reviews: List[Dict[str, Any]], book_id: str) -> List[BookReview]:
        """构建书评列表"""
        book_reviews = []
        
        for review in reviews:
            if review.get('type') == 4:  # 书评类型
                book_review = BookReview(
                    review_id=f"review_{review.get('reviewId', '')}",
                    book_id=book_id,
                    content=review.get('content', ''),
                    create_time=datetime.fromtimestamp(review.get('createTime', 0)),
                    is_private=review.get('isPrivate', False),
                    star_count=review.get('starCount', 0)
                )
                book_reviews.append(book_review)
        
        return book_reviews
    
    async def sync_book_by_id(self, book_id: str) -> SyncResult:
        """
        根据书籍 ID 同步单本书籍
        
        Args:
            book_id: 书籍 ID
            
        Returns:
            同步结果
        """
        self.logger.info(f"📖 开始同步书籍: {book_id}")
        
        # 检查书籍是否有笔记
        notebooks = await self.weread_client.get_notebook_list()
        has_notes = any(notebook['bookId'] == book_id for notebook in notebooks)
        
        result = await self.sync_single_book(book_id, has_notes)
        
        if result.success:
            self.logger.info(f"✅ 书籍同步成功: {result.book_title}")
        else:
            self.logger.error(f"❌ 书籍同步失败: {result.error_message}")
        
        return result
    
    async def get_sync_status(self) -> Dict[str, Any]:
        """
        获取同步状态
        
        Returns:
            同步状态信息
        """
        try:
            # 获取微信读书数据统计
            notebooks = await self.weread_client.get_notebook_list()
            entire_shelf = await self.weread_client.get_entire_shelf()
            shelf_books = entire_shelf.get('books', [])
            
            # 获取 Notion 数据统计
            notion_books = await self.notion_client.list_all_books()
            
            return {
                'weread_books_with_notes': len(notebooks),
                'weread_total_books': len(shelf_books),
                'notion_synced_books': len(notion_books),
                'last_check_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"获取同步状态失败: {str(e)}")
            return {
                'error': str(e),
                'last_check_time': datetime.now().isoformat()
            }