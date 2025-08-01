#!/usr/bin/env python3
"""
微信读书到 Notion 同步示例

这个脚本展示了如何使用同步服务的 API 进行编程化同步。
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import config
except ImportError:
    print("❌ 配置文件不存在！请先创建 config.py")
    sys.exit(1)

from src.sync.service import SyncService


async def example_sync_all():
    """示例：同步所有书籍"""
    print("📚 示例：同步所有书籍")
    
    async with SyncService(
        weread_cookie=config.WEREAD_COOKIE,
        notion_token=config.NOTION_TOKEN,
        notion_database_id=config.NOTION_DATABASE_ID
    ) as sync_service:
        
        # 获取同步状态
        status = await sync_service.get_sync_status()
        print(f"📊 当前状态: {status}")
        
        # 同步所有书籍
        results = await sync_service.sync_all_books()
        
        # 显示结果
        success_count = sum(1 for r in results if r.success)
        print(f"✅ 同步完成: {success_count}/{len(results)} 本书籍")


async def example_sync_single():
    """示例：同步单本书籍"""
    print("📖 示例：同步单本书籍")
    
    # 这里需要替换为实际的书籍 ID
    book_id = "your_book_id_here"
    
    async with SyncService(
        weread_cookie=config.WEREAD_COOKIE,
        notion_token=config.NOTION_TOKEN,
        notion_database_id=config.NOTION_DATABASE_ID
    ) as sync_service:
        
        result = await sync_service.sync_book_by_id(book_id)
        
        if result.success:
            print(f"✅ 同步成功: {result.book_title}")
            print(f"   📝 笔记: {result.notes_synced} 条")
            print(f"   💭 书评: {result.reviews_synced} 条")
        else:
            print(f"❌ 同步失败: {result.error_message}")


async def example_get_status():
    """示例：获取同步状态"""
    print("📊 示例：获取同步状态")
    
    async with SyncService(
        weread_cookie=config.WEREAD_COOKIE,
        notion_token=config.NOTION_TOKEN,
        notion_database_id=config.NOTION_DATABASE_ID
    ) as sync_service:
        
        status = await sync_service.get_sync_status()
        
        if 'error' in status:
            print(f"❌ 获取状态失败: {status['error']}")
        else:
            print(f"📚 微信读书总书籍: {status['weread_total_books']} 本")
            print(f"📝 有笔记的书籍: {status['weread_books_with_notes']} 本")
            print(f"🗂️  Notion 已同步: {status['notion_synced_books']} 本")


async def main():
    """主函数"""
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🚀 微信读书到 Notion 同步示例")
    print("=" * 50)
    
    try:
        # 示例1：获取同步状态
        await example_get_status()
        print()
        
        # 示例2：同步单本书籍（需要设置实际的书籍 ID）
        # await example_sync_single()
        # print()
        
        # 示例3：同步所有书籍（谨慎使用，会同步所有书籍）
        # await example_sync_all()
        
        print("✅ 示例执行完成")
        
    except Exception as e:
        print(f"❌ 执行失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())