# 📚 WeRead → Notion 同步工具

把微信读书的**书架、笔记、划线和阅读时长**同步到 Notion，方便统一管理和回顾。

数据来自**微信读书官方 Agent API**（扫码授权，不再抓取网页接口、不再需要 Cookie）。

## ✨ 功能特点

- 🔐 **官方 API**：用扫码换取的 API Key 鉴权，身份自动识别，无需手工复制 Cookie
- 📖 **书架同步**：书名、作者、封面、分类、ISBN、出版社
- 📊 **阅读进度与时长**：阅读百分比、累计阅读时长（「X小时Y分钟」）、最后阅读时间、想读/在读/已读
- 📝 **笔记同步**：按章节归类的划线、想法/章节点评
- 💭 **书评同步**：整本书的个人点评
- 🎧 **有声书**：书架里的专辑/有声书同样纳入
- 🔁 **全量对账**：上游新增/修改/删除都会反映到 Notion，不是只追加
- 🛡️ **不丢数据**：抓取失败时跳过删除对账，长文本落页面正文，绝不误删截断
- ⚡ **增量与缓存**：书籍元数据本地缓存，`sync --full` 可强制全量刷新
- 📈 **阅读历史**：按年回溯全部阅读时长，写入「阅读记录」库
- 📊 **阅读统计**：查看本周/本月/本年/总计的阅读时长、天数、偏好

## 🛠️ 环境要求

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## 🚀 快速开始

### 1. 安装依赖

```bash
uv sync
```

### 2. 配置

```bash
cp config.example.py config.py
```

然后填写 `config.py`：

**微信读书 API Key**

1. 打开官方入口 <https://weread.qq.com/r/weread-skills>
2. 微信扫码绑定你的微信读书账号
3. 复制生成的 API Key（形如 `wrk-xxxxxxxx`），填入 `WEREAD_API_KEY`
   （也可以不改文件，直接 `export WEREAD_API_KEY=wrk-xxxx`，环境变量优先）

**Notion**

1. 访问 <https://www.notion.so/my-integrations> 创建集成，拿到 Internal Integration Token
2. 在准备存放数据的 Notion 页面右上角 `Share`，把该集成加进去
3. 把 Token 填到 `NOTION_TOKEN`；`NOTION_DATABASE_ID` 可以是「书架」数据库 ID，
   也可以是包含 `书架/分类/作者/笔记/划线` 五个子库的**父页面 ID**（程序会自动发现子库）

### 3. 校验配置

```bash
uv run python main.py check
```

## 📖 使用

```bash
uv run python main.py sync            # 同步所有书籍
uv run python main.py sync --full     # 忽略本地元数据缓存，全量刷新一遍
uv run python main.py sync <book_id>  # 同步指定书籍
uv run python main.py setup-notion    # 只补齐 Notion 结构（新增 笔记ID 属性 / 阅读记录库 / 粒度选项）
uv run python main.py status          # 查看同步状态
uv run python main.py verify          # 全量对账：逐条比对上游与 Notion，确认不丢数据
uv run python main.py stats monthly   # 阅读统计：weekly / monthly / annually / overall
uv run python main.py check           # 检查微信读书网关与 Notion 连通性
uv run python main.py help            # 帮助
```

## ⏰ 自动同步（GitHub Actions）

本项目默认**不本地部署**，由 GitHub Actions 每天定时拉取并同步；本地只用于功能开发和联调。

- 工作流：`.github/workflows/sync.yml`，每天 `09:07 (Asia/Shanghai)` 触发，也支持手动 `Run workflow`（可勾选全量刷新）
- 配置全部来自 Repository Secrets，仓库里不含任何密钥：

| Secret | 说明 |
|---|---|
| `WEREAD_API_KEY` | 微信读书 API Key，`wrk-` 开头 |
| `NOTION_TOKEN` | Notion Integration Token |
| `NOTION_DATABASE_ID` | 父页面 ID 或「书架」数据库 ID |

写入 Secrets：

```bash
gh secret set WEREAD_API_KEY --body "wrk-xxxx"
gh secret set NOTION_TOKEN --body "ntn_xxxx"
gh secret set NOTION_DATABASE_ID --body "xxxxxxxx"
```

配置读取顺序为 **环境变量 > `config.py` > 内置默认值**（见 `src/settings.py`）：
CI 上没有 `config.py`，只靠 Secrets；本地保留 `config.py` 也不会影响 CI。

> 首次跑通后建议执行一次全量刷新：`gh workflow run sync.yml -f full=true`

工作流结束前会跑一次 `main.py verify`：按 `书籍ID`/`笔记ID` 逐条比对微信读书与 Notion，
只要有缺失或多余就判定失败，避免「看起来同步成功、实际少了几条」。

### 不丢数据的几条硬约束

- 笔记/划线按 `笔记ID` 真 upsert，重复同步幂等
- 只有当某个来源**确认取全**时才允许按「上游已删除」清理；没取全时只写入不清理
- Notion 429/5xx 自动退避重试，避免限流把一本书的笔记写成一半
- 书籍 ID / 笔记本索引分页不完整时，跳过该书的清理对账

## 🗂️ 同步到 Notion 的结构

| Notion 库 | 内容 | 关键属性 |
|---|---|---|
| 书架 | 电子书 + 有声书 | 书名、书籍ID、作者(relation)、分类(relation)、封面、ISBN、出版社、阅读进度、阅读时长、最后阅读时间、状态 |
| 分类 | 分类主数据 | 名称 |
| 作者 | 作者主数据 | 名称 |
| 笔记 | 想法 / 章节点评 / 书评 | 内容、书籍(relation)、章节、类型、创建时间 |
| 划线 | 划线原文 | 内容、书籍(relation)、章节、样式、创建时间 |
| 阅读记录 | 每日 / 每月 / 每年阅读时长 | 日期、阅读时长(秒)、时长、年、月、粒度(日/月/年) |

## 📚 文档

- [微信读书官方 API 数据字典](docs/official-api.md)：各接口可得字段、与 Notion 属性的映射、尚未同步的数据

## 🧪 测试

```bash
uv run --with pytest pytest tests/ -q
```

## 📄 许可

见 [LICENSE](LICENSE)
