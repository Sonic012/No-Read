#!/usr/bin/env python3
"""
微信读书到 Notion 同步示例

展示如何以编程方式使用同步服务。数据源为微信读书官方 Agent API。
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


async def example_get_status():
    """示例：获取同步状态"""
    print("📊 示例：获取同步状态")

    async with SyncService.from_config(config) as sync_service:
        status = await sync_service.get_sync_status()

        if "error" in status:
            print(f"❌ 获取状态失败: {status['error']}")
            return

        print(f"📚 书架条目: {status['weread_shelf_items']} 个")
        print(f"   ├─ 电子书: {status['weread_ebooks']} 本")
        print(f"   └─ 有声书: {status['weread_albums']} 个")
        print(f"📓 有笔记的书籍: {status['weread_books_with_notes']} 本")
        print(f"🗂️  Notion 已同步: {status['notion_synced_books']} 本")


async def example_reading_stats():
    """示例：查看阅读统计"""
    print("📈 示例：阅读统计")

    async with SyncService.from_config(config) as sync_service:
        data = await sync_service.get_reading_stats(mode="monthly")

    total_seconds = int(data.get("totalReadTime") or 0)
    hours, remainder = divmod(total_seconds, 3600)
    print(f"⏱️  本月阅读时长: {hours} 小时 {remainder // 60} 分钟")
    print(f"📅 有效阅读天数: {data.get('readDays', 0)} 天")


async def example_sync_single(book_id: str):
    """示例：同步单本书籍"""
    print(f"📖 示例：同步单本书籍 {book_id}")

    async with SyncService.from_config(config) as sync_service:
        result = await sync_service.sync_book_by_id(book_id)

    if result.success:
        print(f"✅ 同步成功: {result.book_title}")
        print(f"   📝 笔记新增/更新: {result.notes_synced} 条")
        print(f"   🗑️  笔记归档: {result.notes_deleted} 条")
    else:
        print(f"❌ 同步失败: {result.error_message}")


async def example_sync_all():
    """示例：同步所有书籍"""
    print("📚 示例：同步所有书籍")

    async with SyncService.from_config(config) as sync_service:
        results = await sync_service.sync_all_books()

    success_count = sum(1 for result in results if result.success)
    print(f"✅ 同步完成: {success_count}/{len(results)} 本书籍")


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("🚀 微信读书到 Notion 同步示例")
    print("=" * 50)

    try:
        await example_get_status()
        print()
        await example_reading_stats()
        print()

        # 需要时取消注释并填入实际书籍 ID：
        # await example_sync_single("43697528")
        # await example_sync_all()

        print("✅ 示例执行完成")
    except Exception as exc:
        print(f"❌ 执行失败: {exc}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
