# 📚 WeRead to Notion 同步工具

这是一个基于 Python 的工具，可以将你的微信读书数据（包括书架、读书笔记、书评等）同步到 Notion 数据库中，方便你在 Notion 中管理和回顾你的阅读记录。

## ✨ 功能特点

- 📖 **完整书籍信息**：同步书名、作者、封面、分类、阅读进度等
- 📝 **读书笔记**：同步所有划线记录和想法笔记，按章节组织
- 💭 **书评同步**：同步你写的书评和评分
- 🔄 **增量更新**：支持增量同步，只更新有变化的内容
- 🎯 **灵活配置**：可配置同步哪些类型的书籍和内容
- 📊 **详细日志**：提供详细的同步日志和状态报告
- 🚀 **异步处理**：使用异步 I/O 提高同步效率

## 🛠️ 环境要求

- Python 3.12+
- uv (Python 包管理器)

## 🚀 快速开始

### 1. 安装 uv

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**
```bash
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**或者使用 pip:**
```bash
pip install uv
```

### 2. 克隆项目

```bash
git clone <你的仓库地址>
cd No-Read
```

### 3. 安装依赖

```bash
# uv 会自动创建虚拟环境并安装所有依赖
uv sync
```

### 4. 配置设置

```bash
# 复制配置文件模板
cp config.example.py config.py
```

然后编辑 `config.py` 文件，填入以下必需的配置：

#### 获取微信读书 Cookie

1. 打开浏览器，访问 [https://weread.qq.com/](https://weread.qq.com/)
2. 登录你的微信读书账号
3. 打开开发者工具 (F12)
4. 在 Network 标签页中刷新页面
5. 找到任意一个请求，复制 Cookie 值
6. 在 `config.py` 中设置：
```python
WEREAD_COOKIE = "你的微信读书Cookie"
```

#### 获取 Notion API Token

1. 访问 [https://www.notion.so/my-integrations](https://www.notion.so/my-integrations)
2. 点击 "New integration" 创建新的集成
3. 填写基本信息，获取 Internal Integration Token
4. 在 `config.py` 中设置：
```python
NOTION_TOKEN = "secret_你的Notion集成Token"
```

#### 设置 Notion 数据库

**方法一：使用现有数据库**
1. 在 Notion 中创建一个数据库页面
2. 复制页面链接，格式如：`https://www.notion.so/your-workspace/database-name-32位字符串?v=view-id`
3. 32位字符串就是数据库 ID
4. 在数据库页面点击右上角的 "Share"
5. 添加你刚创建的集成，并给予适当权限
6. 在 `config.py` 中设置：
```python
NOTION_DATABASE_ID = "你的数据库ID"
```

**方法二：自动创建数据库**
1. 在 Notion 中创建一个页面作为父页面
2. 获取父页面 ID（方法同上）
3. 在 `config.py` 中设置：
```python
NOTION_PARENT_PAGE_ID = "你的父页面ID"
```
程序会自动在该页面下创建书籍数据库。

### 5. 运行同步

```bash
# 同步所有书籍
uv run python main.py sync

# 或者使用 src/main.py
uv run python src/main.py sync

# 查看同步状态
uv run python main.py status

# 同步指定书籍
uv run python main.py sync <书籍ID>

# 查看帮助
uv run python main.py help
```

## 📖 使用说明

### 命令行选项

```bash
# 同步所有书籍（默认命令）
python main.py sync

# 同步指定书籍
python main.py sync <book_id>

# 查看同步状态
python main.py status

# 显示帮助信息
python main.py help
```

### 配置选项

在 `config.py` 中可以配置以下选项：

```python
# 同步选项
SYNC_ALL_BOOKS = True          # 是否同步所有书籍（包括没有笔记的）
SYNC_FINISHED_BOOKS = True     # 是否同步已读完的书籍
SYNC_UNFINISHED_BOOKS = True   # 是否同步未读完的书籍
SYNC_BOOK_COVERS = True        # 是否同步书籍封面
SYNC_BOOK_REVIEWS = True       # 是否同步书评
SYNC_READING_NOTES = True      # 是否同步读书笔记

# API 限制
WEREAD_RATE_LIMIT = 5          # 微信读书每60秒最多请求次数
NOTION_RATE_LIMIT = 3          # Notion每秒最多请求次数

# 数据过滤
MIN_NOTE_LENGTH = 10           # 最小笔记长度（字符）
EXCLUDE_PRIVATE_NOTES = False  # 是否排除私有笔记
EXCLUDE_EMPTY_BOOKS = True     # 是否排除没有内容的书籍
```

## 📊 Notion 数据库结构

同步后，Notion 数据库会包含以下字段：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 书名 | Title | 书籍标题 |
| 作者 | Rich Text | 书籍作者 |
| 书籍ID | Rich Text | 微信读书中的书籍ID |
| 分类 | Select | 书籍分类 |
| 阅读进度 | Number (%) | 阅读进度百分比 |
| 评分 | Number | 书籍评分 |
| 完成阅读 | Checkbox | 是否读完 |
| 最后阅读时间 | Date | 最后阅读时间 |

每个书籍页面还会包含：
- 📖 书籍封面（如果有）
- 📖 书籍简介
- 📝 读书笔记（按章节分组）
- 💭 我的书评

## 🔧 高级配置

### 日志配置

```python
LOG_LEVEL = "INFO"             # 日志级别
LOG_FILE = "logs/sync.log"     # 日志文件路径
LOG_MAX_SIZE = 10 * 1024 * 1024  # 日志文件最大大小
LOG_BACKUP_COUNT = 5           # 保留的日志文件数量
```

### 重试配置

```python
MAX_RETRIES = 3                # 最大重试次数
RETRY_DELAY = 2                # 重试延迟（秒）
```

## 🐛 故障排除

### 常见问题

**Q: 提示 "微信读书Cookie过期了"**
A: 重新获取微信读书 Cookie 并更新 `config.py`

**Q: 提示 "Notion API 权限不足"**
A: 确保在 Notion 数据库页面中添加了你的集成，并给予了适当权限

**Q: 同步速度很慢**
A: 可以调整 `WEREAD_RATE_LIMIT` 和 `NOTION_RATE_LIMIT` 配置，但不要设置过高以免被限制

**Q: 某些书籍同步失败**
A: 查看日志文件了解具体错误原因，通常是网络问题或 API 限制

### 日志文件

程序会在 `logs/sync.log` 中记录详细的运行日志，包括：
- 同步进度
- 错误信息
- API 请求详情

### 调试模式

如需更详细的调试信息，可以在 `config.py` 中设置：
```python
LOG_LEVEL = "DEBUG"
```

## 🔄 定期同步

### 使用 cron（Linux/macOS）

```bash
# 编辑 crontab
crontab -e

# 添加定时任务（每天早上8点同步）
0 8 * * * cd /path/to/No-Read && /path/to/uv run python main.py sync
```

### 使用 Windows 任务计划程序

1. 打开"任务计划程序"
2. 创建基本任务
3. 设置触发器（如每天）
4. 设置操作：启动程序
   - 程序/脚本：`python`
   - 参数：`main.py sync`
   - 起始位置：项目目录路径

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE) 文件。

## ⚠️ 免责声明

- 本工具仅供个人学习和使用
- 请遵守微信读书和 Notion 的服务条款
- 使用本工具产生的任何问题，作者不承担责任
- 建议适度使用，避免频繁请求

## 🙏 致谢

感谢微信读书和 Notion 提供的优秀服务！
