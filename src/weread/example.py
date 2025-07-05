"""
微信读书 API 客户端使用示例
"""

import asyncio
import os
from .api_client import WeReadApiClient


async def main():
    """使用示例"""
    # 从环境变量获取 Cookie
    cookie = os.getenv('WEREAD_COOKIE')
    if not cookie:
        print("请设置 WEREAD_COOKIE 环境变量")
        print("例如: export WEREAD_COOKIE='your_cookie_here'")
        return
    
    # 使用 API 客户端
    async with WeReadApiClient(cookie, rate_limit=5) as client:
        try:
            print("🚀 开始获取微信读书数据...")
            
            # 获取笔记本列表
            notebooks = await client.get_notebook_list()
            print(f"📚 找到 {len(notebooks)} 本有笔记的书籍")
            
            if not notebooks:
                print("❌ 没有找到任何笔记，请确认账号中有读书笔记")
                return
            
            # 处理第一本书
            book = notebooks[0]
            book_id = book['bookId']
            print(f"\n📖 正在处理: {book.get('title', '未知书籍')} (ID: {book_id})")
            
            # 获取书籍详细信息
            book_info = await client.get_book_info(book_id)
            print(f"   作者: {book_info.get('author', '未知')}")
            print(f"   分类: {book_info.get('category', '未知')}")
            
            # 获取划线记录
            bookmarks = await client.get_bookmark_list(book_id)
            print(f"   📝 划线数量: {len(bookmarks)}")
            
            # 获取笔记/想法
            reviews = await client.get_review_list(book_id)
            print(f"   💭 笔记数量: {len(reviews)}")
            
            # 获取章节信息
            chapters = await client.get_chapter_info(book_id)
            print(f"   📑 章节数量: {len(chapters)}")
            
            # 获取阅读进度
            read_info = await client.get_read_info(book_id)
            progress = read_info.get('progress', 0)
            print(f"   📊 阅读进度: {progress}%")
            
            print("\n✅ 数据获取完成！")
            
        except Exception as e:
            print(f"❌ 错误: {e}")


if __name__ == "__main__":
    asyncio.run(main()) 