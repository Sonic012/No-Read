

import asyncio
import json
import os
import random
import time
from typing import Dict, List, Optional, Any
import httpx
from aiolimiter import AsyncLimiter


class WeReadApiClient:
    """微信读书 API 客户端"""
    
    # API URL 常量
    WEREAD_URL = "https://weread.qq.com/"
    WEREAD_NOTEBOOKS_URL = "https://weread.qq.com/api/user/notebook"
    WEREAD_BOOK_INFO_URL = "https://weread.qq.com/api/book/info"
    WEREAD_BOOKMARKLIST_URL = "https://weread.qq.com/web/book/bookmarklist"
    WEREAD_CHAPTER_INFO_URL = "https://weread.qq.com/web/book/chapterInfos"
    WEREAD_REVIEW_LIST_URL = "https://weread.qq.com/web/review/list"
    WEREAD_READ_INFO_URL = "https://weread.qq.com/web/book/getProgress"
    WEREAD_SHELF_SYNC_URL = "https://weread.qq.com/web/shelf/sync"
    WEREAD_BEST_REVIEW_URL = "https://weread.qq.com/web/review/list/best"
    
    def __init__(self, cookie: str = None, rate_limit: int = 10):
        """
        初始化微信读书 API 客户端
        
        Args:
            cookie: 微信读书 Cookie
            rate_limit: 每60秒最多请求次数
        """
        self.cookie = cookie or self._get_cookie_from_env()
        self.client: Optional[httpx.AsyncClient] = None
        self.rate_limiter = AsyncLimiter(max_rate=rate_limit, time_period=60)
        self.initialized = False
    
    def _get_cookie_from_env(self) -> str:
        """从环境变量获取 Cookie"""
        cookie = os.getenv('WEREAD_COOKIE')
        if not cookie:
            raise ValueError("请设置 WEREAD_COOKIE 环境变量或传入 cookie 参数")
        return cookie
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self._init_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
    
    async def _init_client(self):
        """初始化 HTTP 客户端"""
        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0),
                headers=self._get_standard_headers(),
                follow_redirects=True
            )
            self.initialized = True
    
    def _get_standard_headers(self) -> Dict[str, str]:
        """获取标准请求头"""
        return {
            'Cookie': self.cookie,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Ch-Ua': '"Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        }
    
    def _handle_error_code(self, errcode: int):
        """处理错误码"""
        if errcode in [-2012, -2010]:
            raise Exception("微信读书Cookie过期了，请重新设置")
    
    async def _make_request(
        self, 
        method: str, 
        url: str, 
        params: Dict[str, Any] = None, 
        data: Any = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """发送 HTTP 请求"""
        if not self.initialized:
            await self._init_client()
        
        # 添加时间戳避免缓存
        if params is None:
            params = {}
        if method.upper() == 'GET':
            params['_'] = int(time.time() * 1000)
        
        for attempt in range(max_retries):
            try:
                async with self.rate_limiter:
                    # 添加随机延迟，模拟人类行为
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                    
                    if method.upper() == 'GET':
                        response = await self.client.get(url, params=params)
                    else:
                        headers = {'Content-Type': 'application/json;charset=UTF-8'}
                        response = await self.client.post(
                            url, 
                            params=params, 
                            json=data, 
                            headers=headers
                        )
                    
                    response.raise_for_status()
                    result = response.json()
                    
                    # 检查错误码
                    if 'errcode' in result and result['errcode'] != 0:
                        self._handle_error_code(result['errcode'])
                        raise Exception(f"API 返回错误: {result.get('errmsg', 'Unknown error')} (code: {result['errcode']})")
                    
                    return result
                    
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                
                wait_time = (2 ** attempt) + random.uniform(1, 3)
                print(f"请求失败，{wait_time:.1f}秒后重试... (尝试 {attempt + 1}/{max_retries})")
                await asyncio.sleep(wait_time)
    
    async def visit_homepage(self):
        """访问主页，初始化会话"""
        try:
            await self.client.get(self.WEREAD_URL)
        except Exception as e:
            print(f"访问主页失败: {e}")
    
    async def get_bookshelf(self) -> Dict[str, Any]:
        """获取书架信息（存在笔记的书籍）"""
        return await self._make_request('GET', self.WEREAD_NOTEBOOKS_URL)
    
    async def get_entire_shelf(self) -> Dict[str, Any]:
        """获取所有书架书籍信息"""
        return await self._make_request('GET', self.WEREAD_SHELF_SYNC_URL)
    
    async def get_notebook_list(self) -> List[Dict[str, Any]]:
        """获取笔记本列表"""
        data = await self._make_request('GET', self.WEREAD_NOTEBOOKS_URL)
        return data.get('books', [])
    
    async def get_book_info(self, book_id: str) -> Dict[str, Any]:
        """获取书籍信息"""
        params = {'bookId': book_id}
        return await self._make_request('GET', self.WEREAD_BOOK_INFO_URL, params=params)
    
    async def get_bookmark_list(self, book_id: str) -> List[Dict[str, Any]]:
        """获取书籍的划线记录"""
        params = {'bookId': book_id}
        data = await self._make_request('GET', self.WEREAD_BOOKMARKLIST_URL, params=params)
        bookmarks = data.get('updated', [])
        # 过滤有效的划线记录
        return [mark for mark in bookmarks if mark.get('markText') and mark.get('chapterUid')]
    
    async def get_read_info(self, book_id: str) -> Dict[str, Any]:
        """获取阅读进度"""
        params = {'bookId': book_id}
        return await self._make_request('GET', self.WEREAD_READ_INFO_URL, params=params)
    
    async def get_review_list(self, book_id: str) -> List[Dict[str, Any]]:
        """获取笔记/想法列表"""
        params = {
            'bookId': book_id,
            'listType': 4,
            'maxIdx': 0,
            'count': 0,
            'listMode': 2,
            'syncKey': 0
        }
        data = await self._make_request('GET', self.WEREAD_REVIEW_LIST_URL, params=params)
        reviews = data.get('reviews', [])
        
        # 转换格式
        reviews = [x.get('review') for x in reviews if x.get('review')]
        
        # 为书评添加 chapterUid
        for review in reviews:
            if review.get('type') == 4:
                review['chapterUid'] = 1000000
        
        return reviews
    
    async def get_best_reviews(
        self, 
        book_id: str, 
        count: int = 10, 
        max_idx: int = 0, 
        sync_key: int = 0
    ) -> Dict[str, Any]:
        """获取热门书评"""
        params = {
            'bookId': book_id,
            'synckey': sync_key,
            'maxIdx': max_idx,
            'count': count
        }
        return await self._make_request('GET', self.WEREAD_BEST_REVIEW_URL, params=params)
    
    async def get_chapter_info(self, book_id: str) -> Dict[str, Dict[str, Any]]:
        """获取章节信息"""
        # 先访问主页和获取笔记列表，初始化会话
        await self.visit_homepage()
        await self.get_notebook_list()
        
        # 添加随机延迟
        await asyncio.sleep(random.uniform(1, 3))
        
        # 请求章节信息
        data = {'bookIds': [book_id]}
        result = await self._make_request('POST', self.WEREAD_CHAPTER_INFO_URL, data=data)
        
        # 处理不同的响应格式
        update = None
        if result.get('data') and len(result['data']) == 1 and result['data'][0].get('updated'):
            update = result['data'][0]['updated']
        elif result.get('updated') and isinstance(result['updated'], list):
            update = result['updated']
        elif isinstance(result, list) and len(result) > 0 and result[0].get('updated'):
            update = result[0]['updated']
        elif isinstance(result, list) and len(result) > 0 and result[0].get('chapterUid'):
            update = result
        
        if update:
            # 添加点评章节
            update.append({
                'chapterUid': 1000000,
                'chapterIdx': 1000000,
                'updateTime': 1683825006,
                'readAhead': 0,
                'title': '点评',
                'level': 1
            })
            
            # 转换为字典格式
            return {str(chapter['chapterUid']): chapter for chapter in update}
        else:
            raise Exception("获取章节信息失败，返回格式不符合预期")
    
    async def close(self):
        """关闭客户端"""
        if self.client:
            await self.client.aclose()
            self.client = None
            self.initialized = False


# 使用示例
async def main():
    """使用示例"""
    # 从环境变量获取 Cookie
    cookie = os.getenv('WEREAD_COOKIE')
    if not cookie:
        print("请设置 WEREAD_COOKIE 环境变量")
        return
    
    async with WeReadApiClient(cookie) as client:
        try:
            # 获取书架信息
            bookshelf = await client.get_bookshelf()
            print("书架信息:", json.dumps(bookshelf, ensure_ascii=False, indent=2))
            
            # 获取笔记本列表
            notebooks = await client.get_notebook_list()
            print(f"找到 {len(notebooks)} 本有笔记的书籍")
            
            if notebooks:
                book_id = notebooks[0]['bookId']
                print(f"处理第一本书: {book_id}")
                
                # 获取书籍信息
                book_info = await client.get_book_info(book_id)
                print(f"书籍标题: {book_info.get('title', '未知')}")
                
                # 获取划线记录
                bookmarks = await client.get_bookmark_list(book_id)
                print(f"划线数量: {len(bookmarks)}")
                
                # 获取章节信息
                chapters = await client.get_chapter_info(book_id)
                print(f"章节数量: {len(chapters)}")
                
        except Exception as e:
            print(f"错误: {e}")


if __name__ == "__main__":
    asyncio.run(main()) 