import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import config
except ImportError:
    print("❌ 配置文件不存在！")
    print("请复制 config.example.py 为 config.py 并填入正确的配置信息")
    print("详细配置说明请查看 config.example.py 中的注释")
    sys.exit(1)

from src.sync.service import SyncService


def setup_logging():
    """设置日志配置"""
    # 创建日志目录
    log_dir = Path(config.LOG_FILE).parent
    log_dir.mkdir(exist_ok=True)
    
    # 配置日志格式
    formatter = logging.Formatter(
        getattr(config, 'LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    
    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(config, 'LOG_LEVEL', 'INFO'))
    
    # 清除现有处理器
    root_logger.handlers.clear()
    
    # 添加控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # 添加文件处理器
    try:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            config.LOG_FILE,
            maxBytes=getattr(config, 'LOG_MAX_SIZE', 10 * 1024 * 1024),
            backupCount=getattr(config, 'LOG_BACKUP_COUNT', 5),
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"⚠️  无法设置文件日志: {e}")


async def sync_all_books():
    """同步所有书籍"""
    logger = logging.getLogger(__name__)
    
    try:
        # 获取配置
        weread_cookie = getattr(config, 'WEREAD_COOKIE', None)
        notion_token = getattr(config, 'NOTION_TOKEN', None)
        notion_database_id = getattr(config, 'NOTION_DATABASE_ID', None)
        
        if not weread_cookie:
            logger.error("❌ 未配置微信读书 Cookie，请在 config.py 中设置 WEREAD_COOKIE")
            return False
        
        if not notion_token:
            logger.error("❌ 未配置 Notion Token，请在 config.py 中设置 NOTION_TOKEN")
            return False
        
        if not notion_database_id:
            logger.error("❌ 未配置 Notion 数据库 ID，请在 config.py 中设置 NOTION_DATABASE_ID")
            return False
        
        # 创建同步服务
        async with SyncService(
            weread_cookie=weread_cookie,
            notion_token=notion_token,
            notion_database_id=notion_database_id
        ) as sync_service:
            
            # 获取同步状态
            logger.info("📊 检查同步状态...")
            status = await sync_service.get_sync_status()
            
            if 'error' in status:
                logger.error(f"❌ 获取同步状态失败: {status['error']}")
                return False
            
            logger.info(f"📚 微信读书: {status['weread_total_books']} 本书籍，{status['weread_books_with_notes']} 本有笔记")
            logger.info(f"📝 Notion: 已同步 {status['notion_synced_books']} 本书籍")
            
            # 执行同步
            include_finished = getattr(config, 'SYNC_FINISHED_BOOKS', True)
            include_unfinished = getattr(config, 'SYNC_UNFINISHED_BOOKS', True)
            
            results = await sync_service.sync_all_books(
                include_finished=include_finished,
                include_unfinished=include_unfinished
            )
            
            # 统计结果
            success_count = sum(1 for r in results if r.success)
            failed_count = len(results) - success_count
            total_notes = sum(r.notes_synced for r in results)
            total_reviews = sum(r.reviews_synced for r in results)
            
            logger.info(f"🎉 同步完成!")
            logger.info(f"   ✅ 成功: {success_count} 本")
            logger.info(f"   ❌ 失败: {failed_count} 本")
            logger.info(f"   📝 笔记: {total_notes} 条")
            logger.info(f"   💭 书评: {total_reviews} 条")
            
            # 显示失败的书籍
            if failed_count > 0:
                logger.warning("❌ 同步失败的书籍:")
                for result in results:
                    if not result.success:
                        logger.warning(f"   - {result.book_title}: {result.error_message}")
            
            return success_count > 0
            
    except Exception as e:
        logger.error(f"❌ 同步过程中发生错误: {str(e)}", exc_info=True)
        return False


