# 微信读书同步到Notion - 使用指南

## 项目简介

本项目实现了微信读书数据自动同步到Notion，包括书籍信息、阅读进度、阅读时长、笔记和划线等数据。

## 功能特点

- ✅ **完整数据同步**：书籍信息、阅读进度、阅读时长、作者、分类等
- ✅ **智能去重**：根据书籍ID判断，已存在则更新，不存在则创建
- ✅ **关联数据库**：自动创建和关联作者、分类数据库
- ✅ **数据准确性**：从`bookProgress`数组获取正确的阅读时长和进度
- ✅ **简单易用**：单一脚本文件，支持参数化同步

## 快速开始

### 1. 配置微信读书Cookie

编辑 `config_local.py` 文件，填入您的微信读书Cookie：

```python
WEREAD_COOKIE = "your_cookie_here"
```

**获取Cookie方法**：
1. 访问 https://weread.qq.com/
2. 登录您的微信读书账号
3. 打开浏览器开发者工具（F12）
4. 在Network标签中刷新页面
5. 找到任意请求，复制Cookie值

### 2. 配置Notion Integration

编辑 `config_local.py` 文件，填入您的Notion Token：

```python
NOTION_TOKEN = "ntn_xxxxx"
```

**获取Token方法**：
1. 访问 https://www.notion.so/my-integrations
2. 点击"New integration"创建新集成
3. 填写基本信息，复制生成的Token
4. 在Notion页面中添加此Integration的连接权限

### 3. 运行同步

```bash
# 同步所有书籍
python3.11 weread_sync.py --all

# 同步前10本书（测试）
python3.11 weread_sync.py 10

# 同步前5本书
python3.11 weread_sync.py 5
```

## 数据库结构

### 书架数据库

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 书名 | title | 书籍标题 |
| 书籍ID | rich_text | 微信读书书籍唯一ID |
| 作者 | relation | 关联到作者数据库 |
| 阅读时长 | rich_text | 格式化的阅读时长（如"20小时43分"） |
| 阅读进度 | number | 阅读进度百分比（0-100） |
| 年份标签 | select | 最后阅读年份 |
| 封面 | files | 书籍封面图片 |
| ISBN | rich_text | 书籍ISBN号 |
| 出版社 | rich_text | 出版社名称 |
| 状态 | select | 阅读状态（已读/在读/想读） |
| 最后阅读时间 | date | 最后一次阅读的时间 |
| 分类 | relation | 关联到分类数据库 |

### 作者数据库

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 作者名 | title | 作者姓名 |

### 分类数据库

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 分类名 | title | 分类名称 |

## 数据来源说明

### 正确的字段映射

项目从微信读书API的`bookProgress`数组获取准确的阅读数据：

- **阅读时长**：`bookProgress[].readingTime`（秒）→ 格式化为"XX小时XX分"
- **阅读进度**：`bookProgress[].progress`（百分比）
- **更新时间**：`bookProgress[].updateTime`（时间戳）→ 提取年份

### 为什么不使用`books`数组中的数据？

`books`数组中的`readingTime`和`progress`字段都是0，不准确。必须使用`bookProgress`数组中的数据。

## 常见问题

### Q: 为什么有些书没有阅读时长和进度？

A: 只有在微信读书中实际阅读过的书籍才会有`bookProgress`数据。未阅读的书籍这些字段会显示为0。

### Q: 如何避免重复数据？

A: 脚本会根据书籍ID自动判断：
- 如果Notion中已存在该书籍ID，则更新数据
- 如果不存在，则创建新记录

### Q: 同步失败怎么办？

A: 检查以下几点：
1. Cookie是否过期（重新获取）
2. Notion Token是否有效
3. Integration是否有权限访问数据库
4. 网络连接是否正常

### Q: 如何查看同步日志？

A: 如果使用后台运行：
```bash
tail -f /tmp/sync_all.log
```

## 技术细节

### 去重逻辑

```python
def find_existing_book(book_id):
    """根据书籍ID查找已存在的记录"""
    url = f"https://api.notion.com/v1/databases/{BOOKSHELF_DB_ID}/query"
    payload = {
        "filter": {
            "property": "书籍ID",
            "rich_text": {
                "equals": book_id
            }
        }
    }
    response = requests.post(url, headers=NOTION_HEADERS, json=payload)
    if response.status_code == 200:
        results = response.json().get("results", [])
        if results:
            return results[0]
    return None
```

### 作者关联

脚本会自动：
1. 在作者数据库中查找作者
2. 如果不存在，创建新作者
3. 将书籍关联到作者

### 阅读时长格式化

```python
if reading_time > 0:
    hours = reading_time // 3600
    minutes = (reading_time % 3600) // 60
    if hours > 0:
        reading_time_text = f"{hours}小时{minutes}分"
    else:
        reading_time_text = f"{minutes}分钟"
else:
    reading_time_text = "0分钟"
```

## 项目结构

```
No-Read/
├── weread_sync.py          # 主同步脚本
├── config.py               # 配置文件模板
├── config_local.py         # 本地配置（不提交到Git）
├── README.md               # 项目说明
├── USAGE.md                # 使用指南（本文件）
└── .gitignore              # Git忽略文件
```

## 更新日志

### 2026-01-11

- ✅ 修复字段类型映射错误
- ✅ 实现智能去重逻辑
- ✅ 简化为单一同步脚本
- ✅ 使用`bookProgress`获取准确数据
- ✅ 支持作者自动创建和关联
- ✅ 阅读时长格式化为文本
- ✅ 完整同步145本书籍

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！

## 联系方式

如有问题，请在GitHub上提交Issue。
