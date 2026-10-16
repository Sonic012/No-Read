import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src import settings as config
from src.sync.service import SyncService
from src.weread.gateway import WeReadAuthError, WeReadGateway, WeReadUpgradeRequired


def setup_logging() -> None:
    """设置日志配置"""
    Path(config.LOG_FILE).parent.mkdir(exist_ok=True)

    formatter = logging.Formatter(
        getattr(config, "LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(config, "LOG_LEVEL", "INFO"))
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    try:
        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler(
            config.LOG_FILE,
            maxBytes=getattr(config, "LOG_MAX_SIZE", 10 * 1024 * 1024),
            backupCount=getattr(config, "LOG_BACKUP_COUNT", 5),
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as exc:
        print(f"⚠️  无法设置文件日志: {exc}")


def _validate_config() -> bool:
    logger = logging.getLogger(__name__)
    missing = []
    if not _weread_api_key():
        missing.append("WEREAD_API_KEY（到 https://weread.qq.com/r/weread-skills 扫码获取）")
    if not getattr(config, "NOTION_TOKEN", None):
        missing.append("NOTION_TOKEN")
    if not getattr(config, "NOTION_DATABASE_ID", None):
        missing.append("NOTION_DATABASE_ID")

    if missing:
        logger.error("❌ 配置不完整，请通过环境变量或 config.py 设置：")
        for item in missing:
            logger.error("   - %s", item)
        return False
    return True


def _weread_api_key() -> Optional[str]:
    """API Key 走统一配置加载：环境变量优先，config.py 兜底。"""
    return getattr(config, "WEREAD_API_KEY", None) or os.getenv("WEREAD_API_KEY") or None


async def verify_all() -> bool:
    """全量对账：逐条比对微信读书上游与 Notion，确认没有丢数据。"""
    logger = logging.getLogger(__name__)
    if not _validate_config():
        return False

    try:
        async with SyncService.from_config(config) as sync_service:
            return await sync_service.verify_full()
    except Exception as exc:
        logger.error("❌ 对账失败：%s", exc)
        return False


async def sync_all_books(full: bool = False) -> bool:
    """同步所有书籍、笔记与阅读历史"""
    logger = logging.getLogger(__name__)
    if not _validate_config():
        return False

    try:
        async with SyncService.from_config(config) as sync_service:
            logger.info("📊 检查同步状态...")
            status = await sync_service.get_sync_status()
            if "error" in status:
                logger.error("❌ 获取同步状态失败: %s", status["error"])
                return False

            logger.info(
                "📚 微信读书书架: %s 个条目（电子书 %s / 有声书 %s），%s 本有笔记",
                status["weread_shelf_items"],
                status["weread_ebooks"],
                status["weread_albums"],
                status["weread_books_with_notes"],
            )
            logger.info("📝 Notion 已同步: %s 本", status["notion_synced_books"])

            actions = await sync_service.ensure_notion_schema()
            for action in actions:
                logger.info("🔧 %s", action)

            results = await sync_service.sync_all_books(
                include_finished=getattr(config, "SYNC_FINISHED_BOOKS", True),
                include_unfinished=getattr(config, "SYNC_UNFINISHED_BOOKS", True),
                full=full,
            )

            history = await sync_service.sync_reading_history()

            success_count = sum(1 for result in results if result.success)
            failed = [result for result in results if not result.success]

            logger.info("🎉 同步完成！")
            logger.info("   ✅ 成功: %s 本", success_count)
            logger.info("   ❌ 失败: %s 本", len(failed))
            logger.info("   📝 笔记新增/更新: %s 条", sum(r.notes_synced for r in results))
            logger.info("   🗑️  笔记归档: %s 条", sum(r.notes_deleted for r in results))
            logger.info(
                "   📈 阅读记录: 新增 %s / 更新 %s",
                history.get("created", 0),
                history.get("updated", 0),
            )

            for result in failed:
                logger.warning("   - %s: %s", result.book_title, result.error_message)

            return success_count > 0
    except Exception as exc:
        logger.error("❌ 同步过程中发生错误: %s", exc, exc_info=True)
        return False


async def setup_notion() -> bool:
    """只补齐 Notion 模板结构，不拉取微信读书数据（无需 API Key）。"""
    logger = logging.getLogger(__name__)
    notion_token = getattr(config, "NOTION_TOKEN", None)
    notion_database_id = getattr(config, "NOTION_DATABASE_ID", None)
    if not notion_token or not notion_database_id:
        logger.error("❌ 请在 config.py 中设置 NOTION_TOKEN 与 NOTION_DATABASE_ID")
        return False

    try:
        from src.notion.template_client import NotionTemplateClient

        client = NotionTemplateClient(token=notion_token, database_id=notion_database_id)
        actions = await client.ensure_schema()
        if actions:
            print("\n🔧 已补齐 Notion 结构:")
            for action in actions:
                print(f"   - {action}")
        else:
            print("\n✅ Notion 结构已是最新，无需改动")
        return True
    except Exception as exc:
        logger.error("❌ 补齐 Notion 结构失败: %s", exc, exc_info=True)
        return False


async def sync_single_book(book_id: str) -> bool:
    """同步单本书籍"""
    logger = logging.getLogger(__name__)
    if not _validate_config():
        return False

    try:
        async with SyncService.from_config(config) as sync_service:
            result = await sync_service.sync_book_by_id(book_id)
            if result.success:
                logger.info("✅ 书籍同步成功: %s", result.book_title)
                logger.info("   📝 笔记新增/更新: %s 条", result.notes_synced)
                logger.info("   🗑️  笔记归档: %s 条", result.notes_deleted)
                return True
            logger.error("❌ 书籍同步失败: %s", result.error_message)
            return False
    except Exception as exc:
        logger.error("❌ 同步过程中发生错误: %s", exc, exc_info=True)
        return False


async def show_status() -> bool:
    """显示同步状态"""
    logger = logging.getLogger(__name__)
    if not _validate_config():
        return False

    try:
        async with SyncService.from_config(config) as sync_service:
            status = await sync_service.get_sync_status()
            if "error" in status:
                logger.error("❌ 获取状态失败: %s", status["error"])
                return False

            print("\n📊 同步状态:")
            print(f"   📚 书架条目: {status['weread_shelf_items']} 个")
            print(f"      ├─ 电子书: {status['weread_ebooks']} 本")
            print(f"      └─ 有声书: {status['weread_albums']} 个")
            print(f"   📓 有笔记的书籍: {status['weread_books_with_notes']} 本")
            print(f"   🗂️  Notion 已同步: {status['notion_synced_books']} 本")
            print(f"   🕐 检查时间: {status['last_check_time']}")
            return True
    except Exception as exc:
        logger.error("❌ 获取状态时发生错误: %s", exc, exc_info=True)
        return False


async def show_stats(mode: str = "monthly") -> bool:
    """展示微信读书阅读统计（阅读时长/天数/排行/偏好）"""
    logger = logging.getLogger(__name__)
    if not _weread_api_key():
        logger.error("❌ 未配置 WEREAD_API_KEY")
        return False

    mode_labels = {"weekly": "本周", "monthly": "本月", "annually": "本年", "overall": "总计"}
    if mode not in mode_labels:
        logger.error("❌ mode 只能是 weekly / monthly / annually / overall")
        return False

    try:
        gateway = WeReadGateway(
            api_key=_weread_api_key(),
            skill_version=getattr(config, "WEREAD_SKILL_VERSION", None),
            rate_limit=getattr(config, "WEREAD_RATE_LIMIT", 30),
        )
        async with gateway:
            data = await gateway.readdata(mode=mode)
    except Exception as exc:
        logger.error("❌ 获取阅读统计失败: %s", exc)
        return False

    total = int(data.get("totalReadTime") or 0)
    print(f"\n📊 阅读统计（{mode_labels[mode]}）")
    print(f"   ⏱️  总时长: {_human_duration(total)}")
    print(f"   📅 有效阅读天数: {data.get('readDays', 0)} 天")
    print(f"   📈 日均时长: {_human_duration(int(data.get('dayAverageReadTime') or 0))}")

    longest = data.get("readLongest") or []
    if longest:
        print("   🏆 读得最多:")
        for item in longest[:5]:
            book = item.get("book") or {}
            album = item.get("albumInfo") or {}
            name = book.get("title") or album.get("name") or "未知"
            print(f"      - {name}: {_human_duration(int(item.get('readTime') or 0))}")

    if data.get("preferCategoryWord"):
        print(f"   🏷️  {data['preferCategoryWord']}")
    if data.get("preferTimeWord"):
        print(f"   🕐 {data['preferTimeWord']}")
    return True


async def check_services() -> bool:
    """只读检查微信读书官方网关与 Notion 是否可用。"""
    logger = logging.getLogger(__name__)
    ok = True

    print("\n🔎 连通性检查")
    sources = ", ".join(f"{key}={value}" for key, value in getattr(config, "SOURCES", {}).items())
    print(f"   配置来源: {sources}")

    api_key = _weread_api_key()
    if not api_key:
        print("   ❌ 微信读书: 未配置 WEREAD_API_KEY")
        ok = False
    else:
        gateway = WeReadGateway(
            api_key=api_key,
            skill_version=getattr(config, "WEREAD_SKILL_VERSION", None),
            rate_limit=getattr(config, "WEREAD_RATE_LIMIT", 30),
        )
        try:
            async with gateway:
                catalog = await gateway.list_api()
                shelf = await gateway.shelf_sync()
            books = shelf.get("books") or []
            albums = shelf.get("albums") or []
            apis = catalog.get("api_list") or catalog.get("apis") or catalog
            api_count = len(apis) if isinstance(apis, list) else "未知"
            print(f"   ✅ 微信读书: 网关可用，开放接口 {api_count} 个")
            print(f"      书架：{len(books) + len(albums) + (1 if shelf.get('mp') else 0)} 个条目"
                  f"（电子书 {len(books)} / 有声书 {len(albums)}）")
        except WeReadUpgradeRequired as exc:
            print(f"   ⚠️  微信读书: {exc}")
            ok = False
        except WeReadAuthError as exc:
            print(f"   ❌ 微信读书: {exc}")
            ok = False
        except Exception as exc:
            print(f"   ❌ 微信读书: {type(exc).__name__} - {exc}")
            ok = False

    notion_token = getattr(config, "NOTION_TOKEN", None)
    notion_database_id = getattr(config, "NOTION_DATABASE_ID", None)
    if not notion_token or not notion_database_id:
        print("   ❌ Notion: 未配置 NOTION_TOKEN / NOTION_DATABASE_ID")
        ok = False
    else:
        try:
            from src.notion.template_client import NotionTemplateClient

            client = NotionTemplateClient(token=notion_token, database_id=notion_database_id)
            await client._ensure_ready()
            titles = ", ".join(sorted(client.database_ids))
            print(f"   ✅ Notion: 已发现数据库 [{titles}]")
        except Exception as exc:
            print(f"   ❌ Notion: {type(exc).__name__} - {exc}")
            ok = False

    return ok


def _human_duration(seconds: int) -> str:
    hours, remainder = divmod(max(int(seconds), 0), 3600)
    minutes = remainder // 60
    if hours and minutes:
        return f"{hours} 小时 {minutes} 分钟"
    if hours:
        return f"{hours} 小时"
    return f"{minutes} 分钟"


def show_help() -> None:
    print("""
📚 WeRead → Notion 同步工具（官方 Agent API 版）

用法：
  uv run python main.py sync                同步所有书籍 + 笔记 + 阅读历史
  uv run python main.py sync --full         忽略本地缓存，全量刷新一遍
  uv run python main.py sync <book_id>      同步指定书籍
  uv run python main.py setup-notion        只补齐 Notion 模板结构（新增属性/数据库）
  uv run python main.py status              查看同步状态
  uv run python main.py verify              全量对账：逐条比对上游与 Notion，确认不丢数据
  uv run python main.py stats [mode]        查看阅读统计
                                            mode: weekly / monthly / annually / overall
  uv run python main.py check               检查微信读书网关与 Notion 连通性
  uv run python main.py help                查看帮助

配置：
  1. 到 https://weread.qq.com/r/weread-skills 扫码获取 API Key（wrk- 开头）
  2. 在 config.py 中设置 WEREAD_API_KEY / NOTION_TOKEN / NOTION_DATABASE_ID
""")


async def main() -> None:
    """主函数"""
    setup_logging()
    args = sys.argv[1:]

    if not args or args[0] == "sync":
        rest = [item for item in args[1:] if item != "--full"]
        full = "--full" in args[1:]
        if rest:
            success = await sync_single_book(rest[0])
        else:
            success = await sync_all_books(full=full)
    elif args[0] == "setup-notion":
        success = await setup_notion()
    elif args[0] == "status":
        success = await show_status()
    elif args[0] == "verify":
        success = await verify_all()
    elif args[0] == "stats":
        success = await show_stats(args[1] if len(args) > 1 else "monthly")
    elif args[0] == "check":
        success = await check_services()
    elif args[0] in ("help", "-h", "--help"):
        show_help()
        sys.exit(0)
    else:
        print(f"❌ 未知命令: {args[0]}")
        print("使用 'uv run python main.py help' 查看帮助信息")
        sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  用户中断操作")
        sys.exit(1)
    except Exception as exc:
        print(f"❌ 程序执行失败: {exc}")
        sys.exit(1)
