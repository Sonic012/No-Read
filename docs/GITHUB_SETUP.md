# GitHub Actions 配置指南

本文档介绍如何配置 GitHub Actions 环境变量和密钥，以运行微信读书到 Notion 的同步工具。

## 📋 目录

- [概述](#概述)
- [环境变量类型](#环境变量类型)
- [配置步骤](#配置步骤)
- [必需配置](#必需配置)
- [可选配置](#可选配置)
- [测试配置](#测试配置)
- [故障排除](#故障排除)

## 概述

GitHub Actions 使用两种类型的环境变量：
- **Secrets**: 敏感信息（如 API 密钥、Cookie）
- **Variables**: 非敏感配置（如开关、数值）

## 环境变量类型

### 🔐 Secrets (敏感信息)
这些变量在 GitHub 中存储为加密的 secrets，不会在日志中显示：

| 变量名 | 描述 | 获取方法 |
|--------|------|----------|
| `WEREAD_COOKIE` | 微信读书 Cookie | 见下方说明 |
| `NOTION_TOKEN` | Notion API Token | 见下方说明 |
| `NOTION_DATABASE_ID` | Notion 数据库 ID | 见下方说明 |
| `NOTION_PARENT_PAGE_ID` | Notion 父页面 ID | 可选 |

### ⚙️ Variables (配置参数)
这些变量用于控制同步行为：

| 变量名 | 默认值 | 描述 |
|--------|--------|------|
| `SYNC_ALL_BOOKS` | `true` | 是否同步所有书籍 |
| `SYNC_FINISHED_BOOKS` | `true` | 是否同步已读完的书籍 |
| `SYNC_UNFINISHED_BOOKS` | `true` | 是否同步未读完的书籍 |
| `SYNC_BOOK_COVERS` | `true` | 是否同步书籍封面 |
| `SYNC_BOOK_REVIEWS` | `true` | 是否同步书评 |
| `SYNC_READING_NOTES` | `true` | 是否同步读书笔记 |
| `BATCH_SIZE` | `5` | 每批次同步的书籍数量 |
| `BATCH_DELAY` | `2` | 批次之间的延迟（秒） |
| `WEREAD_RATE_LIMIT` | `5` | 微信读书 API 限制 |
| `WEREAD_REQUEST_DELAY` | `1` | 请求之间的延迟（秒） |
| `NOTION_RATE_LIMIT` | `3` | Notion API 限制 |
| `NOTION_REQUEST_TIMEOUT` | `60` | 请求超时时间（秒） |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `MIN_NOTE_LENGTH` | `10` | 最小笔记长度 |
| `EXCLUDE_PRIVATE_NOTES` | `false` | 是否排除私有笔记 |
| `EXCLUDE_EMPTY_BOOKS` | `true` | 是否排除空书籍 |
| `MAX_RETRIES` | `3` | 最大重试次数 |
| `RETRY_DELAY` | `2` | 重试延迟（秒） |
| `ENABLE_CACHE` | `true` | 是否启用缓存 |
| `CACHE_EXPIRE_TIME` | `3600` | 缓存过期时间（秒） |

## 配置步骤

### 1. 访问仓库设置

1. 进入你的 GitHub 仓库
2. 点击 **Settings** 标签
3. 在左侧菜单中找到 **Secrets and variables** → **Actions**

### 2. 配置 Secrets

点击 **New repository secret** 按钮，添加以下必需 secrets：

#### WEREAD_COOKIE
获取方法：
1. 打开浏览器，访问 https://weread.qq.com/
2. 登录你的微信读书账号
3. 按 F12 打开开发者工具
4. 切换到 **Network** 标签页
5. 刷新页面
6. 找到任意一个请求，复制完整的 Cookie 值

#### NOTION_TOKEN
获取方法：
1. 访问 https://www.notion.so/my-integrations
2. 点击 **New integration**
3. 填写基本信息（名称、工作区等）
4. 创建后复制 **Internal Integration Token**

#### NOTION_DATABASE_ID
获取方法：
1. 在 Notion 中创建一个数据库页面
2. 复制页面链接，格式如：
   `https://www.notion.so/your-workspace/database-name-32位字符串?v=view-id`
3. 32位字符串就是数据库 ID

#### NOTION_PARENT_PAGE_ID (可选)
如果不想使用现有数据库，可以设置父页面 ID：
1. 在 Notion 中创建一个页面
2. 复制页面链接中的页面 ID

### 3. 配置 Variables

点击 **Variables** 标签页，然后点击 **New repository variable**，添加配置参数。

## 必需配置

以下配置是运行工作流所必需的：

```bash
# Secrets (必需)
WEREAD_COOKIE=your_weread_cookie_here
NOTION_TOKEN=secret_your_notion_integration_token
NOTION_DATABASE_ID=your_notion_database_id

# Variables (可选，有默认值)
SYNC_ALL_BOOKS=true
SYNC_FINISHED_BOOKS=true
SYNC_UNFINISHED_BOOKS=true
BATCH_SIZE=5
LOG_LEVEL=INFO
```

## 可选配置

以下配置可以根据需要调整：

```bash
# 同步选项
SYNC_BOOK_COVERS=true
SYNC_BOOK_REVIEWS=true
SYNC_READING_NOTES=true

# 性能配置
BATCH_DELAY=2
WEREAD_RATE_LIMIT=5
WEREAD_REQUEST_DELAY=1
NOTION_RATE_LIMIT=3
NOTION_REQUEST_TIMEOUT=60

# 过滤配置
MIN_NOTE_LENGTH=10
EXCLUDE_PRIVATE_NOTES=false
EXCLUDE_EMPTY_BOOKS=true

# 重试配置
MAX_RETRIES=3
RETRY_DELAY=2

# 缓存配置
ENABLE_CACHE=true
CACHE_EXPIRE_TIME=3600
```

## 测试配置

### 1. 手动触发工作流

1. 进入仓库的 **Actions** 标签页
2. 选择 **Sync WeChat Reading to Notion** 工作流
3. 点击 **Run workflow** 按钮
4. 选择分支并运行

### 2. 检查日志

工作流运行后：
1. 点击运行记录
2. 查看 **Inject configuration** 步骤的输出
3. 确认配置是否正确注入
4. 检查 **Run sync** 步骤是否成功

### 3. 下载日志

工作流完成后：
1. 在运行记录页面找到 **sync-logs** 工件
2. 下载并查看详细的同步日志

## 故障排除

### 常见问题

#### 1. 配置注入失败
- 检查环境变量名称是否正确
- 确认变量值格式是否正确
- 查看工作流日志中的错误信息

#### 2. 微信读书认证失败
- 确认 `WEREAD_COOKIE` 是否有效
- Cookie 可能已过期，需要重新获取
- 检查微信读书账号是否正常

#### 3. Notion API 错误
- 确认 `NOTION_TOKEN` 是否正确
- 检查集成是否有正确的权限
- 确认 `NOTION_DATABASE_ID` 是否存在

#### 4. 同步失败
- 检查网络连接
- 确认 API 限制设置是否合理
- 查看详细错误日志

### 调试技巧

1. **启用详细日志**：设置 `LOG_LEVEL=DEBUG`
2. **减少批量大小**：设置 `BATCH_SIZE=1`
3. **增加延迟**：设置 `BATCH_DELAY=5`
4. **检查网络**：确认 GitHub Actions 可以访问外部 API

### 获取帮助

如果遇到问题：
1. 查看工作流日志中的详细错误信息
2. 检查 GitHub Actions 的状态页面
3. 在仓库 Issues 中报告问题

## 安全注意事项

1. **不要提交敏感信息**：确保 `config.py` 文件不包含真实的 API 密钥
2. **定期轮换密钥**：定期更新微信读书 Cookie 和 Notion Token
3. **限制权限**：只给 Notion 集成必要的权限
4. **监控使用**：定期检查同步日志和 API 使用情况