async def sync_single_book(book_id: str):
    """同步单本书籍"""
    logger = logging.getLogger(__name__)
    
    try:
        # 获取配置
        weread_cookie = getattr(config, 'WEREAD_COOKIE', None)
        notion_token = getattr(config, 'NOTION_TOKEN', None)
        notion_database_id = getattr(config, 'NOTION_DATABASE_ID', None)
        
        if not all([weread_cookie, notion_token, notion_database_id]):
            logger.error("❌ 配置不完整，请检查 config.py")
            return False
        
        # 创建同步服务
        async with SyncService(
            weread_cookie=weread_cookie,
            notion_token=notion_token,
            notion_database_id=notion_database_id
        ) as sync_service:
            
            result = await sync_service.sync_book_by_id(book_id)
            
            if result.success:
                logger.info(f"✅ 书籍同步成功: {result.book_title}")
                logger.info(f"   📝 笔记: {result.notes_synced} 条")
                logger.info(f"   💭 书评: {result.reviews_synced} 条")
                return True
            else:
                logger.error(f"❌ 书籍同步失败: {result.error_message}")
                return False
                
    except Exception as e:
        logger.error(f"❌ 同步过程中发生错误: {str(e)}", exc_info=True)
        return False


async def show_status():
    """显示同步状态"""
    logger = logging.getLogger(__name__)
    
    try:
        # 获取配置
        weread_cookie = getattr(config, 'WEREAD_COOKIE', None)
        notion_token = getattr(config, 'NOTION_TOKEN', None)
        notion_database_id = getattr(config, 'NOTION_DATABASE_ID', None)
        
        if not all([weread_cookie, notion_token, notion_database_id]):
            logger.error("❌ 配置不完整，请检查 config.py")
            return False
        
        # 创建同步服务
        async with SyncService(
            weread_cookie=weread_cookie,
            notion_token=notion_token,
            notion_database_id=notion_database_id
        ) as sync_service:
            
            status = await sync_service.get_sync_status()
            
            if 'error' in status:
                logger.error(f"❌ 获取状态失败: {status['error']}")
                return False
            
            print("\n📊 同步状态:")
            print(f"   📚 微信读书总书籍: {status['weread_total_books']} 本")
            print(f"   📝 有笔记的书籍: {status['weread_books_with_notes']} 本")
            print(f"   🗂️  Notion 已同步: {status['notion_synced_books']} 本")
            print(f"   🕐 检查时间: {status['last_check_time']}")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ 获取状态时发生错误: {str(e)}", exc_info=True)
        return False


def show_help():
    """显示帮助信息"""
    print("""
📚 微信读书到 Notion 同步工具

使用方法:
  python src/main.py [command] [options]

命令:
  sync          同步所有书籍到 Notion (默认)
  sync <book_id>  同步指定书籍
  status        显示同步状态
  help          显示此帮助信息

配置:
  请先复制 config.example.py 为 config.py 并填入正确的配置信息
  
  必需配置:
  - WEREAD_COOKIE: 微信读书 Cookie
  - NOTION_TOKEN: Notion API Token  
  - NOTION_DATABASE_ID: Notion 数据库 ID

示例:
  python src/main.py sync                    # 同步所有书籍
  python src/main.py sync 12345678           # 同步指定书籍
  python src/main.py status                  # 查看状态
  
更多信息请查看 README.md
""")


async def main():
    """主函数"""
    # 设置日志
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # 解析命令行参数
    args = sys.argv[1:]
    
    if not args or args[0] == "sync":
        if len(args) > 1:
            # 同步指定书籍
            book_id = args[1]
            logger.info(f"🚀 开始同步书籍: {book_id}")
            success = await sync_single_book(book_id)
        else:
            # 同步所有书籍
            logger.info("🚀 开始同步所有书籍")
            success = await sync_all_books()
        
        sys.exit(0 if success else 1)
        
    elif args[0] == "status":
        logger.info("📊 获取同步状态")
        success = await show_status()
        sys.exit(0 if success else 1)
        
    elif args[0] in ["help", "-h", "--help"]:
        show_help()
        sys.exit(0)
        
    else:
        print(f"❌ 未知命令: {args[0]}")
        print("使用 'python src/main.py help' 查看帮助信息")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 程序执行失败: {str(e)}")
        sys.exit(1) 