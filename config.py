# 项目配置示例
# 复制此文件为 config.py 并填入实际值

# ================================
# 微信读书配置
# ================================
# 获取方法：
# 1. 打开浏览器，访问 https://weread.qq.com/
# 2. 登录你的微信读书账号
# 3. 打开开发者工具 (F12)
# 4. 在 Network 标签页中刷新页面
# 5. 找到任意一个请求，复制 Cookie 值
# Cookie配置在config.local.py中
try:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from config_local import WEREAD_COOKIE as _COOKIE
    WEREAD_COOKIE = _COOKIE
except (ImportError, ModuleNotFoundError):
    WEREAD_COOKIE = "your_weread_cookie_here"

# ================================
# Notion API 配置
# ================================
# 获取方法：
# 1. 访问 https://www.notion.so/my-integrations
# 2. 点击 "New integration" 创建新的集成
# 3. 填写基本信息，获取 Internal Integration Token
# 4. 在你的 Notion 页面中，点击右上角的 "Share"
# 5. 添加你刚创建的集成，并给予适当权限
NOTION_TOKEN = "secret_your_notion_integration_token"

# Notion 数据库 ID
# 获取方法：
# 1. 在 Notion 中创建一个数据库页面
# 2. 复制页面链接，格式如：https://www.notion.so/your-workspace/database-name-32位字符串?v=view-id
# 3. 32位字符串就是数据库 ID
NOTION_DATABASE_ID = "your_notion_database_id"

# 如果没有数据库，可以设置父页面 ID，程序会自动创建数据库
# NOTION_PARENT_PAGE_ID = "your_parent_page_id"

# ================================
# 同步配置
# ================================
# 同步选项
SYNC_ALL_BOOKS = True          # 是否同步所有书籍（包括没有笔记的）
SYNC_FINISHED_BOOKS = True     # 是否同步已读完的书籍
SYNC_UNFINISHED_BOOKS = True   # 是否同步未读完的书籍
SYNC_BOOK_COVERS = True        # 是否同步书籍封面
SYNC_BOOK_REVIEWS = True       # 是否同步书评
SYNC_READING_NOTES = True      # 是否同步读书笔记

# 批量同步设置
BATCH_SIZE = 5                 # 每批次同步的书籍数量
BATCH_DELAY = 2                # 批次之间的延迟（秒）

# ================================
# API 限制配置
# ================================
# 微信读书 API 限制
WEREAD_RATE_LIMIT = 5          # 每60秒最多请求次数
WEREAD_REQUEST_DELAY = 1       # 请求之间的延迟（秒）

# Notion API 限制
NOTION_RATE_LIMIT = 3          # 每秒最多请求次数
NOTION_REQUEST_TIMEOUT = 60    # 请求超时时间（秒）

# ================================
# 日志配置
# ================================
LOG_LEVEL = "INFO"             # 日志级别: DEBUG, INFO, WARNING, ERROR
LOG_FILE = "logs/sync.log"     # 日志文件路径
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_MAX_SIZE = 10 * 1024 * 1024  # 日志文件最大大小（字节）
LOG_BACKUP_COUNT = 5           # 保留的日志文件数量

# ================================
# 高级配置
# ================================
# 数据过滤
MIN_NOTE_LENGTH = 10           # 最小笔记长度（字符）
EXCLUDE_PRIVATE_NOTES = False  # 是否排除私有笔记
EXCLUDE_EMPTY_BOOKS = True     # 是否排除没有内容的书籍

# 重试配置
MAX_RETRIES = 3                # 最大重试次数
RETRY_DELAY = 2                # 重试延迟（秒）

# 缓存配置
ENABLE_CACHE = True            # 是否启用缓存
CACHE_EXPIRE_TIME = 3600       # 缓存过期时间（秒） 