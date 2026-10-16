# 项目配置示例
# 复制此文件为 config.py 并填入实际值
#
# 配置读取顺序：环境变量 > config.py > 内置默认值（见 src/settings.py）
# GitHub Actions 上不需要本文件，配置放在 Repository Secrets 里即可；
# 因此任何一项都可以不改文件，直接用同名环境变量覆盖，例如
#   export NOTION_TOKEN=ntn_xxx

# ================================
# 微信读书配置（官方 Agent API）
# ================================
# 微信读书官方已提供 Agent Skill + API Gateway，不再需要手工复制 Cookie。
#
# 获取 API Key：
# 1. 打开 https://weread.qq.com/r/weread-skills （官方入口）
# 2. 用微信扫码绑定你的微信读书账号
# 3. 复制生成的 API Key（形如 wrk-xxxxxxxx）
WEREAD_API_KEY = "wrk-你的APIKey"

# 官方会随接口调整更新 Skill 版本；回包出现 upgrade_info 时程序会明确提示。
# 默认取官方 SKILL.md 中的 version 字段，一般无需修改。
WEREAD_SKILL_VERSION = "1.0.5"

# ================================
# Notion API 配置
# ================================
# 获取方法：
# 1. 访问 https://www.notion.so/my-integrations
# 2. 点击 "New integration" 创建新的集成
# 3. 填写基本信息，获取 Internal Integration Token
# 4. 在你的 Notion 页面中，点击右上角的 "Share"
# 5. 添加你刚创建的集成，并给予适当权限
NOTION_TOKEN = "ntn_你的Notion集成Token"

# Notion 数据库 ID
# 可以是「书架」数据库 ID，也可以是包含 书架/分类/作者/笔记/划线
# 这 5 个子数据库的父页面 ID（程序会自动发现子数据库）。
NOTION_DATABASE_ID = "你的数据库或父页面ID"

# ================================
# 同步配置
# ================================
SYNC_FINISHED_BOOKS = True     # 是否同步已读完的书籍
SYNC_UNFINISHED_BOOKS = True   # 是否同步未读完的书籍（含仅加入书架的）
SYNC_BOOK_COVERS = True        # 是否同步书籍封面
SYNC_BOOK_NOTES = True         # 是否同步划线/想法笔记

# ================================
# API 限制配置
# ================================
# 微信读书 Agent Gateway 限流（每 60 秒最多请求次数）
WEREAD_RATE_LIMIT = 30
# 每本书之间的额外延迟（秒），用于进一步降低触发限流的概率
WEREAD_REQUEST_DELAY = 0.5

# Notion API 限制
NOTION_RATE_LIMIT = 3          # 每秒最多请求次数

# ================================
# 元数据缓存
# ================================
# 书籍详情/进度变化很慢，缓存后每日同步只需拉取新增或有变化的书籍。
BOOK_CACHE_FILE = "logs/book_metadata.json"
BOOK_CACHE_TTL = 604800        # 缓存有效期（秒），默认 7 天；设为 -1 表示永不过期

# ================================
# 日志配置
# ================================
LOG_LEVEL = "INFO"             # 日志级别: DEBUG, INFO, WARNING, ERROR
LOG_FILE = "logs/sync.log"     # 日志文件路径
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_MAX_SIZE = 10 * 1024 * 1024  # 日志文件最大大小（字节）
LOG_BACKUP_COUNT = 5           # 保留的日志文件数量

# ================================
# 数据过滤
# ================================
EXCLUDE_PRIVATE_NOTES = False  # 是否排除私有划线/想法
